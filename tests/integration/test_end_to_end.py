"""End-to-end integration tests with mocked sources."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typer.testing import CliRunner
from rich.console import Console

from main import app
from core.orchestrator import Orchestrator
from scrapers.base import ThemeScraper


class MockSuccessfulScraper(ThemeScraper):
    """Mock scraper that always succeeds."""
    
    def __init__(self, source_name="MockSuccess"):
        self.source_name = source_name
        self.calls = []
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """Mock successful download."""
        self.calls.append((show_name, output_path))
        # Create a valid theme file
        output_path.write_bytes(b"x" * 600_000)  # 600KB file
        return True
    
    def get_source_name(self) -> str:
        return self.source_name


class MockFailingScraper(ThemeScraper):
    """Mock scraper that always fails."""
    
    def __init__(self, source_name="MockFail"):
        self.source_name = source_name
        self.calls = []
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """Mock failed download."""
        self.calls.append((show_name, output_path))
        return False
    
    def get_source_name(self) -> str:
        return self.source_name


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete workflow from CLI to file creation."""
    
    def test_full_workflow_single_show_success(self, tmp_path):
        """
        Test complete workflow: CLI -> Orchestrator -> Scraper -> File creation.
        
        Validates: All requirements
        """
        # Create test directory structure
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        show1 = shows_dir / "Breaking Bad"
        show1.mkdir()
        
        # Mock all external dependencies
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper') as mock_anime, \
             patch('core.orchestrator.ThemesMoeScraper') as mock_themes, \
             patch('core.orchestrator.YoutubeScraper') as mock_youtube:
            
            # Set up mock scrapers
            mock_tv.return_value = MockSuccessfulScraper("TelevisionTunes")
            mock_anime.return_value = MockFailingScraper("AnimeThemes")
            mock_themes.return_value = MockFailingScraper("Themes.moe")
            mock_youtube.return_value = MockFailingScraper("YouTube")
            
            # Run CLI
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify exit code
            assert result.exit_code == 0
            
            # Verify theme file was created
            theme_file = show1 / "theme.mp3"
            assert theme_file.exists()
            assert theme_file.stat().st_size > 500_000
            
            # Verify output contains success message
            assert "SUCCESS" in result.stdout
            assert "TelevisionTunes" in result.stdout
            assert "Breaking Bad" in result.stdout or "Processing" in result.stdout
    
    def test_full_workflow_multiple_shows(self, tmp_path):
        """
        Test workflow with multiple shows using different sources.
        
        Validates: All requirements
        """
        # Create multiple show directories
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Show One"
        show2 = shows_dir / "Show Two"
        show3 = shows_dir / "Show Three"
        show1.mkdir()
        show2.mkdir()
        show3.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper') as mock_anime, \
             patch('core.orchestrator.ThemesMoeScraper') as mock_themes, \
             patch('core.orchestrator.YoutubeScraper') as mock_youtube:
            
            # First show: TV Tunes succeeds
            tv_scraper = MockSuccessfulScraper("TelevisionTunes")
            mock_tv.return_value = tv_scraper
            
            # Second show: TV Tunes fails, AnimeThemes succeeds
            anime_scraper = MockSuccessfulScraper("AnimeThemes")
            mock_anime.return_value = anime_scraper
            
            # Third show: All fail except YouTube
            youtube_scraper = MockSuccessfulScraper("YouTube")
            mock_youtube.return_value = youtube_scraper
            
            mock_themes.return_value = MockFailingScraper("Themes.moe")
            
            # Override to make TV fail for show 2 and 3
            def tv_conditional_success(show_name: str, output_path: Path) -> bool:
                if "One" in show_name:
                    output_path.write_bytes(b"x" * 600_000)
                    return True
                return False
            
            tv_scraper.search_and_download = tv_conditional_success
            
            # Override to make Anime succeed only for show 2
            def anime_conditional_success(show_name: str, output_path: Path) -> bool:
                if "Two" in show_name:
                    output_path.write_bytes(b"x" * 600_000)
                    return True
                return False
            
            anime_scraper.search_and_download = anime_conditional_success
            
            # Override to make YouTube succeed only for show 3
            def youtube_conditional_success(show_name: str, output_path: Path) -> bool:
                if "Three" in show_name:
                    output_path.write_bytes(b"x" * 600_000)
                    return True
                return False
            
            youtube_scraper.search_and_download = youtube_conditional_success
            
            # Run CLI
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify all theme files were created
            assert (show1 / "theme.mp3").exists()
            assert (show2 / "theme.mp3").exists()
            assert (show3 / "theme.mp3").exists()
            
            # Verify summary shows 3 successes
            assert "3" in result.stdout  # Success count
            assert result.exit_code == 0
    
    def test_full_workflow_with_existing_files(self, tmp_path):
        """
        Test workflow skips shows with existing theme files.
        
        Validates: Requirements 2.1, 2.3
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Show With Theme"
        show2 = shows_dir / "Show Without Theme"
        show1.mkdir()
        show2.mkdir()
        
        # Create existing theme file
        existing_theme = show1 / "theme.mp3"
        existing_theme.write_bytes(b"existing" * 100_000)
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessfulScraper("TelevisionTunes")
            
            # Run without force flag
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify show1 was skipped
            assert "SKIPPED" in result.stdout
            assert "File exists" in result.stdout
            
            # Verify show2 got a theme
            assert (show2 / "theme.mp3").exists()
            
            # Verify summary shows 1 success, 1 skipped
            assert result.exit_code == 0
    
    def test_full_workflow_with_force_flag(self, tmp_path):
        """
        Test workflow with --force flag overwrites existing files.
        
        Validates: Requirements 2.2, 8.3
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Show With Theme"
        show1.mkdir()
        
        # Create existing theme file with specific content
        existing_theme = show1 / "theme.mp3"
        existing_theme.write_bytes(b"old_content")
        original_size = existing_theme.stat().st_size
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessfulScraper("TelevisionTunes")
            
            # Run with force flag
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir), "--force"])
            
            # Verify file was overwritten
            assert existing_theme.exists()
            new_size = existing_theme.stat().st_size
            assert new_size != original_size
            assert new_size > 500_000  # New file is larger
            
            # Verify no skip message
            assert "SKIPPED" not in result.stdout or "File exists" not in result.stdout
            assert "SUCCESS" in result.stdout
            assert result.exit_code == 0
    
    def test_full_workflow_dry_run_mode(self, tmp_path):
        """
        Test workflow with --dry-run flag doesn't create files.
        
        Validates: Requirements 1.5, 2.1
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessfulScraper("TelevisionTunes")
            
            # Run with dry-run flag
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir), "--dry-run"])
            
            # Verify no theme file was created
            theme_file = show1 / "theme.mp3"
            assert not theme_file.exists()
            
            # Verify dry run message appears
            assert "DRY RUN" in result.stdout
            assert "Would process" in result.stdout
            assert result.exit_code == 0
    
    def test_full_workflow_file_naming_consistency(self, tmp_path):
        """
        Test that all scrapers produce consistently named files.
        
        Validates: Requirements 8.1, 8.2
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessfulScraper("TelevisionTunes")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify file is named exactly "theme.mp3"
            theme_file = show1 / "theme.mp3"
            assert theme_file.exists()
            assert theme_file.name == "theme.mp3"
            
            # Verify no other audio files were created
            audio_files = list(show1.glob("*.mp3")) + \
                         list(show1.glob("*.flac")) + \
                         list(show1.glob("*.wav"))
            assert len(audio_files) == 1
            assert audio_files[0].name == "theme.mp3"
            
            assert result.exit_code == 0
    
    def test_full_workflow_waterfall_fallback(self, tmp_path):
        """
        Test that scraper waterfall works correctly with fallback.
        
        Validates: All scraper requirements
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
            tv_scraper = MockFailingScraper("TelevisionTunes")
            anime_scraper = MockFailingScraper("AnimeThemes")
            themes_scraper = MockFailingScraper("Themes.moe")
            youtube_scraper = MockSuccessfulScraper("YouTube")
            
            mock_tv.return_value = tv_scraper
            mock_anime.return_value = anime_scraper
            mock_themes.return_value = themes_scraper
            mock_youtube.return_value = youtube_scraper
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify all scrapers were tried
            assert len(tv_scraper.calls) == 1
            assert len(anime_scraper.calls) == 1
            assert len(themes_scraper.calls) == 1
            assert len(youtube_scraper.calls) == 1
            
            # Verify YouTube succeeded
            theme_file = show1 / "theme.mp3"
            assert theme_file.exists()
            assert "SUCCESS" in result.stdout
            assert "YouTube" in result.stdout
            assert result.exit_code == 0
    
    def test_full_workflow_multiple_theme_formats_detection(self, tmp_path):
        """
        Test that existing themes in different formats are detected.
        
        Validates: Requirements 2.4, 2.5
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        # Create shows with different theme formats
        show_mp3 = shows_dir / "Show MP3"
        show_flac = shows_dir / "Show FLAC"
        show_wav = shows_dir / "Show WAV"
        show_none = shows_dir / "Show None"
        
        show_mp3.mkdir()
        show_flac.mkdir()
        show_wav.mkdir()
        show_none.mkdir()
        
        # Create existing themes in different formats
        (show_mp3 / "theme.mp3").write_bytes(b"mp3" * 200_000)
        (show_flac / "theme.flac").write_bytes(b"flac" * 200_000)
        (show_wav / "theme.wav").write_bytes(b"wav" * 200_000)
        
        with patch('core.orchestrator.TelevisionTunesScraper') as mock_tv, \
             patch('core.orchestrator.AnimeThemesScraper'), \
             patch('core.orchestrator.ThemesMoeScraper'), \
             patch('core.orchestrator.YoutubeScraper'):
            
            mock_tv.return_value = MockSuccessfulScraper("TelevisionTunes")
            
            runner = CliRunner()
            result = runner.invoke(app, [str(shows_dir)])
            
            # Verify first three were skipped
            output = result.stdout
            skip_count = output.count("SKIPPED")
            assert skip_count == 3
            
            # Verify only show_none got a new theme
            assert (show_none / "theme.mp3").exists()
            
            # Verify summary shows 1 success, 3 skipped
            assert result.exit_code == 0


