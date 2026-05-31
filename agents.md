# Investigation Room — Agent Changelog

This file records all architectural changes applied by AI-assisted refactoring sessions.
Each entry lists what changed, which files were touched, and why.

---

## Session 2 — Hardening Pass (2026-05-31)

A code review of the Session 1 commit (`0b7216b`) surfaced two streaming correctness bugs, dead
code from the hook→context migration, missing test coverage, and the still-open spoofable-alias
gap. All four were fixed.

### Step A — Interrogation streaming: single LLM call + correct identity

**Problem:** one user message triggered up to three model invocations — the frontend called
`/talk` again after the stream finished, and the backend streamed a plain-text reply then called
`dialogue.generate()` (JSON mode) a second time to persist, so the text the player watched type
out differed from what was saved. Streaming also always posted as `'Detective'` (an unset
`aliasRef`), corrupting per-player state.

**Fix:**
- `backend/app/services/dialogue.py`: added public `score_reply()` (thin wrapper over the
  deterministic `_heuristic_response`) that returns state deltas without an LLM call.
- `backend/app/services/game.py`: `stream_talk_to_suspect` now accumulates the streamed tokens and
  persists *that exact text*; deltas come from `score_reply` — no second generation.
- `frontend/src/context/useGameActions.ts`: new `handleTalkStreaming(message)` owns the SSE fetch,
  dispatches `APPEND_TRANSCRIPT_TURN` (detective + empty suspect bubble) then streams via
  `UPDATE_STREAMING_REPLY`, and calls `refreshCaseState()` once at the end. Falls back to
  `handleTalk` if the stream is unavailable. Uses the real `state.alias`.
- `frontend/src/context/GameContext.tsx`: `APPEND_TRANSCRIPT_TURN` now creates a default
  conversation when a suspect has none yet (previously dropped the turn).
- `frontend/src/views/InterrogationView.tsx`: stripped local streaming state / `aliasRef` / the
  duplicate `onTalk` call; the live bubble renders from the transcript. `onTalk` is wired to
  `actions.handleTalkStreaming` in `App.tsx`.

### Step B — Dead code removal

- Deleted `frontend/src/hooks/useGameState.ts` and `useSearch.ts` (never called after the Phase 3
  context migration; only their types were still imported).
- Moved `ClueCard` and `ContradictionItem` type definitions into `frontend/src/types.ts`; updated
  `GameContext.tsx` and `InterrogationView.tsx` to import from there.
- Retyped `pinnedDocuments` from `never[]` to `CaseDocument[]` in `GameContext.tsx`; removed the
  three `as unknown as CaseDocument[]` casts in `App.tsx`.
- Kept `APPEND_TRANSCRIPT_TURN` / `UPDATE_STREAMING_REPLY` — Step A made them live.

### Step C — Unspoofable player identity (signed tokens, stdlib only)

`itsdangerous` was not installed, so the token is built with Python's stdlib (`hmac` + `hashlib` +
`base64`) — no new dependency.

- `backend/app/config.py`: added `secret_key` (env `INVESTIGATION_SECRET_KEY`).
- New `backend/app/auth.py`: `issue_token(alias)` → `<b64url(payload)>.<b64url(hmac-sha256)>`;
  `read_token(token)` verifies the signature with `hmac.compare_digest` and returns the alias or
  `None`.
- `backend/app/main.py`: new `POST /session` issues a token for an alias; all routes now depend on
  `get_player`.
- `backend/app/dependencies.py`: `get_alias` replaced by `get_player`, which reads
  `Authorization: Bearer <token>` and raises 401 on missing/invalid tokens.
- `backend/app/models.py`: added `SessionRequest` / `SessionResponse`.
- `frontend/src/api.ts`: transparent token cache (per-alias, persisted to localStorage); `request()`
  and the multipart upload now send `Authorization: Bearer`; exported `API_BASE`, `ensureToken`,
  `authHeaders`. The streaming fetch in `useGameActions.ts` uses `authHeaders`. New aliases handshake
  lazily on first request.

### Step D — Test coverage (12 tests pass, up from 6)

- `test_game_flow.py`: added a leak test asserting case-detail suspects expose no `private_truth` /
  `dialogue_rules` / `memory_rules`.
