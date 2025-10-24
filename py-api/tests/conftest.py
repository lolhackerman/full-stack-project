"""Shared pytest fixtures for MongoDB-enabled services."""

from __future__ import annotations

import sys
from pathlib import Path

import mongomock
import pytest

# Ensure the application package is importable during tests.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import database  # noqa: E402


@pytest.fixture(autouse=True)
def mongo_db(monkeypatch: pytest.MonkeyPatch):
    """Provide an isolated in-memory MongoDB database for each test."""
    test_db_name = "test_cover_letter_app"
    monkeypatch.setenv("ENABLE_MONGODB", "true")
    monkeypatch.setenv("MONGODB_DATABASE", test_db_name)

    client = mongomock.MongoClient()
    db = client[test_db_name]

    monkeypatch.setattr(database, "get_mongo_client", lambda: client)
    monkeypatch.setattr(database, "get_database", lambda: db)

    yield db

    client.drop_database(test_db_name)
