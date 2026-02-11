#!/usr/bin/env python3
"""Verification script for code review fixes."""

import sys
from pathlib import Path


def test_imports():
    """Test that all new modules can be imported."""
    print("Testing imports...")
    
    try:
        from core.config import Config
        print("  ✓ Config imported")
        
        from core.logging_utils import StructuredLogger
        print("  ✓ StructuredLogger imported")
        
        from core.rate_limiter import RateLimiter
        print("  ✓ RateLimiter imported")
        
        from core.ffmpeg_utils import convert_audio, FFmpegError, FFmpegErrorParser
        print("  ✓ FFmpeg utils imported")
        
        from core.security import sanitize_for_subprocess, validate_show_name
        print("  ✓ Security utils imported")
        
        from scrapers.anime_themes import AnimeThemesScraper
        from scrapers.tv_tunes import TelevisionTunesScraper
        from scrapers.youtube import YoutubeScraper
        from scrapers.themes_moe import ThemesMoeScraper
        print("  ✓ All scrapers imported")
        
        from core.orchestrator import Orchestrator
        print("  ✓ Orchestrator imported")
        
        return True
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False


def test_config_constants():
    """Test that Config constants are defined."""
    print("\nTesting Config constants...")
    
    try:
        from core.config import Config
        
        required_constants = [
            'MIN_FILE_SIZE_BYTES',
            'DEFAULT_TIMEOUT_SEC',
            'DOWNLOAD_TIMEOUT_SEC',
            'AUDIO_BITRATE',
            'AUDIO_CODEC',
            'MAX_VIDEO_DURATION_SEC',
            'RATE_LIMIT_MIN_DELAY_SEC',
            'RATE_LIMIT_MAX_DELAY_SEC',
            'MAX_RETRY_ATTEMPTS',
            'RETRY_INITIAL_DELAY_SEC',
            'RETRY_BACKOFF_FACTOR',
            'FFMPEG_CONVERSION_TIMEOUT_SEC',
            'THEME_EXTENSIONS',
        ]
        
        for const in required_constants:
            if not hasattr(Config, const):
                print(f"  ✗ Missing constant: {const}")
                return False
            print(f"  ✓ {const} = {getattr(Config, const)}")
        
        return True
    except Exception as e:
        print(f"  ✗ Config test failed: {e}")
        return False


def test_structured_logger():
    """Test StructuredLogger basic functionality."""
    print("\nTesting StructuredLogger...")
    
    try:
        from core.logging_utils import StructuredLogger
        
        logger = StructuredLogger("test")
        print(f"  ✓ Logger created with correlation_id: {logger.correlation_id}")
        
        # Test context building
        context = logger._build_context("test_op", show_name="Test Show", source="TestSource")
        assert "correlation_id" in context
        assert context["operation"] == "test_op"
        assert context["show_name"] == "Test Show"
        print("  ✓ Context building works")
        
        return True
    except Exception as e:
        print(f"  ✗ StructuredLogger test failed: {e}")
        return False


def test_rate_limiter():
    """Test RateLimiter basic functionality."""
    print("\nTesting RateLimiter...")
    
    try:
        from core.rate_limiter import RateLimiter
        import time
        
        limiter = RateLimiter(min_delay=0.1, max_delay=0.2)
        print("  ✓ RateLimiter created")
        
        # First call should not wait
        start = time.time()
        limiter.wait("test_source")
        elapsed = time.time() - start
        print(f"  ✓ First call: {elapsed:.3f}s (no delay expected)")
        
        # Second call should wait
        start = time.time()
        limiter.wait("test_source")
        elapsed = time.time() - start
        if elapsed >= 0.1:
            print(f"  ✓ Second call: {elapsed:.3f}s (delay applied)")
        else:
            print(f"  ⚠ Second call: {elapsed:.3f}s (delay may be too short)")
        
        return True
    except Exception as e:
        print(f"  ✗ RateLimiter test failed: {e}")
        return False


def test_ffmpeg_error_parser():
    """Test FFmpegErrorParser basic functionality."""
    print("\nTesting FFmpegErrorParser...")
    
    try:
        from core.ffmpeg_utils import FFmpegErrorParser, FFmpegErrorType
        
        # Test missing codec detection
        stderr = "Error: Unknown encoder 'libmp3lame'"
        error = FFmpegErrorParser.parse_error(stderr, 1)
        assert error.error_type == FFmpegErrorType.MISSING_CODEC
        print("  ✓ Missing codec detection works")
        
        # Test disk space detection
        stderr = "Error: No space left on device"
        error = FFmpegErrorParser.parse_error(stderr, 1)
        assert error.error_type == FFmpegErrorType.DISK_SPACE
        print("  ✓ Disk space detection works")
        
        # Test transient error detection
        assert not error.is_transient()
        print("  ✓ Transient error detection works")
        
        return True
    except Exception as e:
        print(f"  ✗ FFmpegErrorParser test failed: {e}")
        return False


def test_security_utils():
    """Test security utilities."""
    print("\nTesting security utilities...")
    
    try:
        from core.security import sanitize_for_subprocess, validate_show_name
        
        # Test sanitization
        dangerous = "test; rm -rf /"
        safe = sanitize_for_subprocess(dangerous)
        assert ";" not in safe
        assert "rm" in safe  # Text should remain, just dangerous chars removed
        print(f"  ✓ Sanitization works: '{dangerous}' -> '{safe}'")
        
        # Test validation
        assert validate_show_name("The Simpsons")
        assert validate_show_name("Attack on Titan (2013)")
        assert not validate_show_name("")
        assert not validate_show_name("\x00malicious")
        print("  ✓ Show name validation works")
        
        return True
    except Exception as e:
        print(f"  ✗ Security utils test failed: {e}")
        return False


def test_scraper_initialization():
    """Test that scrapers can be initialized with timeout parameter."""
    print("\nTesting scraper initialization...")
    
    try:
        from scrapers.anime_themes import AnimeThemesScraper
        from scrapers.tv_tunes import TelevisionTunesScraper
        from scrapers.youtube import YoutubeScraper
        from scrapers.themes_moe import ThemesMoeScraper
        
        # Test with custom timeout
        anime_scraper = AnimeThemesScraper(timeout=60)
        assert anime_scraper.timeout == 60.0
        print("  ✓ AnimeThemesScraper accepts timeout")
        
        tv_scraper = TelevisionTunesScraper(timeout=45)
        assert tv_scraper.timeout_ms == 45000
        print("  ✓ TelevisionTunesScraper accepts timeout")
        
        yt_scraper = YoutubeScraper()
        print("  ✓ YoutubeScraper initializes")
        
        themes_scraper = ThemesMoeScraper(timeout=30)
        assert themes_scraper.timeout_ms == 30000
        print("  ✓ ThemesMoeScraper accepts timeout")
        
        return True
    except Exception as e:
        print(f"  ✗ Scraper initialization test failed: {e}")
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Code Review Fixes - Verification Script")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Config Constants", test_config_constants),
        ("StructuredLogger", test_structured_logger),
        ("RateLimiter", test_rate_limiter),
        ("FFmpegErrorParser", test_ffmpeg_error_parser),
        ("Security Utils", test_security_utils),
        ("Scraper Initialization", test_scraper_initialization),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} test crashed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All verification tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
