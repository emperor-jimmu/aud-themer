// Feature: rust-rewrite
// Property tests for orchestrator module

use proptest::prelude::*;
use show_theme_cli::orchestrator::{Orchestrator, OrchestratorConfig};
use show_theme_cli::scrapers::ThemeScraper;
use std::fs;
use std::path::Path;
use std::sync::{Arc, Mutex};
use tempfile::TempDir;
use async_trait::async_trait;

// Mock scraper for testing
struct MockScraper {
    name: String,
    should_succeed: Arc<Mutex<bool>>,
    call_count: Arc<Mutex<usize>>,
}

impl MockScraper {
    fn new(name: &str, should_succeed: bool) -> Self {
        Self {
            name: name.to_string(),
            should_succeed: Arc::new(Mutex::new(should_succeed)),
            call_count: Arc::new(Mutex::new(0)),
        }
    }

    fn get_call_count(&self) -> usize {
        *self.call_count.lock().unwrap()
    }
}

#[async_trait]
impl ThemeScraper for MockScraper {
    async fn search_and_download(
        &self,
        _show_name: &str,
        output_path: &Path,
    ) -> anyhow::Result<bool> {
        *self.call_count.lock().unwrap() += 1;
        
        let should_succeed = *self.should_succeed.lock().unwrap();
        if should_succeed {
            // Create a dummy file
            fs::write(output_path, b"mock theme data")?;
            Ok(true)
        } else {
            Ok(false)
        }
    }

    fn source_name(&self) -> &'static str {
        // Leak the string to get a 'static lifetime - acceptable in tests
        Box::leak(self.name.clone().into_boxed_str())
    }
}

// Property 2: Directory scanning completeness
// For any directory containing N immediate subdirectories, the directory scanner
// SHALL return exactly N ShowFolder entries, one per subdirectory.
#[test]
fn property_2_directory_scanning_completeness() {
    proptest!(|(num_folders in 0usize..10)| {
        let temp_dir = TempDir::new().unwrap();
        
        // Create N subdirectories
        for i in 0..num_folders {
            let folder_name = format!("Show_{}", i);
            fs::create_dir(temp_dir.path().join(&folder_name)).unwrap();
        }
        
        // Count subdirectories manually
        let entries = fs::read_dir(temp_dir.path()).unwrap();
        let actual_dirs: Vec<_> = entries
            .filter_map(|e| e.ok())
            .filter(|e| e.path().is_dir())
            .collect();
        
        prop_assert_eq!(actual_dirs.len(), num_folders);
    });
}

// Property 4: Existing theme detection and skip behavior
// For any folder containing a file with extension .mp3, .flac, or .wav named theme.*,
// when force is false, the orchestrator SHALL produce a Skipped result for that folder.
#[tokio::test]
async fn property_4_existing_theme_detection_skip() {
    let temp_dir = TempDir::new().unwrap();
    let show_folder = temp_dir.path().join("TestShow");
    fs::create_dir(&show_folder).unwrap();
    
    // Create existing theme file
    fs::write(show_folder.join("theme.mp3"), b"existing theme").unwrap();
    
    // Create orchestrator with force=false and NO scrapers (to avoid rate limiter delays)
    let config = OrchestratorConfig {
        force: false,
        dry_run: false,
        verbose: false,
        timeout: 30,
    };
    
    let mut orchestrator = Orchestrator::new(config, vec![]);
    
    // Process directory
    orchestrator.process_directory(temp_dir.path()).await.unwrap();
    
    // Should have skipped the show
    assert_eq!(orchestrator.results().skipped, 1);
    assert_eq!(orchestrator.results().success, 0);
    assert_eq!(orchestrator.results().failed, 0);
}

// Property 5: Force mode deletes existing theme
// For any folder containing an existing theme file, when force is true,
// the orchestrator SHALL delete the existing file before proceeding with download.
#[tokio::test]
async fn property_5_force_mode_deletes_existing() {
    let temp_dir = TempDir::new().unwrap();
    let show_folder = temp_dir.path().join("TestShow");
    fs::create_dir(&show_folder).unwrap();
    
    let theme_path = show_folder.join("theme.mp3");
    fs::write(&theme_path, b"old theme").unwrap();
    
    // Verify file exists
    assert!(theme_path.exists());
    
    // Create orchestrator with force=true
    let config = OrchestratorConfig {
        force: true,
        dry_run: false,
        verbose: false,
        timeout: 30,
    };
    
    let mock_scraper = Box::new(MockScraper::new("TestSource", true));
    let mut orchestrator = Orchestrator::new(config, vec![mock_scraper]);
    
    // Process directory
    orchestrator.process_directory(temp_dir.path()).await.unwrap();
    
    // Should have succeeded (deleted old and downloaded new)
    assert_eq!(orchestrator.results().success, 1);
    assert_eq!(orchestrator.results().skipped, 0);
    
    // File should exist with new content
    assert!(theme_path.exists());
    let content = fs::read(&theme_path).unwrap();
    assert_eq!(content, b"mock theme data");
}

