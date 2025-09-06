from __future__ import annotations

"""Data access utilities.

All direct interaction with Anki collection objects that provides data to the UI
should reside here.
"""
import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple, cast

from anki.cards import Card, CardId
from anki.decks import DeckId
from anki.models import NotetypeId
from aqt import mw


def deck_card_count(deck_id: Optional[int]) -> int:
    """Return the total number of cards in a given deck, or all decks."""
    if not mw.col:
        return 0
    if deck_id is None:
        return mw.col.card_count()
    deck = mw.col.decks.get(cast(DeckId, deck_id))
    if not deck:
        return mw.col.card_count()
    deck_name = deck["name"].replace('"', '"')
    query = f'deck:"{deck_name}"'
    return len(mw.col.find_cards(query))


def list_decks() -> list[tuple[int, str]]:
    """Return a list of all deck IDs and names."""
    if not mw.col:
        return []
    try:
        return [(d.id, d.name) for d in mw.col.decks.all_names_and_ids()]
    except Exception:
        # fallback for older anki versions
        out: list[tuple[int, str]] = []
        for d in mw.col.decks.all_names_and_ids():  # type: ignore
            did = getattr(d, "id", None) or getattr(d, "did", None)
            name = getattr(d, "name", None)
            if did is not None and name is not None:
                out.append((did, name))
        return out


def list_models() -> list[dict[str, Any]]:
    """Return a list of all note types (models)."""
    if not mw.col:
        return []
    return mw.col.models.all()  # type: ignore[return-value]


def get_model(model_id: int) -> Optional[dict[str, Any]]:
    """Return the model dictionary for a given model ID."""
    if not mw.col:
        return None
    return mw.col.models.get(cast(NotetypeId, model_id))  # type: ignore[return-value]


def model_templates(model_id: int) -> list[dict[str, Any]]:
    """Return the list of templates for a given model ID."""
    m = get_model(model_id)
    if not m:
        return []
    return m.get("tmpls", [])  # type: ignore[return-value]


def model_name(model_id: Optional[int]) -> str:
    """Return the name of a model, or a placeholder if not found."""
    if model_id is None:
        return "(Any Model)"
    m = get_model(model_id)
    if not m:
        return "(Missing Model)"
    return m.get("name", "(Unnamed Model)")


def _get_cards_for_analysis(
    model_id: Optional[int],
    deck_id: Optional[int],
    template_ords: Optional[list[int]],
) -> list[Card]:
    """Fetch cards based on model, deck, and template filters."""
    if not mw.col:
        return []

    parts: list[str] = []
    if model_id is not None:
        parts.append(f"mid:{model_id}")
    if deck_id is not None:
        deck = mw.col.decks.get(cast(DeckId, deck_id))
        if deck:
            dn = deck["name"].replace('"', '"')
            parts.append(f'deck:"{dn}"')
    query = " ".join(parts)
    cids = mw.col.find_cards(query) if query else mw.col.find_cards("")
    if not cids:
        return []

    cards = [mw.col.get_card(cid) for cid in cids]
    if template_ords is not None:
        cards = [c for c in cards if c.ord in template_ords]

    return cards


def _get_first_review_timestamps(cids: list[CardId]) -> dict[int, int]:
    """For a list of card IDs, get the timestamp of their first review."""
    if not mw.col or not mw.col.db or not cids:
        return {}
    revlog_rows = mw.col.db.all(
        f"SELECT cid, MIN(id) FROM revlog WHERE cid IN ({','.join(str(i) for i in cids)}) GROUP BY cid"
    )
    return {cid: rid for cid, rid in revlog_rows}


def _get_template_names(model_id: Optional[int]) -> dict[int, str]:
    """Get a map of template ordinals to names for a given model."""
    if model_id is None:
        return {}
    m = get_model(model_id)
    if not m:
        return {}
    return {
        t.get("ord"): t.get("name") or f"Card {t.get('ord', 0) + 1}"
        for t in m.get("tmpls", [])
    }


