# Investigation Room

Investigation Room is a full-stack AI investigation platform built around authored mystery cases. Players browse approved cases from a searchable home screen, open a case, review a police first-pass archive, question suspects through Ollama-backed dialogue, rescan the archive with newly discovered context, and submit a final theory. Admins can do all of that while also reviewing pending draft cases before approval. The project includes a React/Vite dossier interface, a FastAPI backend, persistent player state, and a case authoring pipeline for JSON, Markdown, and visual assets.

## Quick start

Open two terminals.

Backend:

```powershell
cd C:\Users\Aryan\Documents\RAG_Project
.venv\Scripts\Activate.ps1
$env:INVESTIGATION_ADMIN_ALIASES="Consultant,Admin"
$env:INVESTIGATION_ADMIN_ACCESS_CODE="change-me"
uvicorn backend.app.main:app --reload
```

Frontend:

```powershell
cd C:\Users\Aryan\Documents\RAG_Project\frontend
npm install
npm run dev
```

Optional Ollama setup:

```powershell
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

Then open:

- frontend: `http://127.0.0.1:5173`
- backend: `http://127.0.0.1:8000`
- Ollama: `http://127.0.0.1:11434`

## What the application does

- Loads authored cases from `cases/<case-id>/`
- Serves a dossier-style frontend for a searchable case library, intake, archive review, interrogation, theory building, submission, community results, player-accessible authoring, and admin review
- Uses server-side retrieval over unlocked case documents
- Uses Ollama for suspect dialogue and embeddings when available
- Falls back to deterministic retrieval and dialogue heuristics when Ollama is unavailable
- Persists player progress, suspect conversation state, and theory submissions in SQLite or PostgreSQL
- Supports two explicit session roles: `player` and `admin`
- Keeps generated or edited draft cases private until an admin approves them

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
  - reply sanitization, heuristic fallback responses, and deterministic state deltas
  - SSE token streaming for suspect replies
- `AuthoringService` in `backend/app/services/authoring.py` scaffolds and saves cases, documents, prompts, and uploaded assets
- `SourceIngestionService` in `backend/app/services/source_ingestion.py` converts pasted creator source text into grounded draft case data using chunking, retrieval scoring, optional Ollama embeddings, and source citations
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

- auth users and role-bearing sessions
- player case state
- unlocked documents and suspects
- pinned evidence
- board links
- rescan history
- discovered contexts
- per-suspect conversation state
- community theory submissions

### Authentication and roles

The project uses lightweight account auth plus signed sessions.

- `POST /auth/register` creates an account
- `POST /auth/login` verifies credentials and returns a signed session
- `GET /session` returns the signed session identity
- the frontend stores that token in `localStorage`
- protected API routes require `Authorization: Bearer <token>`
- aliases listed in `INVESTIGATION_ADMIN_ALIASES` become `admin`
- all other aliases become `player`
- admin aliases also require `INVESTIGATION_ADMIN_ACCESS_CODE` during registration and login

Authentication flow:

1. a user registers with `alias + password`
2. if the alias is admin-listed, the user must also provide the admin access code
3. login returns a signed bearer token containing alias and role
4. the frontend restores that session from `localStorage` on reload
5. protected routes resolve the current `SessionPrincipal` from the bearer token

Role behavior:

- `player`
  - can browse approved cases
  - can open and play approved cases
  - can create and edit their own draft cases in the authoring studio
- `admin`
  - can do everything a player can do
  - can see pending draft cases
  - can open draft cases privately
  - can approve draft cases for public listing

Auth implementation:

- `backend/app/auth.py`
- `backend/app/dependencies.py`
- `backend/app/services/accounts.py`

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
- `POST /auth/register`
- `POST /auth/login`
- `GET /session`
- `GET /cases`
- `GET /cases/pending`
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
- `POST /authoring/cases/generate`
- `POST /authoring/cases/ingest`
- `GET /authoring/cases/{case_id}`
- `PUT /authoring/cases/{case_id}`
- `POST /authoring/cases/{case_id}/approve`
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

## Where data lives

By default, persistent app data is stored in:

- SQLite database: `backend/data/investigation_room.db`
- authored/playable case files: `cases/<case-id>/`
- uploaded/generated case assets: `cases/<case-id>/assets/...`

If `INVESTIGATION_DATABASE_URL` is set, player/auth/submission data moves to PostgreSQL instead of SQLite.

## Environment variables

Supported settings are defined in `backend/app/config.py`.

Important variables:

```text
INVESTIGATION_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/investigation_room
INVESTIGATION_DB_PATH=backend/data/investigation_room.db
INVESTIGATION_SECRET_KEY=dev-insecure-key
INVESTIGATION_CORS_ORIGINS=http://localhost:5173
INVESTIGATION_ADMIN_ALIASES=Consultant,Admin
INVESTIGATION_ADMIN_ACCESS_CODE=change-me
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=llama3.1:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_TIMEOUT_SECONDS=45
OLLAMA_STREAM_TIMEOUT_SECONDS=60
```

Notes:

