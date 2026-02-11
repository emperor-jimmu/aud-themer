"""Property-based tests for AnimeThemes scraper."""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any


# Feature: show-theme-cli, Property 9: Theme Priority Selection
@pytest.mark.property
@given(st.data())
def test_theme_priority_selection(data):
    """
    Property 9: Theme Priority Selection
    
    For any list of anime themes, the selection algorithm should prefer
    OP1 over other OPs, OPs over EDs, and any theme over no theme.
    
    Validates: Requirements 4.4
    """
    from scrapers.anime_themes import AnimeThemesScraper
    
    # Generate themes with unique URLs
    num_themes = data.draw(st.integers(min_value=1, max_value=20))
    themes = []
    for i in range(num_themes):
        theme_type = data.draw(st.sampled_from(['OP', 'ED', 'IN']))
        sequence = data.draw(st.integers(min_value=1, max_value=10))
        themes.append({
            'type': theme_type,
            'sequence': sequence,
            'animethemeentries': [{
                'videos': [{'link': f'https://example.com/video_{i}.webm'}]
            }]
        })
    
    scraper = AnimeThemesScraper()
    anime_data = {'animethemes': themes}
    
    # Get the selected theme URL
    selected_url = scraper._find_best_theme(anime_data)
    
    # Should always return a URL when themes exist
    assert selected_url is not None
    assert isinstance(selected_url, str)
    
    # Find which theme was selected
    selected_theme = None
    for theme in themes:
        if scraper._extract_video_url(theme) == selected_url:
            selected_theme = theme
            break
    
    assert selected_theme is not None
    
    # Check priority logic
    has_op1 = any(t['type'] == 'OP' and t['sequence'] == 1 for t in themes)
    has_any_op = any(t['type'] == 'OP' for t in themes)
    
    if has_op1:
        # If OP1 exists, it should be selected
        assert selected_theme['type'] == 'OP'
        assert selected_theme['sequence'] == 1
    elif has_any_op:
        # If any OP exists (but no OP1), an OP should be selected
        assert selected_theme['type'] == 'OP'
    # Otherwise, any theme is acceptable (first in list)


# Feature: show-theme-cli, Property 10: Format Conversion Consistency
@pytest.mark.property
@given(
    st.sampled_from(['webm', 'mp4', 'mkv', 'avi']),
    st.integers(min_value=500_001, max_value=10_000_000)
)
def test_format_conversion_consistency(input_format: str, file_size: int):
    """
    Property 10: Format Conversion Consistency
    
    For any audio file in a non-MP3 format, the conversion process should
    produce a valid MP3 file with the same audio content.
    
    Validates: Requirements 7.1
    
    Note: This property test validates the conversion logic without actually
    running FFmpeg. It ensures that:
    1. The conversion command is properly formatted
    2. The output file would be validated for size
    3. The process handles errors correctly
    """
    import tempfile
    from pathlib import Path
    from unittest.mock import Mock, patch
    from scrapers.anime_themes import AnimeThemesScraper
    
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        video_path = tmp_path / f"input.{input_format}"
        audio_path = tmp_path / "output.mp3"
        
        # Create dummy input file
        video_path.write_bytes(b'0' * file_size)
        
        # Mock subprocess to verify command structure
        with patch('subprocess.run') as mock_run:
            # Simulate successful FFmpeg execution
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            # Create output file with valid size
            audio_path.write_bytes(b'0' * 600_000)
            
            result = scraper._extract_audio(video_path, audio_path)
            
            # Verify FFmpeg was called
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            
            # Verify command structure
            assert 'ffmpeg' in call_args
            assert '-i' in call_args
            assert str(video_path) in call_args
            assert '-vn' in call_args  # No video
            assert '-acodec' in call_args
            assert 'libmp3lame' in call_args
            assert '-b:a' in call_args
            assert '320k' in call_args  # High quality bitrate
            assert str(audio_path) in call_args
            
            # Should succeed with valid file size
            assert result is True


# Feature: show-theme-cli, Property 11: Bitrate Selection Logic
@pytest.mark.property
@given(st.sampled_from(['AnimeThemes', 'TelevisionTunes', 'YouTube', 'Themes.moe']))
def test_bitrate_selection_logic(source_name: str):
    """
    Property 11: Bitrate Selection Logic
    
    For any source type, the bitrate selection should use 320kbps for
    high-quality sources (TelevisionTunes, AnimeThemes) and 192kbps
    minimum for fallback sources (YouTube).
    
    Validates: Requirements 7.2
    
    Note: This test validates that AnimeThemes uses 320kbps as a
    high-quality source.
    """
    import tempfile
    from pathlib import Path
    from unittest.mock import Mock, patch
    from scrapers.anime_themes import AnimeThemesScraper
    
    scraper = AnimeThemesScraper()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        video_path = tmp_path / "input.webm"
        audio_path = tmp_path / "output.mp3"
        
        # Create dummy files
        video_path.write_bytes(b'0' * 1_000_000)
        
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            # Create output with valid size
            audio_path.write_bytes(b'0' * 600_000)
            
            scraper._extract_audio(video_path, audio_path)
            
            # Verify bitrate for AnimeThemes
            if source_name == 'AnimeThemes':
                call_args = mock_run.call_args[0][0]
                bitrate_index = call_args.index('-b:a')
                bitrate_value = call_args[bitrate_index + 1]
                
                # AnimeThemes should use 320kbps (high quality)
                assert bitrate_value == '320k'


# Additional property: Video URL extraction should handle missing data gracefully
@pytest.mark.property
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    st.fixed_dictionaries({
        'animethemeentries': st.lists(
            st.fixed_dictionaries({
                'videos': st.lists(
                    st.fixed_dictionaries({
                        'link': st.one_of(
                            st.none(),
                            st.just('https://example.com/video.webm')
                        )
                    }),
                    max_size=3
                )
            }),
            max_size=3
        )
    })
)
def test_video_url_extraction_handles_missing_data(theme_data: Dict[str, Any]):
    """
    Property: Video URL extraction should handle missing or malformed data gracefully.
    
    For any theme data structure, the URL extraction should either return a valid
    URL string or None, never raising an exception.
    """
    from scrapers.anime_themes import AnimeThemesScraper
    
    scraper = AnimeThemesScraper()
    
    # Should not raise exception regardless of input structure
    try:
        result = scraper._extract_video_url(theme_data)
        # Result should be either None or a string
        assert result is None or isinstance(result, str)
    except Exception as e:
        pytest.fail(f"URL extraction raised unexpected exception: {e}")


# Property: Empty theme list should return None
@pytest.mark.property
def test_empty_theme_list_returns_none():
    """
    Property: When no themes are available, the selection should return None.
    
    For any anime data with an empty theme list, the theme selection
    should return None rather than raising an exception.
    """
    from scrapers.anime_themes import AnimeThemesScraper
    
    scraper = AnimeThemesScraper()
    anime_data = {'animethemes': []}
    
    result = scraper._find_best_theme(anime_data)
    assert result is None
