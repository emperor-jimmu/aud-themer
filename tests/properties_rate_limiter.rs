// Feature: rust-rewrite, Property tests for rate limiter module

use show_theme_cli::rate_limiter::RateLimiter;
use std::time::Instant;

// Feature: rust-rewrite, Property 15: Rate limiter delay bounds
// For any sequence of two consecutive calls to the rate limiter for the same source,
// the elapsed time between the calls SHALL be at least 1.0 seconds.

#[tokio::test]
async fn test_rate_limiter_enforces_minimum_delay() {
    let mut limiter = RateLimiter::with_delays(1000, 1500);

    let start = Instant::now();
    limiter.wait_if_needed("test_source").await;
    let first_call_elapsed = start.elapsed();

    // First call should take at least 1000ms (min delay)
    assert!(
        first_call_elapsed.as_millis() >= 1000,
        "First call should enforce minimum delay of 1000ms, got {}ms",
        first_call_elapsed.as_millis()
    );

    // Second call to same source
    let second_start = Instant::now();
    limiter.wait_if_needed("test_source").await;
    let second_call_elapsed = second_start.elapsed();

    // Second call should also take at least 1000ms
    assert!(
        second_call_elapsed.as_millis() >= 1000,
        "Second call should enforce minimum delay of 1000ms, got {}ms",
        second_call_elapsed.as_millis()
    );
}

#[tokio::test]
async fn test_rate_limiter_delay_bounds_multiple_sources() {
    let mut limiter = RateLimiter::with_delays(500, 800);

    // Test multiple sources
    for source in &["source1", "source2", "source3"] {
        let start = Instant::now();
        limiter.wait_if_needed(source).await;
        let elapsed = start.elapsed();

        assert!(
            elapsed.as_millis() >= 500,
            "Source {} should enforce minimum delay of 500ms, got {}ms",
            source,
            elapsed.as_millis()
        );

        assert!(
            elapsed.as_millis() <= 1500,
            "Source {} delay should be reasonable (< 1500ms), got {}ms",
            source,
            elapsed.as_millis()
        );
    }
}

#[tokio::test]
async fn test_rate_limiter_default_config() {
    let mut limiter = RateLimiter::new();

    let start = Instant::now();
    limiter.wait_if_needed("test_source").await;
    let elapsed = start.elapsed();

    // Should enforce at least 1000ms (Config::RATE_LIMIT_MIN_DELAY_MS)
    assert!(
        elapsed.as_millis() >= 1000,
        "Default rate limiter should enforce minimum delay of 1000ms, got {}ms",
        elapsed.as_millis()
    );
}
