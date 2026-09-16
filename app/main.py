from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.rag import rag_service
from app.schemas import ChatRequest, ChatResponse, DocumentResponse, HealthResponse


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="PDF AI", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", api_key_configured=rag_service.configured)


@app.post("/api/documents", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentResponse:
    filename = Path(file.filename or "document.pdf").name
    if file.content_type not in {"application/pdf", "application/x-pdf"} and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Please upload a PDF file")
    contents = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded PDF is empty")
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="PDF must be 25 MB or smaller")
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The file does not appear to be a valid PDF")
    try:
        session_id, pages, chunks = rag_service.ingest(filename, contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not index the PDF: {exc}") from exc
    return DocumentResponse(
        session_id=session_id,
        filename=filename,
        pages=pages,
        chunks=chunks,
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        answer, sources = rag_service.ask(request.session_id, request.question.strip())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not answer the question: {exc}") from exc
    return ChatResponse(answer=answer, sources=sources)


@app.delete("/api/documents/{session_id}", status_code=204)
async def delete_document(session_id: str) -> None:
    if not rag_service.delete(session_id):
        raise HTTPException(status_code=404, detail="Document session not found")
