# Investigation Room

Investigation Room is a full-stack AI investigation platform built around authored mystery cases. Players review a police first-pass archive, question suspects through Ollama-backed dialogue, rescan the archive with newly discovered context, and submit a final theory. The project includes a React/Vite dossier interface, a FastAPI backend, persistent player state, and a case authoring pipeline for JSON, Markdown, and visual assets.

## What the application does

- Loads authored cases from `cases/<case-id>/`
- Serves a dossier-style frontend for intake, archive review, interrogation, theory building, submission, community results, and authoring
- Uses server-side retrieval over unlocked case documents
- Uses Ollama for suspect dialogue and embeddings when available
- Falls back to deterministic retrieval and dialogue heuristics when Ollama is unavailable
- Persists player progress, suspect conversation state, and theory submissions in SQLite or PostgreSQL

## Architecture

### Backend

- `FastAPI` application in `backend/app/main.py`
- `GameService` in `backend/app/services/game.py` orchestrates state, retrieval, dialogue, rescans, board links, and submissions
- `RetrievalService` in `backend/app/services/retrieval.py` performs paragraph-level search using:
  - token overlap
  - entity-tag matches
  - optional Ollama embeddings via `/api/embed`
- `DialogueService` in `backend/app/services/dialogue.py` performs:
  - Ollama chat calls via `/api/chat`
  - heuristic fallback responses and state deltas
  - SSE token streaming for suspect replies
- `AuthoringService` in `backend/app/services/authoring.py` scaffolds and saves cases, documents, prompts, and uploaded assets
- `case_loader.py` loads JSON/Markdown case content from disk and resolves case asset URLs

### Frontend

- `React + Vite + TypeScript`
- Main UI shell in `frontend/src/App.tsx`
- API client in `frontend/src/api.ts`
- Authoring UI in `frontend/src/AuthoringStudio.tsx`
- Shared UI primitives in `frontend/src/ui.tsx`
- Styling in `frontend/src/styles.css`

### Persistence

Database code lives in `backend/app/database.py`.

Supported backends:

- SQLite by default
- PostgreSQL when `INVESTIGATION_DATABASE_URL` is set

Stored data:

- player case state
- unlocked documents and suspects
- pinned evidence
- board links
- rescan history
- discovered contexts
- per-suspect conversation state
- community theory submissions

### Authentication

The project uses lightweight signed sessions rather than passwords.

- `POST /session` issues an HMAC-signed token for an alias
- the frontend stores that token in `localStorage`
- protected API routes require `Authorization: Bearer <token>`

Auth implementation:

- `backend/app/auth.py`
- `backend/app/dependencies.py`

## Repository layout

```text
backend/
  app/
    main.py
    models.py
    database.py
    case_loader.py
    services/
  tests/

cases/
  case-001/
    case.json
    suspects.json
    archive/
    prompts/
    assets/
      suspects/
      evidence/
      locations/

frontend/
  src/
```

## Current sample case

The repository ships with a working sample case:

- `cases/case-001/case.json`
- `cases/case-001/suspects.json`
- `cases/case-001/archive`

This sample is useful both as a playable reference and as the template for authoring new cases.

## API surface

Implemented routes:

- `GET /health`
- `POST /session`
- `GET /cases`
- `GET /cases/{case_id}`
- `GET /cases/{case_id}/save-state`
- `POST /cases/{case_id}/search`
- `POST /cases/{case_id}/rescan`
- `POST /cases/{case_id}/suspects/{suspect_id}/talk`
- `POST /cases/{case_id}/suspects/{suspect_id}/talk/stream`
- `POST /cases/{case_id}/suspects/{suspect_id}/confront`
- `POST /cases/{case_id}/board/link`
- `POST /cases/{case_id}/pin-evidence`
- `POST /cases/{case_id}/submit-theory`
- `GET /cases/{case_id}/community-stats`
- `GET /authoring/cases`
- `POST /authoring/cases`
- `GET /authoring/cases/{case_id}`
- `PUT /authoring/cases/{case_id}`
- `POST /authoring/cases/{case_id}/assets`

Static case assets are served from:

- `/case-assets/...`

## Setup

### Backend

```powershell
cd C:\Users\Aryan\Documents\RAG_Project
& "C:\Users\Aryan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn backend.app.main:app --reload
```

Backend default URL:

- `http://127.0.0.1:8000`

### Frontend

```powershell
cd C:\Users\Aryan\Documents\RAG_Project\frontend
npm install
npm run dev
```

Frontend default URL:

- `http://127.0.0.1:5173`

## Environment variables

Supported settings are defined in `backend/app/config.py`.

Important variables:

