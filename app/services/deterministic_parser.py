import re
from typing import Dict, List, Optional, Sequence, Tuple

from app.models import ExerciseEntry, ExerciseType, ParseResult


_TOKEN_RE = re.compile(r"\d+|[A-Za-z][A-Za-z'\\-]*")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

_CONNECTORS = {
    "and",
    "or",
    "then",
    "plus",
    "&",
    "+",
}


def _is_valid_count(count: int) -> bool:
    """Validate that count is a positive integer greater than 0."""
    return count > 0


def _normalize_token(token: str) -> str:
    return _NON_ALNUM_RE.sub("", token.lower().strip())


def _singularize(token: str) -> str:
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith("es") and len(token) > 2:
        return token[:-2]
    if token.endswith("s") and len(token) > 1:
        return token[:-1]
    return token


def _pluralize(token: str) -> str:
    if not token:
        return token
    if token.endswith("y") and len(token) > 1:
        return token[:-1] + "ies"
    if token.endswith("s"):
        return token
    return token + "s"


def _alias_string_variants(raw: str) -> List[str]:
    raw = raw.strip().lower()
    if not raw:
        return []

    variants = [raw]
    if "-" in raw:
        variants.append(raw.replace("-", " "))
        variants.append(raw.replace("-", ""))
    if " " in raw:
        variants.append(raw.replace(" ", "-"))
        variants.append(raw.replace(" ", ""))

    if raw.endswith("s") and len(raw) > 1:
        variants.append(raw[:-1])
        if "-" in raw:
            variants.append(raw[:-1].replace("-", " "))
            variants.append(raw[:-1].replace("-", ""))
        if " " in raw:
            variants.append(raw[:-1].replace(" ", "-"))
            variants.append(raw[:-1].replace(" ", ""))
    else:
        variants.append(raw + "s")

    # De-dupe while preserving order
    return list(dict.fromkeys(v for v in variants if v))


def populate_exercise_type_aliases(exercise_types: Sequence[ExerciseType]) -> None:
    """Ensure aliases contain common punctuation/singular/plural variants.

    This mutates the passed-in ExerciseType models in-place.
    """
    for etype in exercise_types:
        raw_aliases: List[str] = []
        raw_aliases.extend(_alias_string_variants(etype.name))
        raw_aliases.extend(_alias_string_variants(etype.display_name))
        for alias in etype.aliases or []:
            raw_aliases.extend(_alias_string_variants(alias))

        # Keep existing aliases first; then add derived ones (unique, case-insensitive)
        seen = {a.strip().lower() for a in (etype.aliases or []) if a.strip()}
        merged: List[str] = list(etype.aliases or [])
        for alias in raw_aliases:
            key = alias.strip().lower()
            if key and key not in seen:
                seen.add(key)
                merged.append(alias)
        etype.aliases = merged


def _build_match_index(
    exercise_types: Sequence[ExerciseType],
) -> Dict[str, List[ExerciseType]]:
    """Build index for matching exercise names and aliases.

    Uses existing aliases if present, otherwise adds simple singular/plural of name.
    """
    index: Dict[str, Dict[int, ExerciseType]] = {}
    for etype in exercise_types:
        # Start with name and display_name
        sources = [etype.name, etype.display_name]

        # Use existing aliases or add simple variant
        if etype.aliases:
            sources.extend(etype.aliases)
        else:
            # If no aliases, add simple plural/singular of name
            name = etype.name.lower().strip()
            if name.endswith('s') and len(name) > 1:
                sources.append(name[:-1])
            else:
                sources.append(name + 's')

        # Normalize each source and create singular/plural variants for matching
        for source in sources:
            base = _normalize_token(source)
            if not base:
                continue
            for variant in {base, _singularize(base), _pluralize(base)}:
                if not variant:
                    continue
                index.setdefault(variant, {})[etype.id] = etype
    return {k: list(v.values()) for k, v in index.items()}


