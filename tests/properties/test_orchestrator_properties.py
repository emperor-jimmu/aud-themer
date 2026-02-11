"""Property-based tests for orchestrator functionality."""

import pytest
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings
from rich.console import Console
from io import StringIO
from core.orchestrator import Orchestrator
from scrapers.base import ThemeScraper


# Reduce examples for faster test execution
fast_settings = settings(max_examples=20)


class MockScraper(ThemeScraper):
    """Mock scraper for testing."""
    
    def __init__(self, name: str, should_succeed: bool = False):
        self.name = name
        self.should_succeed = should_succeed
        self.called = False
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        self.called = True
        if self.should_succeed:
            # Create the file to simulate successful download
            output_path.write_text("mock theme data")
        return self.should_succeed
    
    def get_source_name(self) -> str:
        return self.name


# Feature: show-theme-cli, Property 2: Directory Scanning Completeness
@pytest.mark.property
@settings(max_examples=20)
@given(st.integers(min_value=0, max_value=20))
def test_directory_scanning_completeness(num_folders):
    """
    Property 2: Directory Scanning Completeness
    
    For any directory structure, scanning should identify all immediate
    subdirectories as potential series folders, regardless of their names
    or contents.
    
    Validates: Requirements 1.2
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create specified number of subdirectories
        created_folders = []
        for i in range(num_folders):
            folder = tmp_path / f"show_{i}"
            folder.mkdir()
            created_folders.append(folder)
        
        # Create some files (should be ignored)
        (tmp_path / "file1.txt").write_text("test")
        (tmp_path / "file2.mp3").write_text("test")
        
        # Create orchestrator and scan
        console = Console(file=StringIO())
        orchestrator = Orchestrator(console, dry_run=True)
        scanned_folders = orchestrator._scan_directory(tmp_path)
        
        # Should find exactly the number of folders we created
        assert len(scanned_folders) == num_folders
        
        # All created folders should be in the scanned list
        for folder in created_folders:
            assert folder in scanned_folders


# Feature: show-theme-cli, Property 3: Show Name Extraction Consistency
@pytest.mark.property
@settings(max_examples=20)
@given(st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(
        min_codepoint=32,
        max_codepoint=126,
        blacklist_characters='/\\:*?"<>|'
    )
))
def test_show_name_extraction_consistency(folder_name):
    """
    Property 3: Show Name Extraction Consistency
    
    For any valid directory name, extracting the show name should return
    the directory's base name without path components.
    
    Validates: Requirements 1.4
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create folder with the given name (sanitized for file system)
        safe_name = folder_name.strip()
        if not safe_name:
            safe_name = "test"
        
        folder = tmp_path / safe_name
        folder.mkdir()
        
        # Create orchestrator and extract name
        console = Console(file=StringIO())
        orchestrator = Orchestrator(console)
        extracted_name = orchestrator._extract_show_name(folder)
        
        # Extracted name should match the folder's base name
        assert extracted_name == folder.name
        assert extracted_name == safe_name


