"""
AI-powered technical data extraction from BMW pages.

This script:
1. Loads discovered URLs from crawler output
2. Fetches page content using Crawl4AI
3. Extracts technical data using Claude API
4. Saves results as JSON (one file per vehicle + combined file)
"""
import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from anthropic import Anthropic
from crawl4ai import AsyncWebCrawler
from dotenv import load_dotenv

from technical_data_schema import get_extraction_prompt

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TechnicalDataExtractor:
    """Extract technical data from vehicle pages using AI."""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        """
        Initialize extractor.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.extracted_count = 0
        self.failed_urls = []

    async def fetch_page_content(self, url: str) -> Optional[str]:
        """
        Fetch page content using Crawl4AI.

        Args:
            url: URL to fetch

        Returns:
            HTML content or None if failed
        """
        try:
            async with AsyncWebCrawler(headless=True, verbose=False) as crawler:
                result = await crawler.arun(url=url, bypass_cache=True)

                if not result.success:
                    logger.error(f"Failed to fetch {url}: {result.error_message}")
                    return None

                # Return markdown content (easier for AI to parse)
                return result.markdown or result.html

        except Exception as e:
            logger.error(f"Exception fetching {url}: {e}")
            return None

    def extract_with_ai(self, url: str, content: str) -> Optional[Dict]:
        """
        Extract technical data using Claude API.

        Args:
            url: URL being processed
            content: Page content (HTML or markdown)

        Returns:
            Extracted data as dict or None if failed
        """
        try:
            # Generate extraction prompt
            prompt = get_extraction_prompt(url, content)

            # Call Claude API
            logger.info(f"Sending to Claude API for extraction: {url}")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,  # Deterministic extraction
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract JSON from response
            response_text = message.content[0].text

            # Try to extract JSON (might be wrapped in markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # No code block, assume entire response is JSON
                json_text = response_text

            # Parse JSON
            data = json.loads(json_text)

            # Add metadata
            data['_extraction_metadata'] = {
                'extracted_at': datetime.utcnow().isoformat(),
                'model': self.model,
                'url': url
            }

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Claude response for {url}: {e}")
            logger.error(f"Response was: {response_text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Exception during AI extraction for {url}: {e}")
            return None

    async def extract_from_url(self, url: str) -> Optional[Dict]:
        """
        Complete extraction pipeline for a single URL.

        Args:
            url: URL to process

        Returns:
            Extracted data or None if failed
        """
        logger.info(f"Processing: {url}")

        # Step 1: Fetch page content
        content = await self.fetch_page_content(url)
        if not content:
            self.failed_urls.append({"url": url, "reason": "Failed to fetch content"})
            return None

        logger.info(f"Fetched {len(content)} characters of content")

        # Step 2: Extract with AI
        data = self.extract_with_ai(url, content)
        if not data:
            self.failed_urls.append({"url": url, "reason": "Failed to extract data"})
            return None

        self.extracted_count += 1
        logger.info(f"✓ Successfully extracted data from {url}")

        return data

    async def extract_from_urls(
        self,
        urls: List[str],
        output_dir: str = "output/extracted_data",
        save_individual: bool = True
    ) -> List[Dict]:
        """
        Extract data from multiple URLs.

        Args:
            urls: List of URLs to process
            output_dir: Directory to save results
            save_individual: Whether to save individual JSON files per vehicle

        Returns:
            List of extracted data
        """
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        all_data = []

        for i, url in enumerate(urls, 1):
            logger.info(f"\n[{i}/{len(urls)}] Processing: {url}")

            # Extract data
            data = await self.extract_from_url(url)

            if data:
                all_data.append(data)

                # Save individual file
                if save_individual:
                    # Generate filename from URL
                    filename = self._url_to_filename(url)
                    filepath = output_path / f"{filename}.json"

                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)

                    logger.info(f"Saved to: {filepath}")

                # Save progress (combined file) after each successful extraction
                self._save_combined(all_data, output_path / "all_vehicles.json")

            # Progress update
            logger.info(f"Progress: {self.extracted_count}/{len(urls)} successful, {len(self.failed_urls)} failed")

        # Save final combined file
        self._save_combined(all_data, output_path / "all_vehicles.json")

        # Save failed URLs log
        if self.failed_urls:
            with open(output_path / "failed_urls.json", 'w', encoding='utf-8') as f:
                json.dump(self.failed_urls, f, indent=2)

        return all_data

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename."""
        # Extract the meaningful part from URL
        # e.g., "bmw-ix3-technische-daten.html" -> "bmw-ix3"
        parts = url.rstrip('/').split('/')
        last_part = parts[-1]

        # Remove .html and "technische-daten" suffix
        name = last_part.replace('.html', '').replace('-technische-daten', '')

        # Clean up
        name = re.sub(r'[^a-z0-9-]', '', name.lower())

        return name or 'vehicle'

    def _save_combined(self, data: List[Dict], filepath: Path):
        """Save combined data file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Updated combined file: {filepath}")


async def main():
    """Main extraction pipeline."""
    print("=" * 80)
    print("BMW TECHNICAL DATA EXTRACTION")
    print("=" * 80)
    print()

    # Load API key from .env.scripts (not .env to avoid Claude Code conflict)
    load_dotenv('.env.scripts')
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in .env.scripts file")
        print()
        print("Setup instructions:")
        print("1. Copy .env.example to .env.scripts:")
        print("   cp .env.example .env.scripts")
        print("2. Edit .env.scripts and add your actual API key")
        print("3. Run this script again")
        return

    print("✓ API key loaded from .env.scripts")
    print()

    # Load discovered URLs
    urls_file = "output/bmw_discovered_tech_urls.txt"

    if not os.path.exists(urls_file):
        print(f"ERROR: URLs file not found: {urls_file}")
        print()
        print("Run the crawler first:")
        print("  python3 test_smart_crawler.py")
        return

    with open(urls_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"✓ Loaded {len(urls)} URLs from {urls_file}")
    print()

    # Create extractor
    extractor = TechnicalDataExtractor(api_key=api_key)

    print("Starting extraction...")
    print("This will take several minutes (each URL requires API call)")
    print()

    # Extract data
    results = await extractor.extract_from_urls(
        urls=urls,
        output_dir="output/extracted_data",
        save_individual=True
    )

    # Summary
    print()
    print("=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Successfully extracted: {extractor.extracted_count}/{len(urls)} vehicles")
    print(f"Failed: {len(extractor.failed_urls)}/{len(urls)} vehicles")
    print()
    print("Output files:")
    print(f"  - Individual files: output/extracted_data/*.json")
    print(f"  - Combined file: output/extracted_data/all_vehicles.json")
    if extractor.failed_urls:
        print(f"  - Failed URLs log: output/extracted_data/failed_urls.json")
    print()

    if results:
        print("Sample extraction (first vehicle):")
        sample = results[0]
        if 'vehicle_identification' in sample:
            vid = sample['vehicle_identification']
            print(f"  Model: {vid.get('model', 'N/A')}")
            print(f"  Variant: {vid.get('variant', 'N/A')}")
        print()
        print("SUCCESS! Data extraction complete.")
    else:
        print("WARNING: No data was extracted successfully.")
        print("Check the logs above for errors.")


if __name__ == "__main__":
    asyncio.run(main())
