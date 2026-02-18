pub mod config;
pub mod utils;
pub mod scrapers;
pub mod ffmpeg;
pub mod retry;
pub mod rate_limiter;
pub mod orchestrator;

use std::path::Path;

/// Validate that the input path exists and is a directory
pub fn validate_input_path(path: &Path) -> Result<(), String> {
    if !path.exists() {
        return Err(format!(
            "Error: The path '{}' does not exist",
            path.display()
        ));
    }

    if !path.is_dir() {
        return Err(format!(
            "Error: The path '{}' is not a directory",
            path.display()
        ));
    }

    Ok(())
}
