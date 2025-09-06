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


def template_progress(model_id: Optional[int], template_ords: Optional[list[int]], deck_id: Optional[int], granularity: str) -> dict:
    """Return cumulative counts per template per time bucket.

    Returns dict with keys:
      labels: list[str]
      series: list[{"label": str, "data": list[int]}]
    """
    if not mw.col:
        return {"labels": [], "series": []}

    # Query cards for model/deck filter.
    parts = []
    if model_id is not None:
        parts.append(f"mid:{model_id}")
    if deck_id is not None:
        deck = mw.col.decks.get(cast(DeckId, deck_id))
        if deck:
            dn = deck["name"].replace('"', '\"')
            parts.append(f'deck:"{dn}"')
    query = " ".join(parts) if parts else ""
    cids = mw.col.find_cards(query) if query else mw.col.find_cards("")
    if not cids:
        return {"labels": [], "series": []}

    # Load needed card info
    cards = [mw.col.get_card(cid) for cid in cids]

    # Filter by template ords if provided
    if template_ords is not None:
        cards = [c for c in cards if c.ord in template_ords]

    if not cards:
        return {"labels": [], "series": []}

    # Determine first review time: use c.first_review or revlog earliest entry.
    # For simplicity, we approximate with card's first answer time from revlog.
    # Efficient single query:
    revlog_rows = mw.col.db.all(
        f"SELECT cid, MIN(id) FROM revlog WHERE cid IN ({','.join(str(i) for i in cids)}) GROUP BY cid"
    )
    first_map = {cid: rid for cid, rid in revlog_rows}

    # rid (revlog id) encodes timestamp in milliseconds; convert to date
    def bucket_key(ts_ms: int) -> str:
        dt = _dt.datetime.fromtimestamp(ts_ms / 1000)
        if granularity == "days":
            return dt.strftime("%Y-%m-%d")
        if granularity == "weeks":
            year, week, _ = dt.isocalendar()
            return f"{year}-W{week:02d}"
        if granularity == "months":
            return dt.strftime("%Y-%m")
        if granularity == "quarters":
            q = (dt.month - 1) // 3 + 1
            return f"{dt.year}-Q{q}"
        if granularity == "years":
            return str(dt.year)
        return dt.strftime("%Y-%m-%d")

    # Collect per template bucket counts
    per_template: Dict[int, Dict[str, int]] = {}
    buckets_set = set()
    for c in cards:
        rid = first_map.get(c.id)
        if not rid:
            continue
        key = bucket_key(rid)
        buckets_set.add(key)
        tmpl_dict = per_template.setdefault(c.ord, {})
        tmpl_dict[key] = tmpl_dict.get(key, 0) + 1

    if not buckets_set:
        return {"labels": [], "series": []}

    labels = sorted(buckets_set)
    # cumulative
    series = []
    for ord_, bucket_counts in per_template.items():
        running = 0
        data = []
        for lab in labels:
            running += bucket_counts.get(lab, 0)
            data.append(running)
        series.append({"label": f"Template {ord_+1}", "data": data, "ord": ord_})

    # Sort series by template ord
    series.sort(key=lambda s: s["ord"])  # type: ignore
    for s in series:
        s.pop("ord", None)
    return {"labels": labels, "series": series}
