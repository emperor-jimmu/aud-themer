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

const BASE_URL: &str = "https://www.televisiontunes.com";

pub struct TvTunesScraper {
    browser: Option<Browser>,
}

impl TvTunesScraper {
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

    async fn search_show(&mut self, show_name: &str) -> Result<Option<String>> {
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

        // Navigate directly to search results page
        let search_url = format!("{}/search.php?q={}", BASE_URL, urlencoding::encode(show_name));
        
        tracing::debug!("Searching TelevisionTunes for: {} at {}", show_name, search_url);
        
        page.goto(&search_url)
            .await
            .context("Failed to navigate to search results")?
            .wait_for_navigation()
            .await
            .context("Failed to wait for navigation")?;

        // Wait for search results to load
        tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

        // Find search result links - look for links in the search results area
        // The results are in a specific container, look for links to .html pages
        let results = page.find_elements("a[href*='.html']")
            .await
            .unwrap_or_default();

        if results.is_empty() {
            return Ok(None);
        }

        // Get the first result's href
        let first_result = &results[0];
        let href = first_result.attribute("href")
            .await
            .context("Failed to get href attribute")?;

        if let Some(href) = href {
            let full_url = if href.starts_with("http") {
                href
            } else {
                format!("{}/{}", BASE_URL, href.trim_start_matches('/'))
            };
            tracing::debug!("Found result page: {}", full_url);
            Ok(Some(full_url))
        } else {
            Ok(None)
        }
    }

    async fn download_from_page(&mut self, url: &str, output_path: &Path) -> Result<bool> {
        let browser = self.ensure_browser().await?;
        let page = browser.new_page(url)
            .await
            .context("Failed to create page for download")?;

        page.wait_for_navigation()
            .await
            .context("Failed to wait for page load")?;

        // Wait for page to fully load
        tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

        // Find download link - it's in the format /song/download/{id}
        let download_link = page.find_element("a[href*='/song/download/']")
            .await;

        if download_link.is_err() {
            tracing::debug!("No download link found on page: {}", url);
            return Ok(false);
        }

        let link = download_link.unwrap();
        let href = link.attribute("href")
            .await
            .context("Failed to get download link")?;

        if let Some(download_url) = href {
            let full_url = if download_url.starts_with("http") {
                download_url
            } else {
                format!("{}{}", BASE_URL, download_url)
            };

            tracing::debug!("Attempting to download from: {}", full_url);

            // Download the file
            let client = reqwest::Client::builder()
                .danger_accept_invalid_certs(true)
                .timeout(std::time::Duration::from_secs(Config::DOWNLOAD_TIMEOUT_SEC))
                .build()
                .context("Failed to build HTTP client")?;
                
            let response = client.get(&full_url)
                .send()
                .await
                .context("Failed to download audio file")?;

            if !response.status().is_success() {
                return Ok(false);
            }

            // Get content type before consuming response
            let content_type = response.headers()
                .get("content-type")
                .and_then(|v| v.to_str().ok())
                .unwrap_or("")
                .to_string();

            let bytes = response.bytes()
                .await
                .context("Failed to read audio bytes")?;

            // Determine if we need to convert based on content type or file signature
            let needs_conversion = content_type.contains("wav") || 
                                   content_type.contains("x-wav") ||
                                   // Check WAV file signature (RIFF header)
                                   (bytes.len() > 12 && &bytes[0..4] == b"RIFF" && &bytes[8..12] == b"WAVE");

            if needs_conversion {
                // Save to temporary WAV file
                let temp_wav = output_path.with_extension("temp.wav");
                let mut file = fs::File::create(&temp_wav).await
                    .context("Failed to create temp WAV file")?;
                file.write_all(&bytes).await
                    .context("Failed to write temp WAV file")?;

                // Convert to MP3
                convert_audio(&temp_wav, output_path, Config::AUDIO_BITRATE).await
                    .context("Failed to convert WAV to MP3")?;

                // Clean up temp file
                let _ = fs::remove_file(&temp_wav).await;
            } else {
                // Save directly as MP3
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

impl Default for TvTunesScraper {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for TvTunesScraper {
    fn drop(&mut self) {
        // Browser cleanup happens automatically
    }
}

#[async_trait]
impl ThemeScraper for TvTunesScraper {
    async fn search_and_download(&self, show_name: &str, output_path: &Path) -> Result<bool> {
        // Need mutable self for browser operations
        let mut scraper = Self::new();
        
        // Search for the show
        let result_url = match scraper.search_show(show_name).await? {
            Some(url) => url,
            None => return Ok(false),
        };

        // Download from the result page
        scraper.download_from_page(&result_url, output_path).await
    }

    fn source_name(&self) -> &str {
        "TelevisionTunes"
    }
}
