"""Property-based tests for retry logic with exponential backoff."""

import time
from unittest.mock import Mock
import pytest
from hypothesis import given, strategies as st, settings

from core.utils import retry_with_backoff


# Feature: show-theme-cli, Property 16: Retry with Exponential Backoff
@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    max_attempts=st.integers(min_value=1, max_value=5),
    should_succeed_on_attempt=st.integers(min_value=1, max_value=5)
)
def test_retry_attempts_count(max_attempts, should_succeed_on_attempt):
    """
    Property: For any max_attempts value, the decorated function should be called
    at most max_attempts times before either succeeding or raising an exception.
    
    Validates: Requirements 9.1
    """
    call_count = 0
    
    @retry_with_backoff(max_attempts=max_attempts, initial_delay=0.0, backoff_factor=2.0)
    def failing_function():
        nonlocal call_count
        call_count += 1
        if call_count >= should_succeed_on_attempt:
            return "success"
        raise ValueError("Simulated failure")
    
    try:
        result = failing_function()
        # If it succeeded, verify it was called the expected number of times
        assert call_count == min(should_succeed_on_attempt, max_attempts)
        assert result == "success"
    except ValueError:
        # If it failed, verify it was called exactly max_attempts times
        assert call_count == max_attempts


# Feature: show-theme-cli, Property 16: Retry with Exponential Backoff
@pytest.mark.property
@settings(max_examples=50, deadline=None)
@given(
    initial_delay=st.floats(min_value=0.0, max_value=0.1),
    backoff_factor=st.floats(min_value=1.5, max_value=3.0)
)
def test_exponential_backoff_timing(initial_delay, backoff_factor):
    """
    Property: For any initial_delay and backoff_factor, the delays between retries
    should follow exponential backoff pattern: 0s, initial_delay*backoff^0, 
    initial_delay*backoff^1, etc.
    
    Validates: Requirements 9.1
    """
    max_attempts = 3
    call_times = []
    
    @retry_with_backoff(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor
    )
    def always_failing_function():
        call_times.append(time.time())
        raise ValueError("Always fails")
    
    try:
        always_failing_function()
    except ValueError:
        pass
    
    # Verify we got the expected number of attempts
    assert len(call_times) == max_attempts
    
    # Verify timing between attempts follows exponential backoff
    # Allow 20% tolerance for timing variations
    tolerance = 0.2
    
    for i in range(1, len(call_times)):
        actual_delay = call_times[i] - call_times[i-1]
        
        if i == 1 and initial_delay == 0.0:
            # First retry should be immediate if initial_delay is 0
            expected_delay = 0.0
        else:
            # Subsequent retries follow exponential pattern
            expected_delay = initial_delay * (backoff_factor ** (i - 1))
        
        # Allow for timing variations
        if expected_delay > 0:
            assert actual_delay >= expected_delay * (1 - tolerance)
            assert actual_delay <= expected_delay * (1 + tolerance) + 0.05  # +50ms overhead


# Feature: show-theme-cli, Property 16: Retry with Exponential Backoff
@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    exception_to_raise=st.sampled_from([
        ValueError,
        RuntimeError,
        ConnectionError,
        TimeoutError
    ])
)
def test_retry_only_on_specified_exceptions(exception_to_raise):
    """
    Property: For any exception type, the retry decorator should only retry
    if the exception is in the specified exceptions tuple.
    
    Validates: Requirements 9.1
    """
    call_count = 0
    
    # Configure to only retry on ValueError
    @retry_with_backoff(
        max_attempts=3,
        initial_delay=0.0,
        exceptions=(ValueError,)
    )
    def selective_retry_function():
        nonlocal call_count
        call_count += 1
        raise exception_to_raise("Test exception")
    
    with pytest.raises(exception_to_raise):
        selective_retry_function()
    
    # Should retry 3 times for ValueError, only once for others
    if exception_to_raise == ValueError:
        assert call_count == 3
    else:
        assert call_count == 1


# Feature: show-theme-cli, Property 16: Retry with Exponential Backoff
@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    success_on_attempt=st.integers(min_value=1, max_value=3)
)
def test_retry_returns_on_success(success_on_attempt):
    """
    Property: For any success_on_attempt value within max_attempts, the function
    should return the result immediately upon success without further retries.
    
    Validates: Requirements 9.1
    """
    call_count = 0
    max_attempts = 3
    
    @retry_with_backoff(max_attempts=max_attempts, initial_delay=0.0)
    def eventually_succeeds():
        nonlocal call_count
        call_count += 1
        if call_count == success_on_attempt:
            return f"success_on_{success_on_attempt}"
        raise ValueError("Not yet")
    
    result = eventually_succeeds()
    
    # Should have been called exactly success_on_attempt times
    assert call_count == success_on_attempt
    assert result == f"success_on_{success_on_attempt}"


# Feature: show-theme-cli, Property 16: Retry with Exponential Backoff
@pytest.mark.property
def test_retry_with_default_parameters():
    """
    Property: The retry decorator should work with default parameters
    (3 attempts, 0s initial delay, 2.0 backoff factor, all exceptions).
    
    Validates: Requirements 9.1
    """
    call_count = 0
    
    @retry_with_backoff()
    def default_retry_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Fail")
        return "success"
    
    result = default_retry_function()
    
    assert call_count == 3
    assert result == "success"


# Feature: show-theme-cli, Property 16: Retry with Exponential Backoff
@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    max_attempts=st.integers(min_value=1, max_value=5)
)
def test_retry_preserves_function_metadata(max_attempts):
    """
    Property: For any max_attempts value, the retry decorator should preserve
    the original function's name and docstring.
    
    Validates: Requirements 9.1
    """
    @retry_with_backoff(max_attempts=max_attempts)
    def test_function():
        """Test function docstring."""
        return "result"
    
    assert test_function.__name__ == "test_function"
    assert test_function.__doc__ == "Test function docstring."
