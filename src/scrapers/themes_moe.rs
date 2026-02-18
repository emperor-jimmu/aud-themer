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
                    .with_head()
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

        // Select "Anime Search" mode
        let anime_search_button = page.find_element("button[data-mode='anime'], a[href*='anime']")
            .await;

        if let Ok(button) = anime_search_button {
            button.click()
                .await
                .context("Failed to click anime search mode")?;
            
            tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
        }

        // Find search input
        let search_input = page.find_element("input[type='search'], input[placeholder*='Search']")
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
        tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

        // Find OP theme links in results table
        let op_links = page.find_elements("a[href*='OP'], tr:has-text('OP') a, td:has-text('OP') + td a")
            .await
            .unwrap_or_default();

        if op_links.is_empty() {
            return Ok(None);
        }

        // Get the first OP link
        let first_op = &op_links[0];
        let href = first_op.attribute("href")
            .await
            .context("Failed to get OP link href")?;

        if let Some(href) = href {
            let full_url = if href.starts_with("http") {
                href
            } else {
                format!("{}{}", BASE_URL, href)
            };
            Ok(Some(full_url))
        } else {
            Ok(None)
        }
    }

    async fn download_media(&mut self, url: &str, output_path: &Path) -> Result<bool> {
        let browser = self.ensure_browser().await?;
        let page = browser.new_page(url)
            .await
            .context("Failed to create page for media")?;

        page.wait_for_navigation()
            .await
            .context("Failed to wait for page load")?;

        // Find media source (video or audio)
        let media_element = page.find_element("video source, audio source, video, audio")
            .await;

        if media_element.is_err() {
            return Ok(false);
        }

        let element = media_element.unwrap();
        let src = element.attribute("src")
            .await
            .context("Failed to get media src")?;

        if let Some(media_url) = src {
            let full_url = if media_url.starts_with("http") {
                media_url
            } else {
                format!("{}{}", BASE_URL, media_url)
            };

            // Download the media file
            let client = reqwest::Client::new();
            let response = client.get(&full_url)
                .timeout(std::time::Duration::from_secs(Config::DOWNLOAD_TIMEOUT_SEC))
                .send()
                .await
                .context("Failed to download media file")?;

            if !response.status().is_success() {
                return Ok(false);
            }

            let bytes = response.bytes()
                .await
                .context("Failed to read media bytes")?;

            // Determine if it's a video format that needs conversion
            let is_video = full_url.ends_with(".mp4") || full_url.ends_with(".webm");

            if is_video {
                // Save to temporary video file
                let temp_video = output_path.with_extension("temp.mp4");
                let mut file = fs::File::create(&temp_video).await
                    .context("Failed to create temp video file")?;
                file.write_all(&bytes).await
                    .context("Failed to write temp video file")?;

                // Convert to MP3
                convert_audio(&temp_video, output_path, Config::AUDIO_BITRATE).await
                    .context("Failed to convert video to MP3")?;

                // Clean up temp file
                let _ = fs::remove_file(&temp_video).await;
            } else {
                // Save directly as MP3 or convert if needed
                let mut file = fs::File::create(output_path).await
                    .context("Failed to create output file")?;
                file.write_all(&bytes).await
                    .context("Failed to write output file")?;
            }

            Ok(true)
        } else {
            Ok(false)
        }
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
