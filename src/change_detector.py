"""
Detect changes between discovered URLs and tracking database.

Classifies each discovered URL as:
- NEW: Never seen before (needs extraction)
- EXISTING: Already in database (skip)
- URL_CHANGED: Same fingerprint, different URL (update DB only)
- DISAPPEARED: In database but not discovered (mark inactive)
"""
import sqlite3
from pathlib import Path
from typing import Dict, List, Set
from dataclasses import dataclass

from src.fingerprint import generate_fingerprint


@dataclass
class ChangeDetectionResult:
    """Result of change detection for one manufacturer."""
    manufacturer_slug: str
    new_urls: List[Dict[str, str]]  # [{'url': ..., 'fingerprint': ...}]
    existing_urls: List[Dict[str, str]]  # Already have these
    url_changed: List[Dict[str, str]]  # [{'fingerprint': ..., 'old_url': ..., 'new_url': ...}]
    disappeared: List[Dict[str, str]]  # [{'fingerprint': ..., 'url': ..., 'model': ...}]

    @property
    def total_new(self) -> int:
        return len(self.new_urls)

    @property
    def total_existing(self) -> int:
        return len(self.existing_urls)

    @property
    def total_url_changed(self) -> int:
        return len(self.url_changed)

    @property
    def total_disappeared(self) -> int:
        return len(self.disappeared)


