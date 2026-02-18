use clap::Parser;
use std::path::PathBuf;
use std::process;

mod config;
mod scrapers;
mod utils;

/// Show Theme CLI - Automate theme song downloads for TV shows and anime
#[derive(Parser, Debug)]
#[command(
    name = "show-theme-cli",
    version = env!("CARGO_PKG_VERSION"),
    about = "Automate theme song downloads for TV shows and anime",
    long_about = "Scans local directory structures, identifies shows by folder name, and downloads high-quality theme songs from multiple prioritized sources."
)]
pub struct CliArgs {
    /// Root directory containing show folders
    #[arg(value_name = "INPUT_DIR")]
    pub input_dir: Option<PathBuf>,

    /// Overwrite existing theme files
    #[arg(short, long)]
    pub force: bool,

    /// Enable debug logging
    #[arg(short, long)]
    pub verbose: bool,

    /// Simulate operations without downloading
    #[arg(long)]
    pub dry_run: bool,

    /// Network timeout in seconds
    #[arg(short, long, default_value_t = 30)]
    pub timeout: u64,
}

/// Validate that the input path exists and is a directory
fn validate_input_path(path: &PathBuf) -> Result<(), String> {
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

#[tokio::main]
async fn main() {
    let args = CliArgs::parse();

    // Handle missing input directory
    let input_dir = match args.input_dir {
        Some(dir) => dir,
        None => {
            eprintln!("Error: INPUT_DIR is required");
            eprintln!();
            eprintln!("Usage: show-theme-cli <INPUT_DIR> [OPTIONS]");
            eprintln!();
            eprintln!("For more information, try '--help'");
            process::exit(1);
        }
    };

    // Validate input path
    if let Err(err) = validate_input_path(&input_dir) {
        eprintln!("{}", err);
        process::exit(1);
    }

    // TODO: Initialize logging based on verbose flag
    // TODO: Initialize orchestrator and scrapers
    // TODO: Process directory and display results

    println!("Show Theme CLI initialized successfully!");
    println!("Input directory: {}", input_dir.display());
    println!("Force mode: {}", args.force);
    println!("Verbose mode: {}", args.verbose);
    println!("Dry run: {}", args.dry_run);
    println!("Timeout: {} seconds", args.timeout);
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::Path;

    #[test]
    fn test_validate_input_path_nonexistent() {
        let path = PathBuf::from("/nonexistent/path/that/does/not/exist");
        let result = validate_input_path(&path);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("does not exist"));
    }

    #[test]
    fn test_validate_input_path_file_not_directory() {
        // Create a temporary file
        let temp_file = std::env::temp_dir().join("test_file.txt");
        fs::write(&temp_file, "test").unwrap();

        let result = validate_input_path(&temp_file);
        
        // Clean up
        fs::remove_file(&temp_file).ok();

        assert!(result.is_err());
        assert!(result.unwrap_err().contains("is not a directory"));
    }

    #[test]
    fn test_validate_input_path_valid_directory() {
        let temp_dir = std::env::temp_dir();
        let result = validate_input_path(&temp_dir);
        assert!(result.is_ok());
    }
}
