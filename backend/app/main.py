"""AI 知识库管理平台 — FastAPI 入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import chat, chunk, document, knowledge
from .core.config import settings
from .core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(knowledge.router)
app.include_router(document.router)
app.include_router(chunk.router)
app.include_router(chat.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
