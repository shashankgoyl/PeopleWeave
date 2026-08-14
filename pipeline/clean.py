"""
Normalization helpers shared by merge.py and data_quality_report.py.
Kept dependency-free (no pandas here) so it's easy to unit-test in isolation.
"""
import re

PLACEHOLDER_VALUES = {"", "n/a", "na", "-", "none", "null", "test", "test@test.com", "0000000000"}


def clean_str(v):
    if v is None:
        return None
    s = str(v).strip()
    s = re.sub(r"\s+", " ", s)
    if s.lower() in PLACEHOLDER_VALUES:
        return None
    return s or None


def normalize_name(v):
    s = clean_str(v)
    if not s:
        return None
    return re.sub(r"\s+", " ", s.strip()).title()


def normalize_email(v):
    s = clean_str(v)
    if not s:
        return None
    s = s.lower()
    # basic sanity check - must look like an email, else treat as garbage/missing
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s):
        return None
    return s


def normalize_phone(v):
    """
    Strip everything but digits, drop a leading country code (91) or trunk 0,
    and keep the last 10 digits (Indian mobile numbers). Returns None if what's
    left isn't a plausible 10-digit mobile number.
    """
    s = clean_str(v)
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    digits = digits[-10:] if len(digits) >= 10 else digits
    if len(digits) != 10 or digits == "0" * 10:
        return None
    return digits


def is_valid_email_syntax(v):
    if v is None:
        return False
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(v)) is not None


# City/metro aliasing. India's NCR region gets recorded under half a dozen
# spellings depending on who's typing; without this, "Gurgaon" and "Gurugram"
# would be treated as two different cities.
_CITY_ALIASES = {
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "new delhi": "Delhi",
    "delhi ncr": "Delhi",
    "delhi": "Delhi",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
}


def normalize_city(v):
    s = clean_str(v)
    if not s:
        return None
    key = s.lower().strip()
    return _CITY_ALIASES.get(key, s.title())


import datetime as _dt

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def normalize_date(v):
    """
    Best-effort parser for the mixed date formats seen in source1's 'Applied Date'
    column: 'DD-MM-YYYY', 'YYYY-MM-DD', 'D Mon YYYY', and 'MM/DD/YYYY'.
    Rule of thumb applied (see docs/data_issues_report.md for why): dash-separated
    numeric dates are treated as DD-MM-YYYY, slash-separated as MM/DD/YYYY - this
    matches every unambiguous example in the file (e.g. 07/13/2026 can only be
    MM/DD since 13 isn't a valid month). Returns ISO 'YYYY-MM-DD' or None with the
    original value untouched in raw_row either way.
    """
    s = clean_str(v)
    if not s:
        return None

    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"

    m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", s)
    if m:
        d, mo, y = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"

    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        mo, d, y = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"

    m = re.match(r"^(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})$", s)
    if m:
        d, mon_name, y = m.groups()
        mo = _MONTHS.get(mon_name.lower()[:3])
        if mo:
            return f"{int(y):04d}-{mo:02d}-{int(d):02d}"

    return None  # unrecognized format - left as-is in raw_row, flagged in the report
