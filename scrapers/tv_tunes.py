"""TelevisionTunes.co.uk scraper implementation."""

import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
from scrapers.base import ThemeScraper
from core.utils import validate_file_size, retry_with_backoff
from core.config import Config
from core.ffmpeg_utils import convert_audio, FFmpegError
from core.logging_utils import StructuredLogger
from core.security import sanitize_for_subprocess


class TelevisionTunesScraper(ThemeScraper):
    """Scraper for TelevisionTunes.co.uk using Playwright web automation."""

    BASE_URL = "https://www.televisiontunes.co.uk/"

    def __init__(self, console=None, verbose=False, timeout=Config.DEFAULT_TIMEOUT_SEC):
        """
        Initialize TelevisionTunes scraper.

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
        Search for and download a theme song from TelevisionTunes.

        Args:
            show_name: Name of the TV show
            output_path: Full path where theme file should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        start_time = time.time()

        try:
            self.structured_logger.log_scraper_attempt("TelevisionTunes", show_name, started=True)
            success = self._search_and_download_with_retry(show_name, output_path)

            duration = time.time() - start_time
            if success:
                file_size = output_path.stat().st_size
                self.structured_logger.log_download(
                    "TelevisionTunes", show_name, file_size, duration, str(output_path)
                )
                self.structured_logger.log_scraper_result(
                    "TelevisionTunes", show_name, True, duration
                )
            else:
                self.structured_logger.log_scraper_result(
                    "TelevisionTunes", show_name, False, duration, "Search or download failed"
                )

            return success

        except PlaywrightTimeoutError as exc:
            duration = time.time() - start_time
            self._log_error(
                f"TelevisionTunes timeout for '{show_name}': {str(exc)}",
                exc_info=True
            )
            self.structured_logger.log_scraper_result(
                "TelevisionTunes", show_name, False, duration, f"Timeout: {str(exc)}"
            )
            return False
        except Exception as exc:
            duration = time.time() - start_time
            self._log_error(
                f"TelevisionTunes failed for '{show_name}': {str(exc)}",
                exc_info=True
            )
            self.structured_logger.log_scraper_result(
                "TelevisionTunes", show_name, False, duration, str(exc)
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
            show_name: Name of the TV show
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
                self._log_info(f"TelevisionTunes: Navigating to {self.BASE_URL}")

                # Navigate to homepage
                page.goto(self.BASE_URL, timeout=self.timeout_ms)
                self._log_info("TelevisionTunes: Page loaded successfully")

                # Strip year from show name for search (e.g., "The Simpsons (1989)" -> "The Simpsons")
                search_query = show_name.split('(')[0].strip()
                self._log_debug(f"Searching for: {search_query}")

                # Locate and fill search field (id="s" on the new site)
                search_input = page.locator("#s")
                search_input.fill(search_query)
                search_input.press("Enter")

                # Wait for results to load
                page.wait_for_load_state("networkidle", timeout=self.timeout_ms)

                # Find best matching result from search results
                result = self._find_best_match(page, show_name)
                if not result:
                    self._log_debug("No matching results found")
                    return False

                self._log_debug("Found matching result, navigating to song page")

                # Navigate to song page
                result.click()
                page.wait_for_load_state("networkidle", timeout=self.timeout_ms)

                # Locate download link (looks for .wav or .mp3 files)
                download_link = page.locator("a[href*='/themes/']").first
                if download_link.count() == 0:
                    self._log_debug("No download link found on page")
                    return False

                # Get the download URL
                download_url = download_link.get_attribute("href")
                if not download_url:
                    self._log_debug("Download link has no href attribute")
                    return False

                self._log_debug(f"Downloading theme file from: {download_url}")

                # Download file using page.request instead of clicking
                response = page.request.get(download_url)
                self._log_info(
                    f"TelevisionTunes: Download request - Status: {response.status}, "
                    f"Size: {len(response.body())} bytes"
                )
                
                if response.status != 200:
                    self._log_debug(f"Download failed with status: {response.status}")
                    self._log_warning(f"TelevisionTunes: Download failed - Status: {response.status}")
                    return False

                # Save the file
                with open(output_path, "wb") as f:
                    f.write(response.body())

                # Convert WAV to MP3 if needed
                if download_url.endswith('.wav'):
                    self._log_debug("Converting WAV to MP3")
                    temp_wav = output_path.with_suffix('.wav')
                    output_path.rename(temp_wav)

                    try:
                        success, ffmpeg_error = convert_audio(temp_wav, output_path)

                        if not success:
                            error_msg = str(ffmpeg_error) if ffmpeg_error else "Unknown error"
                            self._log_error(
                                f"FFmpeg conversion failed for {temp_wav}: {error_msg}",
                                exc_info=False
                            )
                            self._log_debug(f"FFmpeg conversion failed: {error_msg}")
                            if output_path.exists():
                                output_path.unlink()
                            return False

                    finally:
                        # Clean up temp file
                        if temp_wav.exists():
                            try:
                                temp_wav.unlink()
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
            time.sleep(random.uniform(
                Config.RATE_LIMIT_MIN_DELAY_SEC,
                Config.RATE_LIMIT_MAX_DELAY_SEC
            ))

    def _find_best_match(self, page: Page, show_name: str):
        """
        Find best matching result from search results list.

        Args:
            page: Playwright page object with search results
            show_name: Name of the show to match

        Returns:
            Locator for the best matching result link, or None if no results
        """
        # Look for list items in the categorylist (search results)
        results = page.locator("ul.categorylist li a")
        count = results.count()

        if count == 0:
            return None

        # Try exact match first (ignoring year in parentheses)
        show_name_lower = show_name.lower()
        # Remove year from search if present (e.g., "The Simpsons (1989)" -> "the simpsons")
        show_name_clean = show_name_lower.split('(')[0].strip()

        for i in range(count):
            result = results.nth(i)
            text = result.text_content()
            if text:
                text_clean = text.lower().strip()
                # Exact match
                if show_name_clean == text_clean:
                    return result

        # Try partial match
        for i in range(count):
            result = results.nth(i)
            text = result.text_content()
            if text and show_name_clean in text.lower():
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
