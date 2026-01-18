"""Hebrew date utilities for lecture titles."""

from datetime import datetime
from typing import Optional

from pyluach import dates, hebrewcal


# Hebrew day names (Sunday = 1 in Python's weekday after adjustment)
HEBREW_DAY_NAMES = {
    0: "שני",      # Monday
    1: "שלישי",    # Tuesday
    2: "רביעי",    # Wednesday
    3: "חמישי",    # Thursday
    4: "שישי",     # Friday
    5: "שבת",      # Saturday
    6: "ראשון",    # Sunday
}

# Hebrew numerals for days
HEBREW_NUMERALS = {
    1: "א'", 2: "ב'", 3: "ג'", 4: "ד'", 5: "ה'",
    6: "ו'", 7: "ז'", 8: "ח'", 9: "ט'", 10: "י'",
    11: "י\"א", 12: "י\"ב", 13: "י\"ג", 14: "י\"ד", 15: "ט\"ו",
    16: "ט\"ז", 17: "י\"ז", 18: "י\"ח", 19: "י\"ט", 20: "כ'",
    21: "כ\"א", 22: "כ\"ב", 23: "כ\"ג", 24: "כ\"ד", 25: "כ\"ה",
    26: "כ\"ו", 27: "כ\"ז", 28: "כ\"ח", 29: "כ\"ט", 30: "ל'",
}

# Hebrew month names
HEBREW_MONTHS = {
    1: "ניסן",
    2: "אייר",
    3: "סיון",
    4: "תמוז",
    5: "אב",
    6: "אלול",
    7: "תשרי",
    8: "חשון",
    9: "כסלו",
    10: "טבת",
    11: "שבט",
    12: "אדר",
    13: "אדר ב'",  # Adar II in leap years
}

# Hebrew year names (recent years)
HEBREW_YEARS = {
    5784: 'תשפ"ד',
    5785: 'תשפ"ה',
    5786: 'תשפ"ו',
    5787: 'תשפ"ז',
    5788: 'תשפ"ח',
    5789: 'תשפ"ט',
    5790: 'תש"צ',
}


def get_hebrew_date(gregorian_date: datetime) -> dates.HebrewDate:
    """Convert a Gregorian date to Hebrew date.
    
    Args:
        gregorian_date: The Gregorian date to convert.
        
    Returns:
        HebrewDate object.
    """
    return dates.HebrewDate.from_pydate(gregorian_date.date())


def get_hebrew_day_name(gregorian_date: datetime) -> str:
    """Get the Hebrew name for the day of the week.
    
    Args:
        gregorian_date: The date to get the day name for.
        
    Returns:
        Hebrew day name (e.g., "שבת", "ראשון").
    """
    return HEBREW_DAY_NAMES[gregorian_date.weekday()]


def get_hebrew_date_string(gregorian_date: datetime) -> str:
    """Get the Hebrew date as a formatted string.
    
    Args:
        gregorian_date: The Gregorian date to convert.
        
    Returns:
        Formatted Hebrew date (e.g., "כ\"ט שבט").
    """
    heb_date = get_hebrew_date(gregorian_date)
    
    day_numeral = HEBREW_NUMERALS.get(heb_date.day, str(heb_date.day))
    month_name = HEBREW_MONTHS.get(heb_date.month, str(heb_date.month))
    
    return f"{day_numeral} {month_name}"


def get_hebrew_year_name(gregorian_date: datetime) -> str:
    """Get the Hebrew year name.
    
    Args:
        gregorian_date: The Gregorian date.
        
    Returns:
        Hebrew year name (e.g., 'תשפ"ו').
    """
    heb_date = get_hebrew_date(gregorian_date)
    return HEBREW_YEARS.get(heb_date.year, f"שנת {heb_date.year}")


def format_lecture_title(raw_title: str, lecture_date: Optional[datetime] = None) -> str:
    """Format the lecture title for WordPress.
    
    Removes "Meet" prefix and adds Hebrew day/date.
    
    Args:
        raw_title: The raw title from Google Meet filename.
        lecture_date: The date of the lecture.
        
    Returns:
        Formatted title for the post.
    """
    # Remove "Meet" prefix (with or without RTL markers)
    title = raw_title
    for prefix in ["Meet ", "‏Meet ", "Meet‏ ", "‏Meet‏ "]:
        if title.startswith(prefix):
            title = title[len(prefix):]
            break
    
    # Clean up the title (remove recording suffix, timestamp parts)
    # Example input: "שידור מבית הרבנית - 2026/01/17 21:07 IST – ‏Recording"
    # We want: "שידור מבית הרבנית"
    
    # Remove date/time patterns and "Recording" suffix
    import re
    # Remove patterns like "- 2026/01/17 21:07 IST – Recording"
    title = re.sub(r'\s*[-–]\s*\d{4}/\d{2}/\d{2}.*$', '', title)
    # Remove standalone "Recording" at the end
    title = re.sub(r'\s*[-–]?\s*‏?Recording‏?$', '', title)
    title = title.strip()
    
    # Add Hebrew date if available
    if lecture_date:
        day_name = get_hebrew_day_name(lecture_date)
        heb_date = get_hebrew_date_string(lecture_date)
        title = f"{title} | {day_name}, {heb_date}"
    
    return title


def get_category_for_date(gregorian_date: datetime) -> str:
    """Get the WordPress category name based on Hebrew year.
    
    Args:
        gregorian_date: The lecture date.
        
    Returns:
        Hebrew year name to use as category (e.g., 'שנת תשפ"ו').
    """
    year_name = get_hebrew_year_name(gregorian_date)
    return f"שנת {year_name}"
