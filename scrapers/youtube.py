"""YouTube fallback scraper implementation using yt-dlp."""

import time
from pathlib import Path

import yt_dlp

from scrapers.base import ThemeScraper
from core.utils import retry_with_backoff
from core.config import Config
from core.logging_utils import StructuredLogger


class YoutubeScraper(ThemeScraper):
    """Scraper for YouTube as a fallback source."""

    def __init__(self, console=None, verbose=False):
        """
        Initialize YouTube scraper.

        Args:
            console: Rich console for output
            verbose: Enable verbose logging
        """
        super().__init__(console, verbose)
        self.structured_logger = StructuredLogger(__name__)

    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """
        Search for and download a theme song from YouTube.

        Args:
            show_name: Name of the TV show or anime
            output_path: Full path where theme file should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        start_time = time.time()

        try:
            self.structured_logger.log_scraper_attempt("YouTube", show_name, started=True)
            success = self._search_and_download_with_retry(show_name, output_path)

            duration = time.time() - start_time
            if success:
                file_size = output_path.stat().st_size
                self.structured_logger.log_download(
                    "YouTube", show_name, file_size, duration, str(output_path)
                )
                self.structured_logger.log_scraper_result(
                    "YouTube", show_name, True, duration
                )
            else:
                self.structured_logger.log_scraper_result(
                    "YouTube", show_name, False, duration, "All search queries failed"
                )

            return success

        except Exception as exc:
            duration = time.time() - start_time
            self._log_error(
                f"YouTube failed for '{show_name}': {str(exc)}",
                exc_info=True
            )
            self.structured_logger.log_scraper_result(
                "YouTube", show_name, False, duration, str(exc)
            )
            return False

    def _get_search_queries(self, show_name: str) -> list[str]:
        """
        Generate multiple search query variations for finding theme songs.

        Args:
            show_name: Name of the TV show or anime

        Returns:
            List of search query strings in priority order
        """
        return [
            f"{show_name} theme song",
            f"{show_name} opening theme",
            f"{show_name} intro theme",
            f"{show_name} main theme",
            f"{show_name} title sequence",
            f"{show_name} op theme",
        ]

    @retry_with_backoff(
        max_attempts=Config.MAX_RETRY_ATTEMPTS,
        initial_delay=Config.RETRY_INITIAL_DELAY_SEC,
        backoff_factor=Config.RETRY_BACKOFF_FACTOR,
        exceptions=(yt_dlp.utils.DownloadError,)
    )
    def _search_and_download_with_retry(self, show_name: str, output_path: Path) -> bool:
        """
        Internal method with retry logic for network timeouts.

        Args:
            show_name: Name of the TV show or anime
            output_path: Full path where theme file should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        # Try multiple search query variations
        queries = self._get_search_queries(show_name)

        for query in queries:
            self._log_debug(f"Trying YouTube search query: {query}")

            try:
                # Configure yt-dlp options for info extraction
                info_opts = {
                    'default_search': 'ytsearch1',
                    'noplaylist': True,
                    'quiet': not self.verbose,
                    'no_warnings': not self.verbose,
                }

                # First, extract video info to check duration
                self._log_info(f"YouTube: Extracting video info for query: {query}")
                try:
                    with yt_dlp.YoutubeDL(info_opts) as ydl:
                        info = ydl.extract_info(query, download=False)

                        # Handle search results
                        if 'entries' in info:
                            if not info['entries']:
                                self._log_debug("No results found, trying next query")
                                self._log_info(f"YouTube: No results for query: {query}")
                                continue
                            info = info['entries'][0]

                        duration = info.get('duration', 0)
                        video_title = info.get('title', 'Unknown')
                        self._log_info(f"YouTube: Found video '{video_title}' - Duration: {duration}s")

                        # Skip if video is longer than max duration
                        if duration > Config.MAX_VIDEO_DURATION_SEC:
                            self._log_debug(
                                f"Video too long ({duration}s > {Config.MAX_VIDEO_DURATION_SEC}s), "
                                f"trying next query"
                            )
                            self._log_info(
                                f"YouTube: Video too long ({duration}s), skipping"
                            )
                            continue

                        self._log_debug(f"Video duration: {duration}s (within limit)")
                
                except yt_dlp.utils.DownloadError as exc:
                    error_msg = str(exc)
                    # Check if this is a video unavailability error
                    if 'not available' in error_msg.lower() or 'unavailable' in error_msg.lower():
                        self._log_info(f"YouTube: Video unavailable for query '{query}', trying next query")
                        self._log_debug(f"Video unavailability details: {error_msg}")
                        continue
                    # For other download errors, re-raise to be caught by outer handler
                    raise

                # Configure yt-dlp options for download
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '160',
                    }],
                    'outtmpl': str(output_path.with_suffix('')),
                    'default_search': 'ytsearch1',
                    'noplaylist': True,
                    'quiet': not self.verbose,
                    'no_warnings': not self.verbose,
                    # Enable remote components for JS challenge solving
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android', 'web'],
                            'skip': ['hls', 'dash']
                        }
                    }
                }

                if self.verbose:
                    # Add progress hooks for verbose mode
                    def progress_hook(d):
                        if d['status'] == 'downloading':
                            self._log_debug(f"Downloading: {d.get('_percent_str', 'N/A')}")
                        elif d['status'] == 'finished':
                            self._log_debug("Download finished, processing...")

                    ydl_opts['progress_hooks'] = [progress_hook]

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        self._log_info(f"YouTube: Starting download for query: {query}")
                        ydl.download([query])
                except yt_dlp.utils.DownloadError as exc:
                    error_msg = str(exc)
                    # Check if this is a video unavailability error
                    if 'not available' in error_msg.lower() or 'unavailable' in error_msg.lower():
                        self._log_info(f"YouTube: Video unavailable during download for query '{query}', trying next query")
                        self._log_debug(f"Video unavailability details: {error_msg}")
                        continue
                    # For other download errors, re-raise to be caught by outer handler
                    raise

                # yt-dlp adds .mp3 extension automatically
                final_path = output_path.with_suffix('.mp3')
                if not final_path.exists():
                    self._log_debug("Output file not found after download")
                    self._log_warning("YouTube: Output file not found after download")
                    continue

                # Rename if needed (in case output_path already has .mp3)
                if final_path != output_path:
                    final_path.rename(output_path)

                # Validate file size
                file_size = output_path.stat().st_size
                if file_size < Config.MIN_FILE_SIZE_BYTES:
                    self._log_debug(
                        f"File too small: {file_size} bytes "
                        f"(min: {Config.MIN_FILE_SIZE_BYTES})"
                    )
                    self._log_warning(f"YouTube: File too small ({file_size} bytes), skipping")
                    output_path.unlink()
                    continue

                self._log_debug(f"Download successful: {output_path}")
                self._log_info(f"YouTube: Download successful - Size: {file_size} bytes")
                return True

            except yt_dlp.utils.DownloadError as exc:
                error_msg = str(exc)
                # Check if this is a video unavailability error
                if 'not available' in error_msg.lower() or 'unavailable' in error_msg.lower():
                    self._log_info(f"YouTube: Video unavailable for query '{query}', trying next query")
                    self._log_debug(f"Video unavailability details: {error_msg}")
                else:
                    # For other download errors, log as error
                    self._log_debug(f"Query '{query}' failed: {error_msg}")
                    self._log_error(f"YouTube: Query '{query}' failed: {error_msg}", exc_info=True)
                continue
            except Exception as exc:
                self._log_debug(f"Query '{query}' failed: {str(exc)}")
                self._log_error(f"YouTube: Query '{query}' failed: {str(exc)}", exc_info=True)
                continue

        # All queries failed
        self._log_error(
            f"YouTube download failed for '{show_name}': All search queries exhausted",
            exc_info=False
        )
        return False

    def get_source_name(self) -> str:
        """
        Return human-readable name of this source.

        Returns:
            String identifier for this scraper source
        """
        return "YouTube"
