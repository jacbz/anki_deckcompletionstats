"""
This module provides functions for analyzing Anki collection data.

It includes functions for calculating learning history, time spent on cards,
identifying difficult cards, and tracking study streaks.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

from anki.cards import Card, CardId
from anki.decks import DeckId
from anki.models import NotetypeId
from anki.notes import Note
from aqt import mw

# Constants for time spent histogram
HIST_BIN_SIZE = 15  # seconds
HIST_MAX_CAP = 450  # seconds


# region Shared Helpers
# These are utility functions used by the main analytics functions.


def _bucket_start(dt: _dt.datetime, granularity: str) -> _dt.date:
    """
    Calculates the start date of a time bucket for a given datetime and granularity.

    Args:
        dt: The datetime to bucket.
        granularity: The time granularity ('days', 'weeks', 'months', 'quarters', 'years').

    Returns:
        The start date of the bucket.
    """
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
    """
    Generates a string label for a date based on granularity.

    Args:
        d: The date to label.
        granularity: The time granularity.

    Returns:
        A formatted string label for the date.
    """
    if granularity == "days":
        return d.strftime("%Y-%m-%d")
    if granularity == "weeks":
        year, week, _ = d.isocalendar()
        return f"{year}-W{week:02d}"
    if granularity == "months":
        return f"{d.year}-{d.month:02d}"
    if granularity == "quarters":
        quarter = (d.month - 1) // 3 + 1
        return f"{d.year}-Q{quarter}"
    if granularity == "years":
        return str(d.year)
    return d.strftime("%Y-%m-%d")


def _next_bucket(d: _dt.date, granularity: str) -> _dt.date:
    """
    Calculates the start date of the next time bucket.

    Args:
        d: The current bucket's start date.
        granularity: The time granularity.

    Returns:
        The start date of the next bucket.
    """
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


def _get_template_name_map(model_id: Optional[int]) -> Dict[int, str]:
    """
    Creates a map of template ordinal to template name for a given model.

    Args:
        model_id: The ID of the note type model.

    Returns:
        A dictionary mapping template ordinals to their names.
    """
    name_map: Dict[int, str] = {}
    if not mw.col or not model_id:
        return name_map

    model = mw.col.models.get(NotetypeId(model_id))
    if model:
        for t in model.get("tmpls", []):
            ordinal = t.get("ord")
            if ordinal is not None:
                name = t.get("name") or f"Card {ordinal + 1}"
                name_map[ordinal] = name
    return name_map


def _safe_field(note: Note, idx: int) -> str:
    """
    Safely retrieves a field from a note by index.

    Args:
        note: The note object.
        idx: The index of the field to retrieve.

    Returns:
        The field content as a string, or an empty string if retrieval fails.
    """
    try:
        if 0 <= idx < len(note.fields):
            return note.fields[idx]
    except Exception:
        pass
    return ""


# endregion

# region Data Collection Core


def _filtered_cards(
    model_id: Optional[int],
    template_ords: Optional[List[int]],
    deck_id: Optional[int],
) -> List[Card]:
    """
    Retrieves a list of cards based on model, template, and deck filters.

    Args:
        model_id: The note type ID to filter by.
        template_ords: A list of template ordinals to include.
        deck_id: The deck ID to filter by.

    Returns:
        A list of filtered card objects.
    """
    if not mw.col:
        return []

    search_parts: List[str] = []
    if model_id is not None:
        search_parts.append(f"mid:{model_id}")
    if deck_id is not None:
        deck = mw.col.decks.get(DeckId(deck_id))
        if deck:
            deck_name = deck["name"].replace('"', '\\"')
            search_parts.append(f'deck:"{deck_name}"')

    query = " ".join(search_parts)
    card_ids = mw.col.find_cards(query)
    if not card_ids:
        return []

    cards = [mw.col.get_card(cid) for cid in card_ids]

    if template_ords is not None:
        cards = [c for c in cards if c.ord in template_ords]

    return cards


# endregion

# region Analytics Functions


def learning_history(
    model_id: Optional[int],
    template_ords: Optional[List[int]],
    deck_id: Optional[int],
    granularity: str,
) -> dict:
    """
    Calculates the non-cumulative learning history (new cards studied over time).

    Args:
        model_id: The note type ID.
        template_ords: The list of template ordinals.
        deck_id: The deck ID.
        granularity: The time granularity for bucketing.

    Returns:
        A dictionary containing labels and data series for a chart.
    """
    cards = _filtered_cards(model_id, template_ords, deck_id)
    if not cards or not mw.col or not mw.col.db:
        return {"labels": [], "series": []}

    card_ids = [c.id for c in cards]
    revlog_rows = mw.col.db.all(
        f"SELECT cid, MIN(id) FROM revlog WHERE cid IN ({','.join(str(i) for i in card_ids)}) GROUP BY cid"
    )
    first_review_map = {cid: rid for cid, rid in revlog_rows}

    bucket_dates: set[_dt.date] = set()
    cards_per_template_bucket: Dict[int, Dict[str, int]] = {}

    for card in cards:
        review_id = first_review_map.get(card.id)
        if not review_id:
            continue

        dt = _dt.datetime.fromtimestamp(review_id / 1000)
        bucket_date = _bucket_start(dt, granularity)
        bucket_dates.add(bucket_date)
        label = _label_from_date(bucket_date, granularity)

        template_buckets = cards_per_template_bucket.setdefault(card.ord, {})
        template_buckets[label] = template_buckets.get(label, 0) + 1

    if not bucket_dates:
        return {"labels": [], "series": []}

    # Extend date range to today to show inactivity plateau
    dates_sorted = sorted(bucket_dates)
    today_bucket = _bucket_start(_dt.datetime.now(), granularity)
    if dates_sorted and dates_sorted[-1] < today_bucket:
        current_date = dates_sorted[-1]
        while current_date < today_bucket:
            current_date = _next_bucket(current_date, granularity)
            dates_sorted.append(current_date)

    labels = [_label_from_date(d, granularity) for d in dates_sorted]
    series = []
    template_name_map = _get_template_name_map(model_id)

    for ordinal in sorted(cards_per_template_bucket.keys()):
        data = [
            cards_per_template_bucket.get(ordinal, {}).get(label, 0) for label in labels
        ]
        series.append(
            {
                "label": template_name_map.get(ordinal, f"Template {ordinal + 1}"),
                "data": data,
            }
        )

    return {"labels": labels, "series": series}


def time_spent_stats(
    model_id: Optional[int],
    template_ords: Optional[List[int]],
    deck_id: Optional[int],
) -> dict:
    """
    Generates a histogram of total review time per card for each template.

    Args:
        model_id: The note type ID.
        template_ords: The list of template ordinals.
        deck_id: The deck ID.

    Returns:
        A dictionary with histogram data, including bin labels, counts, and top cards.
    """
    cards = _filtered_cards(model_id, template_ords, deck_id)
    template_name_map = _get_template_name_map(model_id)
    empty_result = {
        "binSize": HIST_BIN_SIZE,
        "labels": [],
        "histograms": {},
        "top": {},
        "templateNames": template_name_map,
    }

    if not cards or not mw.col or not mw.col.db:
        return empty_result

    card_ids = [c.id for c in cards]
    time_rows = mw.col.db.all(
        f"SELECT cid, SUM(time) FROM revlog WHERE cid IN ({','.join(str(i) for i in card_ids)}) GROUP BY cid"
    )
    total_time_map = {cid: max(0.0, t / 1000.0) for cid, t in time_rows}

    per_template_times: Dict[int, List[Tuple[int, float]]] = {}
    global_max_time = 0.0
    for card in cards:
        total_time = total_time_map.get(card.id, 0.0)
        per_template_times.setdefault(card.ord, []).append((card.id, total_time))
        if total_time > global_max_time:
            global_max_time = total_time

    if global_max_time <= 0:
        return empty_result

    cap = min(global_max_time, HIST_MAX_CAP)
    bin_count = int(cap // HIST_BIN_SIZE) + 1
    has_overflow = global_max_time > HIST_MAX_CAP
    labels: List[str] = []
    for i in range(bin_count):
        start = i * HIST_BIN_SIZE
        end = start + HIST_BIN_SIZE
        if i == bin_count - 1 and has_overflow:
            labels.append(f">={start}s")
        else:
            labels.append(f"{start}-{end}s")

    histograms: Dict[int, Dict[str, Any]] = {}
    top_cards: Dict[int, List[dict]] = {}

    def _format_mmss(secs: float) -> str:
        minutes = int(secs // 60)
        seconds = int(secs % 60)
        return f"{minutes:02d}:{seconds:02d}"

    for ordinal, time_list in per_template_times.items():
        counts = [0] * bin_count
        for _, secs in time_list:
            if has_overflow and secs >= HIST_MAX_CAP:
                idx = bin_count - 1
            else:
                idx = int(min(secs, cap) // HIST_BIN_SIZE)
                if idx >= bin_count:
                    idx = bin_count - 1
            counts[idx] += 1

        top_sorted = sorted(time_list, key=lambda x: x[1], reverse=True)[:10]
        rows: List[dict] = []
        for cid, secs in top_sorted:
            card = mw.col.get_card(CardId(cid))
            if not card:
                continue
            note = card.note()
            primary = _safe_field(note, 0) or str(cid)
            secondary = _safe_field(note, 1)
            display = primary if not secondary else f"{primary} / {secondary}"
            if len(display) > 60:
                display = display[:57] + "…"
            rows.append({"cid": cid, "front": display, "timeSec": _format_mmss(secs)})
        top_cards[ordinal] = rows
        histograms[ordinal] = {
            "name": template_name_map.get(ordinal, f"Card {ordinal + 1}"),
            "counts": counts,
        }

    return {
        "binSize": HIST_BIN_SIZE,
        "labels": labels,
        "histograms": histograms,
        "top": top_cards,
        "templateNames": template_name_map,
    }


def difficult_cards(
    model_id: Optional[int],
    template_ords: Optional[List[int]],
    deck_id: Optional[int],
) -> dict:
    """
    Identifies the most difficult cards based on the number of failures (ease=1).

    Args:
        model_id: The note type ID.
        template_ords: The list of template ordinals.
        deck_id: The deck ID.

    Returns:
        A dictionary containing difficult cards grouped by template.
    """
    cards = _filtered_cards(model_id, template_ords, deck_id)
    template_name_map = _get_template_name_map(model_id)
    empty_result = {
        "byTemplate": {},
        "templateNames": template_name_map,
        "maxFailures": 0,
    }

    if not cards or not mw.col or not mw.col.db:
        return empty_result

    card_ids = [c.id for c in cards]
    fail_rows = mw.col.db.all(
        f"SELECT cid, COUNT(*) FROM revlog WHERE ease = 1 AND cid IN ({','.join(str(i) for i in card_ids)}) GROUP BY cid"
    )
    fail_map = {cid: count for cid, count in fail_rows}

    by_template: Dict[int, List[dict]] = {}
    max_failures = 0
    for card in cards:
        failures = fail_map.get(card.id, 0)
        if failures > max_failures:
            max_failures = failures

        note = card.note()
        primary = _safe_field(note, 0) or str(card.id)
        secondary = _safe_field(note, 1)
        display = primary if not secondary else f"{primary} / {secondary}"
        if len(display) > 60:
            display = display[:57] + "…"

        by_template.setdefault(card.ord, []).append(
            {"cid": card.id, "front": display, "failures": failures}
        )

    for ordinal in by_template:
        by_template[ordinal] = sorted(
            by_template[ordinal], key=lambda x: x["failures"], reverse=True
        )

    return {
        "byTemplate": by_template,
        "templateNames": template_name_map,
        "maxFailures": max_failures,
    }


def streak_days(deck_id: Optional[int]) -> int:
    """
    Calculates the current study streak in days.

    Args:
        deck_id: The deck ID to filter by, or None for all decks.

    Returns:
        The number of consecutive days studied up to today.
    """
    if not mw.col or not mw.col.db:
        return 0

    search_parts: List[str] = []
    if deck_id is not None:
        deck = mw.col.decks.get(DeckId(deck_id))
        if deck:
            deck_name = deck["name"].replace('"', '\\"')
            search_parts.append(f'deck:"{deck_name}"')

    query = " ".join(search_parts)
    card_ids = mw.col.find_cards(query)
    if not card_ids:
        return 0

    revlog_ids = mw.col.db.all(
        f"SELECT id FROM revlog WHERE cid IN ({','.join(str(i) for i in card_ids)}) ORDER BY id DESC"
    )
    if not revlog_ids:
        return 0

    review_dates = set(
        _dt.datetime.fromtimestamp(rid / 1000).date() for (rid,) in revlog_ids
    )
    today = _dt.date.today()
    streak = 0
    current_day = today
    while current_day in review_dates:
        streak += 1
        current_day -= _dt.timedelta(days=1)

    return streak


def time_studied_history(
    model_id: Optional[int],
    template_ords: Optional[List[int]],
    deck_id: Optional[int],
    granularity: str,
) -> dict:
    """
    Calculates the total time studied per period, stacked by card template.

    Args:
        model_id: The note type ID.
        template_ords: The list of template ordinals.
        deck_id: The deck ID.
        granularity: The time granularity for bucketing.

    Returns:
        A dictionary with chart data, including labels, series, and totals.
    """
    cards = _filtered_cards(model_id, template_ords, deck_id)
    empty_result = {"labels": [], "series": [], "totalsSeconds": {}, "totalSecondsAll": 0}

    if not cards or not mw.col or not mw.col.db:
        return empty_result

    card_ids = [c.id for c in cards]
    rev_rows = mw.col.db.all(
        f"SELECT cid, id, time FROM revlog WHERE cid IN ({','.join(str(i) for i in card_ids)})"
    )
    if not rev_rows:
        return empty_result

    template_name_map = _get_template_name_map(model_id)
    card_template_map = {c.id: c.ord for c in cards}

    bucket_dates: set[_dt.date] = set()
    time_per_template_bucket: Dict[int, Dict[str, float]] = {}
    total_time_per_template: Dict[int, float] = {}

    for cid, rid, time_ms in rev_rows:
        ordinal = card_template_map.get(cid)
        if ordinal is None:
            continue

        dt = _dt.datetime.fromtimestamp(rid / 1000.0)
        bucket_date = _bucket_start(dt, granularity)
        bucket_dates.add(bucket_date)
        label = _label_from_date(bucket_date, granularity)
        seconds = max(0.0, (time_ms or 0) / 1000.0)

        template_buckets = time_per_template_bucket.setdefault(ordinal, {})
        template_buckets[label] = template_buckets.get(label, 0.0) + seconds
        total_time_per_template[ordinal] = (
            total_time_per_template.get(ordinal, 0.0) + seconds
        )

    if not bucket_dates:
        return empty_result

    dates_sorted = sorted(bucket_dates)
    today_bucket = _bucket_start(_dt.datetime.now(), granularity)
    if dates_sorted and dates_sorted[-1] < today_bucket:
        current_date = dates_sorted[-1]
        while current_date < today_bucket:
            current_date = _next_bucket(current_date, granularity)
            dates_sorted.append(current_date)

    labels = [_label_from_date(d, granularity) for d in dates_sorted]
    series: List[Dict[str, Any]] = []
    totals_seconds: Dict[str, float] = {}

    for ordinal in sorted(time_per_template_bucket.keys()):
        data = [
            round(time_per_template_bucket.get(ordinal, {}).get(label, 0.0), 2)
            for label in labels
        ]
        label_name = template_name_map.get(ordinal, f"Template {ordinal + 1}")
        series.append({"label": label_name, "data": data})
        totals_seconds[label_name] = total_time_per_template.get(ordinal, 0.0)

    total_all_seconds = sum(total_time_per_template.values())

    return {
        "labels": labels,
        "series": series,
        "totalsSeconds": totals_seconds,
        "totalSecondsAll": total_all_seconds,
    }


# endregion