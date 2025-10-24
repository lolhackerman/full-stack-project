"""/api/uploads routes for managing user-provided files."""

from __future__ import annotations

import base64
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from app.storage import uploaded_files
from app.services import upload_service
from app.utils.auth import generate_token, now_millis, require_session
from app.utils.text import extract_text_from_upload, make_text_excerpt, safe_text_preview

bp = Blueprint("uploads", __name__, url_prefix="/api/uploads")


@bp.post("")
def upload_files():
    """Accept and index uploaded files for personalization prompts."""
    session, error_response = require_session()
    if error_response is not None:
        return error_response

    files = request.files.getlist("files")
    if not files:
        return jsonify(error="No files uploaded."), 400

    uploaded: List[Dict[str, Any]] = []
    for storage in files:
        if storage.filename == "":
            continue

        file_id = generate_token("file")
        raw_bytes = storage.read()
        contents = base64.b64encode(raw_bytes).decode("ascii")
        text_content = extract_text_from_upload(raw_bytes, storage.filename, storage.mimetype)
        text_excerpt = make_text_excerpt(text_content) if text_content else safe_text_preview(contents)

        record = {
            "id": file_id,
            "profile_id": session["profile_id"],
            "name": storage.filename,
            "size": len(raw_bytes),
            "mime_type": storage.mimetype,
            "contents": contents,
            "uploaded_at": now_millis(),
            "text": text_content,
            "text_excerpt": text_excerpt,
        }

        # Store in memory for immediate access
        uploaded_files[file_id] = record
        
        # Persist to MongoDB for cross-device access
        upload_service.save_upload(
            profile_id=session["profile_id"],
            file_id=file_id,
            name=storage.filename,
            size=len(raw_bytes),
            mime_type=storage.mimetype,
            contents=contents,
            text=text_content,
            text_excerpt=text_excerpt,
            uploaded_at=record["uploaded_at"],
        )
        
        uploaded.append(
            {
                "id": file_id,
                "name": record["name"],
                "size": record["size"],
                "mimeType": record["mime_type"],
                "uploadedAt": record["uploaded_at"],
                "hasText": bool(text_content),
            }
        )

    if not uploaded:
        return jsonify(error="No valid files provided."), 400

    return jsonify(files=uploaded), 200


@bp.get("")
def list_uploaded_files():
    """Return all uploaded files for the current session/profile."""
    session, error_response = require_session()
    if error_response is not None:
        return error_response

    profile_id = session["profile_id"]
    
    # First, try to load from MongoDB
    mongo_uploads = upload_service.get_uploads_for_profile(profile_id)
    
    # Sync MongoDB uploads to in-memory storage for immediate use
    for upload in mongo_uploads:
        file_id = upload.get("file_id")
        if file_id and file_id not in uploaded_files:
            uploaded_files[file_id] = {
                "id": file_id,
                "profile_id": upload["profile_id"],
                "name": upload["name"],
                "size": upload["size"],
                "mime_type": upload["mime_type"],
                "contents": upload["contents"],
                "uploaded_at": upload["uploaded_at"],
                "text": upload.get("text"),
                "text_excerpt": upload.get("text_excerpt"),
            }
    
    # Get all files for this profile from in-memory storage
    files = [
        {
            "id": record["id"],
            "name": record["name"],
            "size": record["size"],
            "mimeType": record["mime_type"],
            "uploadedAt": record["uploaded_at"],
            "hasText": bool(record.get("text")),
        }
        for record in uploaded_files.values()
        if record["profile_id"] == profile_id
    ]
    
    # Sort by upload time (most recent first)
    files.sort(key=lambda f: f["uploadedAt"], reverse=True)
    
    return jsonify(files=files), 200


@bp.get("/<file_id>")
def get_uploaded_file(file_id: str):
    """Return uploaded file metadata and contents for the current session."""
    session, error_response = require_session()
    if error_response is not None:
        return error_response

    profile_id = session["profile_id"]
    
    # Try in-memory first
    record = uploaded_files.get(file_id)
    
    # If not in memory, try MongoDB
    if not record or record["profile_id"] != profile_id:
        mongo_record = upload_service.get_upload_by_id(profile_id, file_id)
        if mongo_record:
            # Load into memory for future use
            record = {
                "id": mongo_record["file_id"],
                "profile_id": mongo_record["profile_id"],
                "name": mongo_record["name"],
                "size": mongo_record["size"],
                "mime_type": mongo_record["mime_type"],
                "contents": mongo_record["contents"],
                "uploaded_at": mongo_record["uploaded_at"],
                "text": mongo_record.get("text"),
                "text_excerpt": mongo_record.get("text_excerpt"),
            }
            uploaded_files[file_id] = record
    
    if not record or record["profile_id"] != profile_id:
        return jsonify(error="File not found."), 404

    return (
        jsonify(
            id=record["id"],
            name=record["name"],
            size=record["size"],
            mimeType=record["mime_type"],
            contents=record["contents"],
            uploadedAt=record["uploaded_at"],
            text=record.get("text"),
            textExcerpt=record.get("text_excerpt"),
        ),
        200,
    )


@bp.delete("/<file_id>")
def delete_uploaded_file(file_id: str):
    """Remove a previously uploaded file for the current session."""
    session, error_response = require_session()
    if error_response is not None:
        return error_response

    profile_id = session["profile_id"]
    record = uploaded_files.get(file_id)
    
    if not record or record["profile_id"] != profile_id:
        return jsonify(error="File not found."), 404

    # Remove from in-memory storage
    uploaded_files.pop(file_id, None)
    
    # Remove from MongoDB
    upload_service.delete_upload(profile_id, file_id)

    return jsonify(success=True), 200
