# Code Review: Production Readiness - Requirements

## 1. Overview

This spec documents a comprehensive production-ready code review of the Show Theme CLI codebase. The review identifies issues across architecture, code quality, testing, logging, error handling, and operational concerns, prioritized by severity.

## 2. Critical Issues (Must Fix)

### 2.1 Security & Resource Management

**Issue**: Subprocess injection vulnerability in anime_themes.py

- **Location**: `scrapers/anime_themes.py:27`
- **Problem**: Regex pattern `r'\s*\(\d{4}\)\s*` is incomplete (missing closing delimiter)
- **Impact**: Syntax error prevents module from loading
- **Fix**: Complete the regex pattern: `r'\s*\(\d{4}\)\s*$'`

**Issue**: No timeout on subprocess calls

- **Location**: `scrapers/tv_tunes.py:115`, `scrapers/anime_themes.py:185`
- **Problem**: FFmpeg subprocess has 60s timeout but no resource cleanup on timeout
- **Impact**: Zombie processes, resource leaks
- **Fix**: Add proper cleanup in timeout exception handlers

**Issue**: Browser resource leak in error paths

- **Location**: `scrapers/tv_tunes.py:48-150`
- **Problem**: Playwright browser not closed if exception occurs before finally block
- **Impact**: Memory leaks, file descriptor exhaustion
- **Fix**: Use context manager or ensure browser.close() in all paths

### 2.2 Concurrency Issues

**Issue**: Race condition in results tracking

- **Location**: `core/orchestrator.py:108-110`
- **Problem**: `self.results` dict modified without lock in `process_show()` but has `_results_lock` that's only used in async wrapper
- **Impact**: Lost updates, incorrect counts in concurrent execution
- **Fix**: Use lock consistently in all result modifications

**Issue**: Async/sync mixing anti-pattern

- **Location**: `core/orchestrator.py:108-150`
- **Problem**: `process_show()` is synchronous but called via `asyncio.to_thread()`, scrapers are all synchronous
- **Impact**: Thread pool exhaustion, poor performance
- **Fix**: Either make scrapers truly async or remove async orchestration

### 2.3 Error Handling Gaps

**Issue**: Silent exception swallowing

- **Location**: `scrapers/tv_tunes.py:42-45`, `scrapers/youtube.py:67`
- **Problem**: Broad `except Exception` returns False without logging
- **Impact**: Debugging impossible, silent failures
- **Fix**: Log exceptions before returning False

**Issue**: Incomplete error context

- **Location**: `core/orchestrator.py:195-200`
- **Problem**: OSError handling checks string content instead of errno
- **Impact**: Fragile, locale-dependent error detection
- **Fix**: Use `e.errno == errno.ENOSPC` or `errno.EDQUOT`

## 3. High Priority Issues (Should Fix)

### 3.1 Code Smells & Design Issues

**Issue**: God class anti-pattern

- **Location**: `core/orchestrator.py:Orchestrator`
- **Problem**: 250+ lines, handles scanning, processing, display, async coordination
- **Impact**: Hard to test, maintain, extend
- **Fix**: Extract ResultsTracker, DirectoryScanner, ProgressReporter classes

**Issue**: Magic numbers scattered throughout

- **Location**: Multiple files
- **Examples**:
  - `500_000` (file size threshold) - appears in 5 different files
  - `30000` (timeout) - tv_tunes.py
  - `30.0` (timeout) - anime_themes.py
  - `60.0` (download timeout) - anime_themes.py
- **Impact**: Inconsistent behavior, hard to configure
- **Fix**: Define constants in config module or class-level

**Issue**: Tight coupling to Rich Console

- **Location**: All scraper classes
- **Problem**: Console passed to scrapers, mixed concerns (business logic + presentation)
- **Impact**: Hard to test, can't use scrapers without Rich
- **Fix**: Use logging for scrapers, console only in orchestrator

**Issue**: Inconsistent retry strategies

- **Location**: Multiple scrapers
- **Problem**:
  - tv_tunes: retries only PlaywrightTimeoutError
  - anime_themes: retries httpx timeouts
  - youtube: retries yt_dlp.DownloadError
  - Different backoff configs (0s initial delay everywhere)
- **Impact**: Inconsistent reliability
- **Fix**: Centralize retry configuration, use consistent strategy

### 3.2 Testing Gaps

**Issue**: No integration tests for actual scrapers

