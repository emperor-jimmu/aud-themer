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

        # Mock search API response
        mock_search_response = {
            "search": {
                "anime": [
                    {
                        "name": "Test Anime",
                        "slug": "test_anime"
                    }
                ]
            }
        }

        # Mock full anime data response
        mock_anime_response = {
            "anime": {
                "name": "Test Anime",
                "slug": "test_anime",
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
        }

        with patch('httpx.Client') as mock_client_class, \
             patch('httpx.stream') as mock_stream, \
             patch('scrapers.anime_themes.convert_audio') as mock_convert:

            # Mock API client
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            # First call returns search results, second call returns full anime data
            mock_search = Mock()
            mock_search.status_code = 200
            mock_search.json.return_value = mock_search_response
            
            mock_anime = Mock()
            mock_anime.status_code = 200
            mock_anime.json.return_value = mock_anime_response
            
            mock_client.get.side_effect = [mock_search, mock_anime]

            # Mock video download
            mock_stream_response = MagicMock()
            mock_stream_response.status_code = 200
            mock_stream_response.iter_bytes.return_value = [b'0' * 1_000_000]
            mock_stream.return_value.__enter__.return_value = mock_stream_response

            # Mock FFmpeg
            def convert_side_effect(video, audio):
                # Don't actually run FFmpeg, just create the output file
                output_path.write_bytes(b'0' * 600_000)  # 600KB file
                return (True, None)
            
            mock_convert.side_effect = convert_side_effect

            # Execute the test
            result = scraper.search_and_download("Test Anime", output_path)

            # Verify success
            assert result is True
            assert output_path.exists()
            assert output_path.stat().st_size > 500_000

            # Verify API was called correctly with new search endpoint
            assert mock_client.get.call_count == 2
            first_call = mock_client.get.call_args_list[0]
            assert "/search" in first_call[0][0]
            assert first_call[1]["params"]["q"] == "Test Anime"


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
        
        # Mock search response
        mock_search = Mock()
        mock_search.status_code = 200
        mock_search.json.return_value = {"search": {"anime": []}}
        
        mock_client.get.return_value = mock_search
        
        # Execute search
        result = scraper._search_anime("My Anime")
        
        # Verify API call format
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        
        # Check URL - now uses /search endpoint
        assert call_args[0][0] == "https://api.animethemes.moe/search"
        
        # Check parameters - now uses q and fields[search]
        params = call_args[1]["params"]
        assert params["q"] == "My Anime"
        assert params["fields[search]"] == "anime"


@pytest.mark.unit
def test_json_response_parsing():
    """
    Test JSON response parsing and name matching.
    
    Validates: Requirements 4.2, 4.3
    """
    scraper = AnimeThemesScraper()
    
    # Mock search response
    mock_search_response = {
        "search": {
            "anime": [
                {"name": "Test Anime", "slug": "test_anime"},
                {"name": "Different Anime", "slug": "different_anime"},
                {"name": "Another Anime", "slug": "another_anime"}
            ]
        }
    }
    
    # Mock full anime response
    mock_anime_response = {
        "anime": {
            "name": "Test Anime",
            "slug": "test_anime",
            "animethemes": []
        }
    }
    
    with patch('httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        mock_search = Mock()
        mock_search.status_code = 200
        mock_search.json.return_value = mock_search_response
        
        mock_anime = Mock()
        mock_anime.status_code = 200
        mock_anime.json.return_value = mock_anime_response
        
        mock_client.get.side_effect = [mock_search, mock_anime]
        
        # Execute search
        result = scraper._search_anime("Test Anime")
        
        # Should return the first anime (search API handles relevance)
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
            mock_response.json.return_value = {"anime": []}
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
    from core.ffmpeg_utils import convert_audio
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "input.webm"
        audio_path = Path(tmp_dir) / "output.mp3"
        
        # Create dummy video file
        video_path.write_bytes(b'0' * 1_000_000)
        
        with patch('core.ffmpeg_utils.subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result
            
            # Create output file
            def subprocess_side_effect(*args, **kwargs):
                audio_path.write_bytes(b'0' * 600_000)
                return mock_result
            
            mock_subprocess.side_effect = subprocess_side_effect
            
            # Execute extraction
            success, error = convert_audio(video_path, audio_path)
            
            # Verify success
            assert success is True
            assert error is None
            
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
    from core.ffmpeg_utils import convert_audio
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "input.webm"
        audio_path = Path(tmp_dir) / "output.mp3"
        
        # Create dummy video file
        video_path.write_bytes(b'0' * 1_000_000)
        
        with patch('core.ffmpeg_utils.subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 1  # FFmpeg error
            mock_subprocess.return_value = mock_result
            
            # Execute extraction
            success, error = convert_audio(video_path, audio_path)
            
            # Verify failure
            assert success is False
            assert error is not None


@pytest.mark.unit
def test_file_size_validation_after_extraction():
    """
    Test that convert_audio succeeds but scrapers validate file size separately.
    
    Validates: Requirements 7.4, 8.4
    """
    from core.ffmpeg_utils import convert_audio
    from core.utils import validate_file_size
    from core.config import Config
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "input.webm"
        audio_path = Path(tmp_dir) / "output.mp3"
        
        # Create dummy video file
        video_path.write_bytes(b'0' * 1_000_000)
        
        with patch('core.ffmpeg_utils.subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result
            
            # Create output file that's too small
            def subprocess_side_effect(*args, **kwargs):
                audio_path.write_bytes(b'0' * 100_000)  # Only 100KB
                return mock_result
            
            mock_subprocess.side_effect = subprocess_side_effect
            
            # Execute extraction - should succeed
            success, error = convert_audio(video_path, audio_path)
            
            # convert_audio itself should succeed
            assert success is True
            assert error is None
            
            # But file size validation should fail
            assert not validate_file_size(audio_path, Config.MIN_FILE_SIZE_BYTES)


@pytest.mark.unit
def test_temp_file_cleanup():
    """
    Test that temporary video files are cleaned up after processing.

    Validates: Requirements 4.7
    """
    scraper = AnimeThemesScraper()

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "theme.mp3"
        temp_video = output_path.parent / f"temp_{output_path.stem}.webm"

        # Mock search response
        mock_search_response = {
            "search": {
                "anime": [
                    {"name": "Test Anime", "slug": "test_anime"}
                ]
            }
        }

        # Mock full anime response
        mock_anime_response = {
            "anime": {
                "name": "Test Anime",
                "slug": "test_anime",
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
        }

        with patch('httpx.Client') as mock_client_class, \
             patch('httpx.stream') as mock_stream, \
             patch('scrapers.anime_themes.convert_audio') as mock_convert:

            # Mock API
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            
            mock_search = Mock()
            mock_search.status_code = 200
            mock_search.json.return_value = mock_search_response
            
            mock_anime = Mock()
            mock_anime.status_code = 200
            mock_anime.json.return_value = mock_anime_response
            
            mock_client.get.side_effect = [mock_search, mock_anime]

            # Mock video download
            mock_stream_response = MagicMock()
            mock_stream_response.status_code = 200
            mock_stream_response.iter_bytes.return_value = [b'0' * 1_000_000]
            mock_stream.return_value.__enter__.return_value = mock_stream_response

            # Mock FFmpeg
            def convert_side_effect(video, audio):
                audio.write_bytes(b'0' * 600_000)
                return (True, None)

            mock_convert.side_effect = convert_side_effect

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
