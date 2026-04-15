import random
import datetime
from datetime import timedelta

def calculate_procedure_date() -> str:
    """Return a future procedure date 7–90 days from today (MM-DD-YYYY)."""
    days_ahead = random.randint(7, 90)
    return (datetime.datetime.now() + timedelta(days=days_ahead)).strftime("%m-%d-%Y")


def calculate_encounter_date(procedure_date_str: str, days_before: int) -> str:
    """
    Return an encounter date *days_before* days before *procedure_date_str*.

    Args:
        procedure_date_str: ISO date string (MM-DD-YYYY).
        days_before:        Positive integer.
    """
    procedure_date = datetime.datetime.strptime(procedure_date_str, "%m-%d-%Y")
    return (procedure_date - timedelta(days=days_before)).strftime("%m-%d-%Y")


def get_today_date() -> str:
    """Return today's date (MM-DD-YYYY)."""
    return datetime.datetime.now().strftime("%m-%d-%Y")


def parse_date_any(date_str: str):
    """
    Parse a date string in common formats and return a datetime.date or None.
    Supported: MM-DD-YYYY, YYYY-MM-DD, MM/DD/YYYY.
    """
    if not date_str:
        return None
    s = str(date_str).strip()
    if not s:
        return None
    for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def format_mmddyyyy(d) -> str:
    """Format a datetime.date/datetime into MM-DD-YYYY."""
    if d is None:
        return ""
    if isinstance(d, datetime.datetime):
        d = d.date()
    return d.strftime("%m-%d-%Y")
