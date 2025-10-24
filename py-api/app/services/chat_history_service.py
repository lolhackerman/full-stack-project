"""Service for managing chat history in MongoDB."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import get_database


def update_thread_metadata(
    access_code: str,
    profile_id: str,
    thread_id: str,
    title: Optional[str] = None,
) -> None:
    """
    Update or create thread metadata (e.g., title).
    
    Args:
        access_code: The access code (session code) for the user
        profile_id: The profile/user ID
        thread_id: The thread ID
        title: Optional thread title/summary
    """
    db = get_database()
    collection = db.thread_metadata
    
    normalized_thread = (thread_id or "").strip() or "default"
    
    # Upsert thread metadata
    update_doc = {
        "$set": {
            "updated_at": datetime.utcnow(),
        }
    }
    
    if title is not None:
        update_doc["$set"]["title"] = title
    
    update_doc["$setOnInsert"] = {
        "access_code": access_code,
        "profile_id": profile_id,
        "thread_id": normalized_thread,
        "created_at": datetime.utcnow(),
    }
    
    collection.update_one(
        {
            "access_code": access_code,
            "profile_id": profile_id,
            "thread_id": normalized_thread,
        },
        update_doc,
        upsert=True,
    )


def get_thread_metadata(
    access_code: str,
    profile_id: str,
    thread_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get thread metadata.
    
    Args:
        access_code: The access code (session code) for the user
        profile_id: The profile/user ID
        thread_id: The thread ID
    
    Returns:
        Thread metadata dictionary or None if not found
    """
    db = get_database()
    collection = db.thread_metadata
    
    normalized_thread = (thread_id or "").strip() or "default"
    
    metadata = collection.find_one({
        "access_code": access_code,
        "profile_id": profile_id,
        "thread_id": normalized_thread,
    })
    
    if metadata:
        metadata["_id"] = str(metadata["_id"])
        if "created_at" in metadata:
            metadata["created_at"] = metadata["created_at"].isoformat()
        if "updated_at" in metadata:
            metadata["updated_at"] = metadata["updated_at"].isoformat()
    
    return metadata


