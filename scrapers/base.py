"""Abstract base class for theme scrapers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import logging
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
        self.logger = logging.getLogger(self.__class__.__name__)

    def _log_debug(self, message: str) -> None:
        """
        Log a debug message if verbose mode is enabled.

        Args:
            message: Debug message to log
        """
        if self.verbose and self.console:
            self.console.print(f"    [dim]{message}[/dim]")

    def _log_error(self, message: str, exc_info: bool = False) -> None:
        """
        Log an error message to the error log file.

        Args:
            message: Error message to log
            exc_info: If True, include exception traceback
        """
        self.logger.error(message, exc_info=exc_info)

    def _log_info(self, message: str) -> None:
        """
        Log an info message to the log file.

        Args:
            message: Info message to log
        """
        self.logger.info(message)

    def _log_warning(self, message: str) -> None:
        """
        Log a warning message to the log file.

        Args:
            message: Warning message to log
        """
        self.logger.warning(message)

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

    @abstractmethod
    def get_source_name(self) -> str:
        """
        Return human-readable name of this source.

        Returns:
            String identifier for this scraper source
        """
