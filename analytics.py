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
        start_month = ((dt.month - 1)//3)*3 + 1
        return _dt.date(dt.year, start_month, 1)
    if granularity == "years":
        return _dt.date(dt.year, 1, 1)
    return dt.date()

def _label_from_date(d: _dt.date, granularity: str) -> str:
    if granularity == "days":
        return d.strftime("%Y-%m-%d")
    if granularity == "weeks":
        y,w,_ = d.isocalendar()
        return f"{y}-W{w:02d}"
    if granularity == "months":
        return f"{d.year}-{d.month:02d}"
    if granularity == "quarters":
        q = (d.month-1)//3 + 1
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

def _filtered_cards(model_id: Optional[int], template_ords: Optional[List[int]], deck_id: Optional[int]) -> List[Any]:
    if not mw.col:
        return []
    parts: List[str] = []
    if model_id is not None:
        parts.append(f"mid:{model_id}")
    if deck_id is not None:
        deck = mw.col.decks.get(DeckId(deck_id))  # type: ignore[arg-type]
        if deck:
            dn = deck["name"].replace('"','\\"')
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

def learning_history(model_id: Optional[int], template_ords: Optional[List[int]], deck_id: Optional[int], granularity: str) -> dict:
    cards = _filtered_cards(model_id, template_ords, deck_id)
    if not cards:
        return {"labels": [], "series": []}
    cids = [c.id for c in cards]
    revlog_rows = mw.col.db.all(
        f"SELECT cid, MIN(id) FROM revlog WHERE cid IN ({','.join(str(i) for i in cids)}) GROUP BY cid"
    )
    first_map = {cid: rid for cid, rid in revlog_rows}
    bucket_dates: set[_dt.date] = set()
    per_template: Dict[int, Dict[str,int]] = {}
    total_cards_per_template: Dict[int,int] = {}
    for c in cards:
        total_cards_per_template[c.ord] = total_cards_per_template.get(c.ord,0)+1
        rid = first_map.get(c.id)
        if not rid:
            continue
        dt = _dt.datetime.fromtimestamp(rid/1000)
        bdate = _bucket_start(dt, granularity)
        bucket_dates.add(bdate)
        label = _label_from_date(bdate, granularity)
        d = per_template.setdefault(c.ord, {})
        d[label] = d.get(label,0)+1
    if not bucket_dates:
        return {"labels": [], "series": []}
    dates_sorted = sorted(bucket_dates)
    labels = [_label_from_date(d, granularity) for d in dates_sorted]
    series = []
    # template names
    name_cache: Dict[int,str] = {}
    if model_id is not None:
        m = mw.col.models.get(NotetypeId(model_id))  # type: ignore[arg-type]
        if m:
            for t in m.get('tmpls', []):  # type: ignore
                name_cache[t.get('ord')] = t.get('name') or f"Card {t.get('ord',0)+1}"
    for ord_ in sorted(per_template.keys()):
        data = [per_template.get(ord_, {}).get(l,0) for l in labels]
        series.append({"label": name_cache.get(ord_, f"Template {ord_+1}"), "data": data})
    return {"labels": labels, "series": series}

# Cumulative Frequency (percent) --------------------------------------------

def cumulative_frequency(model_id: Optional[int], template_ords: Optional[List[int]], deck_id: Optional[int], granularity: str) -> dict:
    # reuse learning history for counts per bucket, then cumulative & percent
    lh = learning_history(model_id, template_ords, deck_id, granularity)
    if not lh["labels"]:
        return {"labels": [], "series": []}
    series_out = []
    for s in lh["series"]:
        cumulative: List[int] = []
        run = 0
        for v in s["data"]:
            run += v
            cumulative.append(run)
        if run <= 0:
            continue
        series_out.append({"label": s["label"], "data": [round((c/run)*100,2) for c in cumulative]})
    return {"labels": lh["labels"], "series": series_out}

# Time Spent ----------------------------------------------------------------
TIME_BUCKETS = [
    (0, 60, "<1m"),
    (60, 5*60, "1-5m"),
    (5*60, 10*60, "5-10m"),
    (10*60, 20*60, "10-20m"),
    (20*60, 30*60, "20-30m"),
    (30*60, 60*60, "30-60m"),
    (60*60, 10**12, ">60m"),
]

def time_spent_stats(model_id: Optional[int], template_ords: Optional[List[int]], deck_id: Optional[int]) -> dict:
    cards = _filtered_cards(model_id, template_ords, deck_id)
    if not cards:
        return {"buckets": [], "series": [], "top": {}}
    cids = [c.id for c in cards]
    # total time per card
    time_rows = mw.col.db.all(
        f"SELECT cid, SUM(time) FROM revlog WHERE cid IN ({','.join(str(i) for i in cids)}) GROUP BY cid"
    )
    time_map = {cid: t/1000.0 for cid, t in time_rows}  # seconds
    # template name cache
    name_cache: Dict[int,str] = {}
    if model_id is not None:
        m = mw.col.models.get(NotetypeId(model_id))  # type: ignore[arg-type]
        if m:
            for t in m.get('tmpls', []):  # type: ignore
                name_cache[t.get('ord')] = t.get('name') or f"Card {t.get('ord',0)+1}"
    # bucket counts per template (grouped bars)
    bucket_labels = [b[2] for b in TIME_BUCKETS]
    per_template_bucket: Dict[int, List[int]] = {}
    top_cards: Dict[int, List[dict]] = {}
    for c in cards:
        total_sec = time_map.get(c.id, 0.0)
        # assign bucket
        label_index = 0
        for i,(lo,hi,lab) in enumerate(TIME_BUCKETS):
            if lo <= total_sec < hi:
                label_index = i
                break
        arr = per_template_bucket.setdefault(c.ord, [0]*len(TIME_BUCKETS))
        arr[label_index] += 1
    # top cards by time per template
    per_template_times: Dict[int,List[Tuple[int,float]]] = {}
    for c in cards:
        per_template_times.setdefault(c.ord, []).append((c.id, time_map.get(c.id,0.0)))
    for ord_, lst in per_template_times.items():
        lst_sorted = sorted(lst, key=lambda x: x[1], reverse=True)[:10]
        rows = []
        for cid, secs in lst_sorted:
            note = mw.col.get_card(cid).note()
            front = note.fields[0] if note.fields else str(cid)
            if len(front) > 40:
                front = front[:37] + '…'
            rows.append({"cid": cid, "front": front, "timeSec": round(secs,1)})
        top_cards[ord_] = rows
    series = []
    for ord_, data in per_template_bucket.items():
        series.append({"label": name_cache.get(ord_, f"Template {ord_+1}"), "data": data, "ord": ord_})
    return {"buckets": bucket_labels, "series": series, "top": top_cards}

# Difficult Cards -----------------------------------------------------------

def difficult_cards(model_id: Optional[int], template_ords: Optional[List[int]], deck_id: Optional[int]) -> dict:
    cards = _filtered_cards(model_id, template_ords, deck_id)
    if not cards:
        return {"byTemplate": {}}
    cids = [c.id for c in cards]
    fail_rows = mw.col.db.all(
        f"SELECT cid, COUNT(*) FROM revlog WHERE ease = 1 AND cid IN ({','.join(str(i) for i in cids)}) GROUP BY cid"
    )
    fail_map = {cid: cnt for cid, cnt in fail_rows}
    by_template: Dict[int,List[Tuple[int,int]]] = {}
    for c in cards:
        if c.id in fail_map:
            by_template.setdefault(c.ord, []).append((c.id, fail_map[c.id]))
    out: Dict[int,List[dict]] = {}
    for ord_, lst in by_template.items():
        lst_sorted = sorted(lst, key=lambda x: x[1], reverse=True)[:10]
        rows = []
        for cid, fails in lst_sorted:
            note = mw.col.get_card(cid).note()
            front = note.fields[0] if note.fields else str(cid)
            if len(front) > 40:
                front = front[:37] + '…'
            rows.append({"cid": cid, "front": front, "failures": fails})
        out[ord_] = rows
    return {"byTemplate": out}

# Streak --------------------------------------------------------------------

def streak_days(deck_id: Optional[int]) -> int:
    if not mw.col:
        return 0
    parts: List[str] = []
    if deck_id is not None:
        deck = mw.col.decks.get(DeckId(deck_id))  # type: ignore[arg-type]
        if deck:
            dn = deck['name'].replace('"','\\"')
            parts.append(f'deck:"{dn}"')
    query = " ".join(parts)
    cids = mw.col.find_cards(query) if query else mw.col.find_cards("")
    if not cids:
        return 0
    rev_rows = mw.col.db.all(
        f"SELECT id FROM revlog WHERE cid IN ({','.join(str(i) for i in cids)}) ORDER BY id DESC"
    )
    if not rev_rows:
        return 0
    # Convert to date set
    dates = set(_dt.datetime.fromtimestamp(rid/1000).date() for (rid,) in rev_rows)
    today = _dt.date.today()
    streak = 0
    cur = today
    while cur in dates:
        streak += 1
        cur = cur - _dt.timedelta(days=1)
    return streak
