use anyhow::{Context, Result};
use chromiumoxide::browser::{Browser, BrowserConfig};
use futures::StreamExt;
use std::sync::Arc;
use tokio::sync::Mutex;

/// Shared browser instance for all chromiumoxide-based scrapers.
/// Avoids port conflicts from launching multiple Chrome processes.
#[derive(Clone)]
pub struct SharedBrowser {
    browser: Arc<Mutex<Option<Browser>>>,
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
            let (browser, mut handler) = Browser::launch(
                BrowserConfig::builder()
                    .arg("--ignore-certificate-errors")
                    .arg("--ignore-ssl-errors")
                    .arg("--disable-blink-features=AutomationControlled")
                    .build()
                    .map_err(|e| anyhow::anyhow!("Failed to build browser config: {e}"))?,
            )
            .await
            .context("Failed to launch browser")?;

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
}

impl Default for SharedBrowser {
    fn default() -> Self {
        Self::new()
    }
}
