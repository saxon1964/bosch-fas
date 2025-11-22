"""
Diagnostic script to test Anthropic API key.

This helps identify API key issues before running extraction.
"""
import os
from dotenv import load_dotenv
from anthropic import Anthropic

def test_api_key():
    """Test if API key is valid and has access."""
    print("=" * 80)
    print("ANTHROPIC API KEY DIAGNOSTIC")
    print("=" * 80)
    print()

    # Load API key from .env.scripts (not .env to avoid Claude Code conflict)
    load_dotenv('.env.scripts')
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("✗ ERROR: ANTHROPIC_API_KEY not found in .env.scripts file")
        print()
        print("Please create .env.scripts file with your API key:")
        print("  1. cp .env.example .env.scripts")
        print("  2. Edit .env.scripts and add: ANTHROPIC_API_KEY=your-key-here")
        print()
        print("NOTE: We use .env.scripts instead of .env to prevent")
        print("      Claude Code from auto-loading it (Pro subscription conflict)")
        return

    print("✓ API key loaded from .env.scripts")

    print(f"  Key starts with: {api_key[:12]}...")
    print(f"  Key length: {len(api_key)} characters")
    print()

    # Check key format
    if not api_key.startswith("sk-ant-api"):
        print("⚠ WARNING: Key doesn't start with 'sk-ant-api'")
        print("  Are you sure this is an Anthropic API key?")
        print("  Claude Pro account ≠ API key")
        print("  Get API key from: https://console.anthropic.com/settings/keys")
        print()

    # Test API connection
    print("Testing API connection...")
    print()

    try:
        client = Anthropic(api_key=api_key)

        # Try a simple API call (using Haiku - fast and cheap)
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": "Say 'API key works!'"
            }]
        )

        response_text = message.content[0].text

        print("✓ SUCCESS! API key is valid and working")
        print(f"  API Response: {response_text}")
        print(f"  Model used: claude-3-haiku-20240307")
        print()
        print("Your API key is correctly configured!")
        print("You can now run:")
        print("  - python scripts/test_crawler.py  (test crawler)")
        print("  - python scripts/run_monthly.py   (full monthly run)")

    except Exception as e:
        print("✗ ERROR: API call failed")
        print(f"  Error: {str(e)}")
        print()
        print("Common issues:")
        print("  1. Invalid API key - get a new one from console.anthropic.com")
        print("  2. API key is for wrong service")
        print("  3. No API credits - check your account")
        print("  4. Account doesn't have API access enabled")
        print()
        print("  IMPORTANT: Claude Pro subscription ≠ API access")
        print("  You need a separate API key from:")
        print("  https://console.anthropic.com/settings/keys")


if __name__ == "__main__":
    test_api_key()
