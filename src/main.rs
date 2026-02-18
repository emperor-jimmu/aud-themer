use clap::Parser;
use colored::Colorize;
use show_theme_cli::browser::SharedBrowser;
use show_theme_cli::orchestrator::{Orchestrator, OrchestratorConfig};
use show_theme_cli::scrapers::ThemeScraper;
use show_theme_cli::scrapers::anime_themes::AnimeThemesScraper;
use show_theme_cli::scrapers::themes_moe::ThemesMoeScraper;
use show_theme_cli::scrapers::tv_tunes::TvTunesScraper;
use show_theme_cli::scrapers::youtube::YouTubeScraper;
use show_theme_cli::validate_input_path;
use std::path::PathBuf;
use std::process::{self, Command};
use std::time::Instant;
use tracing::{error, info};
use tracing_subscriber::EnvFilter;

/// Content mode for source selection
#[derive(Debug, Clone, Copy, PartialEq, Eq, clap::ValueEnum, Default)]
pub enum ContentMode {
    /// TV shows only (TelevisionTunes + YouTube)
    Tv,
    /// Anime only (AnimeThemes + Themes.moe + YouTube)
    Anime,
    /// Both TV and anime (all sources)
    #[default]
    Both,
}

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

    /// Content type - tv, anime, or both
    #[arg(short, long, value_enum, default_value_t = ContentMode::Both)]
    pub mode: ContentMode,

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
    if !check_dependency("chromium")
        && !check_dependency("chromium-browser")
        && !check_dependency("google-chrome")
    {
        eprintln!(
            "{} Chromium not found in PATH. Browser automation will attempt to download it automatically.",
            "Warning:".yellow()
        );
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

    // Filter out noisy chromiumoxide errors that don't affect functionality
    // Set chromiumoxide modules to 'off' to completely suppress their logs
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| {
        EnvFilter::new(log_level)
            .add_directive("chromiumoxide::conn=off".parse().unwrap())
            .add_directive("chromiumoxide::handler=off".parse().unwrap())
    });

    // Only create log files in verbose mode to avoid littering the directory
    if verbose {
        // Create log file with timestamp
        let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S");
        let log_file = format!("{}.log", timestamp);

        // Set up file logging
        let file_appender = tracing_appender::rolling::never(".", &log_file);

        let subscriber = tracing_subscriber::fmt()
            .with_env_filter(filter)
            .with_writer(file_appender)
            .with_ansi(false)
            .finish();

        tracing::subscriber::set_global_default(subscriber)
            .expect("Failed to set tracing subscriber");

        println!("{} Logging to {}", "ℹ".blue(), log_file);
    } else {
        // Non-verbose mode: log to stderr only
        let subscriber = tracing_subscriber::fmt()
            .with_env_filter(filter)
            .with_writer(std::io::stderr)
            .with_ansi(false)
            .finish();

        tracing::subscriber::set_global_default(subscriber)
            .expect("Failed to set tracing subscriber");
    }
}

/// Initialize scrapers based on content mode
fn init_scrapers(mode: ContentMode) -> Vec<Box<dyn ThemeScraper>> {
    let shared_browser = SharedBrowser::new();

    match mode {
        ContentMode::Tv => {
            // TV mode: TelevisionTunes + YouTube
            vec![
                Box::new(TvTunesScraper::new(shared_browser)),
                Box::new(YouTubeScraper::new()),
            ]
        }
        ContentMode::Anime => {
            // Anime mode: AnimeThemes + Themes.moe + YouTube
            vec![
                Box::new(AnimeThemesScraper::new()),
                Box::new(ThemesMoeScraper::new(shared_browser)),
                Box::new(YouTubeScraper::new()),
            ]
        }
        ContentMode::Both => {
            // Both mode: All sources
            vec![
                Box::new(TvTunesScraper::new(shared_browser.clone())),
                Box::new(AnimeThemesScraper::new()),
                Box::new(ThemesMoeScraper::new(shared_browser)),
                Box::new(YouTubeScraper::new()),
            ]
        }
    }
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
    ctrlc::set_handler(move || {
        eprintln!(
            "\n{} Interrupted by user. Exiting gracefully...",
            "⚠".yellow()
        );
        process::exit(130); // Standard exit code for SIGINT
    })
    .expect("Error setting Ctrl-C handler");

    // Display banner
    println!("\n{}", "═".repeat(60));
    println!(
        "{} {}",
        "Show Theme CLI".bold().cyan(),
        format!("v{}", env!("CARGO_PKG_VERSION")).dimmed()
    );
    println!("{}", "═".repeat(60));

    // Create orchestrator config
    let config = OrchestratorConfig {
        force: args.force,
        dry_run: args.dry_run,
        verbose: args.verbose,
        timeout: args.timeout,
    };

    // Initialize scrapers based on content mode
    info!("Initializing scrapers for mode: {:?}", args.mode);
    let scrapers = init_scrapers(args.mode);

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