- New `test_streaming.py`: drains `stream_talk_to_suspect` (Ollama unreachable → heuristic
  fallback) and asserts exactly one detective + one suspect turn whose text equals the streamed
  text — proving the no-double-call fix.
- New `test_auth.py`: token issue/read round-trip, tampered-payload rejection, garbage/missing
  rejection.
- New `test_postgres_dialect.py`: mocks `psycopg.connect` so `PostgresDatabase` runs without a
  server; asserts `%s` placeholders (not `?`) and `Jsonb`-wrapped JSON params.

**Files created:** `backend/app/auth.py`, `backend/tests/test_streaming.py`,
`backend/tests/test_auth.py`, `backend/tests/test_postgres_dialect.py`
**Files deleted:** `frontend/src/hooks/useGameState.ts`, `frontend/src/hooks/useSearch.ts`

---

## Session 1 — Full Architectural Refactor (2026-05-31)

### Phase 1 — Backend Fixes

#### 1.1 Private Data Leak — `backend/app/models.py`

**Problem:** `GET /cases/{case_id}` returned full `SuspectConfig` objects including
`private_truth.secrets`, `private_truth.facts_known`, and `dialogue_rules.pressure_triggers`.
Any player could open browser devtools and read every hidden fact and every pressure trigger
that causes a confession.

**Fix:** Added `PublicSuspect` model (id, display_name, unlock_rule, public_profile,
portrait_key, image_path, image_url — nothing private). Changed `CaseDetailResponse.suspects`
from `list[SuspectConfig]` to `list[PublicSuspect]`. Updated `LoadedCase.to_detail()` to
build `PublicSuspect` objects before serialising.

`AuthoringBundle.suspects` stays `list[SuspectConfig]` — authoring endpoints must expose the
full truth to case authors.

The frontend `Suspect` type in `types.ts` already had no private fields, so no frontend change
was needed.

**Files changed:** `backend/app/models.py`

---

#### 1.2 Database Duplication — `backend/app/database.py`

**Problem:** `SQLiteDatabase` and `PostgresDatabase` were ~300 lines each with near-identical
method bodies for all 7 persistence operations. The only real differences were the parameter
placeholder (`?` vs `%s`), JSON column handling, and the connection context manager.

**Fix:** Extracted `BaseDatabase` abstract class that owns all 7 shared method implementations.
Subclasses implement 3 abstract methods (`_execute`, `_execute_write`, `_init_schema`) plus
3 overridable properties (`_ph`, `_excluded`, `_now`) and one overridable serialiser
(`_json`). `PostgresDatabase` overrides `_json` to return a `psycopg.types.json.Jsonb` wrapper
so JSONB columns are populated without needing `::jsonb` SQL casts. Removed `DatabaseProtocol`
(the ABC enforces the contract via `abstractmethod`). The two DDL schema strings
(`SQLITE_SCHEMA`, `POSTGRES_SCHEMA`) remain as separate module-level constants — they differ
too much (TEXT vs JSONB, AUTOINCREMENT vs BIGSERIAL, NOW() vs CURRENT_TIMESTAMP) to merge.

**Files changed:** `backend/app/database.py`

---

#### 1.3 reload_cases Race Condition — `backend/app/services/game.py`

**Problem:** `GameService.reload_cases()` replaced `self.cases` dict without any locking.
FastAPI handles concurrent HTTP requests; a reload mid-request could expose a partially-loaded
dict to another coroutine reading `self.cases` directly.

**Fix:** Added `self._cases_lock = threading.RLock()` to `GameService.__init__`. Disk I/O
(`load_cases(...)`) happens outside the lock so concurrent reads are not blocked during the
load; only the dict swap itself is locked. `get_case()` and `list_cases()` both acquire the
lock before reading `self.cases`.

**Files changed:** `backend/app/services/game.py`

---

#### 1.4 Unbounded Embedding Cache — `backend/app/services/retrieval.py`

**Problem:** `OllamaClient._embedding_cache` was a plain dict that grew without bound for
the lifetime of the process. At ~3 KB per embedding vector this could consume significant
memory on a long-running server.

