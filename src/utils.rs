use std::path::Path;
use std::fs;
use std::sync::LazyLock;
use anyhow::Result;
use regex::Regex;

static YEAR_REGEX: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\s*\(\d{4}\)\s*$").expect("Failed to compile year regex")
});

/// Sanitize a filename by removing or replacing invalid characters
pub fn sanitize_filename(filename: &str) -> String {
    filename
        .chars()
        .map(|c| match c {
            '/' | '\\' | ':' | '*' | '?' | '"' | '<' | '>' | '|' => '_',
            c if c.is_control() => '_',
            c => c,
        })
        .collect::<String>()
        .trim()
        .to_string()
}

/// Validate that a file meets the minimum size requirement
pub fn validate_file_size(path: &Path, min_size: u64) -> bool {
    if let Ok(metadata) = fs::metadata(path) {
        metadata.len() >= min_size
    } else {
        false
    }
}

/// Get formatted file size string (e.g., "1.5 MB")
pub fn get_file_size_formatted(path: &Path) -> String {
    match fs::metadata(path) {
        Ok(metadata) => {
            let size = metadata.len();
            if size < 1024 {
                format!("{} B", size)
            } else if size < 1024 * 1024 {
                format!("{:.1} KB", size as f64 / 1024.0)
            } else if size < 1024 * 1024 * 1024 {
                format!("{:.1} MB", size as f64 / (1024.0 * 1024.0))
            } else {
                format!("{:.1} GB", size as f64 / (1024.0 * 1024.0 * 1024.0))
            }
        }
        Err(_) => "Unknown".to_string(),
    }
}

/// Sanitize input for subprocess calls by removing dangerous characters
pub fn sanitize_for_subprocess(value: &str, max_length: usize) -> Result<String> {
    // Check length
    if value.len() > max_length {
        anyhow::bail!("Input exceeds maximum length of {} characters", max_length);
    }

    // Remove shell metacharacters and control characters
    let sanitized = value
        .chars()
        .filter(|c| {
            !matches!(c, ';' | '|' | '&' | '`' | '<' | '>' | '$' | '\n' | '\r' | '\0')
                && !c.is_control()
        })
        .collect::<String>();

    // Check for path traversal
    if sanitized.contains("..") {
        anyhow::bail!("Input contains path traversal sequence");
    }

    Ok(sanitized)
}

/// Validate a show name for safety and length
pub fn validate_show_name(name: &str) -> bool {
    if name.is_empty() || name.len() > 200 {
        return false;
    }

    // Check for excessive special characters (more than 50% of the string)
    let special_char_count = name.chars().filter(|c| !c.is_alphanumeric() && !c.is_whitespace()).count();
    let ratio = special_char_count as f64 / name.len() as f64;
    
    if ratio > 0.5 {
        return false;
    }

    true
}

/// Validate an output path exists and is a directory
pub fn validate_output_path(path: &Path) -> Result<()> {
    if !path.exists() {
        anyhow::bail!("Path does not exist: {}", path.display());
    }

    if !path.is_dir() {
        anyhow::bail!("Path is not a directory: {}", path.display());
    }

    Ok(())
}

/// Strip year suffix from show name (e.g., "The Simpsons (1989)" -> "The Simpsons")
pub fn strip_year_from_show_name(name: &str) -> String {
    // Match pattern like " (YYYY)" at the end of the string
    YEAR_REGEX.replace(name, "").trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;
    use tempfile::TempDir;

    #[test]
    fn test_sanitize_filename() {
        assert_eq!(sanitize_filename("normal_file.mp3"), "normal_file.mp3");
        assert_eq!(sanitize_filename("file/with\\slashes.mp3"), "file_with_slashes.mp3");
        assert_eq!(sanitize_filename("file:with*special?.mp3"), "file_with_special_.mp3");
        assert_eq!(sanitize_filename("file<with>pipes|.mp3"), "file_with_pipes_.mp3");
    }

    #[test]
    fn test_validate_file_size() {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("test.txt");
        
        // Create a file with 1000 bytes
        let mut file = File::create(&file_path).unwrap();
        file.write_all(&vec![0u8; 1000]).unwrap();
        
        assert!(validate_file_size(&file_path, 500));
        assert!(validate_file_size(&file_path, 1000));
        assert!(!validate_file_size(&file_path, 1001));
    }

    #[test]
    fn test_get_file_size_formatted() {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("test.txt");
        
        let mut file = File::create(&file_path).unwrap();
        file.write_all(&vec![0u8; 1024 * 1024 + 512 * 1024]).unwrap(); // 1.5 MB
        
        let size_str = get_file_size_formatted(&file_path);
        assert!(size_str.contains("MB"));
    }

    #[test]
    fn test_sanitize_for_subprocess() {
        assert_eq!(sanitize_for_subprocess("normal text", 100).unwrap(), "normal text");
        assert_eq!(sanitize_for_subprocess("text;with|shell&chars", 100).unwrap(), "textwithshellchars");
        assert!(sanitize_for_subprocess("text with ..", 100).is_err());
        assert!(sanitize_for_subprocess(&"a".repeat(201), 200).is_err());
    }

    #[test]
    fn test_validate_show_name() {
        assert!(validate_show_name("The Simpsons"));
        assert!(validate_show_name("Breaking Bad (2008)"));
        assert!(!validate_show_name(""));
        assert!(!validate_show_name(&"a".repeat(201)));
        assert!(!validate_show_name("!!!###$$$%%%^^^&&&***"));
    }

    #[test]
    fn test_strip_year_from_show_name() {
        assert_eq!(strip_year_from_show_name("The Simpsons (1989)"), "The Simpsons");
        assert_eq!(strip_year_from_show_name("Breaking Bad (2008)"), "Breaking Bad");
        assert_eq!(strip_year_from_show_name("The Simpsons"), "The Simpsons");
        assert_eq!(strip_year_from_show_name("Show (2020) Extra"), "Show (2020) Extra");
        assert_eq!(strip_year_from_show_name("Show (1999)  "), "Show");
    }
}
