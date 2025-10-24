"""Admin utilities for managing workspaces and debugging."""

from __future__ import annotations

import os
from flask import Blueprint, jsonify

from app.database import get_database

ENABLE_MONGODB = os.getenv("ENABLE_MONGODB", "false").lower() == "true"

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/workspaces")
def list_workspaces():
    """List all workspaces (profile IDs) in the system."""
    if not ENABLE_MONGODB:
        return jsonify(error="MongoDB not enabled", workspaces=[]), 200
    
    try:
        db = get_database()
        
        # Get unique profile IDs from sessions
        sessions = db.sessions.find({}, {"profile_id": 1, "created_at": 1, "_id": 0})
        session_profiles = {s["profile_id"]: s.get("created_at") for s in sessions}
        
        # Get unique profile IDs from chat messages
        chat_profiles = db.chat_messages.distinct("profile_id")
        
        # Combine all unique workspace codes
        all_profiles = set(session_profiles.keys()) | set(chat_profiles)
        
        workspaces = []
        for profile_id in sorted(all_profiles):
            # Get message count
            msg_count = db.chat_messages.count_documents({"profile_id": profile_id})
            
            # Get thread count
            thread_count = db.chat_threads.count_documents({"profile_id": profile_id})
            
            # Get file count
            file_count = db.uploaded_files.count_documents({"profile_id": profile_id})
            
            workspaces.append({
                "workspace_code": profile_id,
                "created_at": session_profiles.get(profile_id),
                "message_count": msg_count,
                "thread_count": thread_count,
                "file_count": file_count,
            })
        
        return jsonify(
            workspaces=workspaces,
            total_count=len(workspaces)
        ), 200
        
    except Exception as e:
        return jsonify(error=str(e)), 500


@bp.get("/stats")
def get_stats():
    """Get overall system statistics."""
    if not ENABLE_MONGODB:
        return jsonify(error="MongoDB not enabled"), 200
    
    try:
        db = get_database()
        
        stats = {
            "total_workspaces": len(db.chat_messages.distinct("profile_id")),
            "total_sessions": db.sessions.count_documents({}),
            "total_messages": db.chat_messages.count_documents({}),
            "total_threads": db.chat_threads.count_documents({}),
            "total_files": db.uploaded_files.count_documents({}),
            "pending_codes": db.verification_codes.count_documents({"used": False}),
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        return jsonify(error=str(e)), 500