**Fix:** Added `_MAX_CACHE = 2048` class constant. When the cache reaches this limit, the
oldest entry is evicted using `del self._embedding_cache[next(iter(self._embedding_cache))]`
(Python 3.7+ dicts preserve insertion order, so the first key is always the oldest). Cap of
2048 entries ≈ 6 MB maximum footprint.

**Files changed:** `backend/app/services/retrieval.py`

---

#### 1.5 Configurable CORS — `backend/app/config.py` + `backend/app/main.py`

**Problem:** `allow_origins=["*"]` was hardcoded, which is insecure for any non-localhost
deployment.

**Fix:** Added `cors_origins: tuple[str, ...]` field to `Settings` that reads
`INVESTIGATION_CORS_ORIGINS` env var (comma-separated, default `http://localhost:5173`).
Updated `main.py` to use `allow_origins=list(settings.cors_origins)`.

**Files changed:** `backend/app/config.py`, `backend/app/main.py`

---

#### 1.6 FastAPI Depends Injection — new `backend/app/dependencies.py` + `backend/app/main.py`

**Problem:** `game = GameService(settings)` and `authoring = AuthoringService(...)` were
module-level singletons in `main.py`. This makes testing awkward (tests must patch module
globals) and couples the app startup to import time.

**Fix:** Created `backend/app/dependencies.py` with `@lru_cache(maxsize=1)` getter functions
`get_game_service()`, `get_authoring_service()`, and a `get_alias()` header extractor.
Updated all 16 routes in `main.py` to inject dependencies via `Annotated[T, Depends(...)]`.
The `app.mount("/case-assets", ...)` line stays at module level — it uses `settings.cases_path`
directly and needs no service.

**Files created:** `backend/app/dependencies.py`
**Files changed:** `backend/app/main.py`

---

### Phase 2 — Frontend Decomposition

**Problem:** `App.tsx` was 1,100 lines containing 20+ `useState` calls, all 7 view renders
inline, all API calls, all event handlers, all `useMemo` derivations, and 3 known bugs:
dead interrogation tool buttons, a hardcoded `hotel-ledger` board node valid only for
case-001, and per-suspect suspicion scores derived from array index rather than game state.

#### 2.1 New directory structure

```
frontend/src/
  views/          — one file per game view
  hooks/          — useGameState.ts, useSearch.ts
  context/        — GameContext.tsx, useGameActions.ts  (Phase 3)
```

#### 2.2 `useGameState` hook — `frontend/src/hooks/useGameState.ts`

Extracted from App.tsx: all case/state/conversation state, the 3 bootstrap `useEffect`
calls, all API action handlers (handleTalk, handleConfront, handleBoardLink,
handleSubmitTheory, handleTogglePin, refreshCaseState, reloadPlayableCases, commitAlias),
and all `useMemo` derivations (pinnedDocuments, boardNodes, folderCounts, contradictionItems,
clueCards, followUpPrompts). Returns a typed `GameStateHook` object.

**Files created:** `frontend/src/hooks/useGameState.ts`

#### 2.3 `useSearch` hook — `frontend/src/hooks/useSearch.ts`

Extracted from App.tsx: searchQuery, searchResults, rescanResults, handleSearch, handleRescan.
Takes `selectedCaseId`, `alias`, and callback params so it can notify the parent when a
document or suspect is unlocked.

**Files created:** `frontend/src/hooks/useSearch.ts`

#### 2.4 View components — `frontend/src/views/`

Each view is a focused component that receives only the props it needs:

| File | Extracted from |
|------|---------------|
| `IntakeView.tsx` | `selectedView === 'intake'` block |
| `ArchiveView.tsx` | `selectedView === 'archive'` block |
| `InterrogationView.tsx` | `selectedView === 'interrogation'` block |
| `BoardView.tsx` | `selectedView === 'board'` block |
| `SubmissionView.tsx` | `selectedView === 'submission'` block |
| `CommunityView.tsx` | `selectedView === 'community'` block |

`api.ts`, `ui.tsx`, and `AuthoringStudio.tsx` were not modified.

**Files created:** all 6 view files above

#### 2.5 Bug fixes

- **Dead buttons:** The four "Interrogation Tools" buttons (Summarize Statement, Check
  Consistency, Compare to Evidence, Generate Follow-up) had no `onClick`. They now pre-fill
  the message textarea with context-appropriate prompts. The player still presses
  "Question Suspect" to submit.

- **Hardcoded `hotel-ledger` node:** `boardNodes` useMemo previously contained
  `{ id: 'hotel-ledger', label: 'Hotel Ledger' }` hardcoded for case-001. Replaced with
  dynamic derivation from `unlockedDocuments` — the node appears naturally once
  `doc_hotel_ledger` is unlocked via rescan. The `victim` logical node is kept (it has no
  corresponding document).

- **Fake suspicion scores:** Per-suspect "heat" in the left rail was derived from array index.
  Now uses real `ConversationState` data:
  `derivedHeat = Math.min(100, guardedness + (trust < 40 ? 20 : 0))`.
  Un-interrogated suspects show "Low" (no conversation = no data).

**Files changed:** `frontend/src/App.tsx` (reduced to ~220-line shell)

---

### Phase 3 — State Management (Context + useReducer)

**Problem:** The Phase 2 hooks still required prop-drilling from `useGameState` → `App.tsx`
→ each view component. Adding a new field meant threading it through multiple layers.

#### 3.1 `GameContext` — `frontend/src/context/GameContext.tsx`

Defines:
- `GameState` — complete application state shape (alias, cases, caseDetail, saveState,
  conversations, selectedIds, search state, media preview, derived fields, loading/error)
- `GameAction` — discriminated union of all dispatchable actions including
  `APPEND_TRANSCRIPT_TURN` and `UPDATE_STREAMING_REPLY` for streaming (Phase 4)
- `gameReducer` — pure function, no side effects. `SET_CASE_DETAIL` and `SET_SAVE_STATE`
  actions recompute all derived fields (boardNodes, folderCounts, pinnedDocuments,
  contradictionItems) so views never need to derive them independently.
- `GameProvider` — wraps the app, creates the reducer
- `useGame()` — typed context consumer hook

**Files created:** `frontend/src/context/GameContext.tsx`

#### 3.2 `useGameActions` — `frontend/src/context/useGameActions.ts`

All async API calls live here (reducers stay pure). Calls `useGame()` for state/dispatch.
Exposes: `loadCases`, `loadCase`, `refreshCaseState`, `reloadPlayableCases`, `handleSearch`,
`handleRescan`, `handleTalk`, `handleConfront`, `handleBoardLink`, `handleSubmitTheory`,
`handleTogglePin`.

**Files created:** `frontend/src/context/useGameActions.ts`

#### 3.3 `main.tsx` — wrapped in `<BrowserRouter><GameProvider>`

**Files changed:** `frontend/src/main.tsx`

---

### Phase 4 — UX Upgrades

**New packages installed:**
```
react-router-dom@6
@xyflow/react
```

#### 4.1 React Router — `frontend/src/App.tsx` + `frontend/src/main.tsx`

Replaced state-based tab switching with URL routes:

```
/                             → redirect to /:caseId/interrogation
/:caseId/intake               → IntakeView
/:caseId/archive              → ArchiveView
/:caseId/interrogation        → InterrogationView
/:caseId/board                → BoardView
/:caseId/submission           → SubmissionView
/:caseId/community            → CommunityView
/:caseId/authoring            → AuthoringStudio
/:caseId/*                    → redirect to interrogation
```

Tab bar and left-rail nav buttons call `navigate(...)`. A `CaseShell` component reads
`caseId` from URL params and triggers `loadCase` when the param changes. Browser back/forward
and deep links now work correctly.

**Files changed:** `frontend/src/App.tsx`, `frontend/src/main.tsx`

#### 4.2 React Flow Evidence Board — `frontend/src/views/BoardView.tsx`

Replaced the CSS orbit widget (`theory-orbit`, `orbit-node`, `orbit-core`) with a React Flow
interactive canvas:

- Nodes derived from `boardNodes` state (suspects + documents + victim), arranged in a grid
  layout using a deterministic position formula
- Confirmed board links rendered as animated green edges (`stroke: #4ade80`)
- Unconfirmed (invalid) deductions rendered as amber edges (`stroke: #f59e0b`)
- Nodes are draggable within the session (React Flow default behaviour)
- Sidebar form retains the source/target/link-type dropdowns and Validate button; clicking
  Validate dispatches the board link and adds the edge to the canvas in-place
