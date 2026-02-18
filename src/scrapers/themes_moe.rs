use anyhow::{Context, Result};
use async_trait::async_trait;
use futures::StreamExt;
use reqwest::Client;
use std::path::Path;
use tokio::fs;
use tokio::io::AsyncWriteExt;

use super::ThemeScraper;
use crate::browser::SharedBrowser;
use crate::config::{Config, USER_AGENT};
use crate::ffmpeg::convert_audio;
use crate::retry::retry_with_backoff;

const BASE_URL: &str = "https://themes.moe";

pub struct ThemesMoeScraper {
    browser: SharedBrowser,
    client: Client,
}

impl ThemesMoeScraper {
    /// Create a new `ThemesMoeScraper` with a shared browser instance
    #[must_use]
    pub fn new(browser: SharedBrowser) -> Self {
        let client = Client::builder()
            .danger_accept_invalid_certs(true)
            .connect_timeout(std::time::Duration::from_secs(Config::DEFAULT_TIMEOUT_SEC))
            .user_agent(USER_AGENT.as_str())
            .build()
            .expect("Failed to build HTTP client");

        Self { browser, client }
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
                browser
                    .new_page("about:blank")
                    .await
                    .context("Failed to create new page")
            },
        )
        .await?;

        // Navigate to Themes.moe
        tracing::info!("[Themes.moe] Navigating to: {}", BASE_URL);
        page.goto(BASE_URL)
            .await
            .context("Failed to navigate to Themes.moe")?
            .wait_for_navigation()
            .await
            .context("Failed to wait for navigation")?;

        // Wait for page to load
        tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

        // Click the mode selector button using JS (chromiumoxide doesn't support :has-text)
        let _ = page
            .evaluate_expression(
                r#"
                (function() {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent.trim();
                        if (text === 'MyAnimeList' || text === 'AniList' || text === 'Anime Search') {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                })()
                "#,
            )
            .await;

        tracing::info!("[Themes.moe] Clicked mode selector");
        tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

        // Click "Anime Search" option from the dropdown
        let _ = page
            .evaluate_expression(
                r#"
                (function() {
                    const items = document.querySelectorAll('li, li > div, li > span');
                    for (const item of items) {
                        if (item.textContent.trim() === 'Anime Search') {
                            item.click();
                            return true;
                        }
                    }
                    return false;
                })()
                "#,
            )
            .await;

        tracing::info!("[Themes.moe] Selected Anime Search mode");
        tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

        // Find and interact with the search input
        tracing::info!("[Themes.moe] Entering search query: {}", show_name);
        let search_input = page
            .find_element("input[role='combobox'], input[type='search'], input[placeholder]")
            .await
            .context("Failed to find search input")?;

        search_input
            .click()
            .await
            .context("Failed to click search input")?;

        search_input
            .type_str(show_name)
            .await
            .context("Failed to type show name")?;

        search_input
            .press_key("Enter")
            .await
            .context("Failed to submit search")?;

        // Wait for results page to load
        tracing::info!("[Themes.moe] Waiting for search results");
        tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;

        // Check for "No anime found" or "No results" using JS
        let no_results: bool = page
            .evaluate_expression(
                r#"
                (function() {
                    const body = document.body.innerText;
                    return body.includes('No anime found') || body.includes('No results available');
                })()
                "#,
            )
            .await
            .ok()
            .and_then(|v| v.value().map(|val| val.as_bool().unwrap_or(false)))
            .unwrap_or(false);

        if no_results {
            tracing::info!("[Themes.moe] No anime found for: {}", show_name);
            return Ok(None);
        }

        // Look for OP theme links in the results table
        let op_links = page
            .find_elements("table a[href*='.webm']")
            .await
            .unwrap_or_default();

        tracing::info!("[Themes.moe] Found {} theme links", op_links.len());

        if op_links.is_empty() {
            tracing::info!("[Themes.moe] No theme links found for: {}", show_name);
            return Ok(None);
        }

        // Find the first OP link (OP1, OP2, etc.)
        for link in &op_links {
            if let Ok(Some(text)) = link.inner_text().await
                && text.to_uppercase().starts_with("OP")
                && let Ok(Some(href)) = link.attribute("href").await
            {
                tracing::info!("[Themes.moe] Found OP theme: {} -> {}", text, href);
                return Ok(Some(href));
            }
        }

        // If no OP found by text, check href for OP pattern
        if let Some(first_link) = op_links.first()
            && let Ok(Some(href)) = first_link.attribute("href").await
            && href.to_uppercase().contains("-OP")
        {
            tracing::info!("[Themes.moe] Found OP theme URL: {}", href);
            return Ok(Some(href));
        }

        tracing::info!("[Themes.moe] No OP themes found for: {}", show_name);
        Ok(None)
    }

    async fn download_media(&self, url: &str, output_path: &Path) -> Result<bool> {
        tracing::info!("[Themes.moe] Downloading media from: {}", url);

        let response = self
            .client
            .get(url)
            .send()
            .await
            .context("Failed to download media file")?;

        let status = response.status();
        tracing::info!("[Themes.moe] Download response status: {}", status);

        if !status.is_success() {
            tracing::error!("[Themes.moe] Download failed with status: {}", status);
            return Ok(false);
        }

        // Stream to temporary video file to avoid timeout on large .webm files
        let temp_video = output_path.with_extension("temp.webm");
        let mut file = fs::File::create(&temp_video)
            .await
            .context("Failed to create temp video file")?;

        let mut stream = response.bytes_stream();
        let mut total_bytes: u64 = 0;

        while let Some(chunk) = stream.next().await {
            let chunk = chunk.context("Failed to read media chunk")?;
            total_bytes += chunk.len() as u64;
            file.write_all(&chunk)
                .await
                .context("Failed to write media chunk")?;
        }

        tracing::info!("[Themes.moe] Downloaded {} bytes", total_bytes);

        // Convert to MP3
        tracing::info!("[Themes.moe] Converting to MP3");
        convert_audio(&temp_video, output_path, Config::AUDIO_BITRATE)
            .await
            .context("Failed to convert video to MP3")?;

        // Clean up temp file
        let _ = fs::remove_file(&temp_video).await;

        tracing::info!("[Themes.moe] Successfully downloaded and converted theme");
        Ok(true)
    }
}

#[async_trait]
impl ThemeScraper for ThemesMoeScraper {
    async fn search_and_download(&self, show_name: &str, output_path: &Path, dry_run: bool) -> Result<bool> {
        tracing::info!("[Themes.moe] Starting search for: {}", show_name);

        let Some(media_url) = self.search_anime(show_name).await? else {
            tracing::info!("[Themes.moe] No theme found for: {}", show_name);
            return Ok(false);
        };

        if dry_run {
            tracing::info!("[Themes.moe] Dry run - would download from: {}", media_url);
            return Ok(true);
        }

        self.download_media(&media_url, output_path).await
    }

    fn source_name(&self) -> &'static str {
        "Themes.moe"
    }
}
