"""Service for managing authentication codes and sessions in MongoDB."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app import database


def save_verification_code(
    code: str,
    profile_id: str,
    expires_at: int,
) -> str:
    """
    Save a verification code to MongoDB.
    
    Args:
        code: The 6-digit verification code
        profile_id: The profile ID associated with this code
        expires_at: Unix timestamp when the code expires
    
    Returns:
        The code that was saved
    """
    db = database.get_database()
    collection = db.verification_codes
    
    document = {
        "code": code,
        "profile_id": profile_id,
        "expires_at": expires_at,
        "created_at": datetime.utcnow(),
        "used": False,
    }
    
    # Upsert: update if code exists, insert if not
    collection.update_one(
        {"code": code},
        {"$set": document},
        upsert=True
    )
    
    return code


def get_verification_code(code: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a verification code from MongoDB.
    
    Args:
        code: The 6-digit verification code
    
    Returns:
        The code document if found and not expired, None otherwise
    """
    db = database.get_database()
    collection = db.verification_codes
    
    document = collection.find_one({"code": code, "used": False})
    
    if document:
        # Convert ObjectId to string
        document["_id"] = str(document["_id"])
    
    return document


def mark_code_as_used(code: str) -> bool:
    """
    Mark a verification code as used so it can't be reused.
    
    Args:
        code: The 6-digit verification code
    
    Returns:
        True if the code was marked as used, False if not found
    """
    db = database.get_database()
    collection = db.verification_codes
    
    result = collection.update_one(
        {"code": code, "used": False},
        {"$set": {"used": True, "used_at": datetime.utcnow()}}
    )
    
    return result.modified_count > 0


def save_session(
    token: str,
    profile_id: str,
    access_code: str,
    expires_at: int,
) -> str:
    """
    Save a session to MongoDB.
    
    Args:
        token: The session token
        profile_id: The profile ID
        access_code: The original verification code (for chat history)
        expires_at: Unix timestamp when the session expires
    
    Returns:
        The token that was saved
    """
    db = database.get_database()
    collection = db.sessions
    
    document = {
        "token": token,
        "profile_id": profile_id,
        "access_code": access_code,
        "expires_at": expires_at,
        "created_at": datetime.utcnow(),
    }
    
    # Upsert: update if token exists, insert if not
    collection.update_one(
        {"token": token},
        {"$set": document},
        upsert=True
    )
    
    return token


def get_session(token: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a session from MongoDB.
    
    Args:
        token: The session token
    
    Returns:
        The session document if found and not expired, None otherwise
    """
    db = database.get_database()
    collection = db.sessions
    
    document = collection.find_one({"token": token})
    
    if document:
        # Convert ObjectId to string
        document["_id"] = str(document["_id"])
        
        # Convert datetime to timestamp for compatibility
        if "created_at" in document:
            document["issued_at"] = int(document["created_at"].timestamp())
    
    return document


def cleanup_expired_codes_and_sessions():
    """Remove expired verification codes and sessions from MongoDB."""
    db = database.get_database()
    
    current_timestamp = int(time.time())
    
    # Delete expired codes
    codes_result = db.verification_codes.delete_many({
        "expires_at": {"$lte": current_timestamp}
    })
    
    # Delete expired sessions
    sessions_result = db.sessions.delete_many({
        "expires_at": {"$lte": current_timestamp}
    })
    
    return {
        "codes_deleted": codes_result.deleted_count,
        "sessions_deleted": sessions_result.deleted_count,
    }


def delete_session(token: str) -> bool:
    """
    Delete a session from MongoDB.
    
    Args:
        token: The session token
    
    Returns:
        True if the session was deleted, False if not found
    """
    db = database.get_database()
    collection = db.sessions
    
    result = collection.delete_one({"token": token})
    return result.deleted_count > 0


def get_profile_by_code(code: str) -> Optional[Dict[str, Any]]:
    """
    Check if a code exists as a profile ID in the sessions or chat history.
    This allows users to re-enter their workspace code to access their data.
    
    Args:
        code: The workspace code (which is also the profile_id)
    
    Returns:
        A session-like document if the profile exists, None otherwise
    """
    db = database.get_database()
    
    # Check if there's any session history for this profile_id
    session = db.sessions.find_one(
        {"profile_id": code},
        sort=[("created_at", -1)]  # Get most recent
    )
    
    if session:
        # Convert ObjectId to string
        session["_id"] = str(session["_id"])
        if "created_at" in session:
            session["issued_at"] = int(session["created_at"].timestamp())
        return session
    
    # Also check chat history as a fallback
    chat_msg = db.chat_messages.find_one({"profile_id": code})
    if chat_msg:
        return {
            "profile_id": code,
            "access_code": code,
        }
    
    return None

