# Code Review: Production Readiness - Requirements

## 1. Overview

This spec documents a comprehensive production-ready code review of the Show Theme CLI codebase, identifying issues across architecture, code quality, testing, logging, and operational concerns.

## 2. Critical Issues (Must Fix)

### 2.1 Duplicate Retry Decorators

**Severity**: Critical  
**Files**: `scrapers/tv_tunes.py` (lines 48-56), `scrapers/youtube.py` (lines 42-50)

The same `@retry_with_backoff` decorator is applied twice to the same function, causing exponential retry behavior (9 attempts instead of 3).

**Impact**:

- Unnecessary network load and delays
- Confusing retry behavior for debugging
- Potential rate limiting issues

**Acceptance Criteria**:

- Remove duplicate decorators from both files
- Verify retry behavior is as expected (3 attempts max)
- Add unit tests to validate retry count

### 2.2 Incomplete Regex Pattern in anime_themes.py

**Severity**: Critical  
**Files**: `scrapers/anime_themes.py` (line 31)

The regex pattern `r'\s*\(\d{4}\)\s*` is incomplete and missing the closing delimiter, causing a syntax error.

**Impact**:

- Code will not run
- AnimeThemes scraper is completely broken

**Acceptance Criteria**:

- Fix regex pattern to properly strip year from show names
- Add unit test for year stripping functionality
- Verify AnimeThemes scraper works end-to-end

### 2.3 Missing Resource Cleanup in Scrapers

**Severity**: High  
**Files**: `scrapers/tv_tunes.py`, `scrapers/themes_moe.py`

Playwright browser instances may not be properly closed if exceptions occur during page operations, leading to resource leaks.

**Impact**:

- Memory leaks in long-running operations
- File descriptor exhaustion
- Zombie browser processes

**Acceptance Criteria**:

- Ensure browser cleanup happens in finally blocks
- Add context manager support for browser lifecycle
- Add integration tests that verify cleanup on exceptions

### 2.4 Hardcoded Magic Numbers

**Severity**: Medium  
**Files**: Multiple files

Magic numbers scattered throughout codebase:

- `500_000` (file size threshold) - appears in 5+ locations
- `30000` (timeout) - appears in multiple scrapers
- `320k` (audio bitrate) - appears in FFmpeg calls
- `600` (max video duration) - YouTube scraper

**Impact**:

- Difficult to maintain and update
- Inconsistent behavior if values diverge
- Poor code readability

**Acceptance Criteria**:

- Extract all magic numbers to class constants or config
- Document the reasoning behind each threshold
- Ensure consistency across all usages

## 3. High Priority Issues

### 3.1 Insufficient Error Context in Logging

**Severity**: High  
**Files**: All scraper files

Error logs lack contextual information needed for production debugging:

- No request IDs or correlation IDs
- No timing information
- No user/session context
- Limited structured logging

**Impact**:

- Difficult to debug production issues
- Cannot trace requests across components
- Poor observability

**Acceptance Criteria**:

- Add structured logging with context fields
- Include timing information for operations
- Add correlation IDs for request tracing
- Log key decision points (which scraper succeeded, why others failed)

### 3.2 No Rate Limiting or Backoff Between Sources

**Severity**: High  
**Files**: `core/orchestrator.py`

The orchestrator tries all scrapers in rapid succession without delays, potentially triggering rate limits or appearing as abuse.

**Impact**:

- Risk of IP bans from sources
- Potential service degradation
- Poor citizenship behavior

**Acceptance Criteria**:

- Add configurable delays between scraper attempts
- Implement exponential backoff for repeated failures
- Add rate limiting per source
- Document rate limit policies for each source

### 3.3 Incomplete FFmpeg Error Handling

**Severity**: High  
**Files**: `scrapers/tv_tunes.py`, `scrapers/anime_themes.py`

FFmpeg errors are logged but not properly categorized. Different failure modes (missing codec, corrupted input, disk space) are treated identically.

**Impact**:

- Cannot distinguish transient from permanent failures
- Poor user feedback
- Difficult to debug conversion issues

**Acceptance Criteria**:

- Parse FFmpeg stderr for specific error types
- Provide actionable error messages to users
- Retry transient errors, fail fast on permanent ones
- Add tests for different FFmpeg failure scenarios

### 3.4 No Timeout Configuration

**Severity**: High  
**Files**: Multiple scrapers

Timeouts are hardcoded and cannot be adjusted for slow networks or large files.

**Impact**:

- Fails on slow connections
- Cannot optimize for different environments
- Poor user experience in constrained networks

