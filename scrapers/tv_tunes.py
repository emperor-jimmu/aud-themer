"""TelevisionTunes.co.uk scraper implementation."""

import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
from scrapers.base import ThemeScraper
from core.utils import validate_file_size, retry_with_backoff


class TelevisionTunesScraper(ThemeScraper):
    """Scraper for TelevisionTunes.co.uk using Playwright web automation."""

    BASE_URL = "https://www.televisiontunes.co.uk/"
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
        except PlaywrightTimeoutError as exc:
            self._log_error(
                f"TelevisionTunes timeout for '{show_name}': {str(exc)}",
                exc_info=True
            )
            return False
        except Exception as exc:
            self._log_error(
                f"TelevisionTunes failed for '{show_name}': {str(exc)}",
                exc_info=True
            )
            return False

    @retry_with_backoff(
        max_attempts=3,
        initial_delay=0.0,
        backoff_factor=2.0,
        exceptions=(PlaywrightTimeoutError,)
    )
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
        browser = None
        try:
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

                    # Strip year from show name for search (e.g., "The Simpsons (1989)" -> "The Simpsons")
                    search_query = show_name.split('(')[0].strip()
                    self._log_debug(f"Searching for: {search_query}")

                    # Locate and fill search field (id="s" on the new site)
                    search_input = page.locator("#s")
                    search_input.fill(search_query)
                    search_input.press("Enter")

                    # Wait for results to load
                    page.wait_for_load_state("networkidle", timeout=self.TIMEOUT)

                    # Find best matching result from search results
                    result = self._find_best_match(page, show_name)
                    if not result:
                        self._log_debug("No matching results found")
                        return False

                    self._log_debug("Found matching result, navigating to song page")

                    # Navigate to song page
                    result.click()
                    page.wait_for_load_state("networkidle", timeout=self.TIMEOUT)

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
                    if response.status != 200:
                        self._log_debug(f"Download failed with status: {response.status}")
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
                            result = subprocess.run(
                                [
                                    "ffmpeg",
                                    "-i", str(temp_wav),
                                    "-vn",  # No video
                                    "-acodec", "libmp3lame",
                                    "-b:a", "320k",
                                    "-y",  # Overwrite
                                    str(output_path)
                                ],
                                capture_output=True,
                                timeout=60
                            )

                            if result.returncode != 0:
                                stderr_output = result.stderr.decode() if result.stderr else "No error output"
                                self._log_error(
                                    f"FFmpeg conversion failed for {temp_wav}: {stderr_output}",
                                    exc_info=False
                                )
                                self._log_debug(f"FFmpeg conversion failed: {stderr_output}")
                                if output_path.exists():
                                    output_path.unlink()
                                return False
                        except subprocess.TimeoutExpired as exc:
                            self._log_error(
                                f"FFmpeg timeout converting {temp_wav}",
                                exc_info=True
                            )
                            self._log_debug(f"FFmpeg timeout: {str(exc)}")
                            if output_path.exists():
                                try:
                                    output_path.unlink()
                                except OSError:
                                    pass
                            return False
                        finally:
                            # Clean up temp file
                            if temp_wav.exists():
                                temp_wav.unlink()

                    # Validate file size
                    if not validate_file_size(output_path):
                        self._log_debug(f"File too small: {output_path.stat().st_size} bytes")
                        output_path.unlink()
                        return False

                    self._log_debug(f"Download successful: {output_path}")
                    return True

                finally:
                    # Ensure browser is closed even if exception occurs
                    if browser:
                        browser.close()
        finally:
            # Rate limiting delay
            time.sleep(random.uniform(1, 3))

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