- "Opportunity / Motive / Means / Truth" percentage metrics moved to a panel below the canvas

**Files changed:** `frontend/src/views/BoardView.tsx`

#### 4.3 Streaming Interrogation

**Backend — `backend/app/services/dialogue.py`:**
Added `stream_reply()` generator method to `DialogueService`. Calls Ollama with
`"stream": True` and yields reply tokens as they arrive. Falls back to yielding the full
heuristic reply in one chunk when Ollama is unavailable.

**Backend — `backend/app/services/game.py`:**
Added `stream_talk_to_suspect()` generator method to `GameService`. Yields tokens from
`dialogue.stream_reply()`, then runs a standard `dialogue.generate()` call after the stream
ends to persist conversation state (trust, guardedness, transcript, revealed facts).

**Backend — `backend/app/main.py`:**
Added `POST /cases/{case_id}/suspects/{suspect_id}/talk/stream` route returning
`StreamingResponse` with `media_type="text/event-stream"`. Each token is yielded as
`data: {token}\n\n`. Final event is `data: [DONE]\n\n`. Existing `/talk` endpoint is
unchanged.

**Frontend — `frontend/src/views/InterrogationView.tsx`:**
Added `handleTalkStreaming()` function that reads the SSE stream using `fetch` + `ReadableStream`.
Tokens are accumulated and rendered in a live "streaming reply" bubble below the transcript
with a blinking `▋` cursor. After the stream ends, falls back to a standard `onTalk()` call
to persist the conversation via the normal path. Falls back to the standard (non-streaming)
call automatically if the stream endpoint is unavailable.

**Files changed:** `backend/app/services/dialogue.py`, `backend/app/services/game.py`,
`backend/app/main.py`, `frontend/src/views/InterrogationView.tsx`

---

### Verification

All 6 backend tests pass after Phase 1–4:
```
test_create_case_scaffold_and_upload_asset ... ok
test_case_loads_expected_documents_and_suspects ... ok
test_create_database_defaults_to_sqlite_without_url ... ok
test_board_link_unlocks_hidden_suspect ... ok
test_rescan_unlocks_hidden_document_from_context ... ok
test_theory_submission_updates_stats ... ok
```

Frontend TypeScript build produces zero errors after each phase.

### Files Created

| File | Phase |
|------|-------|
| `backend/app/dependencies.py` | 1 |
| `frontend/src/hooks/useGameState.ts` | 2 |
| `frontend/src/hooks/useSearch.ts` | 2 |
| `frontend/src/views/IntakeView.tsx` | 2 |
| `frontend/src/views/ArchiveView.tsx` | 2 |
| `frontend/src/views/InterrogationView.tsx` | 2 |
| `frontend/src/views/BoardView.tsx` | 2 |
| `frontend/src/views/SubmissionView.tsx` | 2 |
| `frontend/src/views/CommunityView.tsx` | 2 |
| `frontend/src/context/GameContext.tsx` | 3 |
| `frontend/src/context/useGameActions.ts` | 3 |

### Files Modified

| File | Phase | Summary |
|------|-------|---------|
| `backend/app/models.py` | 1 | Added `PublicSuspect`; updated `CaseDetailResponse` and `LoadedCase.to_detail()` |
| `backend/app/database.py` | 1 | Replaced duplicate classes with `BaseDatabase` ABC |
| `backend/app/config.py` | 1 | Added `cors_origins` field |
| `backend/app/services/game.py` | 1, 4 | Added `_cases_lock`; added `stream_talk_to_suspect()` |
| `backend/app/services/retrieval.py` | 1 | Capped `_embedding_cache` at 2048 entries |
| `backend/app/services/dialogue.py` | 4 | Added `stream_reply()` generator |
| `backend/app/main.py` | 1, 4 | Depends injection; configurable CORS; streaming route |
| `frontend/src/App.tsx` | 2, 4 | Reduced to shell; React Router routes |
| `frontend/src/main.tsx` | 3, 4 | Wrapped in `GameProvider` and `BrowserRouter` |
