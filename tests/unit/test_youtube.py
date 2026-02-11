"""Unit tests for YouTube scraper."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Mock yt_dlp before importing the scraper
import sys
sys.modules['yt_dlp'] = MagicMock()

from scrapers.youtube import YoutubeScraper


@pytest.mark.unit
def test_successful_youtube_search_and_download():
    """
    Test successful YouTube search and download flow.
    
    Validates: Requirements 6.1-6.5
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            # Mock successful download
            def download_side_effect(urls):
                # Simulate yt-dlp creating the output file
                output_path.write_bytes(b'0' * 600_000)  # 600KB file
                return None
            
            mock_ytdl.download.side_effect = download_side_effect
            
            # Execute the test
            result = scraper.search_and_download("Test Show", output_path)
            
            # Verify success
            assert result is True
            assert output_path.exists()
            assert output_path.stat().st_size > 500_000
            
            # Verify download was called with correct query
            mock_ytdl.download.assert_called_once()
            call_args = mock_ytdl.download.call_args[0][0]
            assert len(call_args) == 1
            assert "Test Show" in call_args[0]
            assert "full theme song" in call_args[0]


@pytest.mark.unit
def test_ytdlp_configuration():
    """
    Test that yt-dlp is configured with correct options.
    
    Validates: Requirements 6.1-6.5
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            def download_side_effect(urls):
                output_path.write_bytes(b'0' * 600_000)
                return None
            
            mock_ytdl.download.side_effect = download_side_effect
            
            # Execute
            scraper.search_and_download("Test Show", output_path)
            
            # Verify yt-dlp configuration
            mock_ytdl_class.assert_called_once()
            config = mock_ytdl_class.call_args[0][0]
            
            # Check format selection
            assert config['format'] == 'bestaudio/best'
            
            # Check audio extraction settings
            assert 'postprocessors' in config
            assert len(config['postprocessors']) == 1
            postprocessor = config['postprocessors'][0]
            assert postprocessor['key'] == 'FFmpegExtractAudio'
            assert postprocessor['preferredcodec'] == 'mp3'
            assert postprocessor['preferredquality'] == '160'  # 160kbps minimum
            
            # Check search settings
            assert config['default_search'] == 'ytsearch1'  # Single result
            assert config['noplaylist'] is True  # No playlists
            
            # Check output settings
            assert config['quiet'] is True
            assert config['no_warnings'] is True


@pytest.mark.unit
def test_query_formatting():
    """
    Test that search query is formatted correctly.
    
    Validates: Requirements 6.1, 6.2
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            def download_side_effect(urls):
                output_path.write_bytes(b'0' * 600_000)
                return None
            
            mock_ytdl.download.side_effect = download_side_effect
            
            # Execute with specific show name
            scraper.search_and_download("My Favorite Show", output_path)
            
            # Verify query format
            call_args = mock_ytdl.download.call_args[0][0]
            query = call_args[0]
            
            assert query == "My Favorite Show full theme song"


@pytest.mark.unit
def test_audio_extraction_bitrate():
    """
    Test that audio extraction uses 160kbps minimum quality.
    
    Validates: Requirements 6.4, 7.2
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            def download_side_effect(urls):
                output_path.write_bytes(b'0' * 600_000)
                return None
            
            mock_ytdl.download.side_effect = download_side_effect
            
            # Execute
            scraper.search_and_download("Test Show", output_path)
            
            # Verify bitrate configuration
            config = mock_ytdl_class.call_args[0][0]
            postprocessor = config['postprocessors'][0]
            
            assert postprocessor['preferredquality'] == '160'


@pytest.mark.unit
def test_single_video_download_no_playlists():
    """
    Test that only single videos are downloaded, not playlists.
    
    Validates: Requirements 6.5
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            def download_side_effect(urls):
                output_path.write_bytes(b'0' * 600_000)
                return None
            
            mock_ytdl.download.side_effect = download_side_effect
            
            # Execute
            scraper.search_and_download("Test Show", output_path)
            
            # Verify configuration
            config = mock_ytdl_class.call_args[0][0]
            
            # Check single result search
            assert config['default_search'] == 'ytsearch1'
            
            # Check no playlists
            assert config['noplaylist'] is True


