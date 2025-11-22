"""
Retry failed extractions with improved JSON parsing.

The issue: Claude sometimes returns valid JSON followed by extra text.
The fix: Extract only the first complete JSON object.
"""
import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv

from crawl4ai import AsyncWebCrawler
from anthropic import Anthropic
from technical_data_schema import get_extraction_prompt
from datetime import datetime

async def retry_failed():
    """Retry failed URLs."""
    print("=" * 80)
    print("RETRYING FAILED EXTRACTIONS")
    print("=" * 80)
    print()

    # Load API key from .env.scripts (not .env to avoid Claude Code conflict)
    load_dotenv('.env.scripts')
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in .env.scripts")
        return

    print("✓ API key loaded from .env.scripts\n")

    client = Anthropic(api_key=api_key)

    # Load failed URLs
    with open("output/extracted_data/failed_urls.json", "r") as f:
        failed = json.load(f)

    failed_urls = [item["url"] for item in failed]

    print(f"Retrying {len(failed_urls)} failed URLs...")
    print()

    success_count = 0
    output_dir = Path("output/extracted_data")

    for i, url in enumerate(failed_urls, 1):
        print(f"[{i}/{len(failed_urls)}] {url}")

        # Fetch page
        try:
            async with AsyncWebCrawler(headless=True, verbose=False) as crawler:
                result = await crawler.arun(url=url, bypass_cache=True)
                if not result.success:
                    print(f"  ✗ Failed to fetch")
                    continue
                content = result.markdown or result.html

            # Extract with AI
            prompt = get_extraction_prompt(url, content)
            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            # Extract FIRST complete JSON object
            # Find opening brace
            start_idx = response_text.find('{')
            if start_idx == -1:
                print(f"  ✗ No JSON found")
                continue

            # Count braces to find matching closing brace
            brace_count = 0
            for idx in range(start_idx, len(response_text)):
                if response_text[idx] == '{':
                    brace_count += 1
                elif response_text[idx] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found complete JSON
                        json_text = response_text[start_idx:idx+1]
                        data = json.loads(json_text)

                        # Add metadata
                        data['_extraction_metadata'] = {
                            'extracted_at': datetime.utcnow().isoformat(),
                            'model': 'claude-3-haiku-20240307',
                            'url': url
                        }

                        # Save individual file
                        filename = url.split('/')[-1].replace('.html', '').replace('-technische-daten', '')
                        filename = filename.split('?')[0]  # Remove query params
                        filepath = output_dir / f"{filename}.json"

                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)

                        print(f"  ✓ Extracted and saved to {filepath.name}")
                        success_count += 1
                        break
            else:
                print(f"  ✗ Could not find complete JSON")

        except Exception as e:
            print(f"  ✗ Error: {e}")

    print()
    print("=" * 80)
    print(f"Retry complete: {success_count}/{len(failed_urls)} successful")
    print("=" * 80)

    if success_count == len(failed_urls):
        print()
        print("🎉 100% SUCCESS! All vehicles extracted!")
        print()
        print("Now update the combined file:")
        print("  python3 -c \"import json; from pathlib import Path; files = list(Path('output/extracted_data').glob('*.json')); files.remove(Path('output/extracted_data/failed_urls.json')) if Path('output/extracted_data/failed_urls.json') in files else None; data = [json.load(open(f)) for f in files if f.name not in ['all_vehicles.json', 'failed_urls.json']]; json.dump(data, open('output/extracted_data/all_vehicles.json', 'w'), indent=2)\"")


if __name__ == "__main__":
    asyncio.run(retry_failed())
