# Technology Stack

## Language and Runtime
- Python 3.12+
- Standard library modules for file system operations and subprocess management

## Core Dependencies

### CLI Framework
- **Typer** (>=0.9.0): Modern CLI framework with type hints and automatic help generation

### Console Output
- **Rich** (>=13.0.0): Beautiful console output with progress bars, tables, and colored status messages

### Web Automation
- **Playwright** (>=1.40.0): Robust browser automation for sites without APIs (TelevisionTunes, Themes.moe)

### HTTP Client
- **httpx** (>=0.25.0): Modern async-capable HTTP client for API calls (AnimeThemes.moe)

### Media Processing
- **yt-dlp** (>=2023.11.0): YouTube downloader for fallback source
- **FFmpeg**: External dependency for audio extraction and format conversion (must be installed separately)

### Testing
- **pytest** (>=7.4.0): Test framework
- **pytest-asyncio** (>=0.21.0): Async test support
- **Hypothesis** (>=6.92.0): Property-based testing library

## Code Quality
- **pylint**: Linting with configuration in `.pylintrc`
- Max line length: 100 characters
- 4-space indentation

## Common Commands

### Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Verify FFmpeg is installed
ffmpeg -version
```

### Testing
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

### Linting
```bash
# Run pylint on all Python files
pylint core/ scrapers/ tests/

# Run on specific module
pylint core/orchestrator.py
```

### Running the CLI
```bash
# Basic usage
python main.py /path/to/tv_shows

# With options
python main.py /path/to/tv_shows --force --verbose

# Dry run (no downloads)
python main.py /path/to/tv_shows --dry-run

# Show help
python main.py --help
```

## Testing Configuration

### pytest.ini
- Test discovery: `test_*.py`, `*_test.py`
- Test paths: `tests/`
- Markers: `unit`, `integration`, `property`, `slow`
- Hypothesis profile: default with 100 examples

### Hypothesis Settings
- Max examples: 100
- Deadline: None (no time limit per test)
