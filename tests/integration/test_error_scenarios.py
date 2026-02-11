"""Integration tests for error scenarios."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typer.testing import CliRunner

from main import app
from core.orchestrator import Orchestrator, CriticalError
from scrapers.base import ThemeScraper


class TimeoutScraper(ThemeScraper):
    """Mock scraper that simulates network timeout."""
    
    def __init__(self, source_name="TimeoutScraper"):
        self.source_name = source_name
        self.call_count = 0
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """Simulate timeout."""
        self.call_count += 1
        import time
        time.sleep(0.1)  # Small delay to simulate timeout
        raise TimeoutError("Connection timed out")
    
    def get_source_name(self) -> str:
        return self.source_name


class AllFailingScraper(ThemeScraper):
    """Mock scraper that always fails."""
    
    def __init__(self, source_name="FailingScraper"):
        self.source_name = source_name
        self.call_count = 0
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """Always fail."""
        self.call_count += 1
        return False
    
    def get_source_name(self) -> str:
        return self.source_name


@pytest.mark.integration
class TestErrorScenariosEndToEnd:
    """Test error scenarios from CLI through to completion."""
    
    def test_all_sources_failing(self, tmp_path):
        """
        Test that when all sources fail, show is marked as failed.
        
        Validates: Requirements 9.3
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Impossible Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper') as mock_anime, \
             patch('core.orchestrator.ThemesMoeScraper') as mock_themes, \
             patch('core.orchestrator.YoutubeScraper') as mock_youtube:
            
            # All scrapers fail
            mock_tv.return_value = AllFailingScraper("TelevisionTunes")
            mock_anime.return_value = AllFailingScraper("AnimeThemes")
            mock_themes.return_value = AllFailingScraper("Themes.moe")
            mock_youtube.return_value = AllFailingScraper("YouTube")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify show was marked as failed
            assert "FAILED" in result.stdout
            assert "No sources found" in result.stdout
            
            # Verify no theme file was created
            theme_file = show1 / "theme.mp3"
            assert not theme_file.exists()
            
            # Verify summary shows 1 failure
            assert result.exit_code == 0  # Process completes even with failures
    
    def test_network_timeout_handling(self, tmp_path):
        """
        Test that network timeouts are handled gracefully.
        
        Validates: Requirements 9.1
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Timeout Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper') as mock_anime, \
             patch('core.orchestrator.ThemesMoeScraper') as mock_themes, \
             patch('core.orchestrator.YoutubeScraper') as mock_youtube:
            
            # First scraper times out, others fail normally
            mock_tv.return_value = TimeoutScraper("TelevisionTunes")
            mock_anime.return_value = AllFailingScraper("AnimeThemes")
            mock_themes.return_value = AllFailingScraper("Themes.moe")
            mock_youtube.return_value = AllFailingScraper("YouTube")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify timeout was handled and processing continued
            assert "FAILED" in result.stdout
            
            # Verify no crash occurred
            assert result.exit_code == 0
    
    def test_invalid_input_directory(self):
        """
        Test that invalid input directory shows error and exits.
        
        Validates: Requirements 9.5
        """
        runner = CliRunner()
        result = runner.invoke(app, ["/nonexistent/directory/path"])
        
        # Verify error exit code
        assert result.exit_code != 0
        
        # Verify error message
        output = result.stdout + (result.stderr or "")
        assert "does not exist" in output.lower() or "invalid" in output.lower()
    
    def test_file_instead_of_directory(self, tmp_path):
        """
        Test that providing a file instead of directory shows error.
        
        Validates: Requirements 9.5
        """
        test_file = tmp_path / "not_a_directory.txt"
        test_file.write_text("test content")
        
        runner = CliRunner()
        result = runner.invoke(app, [str(test_file)])
        
        # Verify error exit code
        assert result.exit_code != 0
    
    def test_permission_error_on_directory(self, tmp_path):
        """
        Test that permission errors on directory access are handled.
        
        Validates: Requirements 9.2
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Restricted Show"
        show1.mkdir()
        
        class PermissionErrorScraper(ThemeScraper):
            """Scraper that simulates permission error during file access."""
            
            def search_and_download(self, show_name: str, output_path: Path) -> bool:
                # Simulate permission error when trying to write
                raise OSError("Permission denied")
            
            def get_source_name(self) -> str:
                return "PermissionScraper"
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper') as mock_anime, \
             patch('core.orchestrator.ThemesMoeScraper') as mock_themes, \
             patch('core.orchestrator.YoutubeScraper') as mock_youtube:
            
            # All scrapers raise permission errors
            mock_tv.return_value = PermissionErrorScraper()
            mock_anime.return_value = AllFailingScraper("AnimeThemes")
            mock_themes.return_value = AllFailingScraper("Themes.moe")
            mock_youtube.return_value = AllFailingScraper("YouTube")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify permission error was handled and show failed
            assert "FAILED" in result.stdout or "Failed" in result.stdout
            
            # Verify process completed
            assert result.exit_code == 0
    
    def test_disk_space_error_during_download(self, tmp_path):
        """
        Test that disk space errors are handled and logged.
        
        Validates: Requirements 9.3
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Large Show"
        show1.mkdir()
        
        class DiskSpaceErrorScraper(ThemeScraper):
            """Scraper that raises disk space error."""
            
            def search_and_download(self, show_name: str, output_path: Path) -> bool:
                raise OSError("No space left on device")
            
            def get_source_name(self) -> str:
                return "DiskSpaceScraper"
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = DiskSpaceErrorScraper()
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify disk space error was logged
            assert "Disk space" in result.stdout or "ERROR" in result.stdout
            
            # Verify show was marked as failed (check both formats)
            assert "FAILED" in result.stdout or "Failed" in result.stdout
            
            # Verify process completed
            assert result.exit_code == 0
    
    def test_multiple_shows_with_mixed_errors(self, tmp_path):
        """
        Test that errors in one show don't prevent processing others.
        
        Validates: Requirements 9.4
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Error Show"
        show2 = shows_dir / "Success Show"
        show3 = shows_dir / "Timeout Show"
        show1.mkdir()
        show2.mkdir()
        show3.mkdir()
        
        class ConditionalScraper(ThemeScraper):
            """Scraper with different behavior per show."""
            
            def search_and_download(self, show_name: str, output_path: Path) -> bool:
                if "Error" in show_name:
                    raise RuntimeError("Unexpected error")
                elif "Success" in show_name:
                    output_path.write_bytes(b"x" * 600_000)
                    return True
                elif "Timeout" in show_name:
                    raise TimeoutError("Connection timeout")
                return False
            
            def get_source_name(self) -> str:
                return "ConditionalScraper"
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper') as mock_anime, \
             patch('core.orchestrator.ThemesMoeScraper') as mock_themes, \
             patch('core.orchestrator.YoutubeScraper') as mock_youtube:
            
            # All scrapers use conditional behavior
            mock_tv.return_value = ConditionalScraper()
            mock_anime.return_value = AllFailingScraper("AnimeThemes")
            mock_themes.return_value = AllFailingScraper("Themes.moe")
            mock_youtube.return_value = AllFailingScraper("YouTube")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify success show got a theme
            assert (show2 / "theme.mp3").exists()
            
            # Verify error shows didn't get themes
            assert not (show1 / "theme.mp3").exists()
            assert not (show3 / "theme.mp3").exists()
            
            # Verify summary shows mixed results (check both formats)
            assert "SUCCESS" in result.stdout or "Success" in result.stdout
            assert "FAILED" in result.stdout or "Failed" in result.stdout
            
            # Verify process completed
            assert result.exit_code == 0
    
    def test_keyboard_interrupt_handling(self, tmp_path):
        """
        Test that keyboard interrupt (Ctrl+C) is handled gracefully.
        
        Validates: Requirements 9.5
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        with patch('core.orchestrator.Orchestrator.process_directory') as mock_process:
            mock_process.side_effect = KeyboardInterrupt()
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify keyboard interrupt exit code
            assert result.exit_code == 130
            
            # Verify cancellation message
            assert "cancelled" in result.stdout.lower()
    
    def test_unexpected_exception_handling(self, tmp_path):
        """
        Test that unexpected exceptions are caught and reported.
        
        Validates: Requirements 9.5
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        with patch('core.orchestrator.Orchestrator.process_directory') as mock_process:
            mock_process.side_effect = RuntimeError("Unexpected runtime error")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify error exit code
            assert result.exit_code == 1
            
            # Verify error message
            assert "ERROR" in result.stdout
    
    def test_verbose_mode_shows_error_details(self, tmp_path):
        """
        Test that verbose mode displays detailed error information.
        
        Validates: Requirements 10.6
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        class DetailedErrorScraper(ThemeScraper):
            """Scraper that raises detailed error."""
            
            def search_and_download(self, show_name: str, output_path: Path) -> bool:
                raise ValueError("Detailed error message with context")
            
            def get_source_name(self) -> str:
                return "DetailedErrorScraper"
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = DetailedErrorScraper()
            
            # Run with verbose flag
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir), "--verbose"])
            
            # Verify error details are shown
            assert "Error" in result.stdout or "error" in result.stdout
            
            # Verify process completed
            assert result.exit_code == 0
    
    def test_empty_directory_handling(self, tmp_path):
        """
        Test that empty directories are handled gracefully.
        
        Validates: Requirements 1.2
        """
        shows_dir = tmp_path / "empty_shows"
        shows_dir.mkdir()
        
        runner = CliRunner()
        result = runner.invoke(app, [str(shows_dir)])
        
        # Verify message about no folders
        assert "No series folders found" in result.stdout
        
        # Verify successful exit
        assert result.exit_code == 0
    
    def test_critical_error_stops_execution(self, tmp_path):
        """
        Test that CriticalError stops execution immediately.
        
        Validates: Requirements 9.5
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        with patch('core.orchestrator.Orchestrator.process_directory') as mock_process:
            mock_process.side_effect = CriticalError("Critical system error")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify critical error exit code
            assert result.exit_code == 1
            
            # Verify critical error message
            assert "CRITICAL ERROR" in result.stdout
    
    def test_network_timeout_with_retry_exhaustion(self, tmp_path):
        """
        Test that after retry exhaustion, scraper moves to next source.
        
        Validates: Requirements 9.1
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Retry Show"
        show1.mkdir()
        
        class RetryExhaustionScraper(ThemeScraper):
            """Scraper that always times out."""
            
            def __init__(self, name):
                self.name = name
                self.attempts = 0
            
            def search_and_download(self, show_name: str, output_path: Path) -> bool:
                self.attempts += 1
                raise TimeoutError("Network timeout")
            
            def get_source_name(self) -> str:
                return self.name
        
        class SuccessScraper(ThemeScraper):
            """Scraper that succeeds."""
            
            def search_and_download(self, show_name: str, output_path: Path) -> bool:
                output_path.write_bytes(b"x" * 600_000)
                return True
            
            def get_source_name(self) -> str:
                return "SuccessScraper"
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper') as mock_anime, \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            # First scraper times out, second succeeds
            mock_tv.return_value = RetryExhaustionScraper("TelevisionTunes")
            mock_anime.return_value = SuccessScraper()
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify fallback to next scraper worked
            theme_file = show1 / "theme.mp3"
            assert theme_file.exists()
            
            # Verify success
            assert "SUCCESS" in result.stdout
            assert result.exit_code == 0
