use std::path::Path;
use std::process::Stdio;
use thiserror::Error;
use tokio::process::Command;
use tokio::time::{Duration, timeout};

use crate::config::Config;

/// FFmpeg error categories
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FfmpegErrorType {
    MissingCodec,
    CorruptedInput,
    DiskSpace,
    PermissionDenied,
    Timeout,
    InvalidFormat,
    Unknown,
}

/// FFmpeg error with categorization
#[derive(Error, Debug)]
#[error("FFmpeg {error_type:?}: {message}")]
pub struct FfmpegError {
    pub error_type: FfmpegErrorType,
    pub message: String,
    pub stderr: String,
}

/// Parser for FFmpeg error messages
pub struct FfmpegErrorParser;

impl FfmpegErrorParser {
    /// Categorize FFmpeg error from stderr output
    pub fn categorize_error(stderr: &str) -> FfmpegErrorType {
        let stderr_lower = stderr.to_lowercase();

        // Check for specific error patterns
        if stderr_lower.contains("unknown encoder")
            || stderr_lower.contains("encoder not found")
            || stderr_lower.contains("codec not found")
        {
            return FfmpegErrorType::MissingCodec;
        }

        if stderr_lower.contains("no space left on device") || stderr_lower.contains("disk full") {
            return FfmpegErrorType::DiskSpace;
        }

        if stderr_lower.contains("permission denied") || stderr_lower.contains("access denied") {
            return FfmpegErrorType::PermissionDenied;
        }

        if stderr_lower.contains("invalid data found")
            || stderr_lower.contains("corrupt")
            || stderr_lower.contains("truncated")
            || stderr_lower.contains("header missing")
        {
            return FfmpegErrorType::CorruptedInput;
        }

        if stderr_lower.contains("invalid argument")
            || stderr_lower.contains("unsupported")
            || stderr_lower.contains("unknown format")
        {
            return FfmpegErrorType::InvalidFormat;
        }

        FfmpegErrorType::Unknown
    }
}

/// Convert audio/video file to MP3 format using FFmpeg
pub async fn convert_audio(input: &Path, output: &Path, bitrate: &str) -> Result<(), FfmpegError> {
    tracing::info!(
        "[FFmpeg] Converting {} to {}",
        input.display(),
        output.display()
    );
    tracing::info!("[FFmpeg] Using bitrate: {}", bitrate);

    let timeout_duration = Duration::from_secs(Config::FFMPEG_TIMEOUT_SEC);

    let command_future = Command::new("ffmpeg")
        .arg("-i")
        .arg(input)
        .arg("-vn") // No video
        .arg("-acodec")
        .arg(Config::AUDIO_CODEC)
        .arg("-b:a")
        .arg(bitrate)
        .arg("-y") // Overwrite output file
        .arg(output)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output();

    let result = timeout(timeout_duration, command_future).await;

    match result {
        Ok(Ok(output_result)) => {
            if output_result.status.success() {
                tracing::info!("[FFmpeg] Conversion successful");
                Ok(())
            } else {
                let stderr = String::from_utf8_lossy(&output_result.stderr).to_string();
                let error_type = FfmpegErrorParser::categorize_error(&stderr);
                tracing::error!("[FFmpeg] Conversion failed: {:?}", error_type);
                tracing::error!("[FFmpeg] stderr: {}", stderr);
                Err(FfmpegError {
                    error_type,
                    message: format!(
                        "FFmpeg conversion failed with exit code: {:?}",
                        output_result.status.code()
                    ),
                    stderr,
                })
            }
        }
        Ok(Err(e)) => {
            tracing::error!("[FFmpeg] Failed to execute: {}", e);
            Err(FfmpegError {
                error_type: FfmpegErrorType::Unknown,
                message: format!("Failed to execute FFmpeg: {}", e),
                stderr: String::new(),
            })
        }
        Err(_) => {
            tracing::error!(
                "[FFmpeg] Operation timed out after {} seconds",
                Config::FFMPEG_TIMEOUT_SEC
            );
            Err(FfmpegError {
                error_type: FfmpegErrorType::Timeout,
                message: format!(
                    "FFmpeg operation timed out after {} seconds",
                    Config::FFMPEG_TIMEOUT_SEC
                ),
                stderr: String::new(),
            })
        }
    }
}

/// Get audio duration using ffprobe (async version to avoid blocking tokio runtime)
pub async fn get_audio_duration(path: &Path) -> Option<String> {
    let output = tokio::process::Command::new("ffprobe")
        .arg("-v")
        .arg("error")
        .arg("-show_entries")
        .arg("format=duration")
        .arg("-of")
        .arg("default=noprint_wrappers=1:nokey=1")
        .arg(path)
        .output()
        .await
        .ok()?;

    if output.status.success() {
        let duration_str = String::from_utf8_lossy(&output.stdout);
        let duration_secs: f64 = duration_str.trim().parse().ok()?;

        let minutes = (duration_secs / 60.0).floor() as u32;
        let seconds = (duration_secs % 60.0).round() as u32;

        Some(format!("{}:{:02}", minutes, seconds))
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_categorize_missing_codec() {
        let stderr = "Unknown encoder 'libmp3lame'";
        assert_eq!(
            FfmpegErrorParser::categorize_error(stderr),
            FfmpegErrorType::MissingCodec
        );
    }

    #[test]
    fn test_categorize_disk_space() {
        let stderr = "Error writing output: No space left on device";
        assert_eq!(
            FfmpegErrorParser::categorize_error(stderr),
            FfmpegErrorType::DiskSpace
        );
    }

    #[test]
    fn test_categorize_permission_denied() {
        let stderr = "output.mp3: Permission denied";
        assert_eq!(
            FfmpegErrorParser::categorize_error(stderr),
            FfmpegErrorType::PermissionDenied
        );
    }

    #[test]
    fn test_categorize_corrupted_input() {
        let stderr = "Invalid data found when processing input";
        assert_eq!(
            FfmpegErrorParser::categorize_error(stderr),
            FfmpegErrorType::CorruptedInput
        );
    }

    #[test]
    fn test_categorize_invalid_format() {
        let stderr = "Unknown format detected";
        assert_eq!(
            FfmpegErrorParser::categorize_error(stderr),
            FfmpegErrorType::InvalidFormat
        );
    }

    #[test]
    fn test_categorize_unknown() {
        let stderr = "Some random error message";
        assert_eq!(
            FfmpegErrorParser::categorize_error(stderr),
            FfmpegErrorType::Unknown
        );
    }
}
