use clap::Parser;
use colored::Colorize;
use show_theme_cli::orchestrator::{Orchestrator, OrchestratorConfig};
use show_theme_cli::scrapers::anime_themes::AnimeThemesScraper;
use show_theme_cli::scrapers::themes_moe::ThemesMoeScraper;
use show_theme_cli::scrapers::tv_tunes::TvTunesScraper;
use show_theme_cli::scrapers::youtube::YouTubeScraper;
use show_theme_cli::scrapers::ThemeScraper;
use show_theme_cli::validate_input_path;
use std::path::PathBuf;
use std::process::{self, Command};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Instant;
use tracing::{error, info};
use tracing_subscriber::EnvFilter;

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

/// Check if a command is available in PATH
fn check_dependency(command: &str) -> bool {
    Command::new("which")
        .arg(command)
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

/// Validate all required external dependencies
fn validate_dependencies() -> Result<(), String> {
    let mut missing = Vec::new();

    if !check_dependency("ffmpeg") {
        missing.push("ffmpeg");
    }

    if !check_dependency("yt-dlp") {
        missing.push("yt-dlp");
    }

    // Check for chromium (used by chromiumoxide)
    // Note: chromiumoxide can download chromium automatically, so we just warn
    if !check_dependency("chromium") && !check_dependency("chromium-browser") && !check_dependency("google-chrome") {
        eprintln!("{} Chromium not found in PATH. Browser automation will attempt to download it automatically.", "Warning:".yellow());
    }

    if !missing.is_empty() {
        return Err(format!(
            "Missing required dependencies: {}\nPlease install them before running this tool.",
            missing.join(", ")
        ));
    }

    Ok(())
}

/// Initialize tracing/logging based on verbosity
fn init_logging(verbose: bool) {
    let log_level = if verbose { "debug" } else { "info" };
    
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(log_level));

    // Create log file with timestamp
    let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S");
    let log_file = format!("show-theme-cli-{}.log", timestamp);

    // Set up file logging
    let file_appender = tracing_appender::rolling::never(".", &log_file);
    
    // Set up console logging (only for verbose mode)
    let subscriber = tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_writer(file_appender)
        .with_ansi(false)
        .finish();

    tracing::subscriber::set_global_default(subscriber)
        .expect("Failed to set tracing subscriber");

    if verbose {
        println!("{} Logging to {}", "ℹ".blue(), log_file);
    }
}

/// Initialize all scrapers in priority order
fn init_scrapers() -> Vec<Box<dyn ThemeScraper>> {
    let scrapers: Vec<Box<dyn ThemeScraper>> = vec![
        Box::new(TvTunesScraper::new()),
        Box::new(AnimeThemesScraper::new()),
        Box::new(ThemesMoeScraper::new()),
        Box::new(YouTubeScraper::new()),
    ];
    scrapers
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

    // Validate dependencies
    if let Err(err) = validate_dependencies() {
        eprintln!("{}", err.red());
        process::exit(1);
    }

    // Initialize logging
    init_logging(args.verbose);
    info!("Show Theme CLI v{} starting", env!("CARGO_PKG_VERSION"));
    info!("Input directory: {}", input_dir.display());

    // Set up Ctrl+C handler
    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    
    ctrlc::set_handler(move || {
        eprintln!("\n{} Interrupted by user. Exiting gracefully...", "⚠".yellow());
        r.store(false, Ordering::SeqCst);
        process::exit(130); // Standard exit code for SIGINT
    })
    .expect("Error setting Ctrl-C handler");

    // Display banner
    println!("\n{}", "═".repeat(60));
    println!("{} {}", "Show Theme CLI".bold().cyan(), format!("v{}", env!("CARGO_PKG_VERSION")).dimmed());
    println!("{}", "═".repeat(60));

    // Create orchestrator config
    let config = OrchestratorConfig {
        force: args.force,
        dry_run: args.dry_run,
        verbose: args.verbose,
        timeout: args.timeout,
    };

    // Initialize scrapers
    info!("Initializing scrapers");
    let scrapers = init_scrapers();

    // Create orchestrator
    let mut orchestrator = Orchestrator::new(config, scrapers);

    // Start timer
    let start_time = Instant::now();

    // Process directory
    match orchestrator.process_directory(&input_dir).await {
        Ok(_) => {
            let elapsed = start_time.elapsed();
            let results = orchestrator.results();
            
            info!(
                "Processing complete: {} success, {} skipped, {} failed",
                results.success, results.skipped, results.failed
            );

            // Display elapsed time
            println!(
                "\n{} Completed in {:.2}s",
                "✓".green().bold(),
                elapsed.as_secs_f64()
            );

            // Exit with appropriate code
            if results.failed > 0 && results.success == 0 {
                process::exit(1);
            }
        }
        Err(err) => {
            error!("Critical error: {}", err);
            eprintln!("\n{} {}", "Error:".red().bold(), err);
            process::exit(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

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