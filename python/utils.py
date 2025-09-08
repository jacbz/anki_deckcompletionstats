"""Utility functions shared across modules."""

from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

from anki.notes import Note


def parse_flexible_date(date_str: str, default_to_start: bool = True) -> Optional[str]:
    """
    Parse flexible date input and return ISO format date (YYYY-MM-DD).

    Handles:
    - YYYY-MM-DD, YYYY/MM/DD
    - YYYY-MM, YYYY/MM
    - MM/DD/YYYY
    - DD.MM.YYYY
    - MM.YYYY
    - YYYY
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # YYYY-MM-DD or YYYY/MM/DD
    if re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}$', date_str):
        date_str = date_str.replace('/', '-')
        try:
            _dt.datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            return None

    # MM/DD/YYYY
    if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', date_str):
        month, day, year = date_str.split('/')
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # DD.MM.YYYY
    if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', date_str):
        day, month, year = date_str.split('.')
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # YYYY-MM or YYYY/MM
    if re.match(r'^\d{4}[-/]\d{2}$', date_str):
        year, month = re.split(r'[-/]', date_str)
        if default_to_start:
            return f"{year}-{month.zfill(2)}-01"
        else:
            import calendar
            try:
                last_day = calendar.monthrange(int(year), int(month))[1]
                return f"{year}-{month.zfill(2)}-{last_day:02d}"
            except (ValueError, IndexError):
                return f"{year}-{month.zfill(2)}-01" # Fallback

    # MM.YYYY
    if re.match(r'^\d{1,2}\.\d{4}$', date_str):
        month, year = date_str.split('.')
        if default_to_start:
            return f"{year}-{month.zfill(2)}-01"
        else:
            import calendar
            try:
                last_day = calendar.monthrange(int(year), int(month))[1]
                return f"{year}-{month.zfill(2)}-{last_day:02d}"
            except (ValueError, IndexError):
                return f"{year}-{month.zfill(2)}-01"

    # YYYY
    if re.match(r'^\d{4}$', date_str):
        year = date_str
        if default_to_start:
            return f"{year}-01-01"
        else:
            return f"{year}-12-31"

    # Fallback for unrecognized formats
    return None


class TimeBucketer:
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


def safe_field(note: Note, idx: int) -> str:
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