**Acceptance Criteria**:

- Make timeouts configurable via CLI or config file
- Provide sensible defaults
- Document timeout recommendations
- Add tests with various timeout scenarios

## 4. Medium Priority Issues

### 4.1 Tight Coupling Between Orchestrator and Scrapers

**Severity**: Medium  
**Files**: `core/orchestrator.py` (lines 52-59)

The orchestrator directly instantiates specific scraper classes, violating dependency injection principles.

**Impact**:

- Difficult to test in isolation
- Hard to add/remove scrapers dynamically
- Tight coupling reduces flexibility

**Acceptance Criteria**:

- Use dependency injection for scraper initialization
- Allow scrapers to be configured externally
- Support dynamic scraper registration
- Improve testability with mock scrapers

### 4.2 Inconsistent Error Handling Patterns

**Severity**: Medium  
**Files**: All scraper files

Different scrapers handle errors differently:

- Some catch broad exceptions, others specific ones
- Inconsistent logging patterns
- Different retry strategies

**Impact**:

- Unpredictable behavior
- Difficult to maintain
- Inconsistent user experience

**Acceptance Criteria**:

- Standardize error handling across all scrapers
- Create error handling guidelines
- Implement common error handling utilities
- Add tests for error handling consistency

### 4.3 No Progress Indication for Long Operations

**Severity**: Medium  
**Files**: `core/orchestrator.py`, scraper files

Long-running operations (downloads, conversions) provide no progress feedback.

**Impact**:

- Poor user experience
- Appears frozen during long operations
- Cannot estimate completion time

**Acceptance Criteria**:

- Add progress bars for downloads
- Show conversion progress
- Display estimated time remaining
- Add tests for progress reporting

### 4.4 Insufficient Input Validation

**Severity**: Medium  
**Files**: `main.py`, `core/orchestrator.py`

Limited validation of user inputs:

- No validation of show name format
- No checks for extremely long paths
- No validation of output path writability

**Impact**:

- Cryptic errors for invalid inputs
- Potential security issues
- Poor user experience

**Acceptance Criteria**:

- Validate all user inputs at entry points
- Provide clear error messages for invalid inputs
- Add path length and character validation
- Test with malformed inputs

### 4.5 Missing Concurrency Controls

**Severity**: Medium  
**Files**: `core/orchestrator.py`

The orchestrator has a `max_concurrent` parameter but processes shows sequentially. The concurrency infrastructure is incomplete.

**Impact**:

- Slower than necessary processing
- Misleading parameter
- Wasted opportunity for parallelization

**Acceptance Criteria**:

- Implement actual concurrent processing or remove the parameter
- Add proper synchronization for shared state
- Test concurrent execution
- Document concurrency behavior

## 5. Low Priority Issues

### 5.1 Inconsistent Naming Conventions

**Severity**: Low  
**Files**: Multiple files

Inconsistent naming:

- `_log_debug` vs `_log_error` (underscore prefix)
- `search_and_download` vs `_search_and_download_with_retry`
- Mixed use of `show_name` vs `anime_name`

**Impact**:

- Reduced code readability
- Confusion about public vs private methods

**Acceptance Criteria**:

- Standardize naming conventions
- Document naming guidelines
- Apply consistently across codebase

### 5.2 Incomplete Type Hints

**Severity**: Low  
**Files**: Multiple files

Some functions lack complete type hints, particularly for complex return types and optional parameters.

**Impact**:

- Reduced IDE support
- Harder to catch type errors
- Less self-documenting code

**Acceptance Criteria**:

- Add complete type hints to all public methods
- Use Optional, Union, and other typing constructs appropriately
- Run mypy or similar type checker
- Fix all type errors

### 5.3 Missing Docstring Details

**Severity**: Low  
**Files**: Multiple files

While most functions have docstrings, many lack:

- Raises sections for exceptions
- Examples for complex functions
- Return value details

**Impact**:

- Harder to understand expected behavior
- Incomplete API documentation

**Acceptance Criteria**:

- Add Raises sections to all docstrings
- Include examples for complex functions
- Document all return value possibilities
- Generate API documentation

### 5.4 Test Coverage Gaps

**Severity**: Low  
**Files**: Test suite

Missing test coverage for:

- Edge cases in retry logic
- All FFmpeg error scenarios
- Concurrent execution paths
- Rate limiting behavior

**Impact**:

- Bugs may slip through
- Refactoring is riskier
- Less confidence in changes

**Acceptance Criteria**:

- Achieve >85% code coverage
- Add tests for all identified gaps
- Add integration tests for end-to-end flows
- Document testing strategy

