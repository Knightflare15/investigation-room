# Investigation Room

Investigation Room is a hosted detective game prototype where the player acts as a specialist investigator reviewing a stalled police case from a single operations room. The game combines a dossier-style React frontend with a FastAPI backend, Ollama-powered suspect conversations, archive search, rescans, and community theory submissions.

## Project Structure

```text
backend/              FastAPI API, persistence, retrieval, dialogue, tests
cases/                Authored cases using JSON + Markdown evidence files
frontend/             React + Vite dossier interface
```

## Features

- Police first-pass intake with known suspects and evidence
- Freeform suspect interrogation with evidence confrontation
- Archive search and context-aware rescans
- Unlockable documents and suspects through rescan and board links
- Persistent player case state and suspect memory
- Theory submission with community accusation splits and excerpts
- Built-in case authoring studio with image uploads for suspects, evidence, and location dossiers
- Premium dossier-style investigation UI with parchment readers, brass accents, and structured intelligence rails

## Visual Design

The frontend now uses a darker detective-dossier visual system inspired by a late-Victorian evidence desk rather than a generic admin panel.

- Headings and case titles use `Cormorant Garamond`
- Navigation labels and chrome use `Cinzel`
- Body copy and archive text use `Source Serif 4`
- Missing images render as intentional placeholders instead of broken image boxes

This means the app is fully usable before you add any real art.

## Backend Setup

Use the bundled Python runtime if system Python is unavailable:

```powershell
& "C:\Users\Aryan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Environment variables:

```text
INVESTIGATION_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/investigation_room
INVESTIGATION_DB_PATH=backend/data/investigation_room.db
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=llama3.1:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

`INVESTIGATION_DATABASE_URL` takes precedence over `INVESTIGATION_DB_PATH`. If it is unset, the app uses local SQLite.

## Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

The frontend expects the backend at `http://127.0.0.1:8000` by default. Override with `VITE_API_BASE_URL`.

## Authoring Your Own Mysteries

Open the frontend and switch to the `authoring` tab. The authoring studio lets you:

- scaffold a new case folder under `cases/`
- upload suspect photos, evidence images, and location images
- edit case metadata, police intake, dossiers, suspects, and evidence documents
- save prompts and advanced rescan or board-link rules back to disk

Generated case layout:

```text
cases/
  your-case-id/
    case.json
    suspects.json
    archive/
      doc-001-...
    prompts/
      interrogation_system.txt
      hint_system.txt
    assets/
      suspects/
      evidence/
      locations/
```

The app does not require those folders to contain anything yet. If an image path is missing, the UI shows:

- a framed silhouette plate for suspects
- a pinned blank evidence plate for documents
- a faded dossier/map placeholder for locations and cover art

Image fields now work in three places:

- `case.json`
  - `cover_image_path`
  - `archive_domains[].image_path`
  - `location_dossiers[].image_path`
- `suspects.json`
  - `suspects[].image_path`
- archive markdown front matter
  - `image_path`

Use paths relative to the case `assets/` directory, such as:

```text
suspects/mara-voss.png
evidence/ledger-photo.jpg
locations/ashdown-hotel.webp
```

## Ollama Models

The backend is written to use Ollama for:

- suspect dialogue generation
- optional semantic embeddings during search and rescans

Suggested local pulls:

```powershell
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

If Ollama is unavailable, the backend falls back to deterministic heuristic dialogue and keyword retrieval so the prototype still runs.

## PostgreSQL Setup

The app now supports PostgreSQL as the primary shared persistence layer.

1. Install and start PostgreSQL locally.
2. Create a database:

```sql
CREATE DATABASE investigation_room;
```

3. Set the connection URL before starting the backend:

```powershell
$env:INVESTIGATION_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:5432/investigation_room"
```

4. Restart the API. The backend creates its tables automatically on startup.

If you prefer Docker:

```powershell
docker compose -f docker-compose.postgres.yml up -d
```

You can also copy [.env.example](/C:/Users/Aryan/Documents/RAG_Project/.env.example) into your shell environment and set `INVESTIGATION_DATABASE_URL` before launching the backend.

## Tests

```powershell
& "C:\Users\Aryan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s backend/tests
```
