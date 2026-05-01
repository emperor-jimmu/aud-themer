# AGENTS.md

## Commands

```sh
cargo build                        # debug build (also fetches deps)
cargo build --release              # release build
cargo run --release -- <INPUT_DIR> [OPTIONS]
cargo check                        # typecheck only
cargo clippy -- -D warnings        # lint (all warnings are errors)
cargo fmt                          # format
cargo test                         # all tests
cargo test <name>                  # single test by name
cargo test --test properties_utils # single test file (module)
```

No Makefile, Taskfile, or justfile — plain `cargo` only.

## External Runtime Dependencies (must be on PATH)

- `ffmpeg` — required
- `yt-dlp` — required
- `chromium` / `google-chrome` — optional; auto-downloaded to `.chromium/` if absent

## Architecture

Single crate with one lib (`src/lib.rs`) and one binary (`src/main.rs`).

```
src/
  main.rs          # CLI (clap derive), scraper init, calls Orchestrator
  lib.rs           # re-exports modules; validate_input_path()
  config.rs        # global constants (timeouts, size limits, bitrate)
  orchestrator.rs  # iterates scrapers in waterfall order; mode-agnostic
  browser.rs       # shared chromiumoxide browser instance
  ffmpeg.rs        # FFmpeg subprocess: audio extraction → MP3 320kbps
  rate_limiter.rs  # 1–3 s random delay per source
  retry.rs         # exponential backoff, max 3 attempts, factor 2.0
  utils.rs         # strip_year_from_show_name, sanitize_for_subprocess, validate_file_size
  scrapers/
    mod.rs              # ThemeScraper trait (async_trait) + ScraperOutcome enum
    anime_themes.rs     # animethemes.moe REST API
    themes_moe.rs       # themes.moe browser automation
    tv_tunes.rs         # televisiontunes.com browser automation
    youtube.rs          # yt-dlp subprocess
```

## Key Quirks

- **Rust edition 2024** — requires Rust 1.85+. `let` chain syntax (`if !x && let Err(e) = ...`) is used in `orchestrator.rs`.
- **`Cargo.lock` is gitignored** — unusual for a binary crate; no reproducible lockfile.
- **All scrapers implement `ThemeScraper`**: `Ok(true)` = found, `Ok(false)` = not found (waterfall continues), `Err` = fatal.
- **Scraper waterfall order** is set in `main.rs::init_scrapers()` based on `--mode`; `Orchestrator` is mode-agnostic.
- **`SharedBrowser`** is a single chromiumoxide instance cloned across scrapers. Call `browser.close().await` explicitly after processing.
- **Show names have year stripped** before querying any scraper (`"Show (2008)"` → `"Show"`).
- **`sanitize_for_subprocess`** rejects shell metacharacters (`;|&\`<>$`), path traversal (`..`), and strings > 200 chars.
- **File validation**: minimum 500 KB, accepted extensions `.mp3`/`.flac`/`.wav`, YouTube results capped at 10 minutes.
- **Rate limiter is per-source-name** — each scraper has its own independent delay.

## Tests

- All active property tests are `tests/properties_*.rs` at the `tests/` root.
- `tests/integration/`, `tests/unit/`, `tests/properties/` subdirectories contain only Python `__pycache__` — remnants of a prior Python implementation, no Rust tests inside.
- Property tests use `proptest` 1.5.

## CI

CI (`.github/workflows/main.yml`) only runs on push to `main` and only **builds + publishes releases**. There is no CI step for `cargo test`, `cargo clippy`, or `cargo fmt` — run these locally before merging.
