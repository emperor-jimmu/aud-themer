"""Orchestration logic for theme song retrieval."""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from scrapers.base import ThemeScraper
from scrapers.tv_tunes import TelevisionTunesScraper
from scrapers.anime_themes import AnimeThemesScraper
from scrapers.themes_moe import ThemesMoeScraper
from scrapers.youtube import YoutubeScraper


class CriticalError(Exception):
    """Exception raised for critical errors that should stop execution."""
    pass


class Orchestrator:
    """Orchestrates theme song retrieval across multiple sources."""
    
    THEME_EXTENSIONS = ['.mp3', '.flac', '.wav']
    DEFAULT_CONCURRENCY = 3  # Process 3 shows concurrently by default
    
    def __init__(
        self,
        console: Console,
        force: bool = False,
        dry_run: bool = False,
        verbose: bool = False,
        max_concurrent: int = DEFAULT_CONCURRENCY
    ):
        """
        Initialize the orchestrator.
        
        Args:
            console: Rich console for output
            force: If True, overwrite existing theme files
            dry_run: If True, simulate operations without downloading
            verbose: If True, enable debug logging
            max_concurrent: Maximum number of shows to process concurrently
        """
        self.console = console
        self.force = force
        self.dry_run = dry_run
        self.verbose = verbose
        self.max_concurrent = max_concurrent
        self.scrapers: List[ThemeScraper] = []
        self.results = {
            "success": 0,
            "skipped": 0,
            "failed": 0
        }
        self._results_lock = asyncio.Lock()
        
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
            TelevisionTunesScraper(self.console, self.verbose),
            AnimeThemesScraper(self.console, self.verbose),
            ThemesMoeScraper(self.console, self.verbose),
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
        
        series_folders = self._scan_directory(input_dir)
        
        if not series_folders:
            self.console.print("[yellow]No series folders found[/]")
            return
        
        total_folders = len(series_folders)
        self.console.print(f"Found {total_folders} series folders\n")
        
        # Run async processing
        asyncio.run(self._process_folders_async(series_folders))
        
        self.display_summary()
    
    async def _process_folders_async(self, folders: List[Path]) -> None:
        """
        Process folders concurrently with limited concurrency.
        
        Args:
            folders: List of series folders to process
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        total_folders = len(folders)
        
        async def process_with_semaphore(folder: Path, index: int) -> None:
            async with semaphore:
                self.console.print(f"\n[bold cyan]Folder {index}/{total_folders}[/bold cyan]")
                try:
                    # Run the synchronous process_show in a thread pool
                    await asyncio.to_thread(self.process_show, folder)
                except CriticalError:
                    # Re-raise critical errors to stop execution
                    raise
                except Exception as e:
                    # Log non-critical errors and continue processing
                    self.console.print(
                        f"[red]ERROR[/] Unexpected error processing {folder.name}: {str(e)}"
                    )
                    if self.verbose:
                        import traceback
                        self.console.print(traceback.format_exc())
                    async with self._results_lock:
                        self.results["failed"] += 1
        
        # Create tasks for all folders
        tasks = [
            process_with_semaphore(folder, index)
            for index, folder in enumerate(folders, start=1)
        ]
        
        # Wait for all tasks to complete
        # gather will propagate the first exception (including CriticalError)
        await asyncio.gather(*tasks)
    
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
        
        Checks for theme files with extensions: .mp3, .flac, .wav
        
        Args:
            folder: Path to series folder
            
        Returns:
            Path to existing theme file, or None if not found
        """
        for ext in self.THEME_EXTENSIONS:
            theme_file = folder / f"theme{ext}"
            if theme_file.exists():
                return theme_file
        return None
    
    
    def process_show(self, folder: Path) -> None:
        """
        Process a single show folder (synchronous version).
        
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
                f"[yellow]SKIPPED[/] {show_name} - Permission denied"
            )
            self.results["skipped"] += 1
            return
        except OSError as e:
            self.console.print(
                f"[yellow]SKIPPED[/] {show_name} - Cannot access folder: {str(e)}"
            )
            self.results["skipped"] += 1
            return
        
        # Check if theme already exists
        existing_theme = self._find_existing_theme(folder)
        
        if existing_theme and not self.force:
            self.console.print(f"[yellow]SKIPPED[/] {show_name} - File exists")
            self.results["skipped"] += 1
            return
        
        if self.dry_run:
            self.console.print(f"[blue]DRY RUN[/] Would process: {show_name}")
            return
        
        # If force mode is enabled and a theme exists, delete it before downloading
        if self.force and existing_theme:
            try:
                existing_theme.unlink()
                if self.verbose:
                    self.console.print(f"  Deleted existing theme: {existing_theme.name}")
            except OSError as e:
                self.console.print(
                    f"[yellow]Warning: Could not delete existing theme: {str(e)}[/]"
                )
        
        # Try each scraper in order (waterfall approach)
        self.console.print(f"\n[bold]Processing:[/] {show_name}")
        
        for scraper in self.scrapers:
            source_name = scraper.get_source_name()
            self.console.print(f"  Trying {source_name}...", end="")
            
            try:
                if scraper.search_and_download(show_name, theme_file):
                    self.console.print(f" [green]✓[/]")
                    self.console.print(
                        f"[green]SUCCESS[/] Source: {source_name} | "
                        f"File: {theme_file}"
                    )
                    self.results["success"] += 1
                    return
                else:
                    self.console.print(f" [red]✗[/]")
            except OSError as e:
                # Handle disk space and permission errors during download
                self.console.print(f" [red]✗[/]")
                if "No space left on device" in str(e) or "Disk quota exceeded" in str(e):
                    self.console.print(
                        f"[red]ERROR[/] Disk space error: {str(e)}"
                    )
                    self.results["failed"] += 1
                    return
                elif "Permission denied" in str(e):
                    self.console.print(
                        f"[yellow]Warning: Permission denied writing to {folder}[/]"
                    )
                    # Continue to next scraper
                else:
                    if self.verbose:
                        self.console.print(f"    OS Error: {str(e)}")
            except Exception as e:
                self.console.print(f" [red]✗[/]")
                if self.verbose:
                    self.console.print(f"    Error: {str(e)}")
        
        self.console.print(f"[red]FAILED[/] No sources found for {show_name}")
        self.results["failed"] += 1
    
    def display_summary(self) -> None:
        """Display results summary table."""
        table = Table(title="\nProcessing Summary")
        table.add_column("Status", style="bold")
        table.add_column("Count", justify="right")
        
        table.add_row("Success", f"[green]{self.results['success']}[/]")
        table.add_row("Skipped", f"[yellow]{self.results['skipped']}[/]")
        table.add_row("Failed", f"[red]{self.results['failed']}[/]")
        
        self.console.print(table)
