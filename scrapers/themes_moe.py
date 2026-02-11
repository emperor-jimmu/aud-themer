"""Themes.moe scraper implementation."""

import subprocess
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from scrapers.base import ThemeScraper
from core.utils import validate_file_size


class ThemesMoeScraper(ThemeScraper):
    """Scraper for Themes.moe using Playwright web automation."""
    
    BASE_URL = "https://themes.moe/"
    TIMEOUT = 30000  # 30 seconds in milliseconds
    
    def search_and_download(self, show_name: str, output_path: Path) -> bool:
        """
        Search for and download a theme song from Themes.moe.
        
        Args:
            show_name: Name of the anime
            output_path: Full path where theme file should be saved
            
        Returns:
            True if download succeeded, False otherwise
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                # Navigate to homepage
                page.goto(self.BASE_URL, timeout=self.TIMEOUT)
                
                # Check if search functionality exists
                search_input = page.locator("input[type='search'], input[placeholder*='search' i]")
                if search_input.count() == 0:
                    return False
                
                # Perform search
                search_input.first.fill(show_name)
                search_input.first.press("Enter")
                page.wait_for_load_state("networkidle", timeout=self.TIMEOUT)
                
                # Find audio/video element
                media = page.locator("audio source, video source").first
                if media.count() == 0:
                    return False
                
                media_url = media.get_attribute("src")
                if not media_url:
                    return False
                
                # Download media
                response = page.request.get(media_url)
                if response.status != 200:
                    return False
                
                # Save file
                with open(output_path, "wb") as f:
                    f.write(response.body())
                
                # If video, extract audio
                if media_url.endswith(('.mp4', '.webm')):
                    temp_path = output_path.with_suffix('.temp')
                    output_path.rename(temp_path)
                    
                    result = subprocess.run(
                        [
                            "ffmpeg",
                            "-i", str(temp_path),
                            "-vn",
                            "-acodec", "libmp3lame",
                            "-b:a", "320k",
                            "-y",
                            str(output_path)
                        ],
                        capture_output=True,
                        timeout=60
                    )
                    
                    temp_path.unlink()
                    
                    if result.returncode != 0:
                        return False
                
                # Validate file size
                if not validate_file_size(output_path):
                    output_path.unlink()
                    return False
                
                return True
                
            except PlaywrightTimeoutError:
                return False
            except Exception:
                return False
            finally:
                browser.close()
                # Rate limiting delay
                time.sleep(random.uniform(1, 3))
    
    def get_source_name(self) -> str:
        """
        Return human-readable name of this source.
        
        Returns:
            String identifier for this scraper source
        """
        return "Themes.moe"
