// Feature: rust-rewrite, Property 8: Best match selection by string similarity
// Feature: rust-rewrite, Property 9: Theme type priority selection

use proptest::prelude::*;
use show_theme_cli::scrapers::anime_themes::{AnimeThemesScraper, Anime, AnimeTheme};

// Property 8: Best match selection by string similarity
proptest! {
    #[test]
    fn prop_best_match_has_highest_similarity(
        anime_names in prop::collection::vec(
            "[a-zA-Z0-9 ]{3,20}",
            1..10
        ),
        query in "[a-zA-Z0-9 ]{3,20}"
    ) {
        let anime_list: Vec<Anime> = anime_names
            .iter()
            .map(|name| Anime {
                name: name.clone(),
                anime_themes: vec![],
            })
            .collect();

        if let Some(best_match) = AnimeThemesScraper::select_best_match(&anime_list, &query) {
            let best_score = strsim::jaro_winkler(
                &best_match.name.to_lowercase(),
                &query.to_lowercase()
            );

            // Verify that the selected match has the highest (or tied for highest) similarity score
            for anime in &anime_list {
                let score = strsim::jaro_winkler(
                    &anime.name.to_lowercase(),
                    &query.to_lowercase()
                );
                
                // The best match should have a score >= all others
                prop_assert!(
                    best_score >= score,
                    "Best match score {} should be >= score {} for anime '{}'",
                    best_score,
                    score,
                    anime.name
                );
            }
        }
    }

    #[test]
    fn prop_best_match_returns_some_for_nonempty_list(
        anime_names in prop::collection::vec(
            "[a-zA-Z0-9 ]{3,20}",
            1..10
        ),
        query in "[a-zA-Z0-9 ]{3,20}"
    ) {
        let anime_list: Vec<Anime> = anime_names
            .iter()
            .map(|name| Anime {
                name: name.clone(),
                anime_themes: vec![],
            })
            .collect();

        let result = AnimeThemesScraper::select_best_match(&anime_list, &query);
        prop_assert!(result.is_some(), "Should return Some for non-empty list");
    }

    #[test]
    fn prop_best_match_returns_none_for_empty_list(
        query in "[a-zA-Z0-9 ]{3,20}"
    ) {
        let anime_list: Vec<Anime> = vec![];
        let result = AnimeThemesScraper::select_best_match(&anime_list, &query);
        prop_assert!(result.is_none(), "Should return None for empty list");
    }
}

// Property 9: Theme type priority selection
proptest! {
    #[test]
    fn prop_theme_priority_prefers_op1(
        other_themes in prop::collection::vec(
            prop::sample::select(vec!["OP", "ED", "ED1", "OP2"]),
            0..5
        )
    ) {
        let mut themes: Vec<AnimeTheme> = other_themes
            .iter()
            .map(|theme_type| AnimeTheme {
                theme_type: theme_type.to_string(),
                slug: format!("{}", theme_type),
                entries: vec![],
            })
            .collect();

        // Insert OP1 at a random position
        let op1_position = if themes.is_empty() { 0 } else { themes.len() / 2 };
        themes.insert(op1_position, AnimeTheme {
            theme_type: "OP".to_string(),
            slug: "OP1".to_string(),
            entries: vec![],
        });

        let selected = AnimeThemesScraper::select_best_theme(&themes);
        prop_assert!(selected.is_some(), "Should select a theme");
        
        if let Some(theme) = selected {
            prop_assert_eq!(
                theme.slug.to_uppercase(),
                "OP1",
                "Should select OP1 when present"
            );
        }
    }

    #[test]
    fn prop_theme_priority_prefers_op_when_no_op1(
        other_themes in prop::collection::vec(
            prop::sample::select(vec!["ED", "ED1", "ED2", "IN"]),
            0..5
        )
    ) {
        let mut themes: Vec<AnimeTheme> = other_themes
            .iter()
            .enumerate()
            .map(|(i, theme_type)| AnimeTheme {
                theme_type: theme_type.to_string(),
                slug: format!("{}{}", theme_type, i + 1),
                entries: vec![],
            })
            .collect();

        // Insert a generic OP (not OP1) at a random position
        let op_position = if themes.is_empty() { 0 } else { themes.len() / 2 };
        themes.insert(op_position, AnimeTheme {
            theme_type: "OP".to_string(),
            slug: "OP2".to_string(),
            entries: vec![],
        });

        let selected = AnimeThemesScraper::select_best_theme(&themes);
        prop_assert!(selected.is_some(), "Should select a theme");
        
        if let Some(theme) = selected {
            prop_assert_eq!(
                theme.theme_type.to_uppercase(),
                "OP",
                "Should select OP type when no OP1 present"
            );
        }
    }

    #[test]
    fn prop_theme_priority_returns_first_when_no_op(
        theme_types in prop::collection::vec(
            prop::sample::select(vec!["ED", "ED1", "ED2", "IN"]),
            1..5
        )
    ) {
        let themes: Vec<AnimeTheme> = theme_types
            .iter()
            .enumerate()
            .map(|(i, theme_type)| AnimeTheme {
                theme_type: theme_type.to_string(),
                slug: format!("{}{}", theme_type, i + 1),
                entries: vec![],
            })
            .collect();

        let selected = AnimeThemesScraper::select_best_theme(&themes);
        prop_assert!(selected.is_some(), "Should select a theme");
        
        if let Some(theme) = selected {
            prop_assert_eq!(
                &theme.slug,
                &themes[0].slug,
                "Should select first theme when no OP present"
            );
        }
    }

    #[test]
    fn prop_theme_priority_returns_none_for_empty(
        _dummy in 0..1u8
    ) {
        let themes: Vec<AnimeTheme> = vec![];
        let result = AnimeThemesScraper::select_best_theme(&themes);
        prop_assert!(result.is_none(), "Should return None for empty theme list");
    }
}
