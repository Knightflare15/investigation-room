from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .dependencies import get_auth_service, get_authoring_service, get_game_service, get_player
from .models import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthoringBundle,
    BoardLinkRequest,
    CaseBriefInput,
    CaseIngestionInput,
    CaseIngestionResponse,
    ConfrontRequest,
    CreateCaseRequest,
    GenerateCaseDraftResponse,
    RescanRequest,
    SearchRequest,
    SessionPrincipal,
    SessionStatusResponse,
    SubmitTheoryRequest,
    TalkRequest,
    TogglePinRequest,
)
from .services.accounts import AuthService
from .services.authoring import AuthoringService
from .services.game import GameService

logger = logging.getLogger(__name__)


def _seed_cases_directory() -> None:
    settings.cases_path.mkdir(parents=True, exist_ok=True)
    if not settings.seed_cases_on_start:
        return
    try:
        same_path = settings.cases_path.resolve() == settings.bundled_cases_path.resolve()
    except FileNotFoundError:
        same_path = False
    if same_path or any(settings.cases_path.iterdir()) or not settings.bundled_cases_path.exists():
        return
    shutil.copytree(settings.bundled_cases_path, settings.cases_path, dirs_exist_ok=True)
    logger.info("Seeded writable cases directory from bundled cases at %s", settings.bundled_cases_path)


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404 and scope["method"] in {"GET", "HEAD"}:
            return await super().get_response("index.html", scope)
        return response


_seed_cases_directory()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.mount("/case-assets", StaticFiles(directory=settings.cases_path), name="case-assets")


