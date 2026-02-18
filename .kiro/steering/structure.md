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

- All theme files are saved as `theme.mp3` in each series folder
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
