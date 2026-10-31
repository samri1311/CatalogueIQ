"""FastAPI entry point. Run from backend/: uvicorn app.main:app --reload"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, export, review, similarity, upload
from app.deps import settings, store

# Allowance for multipart framing on top of the file itself.
_BODY_OVERHEAD = 64 * 1024


class _TooLarge(Exception):
    pass


class BodyLimitMiddleware:
    """Reject oversized request bodies before they are parsed or spooled to disk."""

    def __init__(self, app, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        started = False

        async def tracking_send(message):
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        async def reject():
            body = b'{"detail":"Request body is too large."}'
            await tracking_send({"type": "http.response.start", "status": 413,
                                 "headers": [(b"content-type", b"application/json"),
                                             (b"content-length", str(len(body)).encode())]})
            await tracking_send({"type": "http.response.body", "body": body})

        length = dict(scope["headers"]).get(b"content-length", b"")
        if length.isdigit() and int(length) > self.max_bytes:
            return await reject()

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _TooLarge
            return message

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _TooLarge:
            if not started:
                await reject()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def sweep():
        while True:  # expire sessions even when nobody is making requests
            await asyncio.sleep(60)
            store.purge_expired()

    task = asyncio.create_task(sweep())
    yield
    task.cancel()
    store.clear()  # nothing outlives the process


app = FastAPI(title="CatalogueIQ", version="0.4.0", lifespan=lifespan)

app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_upload_bytes + _BODY_OVERHEAD)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # lets the UI use the server's filename
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"  # catalogue data must not be cached
    return response


app.include_router(upload.router)
app.include_router(analysis.router)
app.include_router(review.router)
app.include_router(similarity.router)
app.include_router(export.router)


@app.get("/health")
def health():
    return {"status": "ok"}
