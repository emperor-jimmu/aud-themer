"""AnimeThemes.moe API scraper implementation."""

import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

from scrapers.base import ThemeScraper
from core.utils import retry_with_backoff


class AnimeThemesScraper(ThemeScraper):
    """Scraper for AnimeThemes.moe API."""

    BASE_URL = "https://api.animethemes.moe"
    TIMEOUT = 30.0

    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """
        Search for and download a theme song from AnimeThemes.moe.

        Args:
            show_name: Name of the anime
            output_path: Full path where theme file should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        try:
            # Strip year from show name (e.g., "Show Name (2020)" -> "Show Name")
            import re
            clean_name = re.sub(r'\s*\(\d{4}\)\s*$', '', show_name).strip()
            
            self._log_debug(f"Searching AnimeThemes API for: {clean_name}")

            # Search for anime
            anime_data = self._search_anime(clean_name)
            if not anime_data:
                self._log_debug("No anime found in API response")
                return False

            anime_name = anime_data.get("name", "Unknown")
            self._log_debug(f"Found anime: {anime_name}")

            # Find best theme (prefer OP1)
            video_url = self._find_best_theme(anime_data)
            if not video_url:
                self._log_debug("No theme video URL found")
                return False

            self._log_debug(f"Selected video URL: {video_url}")

            # Download video to temp file
            temp_video = output_path.parent / f"temp_{output_path.stem}.webm"
            self._log_debug(f"Downloading video to: {temp_video}")

            if not self._download_video(video_url, temp_video):
                self._log_debug("Video download failed")
                return False

            self._log_debug("Extracting audio with FFmpeg")

            # Extract audio using FFmpeg
            success = self._extract_audio(temp_video, output_path)

            # Cleanup temp file
            if temp_video.exists():
                temp_video.unlink()

            if success:
                self._log_debug(f"Audio extraction successful: {output_path}")
            else:
                self._log_debug("Audio extraction failed")

            return success

        except Exception as e:
            self._log_error(f"Exception in search_and_download: {str(e)}", exc_info=True)
            self._log_debug(f"Exception: {str(e)}")
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
        max_attempts=3,
        initial_delay=0.0,
        backoff_factor=2.0,
        exceptions=(httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout)
    )
    def _search_anime_with_retry(self, show_name: str) -> Optional[Dict[str, Any]]:
        """
        Internal method with retry logic for network timeouts.

        Args:
            show_name: Name of the anime to search for

        Returns:
            Anime data dictionary if found, None otherwise
        """
        with httpx.Client(timeout=self.TIMEOUT) as client:
            response = client.get(
                f"{self.BASE_URL}/search",
                params={
                    "q": show_name,
                    "include[anime]": "animethemes.animethemeentries.videos"
                }
            )

            self._log_debug(f"API response status: {response.status_code}")

            if response.status_code != 200:
                return None

            data = response.json()

            # Handle case where API returns a list instead of dict
            if isinstance(data, list):
                self._log_debug("API returned a list instead of dict, no results")
                return None

            anime_list = data.get("search", {}).get("anime", [])

            if self.verbose:
                anime_count = len(anime_list)
                self._log_debug(f"API returned {anime_count} anime results")

            if not anime_list:
                return None

            # Filter out non-dict items (API sometimes returns mixed types)
            anime_list = [a for a in anime_list if isinstance(a, dict)]

            if not anime_list:
                return None

            # Find best match by name similarity
            best_match = max(
                anime_list,
                key=lambda a: SequenceMatcher(
                    None,
                    show_name.lower(),
                    a.get("name", "").lower()
                ).ratio()
            )

            return best_match

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
        max_attempts=3,
        initial_delay=0.0,
        backoff_factor=2.0,
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
            with httpx.stream("GET", url, timeout=60.0) as response:
                if response.status_code != 200:
                    return False

                with open(output_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

                return True
        except Exception:
            return False

    def _extract_audio(self, video_path: Path, audio_path: Path) -> bool:
        """
        Extract audio from video using FFmpeg.

        Args:
            video_path: Path to input video file
            audio_path: Path where audio file should be saved

        Returns:
            True if extraction succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-i", str(video_path),
                    "-vn",  # No video
                    "-acodec", "libmp3lame",
                    "-b:a", "320k",
                    "-y",  # Overwrite
                    str(audio_path)
                ],
                capture_output=True,
                timeout=60,
                check=False
            )

            if result.returncode != 0:
                if self.verbose:
                    self._log_debug(f"FFmpeg stderr: {result.stderr.decode()}")
                return False

            # Validate file size
            if audio_path.stat().st_size < 500_000:
                self._log_debug(f"File too small: {audio_path.stat().st_size} bytes")
                audio_path.unlink()
                return False

            return True

        except Exception as e:
            self._log_debug(f"FFmpeg exception: {str(e)}")
            return False

    def get_source_name(self) -> str:
        """
        Return human-readable name of this source.

        Returns:
            String identifier for this scraper source
        """
        return "AnimeThemes"
