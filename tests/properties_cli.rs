// Feature: rust-rewrite, Property 1: Invalid path rejection
//
// For any path string that does not correspond to an existing directory on the filesystem,
// the CLI path validation SHALL return an error.
//
// Validates: Requirements 1.8

use proptest::prelude::*;
use show_theme_cli::validate_input_path;
use std::path::PathBuf;

proptest! {
    #![proptest_config(ProptestConfig::with_cases(100))]

    /// Property 1: Invalid path rejection
    ///
    /// For any path string that does not correspond to an existing directory,
    /// validate_input_path should return an error.
    #[test]
    fn property_invalid_path_rejection(
        // Generate random path components that are unlikely to exist
        path_parts in prop::collection::vec("[a-z0-9]{8,16}", 2..5)
    ) {
        // Construct a path that is extremely unlikely to exist
        let mut path = PathBuf::from("/nonexistent_root_12345");
        for part in path_parts {
            path.push(part);
        }

        // The path should not exist (with overwhelming probability)
        if !path.exists() {
            // Validation should fail
            let result = validate_input_path(&path);
            prop_assert!(result.is_err(), "Expected error for non-existent path: {:?}", path);
            
            // Error message should mention the path doesn't exist
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("does not exist"),
                "Error message should mention path doesn't exist, got: {}",
                err_msg
            );
        }
    }

    /// Property 1b: File path rejection
    ///
    /// For any path that points to a file (not a directory),
    /// validate_input_path should return an error.
    #[test]
    fn property_file_path_rejection(
        filename in "[a-z0-9_]{5,15}\\.txt"
    ) {
        use std::fs;
        use std::io::Write;

        // Create a temporary file
        let temp_dir = std::env::temp_dir();
        let file_path = temp_dir.join(filename);
        
        // Write some content to ensure it's a file
        if let Ok(mut file) = fs::File::create(&file_path) {
            let _ = file.write_all(b"test content");
            drop(file);

            // Validation should fail because it's a file, not a directory
            let result = validate_input_path(&file_path);
            
            // Clean up
            let _ = fs::remove_file(&file_path);

            prop_assert!(result.is_err(), "Expected error for file path: {:?}", file_path);
            
            // Error message should mention it's not a directory
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("is not a directory"),
                "Error message should mention it's not a directory, got: {}",
                err_msg
            );
        }
    }

    /// Property 1c: Valid directory acceptance
    ///
    /// For the temp directory (which always exists and is a directory),
    /// validate_input_path should succeed.
    #[test]
    fn property_valid_directory_acceptance(_dummy in 0..100u32) {
        // Use the system temp directory which should always exist
        let temp_dir = std::env::temp_dir();
        
        // Validation should succeed
        let result = validate_input_path(&temp_dir);
        prop_assert!(result.is_ok(), "Expected success for valid directory: {:?}", temp_dir);
    }
}
