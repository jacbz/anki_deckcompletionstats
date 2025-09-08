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

from . import config
from .data_access import _get_template_key, _get_template_name_for_key

# Constants for time spent histogram
HIST_BIN_SIZE = 15
HIST_MAX_CAP = 450


def _is_within_date_filter(review_timestamp: int) -> bool:
    """Check if a review timestamp falls within the date filter range."""
    start_date_str = config.get_date_filter_start()
    end_date_str = config.get_date_filter_end()
    
    if not start_date_str and not end_date_str:
        return True
    
    review_date = _dt.datetime.fromtimestamp(review_timestamp / 1000).date()
    
    if start_date_str:
        start_date = _dt.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        if review_date < start_date:
            return False
    
    if end_date_str:
        end_date = _dt.datetime.strptime(end_date_str, "%Y-%m-%d").date()
        if review_date > end_date:
            return False
    
    return True


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

        # Apply date filtering
        if not _is_within_date_filter(review_id):
            continue

        dt = _dt.datetime.fromtimestamp(review_id / 1000)
        bucket_date = _bucket_start(dt, granularity)
        bucket_dates.add(bucket_date)
        label = _label_from_date(bucket_date, granularity)

        template_key = _get_template_key(card, model_id)
        template_buckets = cards_per_template_bucket.setdefault(template_key, {})
        template_buckets[label] = template_buckets.get(label, 0) + 1

    if not bucket_dates:
        return {"labels": [], "series": []}

    # Extend date range to today to show inactivity plateau (only if no end date filter)
    dates_sorted = sorted(bucket_dates)
    end_date_str = config.get_date_filter_end()
    
    if not end_date_str:
        today_bucket = _bucket_start(_dt.datetime.now(), granularity)
        if dates_sorted and dates_sorted[-1] < today_bucket:
            current_date = dates_sorted[-1]
            while current_date < today_bucket:
                current_date = _next_bucket(current_date, granularity)
                dates_sorted.append(current_date)

    labels = [_label_from_date(d, granularity) for d in dates_sorted]
    series = []

    for template_key in sorted(cards_per_template_bucket.keys()):
        data = [
            cards_per_template_bucket.get(template_key, {}).get(label, 0) for label in labels
        ]
        series.append(
            {
                "label": _get_template_name_for_key(template_key, model_id),
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
        "templateNames": {},
    }

    if not cards or not mw.col or not mw.col.db:
        return empty_result

    card_ids = [c.id for c in cards]
    
    # Apply date filtering to revlog entries
    start_date_str = config.get_date_filter_start()
    end_date_str = config.get_date_filter_end()
    
    date_filter_sql = ""
    if start_date_str or end_date_str:
        conditions = []
        if start_date_str:
            try:
                start_timestamp = int(_dt.datetime.strptime(start_date_str, "%Y-%m-%d").timestamp() * 1000)
                conditions.append(f"id >= {start_timestamp}")
            except ValueError:
                pass
        if end_date_str:
            try:
                # End of day timestamp (23:59:59)
                end_timestamp = int((_dt.datetime.strptime(end_date_str, "%Y-%m-%d") + _dt.timedelta(days=1) - _dt.timedelta(seconds=1)).timestamp() * 1000)
                conditions.append(f"id <= {end_timestamp}")
            except ValueError:
                pass
        if conditions:
            date_filter_sql = " AND " + " AND ".join(conditions)
    
    time_rows = mw.col.db.all(
        f"SELECT cid, SUM(time) FROM revlog WHERE cid IN ({','.join(str(i) for i in card_ids)}){date_filter_sql} GROUP BY cid"
    )
    total_time_map = {cid: max(0.0, t / 1000.0) for cid, t in time_rows}

    per_template_times: Dict[int, List[Tuple[int, float]]] = {}
    global_max_time = 0.0
    for card in cards:
        total_time = total_time_map.get(card.id, 0.0)
        template_key = _get_template_key(card, model_id)
        per_template_times.setdefault(template_key, []).append((card.id, total_time))
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

    for template_key, time_list in per_template_times.items():
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
        top_cards[template_key] = rows
        histograms[template_key] = {
            "name": _get_template_name_for_key(template_key, model_id),
            "counts": counts,
        }

    # Create template names map using the new helper function
    template_names = {}
    for template_key in histograms.keys():
        template_names[template_key] = _get_template_name_for_key(template_key, model_id)

    return {
        "binSize": HIST_BIN_SIZE,
        "labels": labels,
        "histograms": histograms,
        "top": top_cards,
        "templateNames": template_names,
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
    empty_result = {
        "byTemplate": {},
        "templateNames": {},
        "maxFailures": 0,
    }

    if not cards or not mw.col or not mw.col.db:
        return empty_result

    card_ids = [c.id for c in cards]
    
    # Apply date filtering to revlog entries
    start_date_str = config.get_date_filter_start()
    end_date_str = config.get_date_filter_end()
    
    date_filter_sql = ""
    if start_date_str or end_date_str:
        conditions = []
        if start_date_str:
            try:
                start_timestamp = int(_dt.datetime.strptime(start_date_str, "%Y-%m-%d").timestamp() * 1000)
                conditions.append(f"id >= {start_timestamp}")
            except ValueError:
                pass
        if end_date_str:
            try:
                # End of day timestamp (23:59:59)
                end_timestamp = int((_dt.datetime.strptime(end_date_str, "%Y-%m-%d") + _dt.timedelta(days=1) - _dt.timedelta(seconds=1)).timestamp() * 1000)
                conditions.append(f"id <= {end_timestamp}")
            except ValueError:
                pass
        if conditions:
            date_filter_sql = " AND " + " AND ".join(conditions)
    
    fail_rows = mw.col.db.all(
        f"SELECT cid, COUNT(*) FROM revlog WHERE ease = 1 AND cid IN ({','.join(str(i) for i in card_ids)}){date_filter_sql} GROUP BY cid"
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

        template_key = _get_template_key(card, model_id)
        by_template.setdefault(template_key, []).append(
            {"cid": card.id, "front": display, "failures": failures}
        )

    for template_key in by_template:
        by_template[template_key] = sorted(
            by_template[template_key], key=lambda x: x["failures"], reverse=True
        )

    # Create template names map using the new helper function
    template_names = {}
    for template_key in by_template.keys():
        template_names[template_key] = _get_template_name_for_key(template_key, model_id)

    return {
        "byTemplate": by_template,
        "templateNames": template_names,
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

    try:
        # Build search query for cards
        search_query = ""
        if deck_id is not None:
            # Use deck name lookup that's more compatible across Anki versions
            try:
                # Try newer API first
                if hasattr(mw.col.decks, 'name'):
                    deck_name = mw.col.decks.name(DeckId(deck_id))
                else:
                    # Fallback to older API
                    deck = mw.col.decks.get(DeckId(deck_id))
                    deck_name = deck["name"] if deck else ""
                
                if deck_name:
                    # Escape quotes in deck name
                    deck_name = deck_name.replace('"', '\\"')
                    search_query = f'deck:"{deck_name}"'
            except:
                # If deck lookup fails, use all cards
                search_query = ""

        # Get cards using search
        try:
            if search_query:
                card_ids = mw.col.find_cards(search_query)
            else:
                # Get all cards if no deck filter
                card_ids = mw.col.find_cards("")
        except:
            return 0

        if not card_ids:
            return 0

        # Get review log entries - use more robust SQL approach
        try:
            # For large card lists, use string concatenation but ensure card_ids are integers
            safe_card_ids = [str(int(cid)) for cid in card_ids]
            
            # Apply date filtering to revlog entries
            start_date_str = config.get_date_filter_start()
            end_date_str = config.get_date_filter_end()
            
            date_filter_sql = ""
            if start_date_str or end_date_str:
                conditions = []
                if start_date_str:
                    try:
                        start_timestamp = int(_dt.datetime.strptime(start_date_str, "%Y-%m-%d").timestamp() * 1000)
                        conditions.append(f"id >= {start_timestamp}")
                    except ValueError:
                        pass
                if end_date_str:
                    try:
                        # End of day timestamp (23:59:59)
                        end_timestamp = int((_dt.datetime.strptime(end_date_str, "%Y-%m-%d") + _dt.timedelta(days=1) - _dt.timedelta(seconds=1)).timestamp() * 1000)
                        conditions.append(f"id <= {end_timestamp}")
                    except ValueError:
                        pass
                if conditions:
                    date_filter_sql = " AND " + " AND ".join(conditions)
            
            query = f"SELECT id FROM revlog WHERE cid IN ({','.join(safe_card_ids)}){date_filter_sql} ORDER BY id DESC"
            revlog_ids = mw.col.db.all(query)
        except:
            return 0

        if not revlog_ids:
            return 0

        # Convert timestamps to dates more safely
        review_dates = set()
        for (rid,) in revlog_ids:
            try:
                # Anki revlog IDs are millisecond timestamps
                timestamp = rid / 1000.0
                date = _dt.datetime.fromtimestamp(timestamp).date()
                review_dates.add(date)
            except (ValueError, OverflowError, OSError):
                # Skip invalid timestamps
                continue

        if not review_dates:
            return 0

        # Calculate streak from today backwards
        today = _dt.date.today()
        streak = 0
        current_day = today
        
        # Check if user studied today, if not, start from yesterday
        # This allows streaks to continue even if user hasn't studied yet today
        if today not in review_dates:
            current_day = today - _dt.timedelta(days=1)
        
        while current_day in review_dates:
            streak += 1
            current_day -= _dt.timedelta(days=1)

        return streak

    except Exception as e:
        # Log error but don't crash the addon
        print(f"Error calculating streak: {e}")
        return 0


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
    
    # Apply date filtering to revlog entries
    start_date_str = config.get_date_filter_start()
    end_date_str = config.get_date_filter_end()
    
    date_filter_sql = ""
    if start_date_str or end_date_str:
        conditions = []
        if start_date_str:
            try:
                start_timestamp = int(_dt.datetime.strptime(start_date_str, "%Y-%m-%d").timestamp() * 1000)
                conditions.append(f"id >= {start_timestamp}")
            except ValueError:
                pass
        if end_date_str:
            try:
                # End of day timestamp (23:59:59)
                end_timestamp = int((_dt.datetime.strptime(end_date_str, "%Y-%m-%d") + _dt.timedelta(days=1) - _dt.timedelta(seconds=1)).timestamp() * 1000)
                conditions.append(f"id <= {end_timestamp}")
            except ValueError:
                pass
        if conditions:
            date_filter_sql = " AND " + " AND ".join(conditions)
    
    rev_rows = mw.col.db.all(
        f"SELECT cid, id, time FROM revlog WHERE cid IN ({','.join(str(i) for i in card_ids)}){date_filter_sql}"
    )
    if not rev_rows:
        return empty_result

    template_name_map = _get_template_name_map(model_id)
    card_template_map = {c.id: _get_template_key(c, model_id) for c in cards}

    bucket_dates: set[_dt.date] = set()
    time_per_template_bucket: Dict[int, Dict[str, float]] = {}
    total_time_per_template: Dict[int, float] = {}

    for cid, rid, time_ms in rev_rows:
        template_key = card_template_map.get(cid)
        if template_key is None:
            continue

        dt = _dt.datetime.fromtimestamp(rid / 1000.0)
        bucket_date = _bucket_start(dt, granularity)
        bucket_dates.add(bucket_date)
        label = _label_from_date(bucket_date, granularity)
        seconds = max(0.0, (time_ms or 0) / 1000.0)

        template_buckets = time_per_template_bucket.setdefault(template_key, {})
        template_buckets[label] = template_buckets.get(label, 0.0) + seconds
        total_time_per_template[template_key] = total_time_per_template.get(template_key, 0.0) + seconds

    if not bucket_dates:
        return empty_result

    dates_sorted = sorted(bucket_dates)
    
    # Only extend to today if no end date filter
    end_date_str = config.get_date_filter_end()
    if not end_date_str:
        today_bucket = _bucket_start(_dt.datetime.now(), granularity)
        if dates_sorted and dates_sorted[-1] < today_bucket:
            current_date = dates_sorted[-1]
            while current_date < today_bucket:
                current_date = _next_bucket(current_date, granularity)
                dates_sorted.append(current_date)

    labels = [_label_from_date(d, granularity) for d in dates_sorted]
    series: List[Dict[str, Any]] = []
    totals_seconds: Dict[str, float] = {}

    for template_key in sorted(time_per_template_bucket.keys()):
        data = [
            round(time_per_template_bucket.get(template_key, {}).get(label, 0.0), 2)
            for label in labels
        ]
        template_name = _get_template_name_for_key(template_key, model_id)
        series.append({"label": template_name, "data": data})
        totals_seconds[template_name] = round(total_time_per_template.get(template_key, 0.0), 2)

    total_all_seconds = sum(total_time_per_template.values())

    return {
        "labels": labels,
        "series": series,
        "totalsSeconds": totals_seconds,
        "totalSecondsAll": total_all_seconds,
    }


# endregion