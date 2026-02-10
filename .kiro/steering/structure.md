# Project Structure

## Directory Layout

```
.
├── main.py                 # CLI entry point (Typer application)
├── core/                   # Core orchestration and utilities
│   ├── __init__.py
│   ├── orchestrator.py     # Main processing logic and source coordination
│   └── utils.py            # File system operations, path validation, audio processing
├── scrapers/               # Source-specific scraper implementations
│   ├── __init__.py
│   ├── base.py             # ThemeScraper abstract base class
│   ├── tv_tunes.py         # TelevisionTunes.com scraper (Playwright)
│   ├── anime_themes.py     # AnimeThemes.moe API scraper (httpx)
│   ├── themes_moe.py       # Themes.moe scraper (Playwright)
│   └── youtube.py          # YouTube fallback scraper (yt-dlp)
├── tests/                  # Test suite
│   ├── __init__.py
│   ├── unit/               # Unit tests for specific examples
│   ├── properties/         # Property-based tests (Hypothesis)
│   └── integration/        # End-to-end tests with mocked sources
├── .kiro/                  # Kiro configuration
│   ├── specs/              # Feature specifications
│   └── steering/           # Project steering documents
├── requirements.txt        # Python dependencies
├── pytest.ini              # Pytest configuration
└── .pylintrc               # Pylint configuration
```

## Architecture Patterns

### Modular Scraper Design
Each source is implemented as an independent scraper following the `ThemeScraper` interface:
- `search_and_download(show_name, output_path) -> bool`: Main entry point
- `get_source_name() -> str`: Human-readable source identifier

Scrapers are completely independent and swappable. The orchestrator tries them in priority order until one succeeds.

### Orchestration Pattern
The `Orchestrator` class coordinates the entire workflow:
1. Scans directory for series folders
2. Checks for existing theme files
3. Tries scrapers in priority order (TelevisionTunes → AnimeThemes → Themes.moe → YouTube)
4. Aggregates results and displays summary

### Fail-Fast with Fallback
Each scraper returns `True` on success or `False` on failure. The orchestrator immediately moves to the next source on failure. No retries within a single source (except for network timeouts).

### Rich Console Output
All user-facing output uses Rich library for:
- Colored status indicators (green=success, yellow=skipped, red=failed)
- Progress tracking with folder counts
- Summary tables at completion

## File Naming Conventions

### Output Files
- All theme files are saved as `theme.mp3` in the series folder
- Temporary files use `temp_*.webm` pattern (cleaned up after processing)

### Test Files
- Unit tests: `test_*.py` or `*_test.py`
- Property tests must include property reference in comments:
  ```python
  # Feature: show-theme-cli, Property 1: Path Validation Correctness
  ```

### Module Organization
- One class per file in `scrapers/`
- Utility functions grouped by purpose in `core/utils.py`
- Data models and enums in respective module files

## Key Design Principles

### Separation of Concerns
- CLI layer (main.py): Argument parsing and console setup
- Orchestration layer (core/): Business logic and coordination
- Scraper layer (scrapers/): Source-specific implementation
- Utility layer (core/utils.py): Shared functionality

### Idempotency
The tool can be safely re-run on the same directory:
- Existing themes are skipped by default
- Use `--force` flag to override and re-download

### Error Isolation
Errors in one show don't affect processing of other shows. Each series folder is processed independently with comprehensive error handling.

### Testability
- Abstract base class enables easy mocking of scrapers
- File system operations use Path objects for easy temp directory testing
- Network operations can be intercepted for testing

## Configuration Files

### .pylintrc
- Max line length: 100
- Indentation: 4 spaces
- Disabled warnings: missing-docstring, invalid-name, too-few-public-methods

### pytest.ini
- Test markers: `unit`, `integration`, `property`, `slow`
- Hypothesis: 100 examples per property test
- Output: verbose with short tracebacks

### .gitignore
- Python artifacts: `__pycache__/`, `*.pyc`, `.pytest_cache/`
- Virtual environments: `venv/`, `.venv/`
- Output files: `theme.mp3`, `theme.flac`, `theme.wav`, `temp_*.webm`
- IDE files: `.vscode/`, `.idea/`
