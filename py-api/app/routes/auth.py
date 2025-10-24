"""/api/auth routes handling login code issuance and verification."""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

from app.storage import pending_codes, sessions
from app.utils.auth import (
    CODE_TTL_SECONDS,
    SESSION_TTL_SECONDS,
    generate_code,
    generate_token,
    require_session,
    now_seconds,
)

# Import auth service if MongoDB is enabled
ENABLE_MONGODB = os.getenv("ENABLE_MONGODB", "false").lower() == "true"
if ENABLE_MONGODB:
    try:
        from app.services import auth_service
    except ImportError:
        ENABLE_MONGODB = False
        print("MongoDB enabled but auth_service import failed")

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/request-code")
def request_code():
    """Generate a workspace code that serves as both the access code and profile ID."""
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    provided_code = payload.get("profileId") or payload.get("code")

    # If user provides an existing code, use it (for returning users)
    # Otherwise generate a new one
    if provided_code and isinstance(provided_code, str):
        code = provided_code.strip().upper()
    else:
        code = generate_code()
    
    # The code IS the profile ID - no separate profile needed
    profile_id = code
    expires_at = now_seconds() + CODE_TTL_SECONDS

    # Store in MongoDB if enabled, otherwise use in-memory storage
    if ENABLE_MONGODB:
        try:
            auth_service.save_verification_code(code, profile_id, expires_at)
        except Exception as e:
            current_app.logger.error(f"Failed to save code to MongoDB: {e}")
            # Fall back to in-memory
            pending_codes[code] = {
                "code": code,
                "profile_id": profile_id,
                "expires_at": expires_at,
            }
    else:
        pending_codes[code] = {
            "code": code,
            "profile_id": profile_id,
            "expires_at": expires_at,
        }

    return (
        jsonify(
            code=code,
            profileId=profile_id,  # Same as code
            expiresAt=expires_at * 1000,
        ),
        200,
    )


@bp.post("/verify")
def verify_code():
    """Validate a workspace code and issue a session token.
    
    The code serves as both the access code and the profile ID.
    Users can re-enter their code to access their workspace and history.
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip().upper()

    if not code:
        return jsonify(error="Code is required."), 400

    # Try MongoDB first if enabled - check if this code exists as a profile
    record = None
    existing_profile = False
    
    if ENABLE_MONGODB:
        try:
            # First check if there's an active verification code
            record = auth_service.get_verification_code(code)
            if record and record["expires_at"] > now_seconds():
                # Mark as used so it can't be reused as a pending code
                auth_service.mark_code_as_used(code)
                existing_profile = False
            else:
                # Check if this code is an existing workspace/profile ID
                # by checking if there's any session history for it
                existing_session = auth_service.get_profile_by_code(code)
                if existing_session:
                    # User is re-entering their workspace code
                    record = {
                        "code": code,
                        "profile_id": code,
                        "expires_at": now_seconds() + SESSION_TTL_SECONDS
                    }
                    existing_profile = True
                else:
                    record = None
        except Exception as e:
            current_app.logger.error(f"Failed to get code from MongoDB: {e}")
            record = None
    
    # Fall back to in-memory if MongoDB not available
    if not record and not existing_profile:
        record = pending_codes.pop(code, None)
        if not record or record["expires_at"] <= now_seconds():
            return jsonify(error="Invalid or expired code."), 401

    expires_at = now_seconds() + SESSION_TTL_SECONDS
    token = generate_token("sess")

    # The profile_id is the same as the code
    profile_id = code

    session_data = {
        "token": token,
        "profile_id": profile_id,
        "access_code": code,
        "issued_at": now_seconds(),
        "expires_at": expires_at,
    }

    # Save to MongoDB if enabled
    if ENABLE_MONGODB:
        try:
            auth_service.save_session(token, profile_id, code, expires_at)
        except Exception as e:
            current_app.logger.error(f"Failed to save session to MongoDB: {e}")
    
    # Always keep in-memory for backward compatibility
    sessions[token] = session_data

    return (
        jsonify(
            token=token,
            profileId=profile_id,  # Same as code
            expiresAt=expires_at * 1000,
        ),
        200,
    )


@bp.get("/session")
def get_session_info():
    """Return information about the current session token if it is valid."""
    session, error_response = require_session()
    if error_response is not None:
        return error_response

    return (
        jsonify(
            token=session["token"],
            profileId=session["profile_id"],
            expiresAt=session["expires_at"] * 1000,
        ),
        200,
    )
