use async_trait::async_trait;
use std::path::Path;

pub mod anime_themes;
pub mod themes_moe;
pub mod tv_tunes;
pub mod youtube;

/// Outcome of a scraper operation
#[derive(Debug, Clone, PartialEq)]
pub enum ScraperOutcome {
    /// Theme was successfully downloaded
    Downloaded,
    /// Theme was not found at this source
    NotFound,
    /// An error occurred during scraping
    Error(String),
}

/// Trait for theme song scrapers
#[async_trait]
pub trait ThemeScraper: Send + Sync {
    /// Search for and download a theme song.
    ///
    /// # Arguments
    /// * `show_name` - The name of the show to search for
    /// * `output_path` - The path where the theme file should be saved
    /// * `dry_run` - If true, perform all operations except the actual download
    ///
    /// # Returns
    /// * `Ok(true)` - Theme was successfully downloaded (or would be in dry run)
    /// * `Ok(false)` - Theme was not found at this source
    /// * `Err` - A fatal error occurred
    async fn search_and_download(
        &self,
        show_name: &str,
        output_path: &Path,
        dry_run: bool,
    ) -> anyhow::Result<bool>;

    /// Returns the human-readable name of this scraper source
    fn source_name(&self) -> &'static str;
}
