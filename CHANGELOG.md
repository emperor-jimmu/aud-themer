# Changelog

## [Unreleased]

### Fixed

- AnimeThemes API 403 Forbidden errors by adding User-Agent header to all HTTP requests
- Themes.moe scraper not finding results due to incorrect selectors
  - Updated to use `table a[href*='.webm']` selector for theme links
  - Added check for "No anime found" message
  - Improved OP theme detection by checking both link text and href
  - Fixed async attribute access to avoid blocking calls
- TelevisionTunes and Themes.moe download clients now include User-Agent headers

### Changed

- Added `USER_AGENT` constant to `src/config.rs` with format "show-theme-cli/{version} (repo_url)"
- Updated all HTTP client builders to include `.user_agent(Config::USER_AGENT)`
- Improved Themes.moe scraper to handle website structure changes
- Enhanced error handling for missing anime in Themes.moe database

### Technical Details

- User-Agent header prevents API blocking and improves compatibility
- Themes.moe scraper now properly navigates search results and extracts .webm URLs from table structure
- All scrapers follow consistent HTTP client configuration pattern

## [1.1.0] - 2026-02-11

### Added

- Content mode selection via `--mode` / `-m` CLI option
  - `tv`: Uses TelevisionTunes and YouTube sources only
  - `anime`: Uses AnimeThemes, Themes.moe, and YouTube sources only
  - `both` (default): Uses all available sources
- `ContentMode` enum in `core/orchestrator.py` for mode management
- Mode-based scraper initialization in orchestrator
- `THEME_FOLDER_NAME` constant in config for subfolder organization

### Changed

- Theme files now saved in `theme-music` subfolder within each show folder
- Updated `_find_existing_theme()` to check theme-music subfolder
- Updated `process_show()` to create theme-music subfolder and save files there
- Updated CLI help text to document mode options and source priority
- Modified `Orchestrator.__init__()` to accept `mode` parameter
- Replaced `_initialize_default_scrapers()` with `_initialize_scrapers_by_mode()`
- Updated all documentation files:
  - README.md: Added mode examples, source breakdown by mode, and new folder structure
  - .gitignore: Changed to ignore `theme-music/` folders instead of individual files
  - .kiro/steering/product.md: Updated with mode feature description
  - .kiro/steering/structure.md: Updated orchestration pattern and file conventions
  - .kiro/steering/tech.md: Added mode usage examples

### Technical Details

- Mode selection determines which scrapers are instantiated at runtime
- Theme-music subfolder is created automatically if it doesn't exist
- Maintains backward compatibility (default mode is "both")
- Existing theme detection now checks within theme-music subfolder

## [1.0.0] - Initial Release

### Added

- Initial release with core functionality
- Support for multiple theme sources (TelevisionTunes, AnimeThemes, Themes.moe, YouTube)
- Waterfall approach for source fallback
- Rich console output with progress tracking
- Force mode to overwrite existing themes
- Dry-run mode for testing
- Verbose logging option
