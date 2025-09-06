from __future__ import annotations
"""Data access utilities for Statistics 5000.

All direct interaction with Anki collection objects that provides data to the UI
should reside here to keep the main __init__ lean.
"""
from typing import Optional, Any, cast, Dict, List, Tuple
from aqt import mw
from anki.decks import DeckId
from anki.models import NotetypeId
import datetime as _dt
from math import isfinite


def deck_card_count(deck_id: Optional[int]) -> int:
    if not mw.col:
        return 0
    if deck_id is None:
        return mw.col.card_count()
    deck = mw.col.decks.get(cast(DeckId, deck_id))
    if not deck:
        return mw.col.card_count()
    deck_name = deck["name"].replace('"', '\"')
    query = f'deck:"{deck_name}"'
    return len(mw.col.find_cards(query))


def list_decks() -> list[tuple[int, str]]:
    if not mw.col:
        return []
    try:
        return [(d.id, d.name) for d in mw.col.decks.all_names_and_ids()]
    except Exception:
        # fallback shape
        out: list[tuple[int, str]] = []
        for d in mw.col.decks.all_names_and_ids():  # type: ignore
            did = getattr(d, 'id', None) or getattr(d, 'did', None)
            name = getattr(d, 'name', None)
            if did is not None and name is not None:
                out.append((did, name))
        return out


def list_models() -> list[dict[str, Any]]:
    if not mw.col:
        return []
    return mw.col.models.all()  # type: ignore[return-value]


def get_model(model_id: int) -> Optional[dict[str, Any]]:
    if not mw.col:
        return None
    return mw.col.models.get(cast(NotetypeId, model_id))  # type: ignore[return-value]


def model_templates(model_id: int) -> list[dict[str, Any]]:
    m = get_model(model_id)
    if not m:
        return []
    # Modern Anki: templates under 'tmpls'
    return m.get('tmpls', [])  # type: ignore[return-value]


def model_name(model_id: Optional[int]) -> str:
    if model_id is None:
        return "(Any Model)"
    m = get_model(model_id)
    if not m:
        return "(Missing Model)"
    return m.get('name', '(Unnamed Model)')