def _parse_number_word_pairs(tokens: List[str]) -> Optional[List[Tuple[int, str]]]:
    if not tokens:
        return None

    if len(tokens) == 1 and tokens[0].isdigit():
        count = int(tokens[0])
        if not _is_valid_count(count):
            return None
        return [(count, "")]

    pairs: List[Tuple[int, str]] = []
    i = 0
    while i < len(tokens):
        if tokens[i] in _CONNECTORS:
            return None
        if not tokens[i].isdigit():
            return None

        count = int(tokens[i])
        if not _is_valid_count(count):
            return None
        i += 1

        words: List[str] = []
        while i < len(tokens) and not tokens[i].isdigit() and tokens[i] not in _CONNECTORS:
            words.append(tokens[i])
            i += 1

        if not words:
            return None

        pairs.append((count, " ".join(words)))

        if i < len(tokens) and tokens[i] in _CONNECTORS:
            i += 1
            if i == len(tokens):
                return None

    return pairs


def try_deterministic_parse_workout_message(
    text: str, exercise_types: Sequence[ExerciseType]
) -> Optional[ParseResult]:
    """Try parsing simple workout inputs without calling the LLM.

    Supported deterministic formats:
    - "<number>" (only when exactly one exercise type is active)
    - "<number> <word>" (or multiple pairs like "20 pushups and 30 squats")

    Returns:
        ParseResult if parsing succeeded unambiguously, otherwise None (caller should fall back).
    """
    normalized_text = re.sub(r"(?<=\d),(?=\d)", "", text.strip())
    if not normalized_text:
        return None

    # Check for decimal numbers (e.g., 0.1, 0.01, .5) before tokenizing
    if re.search(r'(\b\d*\.\d+\b|^\.\d+)', normalized_text):
        return ParseResult(
            entries=[],
            is_valid=False,
            error_reason="Count must be greater than 0 and should be an integer."
        )

    tokens = _TOKEN_RE.findall(normalized_text.lower())

    # Check if input looks like it contains a number that needs validation
    has_number = any(token.isdigit() for token in tokens)
    if has_number:
        # Try to extract the number to check if it's invalid
        for token in tokens:
            if token.isdigit():
                num = int(token)
                if num <= 0:
                    # Return an error result instead of None to avoid LLM fallback
                    return ParseResult(
                        entries=[],
                        is_valid=False,
                        error_reason="Count must be greater than 0 and should be an integer."
                    )

    pairs = _parse_number_word_pairs(tokens)
    if not pairs:
        return None

    # Number-only: only deterministic when exactly one active exercise type is in scope.
    if len(pairs) == 1 and pairs[0][1] == "":
        if len(exercise_types) != 1:
            return None
        etype = exercise_types[0]
        count = pairs[0][0]
        duration_seconds = count * 60 if etype.unit.lower() in {"minute", "minutes"} else None
        return ParseResult(
            entries=[
                ExerciseEntry(
                    exercise_type_name=etype.name,
                    count=count,
                    duration_seconds=duration_seconds,
                    notes=None,
                    confidence=1.0,
                )
            ],
            is_valid=True,
            error_reason=None,
        )

    index = _build_match_index(exercise_types)

    ordered_names: List[str] = []
    counts_by_name: Dict[str, int] = {}
    etype_by_name: Dict[str, ExerciseType] = {}

    for count, phrase in pairs:
        key = _normalize_token(phrase)
        if not key:
            return None

        matches = index.get(key, [])
        # Deterministic parsing only succeeds when matching is unambiguous.
        if len(matches) != 1:
            return None

        etype = matches[0]
        if etype.name not in counts_by_name:
            ordered_names.append(etype.name)
            counts_by_name[etype.name] = 0
            etype_by_name[etype.name] = etype
        counts_by_name[etype.name] += count

    entries: List[ExerciseEntry] = []
    for name in ordered_names:
        etype = etype_by_name[name]
        count = counts_by_name[name]
        duration_seconds = count * 60 if etype.unit.lower() in {"minute", "minutes"} else None
        entries.append(
            ExerciseEntry(
                exercise_type_name=name,
                count=count,
                duration_seconds=duration_seconds,
                notes=None,
                confidence=1.0,
            )
        )

    return ParseResult(entries=entries, is_valid=True, error_reason=None)
