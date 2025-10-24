"""Placeholder parsing utilities for cover letter templates."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

LETTER_DATE_PLACEHOLDER_PATTERN = re.compile(r"\[date\]", re.IGNORECASE)
PLACEHOLDER_TOKEN_PATTERN = re.compile(r"\[[^\[\]]+\]")
ALLOWED_PLACEHOLDERS = {"[date]"}


def ensure_cover_letter_date(text: str) -> str:
    """Ensure each cover letter has a leading date, replacing placeholders when needed."""
    from datetime import datetime

    date_line = datetime.now().strftime("%B %d, %Y")

    replaced, count = LETTER_DATE_PLACEHOLDER_PATTERN.subn(date_line, text)
    if count > 0:
        return replaced

    if not text.strip():
        return date_line

    return text


def find_unknown_placeholders(text: str) -> List[str]:
    """Return placeholder tokens that the system cannot currently fulfill."""
    tokens = PLACEHOLDER_TOKEN_PATTERN.findall(text or "")
    unknown: List[str] = []
    for token in tokens:
        if token.lower() in ALLOWED_PLACEHOLDERS:
            continue
        normalized = token.strip("[] ")
        if normalized:
            unknown.append(normalized)
    return sorted(set(unknown))


def collect_unknown_placeholder_tokens(text: str) -> Dict[str, List[str]]:
    """Map normalized placeholder keys to the literal tokens found in the text."""
    mapping: Dict[str, List[str]] = {}
    if not text:
        return mapping

    for token in PLACEHOLDER_TOKEN_PATTERN.findall(text):
        lowered = token.lower()
        if lowered in ALLOWED_PLACEHOLDERS:
            continue
        normalized = token.strip("[] ").strip().lower()
        if not normalized:
            continue
        mapping.setdefault(normalized, []).append(token)

    return mapping


def _match_placeholder_key(candidate: str, choices: List[str]) -> Optional[str]:
    candidate_lower = candidate.strip().lower()
    if not candidate_lower:
        return None

    for choice in choices:
        if candidate_lower == choice:
            return choice

    for choice in choices:
        if candidate_lower in choice:
            return choice

    for choice in choices:
        if choice in candidate_lower:
            return choice

    return None


def parse_placeholder_updates(
    message: str, available_keys: List[str], allow_fallback: bool = True
) -> Dict[str, str]:
    """Parse user instructions into placeholder replacements."""
    updates: Dict[str, str] = {}
    stripped = (message or "").strip()
    if not stripped or not available_keys:
        return updates

    segments = re.split(r"[;\n]", stripped)
    for raw in segments:
        line = raw.strip()
        if not line:
            continue
        match = re.match(r"(?i)^(?P<key>[A-Za-z][A-Za-z\s]{0,50})\s*[:=-]\s*(?P<value>.+)$", line)
        if not match:
            match = re.match(
                r"(?i)^(?:please\s+)?(?:set|update|change|use|replace)\s+(?P<key>[A-Za-z][A-Za-z\s]{0,50})\s+(?:to|as|=|is)\s*(?P<value>.+)$",
                line,
            )
            if not match:
                continue
        key = match.group("key").strip()
        value = match.group("value").strip()
        if not value:
            continue
        matched = _match_placeholder_key(key, available_keys)
        if matched:
            updates[matched] = value

    if updates:
        return updates

    if allow_fallback and len(available_keys) == 1:
        only_key = available_keys[0]
        updates[only_key] = stripped

    return updates


def apply_placeholder_updates(
    text: str, updates: Dict[str, str], placeholders: Dict[str, List[str]]
) -> Tuple[str, bool]:
    """Apply placeholder substitutions to a cover letter when a match is found."""
    if not updates:
        return text, False

    updated_text = text
    replaced = False

    for key, value in updates.items():
        tokens = placeholders.get(key)
        if not tokens:
            continue
        safe_value = value.strip()
        for token in tokens:
            if token in updated_text:
                updated_text = updated_text.replace(token, safe_value)
                replaced = True

    return updated_text, replaced
