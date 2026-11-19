"""Session routes: create, list, read, edit, delete, reprocess, join token.

Sync handlers on purpose: every call below blocks on boto3 or on a short
LiveKit round trip, and Starlette runs sync handlers in its threadpool.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response

from app.service import postprocess
from app.service import sessions as service
from app.service.scripts import ScriptNotFound
from app.types import (
    JoinToken,
    JoinTokenRequest,
    ScriptList,
    SessionCreate,
    SessionDetail,
    SessionList,
    SessionManifest,
    SessionUpdate,
)
from app.types.sessions import SessionClass, SessionStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# SECURITY: unauthenticated, like the rest of this local demo API (see
# docs/SECURITY.md). Anyone who can reach the API can create rooms and delete
# sessions.


def _not_found(session_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Session {session_id} not found")


@router.get("/scripts", response_model=ScriptList)
def list_scripts_endpoint():
    return service.scripts()


@router.post("/sessions", response_model=SessionManifest, status_code=201)
def create_session_endpoint(request: SessionCreate):
    try:
        return service.create_session(request)
    except ScriptNotFound:
        raise HTTPException(status_code=400, detail=f"Unknown script '{request.script_id}'") from None
    except service.LiveKitUnavailable as e:
        raise HTTPException(status_code=502, detail=f"LiveKit is not reachable: {e}") from None


@router.get("/sessions", response_model=SessionList)
def list_sessions_endpoint(
    date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    session_class: SessionClass | None = None,
    status: SessionStatus | None = None,
    cursor: str | None = None,
    limit: int = 50,
):
    try:
        return service.list_sessions(date, session_class, status, cursor, limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session_endpoint(session_id: str):
    try:
        return service.get_detail(session_id)
    except service.SessionNotFound:
        raise _not_found(session_id) from None


@router.patch("/sessions/{session_id}", response_model=SessionManifest)
def update_session_endpoint(session_id: str, request: SessionUpdate):
    try:
        return service.update_session(session_id, request)
    except service.SessionNotFound:
        raise _not_found(session_id) from None
    except service.SessionConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from None


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session_endpoint(session_id: str):
    try:
        service.delete_session(session_id)
    except service.SessionNotFound:
        raise _not_found(session_id) from None
    except RuntimeError:
        raise HTTPException(status_code=502, detail="Failed to delete session from storage") from None
    return Response(status_code=204)


@router.post(
    "/sessions/{session_id}/reprocess", response_model=SessionManifest, status_code=202
)
def reprocess_session_endpoint(session_id: str, background: BackgroundTasks):
    try:
        manifest = service.prepare_reprocess(session_id)
    except service.SessionNotFound:
        raise _not_found(session_id) from None
    except service.SessionConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    background.add_task(postprocess.process_session, session_id)
    return manifest


@router.post("/sessions/{session_id}/token", response_model=JoinToken)
def join_token_endpoint(session_id: str, request: JoinTokenRequest):
    try:
        return service.join_token(session_id, request.identity)
    except service.SessionNotFound:
        raise _not_found(session_id) from None
    except service.SessionConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
