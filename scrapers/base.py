"""Abstract base class for theme scrapers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from rich.console import Console


class ThemeScraper(ABC):
    """Abstract base class for all theme scrapers."""
    
    def __init__(self, console: Optional[Console] = None, verbose: bool = False):
        """
        Initialize the scraper.
        
        Args:
            console: Rich console for debug output (optional)
            verbose: If True, enable debug logging
        """
        self.console = console
        self.verbose = verbose
    
    def _log_debug(self, message: str) -> None:
        """
        Log a debug message if verbose mode is enabled.
        
        Args:
            message: Debug message to log
        """
        if self.verbose and self.console:
            self.console.print(f"    [dim]{message}[/dim]")
    
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