def save_message(
    access_code: str,
    profile_id: str,
    thread_id: Optional[str],
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Save a chat message to MongoDB.
    
    Args:
        access_code: The access code (session code) for the user
        profile_id: The profile/user ID
        thread_id: Optional thread ID for conversation context
        role: Message role ('user' or 'assistant')
        content: The message content
        metadata: Optional metadata (attachments, file_ids, etc.)
    
    Returns:
        The MongoDB document ID as a string
    """
    db = get_database()
    collection = db.chat_history
    
    normalized_thread = (thread_id or "").strip() or "default"
    current_time = datetime.utcnow()
    
    document = {
        "access_code": access_code,
        "profile_id": profile_id,
        "thread_id": normalized_thread,
        "role": role,
        "content": content,
        "metadata": metadata or {},
        "timestamp": current_time,
        "created_at": current_time,
    }
    
    result = collection.insert_one(document)
    
    # Update thread metadata's updated_at timestamp to reflect latest activity
    # This ensures the thread appears at the top of the list
    update_thread_metadata(
        access_code=access_code,
        profile_id=profile_id,
        thread_id=normalized_thread,
    )
    
    return str(result.inserted_id)


def get_chat_history(
    access_code: str,
    profile_id: str,
    thread_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Retrieve chat history for a specific access code and profile.
    
    Args:
        access_code: The access code (session code) for the user
        profile_id: The profile/user ID
        thread_id: Optional thread ID to filter by
        limit: Maximum number of messages to return (default 100)
    
    Returns:
        List of message dictionaries sorted by timestamp (oldest first)
    """
    db = get_database()
    collection = db.chat_history
    
    query: Dict[str, Any] = {
        "access_code": access_code,
        "profile_id": profile_id,
    }
    
    if thread_id:
        normalized_thread = thread_id.strip() or "default"
        query["thread_id"] = normalized_thread
    
    messages = list(
        collection.find(query)
        .sort("timestamp", 1)
        .limit(limit)
    )
    
    # Convert ObjectId to string for JSON serialization
    for msg in messages:
        msg["_id"] = str(msg["_id"])
        if "timestamp" in msg:
            msg["timestamp"] = msg["timestamp"].isoformat()
        if "created_at" in msg:
            msg["created_at"] = msg["created_at"].isoformat()
    
    return messages


def get_all_threads_for_access_code(
    access_code: str,
    profile_id: str,
) -> List[Dict[str, Any]]:
    """
    Get all unique thread IDs for an access code with their last message timestamp and title.
    
    Args:
        access_code: The access code (session code) for the user
        profile_id: The profile/user ID
    
    Returns:
        List of thread info dictionaries with thread_id, title, and last_message_at
    """
    db = get_database()
    collection = db.chat_history
    metadata_collection = db.thread_metadata
    
    pipeline = [
        {
            "$match": {
                "access_code": access_code,
                "profile_id": profile_id,
            }
        },
        {
            "$group": {
                "_id": "$thread_id",
                "last_message_at": {"$max": "$timestamp"},
                "message_count": {"$sum": 1},
            }
        },
        {
            "$sort": {"last_message_at": -1}
        }
    ]
    
    threads = list(collection.aggregate(pipeline))
    
    # Format results and fetch metadata (titles) or generate from first message
    result = []
    for thread in threads:
        thread_id = thread["_id"]
        
        # Try to get thread metadata (title)
        metadata = metadata_collection.find_one({
            "access_code": access_code,
            "profile_id": profile_id,
            "thread_id": thread_id,
        })
        
        title = metadata.get("title") if metadata else None
        
        # If no custom title, get first user message as preview
        if not title:
            first_message = collection.find_one(
                {
                    "access_code": access_code,
                    "profile_id": profile_id,
                    "thread_id": thread_id,
                    "role": "user",
                },
                sort=[("timestamp", 1)]
            )
            if first_message and first_message.get("content"):
                # Use first 60 chars of first user message as title
                title = first_message["content"][:60].strip()
                if len(first_message["content"]) > 60:
                    title += "..."
        
        result.append({
            "thread_id": thread_id,
            "title": title or f"Thread {thread_id}",
            "last_message_at": thread["last_message_at"].isoformat(),
            "message_count": thread["message_count"],
        })
    
    return result


def delete_thread_history(
    access_code: str,
    profile_id: str,
    thread_id: str,
) -> int:
    """
    Delete all messages and metadata for a specific thread.
    
    Args:
        access_code: The access code (session code) for the user
        profile_id: The profile/user ID
        thread_id: The thread ID to delete
    
    Returns:
        Number of messages deleted
    """
    db = get_database()
    collection = db.chat_history
    metadata_collection = db.thread_metadata
    
    normalized_thread = (thread_id or "").strip() or "default"
    
    # Delete messages
    result = collection.delete_many({
        "access_code": access_code,
        "profile_id": profile_id,
        "thread_id": normalized_thread,
    })
    
    # Delete thread metadata
    metadata_collection.delete_one({
        "access_code": access_code,
        "profile_id": profile_id,
        "thread_id": normalized_thread,
    })
    
    return result.deleted_count


def delete_all_history_for_access_code(
    access_code: str,
    profile_id: str,
) -> int:
    """
    Delete all chat history and thread metadata for an access code.
    
    Args:
        access_code: The access code (session code) for the user
        profile_id: The profile/user ID
    
    Returns:
        Number of messages deleted
    """
    db = get_database()
    collection = db.chat_history
    metadata_collection = db.thread_metadata
    
    # Delete all messages
    result = collection.delete_many({
        "access_code": access_code,
        "profile_id": profile_id,
    })
    
    # Delete all thread metadata
    metadata_collection.delete_many({
        "access_code": access_code,
        "profile_id": profile_id,
    })
    
    return result.deleted_count


def create_indexes():
    """Create database indexes for optimal query performance."""
    db = get_database()
    collection = db.chat_history
    metadata_collection = db.thread_metadata
    
    # Index for querying by access_code and profile_id
    collection.create_index([
        ("access_code", 1),
        ("profile_id", 1),
        ("timestamp", 1)
    ])
    
    # Index for querying by thread_id
    collection.create_index([
        ("access_code", 1),
        ("profile_id", 1),
        ("thread_id", 1),
        ("timestamp", 1)
    ])
    
    # TTL index to automatically delete old messages after 90 days (optional)
    collection.create_index("created_at", expireAfterSeconds=60 * 60 * 24 * 90)
    
    # Indexes for thread metadata collection
    metadata_collection.create_index([
        ("access_code", 1),
        ("profile_id", 1),
        ("thread_id", 1)
    ], unique=True)
    
    metadata_collection.create_index("created_at", expireAfterSeconds=60 * 60 * 24 * 90)

