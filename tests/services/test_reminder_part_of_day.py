"""Tests for hour-based reminder labels (header helper and LLM fallback)."""

from unittest.mock import patch

import pytest

from app.services.openai_service import (
    generate_reminder_motivation,
    reminder_part_of_day,
)


@pytest.mark.parametrize(
    "hour,expected",
    [
        (0, "Morning"),
        (9, "Morning"),
        (11, "Morning"),
        (12, "Afternoon"),
        (13, "Afternoon"),
        (17, "Afternoon"),
        (18, "Evening"),
        (21, "Evening"),
        (23, "Evening"),
    ],
)
def test_reminder_part_of_day(hour, expected):
    assert reminder_part_of_day(hour) == expected


def _fail(*args, **kwargs):
    raise RuntimeError("LLM down")


@pytest.mark.parametrize(
    "hour,prefix",
    [(9, "Morning reminder:"), (13, "Afternoon reminder:"), (21, "Evening reminder:")],
)
def test_fallback_uses_part_of_day(hour, prefix):
    with patch(
        "app.services.openai_service.client.chat.completions.create",
        side_effect=_fail,
    ):
        msg = generate_reminder_motivation(
            {"reminder_hour": hour, "left_challenges_count": 2}
        )
    assert msg.startswith(prefix)
    assert "2 challenges" in msg


def test_fallback_without_hour_is_neutral():
    with patch(
        "app.services.openai_service.client.chat.completions.create",
        side_effect=_fail,
    ):
        msg = generate_reminder_motivation({"left_challenges_count": 1})
    assert msg.startswith("Reminder:")
    assert "1 challenge " in msg
