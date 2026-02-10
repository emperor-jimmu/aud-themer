"""Utility functions for file system operations and validation."""

import re
from pathlib import Path
from difflib import SequenceMatcher


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


def validate_file_size(file_path: Path, min_size_bytes: int = 500_000) -> bool:
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
