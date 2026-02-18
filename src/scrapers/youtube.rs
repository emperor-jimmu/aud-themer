use async_trait::async_trait;
use std::path::Path;
use anyhow::{Result, Context};
use tokio::process::Command;
use serde::{Deserialize, Serialize};

use super::ThemeScraper;
use crate::config::Config;
use crate::utils::sanitize_for_subprocess;

#[derive(Debug, Deserialize, Serialize)]
struct VideoInfo {
    duration: Option<f64>,
    title: Option<String>,
    id: Option<String>,
}

pub struct YouTubeScraper;

impl YouTubeScraper {
    pub fn new() -> Self {
        Self
    }

    /// Generate search query variations for a show
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
    pub fn is_duration_acceptable(duration_secs: f64) -> bool {
        duration_secs <= Config::MAX_VIDEO_DURATION_SEC as f64
    }

    async fn search_youtube(&self, query: &str) -> Result<Option<VideoInfo>> {
        // Sanitize query for subprocess
        let safe_query = sanitize_for_subprocess(query, 200)
            .context("Failed to sanitize search query")?;

        // Use yt-dlp to search and get video info
        let output = Command::new("yt-dlp")
            .arg("--dump-json")
            .arg("--skip-download")
            .arg("--default-search")
            .arg("ytsearch1")
            .arg(&safe_query)
            .output()
            .await
            .context("Failed to execute yt-dlp")?;

        if !output.status.success() {
            return Ok(None);
        }

        let stdout = String::from_utf8_lossy(&output.stdout);
        
        // Parse JSON output
        let video_info: VideoInfo = serde_json::from_str(&stdout)
            .context("Failed to parse yt-dlp JSON output")?;

        Ok(Some(video_info))
    }

    async fn download_audio(&self, video_id: &str, output_path: &Path) -> Result<()> {
        let url = format!("https://www.youtube.com/watch?v={}", video_id);
        
        // Use yt-dlp to download and extract audio as MP3
        let output = Command::new("yt-dlp")
            .arg("--extract-audio")
            .arg("--audio-format")
            .arg("mp3")
            .arg("--audio-quality")
            .arg("0") // Best quality
            .arg("--output")
            .arg(output_path.with_extension("").to_str().unwrap())
            .arg(&url)
            .output()
            .await
            .context("Failed to execute yt-dlp for download")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            anyhow::bail!("yt-dlp download failed: {}", stderr);
        }

        Ok(())
    }
}

impl Default for YouTubeScraper {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ThemeScraper for YouTubeScraper {
    async fn search_and_download(&self, show_name: &str, output_path: &Path) -> Result<bool> {
        let queries = Self::generate_search_queries(show_name);

        for query in queries {
            // Search for video
            let video_info = match self.search_youtube(&query).await? {
                Some(info) => info,
                None => continue,
            };

            // Check duration
            if let Some(duration) = video_info.duration {
                if !Self::is_duration_acceptable(duration) {
                    continue; // Try next query
                }
            }

            // Get video ID
            let video_id = match video_info.id {
                Some(id) => id,
                None => continue,
            };

            // Download audio
            match self.download_audio(&video_id, output_path).await {
                Ok(_) => return Ok(true),
                Err(_) => continue, // Try next query
            }
        }

        // All queries exhausted
        Ok(false)
    }

    fn source_name(&self) -> &str {
        "YouTube"
    }
}