### 5.5 No Performance Monitoring

**Severity**: Low  
**Files**: All files

No instrumentation for performance monitoring:

- No timing metrics
- No success/failure rates
- No source performance comparison

**Impact**:

- Cannot identify performance bottlenecks
- No data for optimization decisions
- Cannot track degradation over time

**Acceptance Criteria**:

- Add timing instrumentation
- Log performance metrics
- Create performance dashboard
- Set performance baselines

## 6. Testing Quality Issues

### 6.1 Limited Property-Based Test Coverage

**Severity**: Medium  
**Files**: `tests/properties/`

Property-based tests exist but don't cover:

- Scraper search/download properties
- Retry behavior properties
- Concurrent execution properties
- Error recovery properties

**Acceptance Criteria**:

- Add property tests for scraper behavior
- Test retry properties (idempotency, max attempts)
- Test concurrent execution properties
- Increase Hypothesis examples to 100

### 6.2 Mock Overuse in Unit Tests

**Severity**: Low  
**Files**: `tests/unit/`

Heavy reliance on mocks may hide integration issues. Some tests mock too much, testing the mocks rather than the code.

**Acceptance Criteria**:

- Balance unit tests with integration tests
- Use real objects where practical
- Add more end-to-end tests
- Document when mocking is appropriate

## 7. Security Considerations

### 7.1 No Input Sanitization for Shell Commands

**Severity**: High  
**Files**: FFmpeg subprocess calls

Show names are passed to FFmpeg without sanitization, potential command injection risk.

**Impact**:

- Security vulnerability
- Potential arbitrary code execution

**Acceptance Criteria**:

- Sanitize all inputs passed to subprocess
- Use subprocess argument lists (not shell=True)
- Add security tests with malicious inputs
- Document security considerations

### 7.2 No HTTPS Verification Configuration

**Severity**: Medium  
**Files**: `scrapers/anime_themes.py`

HTTPS certificate verification is not explicitly configured, relying on defaults.

**Impact**:

- Potential MITM attacks
- Unclear security posture

**Acceptance Criteria**:

- Explicitly enable certificate verification
- Add configuration for custom CA bundles
- Document security settings
- Test with invalid certificates

## 8. Operational Concerns

### 8.1 No Health Check Mechanism

**Severity**: Medium  
**Files**: N/A (missing feature)

No way to verify dependencies are working before processing.

**Impact**:

- Fails late in processing
- Wastes time on doomed operations

**Acceptance Criteria**:

- Add health check command
- Verify all dependencies before processing
- Test connectivity to sources
- Provide actionable diagnostics

### 8.2 Insufficient Logging for Production Debugging

**Severity**: High  
**Files**: All files

Current logging is minimal and not structured for production use.

**Impact**:

- Difficult to debug production issues
- Cannot track down failures
- Poor operational visibility

**Acceptance Criteria**:

- Add structured logging (JSON format option)
- Include request/response details
- Log all decision points
- Add log levels for different verbosity

### 8.3 No Metrics or Telemetry

**Severity**: Low  
**Files**: N/A (missing feature)

No metrics collection for operational monitoring.

**Impact**:

- Cannot track success rates
- No visibility into performance
- Cannot detect degradation

**Acceptance Criteria**:

- Add metrics collection
- Track success/failure rates per source
- Monitor processing times
- Export metrics in standard format

## 9. Documentation Gaps

### 9.1 Missing Architecture Documentation

**Severity**: Low  
**Files**: Documentation

No high-level architecture documentation explaining design decisions.

**Acceptance Criteria**:

- Document architecture decisions
- Explain scraper priority order
- Document error handling strategy
- Create architecture diagrams

### 9.2 Incomplete Troubleshooting Guide

**Severity**: Low  
**Files**: Documentation

No troubleshooting guide for common issues.

**Acceptance Criteria**:

- Document common failure scenarios
- Provide troubleshooting steps
- Include FAQ section
- Add debugging tips

## 10. Success Criteria

This code review is complete when:

1. All critical issues are fixed and tested
2. High priority issues have remediation plans
3. Medium priority issues are documented for future work
4. Low priority issues are tracked in backlog
5. Security issues are addressed
6. Operational concerns have mitigation strategies
7. Test coverage is improved
8. Documentation is updated

## 11. Out of Scope

The following are explicitly out of scope for this review:

- Complete rewrite of the codebase
- Adding new features or scrapers
- Performance optimization beyond critical issues
- UI/UX improvements
- Internationalization
- Database integration