@app.middleware("http")
async def production_guardrails(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.monotonic()
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path
    try:
        content_length = int(request.headers.get("content-length", "0") or "0")
    except ValueError:
        return Response("Invalid Content-Length", status_code=400)
    if "multipart/form-data" not in request.headers.get("content-type", "") and content_length > 2 * 1024 * 1024:
        return Response("Request body too large", status_code=413)
    bucket = ""
    limit = 0
    window = 3600
    if path in {"/auth/register", "/auth/login"}:
        bucket, limit, window = "auth", settings.auth_rate_limit, 600
    elif "/suspects/" in path and (path.endswith("/talk") or path.endswith("/talk/stream")):
        bucket, limit = "dialogue", settings.dialogue_rate_limit
    elif path in {"/authoring/cases/generate", "/authoring/cases/ingest"}:
        bucket, limit = "generation", settings.generation_rate_limit
    if settings.rate_limits_enabled and bucket and not get_auth_service().db.consume_rate_limit(bucket, client_ip, limit, window, int(time.time())):
        return Response("Rate limit exceeded", status_code=429, headers={"Retry-After": str(window)})
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' https:"
    logger.info("request_complete request_id=%s method=%s path=%s status=%s duration_ms=%d", request_id, request.method, path, response.status_code, (time.monotonic() - started) * 1000)
    return response

@app.get("/health/live")
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness(game: Annotated[GameService, Depends(get_game_service)]):
    return {"status": "ready", "cases": len(game.list_cases())}


@app.post("/auth/register")
def register(
    payload: AuthRegisterRequest,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        session = auth.register(payload.alias, payload.password)
        response.set_cookie("investigation_session", session.token, httponly=True, secure=settings.secure_cookies, samesite="lax", max_age=settings.session_ttl_seconds)
        return SessionStatusResponse(alias=session.alias, role=session.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/auth/login")
def login(
    payload: AuthLoginRequest,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        session = auth.login(payload.alias, payload.password)
        response.set_cookie("investigation_session", session.token, httponly=True, secure=settings.secure_cookies, samesite="lax", max_age=settings.session_ttl_seconds)
        return SessionStatusResponse(alias=session.alias, role=session.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/session", response_model=SessionStatusResponse)
def get_session(player: Annotated[SessionPrincipal, Depends(get_player)]):
    return SessionStatusResponse(alias=player.alias, role=player.role)


@app.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
):
    token = request.cookies.get("investigation_session")
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token:
        auth.revoke(token)
    response.delete_cookie("investigation_session")
    return {"logged_out": True}


@app.get("/cases")
def list_cases(game: Annotated[GameService, Depends(get_game_service)]):
    return game.list_cases()


@app.get("/cases/pending")
def list_pending_cases(
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.list_pending_cases(player.alias)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/cases/{case_id}")
def get_case(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.get_case_detail(case_id, player.alias)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/cases/{case_id}/save-state")
def get_save_state(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.get_save_state(case_id, player.alias)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/restart")
def restart_case(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.restart_case(case_id, player.alias)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/search")
def search_case(
    case_id: str,
    payload: SearchRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.search_case(case_id, player.alias, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/rescan")
def rescan_case(
    case_id: str,
    payload: RescanRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.rescan_case(case_id, player.alias, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/suspects/{suspect_id}/talk")
def talk_to_suspect(
    case_id: str,
    suspect_id: str,
    payload: TalkRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.talk_to_suspect(case_id, player.alias, suspect_id, payload.message)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/suspects/{suspect_id}/begin-session")
def begin_interrogation_session(
    case_id: str,
    suspect_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.begin_interrogation_session(case_id, player.alias, suspect_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/suspects/{suspect_id}/talk/stream")
def talk_to_suspect_stream(
    case_id: str,
    suspect_id: str,
    payload: TalkRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    def event_generator():
        try:
            lead_event: dict[str, object] = {}
            grounding_results = game.get_talk_grounding(case_id, player.alias, suspect_id, payload.message)
            yield f"data: {json.dumps({'type': 'grounding', 'results': [result.model_dump(mode='json') for result in grounding_results]})}\n\n"
            for token in game.stream_talk_to_suspect(
                case_id,
                player.alias,
                suspect_id,
                payload.message,
                grounding_results=grounding_results,
                event_sink=lead_event,
            ):
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
            yield f"data: {json.dumps({'type': 'leads', **lead_event})}\n\n"
        except KeyError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/cases/{case_id}/suspects/{suspect_id}/confront")
def confront_suspect(
    case_id: str,
    suspect_id: str,
    payload: ConfrontRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.confront_suspect(case_id, player.alias, suspect_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/board/link")
def add_board_link(
    case_id: str,
    payload: BoardLinkRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.add_board_link(case_id, player.alias, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/pin-evidence")
def toggle_pin(
    case_id: str,
    payload: TogglePinRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.toggle_pin(case_id, player.alias, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/submit-theory")
def submit_theory(
    case_id: str,
    payload: SubmitTheoryRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.submit_theory(case_id, player.alias, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/cases/{case_id}/community-stats")
def community_stats(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return game.get_community_stats(case_id, player.alias)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/authoring/cases")
def list_authoring_cases(
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    return authoring.list_bundles(player.alias)


@app.post("/authoring/cases")
def create_authoring_case(
    payload: CreateCaseRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        bundle = authoring.create_case(payload, player.alias, player.user_id)
        game.reload_cases()
        return bundle
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/authoring/cases/generate", response_model=GenerateCaseDraftResponse)
def generate_authoring_case(
    payload: CaseBriefInput,
    game: Annotated[GameService, Depends(get_game_service)],
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        generated = authoring.generate_case_from_brief(payload, player.alias, player.user_id)
        game.reload_cases()
        return generated
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/authoring/cases/ingest", response_model=CaseIngestionResponse)
def ingest_authoring_case(
    payload: CaseIngestionInput,
    game: Annotated[GameService, Depends(get_game_service)],
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        generated = authoring.ingest_case_from_source(payload, player.alias, player.user_id)
        game.reload_cases()
        return generated
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/authoring/cases/{case_id}")
def get_authoring_case(
    case_id: str,
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        return authoring.load_bundle(case_id, player.alias)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/authoring/cases/{case_id}")
def save_authoring_case(
    case_id: str,
    payload: AuthoringBundle,
    game: Annotated[GameService, Depends(get_game_service)],
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        bundle = authoring.save_bundle(case_id, payload, player.alias)
        game.reload_cases()
        return bundle
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/authoring/cases/{case_id}/approve")
def approve_authoring_case(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        bundle = authoring.approve_case(case_id, player.alias)
        game.reload_cases()
        return bundle
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/authoring/cases/{case_id}")
def delete_authoring_case(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
):
    try:
        authoring.delete_case(case_id, player.alias)
        game.reload_cases()
        return {"deleted": True, "case_id": case_id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/authoring/cases/{case_id}/assets")
async def upload_authoring_asset(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
    player: Annotated[SessionPrincipal, Depends(get_player)],
    folder: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        content = await file.read(settings.max_upload_bytes + 1)
        if len(content) > settings.max_upload_bytes:
            raise ValueError("Upload exceeds the 5 MB limit")
        asset = authoring.save_asset(case_id, folder, file.filename or "asset.bin", content, player.alias, file.content_type)
        game.reload_cases()
        return asset
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if settings.frontend_dist_path.exists():
    app.mount("/", SPAStaticFiles(directory=settings.frontend_dist_path, html=True), name="frontend")
