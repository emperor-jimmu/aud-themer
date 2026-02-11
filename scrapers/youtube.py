"""YouTube fallback scraper implementation using yt-dlp."""

from pathlib import Path

import yt_dlp

from scrapers.base import ThemeScraper
from core.utils import retry_with_backoff


class YoutubeScraper(ThemeScraper):
    """Scraper for YouTube as a fallback source."""

    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """
        Search for and download a theme song from YouTube.

        Args:
            show_name: Name of the TV show or anime
            output_path: Full path where theme file should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        return self._search_and_download_with_retry(show_name, output_path)

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
        max_attempts=3,
        initial_delay=0.0,
        backoff_factor=2.0,
        exceptions=(yt_dlp.utils.DownloadError,)
    )
    @retry_with_backoff(
        max_attempts=3,
        initial_delay=0.0,
        backoff_factor=2.0,
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
                with yt_dlp.YoutubeDL(info_opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    
                    # Handle search results
                    if 'entries' in info:
                        if not info['entries']:
                            self._log_debug("No results found, trying next query")
                            continue
                        info = info['entries'][0]
                    
                    duration = info.get('duration', 0)
                    
                    # Skip if video is longer than 10 minutes (600 seconds)
                    if duration > 600:
                        self._log_debug(
                            f"Video too long ({duration}s > 600s), trying next query"
                        )
                        continue
                    
                    self._log_debug(f"Video duration: {duration}s (within limit)")

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

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([query])

                # yt-dlp adds .mp3 extension automatically
                final_path = output_path.with_suffix('.mp3')
                if not final_path.exists():
                    self._log_debug("Output file not found after download")
                    continue

                # Rename if needed (in case output_path already has .mp3)
                if final_path != output_path:
                    final_path.rename(output_path)

                # Validate file size (>500KB)
                if output_path.stat().st_size < 500_000:
                    self._log_debug(f"File too small: {output_path.stat().st_size} bytes")
                    output_path.unlink()
                    continue

                self._log_debug(f"Download successful: {output_path}")
                return True
                
            except Exception as exc:
                self._log_debug(f"Query '{query}' failed: {str(exc)}")
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