# Feature: show-theme-cli, Property 4: Dry Run File Safety
@pytest.mark.property
@settings(max_examples=20)
@given(st.integers(min_value=1, max_value=10))
def test_dry_run_file_safety(num_shows):
    """
    Property 4: Dry Run File Safety
    
    For any series folder processed in dry-run mode, no theme files
    should be created or modified on the file system.
    
    Validates: Requirements 1.5
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create show folders
        show_folders = []
        for i in range(num_shows):
            folder = tmp_path / f"show_{i}"
            folder.mkdir()
            show_folders.append(folder)
        
        # Create orchestrator in dry-run mode with a mock scraper
        console = Console(file=StringIO())
        orchestrator = Orchestrator(console, dry_run=True)
        # Clear default scrapers and add only our mock
        orchestrator.scrapers = []
        mock_scraper = MockScraper("TestSource", should_succeed=True)
        orchestrator.add_scraper(mock_scraper)
        
        # Process directory
        orchestrator.process_directory(tmp_path)
        
        # Verify no theme files were created
        for folder in show_folders:
            theme_mp3 = folder / "theme.mp3"
            theme_flac = folder / "theme.flac"
            theme_wav = folder / "theme.wav"
            
            assert not theme_mp3.exists()
            assert not theme_flac.exists()
            assert not theme_wav.exists()
        
        # Verify scraper was never called (dry-run should skip actual processing)
        assert not mock_scraper.called


# Feature: show-theme-cli, Property 5: Existing File Skip Logic
@pytest.mark.property
@settings(max_examples=20)
@given(st.sampled_from(['.mp3', '.flac', '.wav']))
def test_existing_file_skip_logic(theme_extension):
    """
    Property 5: Existing File Skip Logic
    
    For any series folder containing a theme file (theme.mp3, theme.flac,
    or theme.wav), the folder should be skipped when force mode is disabled.
    
    Validates: Requirements 2.1
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create show folder with existing theme
        show_folder = tmp_path / "test_show"
        show_folder.mkdir()
        existing_theme = show_folder / f"theme{theme_extension}"
        existing_theme.write_text("existing theme data")
        
        # Create orchestrator without force mode
        console = Console(file=StringIO())
        orchestrator = Orchestrator(console, force=False)
        # Clear default scrapers and add only our mock
        orchestrator.scrapers = []
        mock_scraper = MockScraper("TestSource", should_succeed=True)
        orchestrator.add_scraper(mock_scraper)
        
        # Process the show
        orchestrator.process_show(show_folder)
        
        # Verify scraper was not called (show was skipped)
        assert not mock_scraper.called
        
        # Verify skip was recorded
        assert orchestrator.results["skipped"] == 1
        assert orchestrator.results["success"] == 0
        assert orchestrator.results["failed"] == 0


# Feature: show-theme-cli, Property 6: Force Mode Override
@pytest.mark.property
@settings(max_examples=20)
@given(st.sampled_from(['.mp3', '.flac', '.wav']))
def test_force_mode_override(theme_extension):
    """
    Property 6: Force Mode Override
    
    For any series folder containing an existing theme file, the folder
    should be processed when force mode is enabled.
    
    Validates: Requirements 2.2
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create show folder with existing theme
        show_folder = tmp_path / "test_show"
        show_folder.mkdir()
        existing_theme = show_folder / f"theme{theme_extension}"
        existing_theme.write_text("existing theme data")
        
        # Create orchestrator WITH force mode
        console = Console(file=StringIO())
        orchestrator = Orchestrator(console, force=True)
        # Clear default scrapers and add only our mock
        orchestrator.scrapers = []
        mock_scraper = MockScraper("TestSource", should_succeed=True)
        orchestrator.add_scraper(mock_scraper)
        
        # Process the show
        orchestrator.process_show(show_folder)
        
        # Verify scraper WAS called (force mode overrides skip)
        assert mock_scraper.called
        
        # Verify success was recorded (not skipped)
        assert orchestrator.results["skipped"] == 0
        assert orchestrator.results["success"] == 1
        assert orchestrator.results["failed"] == 0


# Feature: show-theme-cli, Property 19: Multiple Theme Format Detection
@pytest.mark.property
@settings(max_examples=20)
@given(
    st.lists(
        st.sampled_from(['.mp3', '.flac', '.wav']),
        min_size=1,
        max_size=3,
        unique=True
    )
)
def test_multiple_theme_format_detection(extensions):
    """
    Property 19: Multiple Theme Format Detection
    
    For any series folder, if any theme file exists with extensions
    .mp3, .flac, or .wav, the folder should be identified as having
    an existing theme.
    
    Validates: Requirements 2.4, 2.5
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create show folder
        show_folder = tmp_path / "test_show"
        show_folder.mkdir()
        
        # Create theme files with the given extensions
        for ext in extensions:
            theme_file = show_folder / f"theme{ext}"
            theme_file.write_text("theme data")
        
        # Create orchestrator
        console = Console(file=StringIO())
        orchestrator = Orchestrator(console, force=False)
        
        # Check if existing theme is found
        existing_theme = orchestrator._find_existing_theme(show_folder)
        
        # Should find at least one theme file
        assert existing_theme is not None
        assert existing_theme.exists()
        assert existing_theme.suffix in ['.mp3', '.flac', '.wav']
        
        # Verify that processing skips the folder
        # Clear default scrapers and add only our mock
        orchestrator.scrapers = []
        mock_scraper = MockScraper("TestSource", should_succeed=True)
        orchestrator.add_scraper(mock_scraper)
        orchestrator.process_show(show_folder)
        
        # Should be skipped
        assert orchestrator.results["skipped"] == 1
        assert not mock_scraper.called
