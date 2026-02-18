# Requirements Document

## Introduction

This document specifies the requirements for rewriting the Show Theme CLI tool from Python to Rust (2024 edition). The tool automates theme song retrieval for TV shows and anime series by scanning local directory structures, identifying shows by folder name, and downloading high-quality theme songs from multiple prioritized sources using a waterfall approach. The Rust rewrite preserves all existing functionality while gaining the benefits of Rust's performance, type safety, and single-binary distribution. The project tooling (agent hooks, steering documents) must also be updated to reflect the Rust ecosystem.

## Glossary

- **CLI**: The command-line interface application that users invoke to process show directories
- **Orchestrator**: The core component that coordinates directory scanning, scraper execution, and result aggregation
- **Scraper**: A source-specific module that searches for and downloads theme songs from a single source
- **Scraper_Chain**: The ordered sequence of scrapers tried in priority order (TelevisionTunes → AnimeThemes → Themes.moe → YouTube)
- **Show_Folder**: A subdirectory within the input directory, where the folder name represents the show name
- **Theme_File**: The output audio file (theme.mp3) saved in a Show_Folder
- **Audio_Converter**: The component responsible for converting downloaded audio/video files to MP3 format using FFmpeg
- **Rate_Limiter**: The component that enforces delays between requests to the same source to prevent IP bans
- **File_Validator**: The component that checks downloaded files meet minimum size requirements

## Requirements

### Requirement 1: CLI Argument Parsing and Configuration

**User Story:** As a user, I want to invoke the tool from the command line with various options, so that I can control how theme songs are downloaded.

#### Acceptance Criteria

1. WHEN a user provides a valid directory path as the input argument, THE CLI SHALL accept the path and begin processing
2. WHEN a user provides the `--force` or `-f` flag, THE CLI SHALL overwrite existing theme files instead of skipping them
3. WHEN a user provides the `--verbose` or `-v` flag, THE CLI SHALL enable debug-level logging output
4. WHEN a user provides the `--dry-run` flag, THE CLI SHALL simulate operations and display what would be processed without downloading any files
5. WHEN a user provides the `--timeout` or `-t` flag with an integer value, THE CLI SHALL use that value in seconds as the network timeout
6. WHEN a user provides the `--version` flag, THE CLI SHALL display the application name and version, then exit
7. WHEN a user provides no input directory and no `--version` flag, THE CLI SHALL display an error message and usage instructions
8. IF the provided input path does not exist or is not a directory, THEN THE CLI SHALL display a descriptive error message and exit with a non-zero status code

### Requirement 2: Directory Scanning and Show Discovery

**User Story:** As a user, I want the tool to automatically discover TV shows from my folder structure, so that I do not have to specify each show individually.

#### Acceptance Criteria

1. WHEN the Orchestrator receives a valid input directory, THE Orchestrator SHALL enumerate all immediate subdirectories as Show_Folders
2. WHEN a Show_Folder name contains a year in parentheses (e.g., "The Simpsons (1989)"), THE Orchestrator SHALL strip the year portion for search queries while preserving the original folder name for display
3. WHEN the input directory contains no subdirectories, THE Orchestrator SHALL display a message indicating no series folders were found and exit gracefully
4. WHEN a Show_Folder cannot be accessed due to permission errors, THE Orchestrator SHALL skip that folder, log a warning, and continue processing remaining folders
5. THE Orchestrator SHALL display the total count of discovered Show_Folders before beginning processing

### Requirement 3: Existing Theme Detection and Idempotency

**User Story:** As a user, I want the tool to skip shows that already have theme files, so that I can safely re-run the tool without re-downloading.

#### Acceptance Criteria

1. WHEN a Show_Folder contains a file named theme.mp3, theme.flac, or theme.wav, THE Orchestrator SHALL consider that show as already having a theme
2. WHEN a show already has a theme and the `--force` flag is not set, THE Orchestrator SHALL skip that show and display a "skipped" status
3. WHEN a show already has a theme and the `--force` flag is set, THE Orchestrator SHALL delete the existing theme file and proceed with downloading a new one
4. IF deletion of an existing theme file fails due to a permission error, THEN THE Orchestrator SHALL log a warning and continue to the next show

### Requirement 4: Waterfall Scraper Chain

**User Story:** As a user, I want the tool to try multiple sources in priority order, so that I get the best available theme song for each show.

#### Acceptance Criteria

