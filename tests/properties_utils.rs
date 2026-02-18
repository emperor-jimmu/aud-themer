// Feature: rust-rewrite, Property tests for utils module

use proptest::prelude::*;
use show_theme_cli::utils::*;
use std::fs::File;
use std::io::Write;
use tempfile::TempDir;

// Feature: rust-rewrite, Property 3: Year stripping preserves base name
// For any string of the form "{name} ({four_digits})", stripping the year portion
// SHALL produce "{name}" (trimmed). For any string without a year pattern,
// stripping SHALL return the original string unchanged.
proptest! {
    #[test]
    fn prop_year_stripping_preserves_base_name(
        base_name in "[a-zA-Z0-9 ]{1,50}",
        year in 1900u32..2100u32
    ) {
        let with_year = format!("{} ({})", base_name, year);
        let stripped = strip_year_from_show_name(&with_year);
        prop_assert_eq!(stripped, base_name.trim());
    }

    #[test]
    fn prop_year_stripping_unchanged_without_pattern(
        name in "[a-zA-Z0-9 ]{1,50}"
    ) {
        let stripped = strip_year_from_show_name(&name);
        prop_assert_eq!(stripped, name.trim());
    }
}

// Feature: rust-rewrite, Property 14: File size validation
// For any file size value, validate_file_size SHALL return true if and only if
// the size exceeds 500,000 bytes.
proptest! {
    #[test]
    fn prop_file_size_validation(size in 0u64..2_000_000u64) {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("test.bin");

        // Create file with exact size
        let mut file = File::create(&file_path).unwrap();
        file.write_all(&vec![0u8; size as usize]).unwrap();
        drop(file);

        let result = validate_file_size(&file_path, 500_000);

        if size >= 500_000 {
            prop_assert!(result, "File with size {} should pass validation", size);
        } else {
            prop_assert!(!result, "File with size {} should fail validation", size);
        }
    }
}

// Feature: rust-rewrite, Property 17: Input sanitization removes dangerous characters
// For any string containing shell metacharacters or control characters or path
// traversal sequences, the sanitization function SHALL produce a string that
// contains none of those characters or sequences.
proptest! {
    #[test]
    fn prop_input_sanitization_removes_dangerous_chars(
        safe_part in "[a-zA-Z0-9 _-]{1,50}",
        dangerous_chars in prop::collection::vec(
            prop::sample::select(vec![';', '|', '&', '`', '<', '>', '$']),
            0..5
        )
    ) {
        let mut input = safe_part.clone();
        for ch in dangerous_chars {
            input.push(ch);
        }

        if input.len() <= 200 {
            let result = sanitize_for_subprocess(&input, 200);

            if let Ok(sanitized) = result {
                // Verify no dangerous characters remain
                prop_assert!(!sanitized.contains(';'));
                prop_assert!(!sanitized.contains('|'));
                prop_assert!(!sanitized.contains('&'));
                prop_assert!(!sanitized.contains('`'));
                prop_assert!(!sanitized.contains('<'));
                prop_assert!(!sanitized.contains('>'));
                prop_assert!(!sanitized.contains('$'));
            }
        }
    }

    #[test]
    fn prop_input_sanitization_rejects_path_traversal(
        prefix in "[a-zA-Z0-9]{1,20}",
        suffix in "[a-zA-Z0-9]{1,20}"
    ) {
        let input = format!("{}..{}", prefix, suffix);
        let result = sanitize_for_subprocess(&input, 200);
        prop_assert!(result.is_err(), "Path traversal should be rejected");
    }

    #[test]
    fn prop_input_sanitization_rejects_long_input(
        length in 201usize..500usize
    ) {
        let input = "a".repeat(length);
        let result = sanitize_for_subprocess(&input, 200);
        prop_assert!(result.is_err(), "Input exceeding max length should be rejected");
    }
}

// Feature: rust-rewrite, Property 18: Show name length validation
// For any string longer than 200 characters, validate_show_name SHALL return false.
// For any non-empty string of 200 characters or fewer (without excessive special
// characters), it SHALL return true.
proptest! {
    #[test]
    fn prop_show_name_length_validation_rejects_long(
        length in 201usize..500usize
    ) {
        let name = "a".repeat(length);
        prop_assert!(!validate_show_name(&name), "Names longer than 200 chars should be rejected");
    }

    #[test]
    fn prop_show_name_length_validation_accepts_valid(
        name in "[a-zA-Z0-9 ]{1,200}"
    ) {
        prop_assert!(validate_show_name(&name), "Valid names should be accepted");
    }

    #[test]
    fn prop_show_name_rejects_excessive_special_chars(
        special_count in 26usize..50usize
    ) {
        let mut name = "a".repeat(50 - special_count);
        name.push_str(&"!".repeat(special_count));

        // More than 50% special characters should be rejected
        prop_assert!(!validate_show_name(&name), "Names with >50% special chars should be rejected");
    }
}

#[test]
fn prop_show_name_rejects_empty() {
    assert!(!validate_show_name(""), "Empty names should be rejected");
}
