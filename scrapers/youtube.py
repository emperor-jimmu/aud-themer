"""YouTube fallback scraper implementation using yt-dlp."""

from pathlib import Path

import yt_dlp

from scrapers.base import ThemeScraper


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
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Format search query
                query = f"{show_name} full theme song"
                ydl.download([query])
            
            # yt-dlp adds .mp3 extension automatically
            final_path = output_path.with_suffix('.mp3')
            if not final_path.exists():
                return False
            
            # Rename if needed (in case output_path already has .mp3)
            if final_path != output_path:
                final_path.rename(output_path)
            
            # Validate file size (>500KB)
            if output_path.stat().st_size < 500_000:
                output_path.unlink()
                return False
            
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
