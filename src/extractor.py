"""
Multi-Manufacturer Technical Data Extractor

Extracts comprehensive technical specifications using AI (Claude API).
Features:
- Throttling (10s delays between extractions)
- Improved JSON parsing (handles Claude's extra text)
- Progress tracking and saving
- Multi-manufacturer support
- Retry logic with exponential backoff
"""
import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from anthropic import Anthropic
from crawl4ai import AsyncWebCrawler
from dotenv import load_dotenv

# Import schema from root (technical_data_schema.py)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from technical_data_schema import get_extraction_prompt

logging.basicConfig(
  level=logging.INFO,
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VehicleExtractor:
  """Extract technical data from a single vehicle URL."""

  def __init__(
    self,
    api_key: str,
    model: str = "claude-3-haiku-20240307",
    max_retries: int = 3
  ):
    """
    Initialize extractor.

    Args:
      api_key: Anthropic API key
      model: Claude model to use
      max_retries: Number of retry attempts for failed extractions
    """
    self.client = Anthropic(api_key=api_key)
    self.model = model
    self.max_retries = max_retries
    self.tokens_used = 0
    self.skipped_count = 0  # Pages with valid_source='no'

  async def extract(self, url: str) -> Optional[Dict]:
    """
    Extract technical data from a vehicle page.

    Args:
      url: Vehicle technical data page URL

    Returns:
      Extracted data dict or None if failed
    """
    for attempt in range(self.max_retries):
      try:
        # Fetch page content
        content = await self._fetch_page(url)
        if not content:
          logger.warning(f"Failed to fetch page: {url}")
          continue

        # Extract with AI
        data = await self._extract_with_ai(url, content)
        if data:
          return data

      except Exception as e:
        logger.error(f"Extraction attempt {attempt + 1} failed for {url}: {e}")

        # Exponential backoff
        if attempt < self.max_retries - 1:
          wait_time = 2 ** attempt
          logger.info(f"Retrying in {wait_time}s...")
          await asyncio.sleep(wait_time)

    logger.error(f"All {self.max_retries} attempts failed for {url}")
    return None

  async def _fetch_page(self, url: str) -> Optional[str]:
    """Fetch page content using Crawl4AI."""
    try:
      async with AsyncWebCrawler(headless=True, verbose=False) as crawler:
        result = await crawler.arun(url=url, bypass_cache=True)

        if not result.success:
          logger.error(f"Crawl failed: {url}")
          return None

        # Use markdown for better AI parsing
        content = result.markdown or result.html
        logger.info(f"Fetched {len(content)} characters from {url}")
        return content

    except Exception as e:
      logger.error(f"Exception fetching {url}: {e}")
      return None

  async def _extract_with_ai(self, url: str, content: str) -> Optional[Dict]:
    """Extract data using Claude API with improved JSON parsing."""
    try:
      # Generate prompt
      prompt = get_extraction_prompt(url, content)

      # Call Claude API
      message = self.client.messages.create(
        model=self.model,
        max_tokens=4096,
        temperature=0,  # Deterministic
        messages=[{
          "role": "user",
          "content": prompt
        }]
      )

      # Track token usage
      self.tokens_used += message.usage.input_tokens + message.usage.output_tokens

      # Extract JSON from response (improved parser)
      response_text = message.content[0].text
      data = self._parse_json_response(response_text)

      if not data:
        logger.error(f"Failed to parse JSON from response for {url}")
        return None

      # Check if page is a valid technical data source
      valid_source = data.get('valid_source', 'maybe').lower()

      if valid_source == 'no':
        self.skipped_count += 1
        logger.info(f"⊘ Skipping {url}: Not a technical data page (valid_source=no)")
        return None

      if valid_source == 'maybe':
        logger.warning(f"⚠ Extracting {url}: Incomplete technical data (valid_source=maybe)")
      elif valid_source == 'yes':
        logger.info(f"✓ Valid technical data page (valid_source=yes)")

      # Add metadata
      data['_extraction_metadata'] = {
        'extracted_at': datetime.utcnow().isoformat(),
        'model': self.model,
        'url': url,
        'tokens_used': message.usage.input_tokens + message.usage.output_tokens,
        'valid_source': valid_source
      }

      return data

    except Exception as e:
      logger.error(f"AI extraction failed for {url}: {e}")
      return None

  def _parse_json_response(self, response_text: str) -> Optional[Dict]:
    """
    Parse JSON from Claude's response.

    Handles cases where Claude returns JSON wrapped in markdown
    or followed by extra text.

    Args:
      response_text: Raw response from Claude

    Returns:
      Parsed JSON dict or None
    """
    # Try 1: Check for JSON in markdown code block
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
      try:
        return json.loads(json_match.group(1))
      except json.JSONDecodeError:
        pass

    # Try 2: Extract first complete JSON object by brace counting
    start_idx = response_text.find('{')
    if start_idx == -1:
      logger.error("No opening brace found in response")
      return None

    brace_count = 0
    for idx in range(start_idx, len(response_text)):
      if response_text[idx] == '{':
        brace_count += 1
      elif response_text[idx] == '}':
        brace_count -= 1
        if brace_count == 0:
          # Found complete JSON object
          json_text = response_text[start_idx:idx+1]
          try:
            return json.loads(json_text)
          except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return None

    logger.error("No complete JSON object found in response")
    return None


class MultiManufacturerExtractor:
  """Extract technical data for multiple manufacturers with throttling."""

  def __init__(self, config_path: str = "config/manufacturers.yaml"):
    """
    Initialize multi-manufacturer extractor.

    Args:
      config_path: Path to manufacturers configuration file
    """
    import yaml
    self.config_path = config_path

    # Load configuration
    with open(config_path, 'r') as f:
      self.config = yaml.safe_load(f)

    # Load API key from .env.scripts
    load_dotenv('.env.scripts')
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
      raise ValueError("ANTHROPIC_API_KEY not found in .env.scripts")

    # Extraction settings
    self.extraction_settings = self.config['extraction_settings']
    self.delay_between_urls = self.extraction_settings['delay_between_urls_seconds']
    self.delay_between_manufacturers = self.extraction_settings['delay_between_manufacturers_seconds']
    self.batch_size = self.extraction_settings['batch_size']

    # Create extractor
    self.extractor = VehicleExtractor(
      api_key=api_key,
      model=self.extraction_settings['claude_model'],
      max_retries=self.extraction_settings['max_retries']
    )

    # Stats tracking
    self.total_extracted = 0
    self.total_failed = 0
    self.start_time = None

  async def extract_manufacturer(
    self,
    manufacturer_slug: str,
    urls: List[str],
    output_dir: Path
  ) -> Dict:
    """
    Extract all URLs for a single manufacturer with throttling.

    Args:
      manufacturer_slug: Manufacturer identifier (e.g., 'bmw')
      urls: List of URLs to extract
      output_dir: Directory to save results

    Returns:
      Summary dict with results
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Extracting {manufacturer_slug.upper()}")
    logger.info(f"URLs to process: {len(urls)}")
    logger.info(f"Estimated time: {len(urls) * self.delay_between_urls / 60:.1f} minutes")
    logger.info(f"{'='*80}\n")

    # Create manufacturer output directory
    manufacturer_dir = output_dir / manufacturer_slug
    manufacturer_dir.mkdir(parents=True, exist_ok=True)

    results = []
    failed_urls = []
    skipped_urls = []

    # Track skipped count before extraction
    skipped_before = self.extractor.skipped_count

    for i, url in enumerate(urls, 1):
      # Progress
      elapsed = time.time() - self.start_time if self.start_time else 0
      logger.info(
        f"[{i}/{len(urls)}] {manufacturer_slug} | "
        f"Elapsed: {elapsed/60:.1f}min | "
        f"Tokens: {self.extractor.tokens_used:,}"
      )
      logger.info(f"  URL: {url}")

      # Extract
      extraction_start = time.time()
      skipped_count_before_this_url = self.extractor.skipped_count
      data = await self.extractor.extract(url)
      extraction_time = time.time() - extraction_start

      if data:
        results.append(data)
        self.total_extracted += 1

        # Save individual file
        filename = self._generate_filename(url, data)
        filepath = manufacturer_dir / f"{filename}.json"

        with open(filepath, 'w', encoding='utf-8') as f:
          json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"  ✓ Success ({extraction_time:.1f}s) | Saved: {filepath.name}")

      else:
        # Check if this was a skip or an actual failure
        if self.extractor.skipped_count > skipped_count_before_this_url:
          # This was a skip (valid_source='no')
          skipped_urls.append(url)
        else:
          # This was an actual failure
          self.total_failed += 1
          failed_urls.append(url)
          logger.error(f"  ✗ Failed after {extraction_time:.1f}s")

      # Save progress every N vehicles
      if i % self.batch_size == 0:
        self._save_progress(manufacturer_slug, results, manufacturer_dir)
        logger.info(f"\n  💾 Progress saved ({len(results)} models)\n")

      # Throttle (except on last URL)
      if i < len(urls):
        logger.info(f"  ⏸  Waiting {self.delay_between_urls}s...\n")
        await asyncio.sleep(self.delay_between_urls)

    # Final save
    self._save_combined(manufacturer_slug, results, manufacturer_dir)

    # Summary
    summary = {
      'manufacturer': manufacturer_slug,
      'total_urls': len(urls),
      'successful': len(results),
      'skipped': len(skipped_urls),
      'failed': len(failed_urls),
      'skipped_urls': skipped_urls,
      'failed_urls': failed_urls,
      'tokens_used': self.extractor.tokens_used
    }

    logger.info(f"\n✓ {manufacturer_slug}: {len(results)}/{len(urls)} extracted")
    if skipped_urls:
      logger.info(f"  ⊘ Skipped: {len(skipped_urls)} non-technical pages")
    if failed_urls:
      logger.warning(f"  ✗ Failed: {len(failed_urls)} URLs")

    return summary

  async def extract_all(self, discovered_urls: Dict[str, List[str]], run_date: str) -> Dict:
    """
    Extract technical data for all manufacturers.

    Args:
      discovered_urls: Dict mapping manufacturer slug to list of URLs
      run_date: Date string for run folder (e.g., '2024-11-22')

    Returns:
      Summary dict with all results
    """
    self.start_time = time.time()

    # Create output directory
    output_dir = Path(f"data/runs/{run_date}/extracted")
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"\n{'#'*80}")
    logger.info(f"# Multi-Manufacturer Extraction")
    logger.info(f"# Manufacturers: {len(discovered_urls)}")
    logger.info(f"# Total URLs: {sum(len(urls) for urls in discovered_urls.values())}")
    logger.info(f"{'#'*80}\n")

    summaries = {}

    for idx, (manufacturer_slug, urls) in enumerate(discovered_urls.items(), 1):
      logger.info(f"\n[{idx}/{len(discovered_urls)}] Processing {manufacturer_slug}")

      # Extract this manufacturer
      summary = await self.extract_manufacturer(
        manufacturer_slug=manufacturer_slug,
        urls=urls,
        output_dir=output_dir
      )
      summaries[manufacturer_slug] = summary

      # Delay between manufacturers (except last one)
      if idx < len(discovered_urls):
        logger.info(f"\n{'─'*80}")
        logger.info(f"Waiting {self.delay_between_manufacturers}s before next manufacturer...")
        logger.info(f"{'─'*80}\n")
        await asyncio.sleep(self.delay_between_manufacturers)

    # Final summary
    total_time = time.time() - self.start_time
    total_urls = sum(s['total_urls'] for s in summaries.values())

    logger.info(f"\n{'='*80}")
    logger.info(f"EXTRACTION COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Total manufacturers: {len(summaries)}")
    logger.info(f"Total URLs processed: {total_urls}")
    logger.info(f"Successfully extracted: {self.total_extracted}")
    logger.info(f"Skipped (non-technical pages): {self.extractor.skipped_count}")
    logger.info(f"Failed: {self.total_failed}")
    logger.info(f"Total tokens used: {self.extractor.tokens_used:,}")
    logger.info(f"Estimated cost: ${self.extractor.tokens_used * 0.000001:.2f}")
    logger.info(f"Total time: {total_time / 60:.1f} minutes")
    logger.info(f"{'='*80}\n")

    return {
      'run_date': run_date,
      'manufacturers': summaries,
      'totals': {
        'urls': total_urls,
        'extracted': self.total_extracted,
        'skipped': self.extractor.skipped_count,
        'failed': self.total_failed,
        'tokens': self.extractor.tokens_used,
        'cost_usd': self.extractor.tokens_used * 0.000001,
        'duration_minutes': total_time / 60
      }
    }

  def _generate_filename(self, url: str, data: Dict) -> str:
    """Generate filename from vehicle data."""
    try:
      # Try to get from vehicle identification
      vid = data.get('vehicle_identification', {})
      brand = vid.get('brand', '').lower()
      model = vid.get('model', '').lower()
      variant = vid.get('variant', '').lower()
      year = vid.get('model_year', '')

      if brand and model:
        parts = [brand, model]
        if variant:
          parts.append(variant)
        if year:
          parts.append(year)

        # Clean and join
        filename = '_'.join(parts)
        filename = re.sub(r'[^a-z0-9_]', '', filename)
        return filename

    except Exception:
      pass

    # Fallback: use URL
    filename = url.split('/')[-1].replace('.html', '').replace('-technische-daten', '')
    filename = re.sub(r'[^a-z0-9-]', '', filename.lower())
    return filename or 'vehicle'

  def _save_progress(self, manufacturer_slug: str, results: List[Dict], output_dir: Path):
    """Save intermediate progress."""
    progress_file = output_dir / f"{manufacturer_slug}_progress.json"
    with open(progress_file, 'w', encoding='utf-8') as f:
      json.dump(results, f, indent=2, ensure_ascii=False)

  def _save_combined(self, manufacturer_slug: str, results: List[Dict], output_dir: Path):
    """Save combined results file."""
    combined_file = output_dir / f"{manufacturer_slug}_all.json"
    with open(combined_file, 'w', encoding='utf-8') as f:
      json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"✓ Saved combined file: {combined_file}")
