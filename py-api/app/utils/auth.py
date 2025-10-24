"""Authentication helpers for session and token management."""

from __future__ import annotations

import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from flask import Flask, jsonify, request

from app.storage import pending_codes, sessions

# Import auth service if MongoDB is enabled
ENABLE_MONGODB = os.getenv("ENABLE_MONGODB", "false").lower() == "true"
if ENABLE_MONGODB:
    try:
        from app.services import auth_service
    except ImportError:
        ENABLE_MONGODB = False

# Session and code expiry windows (seconds).
CODE_TTL_SECONDS = 5 * 60
SESSION_TTL_SECONDS = 24 * 60 * 60


def now_seconds() -> int:
    """Return the current UNIX timestamp in seconds."""
    return int(time.time())


def now_millis() -> int:
    """Return the current UNIX timestamp in milliseconds."""
    return int(time.time() * 1000)


def generate_code() -> str:
    """Return a pseudo-random six character alphanumeric code that serves as the profile ID."""
    # Generate a 6-character alphanumeric code (easier to remember/type)
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Exclude similar looking chars (0,O,1,I)
    return ''.join(secrets.choice(chars) for _ in range(6))


def generate_token(prefix: str = "sess") -> str:
    """Return a signed token with the given prefix suitable for in-memory keys."""
    return f"{prefix}_{secrets.token_urlsafe(12)}"


def prune_expired() -> None:
    """Remove stale verification codes and sessions from in-memory storage."""
    current = now_seconds()

    for code, record in list(pending_codes.items()):
        if record["expires_at"] <= current:
            pending_codes.pop(code, None)

    for token, session in list(sessions.items()):
        if session["expires_at"] <= current:
            sessions.pop(token, None)


def require_session() -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
    """Validate the Bearer token from the request and return the associated session."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify(error="Missing authorization token."), 401)

    token = auth_header[7:].strip()
    
    # Try in-memory first for speed
    session = sessions.get(token)
    
    # If not in memory and MongoDB is enabled, check MongoDB
    if not session and ENABLE_MONGODB:
        try:
            session = auth_service.get_session(token)
            if session:
                # Cache in memory for faster subsequent access
                sessions[token] = session
        except Exception:
            pass  # Fall through to not found

    if not session:
        return None, (jsonify(error="Invalid or expired session."), 401)

    if session["expires_at"] <= now_seconds():
        sessions.pop(token, None)
        if ENABLE_MONGODB:
            try:
                auth_service.delete_session(token)
            except Exception:
                pass
        return None, (jsonify(error="Session expired."), 401)

    return session, None


def register_session_cleanup(app: Flask) -> None:
    """Attach a before-request handler that keeps session state tidy."""

    @app.before_request  # pragma: no cover - trivial wiring
    def _cleanup_state() -> None:
        prune_expired()
