"""Configuration constants for the application."""


class Config:
    """Application-wide configuration constants."""

    # File validation
    MIN_FILE_SIZE_BYTES = 500_000  # 500KB minimum for valid theme files

    # Network timeouts (in seconds)
    DEFAULT_TIMEOUT_SEC = 30  # Default network timeout
    DOWNLOAD_TIMEOUT_SEC = 60  # Timeout for large file downloads
    PLAYWRIGHT_TIMEOUT_MS = 30_000  # Playwright timeout in milliseconds

    # Audio processing
    AUDIO_BITRATE = "320k"  # MP3 encoding bitrate for high quality
    AUDIO_CODEC = "libmp3lame"  # FFmpeg audio codec

    # YouTube constraints
    MAX_VIDEO_DURATION_SEC = 600  # 10 minutes max for YouTube videos

    # Rate limiting
    RATE_LIMIT_MIN_DELAY_SEC = 1.0  # Minimum delay between requests
    RATE_LIMIT_MAX_DELAY_SEC = 3.0  # Maximum delay between requests

    # Retry configuration
    MAX_RETRY_ATTEMPTS = 3  # Maximum number of retry attempts
    RETRY_INITIAL_DELAY_SEC = 0.0  # Initial delay before first retry
    RETRY_BACKOFF_FACTOR = 2.0  # Exponential backoff multiplier

    # FFmpeg timeouts
    FFMPEG_CONVERSION_TIMEOUT_SEC = 60  # Timeout for audio conversion

    # File extensions
    THEME_EXTENSIONS = ['.mp3', '.flac', '.wav']
    DEFAULT_THEME_FILENAME = 'theme.mp3'
