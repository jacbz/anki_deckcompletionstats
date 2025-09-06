from __future__ import annotations
from typing import Optional, Any, Dict, List, Tuple
from aqt import mw
from anki.decks import DeckId
from anki.models import NotetypeId
import datetime as _dt

# Shared helpers ------------------------------------------------------------


def _bucket_start(dt: _dt.datetime, granularity: str) -> _dt.date:
    if granularity == "days":
        return dt.date()
    if granularity == "weeks":
        iso = dt.isocalendar()
        return _dt.date.fromisocalendar(iso[0], iso[1], 1)
    if granularity == "months":
        return _dt.date(dt.year, dt.month, 1)
    if granularity == "quarters":
        start_month = ((dt.month - 1) // 3) * 3 + 1
        return _dt.date(dt.year, start_month, 1)
    if granularity == "years":
        return _dt.date(dt.year, 1, 1)
    return dt.date()


def _label_from_date(d: _dt.date, granularity: str) -> str:
    if granularity == "days":
        return d.strftime("%Y-%m-%d")
    if granularity == "weeks":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    if granularity == "months":
        return f"{d.year}-{d.month:02d}"
    if granularity == "quarters":
        q = (d.month - 1) // 3 + 1
        return f"{d.year}-Q{q}"
    if granularity == "years":
        return str(d.year)
    return d.strftime("%Y-%m-%d")


def _next_bucket(d: _dt.date, granularity: str) -> _dt.date:
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


# Data collection core ------------------------------------------------------


def _filtered_cards(
    model_id: Optional[int], template_ords: Optional[List[int]], deck_id: Optional[int]
) -> List[Any]:
    if not mw.col:
        return []
    parts: List[str] = []
    if model_id is not None:
        parts.append(f"mid:{model_id}")
    if deck_id is not None:
        deck = mw.col.decks.get(DeckId(deck_id))  # type: ignore[arg-type]
        if deck:
            dn = deck["name"].replace('"', '\\"')
            parts.append(f'deck:"{dn}"')
    query = " ".join(parts)
    cids = mw.col.find_cards(query) if query else mw.col.find_cards("")
    if not cids:
        return []
    cards = [mw.col.get_card(cid) for cid in cids]
    if template_ords is not None:
        cards = [c for c in cards if c.ord in template_ords]
    return cards


# Learning History (non-cumulative) -----------------------------------------


def learning_history(
    model_id: Optional[int],
    template_ords: Optional[List[int]],
    deck_id: Optional[int],
    granularity: str,
) -> dict:
    cards = _filtered_cards(model_id, template_ords, deck_id)
    if not cards:
        return {"labels": [], "series": []}
    cids = [c.id for c in cards]
    col = mw.col
    if not getattr(col, "db", None):
        return {"labels": [], "series": []}
    revlog_rows = col.db.all(  # type: ignore[attr-defined]
        f"SELECT cid, MIN(id) FROM revlog WHERE cid IN ({','.join(str(i) for i in cids)}) GROUP BY cid"
    )
    first_map = {cid: rid for cid, rid in revlog_rows}
    bucket_dates: set[_dt.date] = set()
    per_template: Dict[int, Dict[str, int]] = {}
    total_cards_per_template: Dict[int, int] = {}
    for c in cards:
        total_cards_per_template[c.ord] = total_cards_per_template.get(c.ord, 0) + 1
        rid = first_map.get(c.id)
        if not rid:
            continue
        dt = _dt.datetime.fromtimestamp(rid / 1000)
        bdate = _bucket_start(dt, granularity)
        bucket_dates.add(bdate)
        label = _label_from_date(bdate, granularity)
        d = per_template.setdefault(c.ord, {})
        d[label] = d.get(label, 0) + 1
    if not bucket_dates:
        return {"labels": [], "series": []}
    dates_sorted = sorted(bucket_dates)
    # extend to today bucket to show inactivity plateau
    today_b = _bucket_start(_dt.datetime.now(), granularity)
    if dates_sorted and dates_sorted[-1] < today_b:
        cur = dates_sorted[-1]
        while cur < today_b:
            cur = _next_bucket(cur, granularity)
            dates_sorted.append(cur)
    labels = [_label_from_date(d, granularity) for d in dates_sorted]
    series = []
    # template names
    name_cache: Dict[int, str] = {}
    if model_id is not None:
        m = mw.col.models.get(NotetypeId(model_id))  # type: ignore[arg-type]
        if m:
            for t in m.get("tmpls", []):  # type: ignore
                name_cache[t.get("ord")] = t.get("name") or f"Card {t.get('ord',0)+1}"
    for ord_ in sorted(per_template.keys()):
        data = [per_template.get(ord_, {}).get(l, 0) for l in labels]
        series.append(
            {"label": name_cache.get(ord_, f"Template {ord_+1}"), "data": data}
        )
    return {"labels": labels, "series": series}


# Time Spent ----------------------------------------------------------------
# (Reworked: histogram of TOTAL review time per card, per template, 15s buckets)

HIST_BIN_SIZE = 15  # seconds
HIST_MAX_CAP = 450  # cap


def time_spent_stats(
    model_id: Optional[int],
    template_ords: Optional[List[int]],
    deck_id: Optional[int],
    word_field_index: int = 1,
) -> dict:
    cards = _filtered_cards(model_id, template_ords, deck_id)
    if not cards or not mw.col:
        return {"binSize": HIST_BIN_SIZE, "labels": [], "histograms": {}, "top": {}, "templateNames": {}}
    col = mw.col
    if not getattr(col, "db", None):
        return {"binSize": HIST_BIN_SIZE, "labels": [], "histograms": {}, "top": {}, "templateNames": {}}
    cids = [c.id for c in cards]
    # Total review time per card (SUM of revlog time)
    time_rows = col.db.all(  # type: ignore[attr-defined]
        f"SELECT cid, SUM(time) FROM revlog WHERE cid IN ({','.join(str(i) for i in cids)}) GROUP BY cid"
    )
    total_time_map = {cid: max(0.0, t / 1000.0) for cid, t in time_rows}
    # Template name cache
    name_cache: Dict[int, str] = {}
    if model_id is not None:
        m = mw.col.models.get(NotetypeId(model_id))  # type: ignore[arg-type]
        if m:
            for t in m.get("tmpls", []):  # type: ignore
                name_cache[t.get("ord")] = t.get("name") or f"Card {t.get('ord',0)+1}"
    # Gather per-template total times
    per_template_times: Dict[int, List[Tuple[int, float]]] = {}
    global_max = 0.0
    for c in cards:
        tot = total_time_map.get(c.id, 0.0)
        per_template_times.setdefault(c.ord, []).append((c.id, tot))
        if tot > global_max:
            global_max = tot
    if global_max <= 0:
        # No timing info
        return {"binSize": HIST_BIN_SIZE, "labels": [], "histograms": {}, "top": {}, "templateNames": name_cache}
    cap = min(global_max, HIST_MAX_CAP)
    bin_count = int(cap // HIST_BIN_SIZE) + 1
    overflow = global_max > HIST_MAX_CAP
    labels: List[str] = []
    for i in range(bin_count):
        start = i * HIST_BIN_SIZE
        end = start + HIST_BIN_SIZE
        if i == bin_count - 1 and overflow:
            labels.append(f">={start}s")
        else:
            labels.append(f"{start}-{end}s")
    histograms: Dict[int, Dict[str, Any]] = {}
    top_cards: Dict[int, List[dict]] = {}

    def _format_mmss(secs: float) -> str:
        m = int(secs // 60)
        s = int(secs % 60)
        return f"{m:02d}:{s:02d}"

    for ord_, lst in per_template_times.items():
        counts = [0] * bin_count
        for cid, secs in lst:
            if overflow and secs >= HIST_MAX_CAP:
                idx = bin_count - 1
            else:
                idx = int(min(secs, cap) // HIST_BIN_SIZE)
                if idx >= bin_count:
                    idx = bin_count - 1
            counts[idx] += 1
        # Top cards by total time (desc)
        top_sorted = sorted(lst, key=lambda x: x[1], reverse=True)[:10]
        rows: List[dict] = []
        for cid, secs in top_sorted:
            card = mw.col.get_card(cid)  # type: ignore[arg-type]
            note = card.note()
            primary = _safe_field(note, 0) or str(cid)
            secondary = _safe_field(note, word_field_index)
            display = primary if not secondary else f"#{primary} / {secondary}"
            if len(display) > 60:
                display = display[:57] + "…"
            rows.append({"cid": cid, "front": display, "timeSec": _format_mmss(secs)})
        top_cards[ord_] = rows
        histograms[ord_] = {
            "name": name_cache.get(ord_, f"Card {ord_+1}"),
            "counts": counts,
        }

    return {
        "binSize": HIST_BIN_SIZE,
        "labels": labels,
        "histograms": histograms,
        "top": top_cards,
        "templateNames": name_cache,
    }


# Difficult Cards -----------------------------------------------------------


def difficult_cards(
    model_id: Optional[int],
    template_ords: Optional[List[int]],
    deck_id: Optional[int],
    word_field_index: int = 1,
) -> dict:
    cards = _filtered_cards(model_id, template_ords, deck_id)
    if not cards or not mw.col:
        return {"byTemplate": {}, "templateNames": {}}
    col = mw.col
    if not getattr(col, "db", None):
        return {"byTemplate": {}, "templateNames": {}}
    cids = [c.id for c in cards]
    fail_rows = col.db.all(  # type: ignore[attr-defined]
        f"SELECT cid, COUNT(*) FROM revlog WHERE ease = 1 AND cid IN ({','.join(str(i) for i in cids)}) GROUP BY cid"
    )
    fail_map = {cid: cnt for cid, cnt in fail_rows}
    by_template: Dict[int, List[Tuple[int, int]]] = {}
    name_cache: Dict[int, str] = {}
    if model_id is not None:
        m = mw.col.models.get(NotetypeId(model_id))  # type: ignore[arg-type]
        if m:
            for t in m.get("tmpls", []):  # type: ignore
                name_cache[t.get("ord")] = t.get("name") or f"Card {t.get('ord',0)+1}"
    for c in cards:
        if c.id in fail_map:
            by_template.setdefault(c.ord, []).append((c.id, fail_map[c.id]))
    out: Dict[int, List[dict]] = {}
    for ord_, lst in by_template.items():
        lst_sorted = sorted(lst, key=lambda x: x[1], reverse=True)[:10]
        rows = []
        for cid, fails in lst_sorted:
            card = mw.col.get_card(cid)  # type: ignore[arg-type]
            note = card.note()
            primary = _safe_field(note, 0) or str(cid)
            secondary = _safe_field(note, word_field_index)
            display = primary if secondary == "" else f"#{primary} / {secondary}"
            if len(display) > 60:
                display = display[:57] + "…"
            rows.append({"cid": cid, "front": display, "failures": fails})
        out[ord_] = rows
    return {"byTemplate": out, "templateNames": name_cache}


# Streak --------------------------------------------------------------------


def streak_days(deck_id: Optional[int]) -> int:
    if not mw.col:
        return 0
    col = mw.col
    if not getattr(col, "db", None):
        return 0
    parts: List[str] = []
    if deck_id is not None:
        deck = mw.col.decks.get(DeckId(deck_id))  # type: ignore[arg-type]
        if deck:
            dn = deck["name"].replace('"', '\\"')
            parts.append(f'deck:"{dn}"')
    query = " ".join(parts)
    cids = mw.col.find_cards(query) if query else mw.col.find_cards("")
    if not cids:
        return 0
    rev_rows = col.db.all(  # type: ignore[attr-defined]
        f"SELECT id FROM revlog WHERE cid IN ({','.join(str(i) for i in cids)}) ORDER BY id DESC"
    )
    if not rev_rows:
        return 0
    # Convert to date set
    dates = set(_dt.datetime.fromtimestamp(rid / 1000).date() for (rid,) in rev_rows)
    today = _dt.date.today()
    streak = 0
    cur = today
    while cur in dates:
        streak += 1
        cur = cur - _dt.timedelta(days=1)
    return streak


# helper to fetch field safely (reintroduced for time_spent_stats)

def _safe_field(note, idx: int) -> str:
    try:
        if 0 <= idx < len(note.fields):
            return note.fields[idx]
    except Exception:
        pass
    return ""
