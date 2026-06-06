from __future__ import annotations

import json
import logging
import shutil
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
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
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/case-assets", StaticFiles(directory=settings.cases_path), name="case-assets")

if settings.secret_key == "dev-insecure-key" or settings.admin_access_code == "change-me":
    logger.warning(
        "Production security warning: default auth secrets are still configured. Set INVESTIGATION_SECRET_KEY and INVESTIGATION_ADMIN_ACCESS_CODE before going live."
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register")
def register(
    payload: AuthRegisterRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        return auth.register(payload.alias, payload.password, payload.admin_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/auth/login")
def login(
    payload: AuthLoginRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        return auth.login(payload.alias, payload.password, payload.admin_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/session", response_model=SessionStatusResponse)
def get_session(player: Annotated[SessionPrincipal, Depends(get_player)]):
    return SessionStatusResponse(alias=player.alias, role=player.role)


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
            grounding_results = game.get_talk_grounding(case_id, player.alias, suspect_id, payload.message)
            yield f"data: [GROUNDING]{json.dumps([result.model_dump(mode='json') for result in grounding_results])}\n\n"
            for token in game.stream_talk_to_suspect(
                case_id,
                player.alias,
                suspect_id,
                payload.message,
                grounding_results=grounding_results,
            ):
                yield f"data: {token}\n\n"
            lead_event = game.pop_stream_lead_event(case_id, player.alias, suspect_id)
            yield f"data: [LEADS]{json.dumps(lead_event)}\n\n"
        except KeyError as exc:
            yield f"data: [ERROR] {exc}\n\n"
        yield "data: [DONE]\n\n"

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
        bundle = authoring.create_case(payload, player.alias)
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
        generated = authoring.generate_case_from_brief(payload, player.alias)
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
        generated = authoring.ingest_case_from_source(payload, player.alias)
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
        content = await file.read()
        asset = authoring.save_asset(case_id, folder, file.filename or "asset.bin", content, player.alias)
        game.reload_cases()
        return asset
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if settings.frontend_dist_path.exists():
    app.mount("/", SPAStaticFiles(directory=settings.frontend_dist_path, html=True), name="frontend")