def template_progress(model_id: Optional[int], template_ords: Optional[list[int]], deck_id: Optional[int], granularity: str, forecast: bool = False) -> dict:
    """Return cumulative counts per template per time bucket plus optional forecast.

    labels: full label list (includes future buckets if forecast enabled)
    series: list of dicts with keys:
        label: template name
        data: cumulative counts for historical buckets (length = historic buckets)
        forecast: optional list aligned to labels (None for pre-forecast buckets, last actual value repeated at start, then projected cumulative values until total)
        forecastCompletionIndex: index in labels where full total is first reached (if forecast shown)
        forecastCompletionDate: label string (date) for completion point
    """
    if not mw.col:
        return {"labels": [], "series": []}
    col = mw.col
    if not getattr(col, 'db', None):
        return {"labels": [], "series": []}

    # Build search query
    parts: list[str] = []
    if model_id is not None:
        parts.append(f"mid:{model_id}")
    if deck_id is not None:
        deck = mw.col.decks.get(cast(DeckId, deck_id))
        if deck:
            dn = deck["name"].replace('"', '\"')
            parts.append(f'deck:"{dn}"')
    query = " ".join(parts)
    cids = mw.col.find_cards(query) if query else mw.col.find_cards("")
    if not cids:
        return {"labels": [], "series": []}

    cards = [mw.col.get_card(cid) for cid in cids]
    if template_ords is not None:
        cards = [c for c in cards if c.ord in template_ords]
    if not cards:
        return {"labels": [], "series": []}

    # Earliest review per card
    revlog_rows = col.db.all(  # type: ignore[attr-defined]
        f"SELECT cid, MIN(id) FROM revlog WHERE cid IN ({','.join(str(i) for i in cids)}) GROUP BY cid"
    )
    first_map = {cid: rid for cid, rid in revlog_rows}

    # Template names
    template_name_cache: Dict[int, str] = {}
    if model_id is not None:
        m = get_model(model_id)
        if m:
            for t in m.get('tmpls', []):  # type: ignore
                template_name_cache[t.get('ord')] = t.get('name') or f"Card {t.get('ord',0)+1}"

    # Helper conversions (unchanged)
    def label_from_date(dt: _dt.date) -> str:
        if granularity == "days":
            return dt.strftime("%Y-%m-%d")
        if granularity == "weeks":
            year, week, _ = dt.isocalendar()
            return f"{year}-W{week:02d}"
        if granularity == "months":
            return f"{dt.year}-{dt.month:02d}"
        if granularity == "quarters":
            q = (dt.month - 1)//3 + 1
            return f"{dt.year}-Q{q}"
        if granularity == "years":
            return str(dt.year)
        return dt.strftime("%Y-%m-%d")

    def bucket_start(dt: _dt.datetime) -> _dt.date:
        if granularity == "days":
            return dt.date()
        if granularity == "weeks":
            iso = dt.isocalendar()
            return _dt.date.fromisocalendar(iso[0], iso[1], 1)
        if granularity == "months":
            return _dt.date(dt.year, dt.month, 1)
        if granularity == "quarters":
            start_month = ((dt.month - 1)//3)*3 + 1
            return _dt.date(dt.year, start_month, 1)
        if granularity == "years":
            return _dt.date(dt.year, 1, 1)
        return dt.date()

    def next_bucket(d: _dt.date) -> _dt.date:
        if granularity == "days":
            return d + _dt.timedelta(days=1)
        if granularity == "weeks":
            return d + _dt.timedelta(weeks=1)
        if granularity == "months":
            year = d.year + (1 if d.month == 12 else 0)
            month = 1 if d.month == 12 else d.month + 1
            return _dt.date(year, month, 1)
        if granularity == "quarters":
            month = d.month + 3
            year = d.year
            if month > 12:
                month -= 12
                year += 1
            return _dt.date(year, month, 1)
        if granularity == "years":
            return _dt.date(d.year + 1, 1, 1)
        return d + _dt.timedelta(days=1)

    # Aggregate studied counts
    per_template_counts: Dict[int, Dict[str, int]] = {}
    template_total_cards: Dict[int, int] = {}
    bucket_dates_set: set[_dt.date] = set()

    for c in cards:
        template_total_cards[c.ord] = template_total_cards.get(c.ord, 0) + 1
        rid = first_map.get(c.id)
        if not rid:
            continue  # not studied yet
        dt = _dt.datetime.fromtimestamp(rid/1000)
        bdate = bucket_start(dt)
        bucket_dates_set.add(bdate)
        label = label_from_date(bdate)
        tdict = per_template_counts.setdefault(c.ord, {})
        tdict[label] = tdict.get(label, 0) + 1

    if not bucket_dates_set:
        return {"labels": [], "series": []}

    historic_dates = sorted(bucket_dates_set)
    # Extend to current bucket (today) so chart shows inactivity plateau
    today_bucket = bucket_start(_dt.datetime.now())
    if historic_dates and historic_dates[-1] < today_bucket:
        cur_ext = historic_dates[-1]
        while cur_ext < today_bucket:
            cur_ext = next_bucket(cur_ext)
            historic_dates.append(cur_ext)
    historic_labels = [label_from_date(d) for d in historic_dates]

    series = []
    max_future_buckets = 0
    forecast_data_cache: Dict[int, list[Optional[int]]] = {}
    completion_index_cache: Dict[int, int] = {}

    if forecast:
        # Advanced forecast per template: combine weighted moving average of recent deltas with linear regression slope.
        for ord_, total_cards in template_total_cards.items():
            # Build cumulative historical counts for this template
            running = 0
            studied_counts: list[int] = []
            for lab in historic_labels:
                running += per_template_counts.get(ord_, {}).get(lab, 0)
                studied_counts.append(running)
            if not studied_counts:
                continue
            remaining = total_cards - studied_counts[-1]
            if remaining <= 0:
                continue
            # Deltas per bucket
            deltas = [studied_counts[i] - studied_counts[i-1] for i in range(1, len(studied_counts))]
            # Weighted moving average (weights 1..k for last up to 5 deltas)
            recent_d = deltas[-5:] if deltas else []
            if recent_d:
                weights = list(range(1, len(recent_d)+1))
                wma = sum(d*w for d, w in zip(recent_d, weights)) / sum(weights)
            else:
                wma = 1.0
            # Linear regression slope on cumulative curve (simple least squares vs index)
            n = len(studied_counts)
            if n >= 2:
                xs = list(range(n))
                sum_x = sum(xs)
                sum_y = sum(studied_counts)
                sum_x2 = sum(x*x for x in xs)
                sum_xy = sum(x*y for x, y in zip(xs, studied_counts))
                denom = (n * sum_x2 - sum_x * sum_x)
                if denom != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / denom
                else:
                    slope = wma
            else:
                slope = wma
            # Combine (favor recency slightly more)
            base_gain = 0.6 * wma + 0.4 * slope
            if base_gain <= 0:
                base_gain = 1.0
            # If very small remaining, damp overshoot
            # Project future buckets until completion
            forecast_cum: float = float(studied_counts[-1])
            forecast_points: list[int] = []
            rem = remaining
            # Adaptive gain: gently decay if remaining is small to avoid long tail overshoot
            while rem > 0 and len(forecast_points) < 1000:  # safety cap
                # Adjust gain so we don't jump far over remaining
                gain = min(rem, max(1.0, min(base_gain, rem * 0.75 + 1)))
                forecast_cum += gain
                rem -= gain
                forecast_points.append(int(round(forecast_cum)))
                # Optionally re-estimate base_gain after each step using slight decay to simulate slowing near completion
                base_gain *= 0.98 if rem < remaining * 0.3 else 1.0
            buckets_needed = len(forecast_points)
            if buckets_needed == 0:
                continue
            max_future_buckets = max(max_future_buckets, buckets_needed)
            # Series alignment: (hist_len -1) nulls, last actual, then forecast points
            forecast_series = [None]*(len(studied_counts)-1) + [studied_counts[-1]] + forecast_points
            forecast_data_cache[ord_] = forecast_series
            # Completion index relative to full labels (will update after full label build); temporarily store offset position
            completion_index_cache[ord_] = len(forecast_series) - 1  # position within forecast series itself

    # Build final labels (extend by max future buckets if any forecast)
    full_labels = historic_labels
    if forecast and max_future_buckets > 0:
        last_date = historic_dates[-1]
        future_dates: list[_dt.date] = []
        cur = last_date
        for _ in range(max_future_buckets):
            cur = next_bucket(cur)
            future_dates.append(cur)
        full_labels = historic_labels + [label_from_date(d) for d in future_dates]

    # Global max total cards for Y-axis scaling
    global_max_total = max(template_total_cards.values()) if template_total_cards else 0

    # Compose series entries with forecast metadata
    for ord_, total_cards in template_total_cards.items():
        running = 0
        hist_data: list[int] = []
        for lab in historic_labels:
            running += per_template_counts.get(ord_, {}).get(lab, 0)
            hist_data.append(running)
        if not hist_data:
            continue
        label_name = template_name_cache.get(ord_, f"Template {ord_+1}")
        entry: Dict[str, Any] = {"label": label_name, "data": hist_data, "totalCards": total_cards}
        if forecast and ord_ in forecast_data_cache:
            fc = forecast_data_cache[ord_]
            # Pad to full length with None so forecast line stops after completion
            if len(fc) < len(full_labels):
                fc = fc + [None] * (len(full_labels) - len(fc))
            # Clamp any forecast overshoot to totalCards
            fc = [min(v, total_cards) if isinstance(v, int) and v is not None else v for v in fc]
            # Determine completion index inside padded array: first index where value >= total_cards
            completion_idx = None
            for i, v in enumerate(fc):
                if v is not None and v >= total_cards:
                    completion_idx = i
                    break
            if completion_idx is None:
                completion_idx = len(fc) - 1
            entry["forecast"] = fc
            entry["forecastCompletionIndex"] = completion_idx
            if 0 <= completion_idx < len(full_labels):
                entry["forecastCompletionDate"] = full_labels[completion_idx]
        series.append(entry)

    return {"labels": full_labels, "series": series, "yMaxTotal": global_max_total}
