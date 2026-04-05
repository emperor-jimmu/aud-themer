use crate::config::Config;
use crate::rate_limiter::RateLimiter;
use crate::scrapers::ThemeScraper;
use crate::utils::{get_file_size_formatted, strip_year_from_show_name, validate_show_name};
use anyhow::Result;
use colored::Colorize;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

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
    /// Cancellation flag (set by Ctrl+C handler)
    cancel_flag: Arc<AtomicBool>,
}

impl Orchestrator {
    /// Create a new orchestrator with the given configuration and scrapers
    #[must_use]
    pub fn new(config: OrchestratorConfig, scrapers: Vec<Box<dyn ThemeScraper>>) -> Self {
        Self::with_cancel_flag(config, scrapers, Arc::new(AtomicBool::new(false)))
    }

    /// Create a new orchestrator with a cancellation flag for graceful shutdown
    #[must_use]
    pub fn with_cancel_flag(
        config: OrchestratorConfig,
        scrapers: Vec<Box<dyn ThemeScraper>>,
        cancel_flag: Arc<AtomicBool>,
    ) -> Self {
        let rate_limiter = RateLimiter::new();

        Self {
            scrapers,
            rate_limiter,
            config,
            results: ProcessingResults::default(),
            cancel_flag,
        }
    }

    /// Get the current processing results
    #[must_use]
    pub const fn results(&self) -> &ProcessingResults {
        &self.results
    }

    /// Process a directory containing show folders
    ///
    /// # Errors
    ///
    /// Returns an error if the directory cannot be read or if there are critical I/O failures.
    pub async fn process_directory(&mut self, input_dir: &Path) -> Result<()> {
        // Scan directory for show folders
        let show_folders = Self::scan_directory(input_dir)?;

        if show_folders.is_empty() {
            println!(
                "{}",
                "No series folders found in the input directory.".yellow()
            );
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
            // Check for cancellation before each show
            if self.cancel_flag.load(Ordering::SeqCst) {
                tracing::info!("Cancellation requested, stopping after {} shows", index);
                println!(
                    "\n{} Stopped by user after processing {}/{} shows",
                    "⚠".yellow(),
                    index,
                    total
                );
                break;
            }

            let folder_num = index + 1;
            self.process_show(show_folder, folder_num, total).await;
        }

        // Display summary
        self.display_summary();

        Ok(())
    }