@pytest.mark.unit
def test_handling_download_failure():
    """
    Test handling when yt-dlp download fails.
    
    Validates: Requirements 6.1-6.5
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            # Simulate download failure (no file created)
            mock_ytdl.download.return_value = None
            
            # Execute the test
            result = scraper.search_and_download("Nonexistent Show", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_handling_ytdlp_exception():
    """
    Test handling of yt-dlp exceptions.
    
    Validates: Requirements 6.1-6.5
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            # Raise an exception
            mock_ytdl_class.side_effect = Exception("Network error")
            
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
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            # Create file that's too small
            def download_side_effect(urls):
                output_path.write_bytes(b'0' * 100_000)  # Only 100KB
                return None
            
            mock_ytdl.download.side_effect = download_side_effect
            
            # Execute the test
            result = scraper.search_and_download("Test Show", output_path)
            
            # Verify failure and file cleanup
            assert result is False
            assert not output_path.exists()  # File should be deleted


@pytest.mark.unit
def test_output_file_naming():
    """
    Test that output file is named correctly as theme.mp3.
    
    Validates: Requirements 7.3, 8.1
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            def download_side_effect(urls):
                output_path.write_bytes(b'0' * 600_000)
                return None
            
            mock_ytdl.download.side_effect = download_side_effect
            
            # Execute
            result = scraper.search_and_download("Test Show", output_path)
            
            # Verify file naming
            assert result is True
            assert output_path.name == "theme.mp3"
            assert output_path.exists()


@pytest.mark.unit
def test_output_template_configuration():
    """
    Test that output template is configured correctly.
    
    Validates: Requirements 8.1
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            def download_side_effect(urls):
                output_path.write_bytes(b'0' * 600_000)
                return None
            
            mock_ytdl.download.side_effect = download_side_effect
            
            # Execute
            scraper.search_and_download("Test Show", output_path)
            
            # Verify output template
            config = mock_ytdl_class.call_args[0][0]
            
            # Should use output_path without extension (yt-dlp adds .mp3)
            expected_template = str(output_path.with_suffix(''))
            assert config['outtmpl'] == expected_template


@pytest.mark.unit
def test_get_source_name():
    """
    Test that get_source_name returns correct identifier.
    
    Validates: Requirements 6.1-6.5
    """
    scraper = YoutubeScraper()
    assert scraper.get_source_name() == "YouTube"


@pytest.mark.unit
def test_mp3_format_conversion():
    """
    Test that output is converted to MP3 format.
    
    Validates: Requirements 7.1
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            def download_side_effect(urls):
                output_path.write_bytes(b'0' * 600_000)
                return None
            
            mock_ytdl.download.side_effect = download_side_effect
            
            # Execute
            scraper.search_and_download("Test Show", output_path)
            
            # Verify MP3 conversion configuration
            config = mock_ytdl_class.call_args[0][0]
            postprocessor = config['postprocessors'][0]
            
            assert postprocessor['key'] == 'FFmpegExtractAudio'
            assert postprocessor['preferredcodec'] == 'mp3'


@pytest.mark.unit
def test_file_rename_handling():
    """
    Test that file renaming works when yt-dlp creates file with different name.
    
    Validates: Requirements 8.1
    """
    scraper = YoutubeScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        alternate_path = output_path.with_suffix('.mp3')
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl_class:
            mock_ytdl = MagicMock()
            mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
            
            # Simulate yt-dlp creating file with .mp3 extension
            def download_side_effect(urls):
                alternate_path.write_bytes(b'0' * 600_000)
                return None
            
            mock_ytdl.download.side_effect = download_side_effect
            
            # Execute
            result = scraper.search_and_download("Test Show", output_path)
            
            # Verify success and correct file exists
            assert result is True
            assert output_path.exists()
