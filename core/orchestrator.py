"""Orchestration logic for theme song retrieval."""

import logging
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from scrapers.base import ThemeScraper
from scrapers.tv_tunes import TelevisionTunesScraper
from scrapers.anime_themes import AnimeThemesScraper
from scrapers.themes_moe import ThemesMoeScraper
from scrapers.youtube import YoutubeScraper
from core.config import Config
from core.rate_limiter import RateLimiter
from core.logging_utils import StructuredLogger
from core.utils import get_file_size_formatted, get_audio_duration


class CriticalError(Exception):
    """Exception raised for critical errors that should stop execution."""


class Orchestrator:
    """Orchestrates theme song retrieval across multiple sources."""

    def __init__(
        self,
        console: Console,
        force: bool = False,
        dry_run: bool = False,
        verbose: bool = False,
        timeout: int = Config.DEFAULT_TIMEOUT_SEC
    ):
        """
        Initialize the orchestrator.

        Args:
            console: Rich console for output
            force: If True, overwrite existing theme files
            dry_run: If True, simulate operations without downloading
            verbose: If True, enable debug logging
            timeout: Network timeout in seconds
        """
        self.console = console
        self.force = force
        self.dry_run = dry_run
        self.verbose = verbose
        self.timeout = timeout
        self.scrapers: List[ThemeScraper] = []
        self.logger = logging.getLogger(__name__)
        self.structured_logger = StructuredLogger(__name__)
        self.rate_limiter = RateLimiter()
        self.results = {
            "success": 0,
            "skipped": 0,
            "failed": 0
        }

        # Initialize scrapers in priority order
        self._initialize_default_scrapers()

    def _initialize_default_scrapers(self) -> None:
        """
        Initialize scrapers in priority order.

        Priority order:
        1. TelevisionTunes (best for TV shows)
        2. AnimeThemes (best for anime)
        3. Themes.moe (additional anime source)
        4. YouTube (fallback for everything)
        """
        self.scrapers = [
            TelevisionTunesScraper(self.console, self.verbose, self.timeout),
            AnimeThemesScraper(self.console, self.verbose, self.timeout),
            ThemesMoeScraper(self.console, self.verbose, self.timeout),
            YoutubeScraper(self.console, self.verbose)
        ]

    def add_scraper(self, scraper: ThemeScraper) -> None:
        """
        Add a scraper to the orchestrator.

        Args:
            scraper: ThemeScraper instance to add
        """
        self.scrapers.append(scraper)

    def process_directory(self, input_dir: Path) -> None:
        """
        Process all series folders in the input directory.

        Args:
            input_dir: Root directory containing series folders

        Raises:
            CriticalError: If a critical error occurs that should stop execution
        """
        # Validate input directory
        if not input_dir.exists():
            raise CriticalError(f"Input directory does not exist: {input_dir}")

        if not input_dir.is_dir():
            raise CriticalError(f"Input path is not a directory: {input_dir}")

        self.logger.info(f"Scanning directory: {input_dir}")
        series_folders = self._scan_directory(input_dir)

        if not series_folders:
            self.console.print("[yellow]No series folders found[/]")
            self.logger.warning("No series folders found in input directory")
            return

        total_folders = len(series_folders)
        self.console.print(f"[bold dodger_blue1]Found {total_folders} series folders[/bold dodger_blue1]\n")
        self.logger.info(f"Found {total_folders} series folders to process")

        # Process folders sequentially (simpler and safer than async)
        for index, folder in enumerate(series_folders, start=1):
            self.console.print(f"\n[bold magenta]━━━ Folder {index}/{total_folders} ━━━[/bold magenta]")
            self.logger.info(f"Processing folder {index}/{total_folders}: {folder.name}")
            try:
                self.process_show(folder)
            except CriticalError:
                # Re-raise critical errors to stop execution
                raise
            except Exception as exc:
                # Log non-critical errors and continue processing
                self.logger.error(
                    f"Unexpected error processing {folder.name}: {str(exc)}",
                    exc_info=True
                )
                self.console.print(
                    f"[red]ERROR[/] Unexpected error processing {folder.name}: {str(exc)}"
                )
                if self.verbose:
                    import traceback
                    self.console.print(traceback.format_exc())
                self.results["failed"] += 1

        self.logger.info(
            f"Processing complete - Success: {self.results['success']}, "
            f"Skipped: {self.results['skipped']}, Failed: {self.results['failed']}"
        )
        self.display_summary()


    def _scan_directory(self, input_dir: Path) -> List[Path]:
        """
        Scan directory for series folders.

        Args:
            input_dir: Directory to scan

        Returns:
            List of Path objects for each series folder
        """
        series_folders = []

        try:
            for item in input_dir.iterdir():
                if item.is_dir():
                    series_folders.append(item)
        except PermissionError:
            self.console.print(
                f"[yellow]Warning: Permission denied accessing {input_dir}[/]"
            )
        except OSError as e:
            self.console.print(
                f"[yellow]Warning: Error accessing {input_dir}: {str(e)}[/]"
            )

        return series_folders

    def _extract_show_name(self, folder: Path) -> str:
        """
        Extract show name from folder path.

        Args:
            folder: Path to series folder

        Returns:
            Show name (folder's base name)
        """
        return folder.name

    def _find_existing_theme(self, folder: Path) -> Optional[Path]:
        """
        Check if a theme file already exists in the folder.

        Checks for theme files with extensions from Config.THEME_EXTENSIONS

        Args:
            folder: Path to series folder

        Returns:
            Path to existing theme file, or None if not found
        """
        for ext in Config.THEME_EXTENSIONS:
            theme_file = folder / f"theme{ext}"
            if theme_file.exists():
                return theme_file
        return None


    def process_show(self, folder: Path) -> None:
        """
        Process a single show folder.

        Args:
            folder: Path to series folder

        Raises:
            CriticalError: If a critical error occurs that should stop execution
        """
        show_name = self._extract_show_name(folder)
        theme_file = folder / "theme.mp3"

        # Check for permission errors accessing the folder
        try:
            # Test if we can access the folder
            folder.exists()
            list(folder.iterdir())
        except PermissionError:
            self.console.print(
                f"[dim yellow]⊘ SKIPPED[/dim yellow] {show_name} [dim]- Permission denied[/dim]"
            )
            self.results["skipped"] += 1
            return
        except OSError as exc:
            self.console.print(
                f"[dim yellow]⊘ SKIPPED[/dim yellow] {show_name} [dim]- Cannot access folder: {str(exc)}[/dim]"
            )
            self.results["skipped"] += 1
            return

        # Check if theme already exists
        existing_theme = self._find_existing_theme(folder)

        if existing_theme and not self.force:
            self.console.print(f"[dim yellow]⊘ SKIPPED[/dim yellow] {show_name} [dim]- File exists[/dim]")
            self.logger.info(f"Skipped '{show_name}' - theme file already exists")
            self.results["skipped"] += 1
            return

        if self.dry_run:
            self.console.print(f"[bright_blue]⚡ DRY RUN[/bright_blue] Would process: {show_name}")
            self.logger.info(f"Dry run - would process '{show_name}'")
            return

        # If force mode is enabled and a theme exists, delete it before downloading
        if self.force and existing_theme:
            try:
                existing_theme.unlink()
                if self.verbose:
                    self.console.print(f"  Deleted existing theme: {existing_theme.name}")
                self.logger.info(f"Deleted existing theme for '{show_name}' (force mode)")
            except OSError as exc:
                self.console.print(
                    f"[yellow]Warning: Could not delete existing theme: {str(exc)}[/]"
                )
                self.logger.warning(f"Could not delete existing theme: {str(exc)}")

        # Try each scraper in order (waterfall approach)
        self.console.print(f"\n[bold white]Processing:[/bold white] [dodger_blue1]{show_name}[/dodger_blue1]")

        for scraper in self.scrapers:
            source_name = scraper.get_source_name()
            self.console.print(f"  [dim]Trying[/dim] {source_name}...", end="")
            self.logger.info(f"Attempting source: {source_name} for '{show_name}'")

            # Apply rate limiting before attempting scraper
            self.rate_limiter.wait(source_name)

            try:
                if scraper.search_and_download(show_name, theme_file):
                    self.console.print(f" [bold green]✓[/bold green]")
                    
                    # Get file metadata
                    file_size = get_file_size_formatted(theme_file)
                    duration = get_audio_duration(theme_file)
                    
                    self.console.print(
                        f"[bold green]✓ SUCCESS[/bold green] [dim]Source:[/dim] {source_name} "
                        f"[dim]|[/dim] {file_size} [dim]|[/dim] {duration}"
                    )
                    
                    # Log success with details
                    self.logger.info(
                        f"Successfully downloaded theme for '{show_name}' from {source_name} "
                        f"(size: {file_size}, duration: {duration})"
                    )
                    
                    self.results["success"] += 1
                    return
                else:
                    self.console.print(f" [red]✗[/red]")
                    self.logger.info(f"Source {source_name} failed for '{show_name}'")
            except OSError as exc:
                # Handle disk space and permission errors during download
                self.console.print(f" [red]✗[/]")
                import errno
                if exc.errno in (errno.ENOSPC, errno.EDQUOT):
                    self.logger.error(
                        f"Disk space error for {show_name}: {str(exc)}",
                        exc_info=True
                    )
                    self.console.print(
                        f"[red]ERROR[/] Disk space error: {str(exc)}"
                    )
                    self.results["failed"] += 1
                    return
                elif exc.errno == errno.EACCES:
                    self.logger.warning(
                        f"Permission denied for {show_name}: {str(exc)}"
                    )
                    self.console.print(
                        f"[yellow]Warning: Permission denied writing to {folder}[/]"
                    )
                    # Continue to next scraper
                else:
                    self.logger.error(
                        f"OS error for {show_name}: {str(exc)}",
                        exc_info=True
                    )
                    if self.verbose:
                        self.console.print(f"    OS Error: {str(exc)}")
            except Exception as exc:
                self.logger.error(
                    f"Unexpected exception in scraper {scraper.get_source_name()} "
                    f"for {show_name}: {str(exc)}",
                    exc_info=True
                )
                self.console.print(f" [red]✗[/]")
                if self.verbose:
                    self.console.print(f"    Error: {str(exc)}")

        self.console.print(f"[bold red]✗ FAILED[/bold red] [dim]No sources found for[/dim] {show_name}")
        self.logger.warning(f"All sources failed for '{show_name}'")
        self.results["failed"] += 1

    def display_summary(self) -> None:
        """Display results summary table."""
        table = Table(title="\n[bold dodger_blue1]Processing Summary[/bold dodger_blue1]", border_style="dodger_blue1")
        table.add_column("Status", style="bold", no_wrap=True)
        table.add_column("Count", justify="right", style="bold")

        table.add_row("✓ Success", f"[bold green]{self.results['success']}[/bold green]")
        table.add_row("⊘ Skipped", f"[yellow]{self.results['skipped']}[/yellow]")
        table.add_row("✗ Failed", f"[bold red]{self.results['failed']}[/bold red]")

        self.console.print(table)
