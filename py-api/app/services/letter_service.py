"""Business logic for storing and manipulating cover letters."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.storage import cover_letters, job_descriptions, uploaded_files
from app.utils.auth import generate_token, now_millis
from app.utils.placeholders import ensure_cover_letter_date
from app.utils.text import looks_like_job_description, make_text_excerpt

LETTER_READY_FOLLOW_UP = (
    "\n\nWhen you're satisfied, ask me to generate your PDF. Otherwise, let me know what you'd like to revise."
)

ADJUSTMENT_KEYWORDS = (
    "adjust",
    "tweak",
    "change",
    "revise",
    "rewrite",
    "shorter",
    "longer",
    "tone",
    "friendlier",
    "formal",
    "casual",
    "add",
    "include",
    "remove",
    "emphasize",
    "highlight",
    "focus on",
    "soften",
    "strengthen",
    "update",
    "polish",
    "human"
)

JOB_DESCRIPTION_MAX_LENGTH = 5_000
DEFAULT_THREAD_ID = "default"


def appears_to_be_cover_letter(text: str) -> bool:
    """
    Detect if a text appears to be a formatted cover letter.
    
    Checks for:
    - Formal salutation (Dear..., To Whom It May Concern)
    - Formal closing (Sincerely, Best regards, etc.)
    - Substantial length (at least 200 characters)
    
    Returns True if text has the structure of a cover letter.
    """
    if not text or len(text) < 200:
        return False
    
    text_lower = text.lower()
    
    # Check for salutation
    has_salutation = (
        "dear " in text_lower
        or "to whom it may concern" in text_lower
        or "hiring manager" in text_lower
    )
    
    # Check for closing
    has_closing = (
        "sincerely" in text_lower
        or "regards" in text_lower
        or "respectfully" in text_lower
        or "best wishes" in text_lower
    )
    
    return has_salutation and has_closing


def _normalize_thread_id(thread_id: Optional[str]) -> str:
    """Collapse blank thread ids into a shared default bucket."""
    normalized = (thread_id or "").strip()
    return normalized or DEFAULT_THREAD_ID


def _thread_key(profile_id: str, thread_id: Optional[str]) -> str:
    """Return the dictionary key for storing per-thread artifacts."""
    return f"{profile_id}::{_normalize_thread_id(thread_id)}"


def letter_follow_up_text(missing_fields: List[str]) -> str:
    """Return the appropriate follow-up reminder based on missing placeholders."""
    if missing_fields:
        missing_csv = ", ".join(missing_fields)
        return f"\n\nI still need the following details before the PDF is ready: {missing_csv}."
    return LETTER_READY_FOLLOW_UP


def _first_nonempty_line(text: str) -> Optional[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def save_cover_letter(
    profile_id: str,
    thread_id: Optional[str],
    text: str,
    letter_id: Optional[str] = None,
) -> Tuple[str, str]:
    """Persist cover letter text for a profile + thread, returning its id and formatted contents."""
    formatted = ensure_cover_letter_date(text)
    header_line = _first_nonempty_line(formatted)
    timestamp = now_millis()
    normalized_thread = _normalize_thread_id(thread_id)

    if letter_id and letter_id in cover_letters:
        record = cover_letters[letter_id]
        record["text"] = formatted
        record["updated_at"] = timestamp
        record["thread_id"] = normalized_thread
    else:
        letter_id = generate_token("letter")
        record = {
            "id": letter_id,
            "profile_id": profile_id,
            "text": formatted,
            "thread_id": normalized_thread,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        cover_letters[letter_id] = record

    if header_line:
        record["header_date"] = header_line
    else:
        record.pop("header_date", None)

    record.setdefault("created_at", timestamp)
    record.setdefault("updated_at", timestamp)

    return letter_id, formatted


def store_cover_letter(profile_id: str, thread_id: Optional[str], text: str) -> Tuple[str, str]:
    """Convenience wrapper to store a new cover letter for the given profile and thread."""
    return save_cover_letter(profile_id, thread_id, text)


def store_job_description(profile_id: str, thread_id: Optional[str], text: str) -> None:
    """Persist the latest job description shared by the user for future drafts."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return

    limited = cleaned[:JOB_DESCRIPTION_MAX_LENGTH]
    excerpt = make_text_excerpt(limited, limit=600)
    timestamp = now_millis()
    normalized_thread = _normalize_thread_id(thread_id)
    job_descriptions[_thread_key(profile_id, thread_id)] = {
        "profile_id": profile_id,
        "thread_id": normalized_thread,
        "text": limited,
        "excerpt": excerpt,
        "stored_at": timestamp,
    }


