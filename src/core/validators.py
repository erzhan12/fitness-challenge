"""Validation helpers for core models and data."""


def validate_telegram_chat_id(chat_id: int) -> None:
    """Validate that chat_id is within valid Telegram chat ID range.
    
    Telegram chat IDs can be:
    - User IDs: positive integers
    - Group IDs: negative integers (for groups created before supergroups)
    - Supergroup/channel IDs: large negative integers (starting with -100)
    
    All valid Telegram chat IDs fall within the range -10^15 to 10^15.
    
    Args:
        chat_id: The chat ID to validate
        
    Raises:
        ValueError: If chat_id is outside valid range
    """
    if not (-10**15 <= chat_id <= 10**15):
        raise ValueError(
            f"Invalid chat_id: {chat_id}. "
            "Telegram chat IDs must be in range -10^15 to 10^15."
        )
