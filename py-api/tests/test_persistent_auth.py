"""Tests for persistent authentication backed by MongoDB."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import auth_service  # noqa: E402
from app.utils.auth import (  # noqa: E402
    CODE_TTL_SECONDS,
    SESSION_TTL_SECONDS,
    generate_code,
    generate_token,
    now_seconds,
)


def test_verification_code_lifecycle(mongo_db):
    code = generate_code()
    profile_id = f"profile-{generate_token('profile')}"
    expires_at = now_seconds() + CODE_TTL_SECONDS

    auth_service.save_verification_code(code, profile_id, expires_at)

    stored = auth_service.get_verification_code(code)
    assert stored is not None
    assert stored["profile_id"] == profile_id
    assert stored["used"] is False

    assert auth_service.mark_code_as_used(code) is True
    assert auth_service.get_verification_code(code) is None


def test_session_lifecycle():
    token = generate_token("sess")
    profile_id = "profile-session"
    access_code = "access-code"
    expires_at = now_seconds() + SESSION_TTL_SECONDS

    auth_service.save_session(token, profile_id, access_code, expires_at)

    session = auth_service.get_session(token)
    assert session is not None
    assert session["profile_id"] == profile_id
    assert session["access_code"] == access_code
    assert session["token"] == token

    assert auth_service.delete_session(token) is True
    assert auth_service.get_session(token) is None


def test_cleanup_expired_documents(mongo_db):
    now_ts = now_seconds()

    auth_service.save_verification_code("expired-code", "expired-profile", now_ts - 10)
    auth_service.save_verification_code("expired-code-used", "expired-profile", now_ts - 5)
    mongo_db.verification_codes.update_one({"code": "expired-code-used"}, {"$set": {"used": True}})
    auth_service.save_session("expired-token", "expired-profile", "expired", now_ts - 10)
    auth_service.save_verification_code("active-code", "active-profile", now_ts + CODE_TTL_SECONDS)

    result = auth_service.cleanup_expired_codes_and_sessions()

    assert result["sessions_deleted"] == 1
    assert result["codes_deleted"] >= 1
    assert mongo_db.verification_codes.count_documents({"code": "active-code"}) == 1
    assert mongo_db.verification_codes.count_documents({"code": "expired-code"}) == 0
    assert mongo_db.verification_codes.count_documents({"code": "expired-code-used"}) == 0
    assert mongo_db.sessions.count_documents({"token": "expired-token"}) == 0

