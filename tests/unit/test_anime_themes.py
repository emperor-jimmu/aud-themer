"""Unit tests for AnimeThemes scraper."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from scrapers.anime_themes import AnimeThemesScraper


@pytest.mark.unit
def test_successful_api_search_and_download():
    """
    Test successful API search and download flow.
    
    Validates: Requirements 4.1-4.7
    """
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        temp_video = Path(tmp_dir) / "temp_theme.webm"
        
        # Mock API response
        mock_api_response = {
            "search": {
                "anime": [
                    {
                        "name": "Test Anime",
                        "animethemes": [
                            {
                                "type": "OP",
                                "sequence": 1,
                                "animethemeentries": [
                                    {
                                        "videos": [
                                            {"link": "https://example.com/video.webm"}
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        
        with patch('httpx.Client') as mock_client_class, \
             patch('httpx.stream') as mock_stream, \
             patch('subprocess.run') as mock_subprocess:
            
            # Mock API client
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_response
            mock_client.get.return_value = mock_response
            
            # Mock video download
            mock_stream_response = MagicMock()
            mock_stream_response.status_code = 200
            mock_stream_response.iter_bytes.return_value = [b'0' * 1_000_000]
            mock_stream.return_value.__enter__.return_value = mock_stream_response
            
            # Mock FFmpeg
            mock_ffmpeg_result = Mock()
            mock_ffmpeg_result.returncode = 0
            mock_subprocess.return_value = mock_ffmpeg_result
            
            # Create output file when FFmpeg runs
            def subprocess_side_effect(*args, **kwargs):
                output_path.write_bytes(b'0' * 600_000)  # 600KB file
                return mock_ffmpeg_result
            
            mock_subprocess.side_effect = subprocess_side_effect
            
            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify success
            assert result is True
            assert output_path.exists()
            assert output_path.stat().st_size > 500_000
            
            # Verify API was called correctly
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            assert "search" in call_args[0][0]
            assert call_args[1]["params"]["q"] == "Test Anime"
            assert "animethemes.animethemeentries.videos" in call_args[1]["params"]["include"]


@pytest.mark.unit
def test_api_request_formatting():
    """
    Test that API requests are formatted correctly.
    
    Validates: Requirements 4.1, 4.2
    """
    scraper = AnimeThemesScraper()
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"search": {"anime": []}}
        mock_client.get.return_value = mock_response
        
        # Execute search
        result = scraper._search_anime("My Anime")
        
        # Verify API call format
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        
        # Check URL
        assert call_args[0][0] == "https://api.animethemes.moe/search"
        
        # Check parameters
        params = call_args[1]["params"]
        assert params["q"] == "My Anime"
        assert params["include"] == "animethemes.animethemeentries.videos"


@pytest.mark.unit
def test_json_response_parsing():
    """
    Test JSON response parsing and name matching.
    
    Validates: Requirements 4.2, 4.3
    """
    scraper = AnimeThemesScraper()
    
    mock_api_response = {
        "search": {
            "anime": [
                {"name": "Different Anime"},
                {"name": "Test Anime"},
                {"name": "Another Anime"}
            ]
        }
    }
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_response
        mock_client.get.return_value = mock_response
        
        # Execute search
        result = scraper._search_anime("Test Anime")
        
        # Should return the best matching anime
        assert result is not None
        assert result["name"] == "Test Anime"


@pytest.mark.unit
def test_handling_no_api_results():
    """
    Test handling when API returns no results.
    
    Validates: Requirements 4.1-4.7
    """
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"search": {"anime": []}}
            mock_client.get.return_value = mock_response
            
            # Execute the test
            result = scraper.search_and_download("Nonexistent Anime", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_handling_api_error():
    """
    Test handling of API error responses.
    
    Validates: Requirements 4.1-4.7
    """
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            
            mock_response = Mock()
            mock_response.status_code = 500
            mock_client.get.return_value = mock_response
            
            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_video_download():
    """
    Test video download functionality.
    
    Validates: Requirements 4.5
    """
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "video.webm"
        
        with patch('httpx.stream') as mock_stream:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.iter_bytes.return_value = [
                b'chunk1',
                b'chunk2',
                b'chunk3'
            ]
            mock_stream.return_value.__enter__.return_value = mock_response
            
            # Execute download
            result = scraper._download_video("https://example.com/video.webm", output_path)
            
            # Verify success
            assert result is True
            assert output_path.exists()
            assert output_path.read_bytes() == b'chunk1chunk2chunk3'


@pytest.mark.unit
def test_video_download_failure():
    """
    Test handling of video download failure.
    
    Validates: Requirements 4.5
    """
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "video.webm"
        
        with patch('httpx.stream') as mock_stream:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_stream.return_value.__enter__.return_value = mock_response
            
            # Execute download
            result = scraper._download_video("https://example.com/video.webm", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()


@pytest.mark.unit
def test_ffmpeg_audio_extraction():
    """
    Test FFmpeg audio extraction with correct parameters.
    
    Validates: Requirements 4.6, 7.1, 7.2
    """
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "input.webm"
        audio_path = Path(tmp_dir) / "output.mp3"
        
        # Create dummy video file
        video_path.write_bytes(b'0' * 1_000_000)
        
        with patch('subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result
            
            # Create output file
            audio_path.write_bytes(b'0' * 600_000)
            
            # Execute extraction
            result = scraper._extract_audio(video_path, audio_path)
            
            # Verify success
            assert result is True
            
            # Verify FFmpeg command
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args[0][0]
            
            assert "ffmpeg" in call_args
            assert "-i" in call_args
            assert str(video_path) in call_args
            assert "-vn" in call_args  # No video
            assert "-acodec" in call_args
            assert "libmp3lame" in call_args
            assert "-b:a" in call_args
            assert "320k" in call_args  # High quality bitrate
            assert "-y" in call_args  # Overwrite
            assert str(audio_path) in call_args


@pytest.mark.unit
def test_ffmpeg_extraction_failure():
    """
    Test handling of FFmpeg extraction failure.
    
    Validates: Requirements 4.6, 7.1
    """
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "input.webm"
        audio_path = Path(tmp_dir) / "output.mp3"
        
        # Create dummy video file
        video_path.write_bytes(b'0' * 1_000_000)
        
        with patch('subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 1  # FFmpeg error
            mock_subprocess.return_value = mock_result
            
            # Execute extraction
            result = scraper._extract_audio(video_path, audio_path)
            
            # Verify failure
            assert result is False


@pytest.mark.unit
def test_file_size_validation_after_extraction():
    """
    Test that files smaller than 500KB are rejected after extraction.
    
    Validates: Requirements 7.4, 8.4
    """
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "input.webm"
        audio_path = Path(tmp_dir) / "output.mp3"
        
        # Create dummy video file
        video_path.write_bytes(b'0' * 1_000_000)
        
        with patch('subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result
            
            # Create output file that's too small
            audio_path.write_bytes(b'0' * 100_000)  # Only 100KB
            
            # Execute extraction
            result = scraper._extract_audio(video_path, audio_path)
            
            # Verify failure and file cleanup
            assert result is False
            assert not audio_path.exists()  # File should be deleted


@pytest.mark.unit
def test_temp_file_cleanup():
    """
    Test that temporary video files are cleaned up after processing.
    
    Validates: Requirements 4.5, 4.6
    """
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        temp_video = Path(tmp_dir) / "temp_theme.webm"
        
        mock_api_response = {
            "search": {
                "anime": [
                    {
                        "name": "Test Anime",
                        "animethemes": [
                            {
                                "type": "OP",
                                "sequence": 1,
                                "animethemeentries": [
                                    {
                                        "videos": [
                                            {"link": "https://example.com/video.webm"}
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        
        with patch('httpx.Client') as mock_client_class, \
             patch('httpx.stream') as mock_stream, \
             patch('subprocess.run') as mock_subprocess:
            
            # Mock API
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_response
            mock_client.get.return_value = mock_response
            
            # Mock video download
            mock_stream_response = MagicMock()
            mock_stream_response.status_code = 200
            mock_stream_response.iter_bytes.return_value = [b'0' * 1_000_000]
            mock_stream.return_value.__enter__.return_value = mock_stream_response
            
            # Mock FFmpeg
            mock_ffmpeg_result = Mock()
            mock_ffmpeg_result.returncode = 0
            
            def subprocess_side_effect(*args, **kwargs):
                output_path.write_bytes(b'0' * 600_000)
                return mock_ffmpeg_result
            
            mock_subprocess.side_effect = subprocess_side_effect
            
            # Execute
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify temp file was cleaned up
            assert result is True
            assert not temp_video.exists()


@pytest.mark.unit
def test_theme_priority_op1_selected():
    """
    Test that OP1 is selected when available.
    
    Validates: Requirements 4.4
    """
    scraper = AnimeThemesScraper()
    
    anime_data = {
        "animethemes": [
            {
                "type": "ED",
                "sequence": 1,
                "animethemeentries": [{"videos": [{"link": "https://example.com/ed1.webm"}]}]
            },
            {
                "type": "OP",
                "sequence": 2,
                "animethemeentries": [{"videos": [{"link": "https://example.com/op2.webm"}]}]
            },
            {
                "type": "OP",
                "sequence": 1,
                "animethemeentries": [{"videos": [{"link": "https://example.com/op1.webm"}]}]
            }
        ]
    }
    
    result = scraper._find_best_theme(anime_data)
    
    # Should select OP1
    assert result == "https://example.com/op1.webm"


@pytest.mark.unit
def test_theme_priority_any_op_when_no_op1():
    """
    Test that any OP is selected when OP1 is not available.
    
    Validates: Requirements 4.4
    """
    scraper = AnimeThemesScraper()
    
    anime_data = {
        "animethemes": [
            {
                "type": "ED",
                "sequence": 1,
                "animethemeentries": [{"videos": [{"link": "https://example.com/ed1.webm"}]}]
            },
            {
                "type": "OP",
                "sequence": 2,
                "animethemeentries": [{"videos": [{"link": "https://example.com/op2.webm"}]}]
            }
        ]
    }
    
    result = scraper._find_best_theme(anime_data)
    
    # Should select OP2 (any OP)
    assert result == "https://example.com/op2.webm"


@pytest.mark.unit
def test_theme_priority_fallback_to_first():
    """
    Test that first theme is selected when no OP is available.
    
    Validates: Requirements 4.4
    """
    scraper = AnimeThemesScraper()
    
    anime_data = {
        "animethemes": [
            {
                "type": "ED",
                "sequence": 1,
                "animethemeentries": [{"videos": [{"link": "https://example.com/ed1.webm"}]}]
            },
            {
                "type": "ED",
                "sequence": 2,
                "animethemeentries": [{"videos": [{"link": "https://example.com/ed2.webm"}]}]
            }
        ]
    }
    
    result = scraper._find_best_theme(anime_data)
    
    # Should select first theme (ED1)
    assert result == "https://example.com/ed1.webm"


@pytest.mark.unit
def test_get_source_name():
    """
    Test that get_source_name returns correct identifier.
    
    Validates: Requirements 4.1-4.7
    """
    scraper = AnimeThemesScraper()
    assert scraper.get_source_name() == "AnimeThemes"


@pytest.mark.unit
def test_exception_handling():
    """
    Test that exceptions are caught and return False.
    
    Validates: Requirements 4.1-4.7
    """
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        
        with patch('httpx.Client') as mock_client_class:
            # Raise an exception
            mock_client_class.side_effect = Exception("Network error")
            
            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)
            
            # Verify failure
            assert result is False
            assert not output_path.exists()
