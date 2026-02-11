"""FFmpeg error handling and parsing utilities."""

import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from enum import Enum
from core.config import Config


class FFmpegErrorType(Enum):
    """Categories of FFmpeg errors."""

    MISSING_CODEC = "missing_codec"
    CORRUPTED_INPUT = "corrupted_input"
    DISK_SPACE = "disk_space"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    INVALID_FORMAT = "invalid_format"
    UNKNOWN = "unknown"


class FFmpegError(Exception):
    """Exception raised for FFmpeg errors with categorization."""

    def __init__(
        self,
        error_type: FFmpegErrorType,
        message: str,
        stderr: str = ""
    ):
        """
        Initialize FFmpeg error.

        Args:
            error_type: Category of error
            message: Human-readable error message
            stderr: Raw stderr output from FFmpeg
        """
        super().__init__(message)
        self.error_type = error_type
        self.stderr = stderr

    def is_transient(self) -> bool:
        """
        Check if error is transient and worth retrying.

        Returns:
            True if error might succeed on retry, False otherwise
        """
        transient_types = {
            FFmpegErrorType.TIMEOUT,
            FFmpegErrorType.UNKNOWN
        }
        return self.error_type in transient_types


class FFmpegErrorParser:
    """Parses FFmpeg stderr output to categorize errors."""

    # Error patterns for categorization
    PATTERNS = {
        FFmpegErrorType.MISSING_CODEC: [
            r"Unknown encoder",
            r"Encoder .* not found",
            r"codec not currently supported",
        ],
        FFmpegErrorType.CORRUPTED_INPUT: [
            r"Invalid data found",
            r"corrupt",
            r"Header missing",
            r"moov atom not found",
        ],
        FFmpegErrorType.DISK_SPACE: [
            r"No space left on device",
            r"Disk quota exceeded",
        ],
        FFmpegErrorType.PERMISSION_DENIED: [
            r"Permission denied",
            r"Access is denied",
        ],
        FFmpegErrorType.INVALID_FORMAT: [
            r"Invalid argument",
            r"Unsupported codec",
            r"does not contain any stream",
        ],
    }

    @classmethod
    def parse_error(cls, stderr: str, returncode: int) -> FFmpegError:
        """
        Parse FFmpeg stderr and categorize the error.

        Args:
            stderr: FFmpeg stderr output
            returncode: FFmpeg process return code

        Returns:
            FFmpegError with categorized error type
        """
        stderr_lower = stderr.lower()

        # Check each pattern category
        for error_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, stderr_lower, re.IGNORECASE):
                    message = cls._extract_error_message(stderr, error_type)
                    return FFmpegError(error_type, message, stderr)

        # Default to unknown error
        message = cls._extract_error_message(stderr, FFmpegErrorType.UNKNOWN)
        return FFmpegError(FFmpegErrorType.UNKNOWN, message, stderr)

    @classmethod
    def _extract_error_message(
        cls,
        stderr: str,
        error_type: FFmpegErrorType
    ) -> str:
        """
        Extract human-readable error message from stderr.

        Args:
            stderr: FFmpeg stderr output
            error_type: Categorized error type

        Returns:
            Human-readable error message
        """
        # Try to find the actual error line
        lines = stderr.split('\n')
        error_lines = [
            line for line in lines
            if any(keyword in line.lower() for keyword in ['error', 'invalid', 'failed'])
        ]

        if error_lines:
            # Return the first error line, cleaned up
            return error_lines[0].strip()

        # Fallback to generic message based on type
        messages = {
            FFmpegErrorType.MISSING_CODEC: "Required audio codec not available",
            FFmpegErrorType.CORRUPTED_INPUT: "Input file is corrupted or invalid",
            FFmpegErrorType.DISK_SPACE: "Insufficient disk space",
            FFmpegErrorType.PERMISSION_DENIED: "Permission denied writing output file",
            FFmpegErrorType.INVALID_FORMAT: "Invalid or unsupported file format",
            FFmpegErrorType.TIMEOUT: "FFmpeg operation timed out",
            FFmpegErrorType.UNKNOWN: "FFmpeg conversion failed",
        }
        return messages.get(error_type, "Unknown FFmpeg error")


def convert_audio(
    input_path: Path,
    output_path: Path,
    bitrate: str = Config.AUDIO_BITRATE,
    codec: str = Config.AUDIO_CODEC,
    timeout: int = Config.FFMPEG_CONVERSION_TIMEOUT_SEC
) -> Tuple[bool, Optional[FFmpegError]]:
    """
    Convert audio file using FFmpeg with proper error handling.

    Args:
        input_path: Path to input audio/video file
        output_path: Path where converted audio should be saved
        bitrate: Audio bitrate (e.g., "320k")
        codec: Audio codec to use (e.g., "libmp3lame")
        timeout: Timeout in seconds for conversion

    Returns:
        Tuple of (success: bool, error: Optional[FFmpegError])
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", str(input_path),
                "-vn",  # No video
                "-acodec", codec,
                "-b:a", bitrate,
                "-y",  # Overwrite output file
                str(output_path)
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL  # Prevent FFmpeg from waiting for input
        )

        if result.returncode != 0:
            stderr = result.stderr.decode() if result.stderr else ""
            error = FFmpegErrorParser.parse_error(stderr, result.returncode)
            return False, error

        return True, None

    except subprocess.TimeoutExpired:
        error = FFmpegError(
            FFmpegErrorType.TIMEOUT,
            f"FFmpeg conversion timed out after {timeout} seconds",
            ""
        )
        return False, error
    except Exception as e:
        error = FFmpegError(
            FFmpegErrorType.UNKNOWN,
            f"Unexpected error during conversion: {str(e)}",
            ""
        )
        return False, error
