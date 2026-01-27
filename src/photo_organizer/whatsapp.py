"""
WhatsApp filename parsing for extracting date/time information.

Supported patterns:
- WhatsApp Image 2024-10-01 at 10.06.47 AM.jpeg
- WhatsApp Video 2025-02-03 at 2.38.55 AM.mp4
- IMG-20241001-WA0001.jpg
- VID-20241001-WA0001.mp4
"""

import re
from datetime import datetime, date, time
from typing import Optional, Tuple, NamedTuple
from dataclasses import dataclass


class WhatsAppDateTime(NamedTuple):
    """Result of parsing WhatsApp filename."""
    date_value: date
    time_value: Optional[time]  # None if only date was extracted
    pattern_type: str  # 'full' or 'date_only'
    original_pattern: str  # Which regex pattern matched


# Pattern 1: "WhatsApp Image 2024-10-01 at 10.06.47 AM.jpeg"
# Pattern 2: "WhatsApp Video 2025-02-03 at 2.38.55 AM.mp4"
WHATSAPP_FULL_DATETIME_PATTERN = re.compile(
    r'^WhatsApp\s+(Image|Video)\s+'
    r'(\d{4})-(\d{2})-(\d{2})\s+at\s+'
    r'(\d{1,2})\.(\d{2})\.(\d{2})\s*(AM|PM)?',
    re.IGNORECASE
)

# Pattern 3: "IMG-20241001-WA0001.jpg"
# Pattern 4: "VID-20241001-WA0001.mp4"
WHATSAPP_DATE_ONLY_PATTERN = re.compile(
    r'^(IMG|VID)-(\d{4})(\d{2})(\d{2})-WA\d+',
    re.IGNORECASE
)

# Additional pattern for other WhatsApp variants
# Pattern: "IMG_20241001_WA0001.jpg" (underscore variant)
WHATSAPP_DATE_ONLY_UNDERSCORE_PATTERN = re.compile(
    r'^(IMG|VID)_(\d{4})(\d{2})(\d{2})_WA\d+',
    re.IGNORECASE
)


def parse_whatsapp_filename(filename: str) -> Optional[WhatsAppDateTime]:
    """
    Parse a WhatsApp filename to extract date and optionally time.
    
    Args:
        filename: The filename to parse (with or without path)
    
    Returns:
        WhatsAppDateTime if parsing successful, None otherwise
    """
    # Extract just the filename part if path included
    if '/' in filename:
        filename = filename.split('/')[-1]
    if '\\' in filename:
        filename = filename.split('\\')[-1]
    
    # Try full datetime pattern first
    match = WHATSAPP_FULL_DATETIME_PATTERN.match(filename)
    if match:
        media_type, year, month, day, hour, minute, second, am_pm = match.groups()
        
        year = int(year)
        month = int(month)
        day = int(day)
        hour = int(hour)
        minute = int(minute)
        second = int(second)
        
        # Handle AM/PM
        if am_pm:
            am_pm = am_pm.upper()
            if am_pm == 'PM' and hour != 12:
                hour += 12
            elif am_pm == 'AM' and hour == 12:
                hour = 0
        
        try:
            date_val = date(year, month, day)
            time_val = time(hour, minute, second)
            return WhatsAppDateTime(
                date_value=date_val,
                time_value=time_val,
                pattern_type='full',
                original_pattern='whatsapp_full_datetime'
            )
        except ValueError:
            return None
    
    # Try date-only patterns
    for pattern, pattern_name in [
        (WHATSAPP_DATE_ONLY_PATTERN, 'whatsapp_date_only'),
        (WHATSAPP_DATE_ONLY_UNDERSCORE_PATTERN, 'whatsapp_date_only_underscore'),
    ]:
        match = pattern.match(filename)
        if match:
            media_type, year, month, day = match.groups()
            
            try:
                date_val = date(int(year), int(month), int(day))
                return WhatsAppDateTime(
                    date_value=date_val,
                    time_value=None,
                    pattern_type='date_only',
                    original_pattern=pattern_name
                )
            except ValueError:
                continue
    
    return None


def is_whatsapp_file(filename: str) -> bool:
    """Check if a filename appears to be from WhatsApp."""
    return parse_whatsapp_filename(filename) is not None


def format_whatsapp_datetime(wa_dt: WhatsAppDateTime, 
                             inferred_time: Optional[time] = None) -> Optional[datetime]:
    """
    Create a full datetime from WhatsApp parsed data.
    
    Args:
        wa_dt: Parsed WhatsApp datetime
        inferred_time: Time to use if wa_dt only has date
    
    Returns:
        Complete datetime or None if time cannot be determined
    """
    if wa_dt.time_value is not None:
        return datetime.combine(wa_dt.date_value, wa_dt.time_value)
    elif inferred_time is not None:
        return datetime.combine(wa_dt.date_value, inferred_time)
    return None


def get_whatsapp_media_type(filename: str) -> Optional[str]:
    """
    Determine if WhatsApp file is image or video.
    
    Returns:
        'image', 'video', or None if not a WhatsApp file
    """
    filename_lower = filename.lower()
    
    if 'whatsapp image' in filename_lower or filename_lower.startswith('img-') or filename_lower.startswith('img_'):
        return 'image'
    elif 'whatsapp video' in filename_lower or filename_lower.startswith('vid-') or filename_lower.startswith('vid_'):
        return 'video'
    
    return None