1. THE Scraper_Chain SHALL attempt sources in the fixed order: TelevisionTunes, AnimeThemes, Themes.moe, YouTube
2. WHEN a Scraper succeeds in downloading a valid theme file, THE Scraper_Chain SHALL stop and not attempt subsequent sources for that show
3. WHEN a Scraper fails (returns false or raises an error), THE Scraper_Chain SHALL proceed to the next source in the chain
4. WHEN all scrapers in the Scraper_Chain fail for a show, THE Orchestrator SHALL mark that show as failed and display a failure status
5. WHEN a Scraper encounters an error, THE Scraper_Chain SHALL isolate the error so that it does not affect processing of other shows

### Requirement 5: TelevisionTunes Scraper

**User Story:** As a user, I want the tool to search TelevisionTunes.co.uk for TV show themes, so that I can get high-quality theme songs for Western TV shows.

#### Acceptance Criteria

1. WHEN searching for a show, THE TelevisionTunes Scraper SHALL navigate to the TelevisionTunes website, fill the search field, and submit the query using browser automation
2. WHEN search results are returned, THE TelevisionTunes Scraper SHALL select the best matching result by comparing result text against the show name
3. WHEN a download link is found on the result page, THE TelevisionTunes Scraper SHALL download the audio file
4. WHEN the downloaded file is in WAV format, THE Audio_Converter SHALL convert the file to MP3 format
5. IF the browser automation times out, THEN THE TelevisionTunes Scraper SHALL retry up to 3 times with exponential backoff

### Requirement 6: AnimeThemes Scraper

**User Story:** As a user, I want the tool to search AnimeThemes.moe for anime themes, so that I can get opening themes for anime series.

#### Acceptance Criteria

1. WHEN searching for an anime, THE AnimeThemes Scraper SHALL query the AnimeThemes.moe REST API with the show name and request theme entries with video links
2. WHEN multiple anime results are returned, THE AnimeThemes Scraper SHALL select the best match using string similarity comparison
3. WHEN selecting a theme from the matched anime, THE AnimeThemes Scraper SHALL prefer OP1 (first opening), then any OP, then the first available theme
4. WHEN a video URL is obtained, THE AnimeThemes Scraper SHALL download the video file and extract audio using FFmpeg
5. IF the API request times out, THEN THE AnimeThemes Scraper SHALL retry up to 3 times with exponential backoff

### Requirement 7: Themes.moe Scraper

**User Story:** As a user, I want the tool to search Themes.moe as an additional anime source, so that I have more chances of finding anime themes.

#### Acceptance Criteria

1. WHEN searching for an anime, THE Themes.moe Scraper SHALL navigate to the Themes.moe website, select the "Anime Search" mode, and submit the search query using browser automation
2. WHEN search results contain a table with theme links, THE Themes.moe Scraper SHALL select the first OP (opening) theme link
3. WHEN a media URL is obtained, THE Themes.moe Scraper SHALL download the media file
4. WHEN the downloaded file is a video format (mp4 or webm), THE Audio_Converter SHALL extract audio and convert to MP3
5. IF the browser automation times out, THEN THE Themes.moe Scraper SHALL retry up to 3 times with exponential backoff

### Requirement 8: YouTube Fallback Scraper

**User Story:** As a user, I want the tool to fall back to YouTube when other sources fail, so that I can still get theme songs for less common shows.

#### Acceptance Criteria

1. WHEN searching for a show on YouTube, THE YouTube Scraper SHALL try multiple search query variations in order: "{show} theme song", "{show} opening theme", "{show} intro theme", "{show} main theme", "{show} title sequence", "{show} op theme"
2. WHEN a search result is found, THE YouTube Scraper SHALL check the video duration and skip videos longer than 600 seconds
3. WHEN a suitable video is found, THE YouTube Scraper SHALL download the audio using yt-dlp and convert to MP3 format
4. WHEN a search query yields no results or the video is too long, THE YouTube Scraper SHALL proceed to the next query variation
5. WHEN all query variations are exhausted without success, THE YouTube Scraper SHALL return a failure result

### Requirement 9: Audio Conversion and Validation

**User Story:** As a user, I want downloaded audio to be consistently in MP3 format and validated, so that I get reliable, playable theme files.

#### Acceptance Criteria

1. THE Audio_Converter SHALL use FFmpeg to convert audio/video files to MP3 format with 320kbps bitrate using the libmp3lame codec
2. WHEN FFmpeg conversion fails, THE Audio_Converter SHALL parse the stderr output and categorize the error (missing codec, corrupted input, disk space, permission denied, timeout, invalid format)
3. WHEN conversion completes, THE File_Validator SHALL verify the output file exceeds 500KB minimum size
4. WHEN a converted file is smaller than 500KB, THE File_Validator SHALL delete the file and report failure
5. WHEN temporary files are created during conversion, THE Audio_Converter SHALL clean up temporary files regardless of success or failure

### Requirement 10: Console Output and Progress Display

**User Story:** As a user, I want clear, colored console output with progress tracking, so that I can monitor the tool's operation.

#### Acceptance Criteria

1. THE CLI SHALL display colored status indicators: green for success, yellow for skipped, red for failed
2. WHEN processing begins, THE CLI SHALL display the total number of discovered show folders
3. WHEN processing each show, THE CLI SHALL display the current folder number out of the total (e.g., "Folder 3/15")
4. WHEN a theme is successfully downloaded, THE CLI SHALL display the source name, file size, and audio duration
5. WHEN all processing completes, THE CLI SHALL display a summary table with counts of successful, skipped, and failed shows
6. WHEN all processing completes, THE CLI SHALL display the total elapsed time

### Requirement 11: Rate Limiting

**User Story:** As a user, I want the tool to rate-limit requests to sources, so that I do not get IP-banned from theme song websites.

#### Acceptance Criteria

1. THE Rate_Limiter SHALL enforce a random delay between 1.0 and 3.0 seconds between consecutive requests to the same source
2. WHEN a request is made to a source, THE Rate_Limiter SHALL record the timestamp of the request
3. WHEN a subsequent request is made to the same source before the minimum delay has elapsed, THE Rate_Limiter SHALL wait for the remaining delay period

### Requirement 12: Error Isolation and Logging

**User Story:** As a user, I want errors in one show to not affect other shows, and I want a log file for debugging, so that the tool is robust and diagnosable.

#### Acceptance Criteria

1. WHEN an error occurs while processing a single show, THE Orchestrator SHALL catch the error, log it, and continue processing the next show
2. THE CLI SHALL write structured log entries to a timestamped log file (show-theme-cli-YYYYMMDD_HHMMSS.log)
3. WHEN verbose mode is enabled, THE CLI SHALL also output debug-level log messages to the console
4. WHEN a scraper encounters a network error, THE Orchestrator SHALL log the source name, show name, error type, and duration of the attempt

### Requirement 13: Retry with Exponential Backoff

**User Story:** As a user, I want the tool to retry failed network requests, so that transient network issues do not cause unnecessary failures.

#### Acceptance Criteria

1. WHEN a network request fails with a timeout error, THE Scraper SHALL retry up to 3 times
2. THE Scraper SHALL apply exponential backoff with a factor of 2.0 between retries
3. IF all retry attempts fail, THEN THE Scraper SHALL return a failure result and allow the Scraper_Chain to proceed to the next source

### Requirement 14: Scraper Trait Interface

**User Story:** As a developer, I want all scrapers to implement a common interface, so that the orchestrator can treat them uniformly and new sources can be added easily.

#### Acceptance Criteria

1. THE Scraper trait SHALL define a `search_and_download` method that accepts a show name and output path and returns a success/failure result
2. THE Scraper trait SHALL define a `source_name` method that returns a human-readable identifier for the source
3. WHEN a new scraper is implemented, THE Scraper trait SHALL allow it to be added to the Scraper_Chain without modifying the Orchestrator

### Requirement 15: Rust 2024 Edition and Project Tooling

**User Story:** As a developer, I want the project to use modern Rust (2024 edition) and have updated agent hooks and steering documents, so that the tooling reflects the Rust ecosystem instead of Python.

#### Acceptance Criteria

1. THE CLI SHALL be built as a Cargo project using Rust edition 2024 in Cargo.toml
2. WHEN the project is initialized, THE CLI SHALL include a Cargo.toml with all required dependencies (clap, reqwest, indicatif, colored, chromiumoxide, tokio, etc.)
3. THE CLI SHALL update the agent hooks (.kiro/hooks/) to reference Rust idioms, Clippy lints, and Rust best practices instead of Python/PEP 8
4. THE CLI SHALL update the steering documents (.kiro/steering/) to reflect the Rust project structure, Cargo commands, and Rust testing conventions
5. WHEN running quality checks, THE CLI project SHALL use `cargo clippy` for linting and `cargo fmt` for formatting instead of pylint

### Requirement 16: Input Sanitization and Security

**User Story:** As a user, I want the tool to safely handle arbitrary folder names, so that special characters in show names do not cause security issues or crashes.

#### Acceptance Criteria

1. WHEN a show name contains shell metacharacters or control characters, THE CLI SHALL sanitize the name before passing it to subprocess calls or network requests
2. WHEN a show name exceeds 200 characters, THE CLI SHALL reject it and skip that folder
3. WHEN constructing file paths, THE CLI SHALL validate that paths do not contain traversal sequences (e.g., "..")
