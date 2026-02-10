"""Property-based tests for TelevisionTunes scraper."""

import pytest
from hypothesis import given, strategies as st
from unittest.mock import Mock, MagicMock
from scrapers.tv_tunes import TelevisionTunesScraper


# Feature: show-theme-cli, Property 7: Search Result Matching
@pytest.mark.property
@given(
    st.lists(
        st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',))),
        min_size=1,
        max_size=20
    ),
    st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',)))
)
def test_search_result_matching(result_texts, show_name):
    """
    Property 7: Search Result Matching
    
    For any list of search results and a target show name, the matching algorithm
    should prefer exact matches over partial matches, and return the first result
    when no exact match exists.
    
    Validates: Requirements 3.3
    """
    scraper = TelevisionTunesScraper()
    
    # Create mock page with mock results
    mock_page = Mock()
    mock_results = Mock()
    
    # Set up the count of results
    mock_results.count.return_value = len(result_texts)
    
    # Create mock result items
    mock_result_items = []
    for text in result_texts:
        mock_item = Mock()
        mock_item.text_content.return_value = text
        mock_result_items.append(mock_item)
    
    # Set up nth() to return the appropriate mock item
    def nth_side_effect(index):
        return mock_result_items[index]
    
    mock_results.nth.side_effect = nth_side_effect
    mock_results.first = mock_result_items[0] if mock_result_items else None
    
    mock_page.locator.return_value = mock_results
    
    # Call the method under test
    result = scraper._find_best_match(mock_page, show_name)
    
    # Verify the behavior
    if len(result_texts) == 0:
        # No results should return None
        assert result is None
    else:
        # Check if there's an exact match (case-insensitive substring)
        show_name_lower = show_name.lower()
        exact_match_found = False
        expected_index = -1
        
        for i, text in enumerate(result_texts):
            if show_name_lower in text.lower():
                exact_match_found = True
                expected_index = i
                break
        
        if exact_match_found:
            # Should return the first exact match
            assert result == mock_result_items[expected_index]
        else:
            # Should return the first result when no exact match
            assert result == mock_results.first


@pytest.mark.property
@given(st.text(min_size=1, max_size=50))
def test_search_result_matching_empty_results(show_name):
    """
    Property 7 (Edge Case): Search Result Matching with Empty Results
    
    When there are no search results, the matching algorithm should return None.
    
    Validates: Requirements 3.3
    """
    scraper = TelevisionTunesScraper()
    
    # Create mock page with no results
    mock_page = Mock()
    mock_results = Mock()
    mock_results.count.return_value = 0
    mock_page.locator.return_value = mock_results
    
    # Call the method under test
    result = scraper._find_best_match(mock_page, show_name)
    
    # Should return None for empty results
    assert result is None


@pytest.mark.property
@given(
    st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',)))
)
def test_search_result_matching_single_result(show_name):
    """
    Property 7 (Edge Case): Search Result Matching with Single Result
    
    When there is exactly one search result, it should always be returned
    regardless of whether it matches the show name.
    
    Validates: Requirements 3.3
    """
    scraper = TelevisionTunesScraper()
    
    # Create mock page with single result
    mock_page = Mock()
    mock_results = Mock()
    mock_results.count.return_value = 1
    
    mock_item = Mock()
    mock_item.text_content.return_value = "Some Random Show"
    
    mock_results.nth.return_value = mock_item
    mock_results.first = mock_item
    
    mock_page.locator.return_value = mock_results
    
    # Call the method under test
    result = scraper._find_best_match(mock_page, show_name)
    
    # Should return the single result
    assert result == mock_item


@pytest.mark.property
@given(
    st.lists(
        st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',))),
        min_size=2,
        max_size=10
    )
)
def test_search_result_matching_case_insensitive(result_texts):
    """
    Property 7 (Invariant): Search Result Matching is Case-Insensitive
    
    The matching algorithm should perform case-insensitive matching.
    
    Validates: Requirements 3.3
    """
    scraper = TelevisionTunesScraper()
    
    # Use the first result text as the show name with different casing
    if result_texts:
        show_name = result_texts[0]
        
        # Test with uppercase version
        mock_page = Mock()
        mock_results = Mock()
        mock_results.count.return_value = len(result_texts)
        
        mock_result_items = []
        for text in result_texts:
            mock_item = Mock()
            mock_item.text_content.return_value = text
            mock_result_items.append(mock_item)
        
        def nth_side_effect(index):
            return mock_result_items[index]
        
        mock_results.nth.side_effect = nth_side_effect
        mock_results.first = mock_result_items[0]
        
        mock_page.locator.return_value = mock_results
        
        # Test with uppercase show name
        result_upper = scraper._find_best_match(mock_page, show_name.upper())
        
        # Reset mocks for lowercase test
        mock_results.nth.side_effect = nth_side_effect
        
        # Test with lowercase show name
        result_lower = scraper._find_best_match(mock_page, show_name.lower())
        
        # Both should return the same result (first match)
        assert result_upper == mock_result_items[0]
        assert result_lower == mock_result_items[0]