class _TimeBucketer:
    """Handles time-based bucketing of data."""

    def __init__(self, granularity: str):
        self.granularity = granularity

    def label_from_date(self, dt: _dt.date) -> str:
        """Generate a label for a given date based on granularity."""
        if self.granularity == "days":
            return dt.strftime("%Y-%m-%d")
        if self.granularity == "weeks":
            year, week, _ = dt.isocalendar()
            return f"{year}-W{week:02d}"
        if self.granularity == "months":
            return f"{dt.year}-{dt.month:02d}"
        if self.granularity == "quarters":
            q = (dt.month - 1) // 3 + 1
            return f"{dt.year}-Q{q}"
        if self.granularity == "years":
            return str(dt.year)
        return dt.strftime("%Y-%m-%d")

    def bucket_start(self, dt: _dt.datetime) -> _dt.date:
        """Find the start date of the bucket for a given datetime."""
        if self.granularity == "days":
            return dt.date()
        if self.granularity == "weeks":
            iso = dt.isocalendar()
            return _dt.date.fromisocalendar(iso[0], iso[1], 1)
        if self.granularity == "months":
            return _dt.date(dt.year, dt.month, 1)
        if self.granularity == "quarters":
            start_month = ((dt.month - 1) // 3) * 3 + 1
            return _dt.date(dt.year, start_month, 1)
        if self.granularity == "years":
            return _dt.date(dt.year, 1, 1)
        return dt.date()

    def next_bucket(self, d: _dt.date) -> _dt.date:
        """Get the start date of the next bucket."""
        if self.granularity == "days":
            return d + _dt.timedelta(days=1)
        if self.granularity == "weeks":
            return d + _dt.timedelta(weeks=1)
        if self.granularity == "months":
            year = d.year + (1 if d.month == 12 else 0)
            month = 1 if d.month == 12 else d.month + 1
            return _dt.date(year, month, 1)
        if self.granularity == "quarters":
            month = d.month + 3
            year = d.year
            if month > 12:
                month -= 12
                year += 1
            return _dt.date(year, month, 1)
        if self.granularity == "years":
            return _dt.date(d.year + 1, 1, 1)
        return d + _dt.timedelta(days=1)


def _calculate_historic_progress(
    cards: list[Card], first_map: dict[int, int], bucketer: _TimeBucketer
) -> tuple[dict, dict, list, list]:
    """Aggregate historical card study counts into time buckets."""
    per_template_counts: Dict[int, Dict[str, int]] = {}
    template_total_cards: Dict[int, int] = {}
    bucket_dates_set: set[_dt.date] = set()

    for c in cards:
        template_total_cards[c.ord] = template_total_cards.get(c.ord, 0) + 1
        rid = first_map.get(c.id)
        if not rid:
            continue  # not studied yet
        dt = _dt.datetime.fromtimestamp(rid / 1000)
        bdate = bucketer.bucket_start(dt)
        bucket_dates_set.add(bdate)
        label = bucketer.label_from_date(bdate)
        tdict = per_template_counts.setdefault(c.ord, {})
        tdict[label] = tdict.get(label, 0) + 1

    if not bucket_dates_set:
        return {}, {}, [], []

    historic_dates = sorted(bucket_dates_set)
    today_bucket = bucketer.bucket_start(_dt.datetime.now())
    if historic_dates and historic_dates[-1] < today_bucket:
        cur_ext = historic_dates[-1]
        while cur_ext < today_bucket:
            cur_ext = bucketer.next_bucket(cur_ext)
            historic_dates.append(cur_ext)
    historic_labels = [bucketer.label_from_date(d) for d in historic_dates]

    return per_template_counts, template_total_cards, historic_dates, historic_labels


def _calculate_forecast(
    ord_: int,
    total_cards: int,
    historic_labels: list[str],
    per_template_counts: dict,
    template_review_dates: dict,
    bucketer: _TimeBucketer,
) -> tuple[list[Optional[int]], int, str, str]:
    """Calculate forecast data for a single template using only last 30 days of activity.
    
    If there is no activity in the last 30 days, the forecast stays flat at the current level.
    Otherwise, calculates completion rate based on cards studied in the last 30 days only.
    """
    running = 0
    studied_counts: list[int] = []
    for lab in historic_labels:
        running += per_template_counts.get(ord_, {}).get(lab, 0)
        studied_counts.append(running)

    if not studied_counts or studied_counts[-1] >= total_cards:
        return [], -1, "", ""

    dates_list = sorted(template_review_dates.get(ord_, []))
    if not dates_list:
        return [], -1, "", ""

    # Filter to only use data from the last 30 days for rate calculation
    today = _dt.date.today()
    thirty_days_ago = today - _dt.timedelta(days=30)
    recent_dates = [d for d in dates_list if d >= thirty_days_ago]
    
    if not recent_dates:
        # No activity in last 30 days, return flat forecast
        fc_series = [None] * (len(studied_counts) - 1) + [studied_counts[-1]]
        return fc_series, len(studied_counts) - 1, "", ""
    
    earliest = recent_dates[0]
    latest = recent_dates[-1]
    recent_cards_studied = len(recent_dates)
    days_elapsed = max(1, (latest - earliest).days + 1)
    rate_per_day = recent_cards_studied / days_elapsed if days_elapsed > 0 else recent_cards_studied
    if rate_per_day <= 0:
        # No meaningful rate, return flat forecast
        fc_series = [None] * (len(studied_counts) - 1) + [studied_counts[-1]]
        return fc_series, len(studied_counts) - 1, "", ""

    total_studied = studied_counts[-1]
    remaining = total_cards - total_studied
    days_needed = remaining / rate_per_day
    completion_date = latest + _dt.timedelta(days=int(days_needed + 0.999))
    completion_iso = completion_date.isoformat()

    comp_bucket_start = bucketer.bucket_start(
        _dt.datetime.combine(completion_date, _dt.time())
    )

    # This logic determines how many future buckets we need to project
    # It's complex and might be simplified, but for now, we keep it.
    # The key is to find the completion index and date in terms of buckets.
    temp_future_dates: List[_dt.date] = []
    
    last_hist_date = bucketer.bucket_start(_dt.datetime.fromisoformat(dates_list[-1].isoformat()))
    cur_bs = last_hist_date

    while cur_bs < comp_bucket_start and len(temp_future_dates) < 1000:
        cur_bs = bucketer.next_bucket(cur_bs)
        temp_future_dates.append(cur_bs)

    completion_index = (
        len(historic_labels) + len(temp_future_dates) - 1
        if temp_future_dates
        else len(historic_labels) - 1
    )
    
    future_labels = [bucketer.label_from_date(d) for d in temp_future_dates]
    all_labels = historic_labels + future_labels
    
    completion_date_label = all_labels[completion_index] if completion_index < len(all_labels) else ""

    # Create the forecast data array
    fc_series = [None] * (len(studied_counts) - 1) + [studied_counts[-1]]
    buckets_remaining = completion_index - (len(studied_counts) - 1)
    if buckets_remaining > 0:
        remaining_cards = total_cards - studied_counts[-1]
        for i in range(1, buckets_remaining + 1):
            val = studied_counts[-1] + int(
                round(remaining_cards * (i / buckets_remaining))
            )
            fc_series.append(min(val, total_cards))

    return fc_series, completion_index, completion_date_label, completion_iso


def template_progress(
    model_id: Optional[int],
    template_ords: Optional[list[int]],
    deck_id: Optional[int],
    granularity: str,
    forecast: bool = False,
) -> dict:
    """
    Return cumulative counts per template per time bucket plus optional forecast.

    Args:
        model_id: The ID of the note type to filter by.
        template_ords: A list of template ordinals to include.
        deck_id: The ID of the deck to filter by.
        granularity: The time bucketing to use ('days', 'weeks', etc.).
        forecast: Whether to include a forecast of completion dates.

    Returns:
        A dictionary containing labels for the chart, and a series of data
        points for each template, including historical and forecasted progress.
    """
    if not mw.col or not getattr(mw.col, "db", None):
        return {"labels": [], "series": []}

    cards = _get_cards_for_analysis(model_id, deck_id, template_ords)
    if not cards:
        return {"labels": [], "series": []}

    cids = [c.id for c in cards]
    first_map = _get_first_review_timestamps(cids)
    template_name_cache = _get_template_names(model_id)
    bucketer = _TimeBucketer(granularity)

    (
        per_template_counts,
        template_total_cards,
        historic_dates,
        historic_labels,
    ) = _calculate_historic_progress(cards, first_map, bucketer)

    if not historic_dates:
        return {"labels": [], "series": []}

    # Collect review dates for rate calculation and milestones
    template_review_dates: Dict[int, List[_dt.date]] = {}
    for c in cards:
        rid = first_map.get(c.id)
        if rid:
            dt_date = _dt.datetime.fromtimestamp(rid / 1000).date()
            template_review_dates.setdefault(c.ord, []).append(dt_date)

    studied_dates_iso_map: Dict[int, List[str]] = {
        ord_: sorted([d.isoformat() for d in dlist])
        for ord_, dlist in template_review_dates.items()
    }

    series: List[Dict[str, Any]] = []
    full_labels = historic_labels
    full_dates = historic_dates[:]

    # This part combines historical data with forecasts if enabled.
    # It's complex because it needs to align data across different templates
    # that may have different start dates and completion forecasts.

    # First, calculate all forecasts to find the max future date needed
    forecast_results = {}
    if forecast:
        max_future_buckets = 0
        for ord_ in template_total_cards:
            fc_series, comp_idx, comp_date, comp_iso = _calculate_forecast(
                ord_,
                template_total_cards[ord_],
                historic_labels,
                per_template_counts,
                template_review_dates,
                bucketer,
            )
            if fc_series:
                forecast_results[ord_] = (fc_series, comp_idx, comp_date, comp_iso)
                max_future_buckets = max(max_future_buckets, len(fc_series) - len(historic_labels))
        
        if max_future_buckets > 0:
            last_date = historic_dates[-1]
            cur = last_date
            for _ in range(max_future_buckets):
                cur = bucketer.next_bucket(cur)
                full_dates.append(cur)
            full_labels = historic_labels + [bucketer.label_from_date(d) for d in full_dates[len(historic_labels):]]


    # Now, build the final series data
    for ord_, total_cards in template_total_cards.items():
        running = 0
        hist_data: list[int] = []
        for lab in historic_labels:
            running += per_template_counts.get(ord_, {}).get(lab, 0)
            hist_data.append(running)

        if not hist_data:
            continue

        entry: Dict[str, Any] = {
            "label": template_name_cache.get(ord_, f"Template {ord_+1}"),
            "data": hist_data,
            "totalCards": total_cards,
            "studiedDates": studied_dates_iso_map.get(ord_, []),
        }

        # Attach forecast if available and not complete
        if forecast and ord_ in forecast_results and hist_data[-1] < total_cards:
            fc_series, comp_idx, comp_date, comp_iso = forecast_results[ord_]
            
            # Pad forecast series to match full label length
            if len(fc_series) < len(full_labels):
                fc_series.extend([None] * (len(full_labels) - len(fc_series)))
            
            entry["forecast"] = fc_series
            entry["forecastCompletionIndex"] = comp_idx
            entry["forecastCompletionDate"] = comp_date
            entry["forecastCompletionISO"] = comp_iso
        
        # Always compute precise completion ISO if incomplete, even without forecast view
        elif hist_data[-1] < total_cards and studied_dates_iso_map.get(ord_):
             _, _, _, comp_iso = _calculate_forecast(
                ord_,
                total_cards,
                historic_labels,
                per_template_counts,
                template_review_dates,
                bucketer,
            )
             entry["forecastCompletionISO"] = comp_iso

        elif hist_data[-1] >= total_cards and studied_dates_iso_map.get(ord_):
            # Already complete: completion date is date of last studied card
            try:
                entry["forecastCompletionISO"] = studied_dates_iso_map[ord_][
                    total_cards - 1
                ]
            except IndexError:
                pass
        
        series.append(entry)

    # Final data cleanup and preparation for UI
    label_dates_iso = [d.isoformat() for d in full_dates]
    global_max_total = max(template_total_cards.values()) if template_total_cards else 0

    # Clip trailing empty buckets
    last_idx_with_value = -1
    for i in range(len(full_labels)):
        if any(
            (s.get("data", []) + [None] * i)[i] is not None
            or (s.get("forecast", []) + [None] * i)[i] is not None
            for s in series
        ):
            last_idx_with_value = i

    if 0 <= last_idx_with_value < len(full_labels) - 1:
        keep = last_idx_with_value + 1
        full_labels = full_labels[:keep]
        label_dates_iso = label_dates_iso[:keep]
        for s in series:
            s["data"] = s.get("data", [])[:keep]
            if "forecast" in s:
                s["forecast"] = s.get("forecast", [])[:keep]
            if s.get("forecastCompletionIndex", -1) >= keep:
                s["forecastCompletionIndex"] = keep - 1

    return {
        "labels": full_labels,
        "labelDates": label_dates_iso,
        "series": series,
        "yMaxTotal": global_max_total,
    }


def template_status_counts(
    model_id: Optional[int],
    template_ords: Optional[list[int]],
    deck_id: Optional[int],
) -> dict:
    """
    Return per-card-type counts of New / Learning / Review states per template ord.
    Uses card.type (0=new, 1=learning, 2=review, 3=relearning).
    """
    cards = _get_cards_for_analysis(model_id, deck_id, template_ords)
    if not cards:
        return {"byTemplate": {}}

    name_map = _get_template_names(model_id)

    by_t: Dict[int, Dict[str, int]] = {}
    for c in cards:
        st = c.type  # 0 new, 1 learn, 2 review, 3 relearn
        if st == 0:
            key = "new"
        elif st in (1, 3):  # treat relearning as learning
            key = "learning"
        else:
            key = "review"

        bucket = by_t.setdefault(c.ord, {"new": 0, "learning": 0, "review": 0})
        bucket[key] = bucket.get(key, 0) + 1

    out: Dict[int, Dict[str, Any]] = {
        ord_: {"name": name_map.get(ord_, f"Card {ord_+1}"), **counts}
        for ord_, counts in by_t.items()
    }
    return {"byTemplate": out}
