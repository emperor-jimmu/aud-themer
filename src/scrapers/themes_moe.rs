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

    async fn download_media(&self, url: &str, output_path: &Path) -> Result<bool> {
        tracing::debug!("Downloading media from: {}", url);

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

#[async_trait]
impl ThemeScraper for ThemesMoeScraper {
    async fn search_and_download(&self, show_name: &str, output_path: &Path) -> Result<bool> {
        let Some(media_url) = self.search_anime(show_name).await? else {
            return Ok(false);
        };

        self.download_media(&media_url, output_path).await
    }

    fn source_name(&self) -> &'static str {
        "Themes.moe"
    }
}
