#!/usr/bin/env python
"""Test script to verify webhook endpoint is working.

This script sends a test request to the webhook endpoint to verify
it's accessible and responding correctly.

Usage:
    python scripts/check_webhook.py                          # Test localhost
    python scripts/check_webhook.py https://your-ngrok-url   # Test ngrok URL
"""

import sys
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_webhook_endpoint(base_url="http://localhost:8000"):
    """Test the webhook endpoint.

    Args:
        base_url (str): Base URL to test (default: http://localhost:8000)
    """
    webhook_url = f"{base_url}/telegram/webhook"

    print("\n" + "=" * 60)
    print("🧪 WEBHOOK ENDPOINT TEST")
    print("=" * 60)
    print(f"Testing: {webhook_url}")
    print("=" * 60 + "\n")

    # Test 1: GET request (should fail with 400)
    print("Test 1: GET request (should return 400 or 405)")
    print("-" * 60)
    try:
        response = requests.get(webhook_url, timeout=5)
        status_code = response.status_code

        if status_code in [400, 405]:
            print(f"✅ PASS - Got expected {status_code} response")
            print(f"   Response: {response.text[:100]}")
        else:
            print(f"⚠️ UNEXPECTED - Got {status_code} instead of 400/405")
            print(f"   Response: {response.text[:100]}")
    except requests.exceptions.ConnectionError:
        print("❌ FAIL - Connection refused")
        print("   Is the server running?")
        print("   Start with: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
        return False
    except requests.exceptions.Timeout:
        print("❌ FAIL - Request timeout")
        return False
    except Exception as e:
        print(f"❌ FAIL - Unexpected error: {e}")
        return False

    print()

    # Test 2: POST request with invalid JSON (should fail with 400)
    print("Test 2: POST request with invalid JSON (should return 400)")
    print("-" * 60)
    try:
        response = requests.post(
            webhook_url,
            data="invalid json",
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        status_code = response.status_code

        if status_code == 400:
            print("✅ PASS - Got expected 400 response")
            print(f"   Response: {response.text[:100]}")
        else:
            print(f"⚠️ UNEXPECTED - Got {status_code} instead of 400")
            print(f"   Response: {response.text[:100]}")
    except Exception as e:
        print(f"❌ FAIL - Unexpected error: {e}")
        return False

    print()

    # Test 3: POST request with minimal valid Telegram update
    print("Test 3: POST request with minimal valid Telegram update structure")
    print("-" * 60)
    try:
        # Minimal valid Telegram update structure
        test_update = {
            "update_id": 999999999,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456789,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser",
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Test",
                    "username": "testuser",
                    "type": "private",
                },
                "date": 1234567890,
                "text": "/test",
            },
        }

        response = requests.post(webhook_url, json=test_update, timeout=5)
        status_code = response.status_code

        if status_code == 200:
            print("✅ PASS - Got 200 OK response")
            print(f"   Response: {response.text}")
            print("   Note: Bot will process this update if user exists in DB")
        else:
            print(f"⚠️ UNEXPECTED - Got {status_code} instead of 200")
            print(f"   Response: {response.text[:100]}")
    except Exception as e:
        print(f"❌ FAIL - Unexpected error: {e}")
        return False

    print()
    print("=" * 60)
    print("✅ WEBHOOK ENDPOINT TESTS COMPLETE")
    print("=" * 60)
    print()

    return True


def test_ngrok_tunnel():
    """Try to detect and test ngrok tunnel."""
    print("Attempting to detect ngrok tunnel...")
    print("-" * 60)

    try:
        # Query ngrok API for tunnels
        ngrok_api = "http://127.0.0.1:4040/api/tunnels"
        response = requests.get(ngrok_api, timeout=2)

        if response.status_code == 200:
            data = response.json()
            tunnels = data.get("tunnels", [])

            if tunnels:
                for tunnel in tunnels:
                    public_url = tunnel.get("public_url", "")
                    if public_url.startswith("https://"):
                        print(f"✅ Found ngrok tunnel: {public_url}")
                        return public_url

        print("⚠️ ngrok not detected (is it running?)")
        return None

    except requests.exceptions.ConnectionError:
        print("⚠️ ngrok API not accessible (is ngrok running?)")
        return None
    except Exception as e:
        print(f"⚠️ Error detecting ngrok: {e}")
        return None


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("🤖 TELEGRAM WEBHOOK ENDPOINT TESTER")
    print("=" * 60 + "\n")

    # Check if URL provided as argument
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        # Remove trailing slash
        test_url = test_url.rstrip("/")
        # Remove /telegram/webhook if already included
        test_url = test_url.replace("/telegram/webhook", "")

        print(f"Testing provided URL: {test_url}\n")
        success = test_webhook_endpoint(test_url)
    else:
        # Test localhost
        print("Testing localhost (default)\n")
        success = test_webhook_endpoint()

        if success:
            # Try to detect and test ngrok
            print("\n")
            ngrok_url = test_ngrok_tunnel()
            if ngrok_url:
                print("\nTesting ngrok tunnel...\n")
                test_webhook_endpoint(ngrok_url)

    print("\nℹ️ Usage:")
    print("  Test localhost:      python scripts/check_webhook.py")
    print("  Test specific URL:   python scripts/check_webhook.py https://your-url.com")
    print(
        "  Test ngrok:          python scripts/check_webhook.py https://abc123.ngrok-free.app"
    )
    print("\nNote: FastAPI webhook endpoint is at /telegram/webhook")
    print()


if __name__ == "__main__":
    main()
