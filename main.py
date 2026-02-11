"""Show Theme CLI - Main entry point."""

from pathlib import Path
import sys
import logging
from datetime import datetime
import time
from enum import Enum
import typer
from rich.console import Console
from core.orchestrator import Orchestrator, CriticalError, ContentMode
from core.dependencies import validate_dependencies

__version__ = "1.1.0"


class ModeChoice(str, Enum):
    """Content mode choices for CLI."""
    TV = "tv"
    ANIME = "anime"
    BOTH = "both"

app = typer.Typer(
    help="Automate theme song downloads for TV shows and anime",
    add_completion=False
)
console = Console()


@app.command()
def main(
    input_dir: Path = typer.Argument(
        None,
        help="Root directory containing show folders",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True
    ),
    mode: ModeChoice = typer.Option(
        ModeChoice.BOTH,
        "--mode",
        "-m",
        help="Content type: tv (TelevisionTunes, YouTube), anime (AnimeThemes, Themes.moe, YouTube), or both (all sources)"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing theme files"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging"
    ),
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simulate operations without downloading"
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        "-t",
        help="Network timeout in seconds (default: 30)"
    )
):
    """
    Scan a directory of TV shows/anime and download theme songs.

    The tool will scan each subdirectory in INPUT_DIR, identify the show name,
    and attempt to download theme songs from sources based on the selected mode:

    TV Mode (--mode tv):
    1. TelevisionTunes.co.uk
    2. YouTube (fallback)

    Anime Mode (--mode anime):
    1. AnimeThemes.moe
    2. Themes.moe
    3. YouTube (fallback)

    Both Mode (--mode both, default):
    1. TelevisionTunes.co.uk
    2. AnimeThemes.moe
    3. Themes.moe
    4. YouTube (fallback)

    By default, folders with existing theme files are skipped. Use --force to
    overwrite existing files.

    Examples:

        # Process TV shows only
        python main.py /path/to/tv_shows --mode tv

        # Process anime only
        python main.py /path/to/anime --mode anime

        # Process both (default)
        python main.py /path/to/shows --mode both

        # Force overwrite existing themes
        python main.py /path/to/tv_shows --force

        # Dry run to see what would be processed
        python main.py /path/to/tv_shows --dry-run

        # Enable verbose logging
        python main.py /path/to/tv_shows --verbose

        # Show version
        python main.py --version
    """
    # Handle version flag
    if version:
        console.print(f"[bold dodger_blue1]Show Theme CLI[/bold dodger_blue1] version [bold]{__version__}[/bold]")
        sys.exit(0)

    # Validate input_dir is provided
    if input_dir is None:
        console.print("[red]Error:[/red] INPUT_DIR is required")
        console.print("Try 'python main.py --help' for more information.")
        sys.exit(1)

    # Start timing
    start_time = time.time()

    console.print(f"[bold dodger_blue1]Show Theme CLI[/bold dodger_blue1] [dim]v{__version__}[/dim]\n")

    # Setup comprehensive logging to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(f"show-theme-cli-{timestamp}.log")
    
    # Set logging level based on verbose flag
    log_level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler() if verbose else logging.NullHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    # Log startup information
    logger.info(f"Show Theme CLI v{__version__} started")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Mode: {mode.value}")
    logger.info(f"Force mode: {force}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Timeout: {timeout}s")

    # Validate dependencies before processing
    validate_dependencies(console)

    # Convert mode enum to ContentMode
    content_mode = ContentMode[mode.value.upper()]

    try:
        orchestrator = Orchestrator(console, force, dry_run, verbose, timeout, content_mode)
        orchestrator.process_directory(input_dir)
        
        # Display elapsed time
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(int(elapsed_time), 60)
        if minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"
        console.print(f"\n[dim]Completed in {time_str}[/dim]")
        logger.info(f"Processing completed in {time_str}")
    except CriticalError as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)
        console.print(f"[red]CRITICAL ERROR:[/] {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/]")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        console.print(f"[red]UNEXPECTED ERROR:[/] {str(e)}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)
    finally:
        # Always show log file location
        console.print(f"\n[dim]Activity log saved to: {log_file}[/dim]")


if __name__ == "__main__":
    app()