- **Location**: `tests/integration/` (empty or minimal)
- **Problem**: Unit tests use mocks, no real scraper validation
- **Impact**: Can't verify scrapers work with real sites
- **Fix**: Add integration tests with VCR.py for HTTP recording

**Issue**: Property tests don't test actual properties

- **Location**: `tests/properties/test_orchestrator_properties.py`
- **Problem**: Tests use mocks, don't verify real invariants
- **Example**: Property 2 "Directory Scanning Completeness" creates folders and counts them - this is a unit test, not a property
- **Impact**: False confidence in correctness
- **Fix**: Test real properties like "retry always succeeds or exhausts attempts", "file operations are idempotent"

**Issue**: Missing edge case tests

- **Location**: Test suite
- **Missing**:
  - Unicode in show names
  - Very long file paths (>260 chars on Windows)
  - Concurrent access to same folder
  - Network interruption mid-download
  - Partial file writes
- **Fix**: Add edge case test suite

**Issue**: No performance tests

- **Location**: Test suite
- **Problem**: No tests for concurrency limits, memory usage, large directories
- **Impact**: Can't verify performance characteristics
- **Fix**: Add performance test suite with benchmarks

### 3.3 Logging & Observability

**Issue**: Inconsistent logging levels

- **Location**: All scrapers
- **Problem**:
  - `_log_debug()` uses console output, not logger
  - `_log_error()` uses logger
  - No INFO or WARNING levels
- **Impact**: Can't filter logs properly, verbose mode required for any detail
- **Fix**: Use standard logging levels consistently

**Issue**: Missing structured logging

- **Location**: All files
- **Problem**: String formatting in logs, no context fields
- **Impact**: Hard to parse, search, aggregate logs
- **Fix**: Use structured logging (JSON) with context fields

**Issue**: No metrics or telemetry

- **Location**: Entire codebase
- **Problem**: No timing, success rates, source performance tracking
- **Impact**: Can't optimize, identify bottlenecks
- **Fix**: Add metrics collection (timing, counts, errors by source)

**Issue**: Error log file naming collision

- **Location**: `main.py:60`
- **Problem**: `errors-{timestamp}.log` created per run, no rotation
- **Impact**: Disk space exhaustion over time
- **Fix**: Use rotating file handler, configurable log directory

## 4. Medium Priority Issues (Nice to Have)

### 4.1 Code Quality

**Issue**: Missing type hints in many places

- **Location**: Multiple files
- **Examples**:
  - `core/utils.py:retry_with_backoff` - decorator return type
  - `scrapers/tv_tunes.py:_find_best_match` - return type
- **Impact**: Reduced IDE support, type checking
- **Fix**: Add complete type hints, enable mypy

**Issue**: Inconsistent docstring style

- **Location**: All files
- **Problem**: Mix of Google-style and incomplete docstrings
- **Impact**: Reduced documentation quality
- **Fix**: Standardize on one style (Google or NumPy)

**Issue**: Long methods

- **Location**: Multiple files
- **Examples**:
  - `tv_tunes.py:_search_and_download_with_retry` - 110 lines
  - `orchestrator.py:process_show` - 80 lines
- **Impact**: Hard to understand, test
- **Fix**: Extract helper methods

**Issue**: Duplicate code

- **Location**: All scrapers
- **Problem**: FFmpeg audio extraction duplicated in tv_tunes and anime_themes
- **Impact**: Maintenance burden, inconsistency
- **Fix**: Extract to shared utility function

**Issue**: Poor variable naming

- **Location**: Multiple files
- **Examples**:
  - `p` for playwright (tv_tunes.py:48)
  - `e` for exception (multiple places)
  - `f` for file handle (multiple places)
- **Impact**: Reduced readability
- **Fix**: Use descriptive names

### 4.2 Configuration & Flexibility

**Issue**: Hardcoded scraper priority

- **Location**: `core/orchestrator.py:68-75`
- **Problem**: Source priority hardcoded in method
- **Impact**: Can't customize without code changes
- **Fix**: Make priority configurable via config file

**Issue**: No configuration file support

- **Location**: Entire codebase
- **Problem**: All settings via CLI args or hardcoded
- **Impact**: Can't persist preferences, share configs
- **Fix**: Add config file support (YAML/TOML)

**Issue**: Hardcoded output format

- **Location**: All scrapers
- **Problem**: Always outputs MP3 at 320kbps
- **Impact**: Can't customize quality/format
- **Fix**: Make format and quality configurable

