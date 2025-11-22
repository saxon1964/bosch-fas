"""
Bootstrap tracking.db from existing extracted data.

This script:
1. Finds all extracted JSON files in data/runs/
2. Generates fingerprints for each vehicle
3. Creates tracking.db and populates it
4. Copies JSON files to data/archive/
5. Marks all as initial baseline (first_seen = extraction_date)

Run this ONCE after initial extraction to prepare for monthly runs.
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import re


def normalize_field(value) -> str:
    """
    Normalize a field value to string.

    Args:
        value: Field value (string, list, or None)

    Returns:
        Normalized string
    """
    if value is None:
        return ''
    if isinstance(value, list):
        # Join list items with comma
        return ', '.join(str(v) for v in value if v)
    return str(value)


def generate_fingerprint(vehicle_data: dict, url: str) -> str:
    """
    Generate content-based fingerprint for a vehicle.

    Format: "manufacturer_model_variant_year"
    Example: "bmw_ix_xdrive50_2024"

    Args:
        vehicle_data: Extracted vehicle data
        url: Source URL (fallback if data missing)

    Returns:
        Fingerprint string
    """
    try:
        # Try to get from vehicle identification
        vid = vehicle_data.get('vehicle_identification', {})
        brand = normalize_field(vid.get('brand', '')).lower().strip()
        model = normalize_field(vid.get('model', '')).lower().strip()
        variant = normalize_field(vid.get('variant', '')).lower().strip()
        year = normalize_field(vid.get('model_year', '')).strip()

        if brand and model:
            parts = [brand, model]
            if variant:
                parts.append(variant)
            if year:
                parts.append(year)

            # Clean and join
            fingerprint = '_'.join(parts)
            fingerprint = re.sub(r'[^a-z0-9_]', '', fingerprint)
            fingerprint = re.sub(r'_+', '_', fingerprint)  # Remove duplicate underscores
            return fingerprint

    except Exception as e:
        print(f"  Warning: Could not extract fingerprint from data: {e}")

    # Fallback: generate from URL
    # Example: /bmw-i/ix-xdrive50/2024/ -> bmw_i_ix_xdrive50_2024
    url_parts = [p for p in url.split('/') if p and p not in ['de', 'en', 'neufahrzeuge', 'new-vehicles', 'technische-daten', 'technical-data']]
    fingerprint = '_'.join(url_parts[-4:])  # Take last 4 parts
    fingerprint = re.sub(r'[^a-z0-9_-]', '', fingerprint.lower())
    fingerprint = fingerprint.replace('-', '_')
    fingerprint = re.sub(r'_+', '_', fingerprint)
    return fingerprint or 'unknown'


def create_database(db_path: Path):
    """Create tracking database with schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Vehicles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            fingerprint TEXT PRIMARY KEY,
            manufacturer TEXT NOT NULL,
            model TEXT,
            variant TEXT,
            model_year TEXT,

            url TEXT NOT NULL,
            url_history TEXT,  -- JSON array of previous URLs

            first_seen DATE NOT NULL,
            last_seen DATE NOT NULL,
            last_url_change DATE,

            status TEXT DEFAULT 'active',  -- 'active' or 'disappeared'

            json_file_path TEXT  -- Path to JSON file in archive
        )
    """)

    # Manufacturers table
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

    # Run history table
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
    return conn


def bootstrap_from_runs(runs_dir: Path, archive_dir: Path, db_path: Path):
    """
    Import all extracted data from runs/ into tracking.db and archive/.

    Args:
        runs_dir: data/runs/ directory
        archive_dir: data/archive/ directory
        db_path: tracking.db path
    """
    print("="*80)
    print("BOOTSTRAP TRACKING DATABASE")
    print("="*80)
    print()

    # Create database
    print("Creating tracking database...")
    conn = create_database(db_path)
    cursor = conn.cursor()
    print(f"✓ Database created: {db_path}")
    print()

    # Find all run directories
    run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()])

    if not run_dirs:
        print("ERROR: No run directories found in data/runs/")
        return

    print(f"Found {len(run_dirs)} run(s) to import:")
    for rd in run_dirs:
        print(f"  - {rd.name}")
    print()

    total_vehicles = 0
    manufacturers_seen = set()

    # Process each run
    for run_dir in run_dirs:
        run_date = run_dir.name
        extracted_dir = run_dir / "extracted"

        if not extracted_dir.exists():
            print(f"⚠ Skipping {run_date}: No extracted/ directory")
            continue

        print(f"Processing run: {run_date}")
        print("-" * 80)

        # Process each manufacturer
        for manufacturer_dir in extracted_dir.iterdir():
            if not manufacturer_dir.is_dir():
                continue

            manufacturer_slug = manufacturer_dir.name
            manufacturers_seen.add(manufacturer_slug)

            print(f"  {manufacturer_slug.upper()}:")

            # Find all individual JSON files (not *_all.json or *_progress.json)
            json_files = [
                f for f in manufacturer_dir.glob("*.json")
                if not f.stem.endswith('_all') and not f.stem.endswith('_progress')
            ]

            if not json_files:
                print(f"    ⚠ No individual JSON files found")
                continue

            # Create archive directory for this manufacturer
            manufacturer_archive = archive_dir / manufacturer_slug
            manufacturer_archive.mkdir(parents=True, exist_ok=True)

            vehicles_added = 0

            for json_file in json_files:
                try:
                    # Load vehicle data
                    with open(json_file, 'r', encoding='utf-8') as f:
                        vehicle_data = json.load(f)

                    # Get URL from metadata
                    metadata = vehicle_data.get('_extraction_metadata', {})
                    url = metadata.get('url', '')

                    if not url:
                        print(f"    ⚠ Skipping {json_file.name}: No URL in metadata")
                        continue

                    # Generate fingerprint
                    fingerprint = generate_fingerprint(vehicle_data, url)

                    # Extract vehicle info (normalize lists to strings)
                    vid = vehicle_data.get('vehicle_identification', {})
                    manufacturer = normalize_field(vid.get('brand', manufacturer_slug.upper()))
                    model = normalize_field(vid.get('model', ''))
                    variant = normalize_field(vid.get('variant', ''))
                    model_year = normalize_field(vid.get('model_year', ''))

                    # Archive file path
                    archive_file = manufacturer_archive / json_file.name
                    relative_path = str(archive_file.relative_to(archive_dir.parent))

                    # Copy to archive (if not already there)
                    if not archive_file.exists():
                        import shutil
                        shutil.copy2(json_file, archive_file)

                    # Insert into database (or update if exists)
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
                        json.dumps([]),  # Empty URL history for baseline
                        run_date,
                        run_date,
                        'active',
                        relative_path
                    ))

                    vehicles_added += 1

                except Exception as e:
                    print(f"    ✗ Error processing {json_file.name}: {e}")

            print(f"    ✓ Added {vehicles_added} vehicles to database")
            print(f"    ✓ Copied to data/archive/{manufacturer_slug}/")
            total_vehicles += vehicles_added

        print()

    # Update manufacturers table
    print("Updating manufacturers table...")
    for slug in manufacturers_seen:
        # Count models for this manufacturer
        cursor.execute("SELECT COUNT(*) FROM vehicles WHERE manufacturer = ?", (slug.upper(),))
        count = cursor.fetchone()[0]

        cursor.execute("""
            INSERT OR REPLACE INTO manufacturers (slug, name, total_models, first_crawled, last_crawled)
            VALUES (?, ?, ?, ?, ?)
        """, (slug, slug.upper(), count, run_dirs[0].name, run_dirs[-1].name))

    conn.commit()

    # Summary
    print("="*80)
    print("BOOTSTRAP COMPLETE")
    print("="*80)
    print(f"Total vehicles imported: {total_vehicles}")
    print(f"Manufacturers: {len(manufacturers_seen)}")
    print(f"Database: {db_path}")
    print(f"Archive: {archive_dir}")
    print()

    # Show summary by manufacturer
    print("Summary by manufacturer:")
    cursor.execute("""
        SELECT manufacturer, COUNT(*) as count
        FROM vehicles
        GROUP BY manufacturer
        ORDER BY count DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} models")

    print()
    print("✓ Ready for monthly production runs!")
    print()

    conn.close()


def main():
    """Bootstrap database from existing extracted data."""
    project_root = Path(__file__).parent.parent
    runs_dir = project_root / "data" / "runs"
    archive_dir = project_root / "data" / "archive"
    db_path = project_root / "data" / "tracking.db"

    if not runs_dir.exists():
        print(f"ERROR: {runs_dir} does not exist")
        print("Run test_extractor.py first to extract data.")
        return

    if db_path.exists():
        print(f"WARNING: {db_path} already exists")
        response = input("Overwrite existing database? (yes/no): ")
        if response.lower() != 'yes':
            print("Bootstrap cancelled.")
            return
        db_path.unlink()

    bootstrap_from_runs(runs_dir, archive_dir, db_path)


if __name__ == "__main__":
    main()
