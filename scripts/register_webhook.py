import asyncio
import os
import logging
from dotenv import load_dotenv
from app.services.telegram_client import TelegramClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def set_webhook():
    """
    Sets the Telegram webhook for the bot.
    """
    # Load environment variables (for local dev usage if needed, though this script is likely run locally)
    load_dotenv()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    webhook_host = os.getenv("WEBHOOK_HOST", "fitnesschallenge.habitreward.org")
    secret_token = os.getenv("TELEGRAM_SECRET_TOKEN")

    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is missing.")
        return
    
    if not secret_token:
        logger.warning("TELEGRAM_SECRET_TOKEN is missing. It is highly recommended for security.")

    webhook_url = f"https://{webhook_host}/telegram/webhook"
    
    logger.info(f"Setting webhook to: {webhook_url}")

    # Initialize simple client (assuming TelegramClient has methods we can reuse or we use httpx directly)
    # Since TelegramClient in codebase might be specific, let's use a direct call for this utility script
    # to avoid complex dependency injection if not needed.
    
    import httpx
    
    api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    
    params = {
        "url": webhook_url,
        "drop_pending_updates": True,
        "secret_token": secret_token
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_url, json=params)
            response.raise_for_status()
            result = response.json()
            
            if result.get("ok"):
                logger.info("Webhook set successfully!")
                logger.info(f"Response: {result}")
            else:
                logger.error(f"Failed to set webhook: {result}")
                
        except Exception as e:
            logger.error(f"Error setting webhook: {str(e)}")

if __name__ == "__main__":
    asyncio.run(set_webhook())

