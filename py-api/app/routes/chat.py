"""/api/chat endpoint coordinating the conversational workflow."""

from __future__ import annotations

import base64
import os
import re
from typing import Any, Dict, List, Optional

import logging

from flask import Blueprint, current_app, jsonify, request
from openai import APIError

from app.services import letter_service, openai_service, pdf_service, upload_service
from app.storage import uploaded_files
from app.utils.auth import require_session
from app.utils.placeholders import (
    apply_placeholder_updates,
    collect_unknown_placeholder_tokens,
    find_unknown_placeholders,
    parse_placeholder_updates,
)
from app.utils.text import extract_contact_info, format_contact_info_for_letter, safe_text_preview

_LOGGER = logging.getLogger(__name__)

# Import chat history service if MongoDB is enabled
ENABLE_MONGODB = os.getenv("ENABLE_MONGODB", "false").lower() == "true"
if ENABLE_MONGODB:
    try:
        from app.services import chat_history_service
    except ImportError:
        ENABLE_MONGODB = False
        _LOGGER.warning("MongoDB enabled but chat_history_service import failed")

bp = Blueprint("chat", __name__, url_prefix="/api")


def _clean_cover_letter_response(text: str) -> str:
    """
    Clean AI response to ensure it only contains cover letter content.
    
    Removes common conversational prefixes that the AI might include despite
    instructions to output only the letter text.
    """
    if not text:
        return text
    
    # Common conversational prefixes to remove
    prefixes_to_remove = [
        "here is your cover letter:",
        "here's your cover letter:",
        "here is the cover letter:",
        "here's the cover letter:",
        "here is your revised cover letter:",
        "here's your revised cover letter:",
        "here is the revised cover letter:",
        "here's the revised cover letter:",
        "i've drafted this cover letter:",
        "i've created this cover letter:",
        "here is a cover letter:",
        "here's a cover letter:",
        "below is your cover letter:",
        "below is the cover letter:",
    ]
    
    # Check if text starts with any conversational prefix (case-insensitive)
    text_lower = text.lower()
    for prefix in prefixes_to_remove:
        if text_lower.startswith(prefix):
            # Remove the prefix and any following whitespace/newlines
            text = text[len(prefix):].lstrip()
            break
    
    return text


