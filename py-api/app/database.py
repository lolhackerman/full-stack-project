"""MongoDB database configuration and connection management."""

from __future__ import annotations

import os
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database


# Global MongoDB client instance
_client: Optional[MongoClient] = None
_database: Optional[Database] = None


def get_mongo_client() -> MongoClient:
    """Get or create MongoDB client instance."""
    global _client
    if _client is None:
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        _client = MongoClient(mongo_uri)
    return _client


def get_database() -> Database:
    """Get the MongoDB database instance."""
    global _database
    if _database is None:
        client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "cover_letter_app")
        _database = client[db_name]
    return _database


def close_mongo_connection():
    """Close the MongoDB connection."""
    global _client, _database
    if _client is not None:
        _client.close()
        _client = None
        _database = None
