use anyhow::{Context, Result};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::path::Path;
use tokio::process::Command;

use super::ThemeScraper;
use crate::config::Config;
use crate::utils::sanitize_show_name_for_search;
use crate::utils::sanitize_for_subprocess;

#[derive(Debug, Deserialize, Serialize)]
struct VideoInfo {
    duration: Option<f64>,
    title: Option<String>,
    id: Option<String>,
}

pub struct YouTubeScraper {
    cookies_from_browser: Option<String>,
}

impl YouTubeScraper {
    /// Create a new `YouTubeScraper` instance
    #[must_use]
    pub fn new() -> Self {
        Self { cookies_from_browser: None }
    }

    /// Create a new `YouTubeScraper` with browser cookie extraction
    #[must_use]
    pub fn with_cookies_from_browser(browser: Option<String>) -> Self {
        Self { cookies_from_browser: browser }
    }

    /// Generate search query variations for a show
    #[must_use]
    pub fn generate_search_queries(show_name: &str) -> Vec<String> {
        vec![
            format!("{} theme song", show_name),
            format!("{} opening theme", show_name),
            format!("{} intro theme", show_name),
            format!("{} main theme", show_name),
            format!("{} title sequence", show_name),
            format!("{} op theme", show_name),
        ]
    }

    /// Check if video duration is acceptable (≤ 600 seconds)
    #[must_use]
    pub fn is_duration_acceptable(duration_secs: f64) -> bool {
        duration_secs <= Config::MAX_VIDEO_DURATION_SEC as f64
    }

    async fn search_youtube(&self, query: &str) -> Result<Option<VideoInfo>> {
        tracing::info!("[YouTube] Searching for: {}", query);

        // Sanitize query for subprocess
        let safe_query =
            sanitize_for_subprocess(query, 200).context("Failed to sanitize search query")?;

        // Use yt-dlp to search and get video info
        let mut cmd = Command::new("yt-dlp");
        cmd.arg("--dump-json")
            .arg("--skip-download")
            .arg("--default-search")
            .arg("ytsearch1");

        if let Some(ref browser) = self.cookies_from_browser {
            cmd.arg("--cookies-from-browser").arg(browser);
        }

        let output = cmd
            .arg(&safe_query)
            .output()
            .await
            .context("Failed to execute yt-dlp")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            tracing::warn!("[YouTube] Search failed: {}", stderr);

            // DPAPI decryption failure — Chrome cookies are locked (Chrome may be running).
            // Retrying other queries won't help, so bail early with a clear message.
            if stderr.contains("Failed to decrypt with DPAPI") {
                anyhow::bail!(
                    "yt-dlp cannot decrypt Chrome cookies (DPAPI error). \
                    Close Chrome and retry, or use --cookies-from-browser edge/firefox, \
                    or disable cookies with --no-cookies. \
                    See https://github.com/yt-dlp/yt-dlp/issues/10927"
                );
            }

            return Ok(None);
        }

        let stdout = String::from_utf8_lossy(&output.stdout);

        // Parse JSON output
        let video_info: VideoInfo =
            serde_json::from_str(&stdout).context("Failed to parse yt-dlp JSON output")?;

        if let Some(ref title) = video_info.title {
            tracing::info!("[YouTube] Found video: {}", title);
        }
        if let Some(duration) = video_info.duration {
            tracing::info!("[YouTube] Video duration: {:.1}s", duration);
        }

        Ok(Some(video_info))
    }

    async fn download_audio(&self, video_id: &str, output_path: &Path) -> Result<()> {
        let url = format!("https://www.youtube.com/watch?v={}", video_id);

        tracing::info!("[YouTube] Downloading audio from: {}", url);

        // Use yt-dlp to download and extract audio as MP3
        let mut cmd = Command::new("yt-dlp");
        cmd.arg("--extract-audio")
            .arg("--audio-format")
            .arg("mp3")
            .arg("--audio-quality")
            .arg("0"); // Best quality

        if let Some(ref browser) = self.cookies_from_browser {
            cmd.arg("--cookies-from-browser").arg(browser);
        }

        let output = cmd
            .arg("--output")
            .arg(
                output_path
                    .with_extension("")
                    .to_str()
                    .ok_or_else(|| anyhow::anyhow!("Invalid output path: non-UTF-8 characters"))?,
            )
            .arg(&url)
            .output()
            .await
            .context("Failed to execute yt-dlp for download")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            tracing::error!("[YouTube] Download failed: {}", stderr);
            anyhow::bail!("yt-dlp download failed: {}", stderr);
        }

        tracing::info!(
            "[YouTube] Successfully downloaded to: {}",
            output_path.display()
        );
        Ok(())
    }
}

impl Default for YouTubeScraper {
    fn default() -> Self {
        Self { cookies_from_browser: None }
    }
}

#[async_trait]
impl ThemeScraper for YouTubeScraper {
    async fn search_and_download(&self, show_name: &str, output_path: &Path, dry_run: bool) -> Result<bool> {
        let show_name = &sanitize_show_name_for_search(show_name);
        tracing::info!("[YouTube] Starting search for: {}", show_name);

        let queries = Self::generate_search_queries(show_name);
        tracing::info!("[YouTube] Generated {} search queries", queries.len());

        for (idx, query) in queries.iter().enumerate() {
            tracing::info!(
                "[YouTube] Trying query {}/{}: {}",
                idx + 1,
                queries.len(),
                query
            );

            // Search for video
            let video_info = match self.search_youtube(query).await? {
                Some(info) => info,
                None => {
                    tracing::info!("[YouTube] No results for query: {}", query);
                    continue;
                }
            };

            // Check duration
            if let Some(duration) = video_info.duration
                && !Self::is_duration_acceptable(duration)
            {
                tracing::warn!(
                    "[YouTube] Video duration {:.1}s exceeds maximum {}s, skipping",
                    duration,
                    Config::MAX_VIDEO_DURATION_SEC
                );
                continue; // Try next query
            }

            // Get video ID
            let video_id = match video_info.id {
                Some(id) => id,
                None => {
                    tracing::warn!("[YouTube] Video info missing ID");
                    continue;
                }
            };

            if dry_run {
                let url = format!("https://www.youtube.com/watch?v={}", video_id);
                tracing::info!("[YouTube] Dry run - would download from: {}", url);
                return Ok(true);
            }

            // Download audio
            match self.download_audio(&video_id, output_path).await {
                Ok(_) => {
                    tracing::info!("[YouTube] Successfully downloaded theme");
                    return Ok(true);
                }
                Err(e) => {
                    tracing::error!("[YouTube] Download failed: {}", e);
                    continue; // Try next query
                }
            }
        }

        // All queries exhausted
        tracing::info!("[YouTube] All search queries exhausted, no suitable video found");
        Ok(false)
    }

    fn source_name(&self) -> &'static str {
        "YouTube"
    }
}
