use crate::config::Config;
use crate::rate_limiter::RateLimiter;
use crate::scrapers::ThemeScraper;
use crate::utils::{get_file_size_formatted, strip_year_from_show_name, validate_show_name};
use anyhow::Result;
use colored::Colorize;
use std::fs;
use std::path::{Path, PathBuf};

/// Configuration for the orchestrator
#[derive(Debug, Clone)]
pub struct OrchestratorConfig {
    /// Overwrite existing theme files
    pub force: bool,
    /// Simulate operations without downloading
    pub dry_run: bool,
    /// Enable verbose/debug logging
    pub verbose: bool,
    /// Network timeout in seconds
    pub timeout: u64,
}

/// Aggregated processing results
#[derive(Debug, Clone, Default)]
pub struct ProcessingResults {
    /// Number of successfully downloaded themes
    pub success: u32,
    /// Number of skipped shows (already have themes)
    pub skipped: u32,
    /// Number of failed shows (all sources failed)
    pub failed: u32,
}

/// Represents a show folder to be processed
#[derive(Debug, Clone)]
pub struct ShowFolder {
    /// Full path to the show folder
    pub path: PathBuf,
    /// Original folder name
    pub name: String,
    /// Search name with year stripped (e.g., "The Simpsons (1989)" -> "The Simpsons")
    pub search_name: String,
}

/// Result of processing a single show
#[derive(Debug, Clone)]
pub enum ShowResult {
    /// Theme was successfully downloaded
    Success {
        source: String,
        file_size: String,
        duration: String,
    },
    /// Show was skipped (already has theme)
    Skipped { reason: String },
    /// All sources failed to find/download theme
    Failed { attempted_sources: Vec<String> },
    /// Dry run mode (no actual download)
    DryRun,
}

/// Main orchestrator that coordinates directory scanning and scraper execution
pub struct Orchestrator {
    /// List of scrapers to try in priority order
    scrapers: Vec<Box<dyn ThemeScraper>>,
    /// Rate limiter to prevent overwhelming sources
    rate_limiter: RateLimiter,
    /// Configuration options
    config: OrchestratorConfig,
    /// Accumulated results
    results: ProcessingResults,
}

impl Orchestrator {
    /// Create a new orchestrator with the given configuration and scrapers
    pub fn new(
        config: OrchestratorConfig,
        scrapers: Vec<Box<dyn ThemeScraper>>,
    ) -> Self {
        let rate_limiter = RateLimiter::new();

        Self {
            scrapers,
            rate_limiter,
            config,
            results: ProcessingResults::default(),
        }
    }

    /// Get the current processing results
    pub fn results(&self) -> &ProcessingResults {
        &self.results
    }

    /// Process a directory containing show folders
    pub async fn process_directory(&mut self, input_dir: &Path) -> Result<()> {
        // Scan directory for show folders
        let show_folders = self.scan_directory(input_dir)?;

        if show_folders.is_empty() {
            println!("{}", "No series folders found in the input directory.".yellow());
            return Ok(());
        }

        // Display total count
        println!(
            "\n{} {} show folders\n",
            "Found".green().bold(),
            show_folders.len()
        );

        // Process each show folder
        let total = show_folders.len();
        for (index, show_folder) in show_folders.iter().enumerate() {
            let folder_num = index + 1;
            self.process_show(show_folder, folder_num, total).await;
        }

        // Display summary
        self.display_summary();

        Ok(())
    }

