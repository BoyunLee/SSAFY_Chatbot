import os
from contextlib import asynccontextmanager
from pathlib import Path

import chromadb
import numpy as np
import pypdf
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DB_PATH = BASE_DIR / "chroma_data"
ENV_PATH = BASE_DIR / ".env"
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}

load_dotenv(ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip()
RAG_MODEL_NAME = os.getenv("RAG_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
TOP_K = 4
SIMILARITY_THRESHOLD = 0.45

DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)

rag_model: SentenceTransformer | None = None
openai_client = None
collection = None
rag_stats = {
    "document_count": 0,
    "chunk_count": 0,
}


class ChatRequest(BaseModel):
    message: str


def extract_text(file_path: Path) -> str:
    if file_path.suffix.lower() == ".pdf":
        reader = pypdf.PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return file_path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text.strip():
        return []
    if overlap >= size:
        raise ValueError("Chunk overlap must be smaller than chunk size.")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def normalize(vectors):
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim == 1:
        return arr / (np.linalg.norm(arr) + 1e-12)
    norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12
    return arr / norms


def source_files() -> list[Path]:
    return [
        path
        for path in DATA_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS
    ]


def build_rag_index() -> None:
    global collection

    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))

    try:
        chroma_client.delete_collection("ssafy_docs")
    except Exception:
        pass

    collection = chroma_client.create_collection(
        "ssafy_docs",
        metadata={"hnsw:space": "cosine"},
    )

    files = source_files()
    next_id = 0
    total_chunks = 0

    for file_path in files:
        text = extract_text(file_path)
        chunks = chunk_text(text)
        if not chunks:
            continue

        embeddings = normalize(rag_model.encode(chunks))
        ids = [f"doc-{next_id + idx}" for idx in range(len(chunks))]
        next_id += len(chunks)
        total_chunks += len(chunks)

        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings.tolist(),
            metadatas=[{"source": file_path.name} for _ in chunks],
        )

    rag_stats["document_count"] = len(files)
    rag_stats["chunk_count"] = total_chunks


def retrieve_context(question: str) -> dict:
    if collection is None or rag_stats["chunk_count"] == 0:
        return {
            "used_rag": False,
            "sources": [],
            "context": "",
            "matches": [],
        }

    query_embedding = normalize(rag_model.encode(question))
    results = collection.query(query_embeddings=[query_embedding.tolist()], n_results=TOP_K)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    matches = []
    for doc, metadata, distance in zip(documents, metadatas, distances):
        similarity = 1.0 - float(distance)
        matches.append(
            {
                "source": metadata.get("source", "unknown"),
                "similarity": round(similarity, 4),
                "accepted": similarity >= SIMILARITY_THRESHOLD,
                "preview": doc[:240],
                "text": doc,
            }
        )

    accepted_matches = [match for match in matches if match["accepted"]]
    sources = []
    for match in accepted_matches:
        if match["source"] not in sources:
            sources.append(match["source"])

    context = "\n\n".join(match["text"] for match in accepted_matches)

    return {
        "used_rag": len(accepted_matches) > 0,
        "sources": sources,
        "context": context,
        "matches": [
            {
                "source": match["source"],
                "similarity": match["similarity"],
                "accepted": match["accepted"],
                "preview": match["preview"],
            }
            for match in matches
        ],
    }


def generate_answer(system_prompt: str, user_message: str) -> str:
    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content or "응답을 생성하지 못했습니다."


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_model, openai_client

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    rag_model = SentenceTransformer(RAG_MODEL_NAME)
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    build_rag_index()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "provider": "openai",
        "documents": rag_stats["document_count"],
        "chunks": rag_stats["chunk_count"],
    }


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="txt, md, pdf 형식만 업로드할 수 있습니다.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일은 업로드할 수 없습니다.")

    save_path = DATA_DIR / Path(file.filename).name
    save_path.write_bytes(content)

    try:
        extracted_text = extract_text(save_path)
        chunks = chunk_text(extracted_text)
    except Exception as exc:
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(status_code=400, detail=f"파일 처리 중 오류가 발생했습니다: {exc}") from exc

    if not chunks:
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(status_code=400, detail="텍스트를 추출할 수 없는 문서입니다.")

    build_rag_index()

    return {
        "success": True,
        "filename": save_path.name,
        "chunks_added": len(chunks),
        "message": f"{save_path.name} 문서가 저장되었고 RAG 인덱스에 반영되었습니다.",
        "documents": rag_stats["document_count"],
        "chunks": rag_stats["chunk_count"],
    }


@app.get("/documents")
def list_documents():
    files = source_files()
    return {
        "documents": [file.name for file in files],
        "count": len(files),
        "chunks": rag_stats["chunk_count"],
    }


@app.post("/chat")
def chat(req: ChatRequest):
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="질문을 입력해 주세요.")

    try:
        retrieval = retrieve_context(user_message)

        if retrieval["used_rag"]:
            system_prompt = (
                "당신은 SSAFY 학습 도우미입니다. "
                "아래 참고 문서를 우선 근거로 사용해 답변하세요. "
                "답변에는 핵심 근거를 자연스럽게 반영하고, 문서에 없는 내용은 추측하지 마세요.\n\n"
                f"[참고 문서]\n{retrieval['context']}"
            )
            reference_note = "업로드된 문서를 참고해 답변했습니다."
        else:
            system_prompt = (
                "당신은 SSAFY 학습 도우미입니다. "
                "정확하고 이해하기 쉬운 한국어로 답변하세요. "
                "현재 참고 가능한 업로드 문서와의 유사한 검색 결과가 없으므로 일반 지식 기반으로 답변하세요."
            )
            reference_note = "유사한 문서를 찾지 못해 일반 생성형 AI 응답으로 답변했습니다."

        answer = generate_answer(system_prompt, user_message)
        return {
            "answer": answer,
            "sources": retrieval["sources"],
            "used_rag": retrieval["used_rag"],
            "reference_note": reference_note,
            "retrieval_matches": retrieval["matches"],
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "provider": "openai",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI 응답 생성 중 오류가 발생했습니다: {exc}",
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