```text
INVESTIGATION_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/investigation_room
INVESTIGATION_DB_PATH=backend/data/investigation_room.db
INVESTIGATION_SECRET_KEY=dev-insecure-key
INVESTIGATION_CORS_ORIGINS=http://localhost:5173
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=llama3.1:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

Notes:

- `INVESTIGATION_DATABASE_URL` takes precedence over `INVESTIGATION_DB_PATH`
- if no PostgreSQL URL is provided, SQLite is used
- `.env.example` currently includes the main Ollama and PostgreSQL settings

## PostgreSQL

To run against PostgreSQL instead of SQLite:

1. Start PostgreSQL
2. Create the database:

```sql
CREATE DATABASE investigation_room;
```

3. Set the connection string:

```powershell
$env:INVESTIGATION_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:5432/investigation_room"
```

4. Start the backend

There is also a helper compose file:

```powershell
docker compose -f docker-compose.postgres.yml up -d
```

## Ollama integration

The backend tries Ollama first and falls back when local models are unavailable.

Used for:

- suspect dialogue generation
- streaming suspect replies
- embeddings for semantic retrieval

Suggested local models:

```powershell
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

Fallback behavior:

- retrieval still works using token overlap and entity matches
- suspect dialogue still works using heuristic responses and deterministic state deltas

## How case loading works

Case loading is implemented in `backend/app/case_loader.py`.

At startup and after authoring updates, the backend:

- reads `case.json`
- reads `suspects.json`
- reads every Markdown document in `archive/`
- reads prompt text files from `prompts/`
- resolves relative asset paths into `/case-assets/...` URLs

## Case format

Expected structure:

```text
cases/
  <case-id>/
    case.json
    suspects.json
    archive/
      doc-001-*.md
    prompts/
      interrogation_system.txt
      hint_system.txt
    assets/
      suspects/
      evidence/
      locations/
```

### `case.json`

Contains:

- case metadata
- initial unlocked suspects and documents
- open questions
- archive domains
- location dossiers
- rescan rules
- valid board links
- submission requirements

### `suspects.json`

Contains:

- public profile
- private truth
- dialogue rules
- memory rules
- optional portrait key and image path

### Markdown evidence files

Each archive document uses front matter plus a body.

Typical front matter fields:

- `id`
- `title`
- `doc_type`
- `folder`
- `source_label`
- `unlock_rule`
- `entity_tags`
- `summary`
- `image_path`

## Authoring workflow

The authoring UI can:

- scaffold a new case
- edit case metadata
- edit suspects
- edit Markdown-backed documents
- edit prompt templates
- upload visual assets
- save everything back to disk

Authoring asset folders:

- `cases/<case-id>/assets/suspects/`
- `cases/<case-id>/assets/evidence/`
- `cases/<case-id>/assets/locations/`

Asset references are stored as paths relative to `assets/`, for example:

```text
suspects/mara-voss.svg
evidence/incident-board.svg
locations/ashdown-exterior.svg
```

If an image is missing, the frontend shows an intentional placeholder plate instead of a broken image.

## Retrieval and progression model

The current progression loop is:

1. player starts with `start_state` unlocks
2. archive search derives new contexts
3. suspect conversations add additional contexts
4. rescans apply `context_entity_discovered` rules
5. theory-board links apply `board_link_confirmed` rules
6. newly unlocked documents or suspects appear in the active case state

Implementation references:

- `backend/app/services/game.py`
- `backend/app/services/retrieval.py`

## Frontend behavior

The active interface currently supports:

- intake overview
- archive browsing and search
- interrogation with suspect dialogue
- evidence pinning
- theory board linking
- theory submission
- community stats
- authoring studio

The frontend also:

- registers a signed session automatically
- normalizes backend asset URLs to the API origin
- opens visual attachments in a modal viewer

## Tests

Backend tests live in `backend/tests`.

Current coverage includes:

- token auth
- case loading
- authoring persistence
- database factory behavior
- progression flow
- PostgreSQL dialect behavior
- streaming endpoint behavior

Run tests with:

```powershell
cd C:\Users\Aryan\Documents\RAG_Project
& "C:\Users\Aryan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s backend/tests
```

## Build verification

Frontend production build:

```powershell
cd C:\Users\Aryan\Documents\RAG_Project\frontend
npm run build
```

## Notes and limitations

- the backend assumes case content is authored locally on disk
- retrieval is paragraph-based and intentionally lightweight
- the current frontend is primarily implemented in a single shell component plus an authoring surface
- Ollama usage is optional but strongly improves dialogue and retrieval quality
- some extra frontend scaffolding files exist under `frontend/src/context` and `frontend/src/views`, but the main running UI is currently driven by `frontend/src/App.tsx`
