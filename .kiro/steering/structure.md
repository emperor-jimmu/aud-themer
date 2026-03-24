# Project Structure

## Directory Layout

```
.
├── Cargo.toml              # Rust project manifest with dependencies and metadata
├── Cargo.lock              # Dependency lock file
├── src/                    # Source code
│   ├── main.rs             # CLI entry point (clap argument parsing, logging setup)
│   ├── config.rs           # Configuration constants
│   ├── orchestrator.rs     # Main processing logic and scraper coordination
│   ├── utils.rs            # File system operations, path validation, sanitization
│   ├── ffmpeg.rs           # FFmpeg subprocess wrapper and error parsing
│   ├── rate_limiter.rs     # Rate limiting with jitter
│   ├── retry.rs            # Generic retry with exponential backoff
│   └── scrapers/           # Source-specific scraper implementations
│       ├── mod.rs          # ThemeScraper trait definition and module exports
│       ├── tv_tunes.rs     # TelevisionTunes.co.uk scraper (chromiumoxide)
│       ├── anime_themes.rs # AnimeThemes.moe API scraper (reqwest)
│       ├── themes_moe.rs   # Themes.moe scraper (chromiumoxide)
│       └── youtube.rs      # YouTube fallback scraper (yt-dlp subprocess)
├── tests/                  # Test suite
│   ├── properties_*.rs     # Property-based tests (proptest)
│   ├── integration_*.rs    # Integration tests with mocked scrapers
│   └── common/             # Shared test utilities and fixtures
├── target/                 # Build artifacts (gitignored)
├── .kiro/                  # Kiro configuration
│   ├── specs/              # Feature specifications
│   ├── steering/           # Project steering documents
│   └── hooks/              # Agent hooks
└── .gitignore              # Git ignore patterns
```

## Architecture Patterns

### Modular Scraper Design

Each source is implemented as an independent scraper following the `ThemeScraper` trait:

```rust
#[async_trait]
pub trait ThemeScraper: Send + Sync {
    async fn search_and_download(&self, show_name: &str, output_path: &Path) -> anyhow::Result<bool>;
    fn source_name(&self) -> &str;
}
```

Scrapers are completely independent and swappable. The orchestrator tries them in priority order until one succeeds.

### Orchestration Pattern

The `Orchestrator` struct coordinates the entire workflow:

1. Scans directory for series folders
2. Checks for existing theme files
3. Tries scrapers in waterfall priority order:
   - TelevisionTunes → AnimeThemes → Themes.moe → YouTube
4. Aggregates results and displays summary

### Fail-Fast with Fallback

Each scraper returns `Ok(true)` on success or `Ok(false)` on failure. The orchestrator immediately moves to the next source on failure. Network errors trigger retry logic with exponential backoff.

### Console Output

All user-facing output uses indicatif and colored crates for:

- Colored status indicators (green=success, yellow=skipped, red=failed)
- Progress tracking with folder counts
- Summary tables at completion

## File Naming Conventions

### Output Files

- All theme files are saved as `theme.mp3` in a `theme-music/` subfolder within each series folder
- Temporary files use `temp_*.webm` or `temp_*.wav` pattern (cleaned up after processing)

### Test Files

- Property tests: `tests/properties_*.rs`
- Integration tests: `tests/integration_*.rs`
- Property tests must include property reference in comments:

  ```rust
  // Feature: rust-rewrite, Property 1: Invalid path rejection
  ```

### Module Organization

- One scraper per file in `src/scrapers/`
- Utility functions grouped by purpose in dedicated modules (`utils.rs`, `ffmpeg.rs`, etc.)
- Data models and enums defined in respective module files

## Key Design Principles

### Separation of Concerns

- CLI layer (main.rs): Argument parsing and console setup
- Orchestration layer (orchestrator.rs): Business logic and coordination
- Scraper layer (scrapers/): Source-specific implementation
- Utility layer (utils.rs, ffmpeg.rs, etc.): Shared functionality

### Idempotency

The tool can be safely re-run on the same directory:

- Existing themes are skipped by default
- Use `--force` flag to override and re-download

### Error Isolation

Errors in one show don't affect processing of other shows. Each series folder is processed independently with comprehensive error handling using `anyhow::Result`.

### Testability

- Trait-based design enables easy mocking of scrapers
- File system operations use `Path` and `PathBuf` for easy temp directory testing
- Network operations can be intercepted for testing
- Property-based tests validate universal correctness properties

