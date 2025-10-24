"""In-memory data stores backing the prototype state."""

from typing import Any, Dict

# Verification codes waiting to be redeemed.
pending_codes: Dict[str, Dict[str, Any]] = {}

# Active session tokens mapped to their metadata.
# Now includes 'access_code' for MongoDB chat history tracking
sessions: Dict[str, Dict[str, Any]] = {}

# Uploaded files keyed by file id.
uploaded_files: Dict[str, Dict[str, Any]] = {}

# Stored cover letters keyed by letter id.
cover_letters: Dict[str, Dict[str, Any]] = {}

# Stored job descriptions keyed by profile id.
job_descriptions: Dict[str, Dict[str, Any]] = {}
