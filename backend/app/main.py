"""
FRIDAY AI Backend
FastAPI entry point — mounts all routers and configures middleware.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api import chat, voice, websocket, health, settings
from app.core.config import get_settings
from app.core.events import on_startup, on_shutdown
from app.core.logger import get_logger

logger = get_logger(__name__)
cfg = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()


app = FastAPI(
    title="FRIDAY AI",
    description="Personal AI Operating System — Backend API",
    version="4.2.1",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(health.router,    prefix="/api/health",    tags=["Health"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["Chat"])
app.include_router(voice.router,     prefix="/api/voice",     tags=["Voice"])
app.include_router(settings.router,  prefix="/api/settings",  tags=["Settings"])
app.include_router(websocket.router, prefix="/ws",            tags=["WebSocket"])


@app.get("/")
async def root():
    return {"status": "online", "system": "FRIDAY AI OS", "version": "4.2.1"}
