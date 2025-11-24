"""
Production orchestrator for vehicle data extraction system.

Simple one-command workflow:
1. Crawl all manufacturers
2. Detect changes (new/existing/url_changed/disappeared)
3. Extract ONLY new models
4. Update archive and database
5. Print summary

Usage:
    python scripts/run_production.py

For IT amateurs - just add manufacturers to config/manufacturers.yaml and run this script!
"""
import asyncio
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler import MultiManufacturerCrawler
from src.extractor import MultiManufacturerExtractor
from src.change_detector import ChangeDetector
from src.fingerprint import generate_fingerprint


async def main():
    """Run production workflow."""
    print("="*80)
    print("PRODUCTION RUN - Vehicle Data Extraction")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    run_date = datetime.now().strftime("%Y-%m-%d")
    start_time = datetime.now()

    # -------------------------------------------------------------------------
    # STEP 1: CRAWL
    # -------------------------------------------------------------------------
    print("="*80)
    print("STEP 1: CRAWLING ALL MANUFACTURERS")
    print("="*80)
    print()

    crawler = MultiManufacturerCrawler(config_path="config/manufacturers.yaml")
    discovered_urls = await crawler.crawl_all()

    # Save discovered URLs
    crawler.save_results(discovered_urls, run_date)

    # Summary
    total_discovered = sum(len(urls) for urls in discovered_urls.values())
    print(f"\n✓ Crawling complete: {total_discovered} URLs discovered")
    for slug, urls in discovered_urls.items():
        print(f"  - {slug.upper()}: {len(urls)} URLs")
    print()

    # -------------------------------------------------------------------------
    # STEP 2: DETECT CHANGES
    # -------------------------------------------------------------------------
    print("="*80)
    print("STEP 2: DETECTING CHANGES")
    print("="*80)

    # Check if database exists
    db_path = Path("data/tracking.db")
    if not db_path.exists():
        print()
        print("⚠️  WARNING: No tracking database found!")
        print("This appears to be the first run for all manufacturers.")
        print("All discovered models will be treated as NEW.")
        print()

        # Create empty database
        print("Creating tracking database...")
        _create_empty_database(db_path)
        print("✓ Database created")
        print()

    # Detect changes
    detector = ChangeDetector(db_path="data/tracking.db")
    changes = detector.detect_changes(discovered_urls)
    detector.print_summary(changes)

    # -------------------------------------------------------------------------
    # STEP 3: EXTRACT NEW MODELS
    # -------------------------------------------------------------------------
    total_new = sum(result.total_new for result in changes.values())

    if total_new == 0:
        print("="*80)
        print("NO NEW MODELS FOUND")
        print("="*80)
        print("\nAll discovered models already exist in the database.")
        print("Nothing to extract. Run complete!")
        print()

        # Update URL changes and disappeared models in database
        _update_database_metadata(changes, run_date)

        return

    print("="*80)
    print(f"STEP 3: EXTRACTING {total_new} NEW MODELS")
    print("="*80)
    print()

    # Build URL list for extraction (only NEW models)
    urls_to_extract = {}
    for slug, result in changes.items():
        if result.new_urls:
            urls_to_extract[slug] = [item['url'] for item in result.new_urls]

    # Extract
    extractor = MultiManufacturerExtractor(config_path="config/manufacturers.yaml")
    extraction_summary = await extractor.extract_all(urls_to_extract, run_date)

    print()
    print("✓ Extraction complete")
    print()

    # -------------------------------------------------------------------------
    # STEP 4: UPDATE ARCHIVE AND DATABASE
    # -------------------------------------------------------------------------
    print("="*80)
    print("STEP 4: UPDATING ARCHIVE AND DATABASE")
    print("="*80)
    print()

    archive_dir = Path("data/archive")
    run_extracted_dir = Path(f"data/runs/{run_date}/extracted")

    total_archived = 0
    total_db_inserted = 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for slug, result in changes.items():
        if result.total_new == 0:
            continue

        print(f"{slug.upper()}:")

        # Create archive directory
        manufacturer_archive = archive_dir / slug
        manufacturer_archive.mkdir(parents=True, exist_ok=True)

        # Copy new JSON files to archive
        manufacturer_extracted = run_extracted_dir / slug

        if manufacturer_extracted.exists():
            json_files = [
                f for f in manufacturer_extracted.glob("*.json")
                if not f.stem.endswith('_all') and not f.stem.endswith('_progress')
            ]

            for json_file in json_files:
                # Copy to archive
                archive_file = manufacturer_archive / json_file.name

                if not archive_file.exists():
                    shutil.copy2(json_file, archive_file)
                    total_archived += 1

                # Insert into database
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        vehicle_data = json.load(f)

                    metadata = vehicle_data.get('_extraction_metadata', {})
                    url = metadata.get('url', '')

                    if not url:
                        continue

                    # Generate fingerprint
                    fingerprint = generate_fingerprint(url=url, vehicle_data=vehicle_data, manufacturer_slug=slug)

                    # Extract vehicle info
                    vid = vehicle_data.get('vehicle_identification', {})
                    manufacturer = _normalize_field(vid.get('brand', slug.upper()))
                    model = _normalize_field(vid.get('model', ''))
                    variant = _normalize_field(vid.get('variant', ''))
                    model_year = _normalize_field(vid.get('model_year', ''))

                    # Archive file path
                    relative_path = str(archive_file.relative_to(archive_dir.parent))

                    # Insert into database
                    cursor.execute("""
                        INSERT OR REPLACE INTO vehicles (
                            fingerprint,
                            manufacturer,
                            model,
                            variant,
                            model_year,
                            url,
                            url_history,
                            first_seen,
                            last_seen,
                            status,
                            json_file_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        fingerprint,
                        manufacturer,
                        model,
                        variant,
                        model_year,
                        url,
                        json.dumps([]),
                        run_date,
                        run_date,
                        'active',
                        relative_path
                    ))

                    total_db_inserted += 1

                except Exception as e:
                    print(f"  ✗ Error processing {json_file.name}: {e}")

            print(f"  ✓ Archived {total_archived} new models to data/archive/{slug}/")
            print(f"  ✓ Added {total_db_inserted} vehicles to database")

    # Update URL changes and disappeared models
    _update_database_metadata(changes, run_date, cursor)

    # Update manufacturers table
    for slug in discovered_urls.keys():
        cursor.execute("SELECT COUNT(*) FROM vehicles WHERE manufacturer = ?", (slug.upper(),))
        count = cursor.fetchone()[0]

        cursor.execute("""
            INSERT OR REPLACE INTO manufacturers (slug, name, total_models, last_crawled)
            VALUES (?, ?, ?, ?)
        """, (slug, slug.upper(), count, run_date))

    # Save run history
    total_cost = extraction_summary.get('total_cost_usd', 0) if extraction_summary else 0
    duration = (datetime.now() - start_time).total_seconds() / 60

    cursor.execute("""
        INSERT OR REPLACE INTO runs (
            date,
            total_new,
            total_url_changes,
            total_disappeared,
            total_extracted,
            total_cost_usd,
            duration_minutes
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        run_date,
        total_new,
        sum(r.total_url_changed for r in changes.values()),
        sum(r.total_disappeared for r in changes.values()),
        total_new,
        total_cost,
        duration
    ))

    conn.commit()
    conn.close()

    print()
    print("✓ Archive updated")
    print("✓ Database updated")
    print()

    # -------------------------------------------------------------------------
    # FINAL SUMMARY
    # -------------------------------------------------------------------------
    print("="*80)
    print("PRODUCTION RUN COMPLETE")
    print("="*80)
    print(f"Date: {run_date}")
    print(f"Duration: {duration:.1f} minutes")
    print()
    print(f"New models extracted: {total_new}")
    print(f"URL changes updated: {sum(r.total_url_changed for r in changes.values())}")
    print(f"Disappeared models marked: {sum(r.total_disappeared for r in changes.values())}")
    print()
    if total_cost > 0:
        print(f"Total cost: ${total_cost:.2f}")
        print()
    print("Results saved to:")
    print(f"  - data/runs/{run_date}/")
    print(f"  - data/archive/")
    print(f"  - data/tracking.db")
    print()
    print("="*80)


