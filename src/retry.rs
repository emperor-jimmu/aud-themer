use std::fmt::Display;
use tokio::time::{Duration, sleep};

/// Retry an async operation with exponential backoff
///
/// # Arguments
/// * `max_attempts` - Maximum number of attempts (including the first try)
/// * `backoff_factor` - Multiplier for delay between retries (e.g., 2.0 for doubling)
/// * `operation` - Async function to retry
///
/// # Returns
/// * `Ok(T)` if the operation succeeds within max_attempts
/// * `Err(E)` if all attempts fail (returns the last error)
pub async fn retry_with_backoff<F, Fut, T, E>(
    max_attempts: u32,
    backoff_factor: f64,
    mut operation: F,
) -> Result<T, E>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<T, E>>,
    E: Display,
{
    let mut attempt = 0;
    let mut delay_ms = 1000u64; // Start with 1 second delay

    loop {
        attempt += 1;

        match operation().await {
            Ok(result) => {
                if attempt > 1 {
                    tracing::info!("[Retry] Operation succeeded on attempt {}", attempt);
                }
                return Ok(result);
            }
            Err(e) => {
                if attempt >= max_attempts {
                    tracing::error!(
                        "[Retry] All {} attempts failed. Last error: {}",
                        max_attempts,
                        e
                    );
                    return Err(e);
                }

                tracing::warn!(
                    "[Retry] Attempt {}/{} failed: {}. Retrying in {}ms...",
                    attempt,
                    max_attempts,
                    e,
                    delay_ms
                );

                // Wait before retrying
                sleep(Duration::from_millis(delay_ms)).await;

                // Increase delay for next attempt
                delay_ms = (delay_ms as f64 * backoff_factor) as u64;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::sync::atomic::{AtomicU32, Ordering};

    #[tokio::test]
    async fn test_retry_succeeds_on_first_attempt() {
        let result = retry_with_backoff(3, 2.0, || async { Ok::<i32, String>(42) }).await;
        assert_eq!(result, Ok(42));
    }

    #[tokio::test]
    async fn test_retry_succeeds_after_failures() {
        let counter = Arc::new(AtomicU32::new(0));
        let counter_clone = counter.clone();

        let result = retry_with_backoff(3, 2.0, move || {
            let c = counter_clone.clone();
            async move {
                let count = c.fetch_add(1, Ordering::SeqCst);
                if count < 2 {
                    Err(format!("Attempt {}", count + 1))
                } else {
                    Ok(42)
                }
            }
        })
        .await;

        assert_eq!(result, Ok(42));
        assert_eq!(counter.load(Ordering::SeqCst), 3);
    }

    #[tokio::test]
    async fn test_retry_fails_after_max_attempts() {
        let counter = Arc::new(AtomicU32::new(0));
        let counter_clone = counter.clone();

        let result = retry_with_backoff(3, 2.0, move || {
            let c = counter_clone.clone();
            async move {
                c.fetch_add(1, Ordering::SeqCst);
                Err::<i32, String>("Always fails".to_string())
            }
        })
        .await;

        assert!(result.is_err());
        assert_eq!(counter.load(Ordering::SeqCst), 3);
    }
}
