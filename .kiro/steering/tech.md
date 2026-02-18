# Technology Stack

## Language and Runtime

- Rust 2024 edition
- Tokio async runtime for concurrent operations
- Standard library for file system operations and subprocess management

## Core Dependencies

### CLI Framework

- **clap** (>=4.0, derive feature): Modern CLI framework with derive macros for argument parsing

### Console Output

- **indicatif** (>=0.17): Progress bars and spinners
- **colored** (>=2.0): Colored terminal output
- **console** (>=0.15): Additional console utilities

### Web Automation

- **chromiumoxide** (>=0.5): Headless Chrome automation for sites without APIs (TelevisionTunes, Themes.moe)

### HTTP Client

- **reqwest** (>=0.11): Async HTTP client for API calls (AnimeThemes.moe)

### Async Runtime

- **tokio** (>=1.0, full feature): Async runtime for browser automation and HTTP requests
- **async-trait** (>=0.1): Trait support for async methods

### Media Processing

- **yt-dlp**: External dependency called as subprocess for YouTube downloads
- **FFmpeg**: External dependency for audio extraction and format conversion (must be installed separately)

### Error Handling

- **anyhow** (>=1.0): Flexible error handling for application-level errors
- **thiserror** (>=1.0): Derive macros for custom error types

### Utilities

- **strsim** (>=0.10): String similarity comparison for best-match selection
- **rand** (>=0.8): Random number generation for rate limiting jitter
- **scopeguard** (>=1.0): Cleanup guarantees for temporary files

### Logging

- **tracing** (>=0.1): Structured logging framework
- **tracing-subscriber** (>=0.3): Log formatting and output

### Serialization

- **serde** (>=1.0, derive feature): Serialization framework
- **serde_json** (>=1.0): JSON support for API responses

### Testing

- **proptest** (>=1.0): Property-based testing library

## Code Quality

- **clippy**: Rust linter with comprehensive lint checks
- **rustfmt**: Code formatter with standard Rust style
- Edition: 2024

## Common Commands

### Setup

```bash
# Build the project
cargo build

# Build optimized release binary
cargo build --release

# Install Chromium for browser automation
# (chromiumoxide will download it automatically on first use)

# Verify FFmpeg is installed
ffmpeg -version

# Verify yt-dlp is installed
yt-dlp --version
```

### Testing

```bash
# Run all tests
cargo test

# Run with verbose output
cargo test -- --nocapture

# Run specific test module
cargo test properties_utils

# Run property-based tests only
cargo test properties

# Run with test threads (parallel execution)
cargo test -- --test-threads=4

# Run tests with environment variable for proptest
PROPTEST_CASES=100 cargo test
```

### Linting and Formatting

```bash
# Run clippy linter
cargo clippy

# Run clippy with all warnings as errors
cargo clippy -- -D warnings

# Format code
cargo fmt

# Check formatting without modifying files
cargo fmt -- --check
```

### Running the CLI

```bash
# Basic usage (waterfall mode - all sources)
cargo run -- /path/to/tv_shows

# With options
cargo run -- /path/to/tv_shows --force --verbose

# Dry run (no downloads)
cargo run -- /path/to/tv_shows --dry-run

# Custom timeout
cargo run -- /path/to/tv_shows --timeout 60

# Show version
cargo run -- --version

# Show help
cargo run -- --help

# Run release build (optimized)
cargo run --release -- /path/to/tv_shows
```

## Testing Configuration

### Cargo.toml test profile

```toml
[dev-dependencies]
proptest = "1.0"

[profile.test]
opt-level = 0
```

### Proptest Settings

- Default cases: 100 (configurable via `PROPTEST_CASES` environment variable)
- Configurable via `proptest!` macro parameters
- Shrinking enabled by default for minimal failing examples

### Test Organization

- Unit tests: `#[cfg(test)]` modules within source files
- Property tests: `tests/properties_*.rs` files
- Integration tests: `tests/integration_*.rs` files
