"""Show Theme CLI - Main entry point."""

from pathlib import Path
import sys
import logging
from datetime import datetime
import typer
from rich.console import Console
from core.orchestrator import Orchestrator, CriticalError
from core.dependencies import validate_dependencies


app = typer.Typer(
    help="Automate theme song downloads for TV shows and anime",
    add_completion=False
)
console = Console()


@app.command()
def main(
    input_dir: Path = typer.Argument(
        ...,
        help="Root directory containing show folders",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True
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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simulate operations without downloading"
    )
):
    """
    Scan a directory of TV shows/anime and download theme songs.

    The tool will scan each subdirectory in INPUT_DIR, identify the show name,
    and attempt to download theme songs from multiple sources in priority order:

    1. TelevisionTunes.co.uk (best for TV shows)
    2. AnimeThemes.moe (best for anime)
    3. Themes.moe (additional anime source)
    4. YouTube (fallback for everything)

    By default, folders with existing theme files are skipped. Use --force to
    overwrite existing files.

    Examples:

        # Basic usage
        python main.py /path/to/tv_shows

        # Force overwrite existing themes
        python main.py /path/to/tv_shows --force

        # Dry run to see what would be processed
        python main.py /path/to/tv_shows --dry-run

        # Enable verbose logging
        python main.py /path/to/tv_shows --verbose
    """
    console.print("[bold blue]Show Theme CLI[/bold blue]\n")

    # Setup error logging to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(f"errors-{timestamp}.log")
    
    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler() if verbose else logging.NullHandler()
        ]
    )
    logger = logging.getLogger(__name__)

    # Validate dependencies before processing
    validate_dependencies(console)

    try:
        orchestrator = Orchestrator(console, force, dry_run, verbose)
        orchestrator.process_directory(input_dir)
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
        # Only show log file message if errors were logged
        if log_file.exists() and log_file.stat().st_size > 0:
            console.print(f"\n[dim]Error log saved to: {log_file}[/dim]")


if __name__ == "__main__":
    app()
