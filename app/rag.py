from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import threading
import time
from uuid import uuid4

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config import settings


SYSTEM_PROMPT = """You answer questions using only the supplied PDF excerpts.
If the excerpts do not contain enough information, say exactly: "I couldn't find that in the uploaded PDF."
Do not use outside knowledge or invent details. Cite factual statements with page markers such as [Page 3].
Keep the answer direct and readable. For summaries or answers with multiple facts, use a short opening
sentence followed by concise Markdown bullet points. Use descriptive bold labels where helpful. Avoid
large blocks of text."""


@dataclass
class Session:
    filename: str
    vector_store: Chroma
    pages: int
    chunks: int
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    history: list[tuple[str, str]] = field(default_factory=list)
    questions_asked: int = 0


class RagService:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()
        self._client = chromadb.EphemeralClient()
        self._embeddings: GoogleGenerativeAIEmbeddings | None = None
        self._llm: ChatGoogleGenerativeAI | None = None

    @property
    def configured(self) -> bool:
        return bool(settings.google_api_key)

    def _ensure_models(self) -> None:
        if not self.configured:
            raise RuntimeError("GOOGLE_API_KEY is not configured")
        if self._embeddings is None:
            self._embeddings = GoogleGenerativeAIEmbeddings(
                model=settings.embedding_model,
                google_api_key=settings.google_api_key,
            )
        if self._llm is None:
            self._llm = ChatGoogleGenerativeAI(
                model=settings.chat_model,
                google_api_key=settings.google_api_key,
            )

    def _cleanup_expired(self) -> None:
        cutoff = time.time() - settings.session_ttl_seconds
        expired = [key for key, value in self._sessions.items() if value.last_accessed < cutoff]
        for session_id in expired:
            self.delete(session_id)

    def ingest(self, filename: str, pdf_bytes: bytes) -> tuple[str, int, int]:
        self._ensure_models()
        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception as exc:
                    raise ValueError("Password-protected PDFs are not supported") from exc
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("The uploaded file is not a readable PDF") from exc

        documents: list[Document] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                documents.append(
                    Document(
                        page_content=text,
                        metadata={"page": page_number, "source": filename},
                    )
                )
        if not documents:
            raise ValueError("No selectable text was found. Scanned PDFs need OCR, which is not enabled yet.")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = splitter.split_documents(documents)
        session_id = uuid4().hex
        collection_name = f"pdf_{session_id}"
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=self._embeddings,
            client=self._client,
            collection_name=collection_name,
            collection_metadata={"hnsw:space": "cosine"},
        )
        with self._lock:
            self._cleanup_expired()
            if len(self._sessions) >= settings.max_active_sessions:
                raise RuntimeError("The server is currently at its document-session limit. Please try again later.")
            self._sessions[session_id] = Session(
                filename=filename,
                vector_store=vector_store,
                pages=len(reader.pages),
                chunks=len(chunks),
            )
        return session_id, len(reader.pages), len(chunks)

    def ask(self, session_id: str, question: str) -> tuple[str, list[dict[str, object]]]:
        self._ensure_models()
        with self._lock:
            self._cleanup_expired()
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError("Document session not found or expired")
            if session.questions_asked >= settings.max_questions_per_session:
                raise PermissionError("This document session has reached its question limit. Upload the PDF again to start a new session.")
            session.last_accessed = time.time()
            session.questions_asked += 1

        results = session.vector_store.similarity_search_with_relevance_scores(
            question,
            k=settings.retrieval_count,
        )
        if not results:
            return "I couldn't find that in the uploaded PDF.", []

        context_parts: list[str] = []
        sources: list[dict[str, object]] = []
        seen: set[tuple[int, str]] = set()
        for document, _score in results:
            page = int(document.metadata.get("page", 0))
            clean_text = " ".join(document.page_content.split())
            context_parts.append(f"[Page {page}]\n{clean_text}")
            signature = (page, clean_text[:180])
            if signature not in seen:
                seen.add(signature)
                sources.append({"page": page, "excerpt": clean_text[:280]})

        history_text = "\n".join(
            f"User: {user}\nAssistant: {assistant}"
            for user, assistant in session.history[-3:]
        )
        context_text = "\n\n".join(context_parts)
        user_prompt = f"""PDF excerpts:
{context_text}

Recent conversation (use only to understand references in the new question):
{history_text or '(none)'}

Question: {question}"""
        response = self._llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
        )
        # Gemini may return a list of structured content blocks. AIMessage.text
        # extracts only their human-readable text and omits signatures/metadata.
        answer = str(response.text).strip()
        session.history.append((question, answer))
        session.history = session.history[-6:]
        return answer, sources

    def delete(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        try:
            session.vector_store.delete_collection()
        except Exception:
            pass
        return True


rag_service = RagService()
