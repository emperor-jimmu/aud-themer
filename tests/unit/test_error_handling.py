"""Unit tests for error handling in orchestrator."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from rich.console import Console

from core.orchestrator import Orchestrator, CriticalError
from scrapers.base import ThemeScraper


class MockScraper(ThemeScraper):
    """Mock scraper for testing."""
    
    def __init__(self, name="MockScraper", should_succeed=False):
        self.name = name
        self.should_succeed = should_succeed
        self.call_count = 0
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        self.call_count += 1
        return self.should_succeed
    
    def get_source_name(self) -> str:
        return self.name


@pytest.mark.unit
def test_permission_error_on_folder_access(tmp_path):
    """
    Test that permission errors when accessing a folder are handled gracefully.
    
    Validates: Requirements 9.2
    """
    console = Console()
    orchestrator = Orchestrator(console, force=False, dry_run=False, verbose=False)
    
    # Create a mock folder that raises PermissionError
    mock_folder = Mock(spec=Path)
    mock_folder.name = "Test Show"
    mock_folder.__truediv__ = Mock(return_value=Path("/fake/path/theme.mp3"))
    mock_folder.exists.side_effect = PermissionError("Permission denied")
    
    # Process the folder - should skip with warning
    orchestrator.process_show(mock_folder)
    
    # Verify it was skipped
    assert orchestrator.results["skipped"] == 1
    assert orchestrator.results["success"] == 0
    assert orchestrator.results["failed"] == 0


@pytest.mark.unit
def test_disk_space_error_during_download(tmp_path):
    """
    Test that disk space errors during download are handled and logged.
    
    Validates: Requirements 9.3
    """
    console = Console()
    orchestrator = Orchestrator(console, force=False, dry_run=False, verbose=False)
    
    # Create a mock scraper that raises disk space error
    mock_scraper = Mock(spec=ThemeScraper)
    mock_scraper.get_source_name.return_value = "MockSource"
    mock_scraper.search_and_download.side_effect = OSError("No space left on device")
    
    orchestrator.scrapers = [mock_scraper]
    
    # Create a real folder
    show_folder = tmp_path / "Test Show"
    show_folder.mkdir()
    
    # Process the folder
    orchestrator.process_show(show_folder)
    
    # Verify it was marked as failed
    assert orchestrator.results["failed"] == 1
    assert orchestrator.results["success"] == 0


@pytest.mark.unit
def test_critical_error_invalid_input_directory():
    """
    Test that invalid input directory raises CriticalError.
    
    Validates: Requirements 9.5
    """
    console = Console()
    orchestrator = Orchestrator(console)
    
    # Non-existent directory
    invalid_dir = Path("/nonexistent/directory")
    
    with pytest.raises(CriticalError, match="does not exist"):
        orchestrator.process_directory(invalid_dir)


@pytest.mark.unit
def test_critical_error_input_is_file(tmp_path):
    """
    Test that providing a file instead of directory raises CriticalError.
    
    Validates: Requirements 9.5
    """
    console = Console()
    orchestrator = Orchestrator(console)
    
    # Create a file instead of directory
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")
    
    with pytest.raises(CriticalError, match="not a directory"):
        orchestrator.process_directory(test_file)


@pytest.mark.unit
def test_single_show_failure_does_not_stop_processing(tmp_path):
    """
    Test that failure on one show doesn't prevent processing of other shows.
    
    Validates: Requirements 9.4
    """
    console = Console()
    orchestrator = Orchestrator(console, force=False, dry_run=False, verbose=False)
    
    # Create a scraper that always fails
    failing_scraper = MockScraper(name="FailingScraper", should_succeed=False)
    orchestrator.scrapers = [failing_scraper]
    
    # Create multiple show folders
    show1 = tmp_path / "Show 1"
    show2 = tmp_path / "Show 2"
    show3 = tmp_path / "Show 3"
    show1.mkdir()
    show2.mkdir()
    show3.mkdir()
    
    # Process all folders
    orchestrator.process_directory(tmp_path)
    
    # All three should have been attempted (all failed)
    assert orchestrator.results["failed"] == 3
    assert failing_scraper.call_count == 3  # One attempt per show


@pytest.mark.unit
def test_graceful_degradation_with_exception(tmp_path):
    """
    Test that unexpected exceptions in one show don't crash the entire process.
    
    Validates: Requirements 9.4
    """
    console = Console()
    orchestrator = Orchestrator(console, force=False, dry_run=False, verbose=False)
    
    # Create a scraper that raises an unexpected exception
    mock_scraper = Mock(spec=ThemeScraper)
    mock_scraper.get_source_name.return_value = "ExceptionScraper"
    mock_scraper.search_and_download.side_effect = RuntimeError("Unexpected error")
    
    orchestrator.scrapers = [mock_scraper]
    
    # Create show folders
    show1 = tmp_path / "Show 1"
    show2 = tmp_path / "Show 2"
    show1.mkdir()
    show2.mkdir()
    
    # Process directory - should not crash
    orchestrator.process_directory(tmp_path)
    
    # Both shows should be marked as failed, but processing completed
    assert orchestrator.results["failed"] == 2


@pytest.mark.unit
def test_permission_error_on_directory_scan(tmp_path):
    """
    Test that permission errors during directory scan are handled gracefully.
    
    Validates: Requirements 9.2
    """
    console = Console()
    orchestrator = Orchestrator(console)
    
    # Mock the iterdir to raise PermissionError
    with patch.object(Path, 'iterdir', side_effect=PermissionError("Access denied")):
        folders = orchestrator._scan_directory(tmp_path)
    
    # Should return empty list and log warning
    assert folders == []


@pytest.mark.unit
def test_os_error_on_directory_scan(tmp_path):
    """
    Test that OS errors during directory scan are handled gracefully.
    
    Validates: Requirements 9.2
    """
    console = Console()
    orchestrator = Orchestrator(console)
    
    # Mock the iterdir to raise OSError
    with patch.object(Path, 'iterdir', side_effect=OSError("I/O error")):
        folders = orchestrator._scan_directory(tmp_path)
    
    # Should return empty list and log warning
    assert folders == []


@pytest.mark.unit
def test_verbose_mode_shows_error_details(tmp_path):
    """
    Test that verbose mode displays detailed error information.
    
    Validates: Requirements 9.2
    """
    console = Console()
    orchestrator = Orchestrator(console, force=False, dry_run=False, verbose=True)
    
    # Create a scraper that raises an exception
    mock_scraper = Mock(spec=ThemeScraper)
    mock_scraper.get_source_name.return_value = "VerboseScraper"
    mock_scraper.search_and_download.side_effect = ValueError("Detailed error message")
    
    orchestrator.scrapers = [mock_scraper]
    
    # Create show folder
    show_folder = tmp_path / "Test Show"
    show_folder.mkdir()
    
    # Process the folder - should not crash and should log details
    orchestrator.process_show(show_folder)
    
    # Verify it was marked as failed
    assert orchestrator.results["failed"] == 1


@pytest.mark.unit
def test_permission_error_during_write_continues_to_next_scraper(tmp_path):
    """
    Test that permission errors during file write allow trying next scraper.
    
    Validates: Requirements 9.2, 9.4
    """
    console = Console()
    orchestrator = Orchestrator(console, force=False, dry_run=False, verbose=False)
    
    # Create two scrapers: first fails with permission error, second succeeds
    failing_scraper = Mock(spec=ThemeScraper)
    failing_scraper.get_source_name.return_value = "FailingScraper"
    failing_scraper.search_and_download.side_effect = OSError("Permission denied")
    
    succeeding_scraper = MockScraper(name="SucceedingScraper", should_succeed=True)
    
    orchestrator.scrapers = [failing_scraper, succeeding_scraper]
    
    # Create show folder
    show_folder = tmp_path / "Test Show"
    show_folder.mkdir()
    
    # Process the folder
    orchestrator.process_show(show_folder)
    
    # Second scraper should have been tried and succeeded
    assert orchestrator.results["success"] == 1
    assert succeeding_scraper.call_count == 1


@pytest.mark.unit
def test_critical_error_propagates_from_process_directory(tmp_path):
    """
    Test that CriticalError raised during processing propagates correctly.
    
    Validates: Requirements 9.5
    """
    console = Console()
    orchestrator = Orchestrator(console)
    
    # Create a show folder
    show_folder = tmp_path / "Test Show"
    show_folder.mkdir()
    
    # Mock process_show to raise CriticalError
    with patch.object(orchestrator, 'process_show', side_effect=CriticalError("Critical!")):
        with pytest.raises(CriticalError, match="Critical!"):
            orchestrator.process_directory(tmp_path)
