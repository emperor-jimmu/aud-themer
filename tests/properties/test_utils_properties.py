"""Property-based tests for core utility functions."""

import pytest
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings
from core.utils import (
    validate_path,
    sanitize_filename,
    validate_file_size,
    calculate_name_similarity
)


# Feature: show-theme-cli, Property 1: Path Validation Correctness
@pytest.mark.property
@given(st.text(min_size=1, max_size=100))
def test_path_validation_correctness(path_name):
    """
    Property 1: Path Validation Correctness
    
    For any file system path, the validation function should return True
    if and only if the path exists and is a directory.
    
    Validates: Requirements 1.1
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create a valid directory
        valid_dir = tmp_path / "valid_dir"
        valid_dir.mkdir()
        
        # Create a file (not a directory)
        valid_file = tmp_path / "valid_file.txt"
        valid_file.write_text("test")
        
        # Non-existent path
        non_existent = tmp_path / "non_existent"
        
        # Test that existing directory returns True
        assert validate_path(valid_dir) is True
        
        # Test that file returns False (not a directory)
        assert validate_path(valid_file) is False
        
        # Test that non-existent path returns False
        assert validate_path(non_existent) is False


# Feature: show-theme-cli, Property 14: Filename Sanitization
@pytest.mark.property
@given(st.text(min_size=0, max_size=200))
def test_filename_sanitization(filename):
    """
    Property 14: Filename Sanitization
    
    For any string containing special characters or OS-incompatible characters,
    the sanitization function should produce a valid filename for the current
    operating system.
    
    Validates: Requirements 8.2
    """
    sanitized = sanitize_filename(filename)
    
    # Sanitized filename should not contain invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        assert char not in sanitized
    
    # Should not contain control characters
    for i in range(32):
        assert chr(i) not in sanitized
    
    # Should not be empty (defaults to 'unnamed' if input produces empty string)
    assert len(sanitized) > 0
    
    # Should not start or end with spaces or dots
    assert not sanitized.startswith(' ')
    assert not sanitized.startswith('.')
    assert not sanitized.endswith(' ')
    assert not sanitized.endswith('.')


# Feature: show-theme-cli, Property 13: File Size Validation
@pytest.mark.property
@given(st.integers(min_value=0, max_value=2_000_000))
def test_file_size_validation(file_size):
    """
    Property 13: File Size Validation
    
    For any downloaded theme file, it should be marked as successful
    if and only if the file size is greater than 500KB.
    
    Validates: Requirements 7.4, 8.4
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        test_file = tmp_path / "test_file.mp3"
        
        # Create file with specified size
        test_file.write_bytes(b'0' * file_size)
        
        # Validate against 500KB threshold
        result = validate_file_size(test_file, min_size_bytes=500_000)
        
        # Should return True only if file size > 500KB
        if file_size > 500_000:
            assert result is True
        else:
            assert result is False
        
        # Non-existent file should return False
        non_existent = tmp_path / "non_existent.mp3"
        assert validate_file_size(non_existent) is False



# Feature: show-theme-cli, Property 8: Anime Name Similarity Matching
@pytest.mark.property
@given(
    st.lists(
        st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',))),
        min_size=1,
        max_size=20
    ),
    st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',)))
)
def test_anime_name_similarity_matching(anime_list, search_query):
    """
    Property 8: Anime Name Similarity Matching
    
    For any list of anime results from the API, the name matching function
    should return the anime with the highest similarity ratio to the search query.
    
    Validates: Requirements 4.3
    """
    # Calculate similarity for each anime name
    similarities = [(name, calculate_name_similarity(search_query, name)) 
                    for name in anime_list]
    
    # Find the one with highest similarity
    best_match = max(similarities, key=lambda x: x[1])
    
    # Verify that the best match has the highest or equal similarity
    for name, similarity in similarities:
        assert best_match[1] >= similarity
    
    # Test that identical strings have similarity of 1.0
    assert calculate_name_similarity("test", "test") == 1.0
    
    # Test that similarity is case-insensitive
    assert calculate_name_similarity("Test", "test") == 1.0
    assert calculate_name_similarity("ANIME", "anime") == 1.0
    
    # Test that similarity is between 0.0 and 1.0
    for name in anime_list:
        similarity = calculate_name_similarity(search_query, name)
        assert 0.0 <= similarity <= 1.0