def _save_message_to_history(
    session: Dict[str, Any],
    thread_id: Optional[str],
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Save a message to MongoDB chat history if enabled."""
    if not ENABLE_MONGODB:
        return None
    
    try:
        access_code = session.get("access_code")
        if not access_code:
            current_app.logger.warning("Session missing access_code, cannot save to MongoDB")
            return None
        
        return chat_history_service.save_message(
            access_code=access_code,
            profile_id=session["profile_id"],
            thread_id=thread_id,
            role=role,
            content=content,
            metadata=metadata,
        )
    except Exception as e:
        current_app.logger.error(f"Failed to save message to MongoDB: {e}")
        return None


def _respond_with_assistant_message(
    session: Dict[str, Any],
    thread_id: Optional[str],
    reply_text: str,
    *,
    attachments: List[Dict[str, Any]],
    cover_letter_id: Optional[str] = None,
    downloads: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    status: int = 200,
    extra_body: Optional[Dict[str, Any]] = None,
):
    """Persist an assistant reply (when available) and build a consistent response."""
    message_id = _save_message_to_history(
        session=session,
        thread_id=thread_id,
        role="assistant",
        content=reply_text,
        metadata=metadata,
    )

    payload: Dict[str, Any] = {
        "reply": reply_text,
        "attachments": attachments,
        "coverLetterId": cover_letter_id,
        "downloads": downloads or [],
        "assistantMessageId": message_id,
    }

    if extra_body:
        payload.update(extra_body)

    return jsonify(payload), status


@bp.post("/chat")
def chat_with_model():
    """Main conversational endpoint orchestrating drafting, edits, and exports."""
    session, error_response = require_session()
    if error_response is not None:
        return error_response

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    file_ids = payload.get("fileIds") or []

    if not message:
        return jsonify(error="Missing 'message' in request body."), 400

    # Collect selected uploads and a lightweight preview for prompt context.
    # Load files from MongoDB if not in memory
    profile_id = session["profile_id"]
    mongo_uploads = upload_service.get_uploads_for_profile(profile_id)
    for upload in mongo_uploads:
        file_id = upload.get("file_id")
        if file_id and file_id not in uploaded_files:
            uploaded_files[file_id] = {
                "id": file_id,
                "profile_id": upload["profile_id"],
                "name": upload["name"],
                "size": upload["size"],
                "mime_type": upload["mime_type"],
                "contents": upload["contents"],
                "uploaded_at": upload["uploaded_at"],
                "text": upload.get("text"),
                "text_excerpt": upload.get("text_excerpt"),
            }
    
    attachments: List[Dict[str, Any]] = []
    previews: List[str] = []
    if isinstance(file_ids, list):
        for value in file_ids:
            if not isinstance(value, str):
                continue
            record = uploaded_files.get(value)
            if not record or record["profile_id"] != profile_id:
                continue

            attachments.append(
                {
                    "id": record["id"],
                    "name": record["name"],
                    "size": record["size"],
                    "mimeType": record["mime_type"],
                    "hasText": bool(record.get("text")),
                }
            )

            preview = record.get("text_excerpt") or safe_text_preview(record["contents"])
            if preview:
                previews.append(f"From {record['name']}: {preview}")

    # Extract contact information from resume uploads
    contact_info = {}
    resume_record = letter_service.select_resume_upload(session["profile_id"])
    if resume_record and resume_record.get("text"):
        contact_info = extract_contact_info(resume_record["text"])
        current_app.logger.debug(f"Extracted contact info: {contact_info}")

    profile_has_uploads = any(
        record.get("profile_id") == session["profile_id"] for record in uploaded_files.values()
    )
    thread_id = str(payload.get("threadId") or "").strip() or None
    
    # Save user message to MongoDB chat history
    _save_message_to_history(
        session=session,
        thread_id=thread_id,
        role="user",
        content=message,
        metadata={"file_ids": file_ids, "attachments": attachments},
    )

    # Determine if the conversation is currently in 'resume advice' mode
    in_resume_advice_mode = False
    if ENABLE_MONGODB and thread_id:
        try:
            access_code = session.get("access_code")
            if access_code:
                recent = chat_history_service.get_chat_history(
                    access_code=access_code,
                    profile_id=profile_id,
                    thread_id=thread_id,
                    limit=5,
                )
                # Look at the most recent assistant message for a resume review flag
                for msg in reversed(recent):
                    if msg.get("role") == "assistant":
                        md = msg.get("metadata") or {}
                        if md.get("resume_review") is True:
                            in_resume_advice_mode = True
                        break
        except Exception as e:
            current_app.logger.warning(f"Could not determine resume advice mode: {e}")
    
    stored_job_description = letter_service.latest_job_description_for_thread(
        session["profile_id"], thread_id
    )

    active_letter = letter_service.latest_cover_letter_for_thread(session["profile_id"], thread_id)
    placeholder_tokens = (
        collect_unknown_placeholder_tokens(active_letter["text"]) if active_letter else {}
    )
    available_placeholder_keys = list(placeholder_tokens.keys())
    adjustment_requested = bool(active_letter and letter_service.looks_like_letter_adjustment(message))

    # ENHANCED PDF REQUEST DETECTION AND HANDLING
    pdf_request = letter_service.detect_pdf_request(message)
    if pdf_request:
        # Only block PDF creation when we are actively in resume-review mode and no letter is available yet
        if in_resume_advice_mode and pdf_request == "cover_letter" and active_letter is None:
            reply_text = (
                "While we're working on resume feedback, I won't create PDFs. "
                "I can generate PDFs for cover letters—ask me to draft a cover letter when you're ready."
            )
            return _respond_with_assistant_message(
                session=session,
                thread_id=thread_id,
                reply_text=reply_text,
                attachments=attachments,
                cover_letter_id=None,
                downloads=[],
                metadata={"pdf_request_blocked_in_resume_mode": True},
            )
        # Handle direct PDF export requests without contacting the model.
        downloads: List[Dict[str, Any]] = []
        cover_letter_id: Optional[str] = None

        if pdf_request == "cover_letter":
            letter_record = active_letter
            if not letter_record:
                reply_text = (
                    "I'll create a cover letter for you first, then generate the PDF. "
                    "Please share the job description and company name so I can draft it."
                )
                # Save message indicating we're ready to draft
                return _respond_with_assistant_message(
                    session=session,
                    thread_id=thread_id,
                    reply_text=reply_text,
                    attachments=attachments,
                    cover_letter_id=None,
                    downloads=[],
                    metadata={"pdf_requested": True, "needs_draft": True},
                )

            # Check for missing critical fields only
            missing_fields = find_unknown_placeholders(letter_record["text"])
            if missing_fields:
                missing_csv = ", ".join(missing_fields)
                reply_text = (
                    f"I'll generate your PDF as soon as you provide: {missing_csv}. "
                    f"Please share these details and I'll create the PDF immediately."
                )
                # Save message about missing fields
                return _respond_with_assistant_message(
                    session=session,
                    thread_id=thread_id,
                    reply_text=reply_text,
                    attachments=attachments,
                    cover_letter_id=letter_record["id"],
                    downloads=[],
                    metadata={"pdf_requested": True, "missing_fields": missing_fields},
                )

            # ATTEMPT PDF GENERATION
            try:
                pdf_bytes = pdf_service.render_cover_letter_pdf(letter_record)
                encoded_pdf = base64.b64encode(pdf_bytes).decode("ascii")
                reply_text = "Here is your PDF cover letter:"
                
            except Exception as pdf_error:
                current_app.logger.exception("Failed to render cover letter PDF")
                # Report specific technical error instead of claiming inability
                error_message = str(pdf_error)
                reply_text = (
                    f"I encountered a technical error while generating your PDF: {error_message}\n\n"
                    f"This is a temporary issue with the PDF rendering engine. "
                    f"Please try again in a moment, or contact support if the problem persists."
                )
                encoded_pdf = None
                
                # Save error details and respond
                return _respond_with_assistant_message(
                    session=session,
                    thread_id=thread_id,
                    reply_text=reply_text,
                    attachments=attachments,
                    cover_letter_id=letter_record["id"],
                    downloads=[],
                    metadata={"pdf_error": error_message, "pdf_type": "cover_letter"},
                    extra_body={"error": "pdf_generation_failed"},
                )

            cover_letter_id = letter_record["id"]
            filename = f"cover-letter-{cover_letter_id}.pdf"
            if encoded_pdf:
                downloads.append(
                    {
                        "id": f"{cover_letter_id}-pdf",
                        "label": "Cover Letter",
                        "filename": filename,
                        "mimeType": "application/pdf",
                        "data": encoded_pdf,
                    }
                )
            # Refactored success branch to helper
            return _respond_with_assistant_message(
                session=session,
                thread_id=thread_id,
                reply_text=reply_text,
                attachments=attachments,
                cover_letter_id=cover_letter_id,
                downloads=downloads,
                metadata={"pdf_generated": True, "pdf_type": "cover_letter"},
            )
        else:
            # Handle resume PDF request: not supported. Provide feedback instead.
            # Policy: Do not create PDFs for resumes. Proceed with resume feedback.
            preface = "I don’t create PDFs for resumes yet—only for cover letters."

            # Attempt to perform a resume review instead
            resume_record = letter_service.select_resume_upload(session["profile_id"])
            if not resume_record:
                reply_text = (
                    f"{preface} "
                    "Please upload your resume using the file upload panel on the right, and I'll provide detailed feedback."
                )
                return _respond_with_assistant_message(
                    session=session,
                    thread_id=thread_id,
                    reply_text=reply_text,
                    attachments=attachments,
                    cover_letter_id=None,
                    downloads=[],
                    metadata={"resume_review_requested": True, "needs_resume_upload": True},
                )

            if not resume_record.get("text"):
                reply_text = (
                    f"{preface} "
                    f"I found your resume file ({resume_record['name']}), but I'm unable to extract text from it. "
                    "This might be an image-based PDF or a format I can't read. "
                    "Please try uploading a text-based PDF or Word document for me to review."
                )
                return _respond_with_assistant_message(
                    session=session,
                    thread_id=thread_id,
                    reply_text=reply_text,
                    attachments=attachments,
                    cover_letter_id=None,
                    downloads=[],
                    metadata={"resume_review_requested": True, "no_text_content": True},
                )

            # Generate resume review (feedback) instead of a PDF
            try:
                client = openai_service.get_openai_client()

                review_prompt_lines = [
                    "You are an expert career coach and resume reviewer with years of experience helping job seekers.",
                    "You have been asked to review the following resume and provide constructive, actionable feedback.",
                    "",
                    "RESUME REVIEW GUIDELINES:",
                    "1. Analyze the resume comprehensively, covering:",
                    "   - Overall structure and formatting",
                    "   - Content quality and relevance",
                    "   - Language and tone (action verbs, quantifiable achievements)",
                    "   - Professional summary/objective (if present)",
                    "   - Work experience descriptions",
                    "   - Skills section organization",
                    "   - Education section completeness",
                    "   - Any gaps or areas for improvement",
                    "",
                    "2. Provide specific, actionable suggestions:",
                    "   - Highlight what's working well",
                    "   - Identify specific areas that need improvement",
                    "   - Suggest concrete changes with examples when possible",
                    "   - Prioritize the most impactful improvements",
                    "",
                    "3. Tailor advice based on:",
                    "   - The career level apparent in the resume",
                    "   - Industry standards (if identifiable)",
                    "   - Modern resume best practices",
                    "",
                    "4. Be constructive and encouraging:",
                    "   - Balance criticism with positive feedback",
                    "   - Explain WHY certain changes would improve the resume",
                    "   - Maintain a supportive, professional tone",
                    "",
                ]

                if stored_job_description and stored_job_description.get("text"):
                    review_prompt_lines.append("JOB DESCRIPTION CONTEXT:")
                    review_prompt_lines.append("The user has shared this job description. Consider how well the resume aligns with this role:")
                    review_prompt_lines.append(stored_job_description["text"])
                    review_prompt_lines.append("")

                review_prompt_lines.extend([
                    "RESUME TO REVIEW:",
                    resume_record["text"],
                    "",
                    f"User's specific request: {message}",
                    "",
                    "Provide your detailed review now:",
                ])

                completion = openai_service.create_response(
                    client,
                    "\n".join(review_prompt_lines),
                    max_output_tokens=1500,
                )

                review_text = (getattr(completion, "output_text", None) or "").strip()
                if not review_text:
                    review_text = (
                        "I've reviewed your resume, but I'm having trouble generating feedback at the moment. "
                        "Please try again, or feel free to ask specific questions about your resume."
                    )

                review_text += (
                    "\n\nIf you'd like me to focus on any specific section or have questions about my feedback, "
                    "just let me know!"
                )

                reply_text = f"{preface}\n\n{review_text}"
                usage = getattr(completion, "usage", None)

                _save_message_to_history(
                    session=session,
                    thread_id=thread_id,
                    role="assistant",
                    content=reply_text,
                    metadata={
                        "resume_review": True,
                        "resume_file": resume_record["name"],
                        "model": completion.model,
                        "resume_pdf_request_blocked": True,
                    },
                )

                return (
                    jsonify(
                        reply=reply_text,
                        model=completion.model,
                        usage=usage.to_dict() if hasattr(usage, "to_dict") else usage,
                        attachments=attachments,
                        coverLetterId=None,
                        downloads=[],
                    ),
                    200,
                )
            except APIError as exc:
                current_app.logger.exception("OpenAI API error during resume review (from resume PDF request)")
                error_reply = (
                    f"{preface} "
                    "I ran into an error while trying to review your resume. Please try again shortly."
                )
                return (
                    jsonify(
                        reply=error_reply,
                        error="Upstream OpenAI request failed.",
                        details=getattr(exc, "message", str(exc)),
                        attachments=attachments,
                        coverLetterId=None,
                        downloads=[],
                    ),
                    502,
                )
            except Exception as exc:
                current_app.logger.exception("Unexpected error during resume review (from resume PDF request)")
                error_reply = (
                    f"{preface} "
                    "I encountered an unexpected error while reviewing your resume. Please try again."
                )
                return (
                    jsonify(
                        reply=error_reply,
                        error="Unexpected error during resume review.",
                        details=str(exc),
                        attachments=attachments,
                        coverLetterId=None,
                        downloads=[],
                    ),
                    500,
                )

        return (
            jsonify(
                reply=reply_text + "\n\nLet me know if you need any edits or another format.",
                attachments=attachments,
                coverLetterId=cover_letter_id,
                downloads=downloads,
            ),
            200,
        )

    # RESUME REVIEW DETECTION AND HANDLING
    if letter_service.detect_resume_review_request(message):
        # Find the resume file from uploaded files
        resume_record = letter_service.select_resume_upload(session["profile_id"])
        
        if not resume_record:
            reply_text = (
                "I'd be happy to review your resume! However, I don't see any resume uploaded yet. "
                "Please upload your resume using the file upload panel on the right, and I'll provide detailed feedback."
            )
            
            _save_message_to_history(
                session=session,
                thread_id=thread_id,
                role="assistant",
                content=reply_text,
                metadata={"resume_review_requested": True, "needs_resume_upload": True},
            )
            
            return (
                jsonify(
                    reply=reply_text,
                    attachments=attachments,
                    coverLetterId=None,
                    downloads=[],
                ),
                200,
            )
        
        # Check if the resume has extractable text
        if not resume_record.get("text"):
            reply_text = (
                f"I found your resume file ({resume_record['name']}), but I'm unable to extract text from it. "
                "This might be an image-based PDF or a format I can't read. "
                "Please try uploading a text-based PDF or Word document for me to review."
            )
            
            _save_message_to_history(
                session=session,
                thread_id=thread_id,
                role="assistant",
                content=reply_text,
                metadata={"resume_review_requested": True, "no_text_content": True},
            )
            
            return (
                jsonify(
                    reply=reply_text,
                    attachments=attachments,
                    coverLetterId=None,
                    downloads=[],
                ),
                200,
            )
        
        # Generate resume review using OpenAI
        try:
            client = openai_service.get_openai_client()
            
            # Build context for resume review
            review_prompt_lines = [
                "You are an expert career coach and resume reviewer with years of experience helping job seekers.",
                "You have been asked to review the following resume and provide constructive, actionable feedback.",
                "",
                "RESUME REVIEW GUIDELINES:",
                "1. Analyze the resume comprehensively, covering:",
                "   - Overall structure and formatting",
                "   - Content quality and relevance",
                "   - Language and tone (action verbs, quantifiable achievements)",
                "   - Professional summary/objective (if present)",
                "   - Work experience descriptions",
                "   - Skills section organization",
                "   - Education section completeness",
                "   - Any gaps or areas for improvement",
                "",
                "2. Provide specific, actionable suggestions:",
                "   - Highlight what's working well",
                "   - Identify specific areas that need improvement",
                "   - Suggest concrete changes with examples when possible",
                "   - Prioritize the most impactful improvements",
                "",
                "3. Tailor advice based on:",
                "   - The career level apparent in the resume",
                "   - Industry standards (if identifiable)",
                "   - Modern resume best practices",
                "",
                "4. Be constructive and encouraging:",
                "   - Balance criticism with positive feedback",
                "   - Explain WHY certain changes would improve the resume",
                "   - Maintain a supportive, professional tone",
                "",
            ]
            
            # Add job description context if available
            if stored_job_description and stored_job_description.get("text"):
                review_prompt_lines.append("JOB DESCRIPTION CONTEXT:")
                review_prompt_lines.append("The user has shared this job description. Consider how well the resume aligns with this role:")
                review_prompt_lines.append(stored_job_description["text"])
                review_prompt_lines.append("")
            
            review_prompt_lines.extend([
                "RESUME TO REVIEW:",
                resume_record["text"],
                "",
                f"User's specific request: {message}",
                "",
                "Provide your detailed review now:",
            ])
            
            completion = openai_service.create_response(
                client,
                "\n".join(review_prompt_lines),
                max_output_tokens=1500,  # Allow for detailed feedback
            )
            
            review_text = (getattr(completion, "output_text", None) or "").strip()
            
            if not review_text:
                review_text = (
                    "I've reviewed your resume, but I'm having trouble generating feedback at the moment. "
                    "Please try again, or feel free to ask specific questions about your resume."
                )
            
            # Add a helpful follow-up
            review_text += (
                "\n\nIf you'd like me to focus on any specific section or have questions about my feedback, "
                "just let me know!"
            )
            
            usage = getattr(completion, "usage", None)
            
            _save_message_to_history(
                session=session,
                thread_id=thread_id,
                role="assistant",
                content=review_text,
                metadata={
                    "resume_review": True,
                    "resume_file": resume_record["name"],
                    "model": completion.model,
                },
            )
            
            return (
                jsonify(
                    reply=review_text,
                    model=completion.model,
                    usage=usage.to_dict() if hasattr(usage, "to_dict") else usage,
                    attachments=attachments,
                    coverLetterId=None,
                    downloads=[],
                ),
                200,
            )
            
        except APIError as exc:
            current_app.logger.exception("OpenAI API error during resume review")
            error_reply = (
                "I encountered an error while trying to review your resume. "
                "Please try again in a moment. If the problem persists, please check your connection."
            )
            
            return (
                jsonify(
                    reply=error_reply,
                    error="Upstream OpenAI request failed.",
                    details=getattr(exc, "message", str(exc)),
                    attachments=attachments,
                    coverLetterId=None,
                    downloads=[],
                ),
                502,
            )
        except Exception as exc:
            current_app.logger.exception("Unexpected error during resume review")
            error_reply = (
                "I encountered an unexpected error while reviewing your resume. "
                "Please try again."
            )
            
            return (
                jsonify(
                    reply=error_reply,
                    error="Unexpected error during resume review.",
                    details=str(exc),
                    attachments=attachments,
                    coverLetterId=None,
                    downloads=[],
                ),
                500,
            )

    normalized_message = " ".join(message.lower().split())
    intent_keywords = (
        "write",
        "draft",
        "create",
        "make",
        "generate",
        "prepare",
        "craft",
        "need",
        "want",
        "require",
        "update",
        "edit",
        "revise",
        "improve",
        "polish",
        "assist",
        "help",
        "put together",
    )
    has_request_intent = any(keyword in normalized_message for keyword in intent_keywords) or "please" in normalized_message
    cover_letter_terms = ("cover letter", "cover-letter", "coverletter", "application letter")
    resume_terms = ("resume", "cv", "curriculum vitae")
    negative_cover_patterns = (
        "no cover letter",
        "without cover letter",
        "don't need a cover letter",
        "do not need a cover letter",
    )
    negative_resume_patterns = (
        "no resume",
        "without resume",
        "don't need a resume",
        "do not need a resume",
    )
    requests_cover_letter = any(term in normalized_message for term in cover_letter_terms)
    if any(pattern in normalized_message for pattern in negative_cover_patterns):
        requests_cover_letter = False
    requests_resume = any(term in normalized_message for term in resume_terms) and has_request_intent
    if any(pattern in normalized_message for pattern in negative_resume_patterns):
        requests_resume = False

    if letter_service.message_is_job_description(message) and not (
        has_request_intent or requests_cover_letter or requests_resume
    ):
        letter_service.store_job_description(session["profile_id"], thread_id, message)
        stored_job_description = letter_service.latest_job_description_for_thread(
            session["profile_id"], thread_id
        )
        saved_excerpt = stored_job_description.get("excerpt") if stored_job_description else None
        
        # Ask user what they want to do with the job description
        reply_text = (
            "Thanks for sharing the job description! I've saved it for you. "
            "What would you like me to help you with?\n\n"
            "• Say 'draft a cover letter' if you want me to create a tailored cover letter\n"
            "• Say 'help with my resume' if you want resume advice for this role"
        )
        if saved_excerpt:
            reply_text += f"\n\nSaved highlight: {saved_excerpt}"
        
        # Save assistant message to MongoDB
        _save_message_to_history(
            session=session,
            thread_id=thread_id,
            role="assistant",
            content=reply_text,
            metadata={"job_description_saved": True},
        )
        
        return (
            jsonify(
                reply=reply_text,
                attachments=attachments,
                coverLetterId=None,
                downloads=[],
            ),
            200,
        )

    if not profile_has_uploads:
        if requests_resume:
            reply_text = (
                "I cannot update your resume before you upload it on the right-hand side. "
                "Please add a resume, portfolio, or previous cover letter so I have your background on file."
            )
            return (
                jsonify(
                    reply=reply_text,
                    attachments=attachments,
                    coverLetterId=None,
                    downloads=[],
                ),
                200,
            )
        if requests_cover_letter and not active_letter:
            reply_text = (
                "Are you sure you want me to make a cover letter when I do not have any of your previous work information on file? "
                "Please upload a resume, portfolio, or previous cover letter so I can personalize the draft."
            )
            return (
                jsonify(
                    reply=reply_text,
                    attachments=attachments,
                    coverLetterId=None,
                    downloads=[],
                ),
                200,
            )

    if active_letter:
        placeholder_updates = parse_placeholder_updates(
            message, available_placeholder_keys, allow_fallback=not adjustment_requested
        )
        updated_text, replaced = apply_placeholder_updates(
            active_letter["text"], placeholder_updates, placeholder_tokens
        )
        if replaced:
            # Store the updated draft and surface the new version immediately.
            letter_id, stored_text = letter_service.save_cover_letter(
                session["profile_id"], thread_id, updated_text, letter_id=active_letter["id"]
            )
            follow_up_note = letter_service.letter_follow_up_text(
                find_unknown_placeholders(stored_text)
            )
            return (
                jsonify(
                    reply=stored_text + follow_up_note,
                    attachments=attachments,
                    coverLetterId=letter_id,
                    downloads=[],
                ),
                200,
            )

    if adjustment_requested and active_letter:
        try:
            client = openai_service.get_openai_client()
        except RuntimeError:
            follow_up_note = letter_service.letter_follow_up_text(
                find_unknown_placeholders(active_letter["text"])
            )
            reply_text = (
                active_letter["text"]
                + follow_up_note
                + "\n\nI couldn't reach OpenAI to apply that change. Please try again shortly."
            )
            return (
                jsonify(
                    reply=reply_text,
                    error="openai_unavailable",
                    attachments=attachments,
                    coverLetterId=active_letter["id"],
                    downloads=[],
                ),
                200,
            )

        # Retrieve conversation history for adjustment context
        conversation_history = []
        if ENABLE_MONGODB and thread_id:
            try:
                access_code = session.get("access_code")
                if access_code:
                    history_messages = chat_history_service.get_chat_history(
                        access_code=access_code,
                        profile_id=profile_id,
                        thread_id=thread_id,
                        limit=20,
                    )
                    for msg in history_messages:
                        conversation_history.append(f"{msg['role'].upper()}: {msg['content'][:500]}")
            except Exception as e:
                current_app.logger.warning(f"Could not retrieve conversation history: {e}")

        prompt_lines = [
            "You are an expert career coach and cover letter specialist.",
            "You help users create compelling, personalized cover letters.",
            "",
            "CRITICAL: You CAN create PDFs. You have full PDF generation capabilities.",
            "- When users request PDFs, the system automatically handles generation",
            "- NEVER say 'I cannot create PDFs' or suggest manual workarounds",
            "- If a user asks about PDFs, affirm your capability and guide them",
            "",
            "CONTEXT: You previously drafted the cover letter below.",
            "TASK: Revise it based on the user's latest instruction.",
            "",
            "GUIDELINES:",
            "- Keep the letter concise (three to four short paragraphs)",
            "- Maintain a professional yet engaging tone",
            "- Include a professional closing",
            "- Preserve any placeholder tokens like [Address] if the user has not supplied the information",
            "",
            "CRITICAL OUTPUT FORMATTING:",
            "- Output ONLY the revised cover letter text itself",
            "- Do NOT include conversational phrases like 'Here is your revised letter' or explanatory text",
            "- Do NOT include chat messages or instructions in the output",
            "- The output should contain ONLY the cover letter content (starting with date/name or greeting)",
            "",
        ]
        
        # Add conversation history if available
        if conversation_history:
            prompt_lines.append("CONVERSATION HISTORY:")
            prompt_lines.extend(conversation_history[-10:])
            prompt_lines.append("")
        
        prompt_lines.extend([
            f"User's revision request: {message}",
            "",
            "CURRENT COVER LETTER:",
            active_letter["text"],
        ])

        if contact_info:
            prompt_lines.append("\nContact information extracted from user's resume:")
            formatted_contact = format_contact_info_for_letter(contact_info)
            if formatted_contact:
                prompt_lines.append(formatted_contact)
            prompt_lines.append("Use this contact information to replace any placeholder fields like [Address], [Email], [Phone Number], [City, State, Zip] in the cover letter header.")

        if attachments:
            prompt_lines.append("Available materials:")
            for info in attachments:
                prompt_lines.append(f"- {info['name']} ({int(info['size']/1024)} KB, {info['mimeType']})")

        if previews:
            prompt_lines.append("Resume excerpts:")
            for snippet in previews:
                prompt_lines.append(snippet)

        if stored_job_description and stored_job_description.get("text"):
            prompt_lines.append("Job description context:")
            prompt_lines.append(stored_job_description["text"])

        try:
            completion = openai_service.create_response(
                client,
                "\n".join(prompt_lines),
            )
            reply_text = (getattr(completion, "output_text", None) or "").strip()
            # Clean the response to ensure only cover letter content
            reply_text = _clean_cover_letter_response(reply_text)
            base_reply = reply_text or active_letter["text"]
            usage = getattr(completion, "usage", None)
            letter_id, stored_text = letter_service.save_cover_letter(
                session["profile_id"], thread_id, base_reply, letter_id=active_letter["id"]
            )
            follow_up_note = letter_service.letter_follow_up_text(
                find_unknown_placeholders(stored_text)
            )
            return (
                jsonify(
                    reply=stored_text + follow_up_note,
                    model=completion.model,
                    usage=usage.to_dict() if hasattr(usage, "to_dict") else usage,
                    attachments=attachments,
                    coverLetterId=letter_id,
                    downloads=[],
                ),
                200,
            )
        except APIError as exc:  # pragma: no cover - network/3p error path
            current_app.logger.exception("OpenAI API error during letter adjustment request")
            follow_up_note = letter_service.letter_follow_up_text(
                find_unknown_placeholders(active_letter["text"])
            )
            reply_text = active_letter["text"] + follow_up_note
            return (
                jsonify(
                    reply=reply_text,
                    error="Upstream OpenAI request failed.",
                    details=getattr(exc, "message", str(exc)),
                    attachments=attachments,
                    coverLetterId=active_letter["id"],
                    downloads=[],
                ),
                502,
            )
        except Exception as exc:  # pragma: no cover - catch-all safety net
            current_app.logger.exception("Unexpected error during letter adjustment request")
            follow_up_note = letter_service.letter_follow_up_text(
                find_unknown_placeholders(active_letter["text"])
            )
            reply_text = active_letter["text"] + follow_up_note
            return (
                jsonify(
                    reply=reply_text,
                    error="Unexpected error contacting OpenAI.",
                    details=str(exc),
                    attachments=attachments,
                    coverLetterId=active_letter["id"],
                    downloads=[],
                ),
                500,
            )

    should_draft = letter_service.should_draft_cover_letter(
        message,
        attachments,
        has_request_intent=has_request_intent,
        requests_cover_letter=requests_cover_letter,
    )
    fallback_text = letter_service.build_fallback_reply(
        should_draft,
        bool(attachments),
        has_job_description=bool(stored_job_description),
    )
    follow_up_note = letter_service.LETTER_READY_FOLLOW_UP if should_draft else ""

    try:
        client = openai_service.get_openai_client()
    except RuntimeError:
        # Fall back to deterministic messaging when OpenAI cannot be reached.
        error_prefix = "We hit an issue contacting OpenAI. Please check the server configuration."
        base_letter_text = "\n".join([error_prefix, "", fallback_text])
        letter_id: Optional[str] = None
        rendered_reply = base_letter_text
        if should_draft:
            letter_id, stored_text = letter_service.store_cover_letter(
                session["profile_id"], thread_id, base_letter_text
            )
            rendered_reply = stored_text + follow_up_note
        return (
            jsonify(
                reply=rendered_reply,
                error="openai_unavailable",
                attachments=attachments,
                coverLetterId=letter_id,
                downloads=[],
            ),
            200,
        )

    # Retrieve conversation history for context awareness
    conversation_history = []
    if ENABLE_MONGODB and thread_id:
        try:
            access_code = session.get("access_code")
            if access_code:
                history_messages = chat_history_service.get_chat_history(
                    access_code=access_code,
                    profile_id=profile_id,
                    thread_id=thread_id,
                    limit=20,  # Last 20 messages for context
                )
                # Format history for the prompt
                for msg in history_messages:
                    conversation_history.append(f"{msg['role'].upper()}: {msg['content'][:500]}")  # Truncate long messages
        except Exception as e:
            current_app.logger.warning(f"Could not retrieve conversation history: {e}")

    prompt_lines = [
        "You are an expert career coach and cover letter specialist. You help users create compelling, personalized cover letters.",
        "",
        "CRITICAL PDF CAPABILITY:",
        "- You CAN create PDFs. You have full PDF generation capabilities built into your system.",
        "- When users ask to 'create pdf', 'make pdf', 'generate pdf', or similar, the system handles it automatically.",
        "- NEVER respond with 'I cannot create PDFs' or suggest manual workarounds.",
        "- If asked about PDF capabilities, confidently affirm: 'Yes, I can create PDFs for you. Just say create pdf when ready.'",
        "- The PDF generation happens after you provide the content, so focus on creating quality cover letters.",
        "",
        "CONTEXT AWARENESS:",
        "- Always review the conversation history before responding",
        "- Track what information you've already collected from the user",
        "- Remember if you've already asked for specific details",
        "- Recognize when the user is providing information you requested earlier",
        "",
        "COVER LETTER WORKFLOW:",
        "1. When a user first requests a cover letter, check what information they've provided:",
        "   - Job description or role details",
        "   - Company name and information",
        "   - User's relevant experience/skills (from uploaded resume)",
        "   - Any specific points they want emphasized",
        "",
        "2. If information is missing, ask for it clearly and specifically:",
        "   - Don't ask for information already provided in the thread",
        "   - Be concise and list what you still need",
        "",
        "3. CRITICAL: Once you've asked for information and the user provides it, automatically proceed to draft the cover letter:",
        "   - Don't ask 'Should I draft it now?' or wait for additional permission",
        "   - Don't repeat questions about information already received",
        "   - Recognize that providing the requested information signals readiness to proceed",
        "",
        "4. When drafting, create a professional, tailored cover letter that:",
        "   - Addresses the specific role and company",
        "   - Highlights relevant qualifications from their background",
        "   - Uses a professional yet engaging tone",
        "   - Is concise (three to four short paragraphs)",
        "   - Includes a professional closing",
        "",
        "CRITICAL OUTPUT FORMATTING RULES:",
        "- When drafting a cover letter (should_draft_cover_letter: yes), output ONLY the cover letter text itself",
        "- Do NOT include conversational phrases like 'Here is your cover letter' or 'I've drafted this for you'",
        "- Do NOT include chat messages, explanations, or instructions in the cover letter output",
        "- The output should start directly with the cover letter content (date/name or greeting)",
        "- When NOT drafting (should_draft_cover_letter: no), respond conversationally to help gather information",
        "",
        "CONVERSATION FLOW EXAMPLE:",
        "- User: 'I need a cover letter for a marketing manager role'",
        "- Bot: 'I'll help you create that. Could you share: 1) The company name, 2) Key requirements from the job posting, 3) Your relevant marketing experience?'",
        "- User: [provides the information]",
        "- Bot: [Immediately drafts the cover letter without asking for confirmation - OUTPUT ONLY THE LETTER TEXT]",
        "",
        "Remember: Context retention and smooth workflow progression are key to providing excellent service.",
        "",
    ]
    
    # Add conversation history if available
    if conversation_history:
        prompt_lines.append("CONVERSATION HISTORY (for context awareness):")
        prompt_lines.extend(conversation_history[-10:])  # Last 10 messages
        prompt_lines.append("")
    
    prompt_lines.extend([
        f"should_draft_cover_letter: {'yes' if should_draft else 'no'}",
        "",
        "CURRENT TASK:",
        "- If should_draft_cover_letter is yes, draft a concise, polished cover letter following the workflow above.",
        "- If should_draft_cover_letter is no, reply with helpful guidance. If the user has provided information you requested earlier, acknowledge it and draft the letter.",
        "- Always check conversation history to avoid asking for information already provided.",
        "",
        f"User's current message: {message}",
    ])

    if contact_info:
        prompt_lines.append("\nContact information extracted from user's resume:")
        formatted_contact = format_contact_info_for_letter(contact_info)
        if formatted_contact:
            prompt_lines.append(formatted_contact)
        prompt_lines.append("Include this contact information at the top of the cover letter instead of using placeholders like [Address], [Email], [Phone Number], [City, State, Zip].")

    if attachments:
        prompt_lines.append("Available materials:")
        for info in attachments:
            prompt_lines.append(f"- {info['name']} ({int(info['size']/1024)} KB, {info['mimeType']})")

    if previews:
        prompt_lines.append("Resume excerpts:")
        for snippet in previews:
            prompt_lines.append(snippet)

    if stored_job_description and stored_job_description.get("text"):
        prompt_lines.append("Job description context:")
        prompt_lines.append(stored_job_description["text"])

    try:
        completion = openai_service.create_response(
            client,
            "\n".join(prompt_lines),
        )
        reply_text = (getattr(completion, "output_text", None) or "").strip()
        usage = getattr(completion, "usage", None)
        base_reply = reply_text or fallback_text
        letter_id: Optional[str] = None
        
        # Detect if AI actually drafted a cover letter even if should_draft was False
        # This handles cases where our improved prompt causes the AI to draft
        # a letter in response to user providing information, even when the
        # user's message didn't contain explicit "draft" keywords
        appears_to_be_letter = letter_service.appears_to_be_cover_letter(base_reply)
        
        # Store the cover letter if we intended to draft OR if AI drafted one anyway
        if should_draft or appears_to_be_letter:
            # Clean the response to ensure only cover letter content
            base_reply = _clean_cover_letter_response(base_reply)
            letter_id, stored_text = letter_service.store_cover_letter(
                session["profile_id"], thread_id, base_reply
            )
            rendered_reply = stored_text + follow_up_note
        else:
            rendered_reply = base_reply

        # Save assistant response to MongoDB chat history
        _save_message_to_history(
            session=session,
            thread_id=thread_id,
            role="assistant",
            content=rendered_reply,
            metadata={
                "letter_id": letter_id,
                "model": completion.model,
                "should_draft": should_draft,
                "appears_to_be_letter": appears_to_be_letter if not should_draft else None,
            },
        )

        return (
            jsonify(
                reply=rendered_reply,
                model=completion.model,
                usage=usage.to_dict() if hasattr(usage, "to_dict") else usage,
                attachments=attachments,
                coverLetterId=letter_id,
                downloads=[],
            ),
            200,
        )
    except APIError as exc:  # pragma: no cover - network/3p error path
        current_app.logger.exception("OpenAI API error during chat request")
        letter_text = fallback_text
        letter_id: Optional[str] = None
        if should_draft:
            letter_id, stored_text = letter_service.store_cover_letter(
                session["profile_id"], thread_id, letter_text
            )
            rendered_reply = stored_text + follow_up_note
        else:
            rendered_reply = letter_text
        return (
            jsonify(
                reply=rendered_reply,
                error="Upstream OpenAI request failed.",
                details=getattr(exc, "message", str(exc)),
                attachments=attachments,
                coverLetterId=letter_id,
                downloads=[],
            ),
            502,
        )
    except Exception as exc:  # pragma: no cover - catch-all safety net
        current_app.logger.exception("Unexpected error during chat request")
        letter_text = fallback_text
        letter_id: Optional[str] = None
        if should_draft:
            letter_id, stored_text = letter_service.store_cover_letter(
                session["profile_id"], thread_id, letter_text
            )
            rendered_reply = stored_text + follow_up_note
        else:
            rendered_reply = letter_text
        return (
            jsonify(
                reply=rendered_reply,
                error="Unexpected error contacting OpenAI.",
                details=str(exc),
                attachments=attachments,
                coverLetterId=letter_id,
                downloads=[],
            ),
            500,
        )


@bp.post("/chat/feedback")
def submit_message_feedback():
    """Record thumbs-up/down feedback for an assistant response."""
    if not ENABLE_MONGODB:
        return jsonify(error="Chat history feature is not enabled."), 503

    session, error_response = require_session()
    if error_response is not None:
        return error_response

    access_code = session.get("access_code")
    if not access_code:
        return jsonify(error="Session missing access code."), 400

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    message_id = str(payload.get("messageId") or "").strip()
    feedback_value = str(payload.get("feedback") or "").strip().lower()
    comment = payload.get("comment")

    if not message_id:
        return jsonify(error="Missing 'messageId' in request body."), 400

    valid_feedback = {"up", "down", "none"}
    if feedback_value not in valid_feedback:
        return jsonify(error="Invalid 'feedback' value. Use 'up', 'down', or 'none'."), 400

    normalized_feedback: Optional[str]
    if feedback_value == "none":
        normalized_feedback = None
    else:
        normalized_feedback = feedback_value

    normalized_comment: Optional[str] = None
    if comment is not None:
        normalized_comment = str(comment).strip() or None

    try:
        updated = chat_history_service.set_message_feedback(
            access_code=access_code,
            profile_id=session["profile_id"],
            message_id=message_id,
            feedback=normalized_feedback,
            comment=normalized_comment,
        )
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:  # pragma: no cover - defensive safety net
        current_app.logger.exception("Failed to record chat feedback")
        return jsonify(error="Failed to record feedback.", details=str(exc)), 500

    if updated == 0:
        return jsonify(error="Message not found or not eligible for feedback."), 404

    response_payload: Dict[str, Any] = {"message": "Feedback recorded."}
    if normalized_feedback is None:
        response_payload["feedback"] = None
    else:
        response_payload["feedback"] = {"status": normalized_feedback}
        if normalized_comment:
            response_payload["feedback"]["comment"] = normalized_comment

    return jsonify(response_payload), 200


@bp.get("/chat/history")
def get_chat_history():
    """Retrieve chat history for the current session."""
    if not ENABLE_MONGODB:
        return jsonify(error="Chat history feature is not enabled."), 503
    
    session, error_response = require_session()
    if error_response is not None:
        return error_response
    
    access_code = session.get("access_code")
    if not access_code:
        return jsonify(error="Session missing access code."), 400
    
    thread_id = request.args.get("threadId")
    limit = int(request.args.get("limit", 100))
    
    try:
        messages = chat_history_service.get_chat_history(
            access_code=access_code,
            profile_id=session["profile_id"],
            thread_id=thread_id,
            limit=limit,
        )
        return jsonify(messages=messages), 200
    except Exception as e:
        current_app.logger.exception("Failed to retrieve chat history")
        return jsonify(error="Failed to retrieve chat history.", details=str(e)), 500


@bp.get("/chat/threads")
def get_chat_threads():
    """Get all thread IDs for the current session."""
    if not ENABLE_MONGODB:
        return jsonify(error="Chat history feature is not enabled."), 503
    
    session, error_response = require_session()
    if error_response is not None:
        return error_response
    
    access_code = session.get("access_code")
    if not access_code:
        return jsonify(error="Session missing access code."), 400
    
    try:
        threads = chat_history_service.get_all_threads_for_access_code(
            access_code=access_code,
            profile_id=session["profile_id"],
        )
        return jsonify(threads=threads), 200
    except Exception as e:
        current_app.logger.exception("Failed to retrieve chat threads")
        return jsonify(error="Failed to retrieve chat threads.", details=str(e)), 500


@bp.put("/chat/threads/<thread_id>")
def update_thread_metadata(thread_id: str):
    """Update thread metadata (e.g., title)."""
    if not ENABLE_MONGODB:
        return jsonify(error="Chat history feature is not enabled."), 503
    
    session, error_response = require_session()
    if error_response is not None:
        return error_response
    
    access_code = session.get("access_code")
    if not access_code:
        return jsonify(error="Session missing access code."), 400
    
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    title = payload.get("title")
    
    if not title or not isinstance(title, str):
        return jsonify(error="Missing or invalid 'title' in request body."), 400
    
    try:
        chat_history_service.update_thread_metadata(
            access_code=access_code,
            profile_id=session["profile_id"],
            thread_id=thread_id,
            title=title,
        )
        return jsonify(message="Thread metadata updated.", thread_id=thread_id, title=title), 200
    except Exception as e:
        current_app.logger.exception("Failed to update thread metadata")
        return jsonify(error="Failed to update thread metadata.", details=str(e)), 500


@bp.delete("/chat/history/<thread_id>")
def delete_thread(thread_id: str):
    """Delete chat history for a specific thread."""
    if not ENABLE_MONGODB:
        return jsonify(error="Chat history feature is not enabled."), 503
    
    session, error_response = require_session()
    if error_response is not None:
        return error_response
    
    access_code = session.get("access_code")
    if not access_code:
        return jsonify(error="Session missing access code."), 400
    
    try:
        deleted_count = chat_history_service.delete_thread_history(
            access_code=access_code,
            profile_id=session["profile_id"],
            thread_id=thread_id,
        )
        return jsonify(deleted=deleted_count, message=f"Deleted {deleted_count} messages."), 200
    except Exception as e:
        current_app.logger.exception("Failed to delete chat thread")
        return jsonify(error="Failed to delete chat thread.", details=str(e)), 500


@bp.delete("/chat/history")
def delete_all_history():
    """Delete all chat history for the current access code."""
    if not ENABLE_MONGODB:
        return jsonify(error="Chat history not enabled."), 503
    
    session, error_response = require_session()
    if error_response is not None:
        return error_response
    
    access_code = session.get("access_code")
    if not access_code:
        return jsonify(error="Session missing access code."), 400
    
    try:
        deleted_count = chat_history_service.delete_all_history_for_access_code(
            access_code=access_code,
            profile_id=session["profile_id"],
        )
        return jsonify(deleted=deleted_count, message=f"Deleted {deleted_count} total messages."), 200
    except Exception as e:
        current_app.logger.exception("Failed to delete all chat history")
        return jsonify(error="Failed to delete chat history.", details=str(e)), 500