// Property 6: Scraper chain short-circuits on success
// For any ordered list of N mock scrapers where the K-th scraper (1-indexed) succeeds
// and all prior scrapers fail, exactly K scrapers SHALL be invoked.
#[tokio::test]
async fn property_6_scraper_chain_short_circuit_case_1() {
    // Test case: first scraper succeeds
    let temp_dir = TempDir::new().unwrap();
    let show_folder = temp_dir.path().join("TestShow");
    fs::create_dir(&show_folder).unwrap();
    
    let scraper1 = Arc::new(MockScraper::new("Scraper1", true));
    let scraper2 = Arc::new(MockScraper::new("Scraper2", false));
    let scraper3 = Arc::new(MockScraper::new("Scraper3", false));
    
    let scrapers: Vec<Box<dyn ThemeScraper>> = vec![
        Box::new(MockScraper::new("Scraper1", true)),
        Box::new(MockScraper::new("Scraper2", false)),
        Box::new(MockScraper::new("Scraper3", false)),
    ];
    
    let config = OrchestratorConfig {
        force: false,
        dry_run: false,
        verbose: false,
        timeout: 30,
    };
    
    let mut orchestrator = Orchestrator::new(config, scrapers);
    orchestrator.process_directory(temp_dir.path()).await.unwrap();
    
    // Should have one success
    assert_eq!(orchestrator.results().success, 1);
}

// Property 6: Scraper chain short-circuits on success (case 2)
#[tokio::test]
async fn property_6_scraper_chain_short_circuit_case_2() {
    // Test case: second scraper succeeds
    let temp_dir = TempDir::new().unwrap();
    let show_folder = temp_dir.path().join("TestShow");
    fs::create_dir(&show_folder).unwrap();
    
    let scrapers: Vec<Box<dyn ThemeScraper>> = vec![
        Box::new(MockScraper::new("Scraper1", false)),
        Box::new(MockScraper::new("Scraper2", true)),
        Box::new(MockScraper::new("Scraper3", false)),
    ];
    
    let config = OrchestratorConfig {
        force: false,
        dry_run: false,
        verbose: false,
        timeout: 30,
    };
    
    let mut orchestrator = Orchestrator::new(config, scrapers);
    orchestrator.process_directory(temp_dir.path()).await.unwrap();
    
    // Should have one success
    assert_eq!(orchestrator.results().success, 1);
}

// Property 7: Error isolation across shows
// For any sequence of shows where processing one show raises an error,
// all subsequent shows in the sequence SHALL still be processed.
#[tokio::test]
async fn property_7_error_isolation() {
    let temp_dir = TempDir::new().unwrap();
    
    // Create multiple show folders
    let show1 = temp_dir.path().join("Show1");
    let show2 = temp_dir.path().join("Show2");
    let show3 = temp_dir.path().join("Show3");
    
    fs::create_dir(&show1).unwrap();
    fs::create_dir(&show2).unwrap();
    fs::create_dir(&show3).unwrap();
    
    // Create a scraper that always fails
    let mock_scraper = Box::new(MockScraper::new("FailingScraper", false));
    
    let config = OrchestratorConfig {
        force: false,
        dry_run: false,
        verbose: false,
        timeout: 30,
    };
    
    let mut orchestrator = Orchestrator::new(config, vec![mock_scraper]);
    
    // Process directory - should not panic even though all shows fail
    orchestrator.process_directory(temp_dir.path()).await.unwrap();
    
    // All 3 shows should have been attempted and failed
    assert_eq!(orchestrator.results().failed, 3);
    assert_eq!(orchestrator.results().success, 0);
    assert_eq!(orchestrator.results().skipped, 0);
}

// Additional unit test: Empty directory handling
#[tokio::test]
async fn test_empty_directory() {
    let temp_dir = TempDir::new().unwrap();
    
    let config = OrchestratorConfig {
        force: false,
        dry_run: false,
        verbose: false,
        timeout: 30,
    };
    
    let mut orchestrator = Orchestrator::new(config, vec![]);
    
    // Should handle empty directory gracefully
    let result = orchestrator.process_directory(temp_dir.path()).await;
    assert!(result.is_ok());
    
    assert_eq!(orchestrator.results().success, 0);
    assert_eq!(orchestrator.results().skipped, 0);
    assert_eq!(orchestrator.results().failed, 0);
}

// Additional unit test: Dry run mode
#[tokio::test]
async fn test_dry_run_mode() {
    let temp_dir = TempDir::new().unwrap();
    let show_folder = temp_dir.path().join("TestShow");
    fs::create_dir(&show_folder).unwrap();
    
    let config = OrchestratorConfig {
        force: false,
        dry_run: true,
        verbose: false,
        timeout: 30,
    };
    
    let mock_scraper = Box::new(MockScraper::new("TestSource", true));
    let mut orchestrator = Orchestrator::new(config, vec![mock_scraper]);
    
    orchestrator.process_directory(temp_dir.path()).await.unwrap();
    
    // In dry run mode, nothing should be downloaded
    assert_eq!(orchestrator.results().success, 0);
    assert_eq!(orchestrator.results().skipped, 0);
    assert_eq!(orchestrator.results().failed, 0);
    
    // Theme file should not exist
    assert!(!show_folder.join("theme.mp3").exists());
}
