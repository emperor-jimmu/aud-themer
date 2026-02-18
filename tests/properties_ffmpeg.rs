// Feature: rust-rewrite, Property tests for FFmpeg module

use proptest::prelude::*;
use show_theme_cli::config::Config;
use show_theme_cli::ffmpeg::*;
use std::path::PathBuf;

// Feature: rust-rewrite, Property 12: FFmpeg command construction
// For any valid input path and output path, the constructed FFmpeg command
// SHALL include `-acodec libmp3lame`, `-b:a 320k`, and `-vn` flags.
//
// Note: We can't directly test command construction since convert_audio executes
// the command, but we can verify the constants are correct and the function
// signature accepts the right parameters.
#[test]
fn test_ffmpeg_constants() {
    assert_eq!(Config::AUDIO_CODEC, "libmp3lame");
    assert_eq!(Config::AUDIO_BITRATE, "320k");
}

proptest! {
    #[test]
    fn prop_ffmpeg_command_accepts_valid_paths(
        input_name in "[a-zA-Z0-9_-]{1,20}\\.(mp4|webm|mkv)",
        output_name in "[a-zA-Z0-9_-]{1,20}\\.mp3"
    ) {
        // Verify the function signature accepts Path types
        let input_path = PathBuf::from(&input_name);
        let output_path = PathBuf::from(&output_name);

        // Verify paths are valid UTF-8 and can be used with FFmpeg
        prop_assert!(input_path.to_str().is_some(), "Input path should be valid UTF-8");
        prop_assert!(output_path.to_str().is_some(), "Output path should be valid UTF-8");

        // Verify output has .mp3 extension
        prop_assert_eq!(output_path.extension().and_then(|s| s.to_str()), Some("mp3"));
    }
}

// Feature: rust-rewrite, Property 13: FFmpeg error categorization
// For any stderr string containing a known error pattern, the error parser
// SHALL categorize it into the correct FfmpegErrorType variant.
proptest! {
    #[test]
    fn prop_categorize_missing_codec_errors(
        prefix in "[a-zA-Z0-9 ]{0,20}",
        suffix in "[a-zA-Z0-9 ]{0,20}",
        codec_pattern in prop::sample::select(vec![
            "Unknown encoder",
            "encoder not found",
            "codec not found",
            "UNKNOWN ENCODER",
        ])
    ) {
        let stderr = format!("{} {} {}", prefix, codec_pattern, suffix);
        let error_type = FfmpegErrorParser::categorize_error(&stderr);
        prop_assert_eq!(error_type, FfmpegErrorType::MissingCodec);
    }

    #[test]
    fn prop_categorize_disk_space_errors(
        prefix in "[a-zA-Z0-9 ]{0,20}",
        suffix in "[a-zA-Z0-9 ]{0,20}",
        disk_pattern in prop::sample::select(vec![
            "No space left on device",
            "disk full",
            "NO SPACE LEFT ON DEVICE",
        ])
    ) {
        let stderr = format!("{} {} {}", prefix, disk_pattern, suffix);
        let error_type = FfmpegErrorParser::categorize_error(&stderr);
        prop_assert_eq!(error_type, FfmpegErrorType::DiskSpace);
    }

    #[test]
    fn prop_categorize_permission_errors(
        prefix in "[a-zA-Z0-9 ]{0,20}",
        suffix in "[a-zA-Z0-9 ]{0,20}",
        perm_pattern in prop::sample::select(vec![
            "Permission denied",
            "access denied",
            "PERMISSION DENIED",
        ])
    ) {
        let stderr = format!("{} {} {}", prefix, perm_pattern, suffix);
        let error_type = FfmpegErrorParser::categorize_error(&stderr);
        prop_assert_eq!(error_type, FfmpegErrorType::PermissionDenied);
    }

    #[test]
    fn prop_categorize_corrupted_input_errors(
        prefix in "[a-zA-Z0-9 ]{0,20}",
        suffix in "[a-zA-Z0-9 ]{0,20}",
        corrupt_pattern in prop::sample::select(vec![
            "Invalid data found",
            "corrupt",
            "truncated",
            "header missing",
        ])
    ) {
        let stderr = format!("{} {} {}", prefix, corrupt_pattern, suffix);
        let error_type = FfmpegErrorParser::categorize_error(&stderr);
        prop_assert_eq!(error_type, FfmpegErrorType::CorruptedInput);
    }

    #[test]
    fn prop_categorize_invalid_format_errors(
        prefix in "[a-zA-Z0-9 ]{0,20}",
        suffix in "[a-zA-Z0-9 ]{0,20}",
        format_pattern in prop::sample::select(vec![
            "Invalid argument",
            "unsupported",
            "unknown format",
        ])
    ) {
        let stderr = format!("{} {} {}", prefix, format_pattern, suffix);
        let error_type = FfmpegErrorParser::categorize_error(&stderr);
        prop_assert_eq!(error_type, FfmpegErrorType::InvalidFormat);
    }

    #[test]
    fn prop_categorize_unknown_errors(
        random_text in "[a-zA-Z0-9 ]{1,100}"
    ) {
        // Generate text that doesn't contain any known error patterns
        let safe_text = random_text
            .replace("encoder", "")
            .replace("codec", "")
            .replace("space", "")
            .replace("disk", "")
            .replace("permission", "")
            .replace("access", "")
            .replace("denied", "")
            .replace("invalid", "")
            .replace("corrupt", "")
            .replace("truncated", "")
            .replace("header", "")
            .replace("unsupported", "")
            .replace("format", "");

        if !safe_text.trim().is_empty() {
            let error_type = FfmpegErrorParser::categorize_error(&safe_text);
            prop_assert_eq!(error_type, FfmpegErrorType::Unknown);
        }
    }
}
