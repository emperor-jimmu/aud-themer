use async_trait::async_trait;
use std::path::Path;
use anyhow::{Result, Context};
use tokio::fs;
use tokio::io::AsyncWriteExt;

use super::ThemeScraper;
use crate::browser::SharedBrowser;
use crate::config::Config;
use crate::ffmpeg::convert_audio;
use crate::retry::retry_with_backoff;

const BASE_URL: &str = "https://themes.moe";

pub struct ThemesMoeScraper {
    browser: SharedBrowser,
}

impl ThemesMoeScraper {
    /// Create a new `ThemesMoeScraper` with a shared browser instance
    #[must_use]
    pub fn new(browser: SharedBrowser) -> Self {
        Self { browser }
    }

    async fn search_anime(&self, show_name: &str) -> Result<Option<String>> {
        tracing::info!("[Themes.moe] Starting search for: {}", show_name);
        
        let browser_arc = self.browser.get().await?;
        let browser_guard = browser_arc.lock().await;
        let browser = browser_guard.as_ref().unwrap();

        let page = retry_with_backoff(
            Config::MAX_RETRY_ATTEMPTS,
            Config::RETRY_BACKOFF_FACTOR,
            || async {
                browser.new_page("about:blank")
                    .await
                    .context("Failed to create new page")
            }
        ).await?;

        // Navigate to Themes.moe
        tracing::info!("[Themes.moe] Navigating to: {}", BASE_URL);
        page.goto(BASE_URL)
            .await
            .context("Failed to navigate to Themes.moe")?
            .wait_for_navigation()
            .await
            .context("Failed to wait for navigation")?;

        // Wait for page to load
        tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;

        // Click the mode selector button to open dropdown
        let mode_button = page.find_element("button:has-text('MyAnimeList'), button:has-text('AniList'), button:has-text('Anime Search')")
            .await;

        if let Ok(button) = mode_button {
            tracing::info!("[Themes.moe] Clicking mode selector");
            button.click()
                .await
                .context("Failed to click mode selector")?;
            
            tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

            // Click "Anime Search" option from the dropdown
            let anime_search_option = page.find_element("*:has-text('Anime Search')")
                .await;
            
            if let Ok(option) = anime_search_option {
                tracing::info!("[Themes.moe] Selecting Anime Search mode");
                option.click()
                    .await
                    .context("Failed to select Anime Search mode")?;
                
                tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
            }
        }

        // Find search input (combobox)
        tracing::info!("[Themes.moe] Entering search query: {}", show_name);
        let search_input = page.find_element("input[type='search'], input[role='combobox'], input[placeholder*='search']")
            .await
            .context("Failed to find search input")?;

        search_input.click()
            .await
            .context("Failed to click search input")?;

        // Clear any existing text and type the show name
        search_input.type_str(show_name)
            .await
            .context("Failed to type show name")?;

        search_input.press_key("Enter")
            .await
            .context("Failed to submit search")?;

        // Wait for results page to load
        tracing::info!("[Themes.moe] Waiting for search results");
        tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;

        // Check if we got "No anime found" message
        let no_results = page.find_element("p:has-text('No anime found')")
            .await;
        
        if no_results.is_ok() {
            tracing::info!("[Themes.moe] No anime found for: {}", show_name);
            return Ok(None);
        }

        // Look for OP theme links in the table
        // The structure is: table > tbody > tr > td > a[href*='.webm']
        // We want links that contain 'OP' in the text or href
        let op_links = page.find_elements("table a[href*='.webm']")
            .await
            .unwrap_or_default();

        tracing::info!("[Themes.moe] Found {} theme links", op_links.len());

        if op_links.is_empty() {
            tracing::info!("[Themes.moe] No theme links found for: {}", show_name);
            return Ok(None);
        }

        // Find the first OP link (OP1, OP2, etc.)
        for link in &op_links {
            if let Ok(Some(text)) = link.inner_text().await {
                if text.to_uppercase().starts_with("OP") {
                    if let Ok(Some(href)) = link.attribute("href").await {
                        tracing::info!("[Themes.moe] Found OP theme: {} -> {}", text, href);
                        return Ok(Some(href));
                    }
                }
            }
        }

        // If no OP found, try getting href from first link and check if it contains OP
        if let Some(first_link) = op_links.first() {
            if let Ok(Some(href)) = first_link.attribute("href").await {
                if href.to_uppercase().contains("OP") {
                    tracing::info!("[Themes.moe] Found OP theme URL: {}", href);
                    return Ok(Some(href));
                }
            }
        }

        tracing::info!("[Themes.moe] No OP themes found for: {}", show_name);
        Ok(None)
    }

    async fn download_media(&self, url: &str, output_path: &Path) -> Result<bool> {
        tracing::info!("[Themes.moe] Downloading media from: {}", url);

        let client = reqwest::Client::builder()
            .danger_accept_invalid_certs(true)
            .timeout(std::time::Duration::from_secs(Config::DOWNLOAD_TIMEOUT_SEC))
            .user_agent(Config::USER_AGENT)
            .build()
            .context("Failed to build HTTP client")?;
            
        let response = client.get(url)
            .send()
            .await
            .context("Failed to download media file")?;

        let status = response.status();
        tracing::info!("[Themes.moe] Download response status: {}", status);

        if !status.is_success() {
            tracing::error!("[Themes.moe] Download failed with status: {}", status);
            return Ok(false);
        }

        let bytes = response.bytes()
            .await
            .context("Failed to read media bytes")?;

        tracing::info!("[Themes.moe] Downloaded {} bytes", bytes.len());

        // Save to temporary video file
        let temp_video = output_path.with_extension("temp.webm");
        let mut file = fs::File::create(&temp_video).await
            .context("Failed to create temp video file")?;
        file.write_all(&bytes).await
            .context("Failed to write temp video file")?;

        // Convert to MP3
        tracing::info!("[Themes.moe] Converting to MP3");
        convert_audio(&temp_video, output_path, Config::AUDIO_BITRATE).await
            .context("Failed to convert video to MP3")?;

        // Clean up temp file
        let _ = fs::remove_file(&temp_video).await;
        
        tracing::info!("[Themes.moe] Successfully downloaded and converted theme");
        Ok(true)
    }
}

#[async_trait]
impl ThemeScraper for ThemesMoeScraper {
    async fn search_and_download(&self, show_name: &str, output_path: &Path) -> Result<bool> {
        tracing::info!("[Themes.moe] Starting search for: {}", show_name);
        
        let Some(media_url) = self.search_anime(show_name).await? else {
            tracing::info!("[Themes.moe] No theme found for: {}", show_name);
            return Ok(false);
        };

        self.download_media(&media_url, output_path).await
    }

    fn source_name(&self) -> &'static str {
        "Themes.moe"
    }
}