## Configuration Files

### Cargo.toml

- Edition: 2024
- Dependencies: clap, reqwest, tokio, chromiumoxide, indicatif, colored, anyhow, thiserror, tracing, strsim, proptest, etc.
- Binary target: `show-theme-cli`

### src/config.rs

Configuration constants used throughout the application:

- `MIN_FILE_SIZE_BYTES`: 500KB minimum for valid theme files
- `DEFAULT_TIMEOUT_SEC`: 30 seconds for network requests
- `DOWNLOAD_TIMEOUT_SEC`: 60 seconds for file downloads
- `AUDIO_BITRATE`: "320k" for MP3 conversion quality
- `MAX_VIDEO_DURATION_SEC`: 600 seconds (10 minutes) for YouTube
- `MAX_RETRY_ATTEMPTS`: 3 attempts for failed operations
- `RETRY_BACKOFF_FACTOR`: 2.0 for exponential backoff
- `USER_AGENT`: HTTP User-Agent header for all requests (format: "show-theme-cli/{version} (repo_url)")

### .gitignore

- Rust artifacts: `target/`, `Cargo.lock` (for libraries, included for binaries)
- Temporary files: `temp_*.webm`, `temp_*.wav`
- Log files: `*.log`
- IDE files: `.vscode/`, `.idea/`, `*.swp`
- OS files: `.DS_Store`, `Thumbs.db`

### rustfmt.toml (optional)

- Standard Rust formatting rules
- Max line width: 100 (default)

## Rust-Specific Patterns

### Error Handling

- Application-level errors use `anyhow::Result` for flexibility
- Domain-specific errors use `thiserror` derive macros
- FFmpeg errors are categorized into typed enum variants

### Async/Await

- Tokio runtime for async operations
- `async_trait` for trait methods
- Sequential processing to maintain console output order

### Resource Cleanup

- `Drop` implementations for browser instances
- `scopeguard` for temporary file cleanup
- RAII pattern for resource management

### Type Safety

- Strong typing for configuration constants
- Enum variants for scraper outcomes and error types
- Path types (`Path`, `PathBuf`) for file system operations

## Common Issues and Solutions

### HTTP 403 Forbidden Errors

- **Cause**: Missing or invalid User-Agent header in HTTP requests
- **Solution**: All HTTP clients must include `Config::USER_AGENT` in their builder
- **Example**: `.user_agent(Config::USER_AGENT)` in reqwest Client::builder()

### Themes.moe Not Finding Results

- **Cause**: Limited database coverage; not all anime are indexed
- **Solution**: Waterfall pattern automatically falls back to YouTube
- **Note**: Themes.moe pulls from AnimeThemes.moe CDN, so coverage depends on their database

### Browser Automation Failures

- **Cause**: Website structure changes or selector mismatches
- **Solution**: Use Playwright MCP or browser DevTools to inspect current page structure
- **Testing**: Verify selectors match actual DOM elements on live site

### YouTube Bot Detection / "Sign in to confirm" Errors

- **Cause**: YouTube requires authentication to serve search results and video streams
- **Solution**: The tool passes `--cookies-from-browser chrome` to yt-dlp by default, extracting cookies from the user's Chrome session
- **Override**: Use `--cookies-from-browser <browser>` to choose a different browser (firefox, edge, brave, opera, chromium, etc.)
- **Disable**: Use `--no-cookies` to skip cookie extraction entirely (will likely fail on YouTube)
- **Requirement**: The user must be logged into YouTube in the selected browser

### YouTube DPAPI Decryption Error ("Failed to decrypt with DPAPI")

- **Cause**: yt-dlp cannot decrypt Chrome's cookie store because Chrome is running and has the cookies locked, or the Windows DPAPI context doesn't match
- **Solution**: Close Chrome completely before running the tool, then retry
- **Alternative**: Switch to a browser that isn't running: `--cookies-from-browser edge` or `--cookies-from-browser firefox`
- **Disable**: Use `--no-cookies` to skip cookie extraction entirely (YouTube may still work without auth for some searches)
- **Reference**: https://github.com/yt-dlp/yt-dlp/issues/10927

### FFmpeg Conversion Errors

- **Cause**: Corrupted downloads, unsupported formats, or FFmpeg not installed
- **Solution**: Check FFmpeg installation, verify input file integrity, review error logs
- **Validation**: Ensure downloaded files meet minimum size requirements (500KB)
