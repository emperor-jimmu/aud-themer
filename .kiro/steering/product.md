# Product Overview

Show Theme CLI is a command-line tool that automates theme song retrieval for TV shows and anime series. It scans local directory structures, identifies shows by folder name, and downloads high-quality theme songs from multiple prioritized sources.

The tool is implemented in Rust (2024 edition) for performance, type safety, and single-binary distribution. It uses a waterfall approach, attempting sources in priority order until a theme is successfully downloaded:

- Waterfall Mode (default): TelevisionTunes → AnimeThemes → Themes.moe → YouTube

It's designed to be idempotent, safe to re-run without re-downloading existing themes, and provides rich console feedback during operation.

Key features:

- Automatic theme song discovery and download from multiple sources
- Smart source prioritization with waterfall fallback handling
- Skip existing themes (with force override option)
- Rich console output with progress tracking
- Audio format conversion and validation using FFmpeg
- Browser cookie extraction for YouTube authentication (via yt-dlp, defaults to Chrome)
- Dry-run mode for testing
- Single-binary distribution (no runtime dependencies except FFmpeg, Chromium, and yt-dlp)
- Property-based testing for correctness guarantees
