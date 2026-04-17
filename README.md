# Audio Theme Downloader

[![Build and Publish Release](https://github.com/emperor-jimmu/aud-themer/actions/workflows/main.yml/badge.svg)](https://github.com/emperor-jimmu/aud-themer/actions/workflows/main.yml)

A command-line tool that automates theme song retrieval for TV shows and anime series. Scans local directory structures, identifies shows by folder name, and downloads high-quality theme songs from multiple prioritized sources.

## Features

- **Automatic theme discovery**: Scans directories and downloads theme songs automatically
- **Content mode selection**: Choose TV, Anime, YouTube-only, or Both modes
- **Multiple sources**: Tries sources in priority order based on content type
- **Smart fallback**: Automatically tries next source if one fails (waterfall pattern)
- **Skip existing themes**: Won't re-download unless you use `--force`
- **YouTube cookie support**: Extracts browser cookies for yt-dlp by default (Chrome) to avoid bot detection
- **Rich console output**: Progress tracking with colored status indicators
- **Audio format conversion**: Automatically converts to high-quality MP3 (320kbps)
- **Dry-run mode**: Test without downloading anything
- **File validation**: Validates file size (min 500KB) and supports MP3, FLAC, WAV formats

## Requirements

- **Rust** (2024 edition) — for building from source
- **FFmpeg**: Required for audio extraction and format conversion
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- **yt-dlp**: Required for YouTube downloads
  - `pip install yt-dlp` or download from [yt-dlp releases](https://github.com/yt-dlp/yt-dlp/releases)
- **Chromium** (optional): Used automatically by browser-based scrapers; downloaded on first use if not present

## Installation

```bash
# Clone the repository
git clone https://github.com/emperor-jimmu/aud-themer.git
cd aud-themer

# Build
cargo build --release

# Verify dependencies
ffmpeg -version
yt-dlp --version
```

## Usage

### Basic Usage

```bash
# Process both TV shows and anime (default — all sources)
cargo run --release -- /path/to/shows

# Process TV shows only
cargo run --release -- /path/to/tv_shows --mode tv

# Process anime only
cargo run --release -- /path/to/anime --mode anime

# YouTube-only mode
cargo run --release -- /path/to/shows --mode youtube
```

### Command-Line Options

```
audio-theme-downloader [OPTIONS] <INPUT_DIR>
```

| Option | Short | Description | Default |
|---|---|---|---|
| `<INPUT_DIR>` | | Root directory containing show folders | required |
| `--mode` | `-m` | Content type: tv, anime, youtube, both | both |
| `--force` | `-f` | Overwrite existing theme files | false |
| `--verbose` | `-v` | Enable debug logging | false |
| `--dry-run` | | Simulate without downloading | false |
| `--timeout` | `-t` | Network timeout in seconds | 30 |
| `--log-dir` | | Directory for log files | current dir |
| `--cookies-from-browser` | | Browser to extract YouTube cookies from | chrome |
| `--no-cookies` | | Disable cookie extraction for yt-dlp | false |
| `--version` | | Show version and exit | |
| `--help` | | Show help message | |

### YouTube Cookie Authentication

YouTube requires authentication to avoid "Sign in to confirm you're not a bot" errors. By default, the tool extracts cookies from Chrome and passes them to yt-dlp.

```bash
# Default behavior — uses Chrome cookies
cargo run --release -- /path/to/shows

# Use Firefox cookies instead
cargo run --release -- /path/to/shows --cookies-from-browser firefox

# Use Edge cookies
cargo run --release -- /path/to/shows --cookies-from-browser edge

# Other supported browsers: brave, opera, chromium, safari, vivaldi
cargo run --release -- /path/to/shows --cookies-from-browser brave

# Disable cookie extraction entirely (YouTube will likely fail)
cargo run --release -- /path/to/shows --no-cookies
```

You must be logged into YouTube in the selected browser for this to work.

### Examples

```bash
# Force re-download existing themes
cargo run --release -- ~/Media/TV_Shows --force

# Dry run with verbose logging
cargo run --release -- ~/Media/Shows --dry-run --verbose

# Anime mode with Firefox cookies and custom timeout
cargo run --release -- ~/Media/Anime --mode anime --cookies-from-browser firefox --timeout 60
```

## Directory Structure

The tool expects one folder per show:

```
Shows/
├── Breaking Bad/
├── The Office/
├── Attack on Titan/
└── Cowboy Bebop/
```

After running, each folder gets a `theme-music` subfolder containing the theme file:

```
Shows/
├── Breaking Bad/
│   └── theme-music/
│       └── theme.mp3
├── The Office/
│   └── theme-music/
│       └── theme.mp3
└── ...
```

## Supported Sources

Sources are tried in waterfall order based on the selected mode:

| Mode | Source Order |
|---|---|
| `both` (default) | TelevisionTunes → Themes.moe → AnimeThemes → YouTube |
| `tv` | TelevisionTunes → YouTube |
| `anime` | Themes.moe → AnimeThemes → YouTube |
| `youtube` | YouTube only |

- **TelevisionTunes** — Best for Western TV shows. Browser automation via chromiumoxide.
- **AnimeThemes** (animethemes.moe) — REST API for anime OP/ED themes. Prefers OP1.
- **Themes.moe** — Additional anime source. Browser automation via chromiumoxide.
- **YouTube** — Fallback for anything. Uses yt-dlp with cookie authentication.

## File Validation

- Minimum file size: 500KB (smaller files are rejected as corrupt)
- Format: MP3, FLAC, or WAV (converted to MP3 320kbps)
- Duration filter: YouTube results capped at 10 minutes

## Error Handling

- Network timeouts retry up to 3 times with exponential backoff
- Built-in rate limiting (1-3 second delay between requests) to avoid source blocking
- Missing sources automatically fall through to the next one
- Single show failures don't stop processing of other shows
- Ctrl+C gracefully finishes the current operation before exiting

## Development

```bash
# Build
cargo build

# Run tests
cargo test

# Run property-based tests
cargo test properties

# Lint
cargo clippy -- -D warnings

# Format
cargo fmt
```

## Troubleshooting

**"Sign in to confirm you're not a bot" from YouTube:**
Make sure you're logged into YouTube in Chrome (or whichever browser you specify with `--cookies-from-browser`). If Chrome doesn't work, try `--cookies-from-browser edge` or `firefox`.

**"FFmpeg not found" error:**
Install FFmpeg and make sure it's on your PATH.

**All sources failing:**
Run with `--verbose` to see detailed logs. Check your internet connection. Some shows may have names that don't match source databases.

## License

This project is provided as-is for personal use.
