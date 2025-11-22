"""
Test the multi-manufacturer crawler with BMW configuration.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler import MultiManufacturerCrawler


async def main():
    """Test crawler with BMW configuration."""
    print("="*80)
    print("TESTING MULTI-MANUFACTURER CRAWLER")
    print("="*80)
    print()

    # Create crawler
    crawler = MultiManufacturerCrawler(config_path="config/manufacturers.yaml")

    # Crawl all manufacturers (just BMW for now)
    results = await crawler.crawl_all()

    # Save results
    crawler.save_results(results)

    # Summary
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

    for slug, urls in results.items():
        print(f"\n{slug.upper()}:")
        print(f"  Total URLs found: {len(urls)}")
        print(f"  Sample URLs:")
        for url in urls[:5]:
            print(f"    - {url}")
        if len(urls) > 5:
            print(f"    ... and {len(urls) - 5} more")

    print(f"\n✓ Results saved to data/runs/")


if __name__ == "__main__":
    asyncio.run(main())
