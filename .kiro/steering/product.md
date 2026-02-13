# Product Overview

Show Theme CLI is a command-line tool that automates theme song retrieval for TV shows and anime series. It scans local directory structures, identifies shows by folder name, and downloads high-quality theme songs from multiple prioritized sources.

The tool uses a waterfall approach, attempting sources in priority order until a theme is successfully downloaded. Source selection is determined by the content mode:

- TV Mode: TelevisionTunes → YouTube
- Anime Mode: Themes.moe → AnimeThemes → YouTube
- Both Mode (default): TelevisionTunes → Themes.moe → AnimeThemes → YouTube
- YouTube Mode: YouTube only

It's designed to be idempotent, safe to re-run without re-downloading existing themes, and provides rich console feedback during operation.

Key features:
- Automatic theme song discovery and download from multiple sources
- Content mode selection (TV, Anime, Both, or YouTube) for optimized source usage
- Smart source prioritization with fallback handling
- Skip existing themes (with force override option)
- Rich console output with progress tracking
- Audio format conversion and validation
- Dry-run mode for testing