    /// Scan directory and return list of show folders
    fn scan_directory(&self, input_dir: &Path) -> Result<Vec<ShowFolder>> {
        let mut show_folders = Vec::new();

        let entries = fs::read_dir(input_dir)?;

        for entry in entries {
            let entry = match entry {
                Ok(e) => e,
                Err(err) => {
                    eprintln!("{} Failed to read directory entry: {}", "Warning:".yellow(), err);
                    continue;
                }
            };

            let path = entry.path();

            // Skip if not a directory
            if !path.is_dir() {
                continue;
            }

            // Get folder name
            let name = match path.file_name() {
                Some(n) => n.to_string_lossy().to_string(),
                None => continue,
            };

            // Validate show name
            if !validate_show_name(&name) {
                eprintln!(
                    "{} Skipping folder '{}': invalid or too long name",
                    "Warning:".yellow(),
                    name
                );
                continue;
            }

            // Strip year from name for search
            let search_name = strip_year_from_show_name(&name);

            show_folders.push(ShowFolder {
                path,
                name,
                search_name,
            });
        }

        Ok(show_folders)
    }

    /// Process a single show folder
    async fn process_show(&mut self, show_folder: &ShowFolder, folder_num: usize, total: usize) {
        println!(
            "{} {}/{} - {}",
            "Processing".cyan().bold(),
            folder_num,
            total,
            show_folder.name.bold()
        );

        // Check for existing theme
        if let Some(existing_theme) = self.check_existing_theme(&show_folder.path) {
            if !self.config.force {
                println!("  {} Already has theme: {}", "⊘".yellow(), existing_theme);
                self.results.skipped += 1;
                return;
            } else {
                // Force mode: delete existing theme
                println!("  {} Deleting existing theme: {}", "⚠".yellow(), existing_theme);
                if let Err(err) = fs::remove_file(show_folder.path.join(&existing_theme)) {
                    eprintln!(
                        "  {} Failed to delete existing theme: {}",
                        "Error:".red(),
                        err
                    );
                    self.results.failed += 1;
                    return;
                }
            }
        }

        // Dry run mode
        if self.config.dry_run {
            println!("  {} Dry run - would search for theme", "ℹ".blue());
            return;
        }

        // Try scrapers in order
        let mut attempted_sources = Vec::new();
        for scraper in &self.scrapers {
            let source_name = scraper.source_name();
            attempted_sources.push(source_name.to_string());

            println!("  {} Trying {}...", "→".cyan(), source_name);

            // Apply rate limiting
            self.rate_limiter.wait_if_needed(source_name).await;

            // Try to download
            match scraper
                .search_and_download(
                    &show_folder.search_name,
                    &show_folder.path.join("theme.mp3"),
                )
                .await
            {
                Ok(true) => {
                    // Success!
                    let theme_path = show_folder.path.join("theme.mp3");
                    let file_size = get_file_size_formatted(&theme_path);
                    println!(
                        "  {} Downloaded from {} ({})",
                        "✓".green().bold(),
                        source_name.green(),
                        file_size
                    );
                    self.results.success += 1;
                    return;
                }
                Ok(false) => {
                    // Not found at this source
                    println!("  {} Not found at {}", "✗".red(), source_name);
                }
                Err(err) => {
                    // Error occurred
                    eprintln!(
                        "  {} Error with {}: {}",
                        "✗".red(),
                        source_name,
                        err
                    );
                }
            }
        }

        // All sources failed
        println!("  {} Failed to find theme", "✗".red().bold());
        self.results.failed += 1;
    }

    /// Check if a theme file already exists in the folder
    fn check_existing_theme(&self, folder_path: &Path) -> Option<String> {
        for ext in Config::THEME_EXTENSIONS {
            let theme_file = format!("theme{}", ext);
            let theme_path = folder_path.join(&theme_file);
            if theme_path.exists() {
                return Some(theme_file);
            }
        }
        None
    }

    /// Display summary of processing results
    fn display_summary(&self) {
        println!("\n{}", "═".repeat(50));
        println!("{}", "Summary".bold().cyan());
        println!("{}", "═".repeat(50));
        println!(
            "  {} Successful downloads: {}",
            "✓".green(),
            self.results.success
        );
        println!(
            "  {} Skipped (already have theme): {}",
            "⊘".yellow(),
            self.results.skipped
        );
        println!(
            "  {} Failed (not found): {}",
            "✗".red(),
            self.results.failed
        );
        println!("{}", "═".repeat(50));
    }
}
