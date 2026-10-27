"""Scrutiny-officer review endpoints: grouped issues, per-document pipeline, file preview."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import websockets
from fastapi import APIRouter, Depends, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.core.errors import NotFoundError
from app.core.security import (
    DEMO_USER_ALIASES,
    ensure_application_access,
    get_current_user,
    require_roles,
)
from app.models.application import Application
from app.models.document import Document
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.scrutiny import DocumentReportOut, ScrutinyReviewOut
from app.services import document_report_service, speech_to_text_service, scrutiny_view_service

router = APIRouter(tags=["scrutiny"])
logger = logging.getLogger("praman.stt")

_officer = require_roles(UserRole.OFFICER, UserRole.ADMIN)


def _app(db: Session, application_id: str) -> Application:
    app = db.get(Application, application_id)
    if app is None:
        raise NotFoundError("Application not found.")
    return app


def _ws_officer(role: str | None, user_id: str | None) -> User | None:
    """Browser WebSockets cannot send X-Demo-* headers; use query params for demo auth."""
    settings = get_settings()
    if not settings.demo_auth_enabled or not role or not user_id:
        return None
    try:
        claimed = UserRole(role.strip().lower())
    except ValueError:
        return None
    if claimed not in (UserRole.OFFICER, UserRole.ADMIN):
        return None
    ident = user_id.strip()
    resolved = DEMO_USER_ALIASES.get(ident.lower(), ident)
    db = SessionLocal()
    try:
        user = db.get(User, resolved)
        if user is None or not user.is_active or user.role != claimed:
            return None
        db.expunge(user)
        return user
    finally:
        db.close()


@router.post("/scrutiny/transcribe")
async def transcribe_officer_note(
    file: UploadFile = File(...),
    user: User = Depends(_officer),
):
    """Turn a short officer recording into text via Sarvam. Prefer the live Speak WebSocket."""
    content = await file.read()
    return speech_to_text_service.transcribe_audio(
        content,
        file.filename or "note.wav",
        file.content_type,
    )


@router.websocket("/scrutiny/transcribe/ws")
async def transcribe_officer_note_live(websocket: WebSocket):
    """Proxy live PCM audio to Sarvam realtime STT. Key stays on the server."""
    await websocket.accept()
    user = _ws_officer(websocket.query_params.get("role"), websocket.query_params.get("userId"))
    if user is None:
        await websocket.send_json(
            {"event": "error", "message": "Officer authentication required.", "is_fatal": True}
        )
        await websocket.close(code=4401)
        return

    settings = get_settings()
    key = (settings.sarvam_api_key or "").strip()
    if not key:
        await websocket.send_json(
            {
                "event": "error",
                "message": "Speech to text is not configured. Set SARVAM_API_KEY in backend/.env.",
                "is_fatal": True,
            }
        )
        await websocket.close(code=4503)
        return

    sarvam_url = speech_to_text_service.realtime_ws_url()
    try:
        async with websockets.connect(
            sarvam_url,
            additional_headers={"api-subscription-key": key},
            max_size=8 * 1024 * 1024,
            open_timeout=20,
        ) as upstream:
            await websocket.send_json({"event": "proxy.ready", "provider": "sarvam"})

            async def client_to_sarvam() -> None:
                while True:
                    raw = await websocket.receive_text()
                    await upstream.send(raw)

            async def sarvam_to_client() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        continue
                    try:
                        payload = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    await websocket.send_json(payload)

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_sarvam()),
                    asyncio.create_task(sarvam_to_client()),
                ],
                return_when=asyncio.FIRST_EXCEPTION,
            )
            for task in pending:
                task.cancel()
            for task in done:
                exc = task.exception()
                if exc and not isinstance(exc, (WebSocketDisconnect, websockets.ConnectionClosed)):
                    logger.warning("stt proxy ended: %s", exc)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001 — surface to the officer UI
        logger.warning("sarvam realtime connect failed: %s", exc)
        try:
            await websocket.send_json(
                {
                    "event": "error",
                    "message": f"Could not open Sarvam live session: {exc}",
                    "is_fatal": True,
                }
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            await websocket.close(code=1011)
        except Exception:  # noqa: BLE001
            pass


@router.get("/applications/{application_id}/scrutiny-review", response_model=ScrutinyReviewOut)
def get_scrutiny_review(
    application_id: str, db: Session = Depends(get_db), user: User = Depends(_officer)
):
    return scrutiny_view_service.build_review(db, _app(db, application_id))


@router.get(
    "/applications/{application_id}/documents/{document_id}/report",
    response_model=DocumentReportOut,
)
def get_document_report(
    application_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(_officer),
):
    return document_report_service.build_document_report(db, _app(db, application_id), document_id)


@router.get("/documents/{document_id}/file")
def get_document_file(
    document_id: str,
    version: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Serve the stored file for preview. Applicants may only open their own institution's files."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFoundError("Document not found.")
    app = _app(db, doc.application_id)
    ensure_application_access(user, app)
    versions = {v.version: v for v in doc.versions}
    chosen = versions.get(version) if version is not None else doc.latest_version
    if chosen is None:
        raise NotFoundError("Document version not found.")
    path = Path(chosen.storage_path).resolve()
    root = get_settings().upload_path.resolve()
    if root not in path.parents or not path.is_file():
        raise NotFoundError("The stored file is no longer available.")
    return FileResponse(
        path,
        media_type=chosen.mime_type or "application/octet-stream",
        filename=chosen.file_name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )
