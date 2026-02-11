# Requirements Document

## Introduction

The Show Theme CLI is a command-line tool that automates the retrieval of theme songs for TV shows and anime series stored in a local directory structure. The tool scans directories, identifies shows by folder name, and downloads high-quality theme songs from multiple prioritized sources, with automatic audio extraction and format conversion when necessary.

## Glossary

- **CLI**: Command-Line Interface - the text-based interface for user interaction
- **Theme_Downloader**: The core system that orchestrates theme song retrieval
- **Scraper**: A component that retrieves theme songs from a specific source
- **Series_Folder**: A directory containing files for a single TV show or anime series
- **Theme_File**: An audio file (MP3, FLAC, or WAV) containing a show's theme song
- **Source**: A website or service from which theme songs can be retrieved (TelevisionTunes, AnimeThemes, Themes.moe, YouTube)
- **Web_Automation**: Using Playwright to interact with websites programmatically
- **API_Client**: HTTP client for making REST API requests
- **Audio_Extractor**: FFmpeg-based tool for extracting audio from video files

## Requirements

### Requirement 1: Directory Scanning and Show Identification

**User Story:** As a user, I want the tool to scan my TV show directory structure, so that it can identify all shows that need theme songs.

#### Acceptance Criteria

1. WHEN the user provides an input directory path, THE CLI SHALL validate that the path exists and is accessible
2. WHEN scanning the input directory, THE CLI SHALL identify each subdirectory as a potential Series_Folder
3. WHEN a Series_Folder is empty or inaccessible, THE CLI SHALL skip it and log a warning
4. THE CLI SHALL extract the show name from each Series_Folder directory name
5. WHEN the --dry-run flag is set, THE CLI SHALL simulate the scan without downloading files

### Requirement 2: Existing Theme File Detection

**User Story:** As a user, I want the tool to skip shows that already have theme songs, so that I don't waste time re-downloading existing files.

#### Acceptance Criteria

1. WHEN a Theme_File exists in a Series_Folder (theme.mp3, theme.flac, or theme.wav), THE CLI SHALL skip that folder by default
2. WHEN the --force flag is set, THE CLI SHALL process folders even if a Theme_File exists
3. WHEN skipping a folder due to existing Theme_File, THE CLI SHALL log the skip with status "[SKIPPED] File exists"
4. THE CLI SHALL check for all supported theme file extensions (mp3, flac, wav) when determining if a theme already exists
5. WHEN any supported theme file format exists, THE CLI SHALL not re-retrieve the theme unless --force is specified

### Requirement 3: TelevisionTunes Source Integration

**User Story:** As a user, I want the tool to search TelevisionTunes.co.uk first, so that I can get high-quality TV show themes from a dedicated source.

#### Acceptance Criteria

1. WHEN searching for a show theme, THE Scraper SHALL navigate to https://www.televisiontunes.co.uk/ using Web_Automation
2. WHEN the search page loads, THE Scraper SHALL locate the search input field and enter the show name
3. WHEN search results are returned, THE Scraper SHALL identify the most relevant result using exact match or first result heuristics
4. WHEN a matching result is found, THE Scraper SHALL navigate to the song page and locate the download link
5. WHEN a download link is found, THE Scraper SHALL download the audio file to the Series_Folder
6. IF the search fails or no download link is found, THEN THE Scraper SHALL return failure status

### Requirement 4: AnimeThemes API Integration

**User Story:** As a user, I want the tool to search AnimeThemes.moe as a fallback, so that I can get anime opening themes with high accuracy.

#### Acceptance Criteria

1. WHEN TelevisionTunes fails, THE API_Client SHALL query the AnimeThemes.moe API at https://api.animethemes.moe/search
2. WHEN making the API request, THE API_Client SHALL include the show name as a URL-encoded query parameter with include=animethemes.animethemeentries.videos
3. WHEN the API returns results, THE API_Client SHALL parse the JSON response and match the most similar anime by name
4. WHEN multiple themes exist for a show, THE API_Client SHALL prefer opening themes (Type: "OP") over ending themes, and prefer "OP1" when available
5. WHEN a theme video URL is found, THE Audio_Extractor SHALL download the video file and extract the audio track
6. WHEN extracting audio, THE Audio_Extractor SHALL convert the output to MP3 format at 320kbps quality
7. IF the API request fails or no matching anime is found, THEN THE API_Client SHALL return failure status

### Requirement 5: Themes.moe Source Integration

**User Story:** As a user, I want the tool to try Themes.moe as an additional anime source, so that I have more coverage for anime themes.

#### Acceptance Criteria

1. WHEN AnimeThemes fails, THE Scraper SHALL navigate to Themes.moe using Web_Automation
2. WHEN the site loads, THE Scraper SHALL check for a general search functionality
3. IF no search functionality exists, THEN THE Scraper SHALL log a warning and return failure status
4. WHEN search functionality exists, THE Scraper SHALL input the show name and submit the search
5. WHEN results are returned, THE Scraper SHALL locate the audio or video element and extract the source URL
6. WHEN a source URL is found, THE Scraper SHALL download the media and extract audio if necessary

### Requirement 6: YouTube Fallback Integration

**User Story:** As a user, I want the tool to search YouTube as a last resort, so that I can still get theme songs when dedicated sources fail.

#### Acceptance Criteria

1. WHEN all other sources fail, THE Scraper SHALL use yt-dlp to search YouTube with the query "{Show Name} full theme song"
2. WHEN searching YouTube, THE Scraper SHALL limit results to the first match (ytsearch1)
3. WHEN a video is found, THE Scraper SHALL download the best available audio quality
4. WHEN downloading, THE Scraper SHALL extract audio and convert to MP3 format at 192kbps minimum quality
5. THE Scraper SHALL ensure no playlists are downloaded, only single videos

### Requirement 7: Audio Processing and Format Conversion

**User Story:** As a developer, I want all theme files to be in a consistent format, so that playback is reliable across different media players.

#### Acceptance Criteria

1. WHEN a theme is downloaded in a non-MP3 format, THE Audio_Extractor SHALL convert it to MP3
2. WHEN converting to MP3, THE Audio_Extractor SHALL use 320kbps bitrate for sources that support it, and 192kbps minimum for others
3. WHEN conversion is complete, THE Audio_Extractor SHALL save the file as "theme.mp3" in the Series_Folder
4. WHEN a downloaded file is smaller than 500KB, THE CLI SHALL treat it as corrupt and mark the download as failed
5. WHEN audio extraction or conversion fails, THE CLI SHALL log the error and proceed to the next source

### Requirement 8: File Naming and Placement

**User Story:** As a user, I want theme files to be consistently named and placed, so that I can easily locate them in my library.

#### Acceptance Criteria

1. THE CLI SHALL save all theme files with the name "theme.mp3" in the respective Series_Folder
2. WHEN creating file paths, THE CLI SHALL sanitize filenames to ensure OS compatibility
3. WHEN a Theme_File already exists and --force is set, THE CLI SHALL overwrite the existing file
4. THE CLI SHALL validate that the final file size is greater than 500KB before marking as successful

### Requirement 9: Error Handling and Retry Logic

**User Story:** As a user, I want the tool to handle network errors gracefully, so that temporary issues don't cause complete failures.

#### Acceptance Criteria

1. WHEN a network request times out, THE CLI SHALL retry up to 3 times with exponential backoff
2. WHEN a source returns an error, THE CLI SHALL log the error and proceed to the next source
3. WHEN all sources fail for a show, THE CLI SHALL log "[FAILED] No sources found" and continue to the next show
4. WHEN making web requests, THE CLI SHALL add random delays between 1-3 seconds to avoid rate limiting
5. IF a critical error occurs (invalid input directory, missing dependencies), THEN THE CLI SHALL display an error message and exit

### Requirement 10: Progress Reporting and User Feedback

**User Story:** As a user, I want to see real-time progress and results, so that I know what the tool is doing and what succeeded or failed.

#### Acceptance Criteria

1. WHEN processing each show, THE CLI SHALL display which source is currently being attempted
2. WHEN a download succeeds, THE CLI SHALL display "[SUCCESS] Source: {source_name} | File: {file_path}"
3. WHEN a show is skipped, THE CLI SHALL display "[SKIPPED] File exists"
4. WHEN all sources fail, THE CLI SHALL display "[FAILED] No sources found"
5. WHEN processing is complete, THE CLI SHALL display a summary table with success/failure counts
6. WHEN --verbose flag is set, THE CLI SHALL display debug information including API responses and Playwright traces
7. WHEN processing multiple folders, THE CLI SHALL display progression through the folder list with colored status indicators (green for success, yellow for skipped, red for failed)
8. WHEN displaying folder progression, THE CLI SHALL show the current folder number and total folder count

### Requirement 11: Command-Line Interface

**User Story:** As a user, I want a simple and intuitive command-line interface, so that I can easily configure and run the tool.

#### Acceptance Criteria

1. THE CLI SHALL accept a required positional argument for the input directory path
2. THE CLI SHALL support a --force/-f flag to overwrite existing theme files (default: False)
3. THE CLI SHALL support a --verbose/-v flag to enable debug logging (default: False)
4. THE CLI SHALL support a --dry-run flag to simulate operations without downloading (default: False)
5. WHEN invalid arguments are provided, THE CLI SHALL display usage help and exit with an error code
6. WHEN the user requests help (--help), THE CLI SHALL display comprehensive usage documentation

### Requirement 12: Dependency Management and Configuration

**User Story:** As a developer, I want clear dependency specifications and configuration, so that the tool can be easily installed and maintained.

#### Acceptance Criteria

1. THE CLI SHALL require Python 3.12 or higher
2. THE CLI SHALL use Typer for command-line interface implementation
3. THE CLI SHALL use Rich for console output and progress display
4. THE CLI SHALL use Playwright for web automation tasks
5. THE CLI SHALL use httpx for HTTP API requests
6. THE CLI SHALL use yt-dlp for YouTube downloads
7. THE CLI SHALL require FFmpeg to be installed on the system for audio processing
8. THE CLI SHALL use pylint for code quality checks

### Requirement 13: Development Reference and Documentation

**User Story:** As a developer, I want access to API documentation and programming language references during development, so that I can implement features correctly and efficiently.

#### Acceptance Criteria

1. WHEN implementing API integrations, THE Developer SHALL use Context7 MCP to access API documentation for AnimeThemes.moe and other services
2. WHEN working with Python libraries, THE Developer SHALL use Context7 MCP to reference documentation for Typer, Rich, Playwright, httpx, and yt-dlp
3. WHEN implementing audio processing, THE Developer SHALL use Context7 MCP to reference FFmpeg documentation and best practices
4. WHEN encountering implementation questions, THE Developer SHALL consult Context7 MCP for Python 3.12+ language features and standard library usage
