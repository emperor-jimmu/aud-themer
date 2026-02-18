use std::sync::LazyLock;

/// Configuration constants for Show Theme CLI
pub struct Config;

impl Config {
    /// Minimum file size in bytes (500KB)
    pub const MIN_FILE_SIZE_BYTES: u64 = 500_000;

    /// Default network timeout in seconds
    pub const DEFAULT_TIMEOUT_SEC: u64 = 30;

    /// Download timeout in seconds
    pub const DOWNLOAD_TIMEOUT_SEC: u64 = 60;

    /// Audio bitrate for MP3 conversion
    pub const AUDIO_BITRATE: &str = "320k";

    /// Audio codec for `FFmpeg`
    pub const AUDIO_CODEC: &str = "libmp3lame";

    /// Maximum video duration in seconds (10 minutes)
    pub const MAX_VIDEO_DURATION_SEC: u64 = 600;

    /// Minimum rate limit delay in milliseconds
    pub const RATE_LIMIT_MIN_DELAY_MS: u64 = 1000;

    /// Maximum rate limit delay in milliseconds
    pub const RATE_LIMIT_MAX_DELAY_MS: u64 = 3000;

    /// Maximum retry attempts for failed operations
    pub const MAX_RETRY_ATTEMPTS: u32 = 3;

    /// Retry backoff factor for exponential backoff
    pub const RETRY_BACKOFF_FACTOR: f64 = 2.0;

    /// `FFmpeg` operation timeout in seconds
    pub const FFMPEG_TIMEOUT_SEC: u64 = 60;

    /// Valid theme file extensions
    pub const THEME_EXTENSIONS: &[&str] = &[".mp3", ".flac", ".wav"];
}

/// User-Agent header for HTTP requests (dynamically includes version from Cargo.toml)
pub static USER_AGENT: LazyLock<String> = LazyLock::new(|| {
    format!(
        "audio-theme-downloader/{} (https://github.com/audio-theme-downloader/audio-theme-downloader)",
        env!("CARGO_PKG_VERSION")
    )
});
