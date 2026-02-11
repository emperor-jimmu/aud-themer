"""Unit tests for dependency validation."""

import subprocess
from unittest.mock import patch, MagicMock
import pytest
from rich.console import Console
from core.dependencies import check_ffmpeg, check_playwright_browsers, validate_dependencies


@pytest.mark.unit
class TestFFmpegCheck:
    """Tests for FFmpeg availability checking."""
    
    def test_ffmpeg_available(self):
        """Test FFmpeg check when FFmpeg is installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert check_ffmpeg() is True
            mock_run.assert_called_once()
    
    def test_ffmpeg_not_found(self):
        """Test FFmpeg check when FFmpeg is not installed."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            assert check_ffmpeg() is False
    
    def test_ffmpeg_timeout(self):
        """Test FFmpeg check when command times out."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('ffmpeg', 5)):
            assert check_ffmpeg() is False
    
    def test_ffmpeg_error_code(self):
        """Test FFmpeg check when command returns error code."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert check_ffmpeg() is False


@pytest.mark.unit
class TestPlaywrightCheck:
    """Tests for Playwright browser availability checking."""
    
    def test_playwright_browsers_available(self):
        """Test Playwright check when browsers are installed."""
        with patch('playwright.sync_api.sync_playwright') as mock_playwright:
            mock_context = MagicMock()
            mock_browser = MagicMock()
            mock_context.__enter__.return_value.chromium.launch.return_value = mock_browser
            mock_playwright.return_value = mock_context
            
            assert check_playwright_browsers() is True
            mock_browser.close.assert_called_once()
    
    def test_playwright_browser_not_installed(self):
        """Test Playwright check when browser executable is missing."""
        with patch('playwright.sync_api.sync_playwright') as mock_playwright:
            mock_context = MagicMock()
            mock_context.__enter__.return_value.chromium.launch.side_effect = \
                Exception("Executable doesn't exist at /path/to/chromium")
            mock_playwright.return_value = mock_context
            
            assert check_playwright_browsers() is False
    
    def test_playwright_browser_not_installed_alt_message(self):
        """Test Playwright check with alternative error message."""
        with patch('playwright.sync_api.sync_playwright') as mock_playwright:
            mock_context = MagicMock()
            mock_context.__enter__.return_value.chromium.launch.side_effect = \
                Exception("Browser is not installed. Run 'playwright install chromium'")
            mock_playwright.return_value = mock_context
            
            assert check_playwright_browsers() is False
    
    def test_playwright_other_error(self):
        """Test Playwright check with non-installation error."""
        with patch('playwright.sync_api.sync_playwright') as mock_playwright:
            mock_context = MagicMock()
            mock_context.__enter__.return_value.chromium.launch.side_effect = \
                Exception("Some other error")
            mock_playwright.return_value = mock_context
            
            # Other errors should return True (assume browsers installed)
            assert check_playwright_browsers() is True


@pytest.mark.unit
class TestValidateDependencies:
    """Tests for complete dependency validation."""
    
    def test_all_dependencies_available(self):
        """Test validation when all dependencies are available."""
        console = Console()
        
        with patch('core.dependencies.check_ffmpeg', return_value=True), \
             patch('core.dependencies.check_playwright_browsers', return_value=True):
            # Should not raise SystemExit
            validate_dependencies(console)
    
    def test_ffmpeg_missing(self):
        """Test validation when FFmpeg is missing."""
        console = Console()
        
        with patch('core.dependencies.check_ffmpeg', return_value=False), \
             patch('core.dependencies.check_playwright_browsers', return_value=True), \
             pytest.raises(SystemExit) as exc_info:
            validate_dependencies(console)
        
        assert exc_info.value.code == 1
    
    def test_playwright_missing(self):
        """Test validation when Playwright browsers are missing."""
        console = Console()
        
        with patch('core.dependencies.check_ffmpeg', return_value=True), \
             patch('core.dependencies.check_playwright_browsers', return_value=False), \
             pytest.raises(SystemExit) as exc_info:
            validate_dependencies(console)
        
        assert exc_info.value.code == 1
    
    def test_all_dependencies_missing(self):
        """Test validation when all dependencies are missing."""
        console = Console()
        
        with patch('core.dependencies.check_ffmpeg', return_value=False), \
             patch('core.dependencies.check_playwright_browsers', return_value=False), \
             pytest.raises(SystemExit) as exc_info:
            validate_dependencies(console)
        
        assert exc_info.value.code == 1
