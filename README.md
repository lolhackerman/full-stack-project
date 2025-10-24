# Cover Letter Generator - AI Chatbot

A simple full-stack application that generates tailored cover letters using AI. Upload your resume/documents, paste a job description, and get a personalized cover letter.

## URL
https://applywise-ten.vercel.app/ 

## Features

- **openAI-Powered Chat**: Conversational interface using OpenAI GPT models
- **Document Upload**: Upload resumes, portfolios, or any relevant documents (PDF, TXT, DOCX)
- **Cover Letter Generation**: Primary use, creates customized cover letters based on your documents and job descriptions
- **PDF Export**: Download generated cover letters as formatted PDFs
- **Resume Review & Feedback**: Get comprehensive, actionable feedback on your resume
- **Persistent Storage**: Chat history and uploads saved to MongoDB
- **Session Management**: Secure access code-based authentication
- **Multi-Threading**: Manage multiple conversations in separate threads

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- MongoDB 
- OpenAI API key

### 1. Backend Setup

```bash
cd py-api
pip install -r requirements.txt
```

Create `.env` file in `py-api/`:
```bash
OPENAI_API_KEY=your_openai_api_key_here
ENABLE_MONGODB=true  # Set to false to disable persistence
MONGODB_URI=mongodb://localhost:27017/ 
```

Run the backend:
```bash
python app.py
```

Backend runs on `http://localhost:5050`

### 2. Frontend Setup

```bash
cd ui
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`

### 3. Access the App

1. Open `http://localhost:5173`
2. Select 'Create New Workspace' to recieve a new code
3. Select Access 'workspace'
3. Upload your documents
4. Paste a job description
5. Get your cover letter!

### 4. Set up MongoDB
1. Instructions in py-api/app/MONGODB_SETUP.md

## Usage

The application supports multiple workflows:

### Resume Review & Feedback

Get comprehensive feedback on your resume:
- Upload your resume (PDF, DOCX, or TXT format)
- Ask: "Review my resume" or "Can you give me feedback on my resume?"
- Optionally share a job description first for targeted feedback
- Receive detailed analysis with actionable suggestions

The AI analyzes:
- Structure and formatting
- Content quality and relevance
- Language and action verbs
- Quantifiable achievements
- Skills organization
- Alignment with job requirements (if job description provided)

### Cover Letter Generation

Create tailored cover letters:
1. Upload your resume and relevant documents
2. Share the job description
3. Ask: "Draft a cover letter"
4. Review and request edits as needed
5. Download as a styled PDF

### Combined Workflow

Get resume feedback AND a tailored cover letter based on role:
1. Upload your resume
2. Share a job description
3. Ask: "Review my resume for this role"
4. Get targeted feedback
5. Ask: "Now draft a cover letter"
6. Download or drag and drop cover letter

## Architecture

```
ui/ (React + TypeScript + Tailwind)
  └── HomePage.tsx - Main chat interface

py-api/ (Flask + Python)
  ├── app/
  │   ├── routes/ - API endpoints (auth, chat, uploads, cover letters)
  │   ├── services/ - Business logic (OpenAI, PDF generation, MongoDB)
  │   └── utils/ - Auth helpers, text processing
  └── app.py - Entry point
```

## Key Technologies

- **Frontend**: React, TypeScript, Tailwind CSS, Vite
- **Backend**: Flask, Python
- **AI**: OpenAI GPT-4
- **Storage**: MongoDB
- **File Processing**: PyPDF, python-docx, FPDF2

## API Endpoints

- `POST /api/auth/verify` - Create/verify access code session
- `POST /api/chat` - Send message and get AI response
- `POST /api/uploads` - Upload documents
- `GET /api/uploads` - List uploaded files
- `DELETE /api/uploads/:id` - Delete a file
- `GET /api/chat/history` - Get chat history from MongoDB
- `DELETE /api/chat/history` - Clear chat history

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | Required |
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017/

## Development Notes

- Files are stored in MongoDB GridFS
- Chat history is tied to access codes (sessions)
- Cover letters are generated with specific formatting for professional output
- Maximum file upload size: 5MB per request

## Stretch goals, Trade-offs & Future Improvements

**Stretch gaols reached**
- Persistance 
- Deployment(Render, Vercel, Atlas)
- User feedback for replies (thumbs up/down)


**Current Trade-offs:**
- Simple access code auth (no passwords/encryption)
- No logic for resume PDF generation/formatting only cover letter
- No socket streaming or walk through steps


**Future Enhancements:**
- Add OAuth/proper authentication
- Implement streaming responses for better UX
- Add cover letter templates/customization
- Add resume PDF generation logic 
- Add email API to schedule follow up emails for applications
- Add rate limiting and usage quotas
- Support more document formats


## Tool documentation

# PDF Generator Tool

## What It Does
- Converts stored cover letter drafts (and, when text is available, resumes) into downloadable PDFs for chat responses.
- Applies fixed styling: Helvetica fonts, brand colors, safe margins, and auto page breaks.

## How It’s Called
- `POST /api/cover-letters/<letter_id>/pdf` (see `py-api/app/routes/cover_letters.py`) returns the PDF for an existing draft after session and placeholder checks.
- Chat handler in `py-api/app/routes/chat.py` requests a PDF via `render_cover_letter_pdf` and embeds the base64 bytes in the reply.

## Implementation Notes
- Core logic in `py-api/app/services/pdf_service.py`.
- `render_cover_letter_pdf` is the primary entry; `_wrap_long_words_for_pdf` and `_latin1_safe` keep text within FPDF limits.
- `render_resume_pdf` is a fallback helper that stops early if no textual content is present.

## Inputs & Data
- Records come from `app.storage.cover_letters` or MongoDB via the letter service and include fields such as `id`, `profile_id`, `name`, `header_date`, `text`, and optional `uploaded_at` or base64 `contents`.

## Dependencies & Ops
- Uses `fpdf2` for PDF rendering and optionally `pyphen` for hyphenation



