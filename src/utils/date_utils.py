import random
import datetime
from datetime import timedelta

def calculate_procedure_date() -> str:
    """Return a future procedure date 7–90 days from today (ISO format)."""
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
    """Return today's date in ISO format (MM-DD-YYYY)."""
    return datetime.datetime.now().strftime("%m-%d-%Y")
