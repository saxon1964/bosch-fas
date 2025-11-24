"""
Generate content-based fingerprints for vehicles.

Fingerprints are used to identify vehicles consistently across URL changes.
Format: "manufacturer_model_variant_year"
Example: "bmw_ix_xdrive50_2024"
"""
import re
from typing import Dict, Optional
from urllib.parse import urlparse


def generate_fingerprint_from_url(url: str, manufacturer_slug: str = None) -> str:
    """
    Generate fingerprint by parsing URL structure.

    Args:
        url: Vehicle URL (e.g., https://www.bmw.de/de/neufahrzeuge/bmw-i/ix/xdrive50/2024/technische-daten)
        manufacturer_slug: Manufacturer slug (e.g., "bmw")

    Returns:
        Fingerprint string (e.g., "bmw_i_ix_xdrive50_2024")
    """
    # Parse URL
    parsed = urlparse(url)
    path = parsed.path

    # Remove common noise from path
    noise_patterns = [
        'technische-daten', 'technical-data',
        'neufahrzeuge', 'new-vehicles',
        'modelle', 'models',
        'de', 'en', 'fr', 'it',  # Language codes
        'passengercars', 'cars',
        'html', 'htm'
    ]

    # Split path and clean
    parts = []
    for part in path.split('/'):
        # Skip empty parts
        if not part:
            continue

        # Skip noise
        part_lower = part.lower()
        if part_lower in noise_patterns:
            continue
        if part_lower.endswith('.html') or part_lower.endswith('.htm'):
            part = part_lower.replace('.html', '').replace('.htm', '')

        parts.append(part)

    # Clean and normalize each part
    clean_parts = []
    for part in parts:
        # Convert to lowercase
        part = part.lower()
        # Replace hyphens with underscores
        part = part.replace('-', '_')
        # Remove special characters except underscores and numbers
        part = re.sub(r'[^a-z0-9_]', '', part)
        # Remove duplicate underscores
        part = re.sub(r'_+', '_', part)
        # Strip underscores from edges
        part = part.strip('_')

        if part:
            clean_parts.append(part)

    # Join parts
    fingerprint = '_'.join(clean_parts)

    # If we have a manufacturer slug and it's not in the fingerprint, prepend it
    if manufacturer_slug:
        manufacturer_clean = manufacturer_slug.lower().replace('-', '_')
        if not fingerprint.startswith(manufacturer_clean):
            fingerprint = f"{manufacturer_clean}_{fingerprint}"

    # Final cleanup
    fingerprint = re.sub(r'_+', '_', fingerprint)
    fingerprint = fingerprint.strip('_')

    return fingerprint or 'unknown'


def generate_fingerprint_from_data(vehicle_data: Dict, url: str = None, manufacturer_slug: str = None) -> str:
    """
    Generate fingerprint from extracted vehicle data.

    Tries to use vehicle_identification fields first, falls back to URL.

    Args:
        vehicle_data: Extracted vehicle data dictionary
        url: Source URL (fallback)
        manufacturer_slug: Manufacturer slug (fallback)

    Returns:
        Fingerprint string
    """
    try:
        vid = vehicle_data.get('vehicle_identification', {})

        # Extract fields
        brand = _normalize_field(vid.get('brand', ''))
        model = _normalize_field(vid.get('model', ''))
        variant = _normalize_field(vid.get('variant', ''))
        year = _normalize_field(vid.get('model_year', ''))

        if brand and model:
            # Build from data
            parts = [brand.lower()]

            # Clean model name
            model_clean = model.lower()
            model_clean = model_clean.replace(brand.lower(), '')  # Remove brand from model
            model_clean = model_clean.strip()
            if model_clean:
                parts.append(model_clean)

            # Add variant if available
            if variant:
                variant_clean = variant.lower()
                variant_clean = variant_clean.replace(brand.lower(), '')  # Remove brand
                variant_clean = variant_clean.replace(model_clean, '')  # Remove model
                variant_clean = variant_clean.strip()
                if variant_clean:
                    parts.append(variant_clean)

            # Add year if available
            if year:
                parts.append(year)

            # Join and clean
            fingerprint = '_'.join(parts)
            fingerprint = re.sub(r'[^a-z0-9_]', '', fingerprint)
            fingerprint = re.sub(r'_+', '_', fingerprint)
            fingerprint = fingerprint.strip('_')

            if fingerprint:
                return fingerprint

    except Exception as e:
        # Fall through to URL-based fingerprint
        pass

    # Fallback to URL-based fingerprint
    if url:
        return generate_fingerprint_from_url(url, manufacturer_slug)

    return 'unknown'


def _normalize_field(value) -> str:
    """
    Normalize a field value to string.

    Handles lists (takes first item), None, and regular strings.

    Args:
        value: Field value (string, list, or None)

    Returns:
        Normalized string
    """
    if value is None:
        return ''
    if isinstance(value, list):
        # For lists, take first non-empty item
        for item in value:
            if item:
                return str(item).strip()
        return ''
    return str(value).strip()


def generate_fingerprint(url: str = None, vehicle_data: Dict = None, manufacturer_slug: str = None) -> str:
    """
    Generate fingerprint using best available method.

    Tries in order:
    1. From vehicle_data (if provided)
    2. From URL (if provided)
    3. Returns 'unknown'

    Args:
        url: Vehicle URL
        vehicle_data: Extracted vehicle data
        manufacturer_slug: Manufacturer slug

    Returns:
        Fingerprint string
    """
    # Try data-based first
    if vehicle_data:
        fingerprint = generate_fingerprint_from_data(vehicle_data, url, manufacturer_slug)
        if fingerprint != 'unknown':
            return fingerprint

    # Try URL-based
    if url:
        return generate_fingerprint_from_url(url, manufacturer_slug)

    return 'unknown'
