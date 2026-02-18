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

const BASE_URL: &str = "https://www.televisiontunes.com";

pub struct TvTunesScraper {
    browser: SharedBrowser,
}

impl TvTunesScraper {
    /// Create a new `TvTunesScraper` with a shared browser instance
    #[must_use]
    pub fn new(browser: SharedBrowser) -> Self {
        Self { browser }
    }

    async fn search_show(&self, show_name: &str) -> Result<Option<String>> {
        tracing::info!("[TelevisionTunes] Starting search for: {}", show_name);
        
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

        // Navigate directly to search results page
        let search_url = format!("{}/search.php?q={}", BASE_URL, urlencoding::encode(show_name));
        
        tracing::info!("[TelevisionTunes] Navigating to search URL: {}", search_url);
        
        page.goto(&search_url)
            .await
            .context("Failed to navigate to search results")?
            .wait_for_navigation()
            .await
            .context("Failed to wait for navigation")?;

        // Wait for search results to load
        tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

        // Find search result links - look for links in the search results area
        let results = page.find_elements("a[href*='.html']")
            .await
            .unwrap_or_default();

        tracing::info!("[TelevisionTunes] Found {} search results", results.len());

        if results.is_empty() {
            tracing::info!("[TelevisionTunes] No results found for: {}", show_name);
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
            tracing::info!("[TelevisionTunes] Selected result page: {}", full_url);
            Ok(Some(full_url))
        } else {
            tracing::warn!("[TelevisionTunes] First result has no href attribute");
            Ok(None)
        }
    }

    async fn download_from_page(&self, url: &str, output_path: &Path) -> Result<bool> {
        tracing::info!("[TelevisionTunes] Opening result page: {}", url);
        
        let browser_arc = self.browser.get().await?;
        let browser_guard = browser_arc.lock().await;
        let browser = browser_guard.as_ref().unwrap();
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
            tracing::warn!("[TelevisionTunes] No download link found on page: {}", url);
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
                format!("{BASE_URL}{download_url}")
            };

            tracing::info!("[TelevisionTunes] Downloading from: {}", full_url);

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

            let status = response.status();
            tracing::info!("[TelevisionTunes] Download response status: {}", status);

            if !status.is_success() {
                tracing::error!("[TelevisionTunes] Download failed with status: {}", status);
                return Ok(false);
            }

            // Get content type before consuming response
            let content_type = response.headers()
                .get("content-type")
                .and_then(|v| v.to_str().ok())
                .unwrap_or("")
                .to_string();

            tracing::info!("[TelevisionTunes] Content-Type: {}", content_type);

            let bytes = response.bytes()
                .await
                .context("Failed to read audio bytes")?;

            tracing::info!("[TelevisionTunes] Downloaded {} bytes", bytes.len());

            // Determine if we need to convert based on content type or file signature
            let needs_conversion = content_type.contains("wav") || 
                                   content_type.contains("x-wav") ||
                                   // Check WAV file signature (RIFF header)
                                   (bytes.len() > 12 && &bytes[0..4] == b"RIFF" && &bytes[8..12] == b"WAVE");

            if needs_conversion {
                tracing::info!("[TelevisionTunes] Converting WAV to MP3");
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
                tracing::info!("[TelevisionTunes] Conversion complete");
            } else {
                tracing::info!("[TelevisionTunes] Saving directly as MP3");
                // Save directly as MP3
                let mut file = fs::File::create(output_path).await
                    .context("Failed to create output file")?;
                file.write_all(&bytes).await
                    .context("Failed to write output file")?;
            }

            tracing::info!("[TelevisionTunes] Successfully downloaded to: {}", output_path.display());
            Ok(true)
        } else {
            tracing::warn!("[TelevisionTunes] Download link has no href attribute");
            Ok(false)
        }
    }
}

#[async_trait]
impl ThemeScraper for TvTunesScraper {
    async fn search_and_download(&self, show_name: &str, output_path: &Path) -> Result<bool> {
        tracing::info!("[TelevisionTunes] Starting search for: {}", show_name);
        
        // Search for the show
        let Some(result_url) = self.search_show(show_name).await? else {
            tracing::info!("[TelevisionTunes] No show found for: {}", show_name);
            return Ok(false);
        };

        // Download from the result page
        self.download_from_page(&result_url, output_path).await
    }

    fn source_name(&self) -> &'static str {
        "TelevisionTunes"
    }
}
