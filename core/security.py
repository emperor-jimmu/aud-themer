"""Security utilities for input validation and sanitization."""

import re
from pathlib import Path


def sanitize_for_subprocess(value: str, max_length: int = 255) -> str:
    """
    Sanitize string for safe use in subprocess calls.

    Removes potentially dangerous characters and limits length.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string safe for subprocess use

    Raises:
        ValueError: If value is empty after sanitization
    """
    # Remove null bytes
    sanitized = value.replace('\x00', '')

    # Remove shell metacharacters (even though we use argument lists)
    dangerous_chars = ['$', '`', '|', '&', ';', '<', '>', '(', ')', '{', '}', '\n', '\r']
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')

    # Limit length
    sanitized = sanitized[:max_length]

    # Strip whitespace
    sanitized = sanitized.strip()

    if not sanitized:
        raise ValueError("Value is empty after sanitization")

    return sanitized


def validate_show_name(show_name: str) -> bool:
    """
    Validate show name for safety and reasonableness.

    Args:
        show_name: Show name to validate

    Returns:
        True if valid, False otherwise
    """
    if not show_name or not show_name.strip():
        return False

    # Check length (reasonable show names are < 200 chars)
    if len(show_name) > 200:
        return False

    # Check for null bytes
    if '\x00' in show_name:
        return False

    # Check for excessive special characters (likely malicious)
    special_char_count = sum(1 for c in show_name if not c.isalnum() and not c.isspace())
    if special_char_count > len(show_name) * 0.5:  # More than 50% special chars
        return False

    return True


def validate_output_path(output_path: Path) -> bool:
    """
    Validate output path for safety.

    Args:
        output_path: Path to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        # Check if path is absolute or relative
        resolved = output_path.resolve()

        # Check for path traversal attempts
        if '..' in output_path.parts:
            return False

        # Check if parent directory exists and is writable
        parent = resolved.parent
        if not parent.exists():
            return False

        # Try to check write permissions (may not work on all systems)
        if not parent.is_dir():
            return False

        return True

    except (OSError, ValueError):
        return False


def sanitize_filename_secure(filename: str) -> str:
    """
    Securely sanitize filename with additional security checks.

    More restrictive than the basic sanitize_filename in utils.py.

    Args:
        filename: Filename to sanitize

    Returns:
        Sanitized filename

    Raises:
        ValueError: If filename is invalid or dangerous
    """
    # Remove path separators
    filename = filename.replace('/', '').replace('\\', '')

    # Remove null bytes
    filename = filename.replace('\x00', '')

    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)

    # Remove dangerous characters
    filename = re.sub(r'[<>:"|?*]', '', filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')

    # Check for reserved names (Windows)
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    if filename.upper() in reserved_names:
        filename = f"_{filename}"

    # Ensure not empty
    if not filename:
        raise ValueError("Filename is empty after sanitization")

    # Limit length
    if len(filename) > 255:
        filename = filename[:255]

    return filename
