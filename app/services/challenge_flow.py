"""In-memory conversation state for the /challenge Telegram flow.

Manages two-step flow: awaiting_prompt -> awaiting_confirm -> done.
Also handles per-user rate limiting for LLM challenge creation calls.

CRITICAL: This module stores state in process-local dicts. Do NOT deploy
with multiple uvicorn workers (--workers N > 1) — each worker maintains
independent state, causing session loss when requests are load-balanced.
For production scaling, replace in-memory state with Redis or
database-backed session storage.
"""

import time
import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Optional

from src.api.models import ChallengePromptParsed, ExerciseChallengeCreate

logger = logging.getLogger(__name__)

FLOW_TTL_SECONDS = 300  # 5 minutes
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour
RATE_LIMIT_MAX_CALLS = 10


@dataclass
class ChallengeFlowState:
    step: str  # "awaiting_prompt" or "awaiting_confirm"
    chat_id: int
    created_at: float = field(default_factory=time.time)
    parsed_data: Optional[ChallengePromptParsed] = None
    challenge_data: Optional[ExerciseChallengeCreate] = None


# Keyed by telegram_user_id
_flows: Dict[int, ChallengeFlowState] = {}
_flows_lock = Lock()

# Rate limit: telegram_user_id -> list of unix timestamps
_rate_limits: Dict[int, list] = {}
_rate_limits_lock = Lock()


def start_flow(telegram_user_id: int, chat_id: int) -> None:
    with _flows_lock:
        _flows[telegram_user_id] = ChallengeFlowState(
            step="awaiting_prompt",
            chat_id=chat_id,
        )


def get_flow(telegram_user_id: int) -> Optional[ChallengeFlowState]:
    with _flows_lock:
        state = _flows.get(telegram_user_id)
        if state is None:
            return None
        if _is_expired(state):
            _flows.pop(telegram_user_id, None)
            return None
        return state


def set_awaiting_confirm(
    telegram_user_id: int,
    parsed_data: ChallengePromptParsed,
    challenge_data: ExerciseChallengeCreate,
) -> None:
    with _flows_lock:
        state = _flows.get(telegram_user_id)
        if state is None:
            return
        state.step = "awaiting_confirm"
        state.parsed_data = parsed_data
        state.challenge_data = challenge_data
        state.created_at = time.time()  # Reset timer for confirmation


def clear_flow(telegram_user_id: int) -> None:
    with _flows_lock:
        _flows.pop(telegram_user_id, None)


def _is_expired(state: ChallengeFlowState) -> bool:
    return (time.time() - state.created_at) > FLOW_TTL_SECONDS


def check_rate_limit(telegram_user_id: int) -> bool:
    """Return True if the user is within rate limits, False if exceeded."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_limits_lock:
        timestamps = _rate_limits.get(telegram_user_id, [])
        timestamps = [t for t in timestamps if t > cutoff]
        _rate_limits[telegram_user_id] = timestamps
        return len(timestamps) < RATE_LIMIT_MAX_CALLS


def record_llm_call(telegram_user_id: int) -> None:
    """Record an LLM call for rate limiting."""
    with _rate_limits_lock:
        if telegram_user_id not in _rate_limits:
            _rate_limits[telegram_user_id] = []
        _rate_limits[telegram_user_id].append(time.time())
