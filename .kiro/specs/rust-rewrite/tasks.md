# Implementation Plan: Rust Rewrite

## Overview

Rewrite Show Theme CLI from Python to Rust (2024 edition), preserving all existing functionality. Tasks are ordered to build foundational layers first (config, utils, traits), then core orchestration, then individual scrapers, and finally integration wiring. Agent hooks and steering documents are updated as a final step.

## Tasks

- [x] 1. Initialize Rust project and core types
  - [x] 1.1 Create Cargo.toml with edition = "2024" and all dependencies (clap, reqwest, tokio, chromiumoxide, indicatif, colored, console, anyhow, thiserror, tracing, tracing-subscriber, strsim, async-trait, rand, scopeguard, serde, serde_json, proptest)
    - _Requirements: 15.1, 15.2_
  - [x] 1.2 Create `src/config.rs` with all Config constants (MIN_FILE_SIZE_BYTES, DEFAULT_TIMEOUT_SEC, DOWNLOAD_TIMEOUT_SEC, AUDIO_BITRATE, AUDIO_CODEC, MAX_VIDEO_DURATION_SEC, RATE_LIMIT delays, RETRY settings, FFMPEG_TIMEOUT, THEME_EXTENSIONS)
    - _Requirements: 9.1, 11.1_
  - [x] 1.3 Create `src/scrapers/mod.rs` with the `ThemeScraper` async trait definition and `ScraperOutcome` enum
    - _Requirements: 14.1, 14.2, 14.3_
  - [x] 1.4 Create `src/main.rs` with clap derive `CliArgs` struct, version handling, input validation, and basic tokio main
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [x] 2. Implement utility modules
  - [x] 2.1 Create `src/utils.rs` with `sanitize_filename`, `validate_file_size`, `get_file_size_formatted`, `sanitize_for_subprocess`, `validate_show_name`, `validate_output_path`, and year-stripping logic for show names
    - _Requirements: 2.2, 9.3, 9.4, 16.1, 16.2, 16.3_
  - [x] 2.2 Write property tests for utils: year stripping (Property 3), file size validation (Property 14), input sanitization (Property 17), show name length validation (Property 18)
    - **Property 3: Year stripping preserves base name**
    - **Property 14: File size validation**
    - **Property 17: Input sanitization removes dangerous characters**
    - **Property 18: Show name length validation**
    - **Validates: Requirements 2.2, 9.3, 9.4, 16.1, 16.2, 16.3**
  - [x] 2.3 Create `src/ffmpeg.rs` with `FfmpegErrorType` enum, `FfmpegError` struct, `FfmpegErrorParser`, `convert_audio` async function, and `get_audio_duration` function
    - _Requirements: 9.1, 9.2, 9.5_
  - [x] 2.4 Write property tests for FFmpeg: command construction (Property 12), error categorization (Property 13)
    - **Property 12: FFmpeg command construction**
    - **Property 13: FFmpeg error categorization**
    - **Validates: Requirements 9.1, 9.2**
  - [x] 2.5 Create `src/retry.rs` with generic `retry_with_backoff` async function
    - _Requirements: 13.1, 13.2, 13.3_
  - [x] 2.6 Write property test for retry logic (Property 16)
    - **Property 16: Retry with exponential backoff**
    - **Validates: Requirements 13.1, 13.2, 13.3**
  - [x] 2.7 Create `src/rate_limiter.rs` with `RateLimiter` struct implementing delay enforcement with random jitter
    - _Requirements: 11.1, 11.2, 11.3_
  - [x] 2.8 Write property test for rate limiter (Property 15)
    - **Property 15: Rate limiter delay bounds**
    - **Validates: Requirements 11.1, 11.3**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement orchestrator
  - [x] 4.1 Create `src/orchestrator.rs` with `Orchestrator` struct, `OrchestratorConfig`, `ProcessingResults`, `ShowFolder`, and `ShowResult` types
    - _Requirements: 2.1, 2.5, 3.1, 3.2, 3.3, 3.4, 4.1, 4.4_
  - [x] 4.2 Implement `process_directory` method: directory scanning, existing theme detection, scraper chain iteration, result aggregation, and summary display with colored output
    - _Requirements: 2.1, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 12.1_
  - [x] 4.3 Write property tests for orchestrator: directory scanning completeness (Property 2), existing theme detection and skip (Property 4), force mode (Property 5), scraper chain short-circuit (Property 6), error isolation (Property 7)
    - **Property 2: Directory scanning completeness**
    - **Property 4: Existing theme detection and skip behavior**
    - **Property 5: Force mode deletes existing theme**
    - **Property 6: Scraper chain short-circuits on success**
    - **Property 7: Error isolation across shows**
    - **Validates: Requirements 2.1, 3.1, 3.2, 3.3, 4.2, 4.3, 4.5, 12.1**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement scrapers
  - [x] 6.1 Create `src/scrapers/anime_themes.rs` implementing `ThemeScraper` for AnimeThemes.moe API using reqwest, with best-match selection via strsim, theme priority logic (OP1 > OP > first), video download, and FFmpeg audio extraction
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  - [x] 6.2 Write property tests for AnimeThemes: best match selection (Property 8), theme priority selection (Property 9)
    - **Property 8: Best match selection by string similarity**
    - **Property 9: Theme type priority selection**
    - **Validates: Requirements 6.2, 6.3**
  - [x] 6.3 Create `src/scrapers/tv_tunes.rs` implementing `ThemeScraper` for TelevisionTunes.co.uk using chromiumoxide browser automation, with search, best-match result selection, download, and WAV-to-MP3 conversion
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  - [x] 6.4 Create `src/scrapers/themes_moe.rs` implementing `ThemeScraper` for Themes.moe using chromiumoxide browser automation, with Anime Search mode selection, OP link extraction, media download, and video-to-MP3 conversion
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  - [x] 6.5 Create `src/scrapers/youtube.rs` implementing `ThemeScraper` for YouTube using yt-dlp subprocess, with multiple search query generation, duration filtering, and MP3 extraction
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  - [x] 6.6 Write property tests for YouTube: search query generation (Property 10), duration filtering (Property 11)
    - **Property 10: YouTube search query generation**
    - **Property 11: YouTube duration filtering**
    - **Validates: Requirements 8.1, 8.2**

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Wire everything together and add logging
  - [x] 8.1 Complete `src/main.rs`: wire CLI args to OrchestratorConfig, initialize all scrapers in priority order, set up tracing-subscriber for file + console logging, add dependency validation (ffmpeg, chromium, yt-dlp), elapsed time display, and error handling (CriticalError, KeyboardInterrupt equivalent via ctrlc)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 4.1, 10.6, 12.2, 12.3, 12.4_
  - [x] 8.2 Write property test for CLI invalid path rejection (Property 1)
    - **Property 1: Invalid path rejection**
    - **Validates: Requirements 1.8**

- [x] 9. Update agent hooks and steering documents
  - [x] 9.1 Update `.kiro/hooks/code-quality-review.kiro.hook` to reference Rust idioms, Clippy lints, and `cargo fmt` instead of Python/PEP 8
    - _Requirements: 15.3_
  - [x] 9.2 Update `.kiro/hooks/production-code-review.kiro.hook` to reference Rust patterns, Clippy, cargo test, and Rust-specific concerns instead of Python
    - _Requirements: 15.3_
  - [x] 9.3 Update `.kiro/hooks/security-review-hook.kiro.hook` to reference Rust safety (unsafe blocks, memory safety, Command injection) instead of Python
    - _Requirements: 15.3_
  - [x] 9.4 Update `.kiro/steering/tech.md` to reflect Rust toolchain, Cargo commands, crate dependencies, and proptest configuration
    - _Requirements: 15.4, 15.5_
  - [x] 9.5 Update `.kiro/steering/structure.md` to reflect the Rust project directory layout and module organization
    - _Requirements: 15.4_
  - [x] 9.6 Update `.kiro/steering/product.md` to note the Rust implementation
    - _Requirements: 15.4_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The Rust project lives alongside the existing Python code; the Python files can be removed after the rewrite is validated
