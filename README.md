# Show Theme CLI

A command-line tool that automates theme song retrieval for TV shows and anime series. Scans local directory structures, identifies shows by folder name, and downloads high-quality theme songs from multiple prioritized sources.

## Features

- **Automatic theme discovery**: Scans directories and downloads theme songs automatically
- **Content mode selection**: Choose TV, Anime, or Both modes for optimized source usage
- **Multiple sources**: Tries sources in priority order based on content type
- **Smart fallback**: Automatically tries next source if one fails
- **Skip existing themes**: Won't re-download unless you use `--force`
- **Rich console output**: Beautiful progress tracking with colored status indicators
- **Audio format conversion**: Automatically converts to MP3 format
- **Dry-run mode**: Test without downloading anything

## Requirements

- **Python 3.12+**
- **FFmpeg**: Required for audio extraction and format conversion
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Installation

1. Clone or download this repository

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:

```bash
playwright install chromium
```

4. Verify FFmpeg is installed:

```bash
ffmpeg -version
```

## Usage

### Basic Usage

```bash
# Process both TV shows and anime (default)
python main.py /path/to/shows

# Process TV shows only
python main.py /path/to/tv_shows --mode tv

# Process anime only
python main.py /path/to/anime --mode anime
```

This will scan the directory for subdirectories (each representing a show) and download theme songs to each folder as `theme.mp3`.

### Command-Line Options

```bash
python main.py [OPTIONS] INPUT_DIR
```

**Arguments:**

- `INPUT_DIR`: Root directory containing show folders (required)

**Options:**

- `--mode`, `-m`: Content type - tv, anime, or both (default: both)
- `--force`, `-f`: Overwrite existing theme files (default: False)
- `--verbose`, `-v`: Enable debug logging (default: False)
- `--dry-run`: Simulate operations without downloading (default: False)
- `--timeout`, `-t`: Network timeout in seconds (default: 30)
- `--version`: Show version and exit
- `--help`: Show help message and exit

### Examples

**Download themes for all shows (both TV and anime):**

```bash
python main.py ~/Media/Shows
```

**Download themes for TV shows only:**

```bash
python main.py ~/Media/TV_Shows --mode tv
```

**Download themes for anime only:**

```bash
python main.py ~/Media/Anime --mode anime
```

**Force re-download existing themes:**

```bash
python main.py ~/Media/TV_Shows --force
```

**Test without downloading (dry run):**

```bash
python main.py ~/Media/TV_Shows --dry-run
```

**Enable verbose logging:**

```bash
python main.py ~/Media/TV_Shows --verbose
```

**Combine options:**

```bash
python main.py ~/Media/Anime --mode anime --force --verbose
```

## Directory Structure

The tool expects your media to be organized with one folder per show:

```
TV_Shows/
├── Breaking Bad/
├── The Office/
├── Attack on Titan/
└── Cowboy Bebop/
```

After running, theme files will be added in a `theme-music` subfolder:

```
TV_Shows/
├── Breaking Bad/
│   └── theme-music/
│       └── theme.mp3
├── The Office/
│   └── theme-music/
│       └── theme.mp3
├── Attack on Titan/
│   └── theme-music/
│       └── theme.mp3
└── Cowboy Bebop/
    └── theme-music/
        └── theme.mp3
```

## Supported Sources

The tool tries sources in priority order based on the selected mode:

### TV Mode (`--mode tv`)

1. **TelevisionTunes** (televisiontunes.co.uk)
   - Best for TV shows
   - High-quality official themes
   - Web scraping via Playwright

2. **YouTube** (youtube.com)
   - Fallback for any show
   - Searches for "{Show Name} full theme song"
   - Uses yt-dlp for downloads
   - Minimum 192kbps audio quality

### Anime Mode (`--mode anime`)

1. **AnimeThemes** (animethemes.moe)
   - Best for anime
   - Official opening/ending themes
   - REST API with video downloads
   - Prefers OP1 > OP > ED

2. **Themes.moe** (themes.moe)
   - Additional anime source
   - Web scraping via Playwright

3. **YouTube** (youtube.com)
   - Fallback for any show
   - Searches for "{Show Name} full theme song"
   - Uses yt-dlp for downloads
   - Minimum 192kbps audio quality

### Both Mode (`--mode both`, default)

1. **TelevisionTunes** (televisiontunes.co.uk)
2. **AnimeThemes** (animethemes.moe)
3. **Themes.moe** (themes.moe)
4. **YouTube** (youtube.com)

## Output

The tool provides real-time progress with colored status indicators:

```
Found 4 series folders

Folder 1/4
Processing: Breaking Bad
  Trying TelevisionTunes... ✓
SUCCESS Source: TelevisionTunes | File: /path/to/Breaking Bad/theme.mp3

Folder 2/4
SKIPPED The Office - File exists

Folder 3/4
Processing: Attack on Titan
  Trying TelevisionTunes... ✗
  Trying AnimeThemes... ✓
SUCCESS Source: AnimeThemes | File: /path/to/Attack on Titan/theme.mp3

Folder 4/4
Processing: Unknown Show
  Trying TelevisionTunes... ✗
  Trying AnimeThemes... ✗
  Trying Themes.moe... ✗
  Trying YouTube... ✗
FAILED No sources found for Unknown Show

Processing Summary
┏━━━━━━━━━┳━━━━━━━┓
┃ Status  ┃ Count ┃
┡━━━━━━━━━╇━━━━━━━┩
│ Success │     2 │
│ Skipped │     1 │
│ Failed  │     1 │
└─────────┴───────┘
```

## File Validation

Downloaded theme files are validated to ensure quality:

- **Minimum file size**: 500KB (files smaller than this are rejected as corrupt)
- **Format**: All themes are converted to MP3 format
- **Bitrate**: 320kbps for high-quality sources, 192kbps minimum for YouTube

## Error Handling

The tool handles errors gracefully:

- **Network timeouts**: Retries up to 3 times with exponential backoff
- **Missing sources**: Automatically tries next source
- **Permission errors**: Skips folder with warning
- **Single show failure**: Doesn't stop processing other shows

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m property      # Property-based tests only
pytest -m integration   # Integration tests only

# Run with coverage
pytest --cov=core --cov=scrapers
```

### Code Quality

```bash
# Run pylint
pylint core/ scrapers/ tests/

# Run on specific module
pylint core/orchestrator.py
```

## Troubleshooting

**"FFmpeg not found" error:**

- Install FFmpeg using your package manager (see Requirements section)
- Verify installation: `ffmpeg -version`

**"Playwright browsers not installed" error:**

- Run: `playwright install chromium`

**All sources failing:**

- Check your internet connection
- Try with `--verbose` flag to see detailed error messages
- Some shows may have unusual names that don't match source databases

**Permission errors:**

- Ensure you have write permissions to the target directories
- Try running with appropriate permissions

## License

This project is provided as-is for personal use.

## Contributing

This tool was built using spec-driven development with property-based testing. See `.kiro/specs/show-theme-cli/` for detailed requirements, design, and implementation tasks.
