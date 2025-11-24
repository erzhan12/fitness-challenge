#!/usr/bin/env python
"""Script to set Telegram webhook.

This script sets the Telegram webhook URL for the bot using the configuration
from the .env file. It also provides webhook status information.

Usage:
    python scripts/set_webhook.py              # Set webhook
    python scripts/set_webhook.py --delete     # Delete webhook
    python scripts/set_webhook.py --info       # Show webhook info only
"""

import sys
import argparse
from pathlib import Path
from app.config import settings
import httpx

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_webhook_info():
    """Get current webhook information from Telegram.

    Returns:
        dict: Webhook information from Telegram API
    """
    token = settings.TELEGRAM_BOT_TOKEN
    api_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"

    print("[DEBUG] Getting webhook info...")
    print(f"[DEBUG] API URL: {api_url}")
    print(f"[DEBUG] Token (first 10 chars): {token[:10]}...")

    try:
        print("[DEBUG] Sending GET request...")
        response = httpx.get(api_url, timeout=10)
        print(f"[DEBUG] Response status: {response.status_code}")
        print(f"[DEBUG] Response headers: {dict(response.headers)}")

        response.raise_for_status()
        info = response.json()
        print(f"[DEBUG] Response JSON: {info}")

        if info.get("ok"):
            print("[DEBUG] ✅ Successfully retrieved webhook info")
            return info["result"]
        else:
            print(f"❌ Failed to get webhook info: {info.get('description')}")
            print(f"[DEBUG] Full error response: {info}")
            return None
    except httpx.RequestError as e:
        print(f"❌ Network error getting webhook info: {e}")
        print(f"[DEBUG] Exception type: {type(e).__name__}")
        print(f"[DEBUG] Exception details: {repr(e)}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print(f"[DEBUG] Exception type: {type(e).__name__}")
        print(f"[DEBUG] Exception details: {repr(e)}")
        return None


def display_webhook_info(info):
    """Display webhook information in a formatted way.

    Args:
        info (dict): Webhook information from Telegram API
    """
    if not info:
        return

    print("\n" + "=" * 60)
    print("📊 CURRENT WEBHOOK INFO")
    print("=" * 60)

    url = info.get("url", "")
    if url:
        print(f"URL: {url}")
        print("Status: ✅ Webhook is SET")
    else:
        print("URL: (not set)")
        print("Status: ⚠️ No webhook configured (using polling mode)")

    print(f"Pending updates: {info.get('pending_update_count', 0)}")
    print(f"Max connections: {info.get('max_connections', 'N/A')}")

    if info.get("ip_address"):
        print(f"IP address: {info.get('ip_address')}")

    if info.get("last_error_date"):
        print("\n⚠️ LAST ERROR:")
        print(f"   Message: {info.get('last_error_message', 'Unknown')}")
        print(f"   Date: {info.get('last_error_date')}")

    if info.get("last_synchronization_error_date"):
        print("\n⚠️ LAST SYNC ERROR:")
        print(f"   Date: {info.get('last_synchronization_error_date')}")

    print("=" * 60 + "\n")


def set_webhook(drop_pending_updates=False):
    """Set Telegram webhook using bot token and webhook URL from settings.

    Args:
        drop_pending_updates (bool): Whether to drop pending updates when setting webhook

    Returns:
        bool: True if webhook was set successfully, False otherwise
    """
    print("[DEBUG] === Setting webhook ===")
    print(f"[DEBUG] drop_pending_updates: {drop_pending_updates}")

    token = settings.TELEGRAM_BOT_TOKEN
    webhook_url = settings.TELEGRAM_WEBHOOK_URL

    print(f"[DEBUG] Token loaded: {token[:10]}... (length: {len(token)})")
    print(f"[DEBUG] Webhook URL from config: {webhook_url}")

    # Validate configuration
    if not webhook_url:
        print("\n❌ ERROR: TELEGRAM_WEBHOOK_URL not set in .env file")
        print("\nTo set webhook, add this to your .env file:")
        print(
            "TELEGRAM_WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app/telegram/webhook"
        )
        print("\nExample:")
        print("TELEGRAM_WEBHOOK_URL=https://abc123.ngrok-free.app/telegram/webhook")
        return False

    if not webhook_url.startswith("https://"):
        print("\n❌ ERROR: Webhook URL must use HTTPS")
        print(f"Current URL: {webhook_url}")
        print("[DEBUG] URL scheme check failed")
        return False

    print("[DEBUG] ✅ HTTPS validation passed")

    if "/telegram/webhook" not in webhook_url:
        print("\n⚠️ WARNING: Webhook URL should end with /telegram/webhook")
        print(f"Current URL: {webhook_url}")
        print("\nExpected format: https://your-domain.com/telegram/webhook")
        response = input("\nContinue anyway? (y/N): ")
        if response.lower() != "y":
            print("[DEBUG] User cancelled operation")
            return False
        print("[DEBUG] User confirmed to continue despite URL format warning")
    else:
        print("[DEBUG] ✅ URL path validation passed")

    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    print(f"[DEBUG] API URL: {api_url}")

    data = {"url": webhook_url}
    print(f"[DEBUG] Initial data payload: {data}")

    # Add secret token for webhook verification (security feature)
    if settings.TELEGRAM_SECRET_TOKEN:
        data["secret_token"] = settings.TELEGRAM_SECRET_TOKEN
        print(
            f"[DEBUG] Secret token added (length: {len(settings.TELEGRAM_SECRET_TOKEN)})"
        )
    else:
        print("[DEBUG] ⚠️ No secret token configured")

    if drop_pending_updates:
        data["drop_pending_updates"] = True
        print("[DEBUG] Drop pending updates enabled")

    print(f"[DEBUG] Final data payload: {data}")

    print("\n" + "=" * 60)
    print("🔧 SETTING WEBHOOK")
    print("=" * 60)
    print(f"Webhook URL: {webhook_url}")
    if settings.TELEGRAM_SECRET_TOKEN:
        print("Secret token: ✅ Enabled (for security)")
    if drop_pending_updates:
        print("Drop pending updates: Yes")
    print("=" * 60)

    try:
        print("[DEBUG] Sending POST request to Telegram API...")
        print(f"[DEBUG] Request URL: {api_url}")
        print(f"[DEBUG] Request data: {data}")

        response = httpx.post(api_url, data=data, timeout=10)

        print("[DEBUG] Response received")
        print(f"[DEBUG] Status code: {response.status_code}")
        print(f"[DEBUG] Response headers: {dict(response.headers)}")
        print(f"[DEBUG] Response text: {response.text}")

        response.raise_for_status()
        result = response.json()
        print(f"[DEBUG] Response JSON parsed: {result}")

        if result.get("ok"):
            print("\n✅ Webhook set successfully!\n")
            print("[DEBUG] ✅ Operation completed successfully")
            return True
        else:
            print(f"\n❌ Failed to set webhook: {result.get('description')}\n")
            print("[DEBUG] ❌ Telegram API returned ok=False")
            print(f"[DEBUG] Error code: {result.get('error_code', 'N/A')}")
            print(f"[DEBUG] Full response: {result}")
            return False
    except httpx.HTTPStatusError as e:
        print(f"\n❌ HTTP error setting webhook: {e}\n")
        print(f"[DEBUG] Status code: {e.response.status_code}")
        print(f"[DEBUG] Response text: {e.response.text}")
        return False
    except httpx.RequestError as e:
        print(f"\n❌ Network error setting webhook: {e}\n")
        print(f"[DEBUG] Exception type: {type(e).__name__}")
        print(f"[DEBUG] Exception details: {repr(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        print(f"[DEBUG] Exception type: {type(e).__name__}")
        print(f"[DEBUG] Exception details: {repr(e)}")
        import traceback

        print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
        return False


def delete_webhook(drop_pending_updates=False):
    """Delete the current webhook (switches bot to polling mode).

    Args:
        drop_pending_updates (bool): Whether to drop pending updates when deleting webhook

    Returns:
        bool: True if webhook was deleted successfully, False otherwise
    """
    print("[DEBUG] === Deleting webhook ===")
    print(f"[DEBUG] drop_pending_updates: {drop_pending_updates}")

    token = settings.TELEGRAM_BOT_TOKEN
    api_url = f"https://api.telegram.org/bot{token}/deleteWebhook"

    print(f"[DEBUG] Token loaded: {token[:10]}... (length: {len(token)})")
    print(f"[DEBUG] API URL: {api_url}")

    data = {}
    if drop_pending_updates:
        data["drop_pending_updates"] = True
        print("[DEBUG] Drop pending updates enabled")

    print(f"[DEBUG] Request data: {data}")

    print("\n" + "=" * 60)
    print("🗑️ DELETING WEBHOOK")
    print("=" * 60)
    if drop_pending_updates:
        print("Drop pending updates: Yes")
    print("This will switch the bot to polling mode.")
    print("=" * 60)

    try:
        print("[DEBUG] Sending POST request to Telegram API...")
        print(f"[DEBUG] Request URL: {api_url}")
        print(f"[DEBUG] Request data: {data}")

        response = httpx.post(api_url, data=data, timeout=10)

        print("[DEBUG] Response received")
        print(f"[DEBUG] Status code: {response.status_code}")
        print(f"[DEBUG] Response headers: {dict(response.headers)}")
        print(f"[DEBUG] Response text: {response.text}")

        response.raise_for_status()
        result = response.json()
        print(f"[DEBUG] Response JSON parsed: {result}")

        if result.get("ok"):
            print("\n✅ Webhook deleted successfully!\n")
            print("Bot is now in polling mode.")
            print("Note: This FastAPI app uses webhook mode. To switch to polling,")
            print("you would need to implement a polling mechanism.\n")
            print("[DEBUG] ✅ Operation completed successfully")
            return True
        else:
            print(f"\n❌ Failed to delete webhook: {result.get('description')}\n")
            print("[DEBUG] ❌ Telegram API returned ok=False")
            print(f"[DEBUG] Error code: {result.get('error_code', 'N/A')}")
            print(f"[DEBUG] Full response: {result}")
            return False
    except httpx.HTTPStatusError as e:
        print(f"\n❌ HTTP error deleting webhook: {e}\n")
        print(f"[DEBUG] Status code: {e.response.status_code}")
        print(f"[DEBUG] Response text: {e.response.text}")
        return False
    except httpx.RequestError as e:
        print(f"\n❌ Network error deleting webhook: {e}\n")
        print(f"[DEBUG] Exception type: {type(e).__name__}")
        print(f"[DEBUG] Exception details: {repr(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        print(f"[DEBUG] Exception type: {type(e).__name__}")
        print(f"[DEBUG] Exception details: {repr(e)}")
        import traceback

        print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
        return False


def validate_configuration():
    """Validate that required configuration is present.

    Returns:
        bool: True if configuration is valid, False otherwise
    """
    print("[DEBUG] === Validating configuration ===")

    issues = []

    print("[DEBUG] Checking TELEGRAM_BOT_TOKEN...")
    if not settings.TELEGRAM_BOT_TOKEN:
        print("[DEBUG] ❌ TELEGRAM_BOT_TOKEN is empty")
        issues.append("TELEGRAM_BOT_TOKEN is not set or using default test value")
    elif settings.TELEGRAM_BOT_TOKEN == "test_token":
        print("[DEBUG] ❌ TELEGRAM_BOT_TOKEN is using default test value")
        issues.append("TELEGRAM_BOT_TOKEN is not set or using default test value")
    else:
        print(
            f"[DEBUG] ✅ TELEGRAM_BOT_TOKEN is set (length: {len(settings.TELEGRAM_BOT_TOKEN)})"
        )

    print("[DEBUG] Checking TELEGRAM_WEBHOOK_URL...")
    if settings.TELEGRAM_WEBHOOK_URL:
        print(
            f"[DEBUG] ✅ TELEGRAM_WEBHOOK_URL is set: {settings.TELEGRAM_WEBHOOK_URL}"
        )
    else:
        print("[DEBUG] ⚠️ TELEGRAM_WEBHOOK_URL is not set (optional for --info)")

    print("[DEBUG] Checking TELEGRAM_SECRET_TOKEN...")
    if settings.TELEGRAM_SECRET_TOKEN:
        print(
            f"[DEBUG] ✅ TELEGRAM_SECRET_TOKEN is set (length: {len(settings.TELEGRAM_SECRET_TOKEN)})"
        )
    else:
        print("[DEBUG] ⚠️ TELEGRAM_SECRET_TOKEN is not set (optional)")

    if issues:
        print("\n❌ CONFIGURATION ISSUES:")
        for issue in issues:
            print(f"   - {issue}")
        print(
            "\nPlease check your .env file and ensure all required variables are set.\n"
        )
        print("[DEBUG] ❌ Configuration validation failed")
        return False

    print("[DEBUG] ✅ Configuration validation passed")
    return True


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Manage Telegram webhook configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/set_webhook.py                    # Set webhook
  python scripts/set_webhook.py --info             # Show webhook info
  python scripts/set_webhook.py --delete           # Delete webhook
  python scripts/set_webhook.py --drop-pending     # Set webhook and drop pending updates
  python scripts/set_webhook.py --delete --drop-pending  # Delete and drop pending
        """,
    )

    parser.add_argument(
        "--info",
        action="store_true",
        help="Show current webhook information only (no changes)",
    )

    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the webhook (switch to polling mode)",
    )

    parser.add_argument(
        "--drop-pending",
        action="store_true",
        help="Drop pending updates when setting/deleting webhook",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🤖 TELEGRAM WEBHOOK MANAGER")
    print("=" * 60)
    print("Project: fitness-challenge")
    print("=" * 60 + "\n")

    print("[DEBUG] === Script started ===")
    print(f"[DEBUG] Arguments: {vars(args)}")
    print(f"[DEBUG] Project root: {project_root}")
    print(f"[DEBUG] Python version: {sys.version}")

    # Validate configuration
    if not validate_configuration():
        print("[DEBUG] Exiting due to configuration validation failure")
        sys.exit(1)

    # Get and display current webhook info
    print("[DEBUG] Fetching current webhook info...")
    current_info = get_webhook_info()
    print(f"[DEBUG] Current webhook info: {current_info}")

    # If --info flag, just show info and exit
    if args.info:
        display_webhook_info(current_info)
        sys.exit(0)

    # Show current state before making changes
    if current_info:
        current_url = current_info.get("url", "")
        if current_url:
            print(f"Current webhook: {current_url}")
        else:
            print("Current mode: Polling (no webhook set)")
        print()

    # Perform action
    success = False
    print(f"[DEBUG] Performing action: {'delete' if args.delete else 'set'}")

    if args.delete:
        success = delete_webhook(drop_pending_updates=args.drop_pending)
    else:
        success = set_webhook(drop_pending_updates=args.drop_pending)

    print(f"[DEBUG] Action result: {'success' if success else 'failed'}")

    # Show updated webhook info
    if success:
        print("[DEBUG] Fetching updated webhook info...")
        updated_info = get_webhook_info()
        print(f"[DEBUG] Updated webhook info: {updated_info}")
        display_webhook_info(updated_info)
    else:
        print("[DEBUG] Skipping webhook info fetch due to failed operation")

    print("[DEBUG] === Script finished ===")
    print(f"[DEBUG] Exit code: {0 if success else 1}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
