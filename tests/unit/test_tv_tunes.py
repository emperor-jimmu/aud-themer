"""Unit tests for TelevisionTunes scraper."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from scrapers.tv_tunes import TelevisionTunesScraper


@pytest.mark.unit
def test_successful_search_and_download():
    """
    Test successful search and download flow.
    
    Validates: Requirements 3.1-3.6
    """
    scraper = TelevisionTunesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        # Mock Playwright components
        with patch('scrapers.tv_tunes.sync_playwright') as mock_playwright:
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            mock_results = MagicMock()
            mock_result_item = MagicMock()
            mock_download_link = MagicMock()
            mock_download = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock search input
            mock_page.locator.side_effect = lambda selector: {
                "#search_field": mock_search_input,
                ".result-item": mock_results,
                "a[href$='.mp3']": mock_download_link
            }.get(selector, MagicMock())
            
            # Mock search results
            mock_results.count.return_value = 1
            mock_result_item.text_content.return_value = "Test Show Theme"
            mock_results.first = mock_result_item
            
            # Mock download link
            mock_download_link.count.return_value = 1
            mock_download_link.first = mock_download_link
            
            # Mock download
            mock_page.expect_download.return_value.__enter__.return_value = MagicMock(
                value=mock_download
            )
            
            # Create a valid file when save_as is called
            def save_as_side_effect(path):
                Path(path).write_bytes(b'0' * 600_000)  # 600KB file
            
            mock_download.save_as.side_effect = save_as_side_effect
            
            # Execute the test
            result = scraper.search_and_download("Test Show", output_path)
            
            # Verify success
            assert result is True
            assert output_path.exists()
            assert output_path.stat().st_size > 500_000


@pytest.mark.unit
def test_handling_no_results():
    """
    Test handling of no search results.
    
    Validates: Requirements 3.1-3.6
    """
    scraper = TelevisionTunesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.tv_tunes.sync_playwright') as mock_playwright:
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            mock_results = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock search input
            mock_page.locator.side_effect = lambda selector: {
                "#search_field": mock_search_input,
                ".result-item": mock_results
            }.get(selector, MagicMock())
            
            # Mock no search results
            mock_results.count.return_value = 0
            
            # Execute the test
            result = scraper.search_and_download("Nonexistent Show", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_handling_missing_download_link():
    """
    Test handling of missing download link on song page.
    
    Validates: Requirements 3.1-3.6
    """
    scraper = TelevisionTunesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.tv_tunes.sync_playwright') as mock_playwright:
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            mock_results = MagicMock()
            mock_result_item = MagicMock()
            mock_download_link = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock search input and results
            mock_page.locator.side_effect = lambda selector: {
                "#search_field": mock_search_input,
                ".result-item": mock_results,
                "a[href$='.mp3']": mock_download_link
            }.get(selector, MagicMock())
            
            # Mock search results
            mock_results.count.return_value = 1
            mock_result_item.text_content.return_value = "Test Show Theme"
            mock_results.first = mock_result_item
            
            # Mock missing download link
            mock_download_link.count.return_value = 0
            
            # Execute the test
            result = scraper.search_and_download("Test Show", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_timeout_handling():
    """
    Test handling of network timeout.
    
    Validates: Requirements 3.1-3.6, 9.1
    """
    scraper = TelevisionTunesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.tv_tunes.sync_playwright') as mock_playwright:
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
            result = scraper.search_and_download("Test Show", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_file_size_validation():
    """
    Test that files smaller than 500KB are rejected.
    
    Validates: Requirements 7.4, 8.4
    """
    scraper = TelevisionTunesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.tv_tunes.sync_playwright') as mock_playwright:
            # Set up mock chain
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_search_input = MagicMock()
            mock_results = MagicMock()
            mock_result_item = MagicMock()
            mock_download_link = MagicMock()
            mock_download = MagicMock()
            
            # Configure the mock chain
            mock_playwright.return_value.__enter__.return_value = mock_p
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Mock search input
            mock_page.locator.side_effect = lambda selector: {
                "#search_field": mock_search_input,
                ".result-item": mock_results,
                "a[href$='.mp3']": mock_download_link
            }.get(selector, MagicMock())
            
            # Mock search results
            mock_results.count.return_value = 1
            mock_result_item.text_content.return_value = "Test Show Theme"
            mock_results.first = mock_result_item
            
            # Mock download link
            mock_download_link.count.return_value = 1
            mock_download_link.first = mock_download_link
            
            # Mock download
            mock_page.expect_download.return_value.__enter__.return_value = MagicMock(
                value=mock_download
            )
            
            # Create a file that's too small (under 500KB)
            def save_as_side_effect(path):
                Path(path).write_bytes(b'0' * 100_000)  # Only 100KB
            
            mock_download.save_as.side_effect = save_as_side_effect
            
            # Execute the test
            result = scraper.search_and_download("Test Show", output_path)
            
            # Verify failure and file cleanup
            assert result is False
            assert not output_path.exists()  # File should be deleted


@pytest.mark.unit
def test_rate_limiting_delay():
    """
    Test that rate limiting delay is applied after scraping.
    
    Validates: Requirements 9.4
    """
    scraper = TelevisionTunesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('scrapers.tv_tunes.sync_playwright') as mock_playwright, \
             patch('scrapers.tv_tunes.time.sleep') as mock_sleep, \
             patch('scrapers.tv_tunes.random.uniform') as mock_uniform:
            
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
            mock_uniform.return_value = 2.0
            
            # Execute the test
            result = scraper.search_and_download("Test Show", output_path)
            
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
    
    Validates: Requirements 3.1-3.6
    """
    scraper = TelevisionTunesScraper()
    assert scraper.get_source_name() == "TelevisionTunes"


@pytest.mark.unit
def test_exact_match_preferred_over_first_result():
    """
    Test that exact matches are preferred over first result.
    
    Validates: Requirements 3.3
    """
    scraper = TelevisionTunesScraper()
    
    # Create mock page with multiple results
    mock_page = Mock()
    mock_results = Mock()
    
    # Create three mock results
    mock_item1 = Mock()
    mock_item1.text_content.return_value = "Random Show"
    
    mock_item2 = Mock()
    mock_item2.text_content.return_value = "Another Random Show"
    
    mock_item3 = Mock()
    mock_item3.text_content.return_value = "Breaking Bad Theme"
    
    mock_results.count.return_value = 3
    mock_results.nth.side_effect = lambda i: [mock_item1, mock_item2, mock_item3][i]
    mock_results.first = mock_item1
    
    mock_page.locator.return_value = mock_results
    
    # Search for "Breaking Bad"
    result = scraper._find_best_match(mock_page, "Breaking Bad")
    
    # Should return the third item (exact match), not the first
    assert result == mock_item3
