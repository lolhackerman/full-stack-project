"""Text extraction and heuristic utilities."""

from __future__ import annotations

import base64
import re
from io import BytesIO
from typing import List

from flask import current_app
from pypdf import PdfReader

MAX_STORED_TEXT_LENGTH = 20_000


def safe_text_preview(b64_contents: str, limit: int = 1200) -> str:
    """Return a sanitized preview of uploaded text from base64-encoded contents."""
    try:
        decoded = base64.b64decode(b64_contents)
        text = decoded.decode("utf-8", errors="ignore")
    except Exception:  # pragma: no cover - best effort preview
        return ""

    cleaned = " ".join(text.split())
    return cleaned[:limit]


def make_text_excerpt(text: str, limit: int = 1200) -> str:
    """Normalize raw text and clamp it to a preview-friendly length."""
    if not text:
        return ""
    cleaned = " ".join(text.split())
    return cleaned[:limit]


def extract_pdf_text(raw_bytes: bytes) -> str:
    """Extract text from a PDF file while guarding against parser errors."""
    try:
        reader = PdfReader(BytesIO(raw_bytes))
    except Exception:
        current_app.logger.warning("Unable to initialize PdfReader for uploaded file", exc_info=True)
        return ""

    collected: List[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            current_app.logger.warning("Failed to extract text from a PDF page", exc_info=True)
            page_text = ""

        if page_text:
            collected.append(page_text)

    combined = "\n".join(collected).strip()
    if combined:
        return combined[:MAX_STORED_TEXT_LENGTH]
    return ""


def extract_text_from_upload(raw_bytes: bytes, filename: str, mimetype: str) -> str:
    """Extract structured text content from user uploads for downstream prompts."""
    lowered = (filename or "").lower()
    mime = (mimetype or "").lower()

    if mime == "application/pdf" or lowered.endswith(".pdf"):
        return extract_pdf_text(raw_bytes)

    return ""


def looks_like_job_description(text: str) -> bool:
    """Heuristically determine if the provided text appears to be a job description."""
    lowered = text.lower()
    job_signals = [
        "job description",
        "responsibilities",
        "requirements",
        "qualifications",
        "what you will do",
        "what you'll do",
        "about the role",
        "about you",
        "preferred skills",
    ]
    signal_count = sum(1 for term in job_signals if term in lowered)
    long_enough = len(lowered) > 250
    return signal_count >= 2 and long_enough


def extract_contact_info(resume_text: str) -> dict[str, str]:
    """Extract contact information from resume text."""
    if not resume_text:
        return {}
    
    contact_info = {}
    lines = resume_text.strip().split('\n')
    
    # Usually contact info is in the first 15 lines of a resume
    header_section = '\n'.join(lines[:15])
    
    # Extract email
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    email_match = email_pattern.search(header_section)
    if email_match:
        contact_info['email'] = email_match.group(0)
    
    # Extract phone number (various formats)
    phone_pattern = re.compile(
        r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    )
    phone_match = phone_pattern.search(header_section)
    if phone_match:
        contact_info['phone'] = phone_match.group(0).strip()
    
    # Extract name (typically first non-empty line)
    for line in lines[:5]:
        cleaned = line.strip()
        # Skip lines that look like contact info rather than names
        if cleaned and not any(x in cleaned.lower() for x in ['@', 'http', 'linkedin', 'github', '(']):
            # Check if it looks like a name (2-4 words, each capitalized)
            words = cleaned.split()
            if 2 <= len(words) <= 4 and all(word[0].isupper() for word in words if word):
                contact_info['name'] = cleaned
                break
    
    # Extract address, city, state, zip
    # Look for patterns like "City, State Zip" or "City, ST 12345"
    address_pattern = re.compile(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)'
    )
    address_match = address_pattern.search(header_section)
    if address_match:
        contact_info['city'] = address_match.group(1)
        contact_info['state'] = address_match.group(2)
        contact_info['zip'] = address_match.group(3)
    
    # Try to find street address (line with numbers and street keywords)
    street_keywords = ['street', 'st', 'avenue', 'ave', 'road', 'rd', 'drive', 'dr', 'lane', 'ln', 'way', 'court', 'ct']
    for line in lines[:10]:
        cleaned = line.strip().lower()
        if any(keyword in cleaned for keyword in street_keywords) and any(char.isdigit() for char in cleaned):
            contact_info['address'] = line.strip()
            break
    
    return contact_info


def format_contact_info_for_letter(contact_info: dict[str, str]) -> str:
    """Format extracted contact info into cover letter header format."""
    if not contact_info:
        return ""
    
    lines = []
    
    if 'name' in contact_info:
        lines.append(contact_info['name'])
    
    if 'address' in contact_info:
        lines.append(contact_info['address'])
    
    # Format city, state, zip on one line if available
    location_parts = []
    if 'city' in contact_info and 'state' in contact_info:
        location_parts.append(f"{contact_info['city']}, {contact_info['state']}")
        if 'zip' in contact_info:
            location_parts[0] += f" {contact_info['zip']}"
    
    if location_parts:
        lines.append(location_parts[0])
    
    if 'email' in contact_info:
        lines.append(contact_info['email'])
    
    if 'phone' in contact_info:
        lines.append(contact_info['phone'])
    
    return '\n'.join(lines)
