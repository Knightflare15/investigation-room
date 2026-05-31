from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .dependencies import get_alias, get_authoring_service, get_game_service
from .models import (
    AuthoringBundle,
    BoardLinkRequest,
    ConfrontRequest,
    CreateCaseRequest,
    RescanRequest,
    SearchRequest,
    SubmitTheoryRequest,
    TalkRequest,
    TogglePinRequest,
)
from .services.authoring import AuthoringService
from .services.game import GameService

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/case-assets", StaticFiles(directory=settings.cases_path), name="case-assets")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cases")
def list_cases(game: Annotated[GameService, Depends(get_game_service)]):
    return game.list_cases()


@app.get("/cases/{case_id}")
def get_case(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    alias: Annotated[str, Depends(get_alias)],
):
    try:
        return game.get_case_detail(case_id, alias)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/cases/{case_id}/save-state")
def get_save_state(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    alias: Annotated[str, Depends(get_alias)],
):
    try:
        return game.get_save_state(case_id, alias)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/search")
def search_case(
    case_id: str,
    payload: SearchRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    alias: Annotated[str, Depends(get_alias)],
):
    try:
        return game.search_case(case_id, alias, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/rescan")
def rescan_case(
    case_id: str,
    payload: RescanRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    alias: Annotated[str, Depends(get_alias)],
):
    try:
        return game.rescan_case(case_id, alias, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/suspects/{suspect_id}/talk")
def talk_to_suspect(
    case_id: str,
    suspect_id: str,
    payload: TalkRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    alias: Annotated[str, Depends(get_alias)],
):
    try:
        return game.talk_to_suspect(case_id, alias, suspect_id, payload.message)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/suspects/{suspect_id}/talk/stream")
def talk_to_suspect_stream(
    case_id: str,
    suspect_id: str,
    payload: TalkRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    alias: Annotated[str, Depends(get_alias)],
):
    def event_generator():
        try:
            for token in game.stream_talk_to_suspect(case_id, alias, suspect_id, payload.message):
                yield f"data: {token}\n\n"
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
    alias: Annotated[str, Depends(get_alias)],
):
    try:
        return game.confront_suspect(case_id, alias, suspect_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/board/link")
def add_board_link(
    case_id: str,
    payload: BoardLinkRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    alias: Annotated[str, Depends(get_alias)],
):
    try:
        return game.add_board_link(case_id, alias, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/pin-evidence")
def toggle_pin(
    case_id: str,
    payload: TogglePinRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    alias: Annotated[str, Depends(get_alias)],
):
    try:
        return game.toggle_pin(case_id, alias, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/cases/{case_id}/submit-theory")
def submit_theory(
    case_id: str,
    payload: SubmitTheoryRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    alias: Annotated[str, Depends(get_alias)],
):
    try:
        return game.submit_theory(case_id, alias, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/cases/{case_id}/community-stats")
def community_stats(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
):
    try:
        return game.get_community_stats(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/authoring/cases")
def list_authoring_cases(
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
):
    return authoring.list_bundles()


@app.post("/authoring/cases")
def create_authoring_case(
    payload: CreateCaseRequest,
    game: Annotated[GameService, Depends(get_game_service)],
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
):
    try:
        bundle = authoring.create_case(payload)
        game.reload_cases()
        return bundle
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/authoring/cases/{case_id}")
def get_authoring_case(
    case_id: str,
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
):
    try:
        return authoring.load_bundle(case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/authoring/cases/{case_id}")
def save_authoring_case(
    case_id: str,
    payload: AuthoringBundle,
    game: Annotated[GameService, Depends(get_game_service)],
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
):
    try:
        bundle = authoring.save_bundle(case_id, payload)
        game.reload_cases()
        return bundle
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/authoring/cases/{case_id}/assets")
async def upload_authoring_asset(
    case_id: str,
    game: Annotated[GameService, Depends(get_game_service)],
    authoring: Annotated[AuthoringService, Depends(get_authoring_service)],
    folder: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        content = await file.read()
        asset = authoring.save_asset(case_id, folder, file.filename or "asset.bin", content)
        game.reload_cases()
        return asset
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
