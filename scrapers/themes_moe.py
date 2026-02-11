"""Themes.moe scraper implementation."""

import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from scrapers.base import ThemeScraper
from core.utils import validate_file_size, retry_with_backoff
from core.config import Config
from core.ffmpeg_utils import convert_audio, FFmpegError
from core.logging_utils import StructuredLogger


class ThemesMoeScraper(ThemeScraper):
    """Scraper for Themes.moe using Playwright web automation."""

    BASE_URL = "https://themes.moe/"

    def __init__(self, console=None, verbose=False, timeout=Config.DEFAULT_TIMEOUT_SEC):
        """
        Initialize Themes.moe scraper.

        Args:
            console: Rich console for output
            verbose: Enable verbose logging
            timeout: Network timeout in seconds
        """
        super().__init__(console, verbose)
        self.timeout_ms = int(timeout * 1000)  # Convert to milliseconds
        self.structured_logger = StructuredLogger(__name__)

    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """
        Search for and download a theme song from Themes.moe.

        Args:
            show_name: Name of the anime
            output_path: Full path where theme file should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        start_time = time.time()

        try:
            # Strip year from show name (e.g., "Show Name (2020)" -> "Show Name")
            clean_name = re.sub(r'\s*\(\d{4}\)\s*$', '', show_name).strip()

            self.structured_logger.log_scraper_attempt("Themes.moe", show_name, started=True)
            success = self._search_and_download_with_retry(clean_name, output_path)

            duration = time.time() - start_time
            if success:
                file_size = output_path.stat().st_size
                self.structured_logger.log_download(
                    "Themes.moe", show_name, file_size, duration, str(output_path)
                )
                self.structured_logger.log_scraper_result(
                    "Themes.moe", show_name, True, duration
                )
            else:
                self.structured_logger.log_scraper_result(
                    "Themes.moe", show_name, False, duration, "Search or download failed"
                )

            return success

        except PlaywrightTimeoutError as exc:
            duration = time.time() - start_time
            self._log_error("Playwright timeout error", exc_info=True)
            self.structured_logger.log_scraper_result(
                "Themes.moe", show_name, False, duration, f"Timeout: {str(exc)}"
            )
            return False
        except Exception as exc:
            duration = time.time() - start_time
            self._log_error(f"Exception in search_and_download: {str(exc)}", exc_info=True)
            self.structured_logger.log_scraper_result(
                "Themes.moe", show_name, False, duration, str(exc)
            )
            return False

    @retry_with_backoff(
        max_attempts=Config.MAX_RETRY_ATTEMPTS,
        initial_delay=Config.RETRY_INITIAL_DELAY_SEC,
        backoff_factor=Config.RETRY_BACKOFF_FACTOR,
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
        browser = None
        page = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Enable Playwright tracing in verbose mode
                if self.verbose:
                    page.on("console", lambda msg: self._log_debug(f"Browser console: {msg.text}"))

                self._log_debug(f"Navigating to {self.BASE_URL}")

                # Navigate to homepage
                page.goto(self.BASE_URL, timeout=self.timeout_ms)

                # Click the dropdown button to select "Anime Search" mode
                dropdown_button = page.locator(
                    "button:has-text('MyAnimeList'), button:has-text('Anime Search')"
                )
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
                page.wait_for_load_state("networkidle", timeout=self.timeout_ms)

                # Wait a bit for the page to update
                page.wait_for_timeout(1000)

                # Check for "no results" message
                no_results = page.locator("text=/No anime found|No results available/i")
                if no_results.count() > 0:
                    self._log_debug("No anime found in search results")
                    return False

                # Wait for the results table to appear (with timeout)
                try:
                    page.wait_for_selector("table", timeout=5000)
                except PlaywrightTimeoutError:
                    self._log_debug("Results table did not load in time")
                    return False

                table = page.locator("table")
                if table.count() == 0:
                    self._log_debug("No results table found")
                    return False

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

                    try:
                        success, ffmpeg_error = convert_audio(temp_path, output_path)

                        if not success:
                            error_msg = str(ffmpeg_error) if ffmpeg_error else "Unknown error"
                            self._log_error(
                                f"FFmpeg conversion failed: {error_msg}",
                                exc_info=False
                            )
                            if self.verbose:
                                self._log_debug(f"FFmpeg error: {error_msg}")
                            return False

                    finally:
                        # Clean up temp file
                        if temp_path.exists():
                            try:
                                temp_path.unlink()
                            except OSError:
                                pass

                # Validate file size
                if not validate_file_size(output_path, Config.MIN_FILE_SIZE_BYTES):
                    self._log_debug(f"File too small: {output_path.stat().st_size} bytes")
                    output_path.unlink()
                    return False

                self._log_debug(f"Download successful: {output_path}")
                return True

        finally:
            # Ensure browser is always closed
            if page:
                try:
                    page.close()
                except Exception:
                    pass
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass

            # Rate limiting delay
            import random
            time.sleep(random.uniform(
                Config.RATE_LIMIT_MIN_DELAY_SEC,
                Config.RATE_LIMIT_MAX_DELAY_SEC
            ))

    def get_source_name(self) -> str:
        """
        Return human-readable name of this source.

        Returns:
            String identifier for this scraper source
        """
        return "Themes.moe"
