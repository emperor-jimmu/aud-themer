"""Utility functions for file system operations and validation."""

import re
import time
from pathlib import Path
from difflib import SequenceMatcher
from functools import wraps
from typing import Callable, Any
from core.config import Config


def validate_path(path: Path) -> bool:
    """
    Validate that a path exists and is a directory.

    Args:
        path: Path object to validate

    Returns:
        True if path exists and is a directory, False otherwise
    """
    return path.exists() and path.is_dir()


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to ensure OS compatibility.

    Removes or replaces characters that are invalid in filenames
    on Windows, macOS, and Linux.

    Args:
        filename: Original filename string

    Returns:
        Sanitized filename safe for all major operating systems
    """
    # Remove or replace invalid characters: < > : " / \ | ? *
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)

    # Remove control characters (ASCII 0-31)
    sanitized = re.sub(r'[\x00-\x1f]', '', sanitized)

    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)

    # Strip leading/trailing whitespace and dots
    sanitized = sanitized.strip('. ')

    # If empty after sanitization, use a default name
    if not sanitized:
        sanitized = 'unnamed'

    return sanitized


def validate_file_size(file_path: Path, min_size_bytes: int = Config.MIN_FILE_SIZE_BYTES) -> bool:
    """
    Validate that a file meets minimum size requirements.

    Args:
        file_path: Path to the file to validate
        min_size_bytes: Minimum file size in bytes (default: 500KB)

    Returns:
        True if file exists and is larger than min_size_bytes, False otherwise
    """
    if not file_path.exists() or not file_path.is_file():
        return False

    return file_path.stat().st_size > min_size_bytes


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity ratio between two strings.

    Uses difflib.SequenceMatcher to compute similarity ratio.
    Comparison is case-insensitive.

    Args:
        name1: First string to compare
        name2: Second string to compare

    Returns:
        Similarity ratio between 0.0 (no match) and 1.0 (exact match)
    """
    return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 0.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator to retry a function with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 0)
        backoff_factor: Multiplier for delay between retries (default: 2.0)
        exceptions: Tuple of exception types to catch and retry (default: all exceptions)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_attempts=3, initial_delay=0, backoff_factor=2)
        def network_operation():
            # This will retry up to 3 times with delays: 0s, 2s, 4s
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    # If this was the last attempt, raise the exception
                    if attempt == max_attempts - 1:
                        raise

                    # Wait before retrying (skip delay on first attempt if initial_delay is 0)
                    if delay > 0 or attempt > 0:
                        time.sleep(delay if attempt == 0 else delay * (backoff_factor ** attempt))

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            return None

        return wrapper
    return decorator


def get_file_size_formatted(file_path: Path) -> str:
    """
    Get formatted file size string.

    Args:
        file_path: Path to the file

    Returns:
        Formatted file size string (e.g., "2.5 MB", "512 KB")
    """
    if not file_path.exists():
        return "0 B"
    
    size_bytes = file_path.stat().st_size
    
    # Convert to appropriate unit
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def get_audio_duration(file_path: Path) -> str:
    """
    Get audio duration using ffprobe.

    Args:
        file_path: Path to the audio file

    Returns:
        Formatted duration string (e.g., "3:45", "1:23") or "unknown" if unable to determine
    """
    import subprocess
    
    if not file_path.exists():
        return "unknown"
    
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file_path)
            ],
            capture_output=True,
            timeout=5,
            check=False
        )
        
        if result.returncode == 0 and result.stdout:
            duration_seconds = float(result.stdout.decode().strip())
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            return f"{minutes}:{seconds:02d}"
        
        return "unknown"
    except (subprocess.TimeoutExpired, ValueError, Exception):
        return "unknown"