def latest_job_description_for_thread(profile_id: str, thread_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the most recently stored job description for the profile + thread."""
    return job_descriptions.get(_thread_key(profile_id, thread_id))


def message_is_job_description(message: str) -> bool:
    """Identify whether the message text resembles a standalone job description."""
    return looks_like_job_description(message or "")


def latest_cover_letter_for_thread(profile_id: str, thread_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the most recent cover letter stored for the provided profile + thread."""
    normalized_thread = _normalize_thread_id(thread_id)
    matches = [
        record
        for record in cover_letters.values()
        if record.get("profile_id") == profile_id
        and _normalize_thread_id(record.get("thread_id")) == normalized_thread
    ]
    if not matches:
        return None
    return max(matches, key=lambda record: record.get("created_at", 0))


def select_resume_upload(profile_id: str) -> Optional[Dict[str, Any]]:
    """Pick the best resume candidate among uploaded files for styling and export."""
    matches = [record for record in uploaded_files.values() if record.get("profile_id") == profile_id]
    if not matches:
        return None

    def _priority(record: Dict[str, Any]) -> Tuple[int, int]:
        name = (record.get("name") or "").lower()
        mime = (record.get("mime_type") or "").lower()
        priority = 0
        if "resume" in name or "cv" in name:
            priority = 2
        elif mime == "application/pdf":
            priority = 1
        timestamp = int(record.get("uploaded_at") or 0)
        return (priority, timestamp)

    return max(matches, key=_priority)


def looks_like_letter_adjustment(message: str) -> bool:
    """Return True when the message appears to ask for an edit to an existing draft."""
    normalized = " ".join((message or "").lower().split())
    if not normalized:
        return False

    if normalized.startswith("create pdf") or normalized.startswith("download pdf"):
        return False

    if normalized.startswith("make it "):
        return True

    adjustment_starters = ("can you", "could you", "please", "update ", "change ")
    if normalized.startswith(adjustment_starters):
        return True

    for keyword in ADJUSTMENT_KEYWORDS:
        if keyword in normalized:
            return True

    return False


def should_draft_cover_letter(
    message: str,
    attachments: List[Dict[str, Any]],
    *,
    has_request_intent: bool = False,
    requests_cover_letter: bool = False,
) -> bool:
    """Decide whether a user message warrants producing a full cover letter draft."""
    normalized = " ".join(message.lower().split())
    if not normalized:
        return False

    explicit_phrases = [
        "cover letter",
        "cover-letter",
        "application letter",
    ]
    if any(phrase in normalized for phrase in explicit_phrases):
        return True

    request_verbs = ["write", "draft", "create", "craft", "prepare", "generate"]
    if any(verb in normalized for verb in request_verbs) and "letter" in normalized:
        return True

    if looks_like_job_description(message):
        return requests_cover_letter or has_request_intent

    if attachments and any(verb in normalized for verb in request_verbs):
        return True

    return False


def is_providing_requested_info(message: str, conversation_history: List[str]) -> bool:
    """
    Detect if user is providing information that was previously requested.
    
    This helps identify when users respond to requests for company name,
    job details, or other missing information needed for PDF generation.
    
    Args:
        message: The current user message
        conversation_history: Previous messages in the conversation
    
    Returns:
        True if the message appears to be providing requested information
    """
    if not conversation_history:
        return False
    
    # Check if assistant recently asked for information
    recent_messages = conversation_history[-5:]  # Last 5 messages
    assistant_asked_pattern = [
        "need",
        "provide",
        "share",
        "could you",
        "can you",
        "please provide",
        "what is",
        "which company",
        "tell me about",
        "missing",
    ]
    
    assistant_asked_for_info = any(
        any(pattern in msg.lower() for pattern in assistant_asked_pattern)
        for msg in recent_messages
        if msg.startswith("ASSISTANT:")
    )
    
    if not assistant_asked_for_info:
        return False
    
    # Check if current message is providing information (not a question or command)
    normalized = message.lower().strip()
    
    # Short messages with company names or details
    if len(message.split()) < 50 and not normalized.startswith(("can you", "could you", "please", "i want", "i need")):
        return True
    
    return False


def build_fallback_reply(should_draft: bool, has_attachments: bool, has_job_description: bool = False) -> str:
    """Return the non-LLM fallback response based on available context."""
    if should_draft:
        lines = [
            "Working on your cover letter request.",
            "I'll incorporate your uploaded materials while drafting the letter." if has_attachments else "Upload your resume to help me personalize the cover letter.",
        ]
    else:
        lines = [
            "Hi! I'm ApplyWise, your cover letter co-pilot.",
            "Share a job description when you're ready and I'll draft a tailored cover letter for you.",
            "You can upload your resume for more personalization." if not has_attachments else "I have your materials; send the job details or ask for tips when you're ready.",
        ]
        if has_job_description:
            lines.append("I've saved the role details you shared; just tell me when to start drafting.")

    return "\n".join(lines)


def detect_pdf_request(message: str) -> Optional[str]:
    """
    Detect PDF creation requests from user input with enhanced trigger detection.
    
    This function uses case-insensitive matching to identify when users want to
    generate PDFs, including variations like "can you pdf this?" or "pdf please".
    
    Trigger phrases include:
    - Direct requests: "create pdf", "make pdf", "generate pdf", "build pdf"
    - Action requests: "print to pdf", "export to pdf", "save as pdf", "download pdf"
    - Conversion requests: "convert to pdf", "pdf this", "give me a pdf"
    - Short forms: "pdf please", "can you pdf this?", "pdf it"
    
    Returns:
        - "cover_letter" if requesting a cover letter PDF
        - "resume" if requesting a resume/CV PDF
        - None if no PDF request detected
    """
    normalized = " ".join((message or "").lower().split())
    if not normalized:
        return None
    
    # Comprehensive PDF request patterns (case-insensitive)
    pdf_patterns = [
        # Explicit PDF actions
        "create pdf",
        "make pdf",
        "generate pdf",
        "build pdf",
        "draft pdf",
        "write pdf",
        "produce pdf",
        
        # With articles
        "create a pdf",
        "make a pdf",
        "generate a pdf",
        "build a pdf",
        "draft a pdf",
        "write a pdf",
        
        # Action + to/as/in + pdf
        "print to pdf",
        "export to pdf",
        "save as pdf",
        "save to pdf",
        "download pdf",
        "download as pdf",
        "convert to pdf",
        "turn into pdf",
        "change to pdf",
        
        # PDF + noun combinations
        "pdf version",
        "pdf format",
        "pdf file",
        "pdf copy",
        "pdf document",
        
        # Short imperative forms
        "pdf",
        "pdf this",
        "pdf it",
        "pdf please",
        "pdf now",
        "pdf that",
        
        # Question forms
        "can you pdf",
        "could you pdf",
        "will you pdf",
        "would you pdf",
        "please pdf",
        
        # General file requests (often mean PDF)
        "create file",
        "make file",
        "generate file",
        "download file",
        "export file",
        "save file",
        "create a file",
        "make a file",
        "generate a file",
        "download a file",
        "export a file",
        "save a file",
        
        # Positional variants
        "as pdf",
        "to pdf",
        "in pdf",
        "into pdf",
    ]
    
    # Check if any explicit PDF/file request pattern is present
    has_pdf_request = any(pattern in normalized for pattern in pdf_patterns)
    
    if not has_pdf_request:
        return None

    # Determine what type of PDF to generate based on context
    if any(term in normalized for term in ("resume", "cv", "curriculum vitae")):
        return "resume"

    if any(phrase in normalized for phrase in ("cover letter", "cover-letter", "coverletter", "application letter")):
        return "cover_letter"

    # Default to cover letter for generic PDF requests
    # (most common use case in this application)
    return "cover_letter"


def detect_resume_review_request(message: str) -> bool:
    """
    Detect if the user is asking for resume review or feedback.
    
    Returns True if the message appears to request resume review, critique, or feedback.
    """
    normalized = " ".join((message or "").lower().split())
    if not normalized:
        return False
    
    # Resume/CV identifiers
    resume_terms = ("resume", "cv", "curriculum vitae")
    has_resume_term = any(term in normalized for term in resume_terms)
    
    # Review/feedback actions
    review_patterns = [
        "review",
        "critique",
        "feedback",
        "look at",
        "check",
        "evaluate",
        "assess",
        "analyze",
        "improve",
        "suggestions",
        "advice",
        "help with",
        "tips",
        "enhance",
        "optimize",
        "fix",
        "better",
        "stronger",
        "thoughts on",
        "opinion on",
        "what do you think",
    ]
    
    has_review_action = any(pattern in normalized for pattern in review_patterns)
    
    # Specific phrases that indicate resume review
    specific_phrases = [
        "review my resume",
        "review the resume",
        "look at my resume",
        "check my resume",
        "feedback on my resume",
        "thoughts on my resume",
        "help with my resume",
        "improve my resume",
        "make my resume better",
        "resume feedback",
        "resume review",
        "resume advice",
        "resume tips",
        "resume suggestions",
        "what do you think of my resume",
        "can you review",
        "could you review",
        "please review",
    ]
    
    has_specific_phrase = any(phrase in normalized for phrase in specific_phrases)
    
    # Return True if we have both a resume term and review action, OR a specific phrase
    return (has_resume_term and has_review_action) or has_specific_phrase