    /// Scan directory and return list of show folders
    fn scan_directory(input_dir: &Path) -> Result<Vec<ShowFolder>> {
        tracing::info!("Scanning directory: {}", input_dir.display());

        let mut show_folders = Vec::new();

        let entries = fs::read_dir(input_dir)?;

        for entry in entries {
            let entry = match entry {
                Ok(e) => e,
                Err(err) => {
                    tracing::warn!("Failed to read directory entry: {}", err);
                    eprintln!(
                        "{} Failed to read directory entry: {}",
                        "Warning:".yellow(),
                        err
                    );
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
                tracing::warn!("Skipping folder '{}': invalid or too long name", name);
                eprintln!(
                    "{} Skipping folder '{}': invalid or too long name",
                    "Warning:".yellow(),
                    name
                );
                continue;
            }

            // Strip year from name for search
            let search_name = strip_year_from_show_name(&name);

            tracing::debug!("Found show folder: {} (search: {})", name, search_name);

            show_folders.push(ShowFolder {
                path,
                name,
                search_name,
            });
        }

        // Sort by name for reproducible processing order
        show_folders.sort_by(|a, b| a.name.cmp(&b.name));

        tracing::info!("Found {} show folders", show_folders.len());
        Ok(show_folders)
    }

    /// Process a single show folder
    async fn process_show(&mut self, show_folder: &ShowFolder, folder_num: usize, total: usize) {
        tracing::info!(
            "Processing show {}/{}: {} (search name: {})",
            folder_num,
            total,
            show_folder.name,
            show_folder.search_name
        );

        println!(
            "{} {}/{} - {}",
            "Processing".cyan().bold(),
            folder_num,
            total,
            show_folder.name.bold()
        );

        // Check for existing theme
        if let Some(existing_theme) = Self::check_existing_theme(&show_folder.path) {
            if self.config.force {
                // Force mode: delete existing theme
                tracing::info!("Force mode: deleting existing theme: {}", existing_theme);
                println!(
                    "  {} Deleting existing theme: {}",
                    "⚠".yellow(),
                    existing_theme
                );
                if let Err(err) =
                    fs::remove_file(show_folder.path.join("theme-music").join(&existing_theme))
                {
                    tracing::error!("Failed to delete existing theme: {}", err);
                    eprintln!(
                        "  {} Failed to delete existing theme: {}",
                        "Error:".red(),
                        err
                    );
                    self.results.failed += 1;
                    return;
                }
            } else {
                tracing::info!("Skipping - already has theme: {}", existing_theme);
                println!("  {} Already has theme: {}", "⊘".yellow(), existing_theme);
                self.results.skipped += 1;
                return;
            }
        }

        // Try scrapers in order
        for scraper in &self.scrapers {
            let source_name = scraper.source_name();

            tracing::info!("Attempting scraper: {}", source_name);
            println!("  {} Trying {}...", "→".cyan(), source_name);

            // Ensure theme-music directory exists
            let theme_dir = show_folder.path.join("theme-music");
            if !self.config.dry_run && let Err(err) = fs::create_dir_all(&theme_dir) {
                tracing::error!("Failed to create theme-music directory: {}", err);
                eprintln!(
                    "  {} Failed to create theme-music directory: {}",
                    "Error:".red(),
                    err
                );
                self.results.failed += 1;
                return;
            }

            // Apply rate limiting (skip in dry run to speed up)
            if !self.config.dry_run {
                self.rate_limiter.wait_if_needed(source_name).await;
            }

            // Try to download (or simulate in dry run)
            match scraper
                .search_and_download(
                    &show_folder.search_name,
                    &show_folder.path.join("theme-music").join("theme.mp3"),
                    self.config.dry_run,
                )
                .await
            {
                Ok(true) => {
                    // Success (or would succeed in dry run)
                    if self.config.dry_run {
                        tracing::info!("Dry run: Would download from {}", source_name);
                        println!(
                            "  {} Would download from {}",
                            "✓".green().bold(),
                            source_name.green()
                        );
                        self.results.success += 1;
                        return;
                    }

                    // Verify the file was actually written
                    let theme_path = show_folder.path.join("theme-music").join("theme.mp3");
                    if !theme_path.exists() {
                        tracing::warn!(
                            "{} claimed success but theme file not found at: {}",
                            source_name,
                            theme_path.display()
                        );
                        eprintln!(
                            "  {} {} reported success but file not found, trying next source",
                            "⚠".yellow(),
                            source_name
                        );
                        continue;
                    }

                    let file_size = get_file_size_formatted(&theme_path);
                    tracing::info!(
                        "Successfully downloaded from {} ({})",
                        source_name,
                        file_size
                    );
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
                    tracing::info!("Not found at {}", source_name);
                    println!("  {} Not found at {}", "✗".red(), source_name);
                }
                Err(err) => {
                    // Error occurred
                    tracing::error!("Error with {}: {}", source_name, err);
                    eprintln!("  {} Error with {}: {}", "✗".red(), source_name, err);
                }
            }
        }

        // All sources failed
        tracing::warn!("Failed to find theme for: {}", show_folder.name);
        println!("  {} Failed to find theme", "✗".red().bold());
        self.results.failed += 1;
    }

    /// Check if a theme file already exists in the folder
    fn check_existing_theme(folder_path: &Path) -> Option<String> {
        for ext in Config::THEME_EXTENSIONS {
            let theme_file = format!("theme{ext}");
            let theme_path = folder_path.join("theme-music").join(&theme_file);
            tracing::debug!(
                "Checking for existing theme: {} (exists={})",
                theme_path.display(),
                theme_path.exists()
            );
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
