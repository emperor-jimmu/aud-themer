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

            // Create a unique temporary user data dir per process to avoid
            // collisions with any running Chrome instance (exit status 21 on Windows).
            let temp_user_data = std::env::temp_dir().join(format!(
                "audio-theme-downloader-chrome-{}-{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis()
            ));
            if !temp_user_data.exists() {
                std::fs::create_dir_all(&temp_user_data).map_err(|e| {
                    anyhow::anyhow!("Failed to create temp Chrome profile dir: {e}")
                })?;
            }
            tracing::info!("Using temp Chrome profile: {}", temp_user_data.display());

            let mut config_builder = BrowserConfig::builder()
                .user_data_dir(&temp_user_data)
                .new_headless_mode()
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

            let (browser, mut handler) = Browser::launch(config).await.map_err(|e| {
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
        // Strategy: Try system Chrome first, then local .chromium, then download

        // 1. Check if system Chrome/Chromium exists
        if let Some(system_chrome) = Self::find_system_chrome() {
            tracing::info!("Found system Chrome at: {}", system_chrome.display());
            return Ok(Some(system_chrome));
        }

        // 2. Check for already-downloaded Chromium next to the executable
        //    (handles running from target/release or installed location)
        let exe_chromium = Self::find_local_chromium();
        if let Some(local_chrome) = exe_chromium {
            tracing::info!("Found local Chromium at: {}", local_chrome.display());
            return Ok(Some(local_chrome));
        }

        tracing::info!("No system or local Chrome found, attempting to download Chromium...");

        // 3. Download as fallback
        let download_dir = std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.join(".chromium")))
            .unwrap_or_else(|| {
                std::env::current_dir()
                    .unwrap_or_default()
                    .join(".chromium")
            });

        // Create download directory if it doesn't exist
        if !download_dir.exists() {
            tokio::fs::create_dir_all(&download_dir).await?;
        }

        let fetcher = BrowserFetcher::new(
            BrowserFetcherOptions::builder()
                .with_path(&download_dir)
                .build()
                .map_err(|e| anyhow::anyhow!("Failed to create browser fetcher: {e}"))?,
        );

        match fetcher.fetch().await {
            Ok(info) => {
                tracing::info!("Chromium available at: {}", info.executable_path.display());
                Ok(Some(info.executable_path))
            }
            Err(e) => {
                tracing::warn!(
                    "Failed to fetch Chromium: {}. Browser automation will be unavailable.",
                    e
                );
                Ok(None)
            }
        }
    }

    /// Look for a previously-downloaded Chromium in .chromium directories
    /// relative to the executable or the current working directory.
    fn find_local_chromium() -> Option<PathBuf> {
        let candidate_dirs: Vec<PathBuf> = [
            // Next to the executable (e.g. target/release/.chromium)
            std::env::current_exe()
                .ok()
                .and_then(|p| p.parent().map(|d| d.join(".chromium"))),
            // Current working directory
            std::env::current_dir().ok().map(|d| d.join(".chromium")),
            // Project root (two levels up from target/release)
            std::env::current_exe()
                .ok()
                .and_then(|p| p.parent()?.parent()?.parent().map(|d| d.join(".chromium"))),
        ]
        .into_iter()
        .flatten()
        .collect();

        for dir in candidate_dirs {
            if !dir.exists() {
                continue;
            }
            // Walk one level: .chromium/<revision>/<platform>/chrome.exe
            if let Ok(entries) = std::fs::read_dir(&dir) {
                for entry in entries.flatten() {
                    let revision_dir = entry.path();
                    if !revision_dir.is_dir() {
                        continue;
                    }
                    // Look inside revision dir for chrome-win/chrome.exe (Windows)
                    let chrome_exe = revision_dir.join("chrome-win").join("chrome.exe");
                    if chrome_exe.exists() {
                        return Some(chrome_exe);
                    }
                    // Also check chrome-linux/chrome (Linux)
                    let chrome_linux = revision_dir.join("chrome-linux").join("chrome");
                    if chrome_linux.exists() {
                        return Some(chrome_linux);
                    }
                    // Check if the fetcher put it directly in the revision dir
                    if let Ok(sub_entries) = std::fs::read_dir(&revision_dir) {
                        for sub in sub_entries.flatten() {
                            let sub_path = sub.path();
                            if sub_path.is_dir() {
                                let exe = sub_path.join("chrome.exe");
                                if exe.exists() {
                                    return Some(exe);
                                }
                            }
                        }
                    }
                }
            }
        }

        None
    }

    /// Try to find system-installed Chrome/Chromium
    fn find_system_chrome() -> Option<PathBuf> {
        #[cfg(target_os = "windows")]
        {
            let possible_paths = vec![
                // Chrome stable
                std::env::var("PROGRAMFILES")
                    .ok()
                    .map(|p| PathBuf::from(p).join("Google\\Chrome\\Application\\chrome.exe")),
                std::env::var("PROGRAMFILES(X86)")
                    .ok()
                    .map(|p| PathBuf::from(p).join("Google\\Chrome\\Application\\chrome.exe")),
                std::env::var("LOCALAPPDATA")
                    .ok()
                    .map(|p| PathBuf::from(p).join("Google\\Chrome\\Application\\chrome.exe")),
                // Chromium
                std::env::var("PROGRAMFILES")
                    .ok()
                    .map(|p| PathBuf::from(p).join("Chromium\\Application\\chrome.exe")),
                std::env::var("LOCALAPPDATA")
                    .ok()
                    .map(|p| PathBuf::from(p).join("Chromium\\Application\\chrome.exe")),
                // Edge (Chromium-based)
                std::env::var("PROGRAMFILES(X86)")
                    .ok()
                    .map(|p| PathBuf::from(p).join("Microsoft\\Edge\\Application\\msedge.exe")),
                std::env::var("PROGRAMFILES")
                    .ok()
                    .map(|p| PathBuf::from(p).join("Microsoft\\Edge\\Application\\msedge.exe")),
            ];

            for path in possible_paths.into_iter().flatten() {
                if path.exists() {
                    tracing::debug!("Found Chrome at: {}", path.display());
                    return Some(path);
                }
            }
        }

        #[cfg(target_os = "linux")]
        {
            let candidates = [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "/snap/bin/chromium",
            ];
            for candidate in candidates {
                let path = PathBuf::from(candidate);
                if path.exists() {
                    tracing::debug!("Found Chrome at: {}", path.display());
                    return Some(path);
                }
            }
        }

        #[cfg(target_os = "macos")]
        {
            let candidates = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            ];
            for candidate in candidates {
                let path = PathBuf::from(candidate);
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
