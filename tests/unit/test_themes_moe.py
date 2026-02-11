"""Unit tests for Themes.moe scraper."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from scrapers.themes_moe import ThemesMoeScraper


@pytest.mark.unit
def test_successful_search_and_download_audio():
    """
    Test successful search and download flow with audio file.

    Validates: Requirements 5.1-5.6
    """
    scraper = ThemesMoeScraper()

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"

        with patch('scrapers.themes_moe.sync_playwright') as mock_playwright, \
             patch('scrapers.themes_moe.time.sleep'), \
             patch('scrapers.themes_moe.random.uniform', return_value=1.0):

            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            mock_media = MagicMock()
            mock_response = MagicMock()
            mock_no_results = MagicMock()

            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page

            # Mock search input exists
            def locator_side_effect(selector):
                if "role=combobox" in selector:
                    return mock_search_input
                elif "no results" in selector.lower() or "no anime found" in selector.lower():
                    return mock_no_results
                elif selector == "table":
                    mock_table = MagicMock()
                    mock_table.count.return_value = 1
                    return mock_table
                elif "table a:has-text('OP1')" in selector or "table a:has-text('OP')" in selector:
                    mock_op_link = MagicMock()
                    mock_op_link.count.return_value = 1
                    mock_op_link.first = MagicMock()
                    mock_op_link.first.get_attribute.return_value = "https://themes.moe/audio/test.mp3"
                    return mock_op_link
                return MagicMock()

            mock_page.locator.side_effect = locator_side_effect
            mock_page.wait_for_selector = MagicMock()  # Mock wait_for_selector
            mock_page.wait_for_timeout = MagicMock()  # Mock wait_for_timeout

            mock_search_input.count.return_value = 1
            mock_search_input.first = mock_search_input

            # Mock no results message not present
            mock_no_results.count.return_value = 0

            # Mock successful download
            mock_response.status = 200
            mock_response.body.return_value = b'0' * 600_000  # 600KB audio file
            mock_page.request.get.return_value = mock_response

            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)

            # Verify success
            assert result is True
            assert output_path.exists()
            assert output_path.stat().st_size > 500_000


@pytest.mark.unit
def test_successful_search_and_download_video():
    """
    Test successful search and download flow with video file requiring extraction.

    Validates: Requirements 5.1-5.6
    """
    scraper = ThemesMoeScraper()

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"

        with patch('scrapers.themes_moe.sync_playwright') as mock_playwright, \
             patch('scrapers.themes_moe.subprocess.run') as mock_subprocess, \
             patch('scrapers.themes_moe.time.sleep'), \
             patch('scrapers.themes_moe.random.uniform', return_value=1.0):

            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            mock_media = MagicMock()
            mock_response = MagicMock()
            mock_no_results = MagicMock()

            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page

            # Mock search input exists
            def locator_side_effect(selector):
                if "input[type='search']" in selector or "input[placeholder" in selector:
                    return mock_search_input
                elif "audio source" in selector or "video source" in selector:
                    return mock_media
                elif "no results" in selector.lower() or "not found" in selector.lower():
                    return mock_no_results
                return MagicMock()

            mock_page.locator.side_effect = locator_side_effect

            mock_search_input.count.return_value = 1
            mock_search_input.first = mock_search_input

            # Mock no results message not present
            mock_no_results.count.return_value = 0

            # Mock media element with video URL
            mock_media.count.return_value = 1
            mock_media_element = MagicMock()
            mock_media_element.get_attribute.return_value = "https://themes.moe/video/test.webm"
            mock_media.first = mock_media_element

            # Mock successful video download
            mock_response.status = 200
            mock_response.body.return_value = b'0' * 1_000_000  # 1MB video file
            mock_page.request.get.return_value = mock_response

            # Mock FFmpeg extraction
            mock_ffmpeg_result = Mock()
            mock_ffmpeg_result.returncode = 0

            def subprocess_side_effect(*args, **kwargs):
                output_path.write_bytes(b'0' * 600_000)  # 600KB audio file
                return mock_ffmpeg_result

            mock_subprocess.side_effect = subprocess_side_effect

            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)

            # Verify success
            assert result is True
            assert output_path.exists()
            assert output_path.stat().st_size > 500_000


@pytest.mark.unit
def test_missing_search_functionality():
    """
    Test handling when search functionality doesn't exist.
    
    Validates: Requirements 5.1-5.6
    """
    scraper = ThemesMoeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.themes_moe.sync_playwright') as mock_playwright:
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock no search input found
            mock_page.locator.return_value = mock_search_input
            mock_search_input.count.return_value = 0
            
            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_missing_media_element():
    """
    Test handling when no media element is found.
    
    Validates: Requirements 5.1-5.6
    """
    scraper = ThemesMoeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.themes_moe.sync_playwright') as mock_playwright:
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            mock_media = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock search input exists
            mock_page.locator.side_effect = lambda selector: {
                "input[type='search'], input[placeholder*='search' i]": mock_search_input,
                "audio source, video source": mock_media
            }.get(selector, MagicMock())
            
            mock_search_input.count.return_value = 1
            mock_search_input.first = mock_search_input
            
            # Mock no media element found
            mock_media.count.return_value = 0
            
            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_timeout_handling():
    """
    Test handling of network timeout.
    
    Validates: Requirements 5.1-5.6, 9.1
    """
    scraper = ThemesMoeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.themes_moe.sync_playwright') as mock_playwright:
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock timeout error
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            mock_page.goto.side_effect = PlaywrightTimeoutError("Timeout")
            
            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_file_size_validation():
    """
    Test that files smaller than 500KB are rejected.
    
    Validates: Requirements 7.4, 8.4
    """
    scraper = ThemesMoeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.themes_moe.sync_playwright') as mock_playwright:
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            mock_media = MagicMock()
            mock_response = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock search input exists
            mock_page.locator.side_effect = lambda selector: {
                "input[type='search'], input[placeholder*='search' i]": mock_search_input,
                "audio source, video source": mock_media
            }.get(selector, MagicMock())
            
            mock_search_input.count.return_value = 1
            mock_search_input.first = mock_search_input
            
            # Mock media element
            mock_media.count.return_value = 1
            mock_media.get_attribute.return_value = "https://themes.moe/audio/test.mp3"
            
            # Mock download with file that's too small
            mock_response.status = 200
            mock_response.body.return_value = b'0' * 100_000  # Only 100KB
            mock_page.request.get.return_value = mock_response
            
            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify failure and file cleanup
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_rate_limiting_delay():
    """
    Test that rate limiting delay is applied after scraping.
    
    Validates: Requirements 9.4
    """
    scraper = ThemesMoeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.themes_moe.sync_playwright') as mock_playwright, \
             patch('scrapers.themes_moe.time.sleep') as mock_sleep, \
             patch('scrapers.themes_moe.random.uniform') as mock_uniform:
            
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock timeout to trigger finally block quickly
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            mock_page.goto.side_effect = PlaywrightTimeoutError("Timeout")
            
            # Mock random delay
            mock_uniform.return_value = 2.5
            
            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify rate limiting was applied
            # With retry decorator (3 attempts) and rate limiting in finally block,
            # we expect: uniform called 3 times (once per attempt in finally block)
            # and sleep called for backoff + rate limiting
            assert mock_uniform.call_count == 3
            assert all(call[0] == (1, 3) for call in mock_uniform.call_args_list)
            # Sleep is called for both backoff delays and rate limiting delays
            assert mock_sleep.call_count >= 3  # At least 3 for rate limiting


@pytest.mark.unit
def test_get_source_name():
    """
    Test that get_source_name returns correct identifier.
    
    Validates: Requirements 5.1-5.6
    """
    scraper = ThemesMoeScraper()
    assert scraper.get_source_name() == "Themes.moe"


@pytest.mark.unit
def test_ffmpeg_extraction_failure():
    """
    Test handling when FFmpeg extraction fails.
    
    Validates: Requirements 5.1-5.6, 7.1
    """
    scraper = ThemesMoeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.themes_moe.sync_playwright') as mock_playwright, \
             patch('scrapers.themes_moe.subprocess.run') as mock_subprocess:
            
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            mock_media = MagicMock()
            mock_response = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock search input exists
            mock_page.locator.side_effect = lambda selector: {
                "input[type='search'], input[placeholder*='search' i]": mock_search_input,
                "audio source, video source": mock_media
            }.get(selector, MagicMock())
            
            mock_search_input.count.return_value = 1
            mock_search_input.first = mock_search_input
            
            # Mock media element with video URL
            mock_media.count.return_value = 1
            mock_media.get_attribute.return_value = "https://themes.moe/video/test.mp4"
            
            # Mock successful download
            mock_response.status = 200
            mock_response.body.return_value = b'0' * 600_000
            mock_page.request.get.return_value = mock_response
            
            # Mock FFmpeg failure
            mock_subprocess_result = MagicMock()
            mock_subprocess_result.returncode = 1  # Non-zero indicates failure
            mock_subprocess.return_value = mock_subprocess_result
            
            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_download_failure():
    """
    Test handling when media download fails.
    
    Validates: Requirements 5.1-5.6
    """
    scraper = ThemesMoeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.themes_moe.sync_playwright') as mock_playwright:
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            mock_media = MagicMock()
            mock_response = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock search input exists
            mock_page.locator.side_effect = lambda selector: {
                "input[type='search'], input[placeholder*='search' i]": mock_search_input,
                "audio source, video source": mock_media
            }.get(selector, MagicMock())
            
            mock_search_input.count.return_value = 1
            mock_search_input.first = mock_search_input
            
            # Mock media element
            mock_media.count.return_value = 1
            mock_media.get_attribute.return_value = "https://themes.moe/audio/test.mp3"
            
            # Mock failed download (non-200 status)
            mock_response.status = 404
            mock_page.request.get.return_value = mock_response
            
            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()
