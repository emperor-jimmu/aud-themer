"""TelevisionTunes.com scraper implementation."""

import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
from scrapers.base import ThemeScraper
from core.utils import validate_file_size, retry_with_backoff


class TelevisionTunesScraper(ThemeScraper):
    """Scraper for TelevisionTunes.com using Playwright web automation."""
    
    BASE_URL = "https://www.televisiontunes.com/"
    TIMEOUT = 30000  # 30 seconds in milliseconds
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """
        Search for and download a theme song from TelevisionTunes.
        
        Args:
            show_name: Name of the TV show
            output_path: Full path where theme file should be saved
            
        Returns:
            True if download succeeded, False otherwise
        """
        try:
            return self._search_and_download_with_retry(show_name, output_path)
        except PlaywrightTimeoutError:
            return False
        except Exception:
            return False
    
    @retry_with_backoff(
        max_attempts=3,
        initial_delay=0.0,
        backoff_factor=2.0,
        exceptions=(PlaywrightTimeoutError,)
    )
    def _search_and_download_with_retry(self, show_name: str, output_path: Path) -> bool:
        """
        Internal method with retry logic for network timeouts.
        
        Args:
            show_name: Name of the TV show
            output_path: Full path where theme file should be saved
            
        Returns:
            True if download succeeded, False otherwise
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Enable Playwright tracing in verbose mode
            if self.verbose:
                page.on("console", lambda msg: self._log_debug(f"Browser console: {msg.text}"))
            
            try:
                self._log_debug(f"Navigating to {self.BASE_URL}")
                
                # Navigate to homepage
                page.goto(self.BASE_URL, timeout=self.TIMEOUT)
                
                self._log_debug(f"Searching for: {show_name}")
                
                # Locate and fill search field
                search_input = page.locator("#search_field")
                search_input.fill(show_name)
                search_input.press("Enter")
                
                # Wait for results to load
                page.wait_for_load_state("networkidle", timeout=self.TIMEOUT)
                
                # Find best matching result
                result = self._find_best_match(page, show_name)
                if not result:
                    self._log_debug("No matching results found")
                    return False
                
                self._log_debug("Found matching result, navigating to song page")
                
                # Navigate to song page
                result.click()
                page.wait_for_load_state("networkidle", timeout=self.TIMEOUT)
                
                # Locate download link
                download_link = page.locator("a[href$='.mp3']").first
                if download_link.count() == 0:
                    self._log_debug("No download link found on page")
                    return False
                
                self._log_debug("Downloading theme file")
                
                # Download file
                with page.expect_download(timeout=self.TIMEOUT) as download_info:
                    download_link.click()
                download = download_info.value
                download.save_as(str(output_path))
                
                # Validate file size
                if not validate_file_size(output_path):
                    self._log_debug(f"File too small: {output_path.stat().st_size} bytes")
                    output_path.unlink()
                    return False
                
                self._log_debug(f"Download successful: {output_path}")
                return True
                
            finally:
                browser.close()
                # Rate limiting delay
                time.sleep(random.uniform(1, 3))
    
    def _find_best_match(self, page: Page, show_name: str):
        """
        Find best matching result using exact match or first result.
        
        Args:
            page: Playwright page object with search results
            show_name: Name of the show to match
            
        Returns:
            Locator for the best matching result, or None if no results
        """
        results = page.locator(".result-item")
        count = results.count()
        
        if count == 0:
            return None
        
        # Try exact match first
        show_name_lower = show_name.lower()
        for i in range(count):
            result = results.nth(i)
            text = result.text_content()
            if text and show_name_lower in text.lower():
                return result
        
        # Fall back to first result
        return results.first
    
    def get_source_name(self) -> str:
        """
        Return human-readable name of this source.
        
        Returns:
            String identifier for this scraper source
        """
        return "TelevisionTunes"
