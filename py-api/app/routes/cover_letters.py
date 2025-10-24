"""/api/cover-letters endpoints for export flows."""

from __future__ import annotations

from io import BytesIO

from flask import Blueprint, jsonify, send_file

from app.services.pdf_service import render_cover_letter_pdf
from app.storage import cover_letters
from app.utils.auth import require_session
from app.utils.placeholders import find_unknown_placeholders

bp = Blueprint("cover_letters", __name__, url_prefix="/api/cover-letters")


@bp.post("/<letter_id>/pdf")
def generate_cover_letter_pdf(letter_id: str):
    """Return a downloadable PDF for an existing cover letter draft."""
    session, error_response = require_session()
    if error_response is not None:
        return error_response

    record = cover_letters.get(letter_id)
    if not record or record["profile_id"] != session["profile_id"]:
        return jsonify(error="Cover letter not found."), 404

    missing_fields = find_unknown_placeholders(record["text"])
    if missing_fields:
        missing_csv = ", ".join(missing_fields)
        return (
            jsonify(
                error="cover_letter_missing_info",
                message=f"Please provide the following details before downloading a PDF: {missing_csv}.",
                missingFields=missing_fields,
            ),
            400,
        )

    pdf_bytes = render_cover_letter_pdf(record)
    buffer = BytesIO(pdf_bytes)
    buffer.seek(0)

    filename = f"cover-letter-{letter_id}.pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
