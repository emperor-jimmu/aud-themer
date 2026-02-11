"""AnimeThemes.moe API scraper implementation."""

import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

from scrapers.base import ThemeScraper
from core.utils import retry_with_backoff
from core.config import Config
from core.ffmpeg_utils import convert_audio, FFmpegError
from core.logging_utils import StructuredLogger
from core.security import sanitize_for_subprocess


class AnimeThemesScraper(ThemeScraper):
    """Scraper for AnimeThemes.moe API."""

    BASE_URL = "https://api.animethemes.moe"

    def __init__(self, console=None, verbose=False, timeout=Config.DEFAULT_TIMEOUT_SEC):
        """
        Initialize AnimeThemes scraper.

        Args:
            console: Rich console for output
            verbose: Enable verbose logging
            timeout: Network timeout in seconds
        """
        super().__init__(console, verbose)
        self.timeout = float(timeout)
        self.structured_logger = StructuredLogger(__name__)

    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """
        Search for and download a theme song from AnimeThemes.moe.

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

            self._log_debug(f"Searching AnimeThemes API for: {clean_name}")
            self.structured_logger.log_scraper_attempt("AnimeThemes", show_name, started=True)

            # Search for anime
            anime_data = self._search_anime(clean_name)
            if not anime_data:
                self._log_debug("No anime found in API response")
                duration = time.time() - start_time
                self.structured_logger.log_scraper_result(
                    "AnimeThemes", show_name, False, duration, "No anime found"
                )
                return False

            anime_name = anime_data.get("name", "Unknown")
            self._log_debug(f"Found anime: {anime_name}")

            # Find best theme (prefer OP1)
            video_url = self._find_best_theme(anime_data)
            if not video_url:
                self._log_debug("No theme video URL found")
                duration = time.time() - start_time
                self.structured_logger.log_scraper_result(
                    "AnimeThemes", show_name, False, duration, "No video URL found"
                )
                return False

            self._log_debug(f"Selected video URL: {video_url}")

            # Download video to temp file
            temp_video = output_path.parent / f"temp_{output_path.stem}.webm"
            self._log_debug(f"Downloading video to: {temp_video}")

            if not self._download_video(video_url, temp_video):
                self._log_debug("Video download failed")
                duration = time.time() - start_time
                self.structured_logger.log_scraper_result(
                    "AnimeThemes", show_name, False, duration, "Video download failed"
                )
                return False

            self._log_debug("Extracting audio with FFmpeg")
            self._log_debug(f"Input video: {temp_video}, size: {temp_video.stat().st_size} bytes")
            self._log_debug(f"Output path: {output_path}")

            # Extract audio using FFmpeg with improved error handling
            success, ffmpeg_error = convert_audio(temp_video, output_path)
            
            self._log_debug(f"FFmpeg conversion completed: success={success}")

            # Cleanup temp file
            if temp_video.exists():
                try:
                    temp_video.unlink()
                except OSError:
                    pass

            duration = time.time() - start_time

            if success:
                # Validate file size
                if output_path.stat().st_size < Config.MIN_FILE_SIZE_BYTES:
                    self._log_debug(
                        f"File too small: {output_path.stat().st_size} bytes "
                        f"(min: {Config.MIN_FILE_SIZE_BYTES})"
                    )
                    if output_path.exists():
                        output_path.unlink()
                    self.structured_logger.log_scraper_result(
                        "AnimeThemes", show_name, False, duration, "File too small"
                    )
                    return False
                
                self._log_debug(f"Audio extraction successful: {output_path}")
                file_size = output_path.stat().st_size
                self.structured_logger.log_download(
                    "AnimeThemes", show_name, file_size, duration, str(output_path)
                )
                self.structured_logger.log_scraper_result(
                    "AnimeThemes", show_name, True, duration
                )
            else:
                error_msg = str(ffmpeg_error) if ffmpeg_error else "Unknown error"
                self._log_debug(f"Audio extraction failed: {error_msg}")
                self.structured_logger.log_scraper_result(
                    "AnimeThemes", show_name, False, duration, error_msg
                )

            return success

        except Exception as exc:
            duration = time.time() - start_time
            self._log_error(
                f"AnimeThemes search_and_download failed for '{show_name}': {str(exc)}",
                exc_info=True
            )
            self._log_debug(f"Exception: {str(exc)}")
            self.structured_logger.log_scraper_result(
                "AnimeThemes", show_name, False, duration, str(exc)
            )
            return False

    def _search_anime(self, show_name: str) -> Optional[Dict[str, Any]]:
        """
        Search AnimeThemes API for matching anime.

        Args:
            show_name: Name of the anime to search for

        Returns:
            Anime data dictionary if found, None otherwise
        """
        return self._search_anime_with_retry(show_name)

    @retry_with_backoff(
        max_attempts=Config.MAX_RETRY_ATTEMPTS,
        initial_delay=Config.RETRY_INITIAL_DELAY_SEC,
        backoff_factor=Config.RETRY_BACKOFF_FACTOR,
        exceptions=(httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout)
    )
    @retry_with_backoff(
        max_attempts=Config.MAX_RETRY_ATTEMPTS,
        initial_delay=Config.RETRY_INITIAL_DELAY_SEC,
        backoff_factor=Config.RETRY_BACKOFF_FACTOR,
        exceptions=(httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout)
    )
    def _search_anime_with_retry(self, show_name: str) -> Optional[Dict[str, Any]]:
        """
        Internal method with retry logic for network timeouts.
        Uses the search endpoint which handles both English and Japanese names,
        as well as alternative titles.

        Args:
            show_name: Name of the anime to search for

        Returns:
            Anime data dictionary if found, None otherwise
        """
        with httpx.Client(timeout=self.timeout) as client:
            # Use the search endpoint which handles alternative titles
            response = client.get(
                f"{self.BASE_URL}/search",
                params={
                    "q": show_name,
                    "fields[search]": "anime"
                }
            )

            self._log_debug(f"API response status: {response.status_code}")
            self.logger.info(
                f"AnimeThemes API request for '{show_name}' - Status: {response.status_code}"
            )

            if response.status_code != 200:
                self.logger.warning(
                    f"AnimeThemes API returned non-200 status: {response.status_code}"
                )
                return None

            data = response.json()

            # Handle case where API returns unexpected data structure
            if not isinstance(data, dict):
                self._log_debug(f"API returned unexpected type: {type(data).__name__}")
                return None

            # Get anime list from search results
            search_data = data.get("search", {})
            anime_list = search_data.get("anime", [])

            if self.verbose:
                anime_count = len(anime_list) if isinstance(anime_list, list) else 0
                self._log_debug(f"API returned {anime_count} anime results")

            if not anime_list or not isinstance(anime_list, list):
                return None

            # Filter out non-dict items (API sometimes returns mixed types)
            anime_list = [a for a in anime_list if isinstance(a, dict)]

            if not anime_list:
                return None

            # The search endpoint handles alternative titles internally
            # and returns results sorted by relevance. For most queries,
            # the first result is the best match.
            best_match = anime_list[0]
            
            if self.verbose:
                match_name = best_match.get("name", "Unknown")
                self._log_debug(f"Selected best match: {match_name}")

            # Now fetch the full anime data with themes included
            anime_slug = best_match.get("slug")
            if not anime_slug:
                return None

            self._log_debug(f"Fetching full data for anime slug: {anime_slug}")

            # Fetch full anime data with themes
            full_response = client.get(
                f"{self.BASE_URL}/anime/{anime_slug}",
                params={
                    "include": "animethemes.animethemeentries.videos"
                }
            )

            if full_response.status_code != 200:
                self.logger.warning(
                    f"Failed to fetch full anime data: {full_response.status_code}"
                )
                return None

            full_data = full_response.json()
            anime_data = full_data.get("anime")

            return anime_data if isinstance(anime_data, dict) else None


    def _find_best_theme(self, anime_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract best theme video URL (prefer OP1).

        Args:
            anime_data: Anime data dictionary from API

        Returns:
            Video URL if found, None otherwise
        """
        themes = anime_data.get("animethemes", [])

        if not themes:
            return None

        # Collect all OP1 themes
        op1_themes = [t for t in themes if t.get("type") == "OP" and t.get("sequence") == 1]
        if op1_themes:
            return self._extract_video_url(op1_themes[0])

        # Collect all OP themes (any sequence)
        op_themes = [t for t in themes if t.get("type") == "OP"]
        if op_themes:
            return self._extract_video_url(op_themes[0])

        # Fall back to first theme
        return self._extract_video_url(themes[0])

    def _extract_video_url(self, theme: Dict[str, Any]) -> Optional[str]:
        """
        Extract video URL from theme data.

        Args:
            theme: Theme data dictionary

        Returns:
            Video URL if found, None otherwise
        """
        entries = theme.get("animethemeentries", [])
        if not entries:
            return None

        videos = entries[0].get("videos", [])
        if not videos:
            return None

        return videos[0].get("link")

    def _download_video(self, url: str, output_path: Path) -> bool:
        """
        Download video file from URL.

        Args:
            url: Video URL to download
            output_path: Path where video should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        return self._download_video_with_retry(url, output_path)

    @retry_with_backoff(
        max_attempts=Config.MAX_RETRY_ATTEMPTS,
        initial_delay=Config.RETRY_INITIAL_DELAY_SEC,
        backoff_factor=Config.RETRY_BACKOFF_FACTOR,
        exceptions=(httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout)
    )
    def _download_video_with_retry(self, url: str, output_path: Path) -> bool:
        """
        Internal method with retry logic for network timeouts.

        Args:
            url: Video URL to download
            output_path: Path where video should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        try:
            with httpx.stream("GET", url, timeout=Config.DOWNLOAD_TIMEOUT_SEC) as response:
                if response.status_code != 200:
                    return False

                with open(output_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

                return True
        except Exception as exc:
            self._log_error(
                f"Video download failed from {url}: {str(exc)}",
                exc_info=True
            )
            return False

    def get_source_name(self) -> str:
        """
        Return human-readable name of this source.

        Returns:
            String identifier for this scraper source
        """
        return "AnimeThemes"
