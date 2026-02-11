"""Dependency validation utilities."""

import subprocess
import sys
from rich.console import Console


def check_ffmpeg() -> bool:
    """
    Check if FFmpeg is installed and available.
    
    Returns:
        True if FFmpeg is available, False otherwise
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_playwright_browsers() -> bool:
    """
    Check if Playwright browsers are installed.
    
    Returns:
        True if browsers are available, False otherwise
    """
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            # Try to launch chromium to verify it's installed
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception as e:
        # Check if it's specifically a browser not found error
        error_str = str(e)
        if "executable doesn't exist" in error_str.lower() or \
           "browser is not installed" in error_str.lower():
            return False
        # For other errors, assume browsers are installed but something else failed
        return True


def validate_dependencies(console: Console) -> None:
    """
    Validate all required dependencies are installed.
    
    Args:
        console: Rich console for output
        
    Raises:
        SystemExit: If any required dependency is missing
    """
    missing_deps = []
    
    # Check FFmpeg
    if not check_ffmpeg():
        missing_deps.append({
            "name": "FFmpeg",
            "install": "Install from https://ffmpeg.org/ or use your package manager:\n"
                      "  - macOS: brew install ffmpeg\n"
                      "  - Ubuntu/Debian: sudo apt install ffmpeg\n"
                      "  - Windows: Download from https://ffmpeg.org/download.html"
        })
    
    # Check Playwright browsers
    if not check_playwright_browsers():
        missing_deps.append({
            "name": "Playwright browsers",
            "install": "Run: playwright install chromium"
        })
    
    if missing_deps:
        console.print("[red]ERROR: Missing required dependencies[/]\n")
        for dep in missing_deps:
            console.print(f"[yellow]Missing:[/] {dep['name']}")
            console.print(f"[cyan]Install:[/] {dep['install']}\n")
        sys.exit(1)
