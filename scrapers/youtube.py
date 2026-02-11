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
        try:
            # Format search query
            query = f"{show_name} full theme song"
            self._log_debug(f"YouTube search query: {query}")
            
            # Configure yt-dlp options
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '160',
                }],
                'outtmpl': str(output_path.with_suffix('')),
                'default_search': 'ytsearch1',  # Search YouTube, limit to first result
                'noplaylist': True,  # Don't download playlists
                'quiet': not self.verbose,
                'no_warnings': not self.verbose,
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
                return False
            
            # Rename if needed (in case output_path already has .mp3)
            if final_path != output_path:
                final_path.rename(output_path)
            
            # Validate file size (>500KB)
            if output_path.stat().st_size < 500_000:
                self._log_debug(f"File too small: {output_path.stat().st_size} bytes")
                output_path.unlink()
                return False
            
            self._log_debug(f"Download successful: {output_path}")
            return True
        except Exception:
            return False
    
    def get_source_name(self) -> str:
        """
        Return human-readable name of this source.
        
        Returns:
            String identifier for this scraper source
        """
        return "YouTube"
