# Changelog

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
