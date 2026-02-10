"""Abstract base class for theme scrapers."""

from abc import ABC, abstractmethod
from pathlib import Path


class ThemeScraper(ABC):
    """Abstract base class for all theme scrapers."""
    
    @abstractmethod
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """
        Search for and download a theme song.
        
        Args:
            show_name: Name of the TV show or anime
            output_path: Full path where theme file should be saved
            
        Returns:
            True if download succeeded, False otherwise
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """
        Return human-readable name of this source.
        
        Returns:
            String identifier for this scraper source
        """
        pass
