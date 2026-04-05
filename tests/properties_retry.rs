// Feature: rust-rewrite, Property tests for retry module

use audio_theme_downloader::retry::retry_with_backoff;
use proptest::prelude::*;
use std::sync::Arc;
use std::sync::atomic::{AtomicU32, Ordering};

// Feature: rust-rewrite, Property 16: Retry with exponential backoff
// For any operation that fails K times (K < 3) then succeeds, the retry mechanism
// SHALL make exactly K+1 total attempts. If the operation fails all 3 times,
// the mechanism SHALL return a failure result after exactly 3 attempts.

proptest! {
    #![proptest_config(ProptestConfig::with_cases(20))]

    #[test]
    fn prop_retry_succeeds_after_k_failures(
        k in 0u32..3u32
    ) {
        let rt = tokio::runtime::Runtime::new().unwrap();
        let counter = Arc::new(AtomicU32::new(0));
        let counter_clone = counter.clone();

        let result = rt.block_on(retry_with_backoff(3, 2.0, move || {
            let c = counter_clone.clone();
            async move {
                let count = c.fetch_add(1, Ordering::SeqCst);
                if count < k {
                    Err(format!("Attempt {}", count + 1))
                } else {
                    Ok(42)
                }
            }
        }));

        prop_assert_eq!(result, Ok(42));
        prop_assert_eq!(counter.load(Ordering::SeqCst), k + 1);
    }

    #[test]
    fn prop_retry_fails_after_max_attempts(
        max_attempts in 1u32..5u32
    ) {
        let rt = tokio::runtime::Runtime::new().unwrap();
        let counter = Arc::new(AtomicU32::new(0));
        let counter_clone = counter.clone();

        let result = rt.block_on(retry_with_backoff(max_attempts, 2.0, move || {
            let c = counter_clone.clone();
            async move {
                c.fetch_add(1, Ordering::SeqCst);
                Err::<i32, String>("Always fails".to_string())
            }
        }));

        prop_assert!(result.is_err());
        prop_assert_eq!(counter.load(Ordering::SeqCst), max_attempts);
    }

    #[test]
    fn prop_retry_succeeds_immediately_on_first_success(
        _dummy in 0u32..10u32
    ) {
        let rt = tokio::runtime::Runtime::new().unwrap();
        let counter = Arc::new(AtomicU32::new(0));
        let counter_clone = counter.clone();

        let result = rt.block_on(retry_with_backoff(3, 2.0, move || {
            let c = counter_clone.clone();
            async move {
                c.fetch_add(1, Ordering::SeqCst);
                Ok::<i32, String>(42)
            }
        }));

        prop_assert_eq!(result, Ok(42));
        prop_assert_eq!(counter.load(Ordering::SeqCst), 1);
    }
}

// Additional test for the specific requirement: exactly 3 attempts when all fail
#[tokio::test]
async fn test_retry_exactly_three_attempts_on_all_failures() {
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

// Test for K=0 (succeeds on first try)
#[tokio::test]
async fn test_retry_k_equals_zero() {
    let counter = Arc::new(AtomicU32::new(0));
    let counter_clone = counter.clone();

    let result = retry_with_backoff(3, 2.0, move || {
        let c = counter_clone.clone();
        async move {
            c.fetch_add(1, Ordering::SeqCst);
            Ok::<i32, String>(42)
        }
    })
    .await;

    assert_eq!(result, Ok(42));
    assert_eq!(counter.load(Ordering::SeqCst), 1); // K=0, so K+1=1
}

// Test for K=1 (fails once, succeeds on second try)
#[tokio::test]
async fn test_retry_k_equals_one() {
    let counter = Arc::new(AtomicU32::new(0));
    let counter_clone = counter.clone();

    let result = retry_with_backoff(3, 2.0, move || {
        let c = counter_clone.clone();
        async move {
            let count = c.fetch_add(1, Ordering::SeqCst);
            if count < 1 {
                Err("Attempt 1".to_string())
            } else {
                Ok(42)
            }
        }
    })
    .await;

    assert_eq!(result, Ok(42));
    assert_eq!(counter.load(Ordering::SeqCst), 2); // K=1, so K+1=2
}

// Test for K=2 (fails twice, succeeds on third try)
#[tokio::test]
async fn test_retry_k_equals_two() {
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
    assert_eq!(counter.load(Ordering::SeqCst), 3); // K=2, so K+1=3
}
