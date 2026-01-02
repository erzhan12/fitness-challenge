from app.services.deterministic_parser import get_numbers_from_message
from src.api.services import get_ordered_challenges

class TestMultiNumberParsing:
    def test_numbers_only_comma(self):
        text = "10, 20"
        counts, error = get_numbers_from_message(text)
        assert error is None
        assert counts == [10, 20]

    def test_numbers_only_space(self):
        text = "10 20 30"
        counts, error = get_numbers_from_message(text)
        assert error is None
        assert counts == [10, 20, 30]

    def test_numbers_only_parens(self):
        text = "(10 20)"
        counts, error = get_numbers_from_message(text)
        assert error is None
        assert counts == [10, 20]

    def test_mixed_content_fails(self):
        text = "10 pushups 20"
        counts, error = get_numbers_from_message(text)
        assert counts is None
        assert error is None # Not numbers-only, just invalid for this parser

    def test_decimals_fails(self):
        text = "10.5 20"
        counts, error = get_numbers_from_message(text)
        assert counts is None
        assert error == "Count must be greater than 0 and should be an integer."

    def test_single_number_returns_none(self):
        text = "10"
        counts, error = get_numbers_from_message(text)
        assert counts is None
        assert error is None # Not multi-number

class TestChallengeOrdering:
    def test_default_first(self):
        challenges = [
            {"id": 20, "is_default": False},
            {"id": 10, "is_default": True}, # Should be first
            {"id": 30, "is_default": False}
        ]
        ordered = get_ordered_challenges(challenges)
        ids = [c["id"] for c in ordered]
        assert ids == [10, 20, 30]

    def test_no_default_lowest_first(self):
        challenges = [
            {"id": 20, "is_default": False},
            {"id": 10, "is_default": False}, # Lowest
            {"id": 30, "is_default": False}
        ]
        ordered = get_ordered_challenges(challenges)
        ids = [c["id"] for c in ordered]
        assert ids == [10, 20, 30]

    def test_multiple_defaults_lowest_wins(self):
        challenges = [
            {"id": 20, "is_default": True},
            {"id": 10, "is_default": True}, # Lowest default
            {"id": 30, "is_default": False}
        ]
        ordered = get_ordered_challenges(challenges)
        ids = [c["id"] for c in ordered]
        assert ids == [10, 20, 30]

