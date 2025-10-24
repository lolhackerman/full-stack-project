"""Utilities for rendering PDFs using FPDF."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any, Dict, Optional

from fpdf import FPDF

# Optional hyphenation support
try:
    import pyphen
except Exception:  # pragma: no cover - optional dependency
    pyphen = None


def _pdf_bytes(pdf: FPDF) -> bytes:
    """Return raw PDF bytes from an FPDF instance across pyfpdf/fpdf2 versions."""
    raw = pdf.output(dest="S")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return raw.encode("latin-1")


CORE_FONT_ENCODING = "cp1252"


def _latin1_safe(text: str) -> str:
    """Best-effort conversion ensuring FPDF receives core-font friendly content."""
    if not text:
        return ""
    return text.encode(CORE_FONT_ENCODING, "replace").decode(CORE_FONT_ENCODING)


def _wrap_long_words_for_pdf(text: str, pdf: FPDF) -> str:
    """Insert breaks into extremely long tokens so FPDF can wrap them.

    FPDF raises when a single word/token is wider than the printable width.
    This helper splits such tokens into smaller chunks that fit the current
    font and printable area so `multi_cell` can render without error.
    """
    if not text:
        return ""

    max_w = pdf.w - pdf.l_margin - pdf.r_margin
    words = text.split(" ")
    out_words: list[str] = []

    for word in words:
        # If current word fits, keep as-is.
        if pdf.get_string_width(word) <= max_w:
            out_words.append(word)
            continue

        # Try hyphenation when available to produce nicer visual breaks.
        hyphenated = None
        if pyphen is not None:
            try:
                dic = pyphen.Pyphen(lang="en")
                pieces = dic.inserted(word).split("-")
                # Join with hyphens but still ensure each piece fits.
                reconstructed = "-".join(pieces)
                if pdf.get_string_width(reconstructed) <= max_w:
                    hyphenated = reconstructed
                else:
                    # keep pieces to be evaluated below
                    pieces_list = pieces
            except Exception:
                hyphenated = None

        if hyphenated:
            out_words.append(hyphenated)
            continue

        # If hyphenation didn't yield a fit or is unavailable, fall back to
        # splitting into smaller character chunks that fit the line.
        chunk = ""
        for ch in word:
            if pdf.get_string_width(chunk + ch) <= max_w:
                chunk += ch
            else:
                if chunk:
                    out_words.append(chunk)
                chunk = ch
        if chunk:
            out_words.append(chunk)

    return " ".join(out_words)


def render_cover_letter_pdf(record: Dict[str, Any]) -> bytes:
    """Render a styled cover letter PDF from the stored cover letter record."""
    pdf = FPDF()
    pdf.set_doc_option("core_fonts_encoding", CORE_FONT_ENCODING)
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(34, 197, 94)
    pdf.cell(0, 12, "Cover Letter", ln=True)
    pdf.set_draw_color(34, 197, 94)
    pdf.set_line_width(0.6)
    current_y = pdf.get_y()
    pdf.line(15, current_y, 195, current_y)
    pdf.ln(6)

    header_line = record.get("header_date")
    stored_name = (record.get("name") or "").strip().lower()
    normalized_header = (header_line or "").strip().lower()
    header_has_placeholder = "[" in (header_line or "") and "]" in (header_line or "")
    should_render_header = bool(header_line) and not header_has_placeholder
    if should_render_header and stored_name and normalized_header == stored_name:
        should_render_header = False

    if should_render_header:
        pdf.set_font("Helvetica", "I", 12)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 6, _latin1_safe(header_line), ln=True)
        pdf.ln(4)

    pdf.set_font("Helvetica", size=12)
    pdf.set_text_color(15, 23, 42)

    body_text = record.get("text", "") or ""
    if should_render_header and body_text:
        lines = body_text.splitlines()
        remaining_lines: list[str] = []
        removed_header = False
        for line in lines:
            stripped = line.strip()
            if not removed_header and stripped:
                if stripped.lower() == normalized_header:
                    removed_header = True
                    continue
            remaining_lines.append(line)
        body_text = "\n".join(remaining_lines).lstrip()

    paragraphs = [block.strip() for block in body_text.split("\n\n") if block.strip()]
    if not paragraphs:
        paragraphs = [body_text.strip()]

    for paragraph in paragraphs:
        lines = [line.rstrip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        for line in lines:
            safe = _latin1_safe(line)
            safe = _wrap_long_words_for_pdf(safe, pdf)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 6, safe, align='L')
        pdf.ln(3)

    return _pdf_bytes(pdf)


def _first_nonempty_line(text: str) -> Optional[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def render_resume_pdf(record: Dict[str, Any]) -> Optional[bytes]:
    """Render a pseudo-styled resume PDF when enough text content is available."""
    text = record.get("text")
    if not text:
        contents = record.get("contents")
        if contents:
            try:
                decoded = base64.b64decode(contents)
                text = decoded.decode("utf-8", errors="ignore")
            except Exception:
                text = None

    if not text:
        return None

    text = text.strip()
    if not text:
        return None

    primary_heading = _first_nonempty_line(text) or (record.get("name") or "Resume")
    remaining_lines = text.splitlines()
    if remaining_lines and remaining_lines[0].strip().lower() == primary_heading.strip().lower():
        remaining_lines = remaining_lines[1:]

    content = "\n".join(remaining_lines).strip()

    pdf = FPDF()
    pdf.set_doc_option("core_fonts_encoding", CORE_FONT_ENCODING)
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(59, 130, 246)
    pdf.cell(0, 12, _latin1_safe(primary_heading), ln=True)

    subtitle = record.get("name") or "Generated resume"
    pdf.set_font("Helvetica", size=11)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, _latin1_safe(subtitle), ln=True)
    pdf.ln(6)
    printable_w = pdf.w - pdf.l_margin - pdf.r_margin

    sections = [section.strip() for section in content.split("\n\n") if section.strip()]
    if not sections and content:
        sections = [content]

    for section in sections:
        lines = [line.strip() for line in section.splitlines() if line.strip()]
        if not lines:
            continue
        header_candidate = lines[0]
        remaining = lines[1:]
        is_header = (header_candidate.isupper() or header_candidate.endswith(":")) and remaining

        if is_header:
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(34, 197, 94)
            pdf.cell(0, 8, _latin1_safe(header_candidate.rstrip(":")), ln=True)
            pdf.set_font("Helvetica", size=12)
            pdf.set_text_color(15, 23, 42)
        else:
            remaining = lines

        for line in remaining:
            if line.startswith("-") or line.startswith("*"):
                bullet_text = line.lstrip("-*").strip()
                safe = _latin1_safe(f"- {bullet_text}")
                safe = _wrap_long_words_for_pdf(safe, pdf)
                pdf.multi_cell(printable_w, 6, safe, 0, 'L')
            else:
                safe = _latin1_safe(line)
                safe = _wrap_long_words_for_pdf(safe, pdf)
                pdf.multi_cell(printable_w, 6, safe, 0, 'L')
        pdf.ln(2)

    uploaded_at = record.get("uploaded_at")
    if uploaded_at:
        pdf.set_text_color(148, 163, 184)
        pdf.set_font("Helvetica", size=10)
        timestamp = datetime.fromtimestamp(int(uploaded_at) / 1000).strftime("%B %d, %Y %I:%M %p")
        pdf.cell(0, 5, _latin1_safe(f"Source: {record.get('name')} uploaded on {timestamp}"), ln=True)

    return _pdf_bytes(pdf)