**Issue**: No plugin system

- **Location**: `core/orchestrator.py`
- **Problem**: Can't add scrapers without modifying code
- **Impact**: Hard to extend
- **Fix**: Add plugin discovery mechanism

### 4.3 User Experience

**Issue**: No progress indication for long operations

- **Location**: All scrapers
- **Problem**: Downloads can take minutes with no feedback
- **Impact**: Appears frozen
- **Fix**: Add progress bars for downloads

**Issue**: Poor error messages

- **Location**: Multiple files
- **Examples**:
  - "No sources found" - doesn't say which sources were tried
  - "Download failed" - no reason given
- **Impact**: Users can't troubleshoot
- **Fix**: Provide actionable error messages

**Issue**: No resume capability

- **Location**: Entire codebase
- **Problem**: If interrupted, must start over
- **Impact**: Wastes time on large directories
- **Fix**: Add state file to track progress

## 5. Low Priority Issues (Polish)

### 5.1 Documentation

**Issue**: Missing architecture documentation

- **Location**: Repository
- **Problem**: No docs explaining design decisions, extension points
- **Impact**: Hard for contributors to understand
- **Fix**: Add ARCHITECTURE.md

**Issue**: Incomplete README

- **Location**: Repository (assumed)
- **Problem**: No troubleshooting section, FAQ
- **Impact**: Repeated support questions
- **Fix**: Expand README with common issues

**Issue**: No API documentation

- **Location**: Code
- **Problem**: No generated API docs
- **Impact**: Hard to use as library
- **Fix**: Add Sphinx documentation

### 5.2 Development Experience

**Issue**: No pre-commit hooks

- **Location**: Repository
- **Problem**: No automated linting, formatting
- **Impact**: Inconsistent code style
- **Fix**: Add pre-commit config with black, isort, pylint

**Issue**: No CI/CD configuration

- **Location**: Repository
- **Problem**: No automated testing, releases
- **Impact**: Manual testing burden
- **Fix**: Add GitHub Actions workflow

**Issue**: Missing development documentation

- **Location**: Repository
- **Problem**: No CONTRIBUTING.md, development setup guide
- **Impact**: Hard for new contributors
- **Fix**: Add contributor documentation

## 6. Positive Observations

### 6.1 Strengths

- **Good separation of concerns**: Scrapers are independent, swappable
- **Comprehensive error handling**: Most error cases are handled
- **Property-based testing**: Good use of Hypothesis for validation
- **Rich console output**: Professional, user-friendly interface
- **Dependency validation**: Checks for FFmpeg and Playwright upfront
- **Idempotent operations**: Safe to re-run
- **Async support**: Foundation for concurrent processing

### 6.2 Best Practices Followed

- **Abstract base class**: Good use of ABC for scraper interface
- **Type hints**: Most functions have type annotations
- **Docstrings**: Most functions documented
- **Test markers**: Good test categorization
- **Retry logic**: Exponential backoff implemented
- **File validation**: Size checks prevent corrupt downloads

## 7. Acceptance Criteria

### 7.1 Critical Issues Fixed

- [ ] Regex syntax error in anime_themes.py fixed
- [ ] Browser resource leaks eliminated
- [ ] Race conditions in results tracking resolved
- [ ] Async/sync architecture clarified and consistent
- [ ] All exceptions logged before swallowing

### 7.2 High Priority Issues Addressed

- [ ] Magic numbers extracted to constants
- [ ] Orchestrator refactored (< 150 lines)
- [ ] Retry strategies unified
- [ ] Integration tests added for scrapers
- [ ] Structured logging implemented
- [ ] Metrics collection added

### 7.3 Code Quality Improved

- [ ] Type hints complete, mypy passing
- [ ] Docstrings standardized
- [ ] Long methods refactored (< 50 lines)
- [ ] Duplicate code eliminated
- [ ] Configuration file support added

### 7.4 Testing Enhanced

- [ ] Test coverage > 80%
- [ ] Property tests verify real invariants
- [ ] Edge case tests added
- [ ] Performance tests added

### 7.5 Documentation Complete

- [ ] ARCHITECTURE.md added
- [ ] README expanded with troubleshooting
- [ ] API documentation generated
- [ ] CONTRIBUTING.md added

## 8. Out of Scope

- Rewriting in another language
- Adding GUI interface
- Supporting additional media formats beyond audio
- Implementing custom audio processing beyond format conversion
- Building web service/API
