"""Service for managing uploaded files in MongoDB."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.database import get_database


def _get_uploads_collection() -> Optional[Collection]:
    """Get the MongoDB uploads collection if MongoDB is enabled."""
    if os.getenv("ENABLE_MONGODB", "").lower() != "true":
        return None
    
    try:
        db = get_database()
        return db["uploads"]
    except Exception:
        return None


def save_upload(
    profile_id: str,
    file_id: str,
    name: str,
    size: int,
    mime_type: str,
    contents: str,
    text: Optional[str] = None,
    text_excerpt: Optional[str] = None,
    uploaded_at: Optional[int] = None,
) -> bool:
    """
    Save an uploaded file to MongoDB.
    
    Args:
        profile_id: The profile ID that owns this file
        file_id: Unique file identifier
        name: Original filename
        size: File size in bytes
        mime_type: MIME type of the file
        contents: Base64-encoded file contents
        text: Extracted text content (if available)
        text_excerpt: Brief excerpt of text content
        uploaded_at: Upload timestamp in milliseconds
        
    Returns:
        True if saved successfully, False otherwise
    """
    collection = _get_uploads_collection()
    if collection is None:
        return False
    
    try:
        upload_doc = {
            "profile_id": profile_id,
            "file_id": file_id,
            "name": name,
            "size": size,
            "mime_type": mime_type,
            "contents": contents,
            "text": text,
            "text_excerpt": text_excerpt,
            "uploaded_at": uploaded_at or int(datetime.now().timestamp() * 1000),
            "created_at": datetime.utcnow(),
        }
        
        # Use upsert to avoid duplicates
        collection.update_one(
            {"profile_id": profile_id, "file_id": file_id},
            {"$set": upload_doc},
            upsert=True
        )
        
        return True
    except PyMongoError as e:
        print(f"Error saving upload to MongoDB: {e}")
        return False


def get_uploads_for_profile(profile_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all uploaded files for a specific profile.
    
    Args:
        profile_id: The profile ID to retrieve files for
        
    Returns:
        List of upload documents
    """
    collection = _get_uploads_collection()
    if collection is None:
        return []
    
    try:
        uploads = list(collection.find(
            {"profile_id": profile_id}
        ).sort("uploaded_at", -1))
        
        # Remove MongoDB's _id field for cleaner response
        for upload in uploads:
            upload.pop("_id", None)
        
        return uploads
    except PyMongoError as e:
        print(f"Error retrieving uploads from MongoDB: {e}")
        return []


def get_upload_by_id(profile_id: str, file_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific uploaded file.
    
    Args:
        profile_id: The profile ID that owns the file
        file_id: The file identifier
        
    Returns:
        Upload document or None if not found
    """
    collection = _get_uploads_collection()
    if collection is None:
        return None
    
    try:
        upload = collection.find_one({
            "profile_id": profile_id,
            "file_id": file_id
        })
        
        if upload:
            upload.pop("_id", None)
        
        return upload
    except PyMongoError as e:
        print(f"Error retrieving upload from MongoDB: {e}")
        return None


def delete_upload(profile_id: str, file_id: str) -> bool:
    """
    Delete an uploaded file from MongoDB.
    
    Args:
        profile_id: The profile ID that owns the file
        file_id: The file identifier
        
    Returns:
        True if deleted successfully, False otherwise
    """
    collection = _get_uploads_collection()
    if collection is None:
        return False
    
    try:
        result = collection.delete_one({
            "profile_id": profile_id,
            "file_id": file_id
        })
        
        return result.deleted_count > 0
    except PyMongoError as e:
        print(f"Error deleting upload from MongoDB: {e}")
        return False


def delete_all_uploads_for_profile(profile_id: str) -> int:
    """
    Delete all uploaded files for a specific profile.
    
    Args:
        profile_id: The profile ID
        
    Returns:
        Number of files deleted
    """
    collection = _get_uploads_collection()
    if collection is None:
        return 0
    
    try:
        result = collection.delete_many({"profile_id": profile_id})
        return result.deleted_count
    except PyMongoError as e:
        print(f"Error deleting uploads from MongoDB: {e}")
        return 0


def cleanup_old_uploads(days: int = 90) -> int:
    """
    Delete uploaded files older than the specified number of days.
    
    Args:
        days: Number of days to keep files
        
    Returns:
        Number of files deleted
    """
    collection = _get_uploads_collection()
    if collection is None:
        return 0
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        result = collection.delete_many({
            "created_at": {"$lt": cutoff_date}
        })
        
        return result.deleted_count
    except PyMongoError as e:
        print(f"Error cleaning up old uploads: {e}")
        return 0
