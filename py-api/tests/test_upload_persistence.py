"""Tests for file upload persistence in MongoDB."""

from __future__ import annotations

import base64
import sys
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import upload_service  # noqa: E402


def test_upload_crud_flow():
    profile_id = "profile-uploads"
    file_id = "file-123"
    payload = b"Example resume content"
    encoded = base64.b64encode(payload).decode("ascii")

    saved = upload_service.save_upload(
        profile_id=profile_id,
        file_id=file_id,
        name="resume.pdf",
        size=len(payload),
        mime_type="application/pdf",
        contents=encoded,
        text="Example resume content",
        text_excerpt="Example resume",
    )

    assert saved is True

    retrieved = upload_service.get_upload_by_id(profile_id, file_id)
    assert retrieved is not None
    assert retrieved["name"] == "resume.pdf"
    assert retrieved["contents"] == encoded

    uploads = upload_service.get_uploads_for_profile(profile_id)
    assert len(uploads) == 1
    assert uploads[0]["file_id"] == file_id

    assert upload_service.delete_upload(profile_id, file_id) is True
    assert upload_service.get_upload_by_id(profile_id, file_id) is None


def test_cleanup_old_uploads():
    collection = upload_service._get_uploads_collection()
    assert collection is not None

    collection.insert_one(
        {
            "profile_id": "profile-old",
            "file_id": "old-file",
            "name": "old.pdf",
            "size": 100,
            "mime_type": "application/pdf",
            "contents": "",
            "uploaded_at": int(datetime.utcnow().timestamp() * 1000),
            "created_at": datetime.utcnow() - timedelta(days=120),
        }
    )

    removed = upload_service.cleanup_old_uploads(days=90)

    assert removed == 1
    assert collection.count_documents({"file_id": "old-file"}) == 0