- `INVESTIGATION_DATABASE_URL` takes precedence over `INVESTIGATION_DB_PATH`
- if no PostgreSQL URL is provided, SQLite is used
- `.env.example` currently includes the main Ollama and PostgreSQL settings
- the chat and stream timeout settings control how long the backend waits before using the deterministic fallback dialogue path

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

### Current dialogue behavior

There are two suspect-talk routes:

- `POST /cases/{case_id}/suspects/{suspect_id}/talk`
- `POST /cases/{case_id}/suspects/{suspect_id}/talk/stream`

Current behavior:

- both routes try Ollama first for the visible suspect reply
- the backend now sends a lighter prompt that asks for plain suspect speech instead of narrated prose
- streaming uses Ollama token output directly when available
- non-stream talk also uses Ollama for reply text, but uses deterministic backend logic for trust/guardedness/suspicion updates
- if Ollama fails, times out, or returns metadata-leaky text, the backend falls back to a cleaner heuristic reply
- repeated character catchphrases are no longer injected by the backend as a default dialogue feature
- interrogations are session-based: reopening a suspect starts a fresh live session while retaining a compacted summary of earlier interactions

This means progression logic stays stable even if the exact wording changes, while the visible response is still usually model-generated.

### Troubleshooting Ollama

Useful checks:

```powershell
curl http://127.0.0.1:11434/api/tags
ollama run llama3.1:8b
```

What to look for:

- if `/api/tags` fails, Ollama is not running
- if the model is missing, pull it with `ollama pull llama3.1:8b`
- if suspect replies sound stiff but still coherent, you are probably seeing the deterministic fallback
- if the first turn is slow, warm the model once with `ollama run llama3.1:8b` before using the app

Backend logs now emit warning messages when a dialogue turn falls back from Ollama to the heuristic responder.

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
- personality profile
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
- generate a draft case from a pasted semi-structured case brief
- ingest a raw pasted source packet into a draft case with source-grounding notes
- open a post-generation review modal showing detected suspects, evidence, locations, warnings, and source grounding
- regenerate the same draft with a structured follow-up prompt describing what is missing
- assign default template visuals or upload custom images before review
- edit case metadata
- edit suspects
- edit Markdown-backed documents
- edit prompt templates
- upload visual assets
- save everything back to disk
- approve a draft case if the current session is `admin`

Draft ID behavior:

- manual case IDs are now optional in all authoring entry paths
- if the creator leaves the case ID blank, the backend auto-generates a unique draft ID from the title
- repeated titles get numeric suffixes automatically, for example `draft-the-glass-harbor-affair` then `draft-the-glass-harbor-affair-2`
- if the creator explicitly provides a case ID, that value is still used

Required case-brief headings for generation:

- `Case Title`
- `Premise`
- `Victim`
- `Setting`
- `Suspects`
- `Relationships`
- `Timeline`
- `Evidence`
- `Hidden Truth`
- `Solution`

### Raw source ingestion workflow

The heavier RAG-style import path is available from `Authoring Studio` by selecting `Raw Source Packet`.

This flow accepts creator-authored mystery/worldbuilding text rather than raw police files or PDFs. The source can include narrative premise, people involved, bios, relationships, timeline notes, evidence notes, hidden truth, and solution details.

Backend ingestion flow:

1. normalize the pasted source text
2. split the source into stable chunks
3. precompute chunk embeddings once for that ingestion request when Ollama embeddings are available
4. detect entities and keywords per chunk
5. retrieve relevant chunks for extraction passes such as victim, setting, suspects, timeline, evidence, hidden truth, and solution
6. use two-stage ranking: lexical/entity shortlist first, then embedding rerank when vectors are available
7. ask Ollama for strict JSON extraction per field group when possible, then validate it before building the draft
8. fall back to heuristic extraction when Ollama is unavailable or returns invalid structured output
9. convert extracted material into the existing `ExtractedCaseDraft`
10. reuse the normal draft-bundle generator so output remains an editable `AuthoringBundle`
11. return warnings and `SourceGrounding` notes showing which source chunks supported generated fields

Generated raw-source drafts:

- always start as `draft`
- use template images by default
- remain private to the creator/admin until approval
- include source-grounding notes in the authoring response
- save compact `source_grounding_notes` into prompts for later review
- include per-item grounding metadata with:
  - generated field name
  - generated value
  - supporting chunk ids
  - confidence label
  - extraction method (`ollama` or `heuristic`)

Post-generation review flow:

1. creator generates a draft from structured or raw input
2. a review modal opens automatically
3. the modal shows detected suspects, evidence, locations, warnings, and grounding notes
4. the creator can add a structured refinement prompt if extraction missed something
5. for raw-source ingestion, the creator can target only one section such as `suspects`, `evidence`, or `locations`
6. if the creator supplied or kept the same draft ID, that same private draft is regenerated in place while it is still unapproved
7. the creator can assign template assets or upload custom suspect, evidence, and location images
8. the creator sends the draft to review
9. the case remains `draft` until an admin approves it

The current ingestion path is intentionally paste-only. It does not yet perform PDF parsing, OCR, automatic image moderation, or multi-document police-file ingestion.

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

Generated draft cases also receive default template images for:

