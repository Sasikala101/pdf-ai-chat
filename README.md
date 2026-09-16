# PDF AI

A local, privacy-conscious PDF question-answering application built with FastAPI, LangChain, ChromaDB, and Google Gemini.

## What stays local

Uploaded PDF bytes and Chroma vectors are held in server memory only. They are cleared when a document is removed or the server stops. Extracted text is sent to the Gemini API to create embeddings and answer questions, so this application is not fully offline.

## Local setup

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add your Gemini key to `.env`:

```env
GOOGLE_API_KEY=your_key_here
```

Start the application:

```bash
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

## Configuration

Optional `.env` settings:

```env
GEMINI_CHAT_MODEL=gemini-3.6-flash
GEMINI_EMBEDDING_MODEL=models/gemini-embedding-001
```

Current limitations: text-based PDFs only, one PDF per session, no OCR, and sessions are lost when the server restarts.

## Public deployment on Render

The repository includes a `Dockerfile` and `render.yaml` Blueprint.

1. Push the project to a private or public GitHub repository. Never commit `.env`.
2. In Render, choose **New > Blueprint** and connect the repository.
3. When Render prompts for `GOOGLE_API_KEY`, paste the key as a secret.
4. Create the Blueprint and wait for the health check to pass.

The public service uses ephemeral in-memory sessions. The default safeguards allow 20 active documents and 30 questions per document session. These are basic process-level limits, not a replacement for authentication or a distributed rate limiter on a high-traffic deployment.