class ChangeDetector:
    """Detect changes between discovered URLs and tracking database."""

    def __init__(self, db_path: str = "data/tracking.db"):
        """
        Initialize change detector.

        Args:
            db_path: Path to tracking database
        """
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Tracking database not found: {db_path}\n"
                f"Run bootstrap_db.py first to create the database."
            )

    def detect_changes(
        self,
        discovered_urls: Dict[str, List[str]],
        manufacturer_slug: str = None
    ) -> Dict[str, ChangeDetectionResult]:
        """
        Detect changes for all manufacturers or a specific one.

        Args:
            discovered_urls: Dict mapping manufacturer_slug to list of URLs
            manufacturer_slug: Optional - process only this manufacturer

        Returns:
            Dict mapping manufacturer_slug to ChangeDetectionResult
        """
        results = {}

        # Filter to specific manufacturer if requested
        if manufacturer_slug:
            if manufacturer_slug not in discovered_urls:
                raise ValueError(f"Manufacturer '{manufacturer_slug}' not in discovered URLs")
            manufacturers_to_process = {manufacturer_slug: discovered_urls[manufacturer_slug]}
        else:
            manufacturers_to_process = discovered_urls

        # Process each manufacturer
        for slug, urls in manufacturers_to_process.items():
            results[slug] = self._detect_changes_for_manufacturer(slug, urls)

        return results

    def _detect_changes_for_manufacturer(
        self,
        manufacturer_slug: str,
        discovered_urls: List[str]
    ) -> ChangeDetectionResult:
        """
        Detect changes for a single manufacturer.

        Args:
            manufacturer_slug: Manufacturer slug (e.g., "bmw")
            discovered_urls: List of discovered URLs for this manufacturer

        Returns:
            ChangeDetectionResult
        """
        # Connect to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Load existing vehicles for this manufacturer
        cursor.execute("""
            SELECT fingerprint, url, model, variant, model_year, status
            FROM vehicles
            WHERE manufacturer = ? OR manufacturer = ?
        """, (manufacturer_slug.upper(), manufacturer_slug.lower()))

        existing_vehicles = {}
        for row in cursor.fetchall():
            fingerprint, url, model, variant, year, status = row
            existing_vehicles[fingerprint] = {
                'fingerprint': fingerprint,
                'url': url,
                'model': model or '',
                'variant': variant or '',
                'model_year': year or '',
                'status': status
            }

        # Generate fingerprints for discovered URLs
        discovered_fingerprints = {}
        for url in discovered_urls:
            fingerprint = generate_fingerprint(url=url, manufacturer_slug=manufacturer_slug)
            discovered_fingerprints[fingerprint] = url

        # Classify URLs
        new_urls = []
        existing_urls = []
        url_changed = []

        for fingerprint, url in discovered_fingerprints.items():
            if fingerprint in existing_vehicles:
                # Vehicle exists in database
                existing_url = existing_vehicles[fingerprint]['url']

                if url == existing_url:
                    # Exact match - already have this
                    existing_urls.append({
                        'url': url,
                        'fingerprint': fingerprint
                    })
                else:
                    # URL changed for same vehicle
                    url_changed.append({
                        'fingerprint': fingerprint,
                        'old_url': existing_url,
                        'new_url': url,
                        'model': existing_vehicles[fingerprint]['model']
                    })
            else:
                # New vehicle never seen before
                new_urls.append({
                    'url': url,
                    'fingerprint': fingerprint
                })

        # Find disappeared vehicles (in DB but not discovered)
        discovered_fp_set = set(discovered_fingerprints.keys())
        existing_fp_set = set(existing_vehicles.keys())
        disappeared_fps = existing_fp_set - discovered_fp_set

        disappeared = []
        for fp in disappeared_fps:
            vehicle = existing_vehicles[fp]
            # Only report if currently active
            if vehicle['status'] == 'active':
                disappeared.append({
                    'fingerprint': fp,
                    'url': vehicle['url'],
                    'model': vehicle['model'],
                    'variant': vehicle['variant'],
                    'model_year': vehicle['model_year']
                })

        conn.close()

        return ChangeDetectionResult(
            manufacturer_slug=manufacturer_slug,
            new_urls=new_urls,
            existing_urls=existing_urls,
            url_changed=url_changed,
            disappeared=disappeared
        )

    def print_summary(self, results: Dict[str, ChangeDetectionResult]):
        """
        Print human-readable summary of changes.

        Args:
            results: Dict mapping manufacturer_slug to ChangeDetectionResult
        """
        print("\n" + "="*80)
        print("CHANGE DETECTION SUMMARY")
        print("="*80)

        total_new = 0
        total_existing = 0
        total_url_changed = 0
        total_disappeared = 0

        for slug, result in results.items():
            print(f"\n{slug.upper()}:")
            print(f"  ✨ NEW models: {result.total_new}")
            print(f"  ✓ EXISTING models: {result.total_existing}")
            print(f"  🔄 URL changes: {result.total_url_changed}")
            print(f"  ⚠️  DISAPPEARED models: {result.total_disappeared}")

            # Show details for new models
            if result.new_urls:
                print(f"\n  New models to extract:")
                for item in result.new_urls[:5]:
                    print(f"    - {item['url']}")
                if len(result.new_urls) > 5:
                    print(f"    ... and {len(result.new_urls) - 5} more")

            # Show URL changes
            if result.url_changed:
                print(f"\n  URL changes (will update database):")
                for item in result.url_changed[:3]:
                    print(f"    - {item['model']}")
                    print(f"      Old: {item['old_url']}")
                    print(f"      New: {item['new_url']}")
                if len(result.url_changed) > 3:
                    print(f"    ... and {len(result.url_changed) - 3} more")

            # Show disappeared models
            if result.disappeared:
                print(f"\n  ⚠️  Models no longer found (will mark inactive):")
                for item in result.disappeared[:5]:
                    model_str = f"{item['model']} {item['variant']} {item['model_year']}".strip()
                    print(f"    - {model_str}")
                if len(result.disappeared) > 5:
                    print(f"    ... and {len(result.disappeared) - 5} more")

            total_new += result.total_new
            total_existing += result.total_existing
            total_url_changed += result.total_url_changed
            total_disappeared += result.total_disappeared

        print("\n" + "="*80)
        print(f"TOTALS:")
        print(f"  ✨ NEW models to extract: {total_new}")
        print(f"  ✓ EXISTING models (skip): {total_existing}")
        print(f"  🔄 URL changes: {total_url_changed}")
        print(f"  ⚠️  DISAPPEARED models: {total_disappeared}")
        print("="*80)

        # Cost estimate
        if total_new > 0:
            estimated_cost = total_new * 0.006  # Based on actual cost from BMW extraction
            estimated_time = total_new * 10 / 60  # 10 seconds per model
            print(f"\nEstimated extraction cost: ${estimated_cost:.2f}")
            print(f"Estimated extraction time: {estimated_time:.1f} minutes")
        print()
