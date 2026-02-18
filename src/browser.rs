use anyhow::{Context, Result};
use chromiumoxide::browser::{Browser, BrowserConfig};
use chromiumoxide::fetcher::{BrowserFetcher, BrowserFetcherOptions};
use futures::StreamExt;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::Mutex;

/// Shared browser instance for all chromiumoxide-based scrapers.
/// Avoids port conflicts from launching multiple Chrome processes.
#[derive(Clone)]
pub struct SharedBrowser {
    browser: Arc<Mutex<Option<Browser>>>,
}

impl Drop for SharedBrowser {
    fn drop(&mut self) {
        // Attempt to close the browser gracefully when the last reference is dropped
        if Arc::strong_count(&self.browser) == 1 {
            let browser = Arc::clone(&self.browser);
            tokio::spawn(async move {
                let mut guard = browser.lock().await;
                if let Some(mut browser) = guard.take() {
                    let _ = browser.close().await;
                }
            });
        }
    }
}

impl SharedBrowser {
    /// Create a new shared browser (lazy — Chrome is not launched until first use)
    #[must_use]
    pub fn new() -> Self {
        Self {
            browser: Arc::new(Mutex::new(None)),
        }
    }

    /// Get a reference to the browser, launching it if needed
    pub async fn get(&self) -> Result<Arc<Mutex<Option<Browser>>>> {
        let mut guard = self.browser.lock().await;

        if guard.is_none() {
            tracing::info!("Launching browser instance...");
            
            // Try to find/download Chromium
            let chrome_path = Self::ensure_chromium().await?;
            
            // Create a temporary user data dir so we don't collide with
            // an already-running Chrome session (exit status 21 on Windows).
            let temp_user_data = std::env::temp_dir()
                .join("show-theme-cli-chrome-profile");
            if !temp_user_data.exists() {
                std::fs::create_dir_all(&temp_user_data)
                    .map_err(|e| anyhow::anyhow!("Failed to create temp Chrome profile dir: {e}"))?;
            }
            tracing::info!("Using temp Chrome profile: {}", temp_user_data.display());
            
            let mut config_builder = BrowserConfig::builder()
                .user_data_dir(&temp_user_data)
                .new_headless_mode()
                .no_sandbox()
                .arg("--disable-blink-features=AutomationControlled")
                .arg("--disable-gpu")
                .arg("--disable-extensions")
                .arg("--disable-default-apps")
                .arg("--disable-sync")
                .arg("--no-first-run")
                .arg("--mute-audio");
            
            if let Some(path) = chrome_path {
                tracing::info!("Using Chrome at: {}", path.display());
                config_builder = config_builder.chrome_executable(path);
            }
            
            let config = config_builder
                .build()
                .map_err(|e| anyhow::anyhow!("Failed to build browser config: {e}"))?;

            let (browser, mut handler) = Browser::launch(config)
                .await
                .map_err(|e| {
                    tracing::error!("Browser launch failed: {}", e);
                    anyhow::anyhow!("Failed to launch browser: {e}")
                })?;

            tracing::info!("Browser launched successfully");

            // Silently consume CDP events in the background
            tokio::spawn(async move {
                while let Some(event) = handler.next().await {
                    drop(event);
                }
            });

            *guard = Some(browser);
        }

        drop(guard);
        Ok(Arc::clone(&self.browser))
    }
    
    /// Ensure Chromium is available, downloading if necessary
    async fn ensure_chromium() -> Result<Option<PathBuf>> {
        // Strategy: Try system Chrome first, then download as fallback
        // This avoids the Windows exit status 21 issue with downloaded Chromium
        
        // First, check if system Chrome/Chromium exists
        if let Some(system_chrome) = Self::find_system_chrome() {
            tracing::info!("Found system Chrome at: {}", system_chrome.display());
            return Ok(Some(system_chrome));
        }
        
        tracing::info!("No system Chrome found, attempting to download Chromium...");
        
        // Check if we should download Chromium
        let download_dir = std::env::current_dir()?.join(".chromium");
        
        // Create download directory if it doesn't exist
        if !download_dir.exists() {
            tokio::fs::create_dir_all(&download_dir).await?;
        }
        
        // Check if we already have a downloaded version
        let fetcher = BrowserFetcher::new(
            BrowserFetcherOptions::builder()
                .with_path(&download_dir)
                .build()
                .map_err(|e| anyhow::anyhow!("Failed to create browser fetcher: {e}"))?,
        );
        
        // Try to fetch (will download if not present)
        match fetcher.fetch().await {
            Ok(info) => {
                tracing::info!("Chromium downloaded to: {}", info.executable_path.display());
                Ok(Some(info.executable_path))
            }
            Err(e) => {
                tracing::warn!("Failed to fetch Chromium: {}. Browser automation will be unavailable.", e);
                // Return None to let chromiumoxide try its default behavior
                Ok(None)
            }
        }
    }
    
    /// Try to find system-installed Chrome/Chromium
    fn find_system_chrome() -> Option<PathBuf> {
        // Common Chrome/Chromium installation paths on Windows
        let possible_paths = vec![
            // Chrome stable
            std::env::var("PROGRAMFILES").ok()
                .map(|p| PathBuf::from(p).join("Google\\Chrome\\Application\\chrome.exe")),
            std::env::var("PROGRAMFILES(X86)").ok()
                .map(|p| PathBuf::from(p).join("Google\\Chrome\\Application\\chrome.exe")),
            std::env::var("LOCALAPPDATA").ok()
                .map(|p| PathBuf::from(p).join("Google\\Chrome\\Application\\chrome.exe")),
            
            // Chromium
            std::env::var("PROGRAMFILES").ok()
                .map(|p| PathBuf::from(p).join("Chromium\\Application\\chrome.exe")),
            std::env::var("LOCALAPPDATA").ok()
                .map(|p| PathBuf::from(p).join("Chromium\\Application\\chrome.exe")),
            
            // Edge (Chromium-based)
            std::env::var("PROGRAMFILES(X86)").ok()
                .map(|p| PathBuf::from(p).join("Microsoft\\Edge\\Application\\msedge.exe")),
            std::env::var("PROGRAMFILES").ok()
                .map(|p| PathBuf::from(p).join("Microsoft\\Edge\\Application\\msedge.exe")),
        ];
        
        for path_opt in possible_paths {
            if let Some(path) = path_opt {
                if path.exists() {
                    tracing::debug!("Found Chrome at: {}", path.display());
                    return Some(path);
                }
            }
        }
        
        tracing::debug!("No system Chrome installation found");
        None
    }

    /// Explicitly close the browser instance
    pub async fn close(&self) -> Result<()> {
        let mut guard = self.browser.lock().await;
        if let Some(mut browser) = guard.take() {
            browser.close().await.context("Failed to close browser")?;
        }
        Ok(())
    }
}

impl Default for SharedBrowser {
    fn default() -> Self {
        Self::new()
    }
}
