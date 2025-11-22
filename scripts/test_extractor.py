"""
Test the multi-manufacturer extractor with discovered URLs.
"""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractor import MultiManufacturerExtractor


async def main():
    """Test extractor with discovered URLs from crawler."""
    print("="*80)
    print("TESTING MULTI-MANUFACTURER EXTRACTOR")
    print("="*80)
    print()

    # Find most recent run
    runs_dir = Path("data/runs")
    if not runs_dir.exists():
        print("ERROR: No crawler results found. Run test_crawler.py first.")
        return

    # Get latest run directory
    run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], reverse=True)
    if not run_dirs:
        print("ERROR: No crawler results found. Run test_crawler.py first.")
        return

    latest_run = run_dirs[0]
    run_date = latest_run.name

    print(f"Using crawler results from: {run_date}")
    print()

    # Load discovered URLs
    discovered_dir = latest_run / "discovered"
    if not discovered_dir.exists():
        print(f"ERROR: No discovered URLs found in {latest_run}")
        return

    discovered_urls = {}
    for url_file in discovered_dir.glob("*_urls.txt"):
        manufacturer_slug = url_file.stem.replace("_urls", "")

        with open(url_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]

        discovered_urls[manufacturer_slug] = urls
        print(f"Loaded {len(urls)} URLs for {manufacturer_slug.upper()}")

    if not discovered_urls:
        print("ERROR: No URLs found to extract")
        return

    print()
    total_urls = sum(len(urls) for urls in discovered_urls.values())
    print(f"Total URLs to extract: {total_urls}")
    print(f"Estimated cost: ${total_urls * 0.02:.2f}")
    print(f"Estimated time: {total_urls * 10 / 60:.1f} minutes (with 10s throttling)")
    print()

    response = input("Continue with extraction? (yes/no): ")
    if response.lower() != 'yes':
        print("Extraction cancelled.")
        return

    print()
    print("Starting extraction...")
    print()

    # Create extractor
    extractor = MultiManufacturerExtractor(config_path="config/manufacturers.yaml")

    # Extract all
    summary = await extractor.extract_all(discovered_urls, run_date)

    # Print summary
    print("\n" + "="*80)
    print("EXTRACTION SUMMARY")
    print("="*80)
    print(json.dumps(summary, indent=2))
    print()
    print(f"✓ Results saved to data/runs/{run_date}/extracted/")


if __name__ == "__main__":
    asyncio.run(main())