- suspect portraits
- evidence plates
- location/cover art

Draft publication flow:

1. a creator creates or generates a case
2. the case starts with `status = "draft"`
3. players do not see draft cases in the public library
4. admins can review drafts from the pending list
5. an admin approves the case
6. only then does it appear in `GET /cases` and on the public home screen

## Retrieval and progression model

The current progression loop is:

1. player starts with `start_state` unlocks
2. archive search derives new contexts
3. suspect conversations add additional contexts
4. rescans apply `context_entity_discovered` rules
5. focused rescans apply `context_entity_discovered` rules using the specific lead the player typed in the specific location they selected
6. the theory board remains a workspace for organizing links, not a progression unlock system
7. newly unlocked documents or suspects appear in the active case state

Conversation-driven discoveries now return explicit lead metadata:

- `unlocked_documents`
- `unlocked_suspects`
- `lead_messages`

For streaming interrogation, the backend sends retrieved context first, streams the visible suspect reply, then sends a final `[LEADS]` SSE event. This keeps the saved transcript equal to what the player saw while still surfacing new investigative leads in the UI.

Retrieval is now more RAG-focused in two places:

- gameplay retrieval caches per-chunk embeddings in memory so repeated archive searches and interrogation grounding do not keep re-embedding the same paragraphs
- dialogue grounding now prefers smaller, higher-quality evidence snippets based on the suspect, conversation memory, pinned evidence, and recent discovered context

Implementation references:

- `backend/app/services/game.py`
- `backend/app/services/retrieval.py`

## Frontend behavior

The active interface currently supports:

- searchable home screen for public case browsing
- intake overview
- archive browsing and search
- direct selection of every unlocked archive document from the archive screen
- interrogation with suspect dialogue
- visible `New Leads` feedback when interrogation surfaces a document or suspect
- evidence pinning
- theory board linking
- theory submission
- community stats
- authoring studio for both players and admins
- admin-only pending-case review and approval

The frontend also:

- supports explicit register and login flows
- restores the current signed session from `localStorage`
- resolves the current session role as `player` or `admin`
- normalizes backend asset URLs to the API origin
- opens visual attachments in a modal viewer

## Current workflow

### Player workflow

1. register or log in with alias and password
2. frontend restores the signed session on later visits
3. home screen loads approved cases only
4. player can open `Authoring Studio` to create a draft case, or search the public library and open a case
5. when authoring, the player can leave the draft case ID blank and let the backend generate a unique non-repeating draft ID automatically
6. backend creates or loads player save state
7. player opens unlocked documents directly from the archive screen, searches evidence, interrogates suspects in session-style conversations, runs focused rescans from specific leads in specific locations, uses the board to organize theory notes, and submits a theory

### Admin workflow

1. register or log in with an alias listed in `INVESTIGATION_ADMIN_ALIASES`
2. provide the admin access code
3. frontend resolves the session as `admin`
3. home screen shows approved cases plus pending draft cases
4. admin can still create personal draft cases through authoring like any player
5. admin can also open a pending case in play mode or review it in authoring
6. admin edits text/assets if needed
7. admin approves the case
8. approved case moves into the public case library

## Tests

Backend tests live in `backend/tests`.

Current coverage includes:

- token auth
- register/login flow
- case loading
- authoring persistence
- database factory behavior
- progression flow
- raw source ingestion and grounding
- PostgreSQL dialect behavior
- streaming endpoint behavior
- dialogue fallback sanitization

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

## Manual next tweaks

These are the highest-value human review tasks before presenting or deploying the project:

- Replace development secrets before any demo beyond localhost: set a real `INVESTIGATION_SECRET_KEY`, change `INVESTIGATION_ADMIN_ACCESS_CODE`, and avoid committing real secrets.
- Manually author one strong raw-source sample case and run it through `Raw Source Packet` import. Check whether the generated culprit, motive, suspects, and evidence match your intended story.
- Review generated `SourceGrounding` notes after ingestion. They show which source chunks supported generated fields, but they are not proof that every generated sentence is perfect.
- Strengthen suspect voice by editing each generated suspect's `personality_profile`, `private_truth`, and `dialogue_rules` in Authoring Studio after ingestion.
- Replace template images before approval. The current placeholders are useful for drafts, but approved cases should have intentional suspect, evidence, and location visuals.
- Keep generated build artifacts out of git. `*.tsbuildinfo` is already ignored.
- Try one full playthrough as a fresh player account after approving a generated case. Confirm the first documents, interrogation leads, rescans, board links, and final theory flow feel fair.
- For a stronger RAG resume story, add one future pass where Ollama extracts structured JSON from retrieved source chunks, then compare it against the current deterministic extractor.

## Notes and limitations

- the backend assumes case content is authored locally on disk
- retrieval is paragraph-based and intentionally lightweight
- auth is lightweight and local; it is not a production identity platform
- Ollama usage is optional but strongly improves dialogue and retrieval quality
- the frontend is route-based, with shared state in `frontend/src/context` and screen components under `frontend/src/views`
- suspect dialogue is more robust than before, but still depends on local-model quality and latency
