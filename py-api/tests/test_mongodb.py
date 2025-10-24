"""Tests for chat history persistence in MongoDB."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import chat_history_service  # noqa: E402


def test_save_and_fetch_chat_history(mongo_db):
    access_code = "code-123"
    profile_id = "profile-abc"
    thread_id = "thread-xyz"
    metadata = {"source": "unit-test"}

    message_id = chat_history_service.save_message(
        access_code=access_code,
        profile_id=profile_id,
        thread_id=thread_id,
        role="user",
        content="Test message content",
        metadata=metadata,
    )

    assert isinstance(message_id, str)

    history = chat_history_service.get_chat_history(
        access_code=access_code,
        profile_id=profile_id,
        thread_id=thread_id,
    )

    assert len(history) == 1
    stored = history[0]
    assert stored["role"] == "user"
    assert stored["content"] == "Test message content"
    assert stored["metadata"] == metadata

    metadata_doc = mongo_db.thread_metadata.find_one({
        "access_code": access_code,
        "profile_id": profile_id,
        "thread_id": thread_id,
    })
    assert metadata_doc is not None


def test_get_all_threads_returns_sorted_summary(mongo_db):
    access_code = "code-threads"
    profile_id = "profile-threads"

    chat_history_service.save_message(
        access_code=access_code,
        profile_id=profile_id,
        thread_id="alpha",
        role="user",
        content="First thread",
    )
    chat_history_service.update_thread_metadata(
        access_code=access_code,
        profile_id=profile_id,
        thread_id="alpha",
        title="Alpha Thread",
    )

    chat_history_service.save_message(
        access_code=access_code,
        profile_id=profile_id,
        thread_id="beta",
        role="assistant",
        content="Second thread",
    )

    threads = chat_history_service.get_all_threads_for_access_code(
        access_code=access_code,
        profile_id=profile_id,
    )

    assert {thread["thread_id"] for thread in threads} == {"alpha", "beta"}
    alpha_thread = next(thread for thread in threads if thread["thread_id"] == "alpha")
    assert alpha_thread["title"] == "Alpha Thread"


def test_delete_thread_history_removes_documents(mongo_db):
    access_code = "code-delete"
    profile_id = "profile-delete"
    thread_id = "thread-delete"

    chat_history_service.save_message(
        access_code=access_code,
        profile_id=profile_id,
        thread_id=thread_id,
        role="assistant",
        content="Message to delete",
    )

    deleted_count = chat_history_service.delete_thread_history(
        access_code=access_code,
        profile_id=profile_id,
        thread_id=thread_id,
    )

    assert deleted_count == 1
    remaining = chat_history_service.get_chat_history(
        access_code=access_code,
        profile_id=profile_id,
        thread_id=thread_id,
    )
    assert remaining == []