def _normalize_field(value) -> str:
    """Normalize field value to string."""
    if value is None:
        return ''
    if isinstance(value, list):
        return ', '.join(str(v) for v in value if v)
    return str(value)


def _create_empty_database(db_path: Path):
    """Create empty tracking database with schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            fingerprint TEXT PRIMARY KEY,
            manufacturer TEXT NOT NULL,
            model TEXT,
            variant TEXT,
            model_year TEXT,
            url TEXT NOT NULL,
            url_history TEXT,
            first_seen DATE NOT NULL,
            last_seen DATE NOT NULL,
            last_url_change DATE,
            status TEXT DEFAULT 'active',
            json_file_path TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manufacturers (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            root_url TEXT,
            first_crawled DATE,
            last_crawled DATE,
            total_models INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            date DATE PRIMARY KEY,
            total_new INTEGER DEFAULT 0,
            total_url_changes INTEGER DEFAULT 0,
            total_disappeared INTEGER DEFAULT 0,
            total_extracted INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0,
            duration_minutes REAL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def _update_database_metadata(changes, run_date, cursor=None):
    """Update URL changes and disappeared models in database."""
    should_close = False
    if cursor is None:
        conn = sqlite3.connect("data/tracking.db")
        cursor = conn.cursor()
        should_close = True

    # Update URL changes
    for slug, result in changes.items():
        for item in result.url_changed:
            fingerprint = item['fingerprint']
            new_url = item['new_url']
            old_url = item['old_url']

            # Get current URL history
            cursor.execute("SELECT url_history FROM vehicles WHERE fingerprint = ?", (fingerprint,))
            row = cursor.fetchone()
            if row:
                url_history = json.loads(row[0]) if row[0] else []
                # Add old URL to history if not already there
                if old_url not in url_history:
                    url_history.append(old_url)

                # Update vehicle
                cursor.execute("""
                    UPDATE vehicles
                    SET url = ?, url_history = ?, last_seen = ?, last_url_change = ?
                    WHERE fingerprint = ?
                """, (new_url, json.dumps(url_history), run_date, run_date, fingerprint))

        # Mark disappeared models as inactive
        for item in result.disappeared:
            fingerprint = item['fingerprint']
            cursor.execute("""
                UPDATE vehicles
                SET status = 'disappeared'
                WHERE fingerprint = ?
            """, (fingerprint,))

        # Update last_seen for existing models
        for item in result.existing_urls:
            fingerprint = item['fingerprint']
            cursor.execute("""
                UPDATE vehicles
                SET last_seen = ?
                WHERE fingerprint = ?
            """, (run_date, fingerprint))

    if should_close:
        conn.commit()
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
