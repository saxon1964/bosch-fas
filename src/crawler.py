"""
Multi-Manufacturer Vehicle Crawler

Discovers technical data pages across multiple manufacturers without using AI.
Uses pattern matching to identify relevant URLs (cost-free discovery phase).
"""
import asyncio
import logging
import yaml
from pathlib import Path
from typing import List, Set, Dict, Optional
from urllib.parse import urljoin, urlparse
from fnmatch import fnmatch
from datetime import datetime
from crawl4ai import AsyncWebCrawler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ManufacturerCrawler:
    """Crawls a single manufacturer's website for technical data pages."""

    def __init__(
        self,
        manufacturer_config: Dict,
        headless: bool = True,
        verbose: bool = False
    ):
        """
        Initialize crawler for one manufacturer.

        Args:
            manufacturer_config: Manufacturer configuration from YAML
            headless: Run browser in headless mode
            verbose: Enable verbose logging
        """
        self.config = manufacturer_config
        self.name = manufacturer_config['name']
        self.slug = manufacturer_config['slug']
        self.headless = headless
        self.verbose = verbose

        # Crawl settings
        crawl_settings = manufacturer_config['crawl_settings']
        self.start_urls = crawl_settings['start_urls']
        self.max_depth = crawl_settings['max_depth']
        self.patterns = crawl_settings['patterns']
        self.anti_patterns = crawl_settings['anti_patterns']
        self.rate_limit = crawl_settings.get('rate_limit_seconds', 1)

        # Extract domain from root URL
        parsed = urlparse(manufacturer_config['root_url'])
        self.domain = parsed.netloc

        # State tracking
        self.visited: Set[str] = set()
        self.discovered_urls: List[str] = []
        self.to_crawl: List[tuple[str, int]] = []  # (url, depth)

        logger.info(f"Initialized crawler for {self.name} (max_depth={self.max_depth})")

    async def crawl(self) -> List[str]:
        """
        Discover all technical data pages for this manufacturer.

        Returns:
            List of discovered URLs
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Crawling {self.name}")
        logger.info(f"{'='*80}")
        logger.info(f"Start URLs: {', '.join(self.start_urls)}")
        logger.info(f"Patterns: {', '.join(self.patterns)}")
        logger.info(f"Max depth: {self.max_depth}")

        # Reset state
        self.visited.clear()
        self.discovered_urls.clear()
        self.to_crawl.clear()

        # Add start URLs to queue
        for start_url in self.start_urls:
            self.to_crawl.append((start_url, 0))

        async with AsyncWebCrawler(headless=self.headless, verbose=self.verbose) as crawler:
            while self.to_crawl:
                url, depth = self.to_crawl.pop(0)

                # Skip if already visited
                if url in self.visited:
                    continue

                await self._crawl_page(crawler, url, depth)

                # Rate limiting
                if self.to_crawl:  # Don't sleep after last URL
                    await asyncio.sleep(self.rate_limit)

                # Progress update
                if len(self.visited) % 10 == 0:
                    logger.info(
                        f"  Progress: Visited={len(self.visited)}, "
                        f"Queue={len(self.to_crawl)}, "
                        f"Found={len(self.discovered_urls)}"
                    )

        logger.info(f"\n✓ {self.name}: Found {len(self.discovered_urls)} technical data pages")
        return self.discovered_urls

    async def _crawl_page(self, crawler: AsyncWebCrawler, url: str, depth: int):
        """Crawl a single page and extract links."""
        # Mark as visited
        self.visited.add(url)

        # Check if this URL matches our patterns
        if self._matches_patterns(url):
            logger.info(f"  ✓ Found: {url}")
            if url not in self.discovered_urls:
                self.discovered_urls.append(url)

        # Stop if reached max depth
        if depth >= self.max_depth:
            return

        try:
            # Fetch the page
            result = await crawler.arun(url=url, bypass_cache=True)

            if not result.success:
                logger.warning(f"  ✗ Failed to crawl {url}")
                return

            # Extract links
            links = self._extract_links(result, url)

            # Add valid links to queue
            for link_url in links:
                if self._should_follow_link(link_url):
                    if link_url not in self.visited:
                        # Check if already in queue
                        if not any(link_url == queued_url for queued_url, _ in self.to_crawl):
                            self.to_crawl.append((link_url, depth + 1))

        except Exception as e:
            logger.error(f"  ✗ Error crawling {url}: {e}")

    def _extract_links(self, result, base_url: str) -> List[str]:
        """Extract and normalize links from crawl result."""
        links = []

        if not hasattr(result, 'links') or not result.links:
            return links

        # Handle different link formats from crawl4ai
        raw_links = []
        if isinstance(result.links, dict):
            # Extract all links from dict (internal, external, etc.)
            for key in result.links:
                if isinstance(result.links[key], list):
                    raw_links.extend(result.links[key])
        elif isinstance(result.links, list):
            raw_links = result.links

        # Normalize and filter links
        for link_obj in raw_links:
            # Handle both dict and string formats
            if isinstance(link_obj, str):
                link_url = link_obj
            elif isinstance(link_obj, dict):
                link_url = link_obj.get('href', '')
            else:
                continue

            if not link_url:
                continue

            # Normalize URL (handle relative links)
            link_url = urljoin(base_url, link_url)

            # Remove fragments
            if '#' in link_url:
                link_url = link_url.split('#')[0]

            links.append(link_url)

        return links

    def _matches_patterns(self, url: str) -> bool:
        """Check if URL matches any of the inclusion patterns."""
        for pattern in self.patterns:
            if fnmatch(url, pattern):
                return True
        return False

    def _matches_anti_patterns(self, url: str) -> bool:
        """Check if URL matches any of the exclusion patterns."""
        for pattern in self.anti_patterns:
            if fnmatch(url, pattern):
                return True
        return False

    def _should_follow_link(self, url: str) -> bool:
        """Determine if a link should be followed."""
        parsed = urlparse(url)

        # Must be same domain
        if self.domain not in parsed.netloc:
            return False

        # Check anti-patterns
        if self._matches_anti_patterns(url):
            return False

        # Skip common non-content patterns
        skip_patterns = [
            'javascript:',
            'mailto:',
            'tel:',
            '.pdf',
            '.jpg',
            '.jpeg',
            '.png',
            '.gif',
            '.svg',
            '.zip',
            '.exe'
        ]

        url_lower = url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False

        return True


class MultiManufacturerCrawler:
    """Crawls multiple manufacturers based on configuration file."""

    def __init__(self, config_path: str = "config/manufacturers.yaml"):
        """
        Initialize multi-manufacturer crawler.

        Args:
            config_path: Path to manufacturers.yaml configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.manufacturers = self.config['manufacturers']

        logger.info(f"Loaded configuration for {len(self.manufacturers)} manufacturers")

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        config_file = Path(self.config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        return config

    async def crawl_all(self) -> Dict[str, List[str]]:
        """
        Crawl all configured manufacturers.

        Returns:
            Dictionary mapping manufacturer slug to list of discovered URLs
        """
        results = {}

        logger.info(f"\n{'#'*80}")
        logger.info(f"# Starting multi-manufacturer crawl")
        logger.info(f"# Manufacturers: {len(self.manufacturers)}")
        logger.info(f"{'#'*80}\n")

        for idx, manufacturer_config in enumerate(self.manufacturers, 1):
            slug = manufacturer_config['slug']
            name = manufacturer_config['name']

            logger.info(f"\n[{idx}/{len(self.manufacturers)}] {name}")

            # Create crawler for this manufacturer
            crawler = ManufacturerCrawler(
                manufacturer_config=manufacturer_config,
                headless=True,
                verbose=False
            )

            # Crawl
            urls = await crawler.crawl()
            results[slug] = urls

            # Delay between manufacturers (if not last one)
            if idx < len(self.manufacturers):
                delay = self.config['extraction_settings']['delay_between_manufacturers_seconds']
                logger.info(f"\n⏸  Waiting {delay}s before next manufacturer...")
                await asyncio.sleep(delay)

        # Summary
        total_urls = sum(len(urls) for urls in results.values())
        logger.info(f"\n{'='*80}")
        logger.info(f"CRAWL COMPLETE")
        logger.info(f"{'='*80}")
        for slug, urls in results.items():
            logger.info(f"  {slug}: {len(urls)} URLs")
        logger.info(f"  TOTAL: {total_urls} URLs")
        logger.info(f"{'='*80}\n")

        return results

    def save_results(self, results: Dict[str, List[str]], run_date: str = None):
        """
        Save discovered URLs to files.

        Args:
            results: Dictionary mapping manufacturer slug to URLs
            run_date: Date string for run folder (default: today)
        """
        if not run_date:
            run_date = datetime.now().strftime("%Y-%m-%d")

        # Create run directory
        run_dir = Path(f"data/runs/{run_date}/discovered")
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save per manufacturer
        for slug, urls in results.items():
            output_file = run_dir / f"{slug}_urls.txt"

            with open(output_file, 'w') as f:
                for url in urls:
                    f.write(url + '\n')

            logger.info(f"✓ Saved {len(urls)} URLs to {output_file}")

        # Save summary
        summary_file = run_dir / "summary.json"
        import json
        summary = {
            "date": run_date,
            "manufacturers": {
                slug: {
                    "count": len(urls),
                    "urls": urls
                }
                for slug, urls in results.items()
            },
            "total_urls": sum(len(urls) for urls in results.values())
        }

        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"✓ Saved summary to {summary_file}")


async def main():
    """Example usage of the multi-manufacturer crawler."""
    # Create crawler
    crawler = MultiManufacturerCrawler(config_path="config/manufacturers.yaml")

    # Crawl all manufacturers
    results = await crawler.crawl_all()

    # Save results
    crawler.save_results(results)

    print(f"\n✓ Crawl complete! Found URLs for:")
    for slug, urls in results.items():
        print(f"  - {slug}: {len(urls)} URLs")


if __name__ == "__main__":
    asyncio.run(main())
