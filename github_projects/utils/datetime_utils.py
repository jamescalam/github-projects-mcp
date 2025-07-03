from datetime import datetime, timezone
from typing import Optional 
import re


def parse_datetime_flexible(dt_str: Optional[str]) -> Optional[datetime]:
    """
    Parse datetime string with flexible format support.
    
    Handles various datetime formats and ensures timezone-aware output.
    Supports:
    - ISO format with Z suffix: "2025-01-01T12:00:00Z"
    - ISO format with timezone: "2025-01-01T12:00:00+00:00"
    - ISO format without timezone: "2025-01-01T12:00:00"
    - Date only: "2025-01-01"
    - Various other common formats
    
    Returns timezone-aware datetime or None if parsing fails.
    """
    if not dt_str:
        return None
    
    # Convert to string if needed
    dt_str = str(dt_str).strip()
    
    try:
        # Handle ISO format with Z suffix (GitHub API format)
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'
            return datetime.fromisoformat(dt_str)
        
        # Handle ISO format with timezone offset
        if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', dt_str):
            return datetime.fromisoformat(dt_str)
        
        # Handle ISO format without timezone (assume UTC)
        if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', dt_str):
            dt = datetime.fromisoformat(dt_str)
            return dt.replace(tzinfo=timezone.utc)
        
        # Handle date-only format (assume start of day UTC)
        if re.match(r'^\d{4}-\d{2}-\d{2}$', dt_str):
            dt = datetime.strptime(dt_str, "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc)
        
        # Try standard datetime formats
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str, fmt)
                # Make timezone-aware if not already
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        
        # If all else fails, try fromisoformat as last resort
        return datetime.fromisoformat(dt_str)
        
    except (ValueError, TypeError, AttributeError):
        return None


def ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime is timezone-aware. If naive, assume UTC.
    
    Args:
        dt: datetime object (can be naive or aware)
        
    Returns:
        timezone-aware datetime or None if input is None
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    
    return dt


def normalize_datetime_for_comparison(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalize datetime for comparison by ensuring it's timezone-aware.
    
    Args:
        dt: datetime object to normalize
        
    Returns:
        timezone-aware datetime normalized to UTC, or None if input is None
    """
    if dt is None:
        return None
    
    dt = ensure_timezone_aware(dt)
    if dt is None:
        return None
    
    # Convert to UTC for consistent comparison
    return dt.astimezone(timezone.utc)


def parse_date_string(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse date string in YYYY-MM-DD format and return timezone-aware datetime.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        
    Returns:
        timezone-aware datetime at start of day UTC, or None if parsing fails
    """
    if not date_str:
        return None
    
    try:
        dt = datetime.strptime(str(date_str), "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def format_datetime_for_display(dt: Optional[datetime]) -> str:
    """
    Format datetime for display in a user-friendly format.
    
    Args:
        dt: datetime object to format
        
    Returns:
        Formatted string or "N/A" if dt is None
    """
    if dt is None:
        return "N/A"
    
    dt = ensure_timezone_aware(dt)
    if dt is None:
        return "N/A"
    
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC") 