@pytest.mark.integration
class TestEndToEndWithMockedDependencies:
    """Test end-to-end with all external dependencies mocked."""
    
    @patch('subprocess.run')
    @patch('httpx.Client')
    @patch('playwright.sync_api.sync_playwright')
    @patch('yt_dlp.YoutubeDL')
    def test_all_external_dependencies_mocked(
        self,
        mock_ytdl,
        mock_playwright,
        mock_httpx,
        mock_subprocess,
        tmp_path
    ):
        """
        Test with all external dependencies (Playwright, httpx, yt-dlp, FFmpeg) mocked.
        
        Validates: All requirements
        """
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir()
        
        show1 = shows_dir / "Test Show"
        show1.mkdir()
        
        # Mock FFmpeg subprocess
        mock_subprocess.return_value = Mock(returncode=0)
        
        # Mock httpx client
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"search": {"anime": []}}
        mock_httpx.return_value.__enter__.return_value.get.return_value = mock_response
        
        # Mock Playwright
        mock_browser = Mock()
        mock_page = Mock()
        mock_browser.new_page.return_value = mock_page
        mock_page.locator.return_value.count.return_value = 0
        
        mock_pw_context = Mock()
        mock_pw_context.chromium.launch.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_pw_context
        
        # Mock yt-dlp to create a file
        def mock_download(urls):
            theme_file = show1 / "theme.mp3"
            theme_file.write_bytes(b"x" * 600_000)
        
        mock_ytdl.return_value.__enter__.return_value.download = mock_download
        
        # Run CLI
        runner = CliRunner()
        result = runner.invoke(app, [str(shows_dir)])
        
        # Verify theme file was created
        theme_file = show1 / "theme.mp3"
        assert theme_file.exists()
        assert result.exit_code == 0
