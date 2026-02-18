use async_trait::async_trait;
use std::path::Path;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use anyhow::{Result, Context};
use tokio::fs;
use tokio::io::AsyncWriteExt;

use super::ThemeScraper;
use crate::config::Config;
use crate::ffmpeg::convert_audio;
use crate::retry::retry_with_backoff;

const API_BASE_URL: &str = "https://api.animethemes.moe";

#[derive(Debug, Deserialize, Serialize, Clone)]
struct AnimeThemesResponse {
    anime: Vec<Anime>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct Anime {
    pub name: String,
    #[serde(rename = "animethemes")]
    pub anime_themes: Vec<AnimeTheme>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct AnimeTheme {
    #[serde(rename = "type")]
    pub theme_type: String,
    pub slug: String,
    #[serde(rename = "animethemeentries")]
    pub entries: Vec<ThemeEntry>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ThemeEntry {
    pub videos: Vec<Video>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct Video {
    pub link: String,
}

pub struct AnimeThemesScraper {
    client: Client,
}

impl AnimeThemesScraper {
    /// Create a new `AnimeThemesScraper` instance
    ///
    /// # Panics
    ///
    /// Panics if the HTTP client cannot be built (e.g., TLS backend issues).
    #[must_use]
    pub fn new() -> Self {
        Self {
            client: Client::builder()
                .timeout(std::time::Duration::from_secs(Config::DEFAULT_TIMEOUT_SEC))
                .build()
                .expect("Failed to build HTTP client"),
        }
    }

    /// Select the best matching anime from search results
    #[must_use]
    pub fn select_best_match<'a>(anime_list: &'a [Anime], query: &str) -> Option<&'a Anime> {
        if anime_list.is_empty() {
            return None;
        }

        let query_lower = query.to_lowercase();
        anime_list.iter()
            .max_by(|a, b| {
                let score_a = strsim::jaro_winkler(&a.name.to_lowercase(), &query_lower);
                let score_b = strsim::jaro_winkler(&b.name.to_lowercase(), &query_lower);
                score_a.partial_cmp(&score_b).unwrap_or(std::cmp::Ordering::Equal)
            })
    }

    /// Select the best theme based on priority: OP1 > OP > first available
    #[must_use]
    pub fn select_best_theme(themes: &[AnimeTheme]) -> Option<&AnimeTheme> {
        if themes.is_empty() {
            return None;
        }

        // Priority 1: Look for OP1
        if let Some(theme) = themes.iter().find(|t| t.slug.to_uppercase() == "OP1") {
            return Some(theme);
        }

        // Priority 2: Look for any OP
        if let Some(theme) = themes.iter().find(|t| t.theme_type.to_uppercase() == "OP") {
            return Some(theme);
        }

        // Priority 3: Return first theme
        Some(&themes[0])
    }

    /// Extract video URL from theme
    fn extract_video_url(theme: &AnimeTheme) -> Option<String> {
        theme.entries.first()
            .and_then(|entry| entry.videos.first())
            .map(|video| video.link.clone())
    }

    async fn search_anime(&self, show_name: &str) -> Result<Option<Anime>> {
        let url = format!("{}/anime?filter[name]={}&include=animethemes.animethemeentries.videos", 
            API_BASE_URL, 
            urlencoding::encode(show_name)
        );

        tracing::info!("[AnimeThemes] API request: {}", url);

        let response = retry_with_backoff(
            Config::MAX_RETRY_ATTEMPTS,
            Config::RETRY_BACKOFF_FACTOR,
            || async {
                self.client.get(&url)
                    .send()
                    .await
                    .context("Failed to send request to AnimeThemes API")
            }
        ).await?;

        let status = response.status();
        tracing::info!("[AnimeThemes] API response status: {}", status);

        if !status.is_success() {
            tracing::warn!("[AnimeThemes] API returned non-success status: {}", status);
            return Ok(None);
        }

        let data: AnimeThemesResponse = response.json().await
            .context("Failed to parse AnimeThemes API response")?;

        tracing::info!("[AnimeThemes] Found {} anime results", data.anime.len());

        let best_match = Self::select_best_match(&data.anime, show_name);
        
        if let Some(anime) = best_match {
            tracing::info!("[AnimeThemes] Best match: {} (with {} themes)", anime.name, anime.anime_themes.len());
        } else {
            tracing::info!("[AnimeThemes] No matching anime found for: {}", show_name);
        }

        Ok(best_match.cloned())
    }

    async fn download_video(&self, url: &str, output_path: &Path) -> Result<()> {
        tracing::info!("[AnimeThemes] Downloading video from: {}", url);
        
        let response = self.client.get(url)
            .timeout(std::time::Duration::from_secs(Config::DOWNLOAD_TIMEOUT_SEC))
            .send()
            .await
            .context("Failed to download video")?;

        let status = response.status();
        tracing::info!("[AnimeThemes] Download response status: {}", status);

        if !status.is_success() {
            tracing::error!("[AnimeThemes] Download failed with status: {}", status);
            anyhow::bail!("Failed to download video: HTTP {}", status);
        }

        let bytes = response.bytes().await
            .context("Failed to read video bytes")?;

        tracing::info!("[AnimeThemes] Downloaded {} bytes", bytes.len());

        let mut file = fs::File::create(output_path).await
            .context("Failed to create output file")?;

        file.write_all(&bytes).await
            .context("Failed to write video file")?;

        tracing::info!("[AnimeThemes] Video saved to: {}", output_path.display());
        Ok(())
    }
}

impl Default for AnimeThemesScraper {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ThemeScraper for AnimeThemesScraper {
    async fn search_and_download(&self, show_name: &str, output_path: &Path) -> Result<bool> {
        tracing::info!("[AnimeThemes] Starting search for: {}", show_name);
        
        // Search for anime
        let Some(anime) = self.search_anime(show_name).await? else {
            tracing::info!("[AnimeThemes] No anime found for: {}", show_name);
            return Ok(false);
        };

        // Select best theme
        let Some(theme) = Self::select_best_theme(&anime.anime_themes) else {
            tracing::warn!("[AnimeThemes] No suitable theme found for: {}", anime.name);
            return Ok(false);
        };

        tracing::info!("[AnimeThemes] Selected theme: {} ({})", theme.slug, theme.theme_type);

        // Extract video URL
        let Some(video_url) = Self::extract_video_url(theme) else {
            tracing::warn!("[AnimeThemes] No video URL found for theme: {}", theme.slug);
            return Ok(false);
        };

        tracing::info!("[AnimeThemes] Video URL: {}", video_url);

        // Download video to temporary file
        let temp_video = output_path.with_extension("temp.webm");
        self.download_video(&video_url, &temp_video).await?;

        // Convert to MP3
        tracing::info!("[AnimeThemes] Converting to MP3");
        convert_audio(&temp_video, output_path, Config::AUDIO_BITRATE).await
            .context("Failed to convert video to MP3")?;

        // Clean up temporary file
        let _ = fs::remove_file(&temp_video).await;
        tracing::info!("[AnimeThemes] Successfully downloaded and converted theme");

        Ok(true)
    }

    fn source_name(&self) -> &'static str {
        "AnimeThemes"
    }
}
