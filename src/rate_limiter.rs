use rand::RngExt;
use std::collections::HashMap;
use std::time::Instant;
use tokio::time::{Duration, sleep};

use crate::config::Config;

/// Rate limiter with random jitter to prevent IP bans
pub struct RateLimiter {
    last_attempt: HashMap<String, Instant>,
    min_delay_ms: u64,
    max_delay_ms: u64,
}

impl RateLimiter {
    /// Create a new rate limiter with default delays from config
    pub fn new() -> Self {
        Self {
            last_attempt: HashMap::new(),
            min_delay_ms: Config::RATE_LIMIT_MIN_DELAY_MS,
            max_delay_ms: Config::RATE_LIMIT_MAX_DELAY_MS,
        }
    }

    /// Create a rate limiter with custom delay bounds
    pub fn with_delays(min_delay_ms: u64, max_delay_ms: u64) -> Self {
        Self {
            last_attempt: HashMap::new(),
            min_delay_ms,
            max_delay_ms,
        }
    }

    /// Wait if necessary before making a request to the given source
    pub async fn wait_if_needed(&mut self, source: &str) {
        let now = Instant::now();

        // Calculate required delay
        let delay_ms = if let Some(&last_time) = self.last_attempt.get(source) {
            let elapsed = now.duration_since(last_time);
            let min_delay = Duration::from_millis(self.min_delay_ms);

            if elapsed < min_delay {
                // Need to wait for remaining time plus jitter
                let remaining = min_delay.saturating_sub(elapsed);
                let jitter_ms =
                    rand::rng().random_range(0..=(self.max_delay_ms - self.min_delay_ms));
                remaining.as_millis() as u64 + jitter_ms
            } else {
                // Enough time has passed, just add jitter
                rand::rng().random_range(0..=(self.max_delay_ms - self.min_delay_ms))
            }
        } else {
            // First request to this source, use random delay between min and max
            rand::rng().random_range(self.min_delay_ms..=self.max_delay_ms)
        };

        // Wait for the calculated delay
        sleep(Duration::from_millis(delay_ms)).await;

        // Record this attempt
        self.last_attempt.insert(source.to_string(), Instant::now());
    }
}

impl Default for RateLimiter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_rate_limiter_enforces_delay() {
        let mut limiter = RateLimiter::with_delays(100, 200);

        let start = Instant::now();
        limiter.wait_if_needed("test_source").await;
        let elapsed = start.elapsed();

        // Should wait at least min_delay_ms
        assert!(elapsed.as_millis() >= 100);
    }

    #[tokio::test]
    async fn test_rate_limiter_different_sources() {
        let mut limiter = RateLimiter::with_delays(50, 100);

        // First source
        limiter.wait_if_needed("source1").await;

        // Second source should not be affected by first
        let start = Instant::now();
        limiter.wait_if_needed("source2").await;
        let elapsed = start.elapsed();

        // Should still enforce delay for new source
        assert!(elapsed.as_millis() >= 50);
    }

    #[test]
    fn test_rate_limiter_creation() {
        let limiter = RateLimiter::new();
        assert_eq!(limiter.min_delay_ms, Config::RATE_LIMIT_MIN_DELAY_MS);
        assert_eq!(limiter.max_delay_ms, Config::RATE_LIMIT_MAX_DELAY_MS);
    }

    #[test]
    fn test_rate_limiter_custom_delays() {
        let limiter = RateLimiter::with_delays(500, 1000);
        assert_eq!(limiter.min_delay_ms, 500);
        assert_eq!(limiter.max_delay_ms, 1000);
    }
}
