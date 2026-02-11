# Code Review Fixes - Design Document

## 1. Overview

This document outlines the design for fixing critical and high priority issues identified in the code review.

## 2. Critical Issues - Solutions

### 2.1 Duplicate Retry Decorators

**Solution**: Remove duplicate decorators from `tv_tunes.py` and `youtube.py`

**Implementation**:

- Keep only one `@retry_with_backoff` decorator per function
- Verify retry count with unit tests

### 2.2 Incomplete Regex Pattern

**Solution**: Fix regex in `anime_themes.py` line 31

**Implementation**:

```python
clean_name = re.sub(r'\s*\(\d{4}\)\s*$', '', show_name).strip()
```

### 2.3 Resource Cleanup

**Solution**: Ensure Playwright browsers are always closed using context managers

**Implementation**:

- Use try-finally blocks consistently
- Move browser close to finally block
- Add context manager wrapper for browser lifecycle

### 2.4 Magic Numbers

**Solution**: Extract all magic numbers to class constants

**Implementation**:

- Create constants at class level
- Add docstrings explaining each threshold
- Update all references

**Constants to extract**:

```python
MIN_FILE_SIZE_BYTES = 500_000  # 500KB minimum for valid theme files
DEFAULT_TIMEOUT_MS = 30_000    # 30 seconds for network operations
AUDIO_BITRATE = "320k"         # MP3 encoding bitrate
MAX_VIDEO_DURATION_SEC = 600   # 10 minutes max for YouTube videos
RATE_LIMIT_DELAY_SEC = (1, 3)  # Random delay between 1-3 seconds
```

## 3. High Priority Issues - Solutions

### 3.1 Structured Logging

**Solution**: Implement structured logging with context

**Implementation**:

- Create logging utility with context support
- Add correlation IDs for request tracing
- Include timing information
- Add structured fields (source, show_name, operation, duration)

**New utility**: `core/logging_utils.py`

```python
class StructuredLogger:
    def log_operation(self, operation, show_name, source, duration, success, error=None)
    def log_scraper_attempt(self, source, show_name, result)
    def log_download(self, source, show_name, file_size, duration)
```

### 3.2 Rate Limiting

**Solution**: Add configurable delays between scraper attempts

**Implementation**:

- Add delay after each scraper attempt (success or failure)
- Use random jitter to avoid thundering herd
- Make delays configurable
- Add per-source rate limiting

**New class**: `core/rate_limiter.py`

```python
class RateLimiter:
    def __init__(self, min_delay, max_delay)
    def wait(self, source_name)
    def record_attempt(self, source_name)
```

### 3.3 FFmpeg Error Handling

**Solution**: Parse FFmpeg stderr and categorize errors

**Implementation**:

- Create FFmpeg error parser
- Categorize errors (missing codec, corrupted input, disk space, timeout)
- Provide actionable error messages
- Retry transient errors only

**New utility**: `core/ffmpeg_utils.py`

```python
class FFmpegError(Exception):
    def __init__(self, error_type, message, stderr)

class FFmpegErrorParser:
    def parse_error(self, stderr) -> FFmpegError
    def is_transient(self, error) -> bool
```

### 3.4 Configurable Timeouts

**Solution**: Make timeouts configurable via CLI and config

**Implementation**:

- Add timeout parameters to CLI
- Pass timeouts to scrapers
- Provide sensible defaults
- Document timeout recommendations

**CLI changes**:

```python
@app.command()
def main(
    ...
    timeout: int = typer.Option(30, "--timeout", "-t", help="Network timeout in seconds"),
    download_timeout: int = typer.Option(60, "--download-timeout", help="Download timeout in seconds")
)
```

### 3.5 Input Sanitization

**Solution**: Sanitize all inputs passed to subprocess calls

**Implementation**:

- Create input sanitization utility
- Validate show names before passing to FFmpeg
- Use subprocess argument lists (already doing this)
- Add security tests

**New utility**: `core/security.py`

```python
def sanitize_for_subprocess(value: str) -> str
def validate_show_name(show_name: str) -> bool
```

## 4. Implementation Plan

### Phase 1: Critical Fixes (Immediate)

1. Fix duplicate retry decorators
2. Fix regex pattern in anime_themes.py
3. Improve resource cleanup
4. Extract magic numbers to constants

### Phase 2: High Priority Fixes (Next)

1. Implement structured logging
2. Add rate limiting
3. Improve FFmpeg error handling
4. Add configurable timeouts
5. Add input sanitization

### Phase 3: Testing

1. Add unit tests for all fixes
2. Add integration tests
3. Add security tests
4. Verify no regressions

## 5. File Changes Summary

### New Files

- `core/logging_utils.py` - Structured logging utilities
- `core/rate_limiter.py` - Rate limiting implementation
- `core/ffmpeg_utils.py` - FFmpeg error handling
- `core/security.py` - Input sanitization
- `core/config.py` - Configuration constants

### Modified Files

- `scrapers/tv_tunes.py` - Remove duplicate decorator, add constants, improve cleanup
- `scrapers/youtube.py` - Remove duplicate decorator, add constants
- `scrapers/anime_themes.py` - Fix regex, add constants
- `scrapers/themes_moe.py` - Add constants, improve cleanup
- `scrapers/base.py` - Add structured logging support
- `core/orchestrator.py` - Add rate limiting, structured logging
- `main.py` - Add timeout configuration
- `core/utils.py` - Add security utilities

### New Test Files

- `tests/unit/test_logging_utils.py`
- `tests/unit/test_rate_limiter.py`
- `tests/unit/test_ffmpeg_utils.py`
- `tests/unit/test_security.py`
- `tests/integration/test_rate_limiting.py`

## 6. Backward Compatibility

All changes maintain backward compatibility:

- New CLI options have defaults
- Existing behavior preserved
- No breaking API changes

## 7. Performance Impact

Expected performance changes:

- Slight slowdown due to rate limiting (intentional)
- Minimal overhead from structured logging
- No impact on success rates
- Better error recovery may improve overall throughput
