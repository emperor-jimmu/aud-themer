use async_trait::async_trait;
use std::path::Path;
use anyhow::{Result, Context};
use chromiumoxide::browser::{Browser, BrowserConfig};
use tokio::fs;
use tokio::io::AsyncWriteExt;
use futures::StreamExt;

use super::ThemeScraper;
use crate::config::Config;
use crate::ffmpeg::convert_audio;
use crate::retry::retry_with_backoff;

const BASE_URL: &str = "https://themes.moe";

pub struct ThemesMoeScraper {
    browser: Option<Browser>,
}

impl ThemesMoeScraper {
    pub fn new() -> Self {
        Self { browser: None }
    }

    async fn ensure_browser(&mut self) -> Result<&Browser> {
        if self.browser.is_none() {
            let (browser, mut handler) = Browser::launch(
                BrowserConfig::builder()
                    .arg("--ignore-certificate-errors")
                    .arg("--ignore-ssl-errors")
                    .build()
                    .map_err(|e| anyhow::anyhow!("Failed to build browser config: {}", e))?
            )
            .await
            .context("Failed to launch browser")?;

            // Spawn handler task
            tokio::spawn(async move {
                while let Some(_event) = handler.next().await {
                    // Handle browser events
                }
            });

            self.browser = Some(browser);
        }

        Ok(self.browser.as_ref().unwrap())
    }

    async fn search_anime(&mut self, show_name: &str) -> Result<Option<String>> {
        let browser = self.ensure_browser().await?;
        
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
        page.goto(BASE_URL)
            .await
            .context("Failed to navigate to Themes.moe")?
            .wait_for_navigation()
            .await
            .context("Failed to wait for navigation")?;

        // Wait for page to load
        tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;

        // Click the mode selector button (MyAnimeList/AniList/Anime Search dropdown)
        let mode_button = page.find_element("button:has-text('MyAnimeList'), button:has-text('AniList'), button:has-text('Anime Search')")
            .await;

        if let Ok(button) = mode_button {
            button.click()
                .await
                .context("Failed to click mode selector")?;
            
            tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

            // Click "Anime Search" option from the dropdown
            let anime_search_option = page.find_element("*:has-text('Anime Search')")
                .await;
            
            if let Ok(option) = anime_search_option {
                option.click()
                    .await
                    .context("Failed to select Anime Search mode")?;
                
                tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
            }
        }

        // Find search input
        let search_input = page.find_element("input[type='search'], input[placeholder*='search'], input[role='combobox']")
            .await
            .context("Failed to find search input")?;

        search_input.click()
            .await
            .context("Failed to click search input")?;

        search_input.type_str(show_name)
            .await
            .context("Failed to type show name")?;

        search_input.press_key("Enter")
            .await
            .context("Failed to submit search")?;

        // Wait for results
        tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;

        // Find OP theme links - they're direct .webm links in the table
        let op_links = page.find_elements("a[href*='.webm'][href*='OP']")
            .await
            .unwrap_or_default();

        if op_links.is_empty() {
            tracing::debug!("No OP themes found for: {}", show_name);
            return Ok(None);
        }

        // Get the first OP link
        let first_op = &op_links[0];
        let href = first_op.attribute("href")
            .await
            .context("Failed to get OP link href")?;

        if let Some(href) = href {
            tracing::debug!("Found theme URL: {}", href);
            Ok(Some(href))
        } else {
            Ok(None)
        }
    }

    async fn download_media(&mut self, url: &str, output_path: &Path) -> Result<bool> {
        // The URL is a direct link to the .webm file, no need for browser
        tracing::debug!("Downloading media from: {}", url);

        // Download the media file
        let client = reqwest::Client::builder()
            .danger_accept_invalid_certs(true)
            .timeout(std::time::Duration::from_secs(Config::DOWNLOAD_TIMEOUT_SEC))
            .build()
            .context("Failed to build HTTP client")?;
            
        let response = client.get(url)
            .send()
            .await
            .context("Failed to download media file")?;

        if !response.status().is_success() {
            return Ok(false);
        }

        let bytes = response.bytes()
            .await
            .context("Failed to read media bytes")?;

        // Save to temporary video file
        let temp_video = output_path.with_extension("temp.webm");
        let mut file = fs::File::create(&temp_video).await
            .context("Failed to create temp video file")?;
        file.write_all(&bytes).await
            .context("Failed to write temp video file")?;

        // Convert to MP3
        convert_audio(&temp_video, output_path, Config::AUDIO_BITRATE).await
            .context("Failed to convert video to MP3")?;

        // Clean up temp file
        let _ = fs::remove_file(&temp_video).await;

        Ok(true)
    }
}

impl Default for ThemesMoeScraper {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for ThemesMoeScraper {
    fn drop(&mut self) {
        // Browser cleanup happens automatically
    }
}

#[async_trait]
impl ThemeScraper for ThemesMoeScraper {
    async fn search_and_download(&self, show_name: &str, output_path: &Path) -> Result<bool> {
        // Need mutable self for browser operations
        let mut scraper = Self::new();
        
        // Search for the anime
        let media_url = match scraper.search_anime(show_name).await? {
            Some(url) => url,
            None => return Ok(false),
        };

        // Download the media
        scraper.download_media(&media_url, output_path).await
    }

    fn source_name(&self) -> &str {
        "Themes.moe"
    }
}
