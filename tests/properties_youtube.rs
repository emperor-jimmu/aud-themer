// Feature: rust-rewrite, Property 10: YouTube search query generation
// Feature: rust-rewrite, Property 11: YouTube duration filtering

use proptest::prelude::*;
use show_theme_cli::scrapers::youtube::YouTubeScraper;
use show_theme_cli::config::Config;

// Property 10: YouTube search query generation
proptest! {
    #[test]
    fn prop_search_queries_contain_show_name(
        show_name in "[a-zA-Z0-9 ]{3,50}"
    ) {
        let queries = YouTubeScraper::generate_search_queries(&show_name);
        
        // All queries should contain the show name as a substring
        for query in &queries {
            prop_assert!(
                query.contains(&show_name),
                "Query '{}' should contain show name '{}'",
                query,
                show_name
            );
        }
    }

    #[test]
    fn prop_search_queries_include_theme_song_variation(
        show_name in "[a-zA-Z0-9 ]{3,50}"
    ) {
        let queries = YouTubeScraper::generate_search_queries(&show_name);
        
        // Should include at least the "theme song" variation
        let has_theme_song = queries.iter().any(|q| q.contains("theme song"));
        prop_assert!(
            has_theme_song,
            "Queries should include 'theme song' variation"
        );
    }

    #[test]
    fn prop_search_queries_nonempty_for_nonempty_input(
        show_name in "[a-zA-Z0-9 ]{1,50}"
    ) {
        let queries = YouTubeScraper::generate_search_queries(&show_name);
        
        // Should return at least one query
        prop_assert!(
            !queries.is_empty(),
            "Should generate at least one query for non-empty show name"
        );
    }

    #[test]
    fn prop_search_queries_all_nonempty(
        show_name in "[a-zA-Z0-9 ]{3,50}"
    ) {
        let queries = YouTubeScraper::generate_search_queries(&show_name);
        
        // All queries should be non-empty
        for query in &queries {
            prop_assert!(
                !query.is_empty(),
                "All generated queries should be non-empty"
            );
        }
    }
}

// Property 11: YouTube duration filtering
proptest! {
    #[test]
    fn prop_duration_accepts_short_videos(
        duration in 0.0..=600.0f64
    ) {
        let result = YouTubeScraper::is_duration_acceptable(duration);
        prop_assert!(
            result,
            "Duration {} seconds (≤ 600) should be acceptable",
            duration
        );
    }

    #[test]
    fn prop_duration_rejects_long_videos(
        duration in 600.1..=3600.0f64
    ) {
        let result = YouTubeScraper::is_duration_acceptable(duration);
        prop_assert!(
            !result,
            "Duration {} seconds (> 600) should be rejected",
            duration
        );
    }

    #[test]
    fn prop_duration_boundary_at_max(
        _dummy in 0..1u8
    ) {
        // Test exact boundary
        let max_duration = Config::MAX_VIDEO_DURATION_SEC as f64;
        
        // Exactly at max should be acceptable
        prop_assert!(
            YouTubeScraper::is_duration_acceptable(max_duration),
            "Duration exactly at {} seconds should be acceptable",
            max_duration
        );
        
        // Just over max should be rejected
        prop_assert!(
            !YouTubeScraper::is_duration_acceptable(max_duration + 0.1),
            "Duration at {} seconds should be rejected",
            max_duration + 0.1
        );
    }

    #[test]
    fn prop_duration_accepts_zero(
        _dummy in 0..1u8
    ) {
        let result = YouTubeScraper::is_duration_acceptable(0.0);
        prop_assert!(
            result,
            "Duration of 0 seconds should be acceptable"
        );
    }
}
