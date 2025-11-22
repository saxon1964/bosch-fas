"""
Smart crawler that discovers technical data pages without using AI.

This implements a two-phase approach:
1. Discovery phase: Crawl site to find all pages matching a pattern (NO AI)
2. Extraction phase: Use AI only on discovered pages to extract data
"""
import asyncio
import logging
import re
from typing import List, Set, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from crawl4ai import AsyncWebCrawler

logger = logging.getLogger(__name__)


class SmartVehicleCrawler:
    """
    Intelligent crawler that discovers technical data pages systematically.

    Phase 1: Discovery (No AI, pure crawling)
    - Starts from a root URL
    - Follows all internal links
    - Identifies pages matching target pattern

    Phase 2: Extraction (AI-powered)
    - Extracts structured data from discovered pages only
    """

    def __init__(
        self,
        headless: bool = True,
        max_depth: int = 3,
        max_pages: int = 500,
        concurrent_crawls: int = 5,
        verbose: bool = False
    ):
        """
        Initialize the smart crawler.

        Args:
            headless: Run browser in headless mode
            max_depth: Maximum crawl depth from root URL
            max_pages: Maximum total pages to crawl (safety limit)
            concurrent_crawls: Number of concurrent crawl operations
            verbose: Enable verbose logging
        """
        self.headless = headless
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.concurrent_crawls = concurrent_crawls
        self.verbose = verbose

        # Track visited URLs to avoid duplicates
        self.visited: Set[str] = set()
        self.discovered_tech_pages: List[str] = []
        self.to_crawl: List[tuple[str, int]] = []  # (url, depth)

        logger.info(f"Initialized SmartVehicleCrawler (max_depth={max_depth}, max_pages={max_pages})")

    async def discover_technical_pages(
        self,
        root_url: str,
        pattern: str,
        domain_filter: Optional[str] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> List[str]:
        """
        Phase 1: Discover all pages matching the pattern.

        This crawls the website systematically, following links and identifying
        pages that match the target pattern (e.g., "*technische-daten.html").
        NO AI is used in this phase - only pattern matching.

        Args:
            root_url: Starting URL for crawling
            pattern: URL pattern to match (e.g., "technische-daten.html")
            domain_filter: Only follow links within this domain (default: extract from root_url)
            exclude_patterns: URL patterns to exclude from crawling

        Returns:
            List of URLs matching the pattern
        """
        logger.info(f"Starting discovery phase from: {root_url}")
        logger.info(f"Looking for pattern: {pattern}")

        # Reset state
        self.visited.clear()
        self.discovered_tech_pages.clear()
        self.to_crawl.clear()

        # Extract domain from root URL if not specified
        if not domain_filter:
            parsed = urlparse(root_url)
            domain_filter = parsed.netloc

        logger.info(f"Domain filter: {domain_filter}")

        # Start crawling from root
        self.to_crawl.append((root_url, 0))

        async with AsyncWebCrawler(headless=self.headless, verbose=self.verbose) as crawler:
            while self.to_crawl and len(self.visited) < self.max_pages:
                # Get next batch of URLs to crawl
                batch = []
                for _ in range(min(self.concurrent_crawls, len(self.to_crawl))):
                    if self.to_crawl:
                        batch.append(self.to_crawl.pop(0))

                # Crawl batch concurrently
                tasks = [
                    self._crawl_page(crawler, url, depth, pattern, domain_filter, exclude_patterns)
                    for url, depth in batch
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

                logger.info(
                    f"Progress: Visited={len(self.visited)}, "
                    f"Queue={len(self.to_crawl)}, "
                    f"Found={len(self.discovered_tech_pages)}"
                )

        logger.info(f"Discovery complete! Found {len(self.discovered_tech_pages)} technical pages")
        return self.discovered_tech_pages

    async def _crawl_page(
        self,
        crawler: AsyncWebCrawler,
        url: str,
        depth: int,
        pattern: str,
        domain_filter: str,
        exclude_patterns: Optional[List[str]]
    ):
        """Crawl a single page and extract links."""
        # Skip if already visited
        if url in self.visited:
            return

        # Mark as visited
        self.visited.add(url)

        # Check if this page matches our target pattern
        if pattern in url:
            logger.info(f"✓ Found technical page: {url}")
            self.discovered_tech_pages.append(url)

        # Stop if we've reached max depth
        if depth >= self.max_depth:
            return

        try:
            # Crawl the page
            result = await crawler.arun(url=url, bypass_cache=True)

            if not result.success:
                logger.warning(f"Failed to crawl {url}: {result.error_message}")
                return

            # Extract links from the page
            internal_links = []

            if hasattr(result, 'links') and result.links:
                # Handle different link formats from crawl4ai
                if isinstance(result.links, dict) and 'internal' in result.links:
                    internal_links = result.links['internal']
                    logger.debug(f"Got {len(internal_links)} internal links")
                elif isinstance(result.links, dict):
                    # Debug: log the keys
                    logger.debug(f"Link dict keys: {result.links.keys()}")
                    # Try to get all links from dict
                    for key in result.links:
                        if isinstance(result.links[key], list):
                            internal_links.extend(result.links[key])
                elif isinstance(result.links, list):
                    internal_links = result.links
                else:
                    logger.debug(f"Unknown link format: {type(result.links)}")
            else:
                logger.warning(f"No links attribute or links is empty on {url}")

            logger.info(f"Found {len(internal_links)} links on {url}")

            for link_obj in internal_links:
                # Handle both dict and string link formats
                if isinstance(link_obj, str):
                    link_url = link_obj
                elif isinstance(link_obj, dict):
                    link_url = link_obj.get('href', '')
                else:
                    continue

                if not link_url:
                    continue

                # Normalize URL
                link_url = urljoin(url, link_url)

                # Apply filters
                if not self._should_follow_link(link_url, domain_filter, exclude_patterns):
                    continue

                # Check if this link matches our target pattern (don't waste page budget on non-matches)
                if pattern in link_url:
                    if link_url not in self.discovered_tech_pages:
                        logger.info(f"✓ Found technical page link: {link_url}")
                        self.discovered_tech_pages.append(link_url)

                # Add to crawl queue if not visited
                if link_url not in self.visited and (link_url, depth + 1) not in self.to_crawl:
                    self.to_crawl.append((link_url, depth + 1))

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")

    def _should_follow_link(
        self,
        url: str,
        domain_filter: str,
        exclude_patterns: Optional[List[str]]
    ) -> bool:
        """Check if a link should be followed."""
        parsed = urlparse(url)

        # Must be same domain
        if domain_filter not in parsed.netloc:
            return False

        # Check exclude patterns
        if exclude_patterns:
            for pattern in exclude_patterns:
                if pattern in url:
                    return False

        # Skip common non-content pages
        skip_patterns = [
            '/search',
            '/login',
            '/logout',
            '/cart',
            '/checkout',
            '/account',
            '#',
            'javascript:',
            'mailto:',
            'tel:',
            '.pdf',
            '.jpg',
            '.png',
            '.gif',
            '.zip'
        ]

        for pattern in skip_patterns:
            if pattern in url.lower():
                return False

        return True

    def save_discovered_urls(self, output_file: str):
        """Save discovered URLs to a file."""
        with open(output_file, 'w') as f:
            for url in self.discovered_tech_pages:
                f.write(url + '\n')
        logger.info(f"Saved {len(self.discovered_tech_pages)} URLs to {output_file}")

    def load_discovered_urls(self, input_file: str) -> List[str]:
        """Load previously discovered URLs from a file."""
        with open(input_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        logger.info(f"Loaded {len(urls)} URLs from {input_file}")
        return urls
