"""Themes.moe scraper implementation."""

import subprocess
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from scrapers.base import ThemeScraper
from core.utils import validate_file_size, retry_with_backoff


class ThemesMoeScraper(ThemeScraper):
    """Scraper for Themes.moe using Playwright web automation."""

    BASE_URL = "https://themes.moe/"
    TIMEOUT = 30000  # 30 seconds in milliseconds

    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """
        Search for and download a theme song from Themes.moe.

        Args:
            show_name: Name of the anime
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
            show_name: Name of the anime
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

                # Click the dropdown button to select "Anime Search" mode
                dropdown_button = page.locator("button:has-text('MyAnimeList'), button:has-text('Anime Search')")
                if dropdown_button.count() == 0:
                    self._log_debug("No search dropdown found on page")
                    return False

                # If button shows "MyAnimeList", click to open dropdown
                if "MyAnimeList" in dropdown_button.first.text_content():
                    dropdown_button.first.click()
                    page.wait_for_timeout(500)  # Wait for dropdown to appear

                    # Click "Anime Search" option
                    anime_search_option = page.locator("text='Anime Search'")
                    if anime_search_option.count() == 0:
                        self._log_debug("Anime Search option not found in dropdown")
                        return False
                    anime_search_option.click()
                    page.wait_for_timeout(500)

                self._log_debug(f"Searching for: {show_name}")

                # Find and fill the search combobox
                search_input = page.locator("role=combobox")
                if search_input.count() == 0:
                    self._log_debug("No search combobox found on page")
                    return False

                # Perform search
                search_input.first.fill(show_name)
                search_input.first.press("Enter")
                page.wait_for_load_state("networkidle", timeout=self.TIMEOUT)

                # Find the first OP (opening) link in the results table
                # Look for links with text "OP1" or "OP" in the table
                op_link = page.locator("table a:has-text('OP1'), table a:has-text('OP')")
                if op_link.count() == 0:
                    self._log_debug("No opening theme found in search results")
                    return False

                # Get the media URL from the first OP link
                media_url = op_link.first.get_attribute("href")
                if not media_url:
                    self._log_debug("No media URL found in OP link")
                    return False

                self._log_debug(f"Found media URL: {media_url}")

                # Download media
                response = page.request.get(media_url)
                if response.status != 200:
                    self._log_debug(f"Media download failed with status: {response.status}")
                    return False

                # Save file
                with open(output_path, "wb") as f:
                    f.write(response.body())

                # If video, extract audio
                if media_url.endswith(('.mp4', '.webm')):
                    self._log_debug("Extracting audio from video with FFmpeg")
                    temp_path = output_path.with_suffix('.temp')
                    output_path.rename(temp_path)

                    result = subprocess.run(
                        [
                            "ffmpeg",
                            "-i", str(temp_path),
                            "-vn",
                            "-acodec", "libmp3lame",
                            "-b:a", "320k",
                            "-y",
                            str(output_path)
                        ],
                        capture_output=True,
                        timeout=60,
                        check=False
                    )

                    temp_path.unlink()

                    if result.returncode != 0:
                        if self.verbose:
                            self._log_debug(f"FFmpeg stderr: {result.stderr.decode()}")
                        return False

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

    def get_source_name(self) -> str:
        """
        Return human-readable name of this source.

        Returns:
            String identifier for this scraper source
        """
        return "Themes.moe"
