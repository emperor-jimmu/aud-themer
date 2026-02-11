"""Property-based tests for file operations."""

import pytest
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings
from rich.console import Console
from io import StringIO
from core.orchestrator import Orchestrator
from scrapers.base import ThemeScraper


class MockScraper(ThemeScraper):
    """Mock scraper for testing file operations."""
    
    def __init__(self, name: str, should_succeed: bool = False):
        self.name = name
        self.should_succeed = should_succeed
        self.called = False
        self.output_path_used = None
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        self.called = True
        self.output_path_used = output_path
        if self.should_succeed:
            # Create the file to simulate successful download
            # Write enough data to pass file size validation (>500KB)
            output_path.write_bytes(b"mock theme data" * 40000)
        return self.should_succeed
    
    def get_source_name(self) -> str:
        return self.name


# Feature: show-theme-cli, Property 12: Output File Naming
@pytest.mark.property
@settings(max_examples=100)
@given(st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        min_codepoint=32,
        max_codepoint=126,
        blacklist_characters='/\\:*?"<>|'
    )
))
def test_output_file_naming(show_name):
    """
    Property 12: Output File Naming
    
    For any series folder, the output theme file should always be named
    "theme.mp3" regardless of the source or original filename.
    
    Validates: Requirements 7.3, 8.1
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create show folder with sanitized name
        safe_name = show_name.strip()
        # Handle edge cases: empty strings, dots, and other problematic names
        if not safe_name or safe_name in ('.', '..'):
            safe_name = "test_show"
        
        show_folder = tmp_path / safe_name
        # Use exist_ok=True to handle edge cases where folder might already exist
        show_folder.mkdir(exist_ok=True)
        
        # Create orchestrator with mock scraper
        console = Console(file=StringIO())
        orchestrator = Orchestrator(console, force=False)
        # Clear default scrapers and add only our mock
        orchestrator.scrapers = []
        mock_scraper = MockScraper("TestSource", should_succeed=True)
        orchestrator.add_scraper(mock_scraper)
        
        # Process the show
        orchestrator.process_show(show_folder)
        
        # Verify the scraper was called
        assert mock_scraper.called
        
        # Verify the output path passed to scraper is always "theme.mp3"
        assert mock_scraper.output_path_used is not None
        assert mock_scraper.output_path_used.name == "theme.mp3"
        assert mock_scraper.output_path_used.parent == show_folder
        
        # Verify the file was actually created with the correct name
        theme_file = show_folder / "theme.mp3"
        assert theme_file.exists()
        assert theme_file.name == "theme.mp3"


# Feature: show-theme-cli, Property 15: Force Mode Overwrite
@pytest.mark.property
@settings(max_examples=100)
@given(st.sampled_from(['.mp3', '.flac', '.wav']))
def test_force_mode_overwrite(existing_extension):
    """
    Property 15: Force Mode Overwrite
    
    For any existing theme file, when force mode is enabled, the new
    download should replace the existing file completely.
    
    Validates: Requirements 8.3
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create show folder with existing theme
        show_folder = tmp_path / "test_show"
        show_folder.mkdir()
        existing_theme = show_folder / f"theme{existing_extension}"
        original_content = b"original theme data" * 1000
        existing_theme.write_bytes(original_content)
        original_size = existing_theme.stat().st_size
        
        # Create orchestrator WITH force mode
        console = Console(file=StringIO())
        orchestrator = Orchestrator(console, force=True)
        # Clear default scrapers and add only our mock
        orchestrator.scrapers = []
        mock_scraper = MockScraper("TestSource", should_succeed=True)
        orchestrator.add_scraper(mock_scraper)
        
        # Process the show
        orchestrator.process_show(show_folder)
        
        # Verify scraper was called (force mode overrides skip)
        assert mock_scraper.called
        
        # Verify new theme.mp3 was created
        new_theme = show_folder / "theme.mp3"
        assert new_theme.exists(), "New theme.mp3 should exist"
        
        # Verify the new file has different content (from mock scraper)
        new_content = new_theme.read_bytes()
        assert new_content != original_content, \
            "New file should have different content than original"
        assert b"mock theme data" in new_content, \
            "New file should contain mock scraper data"
        
        # If the original extension was different from .mp3, verify old file was deleted
        if existing_extension != '.mp3':
            assert not existing_theme.exists(), \
                f"Old theme file {existing_theme.name} should have been deleted"
        
        # Verify only theme.mp3 exists (no other theme formats)
        for ext in ['.mp3', '.flac', '.wav']:
            theme_file = show_folder / f"theme{ext}"
            if ext == '.mp3':
                assert theme_file.exists(), "theme.mp3 should exist"
            else:
                assert not theme_file.exists(), \
                    f"theme{ext} should not exist after force mode overwrite"
        
        # Verify success was recorded
        assert orchestrator.results["success"] == 1
        assert orchestrator.results["skipped"] == 0
