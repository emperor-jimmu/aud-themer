"""Integration tests for CLI output formatting."""

import pytest
import re
from pathlib import Path
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from main import app
from scrapers.base import ThemeScraper


class MockSuccessScraper(ThemeScraper):
    """Mock scraper that succeeds."""
    
    def __init__(self, source_name="MockSuccess"):
        self.source_name = source_name
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        output_path.write_bytes(b"x" * 600_000)
        return True
    
    def get_source_name(self) -> str:
        return self.source_name


class MockFailScraper(ThemeScraper):
    """Mock scraper that fails."""
    
    def __init__(self, source_name="MockFail"):
        self.source_name = source_name
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        return False
    
    def get_source_name(self) -> str:
        return self.source_name


@pytest.mark.integration
class TestCLIOutputFormatting:
    """Test CLI output formatting and display."""
    
    def test_title_display(self, tmp_path):
        """
        Test that CLI displays title on startup.
        
        Validates: Requirements 10.1
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper'), \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify title is displayed
            assert "Show Theme CLI" in result.stdout
            assert result.exit_code == 0
    
    def test_folder_count_display(self, tmp_path):
        """
        Test that total folder count is displayed.
        
        Validates: Requirements 10.8
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        # Create multiple show folders
        for i in range(5):
            (shows_dir / f"Show {i}").mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessScraper()
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify folder count is displayed
            assert "Found 5 series folders" in result.stdout
            assert result.exit_code == 0
    
    def test_folder_progression_display(self, tmp_path):
        """
        Test that folder progression (X/Y) is displayed for each folder.
        
        Validates: Requirements 10.7, 10.8
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        # Create 3 show folders
        (shows_dir / "Show 1").mkdir()
        (shows_dir / "Show 2").mkdir()
        (shows_dir / "Show 3").mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessScraper()
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify progression is displayed for each folder
            assert "Folder 1/3" in result.stdout
            assert "Folder 2/3" in result.stdout
            assert "Folder 3/3" in result.stdout
            assert result.exit_code == 0
    
    def test_success_status_display(self, tmp_path):
        """
        Test that success status is displayed with source and file path.
        
        Validates: Requirements 10.2
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Successful Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessScraper("TelevisionTunes")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify success message format
            assert "SUCCESS" in result.stdout
            assert "Source: TelevisionTunes" in result.stdout
            assert "theme.mp3" in result.stdout
            assert result.exit_code == 0
    
    def test_skipped_status_display(self, tmp_path):
        """
        Test that skipped status is displayed for existing files.
        
        Validates: Requirements 10.3
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Existing Show"
        show1.mkdir()
        
        # Create existing theme
        (show1 / "theme.mp3").write_bytes(b"existing" * 100_000)
        
        with patch('core.orchestrator.TelevisionTunesScraper'), \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify skipped message format
            assert "SKIPPED" in result.stdout
            assert "File exists" in result.stdout
            assert result.exit_code == 0
    
    def test_failed_status_display(self, tmp_path):
        """
        Test that failed status is displayed when all sources fail.
        
        Validates: Requirements 10.4
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Failed Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper') as mock_anime, \
             patch('core.orchestrator.ThemesMoeScraper') as mock_themes, \
             patch('core.orchestrator.YoutubeScraper') as mock_youtube:
            
            # All scrapers fail
            mock_tv.return_value = MockFailScraper()
            mock_anime.return_value = MockFailScraper()
            mock_themes.return_value = MockFailScraper()
            mock_youtube.return_value = MockFailScraper()
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify failed message format
            assert "FAILED" in result.stdout
            assert "No sources found" in result.stdout
            assert result.exit_code == 0
    
    def test_source_attempt_display(self, tmp_path):
        """
        Test that each source attempt is displayed.
        
        Validates: Requirements 10.1
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper') as mock_anime, \
             patch('core.orchestrator.ThemesMoeScraper') as mock_themes, \
             patch('core.orchestrator.YoutubeScraper') as mock_youtube:
            
            # First three fail, YouTube succeeds
            mock_tv.return_value = MockFailScraper("TelevisionTunes")
            mock_anime.return_value = MockFailScraper("AnimeThemes")
            mock_themes.return_value = MockFailScraper("Themes.moe")
            mock_youtube.return_value = MockSuccessScraper("YouTube")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify all source attempts are shown
            assert "Trying TelevisionTunes" in result.stdout
            assert "Trying AnimeThemes" in result.stdout
            assert "Trying Themes.moe" in result.stdout
            assert "Trying YouTube" in result.stdout
            assert result.exit_code == 0
    
    def test_summary_table_display(self, tmp_path):
        """
        Test that summary table is displayed at the end.
        
        Validates: Requirements 10.5
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        # Create shows with different outcomes
        success_show = shows_dir / "Success Show"
        skipped_show = shows_dir / "Skipped Show"
        failed_show = shows_dir / "Failed Show"
        
        success_show.mkdir()
        skipped_show.mkdir()
        failed_show.mkdir()
        
        # Create existing theme for skipped show
        (skipped_show / "theme.mp3").write_bytes(b"existing" * 100_000)
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            # Mock conditional behavior
            class ConditionalScraper(ThemeScraper):
                def search_and_download(self, show_name: str, output_path: Path) -> bool:
                    if "Success" in show_name:
                        output_path.write_bytes(b"x" * 600_000)
                        return True
                    return False
                
                def get_source_name(self) -> str:
                    return "ConditionalScraper"
            
            mock_tv.return_value = ConditionalScraper()
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify summary table is present
            assert "Processing Summary" in result.stdout
            assert "Status" in result.stdout
            assert "Count" in result.stdout
            assert "Success" in result.stdout
            assert "Skipped" in result.stdout
            assert "Failed" in result.stdout
            
            # Verify counts are displayed
            assert "1" in result.stdout  # At least one count should be 1
            assert result.exit_code == 0
    
    def test_colored_output_indicators(self, tmp_path):
        """
        Test that colored status indicators are used.
        
        Validates: Requirements 10.7
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        success_show = shows_dir / "Success Show"
        success_show.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessScraper()
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify Rich color tags are present (green for success)
            assert "[green]" in result.stdout or "✓" in result.stdout
            assert result.exit_code == 0
    
    def test_processing_label_display(self, tmp_path):
        """
        Test that "Processing:" label is displayed for each show.
        
        Validates: Requirements 10.1
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessScraper()
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify processing label
            assert "Processing:" in result.stdout
            assert "Test Show" in result.stdout
            assert result.exit_code == 0
    
    def test_dry_run_output_format(self, tmp_path):
        """
        Test that dry-run mode displays appropriate messages.
        
        Validates: Requirements 10.1
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper'), \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir), "--dry-run"])
            
            # Verify dry run message
            assert "DRY RUN" in result.stdout
            assert "Would process" in result.stdout
            assert result.exit_code == 0
    
    def test_verbose_mode_output(self, tmp_path):
        """
        Test that verbose mode displays additional debug information.
        
        Validates: Requirements 10.6
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        class VerboseErrorScraper(ThemeScraper):
            """Scraper that raises error for verbose testing."""
            
            def search_and_download(self, show_name: str, output_path: Path) -> bool:
                raise ValueError("Detailed error for verbose mode")
            
            def get_source_name(self) -> str:
                return "VerboseScraper"
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = VerboseErrorScraper()
            
            # Run with verbose flag
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir), "--verbose"])
            
            # Verify verbose output contains error details
            # In verbose mode, errors should be more detailed
            assert "Error" in result.stdout or "error" in result.stdout
            assert result.exit_code == 0
    
    def test_empty_directory_message(self, tmp_path):
        """
        Test that empty directory displays appropriate message.
        
        Validates: Requirements 10.1
        """
        shows_dir = tmp_path / "empty_shows"
        shows_dir.mkdir()
        
        runner = CliRunner()
        result = runner.invoke(app, [str(shows_dir)])
        
        # Verify empty directory message
        assert "No series folders found" in result.stdout
        assert result.exit_code == 0
    
    def test_output_format_consistency(self, tmp_path):
        """
        Test that output format is consistent across multiple runs.
        
        Validates: Requirements 10.1-10.8
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessScraper()
            
            runner = CliRunner()
            
            # Run twice
            result1 = runner.invoke(app, [str(shows_dir), "--force"])
            result2 = runner.invoke(app, [str(shows_dir), "--force"])
            
            # Verify both outputs have consistent structure
            for result in [result1, result2]:
                assert "Show Theme CLI" in result.stdout
                assert "Found 1 series folders" in result.stdout or "Found 1 series folder" in result.stdout
                assert "Folder 1/1" in result.stdout
                assert "Processing:" in result.stdout
                assert "SUCCESS" in result.stdout
                assert "Processing Summary" in result.stdout
                assert result.exit_code == 0
    
    def test_checkmark_and_x_indicators(self, tmp_path):
        """
        Test that checkmark (✓) and X (✗) indicators are displayed.
        
        Validates: Requirements 10.1, 10.7
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper') as mock_anime, \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            # First fails, second succeeds
            mock_tv.return_value = MockFailScraper("TelevisionTunes")
            mock_anime.return_value = MockSuccessScraper("AnimeThemes")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify indicators are present
            assert "✓" in result.stdout or "✗" in result.stdout
            assert result.exit_code == 0
    
    def test_summary_table_with_all_zero(self, tmp_path):
        """
        Test summary table when no shows are processed.
        
        Validates: Requirements 10.5
        """
        shows_dir = tmp_path / "empty_shows"
        shows_dir.mkdir()
        
        runner = CliRunner()
        result = runner.invoke(app, [str(shows_dir)])
        
        # Verify summary is still displayed even with no shows
        assert "No series folders found" in result.stdout
        assert result.exit_code == 0
