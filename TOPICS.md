# Topics Curriculum

This file is a real curriculum, not just a topic checklist.

It is designed for someone who is new to:

- full-stack web development
- backend architecture
- AI and ML basics
- LLMs and embeddings
- retrieval and RAG systems
- shipping a real product

It uses this repo as the practical anchor, so every major topic also points to where the idea is implemented here.

The goal is that if you follow this properly, you should be able to:

- understand how this project works end to end
- explain it honestly in interviews
- make meaningful improvements on your own
- become competent in the broader domain of AI-assisted application development

## What This Curriculum Tries To Make You Good At

By the end, you should be comfortable with:

- modern web application architecture
- backend API design
- stateful frontend applications
- authentication and authorization
- database-backed persistence
- file-backed content systems
- search and retrieval
- embeddings and semantic similarity
- local LLM integration with Ollama
- structured extraction pipelines
- RAG-style ingestion and grounding
- testing and debugging
- deployment and production basics

## How Deep This Is

This curriculum is deeper than a topic list, but it is still practical rather than academic.

It is built for:

- building products
- understanding codebases
- becoming strong enough to improve or ship systems like this

It is not built for:

- ML research
- model training from scratch
- advanced statistics-heavy machine learning theory
- distributed systems at large company scale

## How To Use It

Study in this order:

1. read the module overview
2. learn the concepts listed
3. open the repo files linked under `Where It Appears Here`
4. do the exercises
5. pass the checkpoint before moving on

Do not skip the exercises.

If you only read, you will recognize terms.
If you build, debug, and explain, you will actually learn.

## Suggested Pace

If you are serious, a good pace is:

- light pace: 4 to 6 months
- focused pace: 8 to 12 weeks
- intense pace: 5 to 7 weeks full-time

## Curriculum Structure

This curriculum has 15 modules:

1. Programming Foundations
2. Web and HTTP Foundations
3. Frontend Foundations
4. Backend Foundations
5. Data Modeling and Validation
6. Persistence and Databases
7. Authentication and Authorization
8. Filesystem Content and Authoring Systems
9. Search and Retrieval Foundations
10. AI and LLM Foundations
11. Embeddings and Semantic Search
12. RAG and Grounded Generation
13. Dialogue Systems and Product Logic
14. Testing, Debugging, and Reliability
15. Deployment and Production Readiness

---

## Module 1: Programming Foundations

### Goal

Build enough comfort with Python, TypeScript, and general programming so the rest of the repo does not feel mysterious.

### Learn These Topics

- variables and assignment
- primitive types
- strings, numbers, booleans
- lists, arrays, dictionaries, objects, sets
- conditionals
- loops
- functions
- parameters and return values
- classes
- modules and imports
- error handling
- reading and writing files
- basic type systems
- mutability vs immutability

### Why This Matters Here

This repo mixes:

- Python backend logic
- TypeScript frontend logic
- JSON and Markdown content files

If your fundamentals are shaky, the AI-specific parts will feel much harder than they actually are.

### Where It Appears Here

- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/services/*.py`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/context/GameContext.tsx`

### Exercises

1. Open `backend/app/models.py` and explain what each model represents.
2. Open `frontend/src/types.ts` and compare it to backend models.
3. Pick one backend function and rewrite it in your own words line by line.
4. Add a tiny Python scratch file and practice:
   - parsing a dictionary
   - iterating over a list
   - writing a JSON file

### Checkpoint

You should be able to:

- read a Python function without panic
- read a TypeScript object shape without confusion
- explain the difference between a list/array and a dictionary/object

---

## Module 2: Web and HTTP Foundations

### Goal

Understand how browsers, frontend apps, and backend APIs communicate.

### Learn These Topics

- client vs server
- request and response
- URL paths
- query params
- HTTP verbs:
  - GET
  - POST
  - PUT
  - DELETE
- headers
- JSON request bodies
- status codes:
  - 200
  - 400
  - 401
  - 403
  - 404
  - 500
- CORS
- bearer tokens

### Why This Matters Here

This project is a web app first.
Everything else sits on top of that.

### Where It Appears Here

- `backend/app/main.py`
- `frontend/src/api.ts`
- `backend/app/config.py`

### Exercises

1. List all the API routes in `backend/app/main.py`.
2. Match each route to the frontend action that calls it.
3. Explain what happens when login fails.
4. Explain why `localhost:5173` and `127.0.0.1:5173` can cause a CORS issue.

### Checkpoint

You should be able to explain:

- what happens when the frontend calls `/auth/login`
- what a bearer token is
- why CORS exists

---

## Module 3: Frontend Foundations

### Goal

Understand how the React frontend is structured and how the UI works.

### Learn These Topics

- components
- props
- local state
- shared state
- forms
- controlled inputs
- event handlers
- rendering dynamic lists
- conditional rendering
- routing
- component composition
- UI state vs business state

### Where It Appears Here

- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/views/*.tsx`
- `frontend/src/AuthoringStudio.tsx`
- `frontend/src/ui.tsx`
- `frontend/src/styles.css`

### Important Subtopics

#### React routing

Learn:

- page routes
- route params
- redirects
- navigation

Where here:

- `frontend/src/App.tsx`
- `frontend/src/main.tsx`

#### Context and reducers

Learn:

- global state
- dispatch
- reducer-based updates
- why this scales better than many unrelated local states

Where here:

- `frontend/src/context/GameContext.tsx`
- `frontend/src/context/useGameActions.ts`

### Exercises

1. Trace what happens when a player opens a case from the home screen.
2. Trace what happens when a user clicks `Generate Draft Case`.
3. Explain which state lives in `GameContext` and which stays local to a component.

### Checkpoint

You should be able to explain:

- how the app moves between pages
- how shared app state is stored
- how the authoring modal gets its data

---

## Module 4: Backend Foundations

### Goal

Understand how the backend is structured as a service-based application.

### Learn These Topics

- routes/controllers
- service layer
- dependency injection
- request validation
- response shaping
- app startup
- static file serving

### Where It Appears Here

- `backend/app/main.py`
- `backend/app/dependencies.py`
- `backend/app/services/game.py`
- `backend/app/services/authoring.py`
- `backend/app/services/dialogue.py`
- `backend/app/services/retrieval.py`
- `backend/app/services/source_ingestion.py`

### Important Subtopics

#### Thin routes

Routes should mostly:

- parse input
- call a service
- map exceptions to HTTP errors

Where here:

- `backend/app/main.py`

#### Business logic in services

The real logic should live in service classes.

Where here:

- `backend/app/services/*.py`

### Exercises

1. Find one route and identify the exact service method it calls.
2. Explain why keeping all business logic in `main.py` would be worse.
3. Explain what `get_game_service()` and `get_authoring_service()` do.

### Checkpoint

You should be able to explain:

- why service layers exist
- what dependency injection does in this repo
- how the backend separates HTTP concerns from product logic

---

## Module 5: Data Modeling and Validation

### Goal

Understand how the system defines and validates its data.

### Learn These Topics

- schemas
- validation
- nested models
- request models
- response models
- domain models
- public vs private representations

### Where It Appears Here

- `backend/app/models.py`
- `frontend/src/types.ts`

### Important Subtopics

#### Public vs private data

This project deliberately hides secret suspect info from players.

Where here:

- `PublicSuspect` vs `SuspectConfig` in `backend/app/models.py`

#### Authoring vs gameplay models

The authoring side sees more than the gameplay side.

Where here:

- `AuthoringBundle`
- `CaseDetailResponse`
- `CaseIngestionResponse`

### Exercises

1. Compare `PublicSuspect` and `SuspectConfig`.
2. Explain why the frontend gameplay view should not receive `private_truth`.
3. Find one model used for requests and one model used for responses.

### Checkpoint

You should be able to explain:

- why typed models are useful
- how validation reduces bugs
- how this repo prevents a hidden-data leak

---

## Module 6: Persistence and Databases

### Goal

Understand how the app stores user state, conversations, and submissions.

### Learn These Topics

- relational databases
- tables and rows
- primary keys
- composite keys
- CRUD
- upsert
- transactions at a basic level
- SQLite
- PostgreSQL
- JSON fields

### Where It Appears Here

- `backend/app/database.py`
- `backend/app/config.py`
- `docker-compose.postgres.yml`

### Important Subtopics

#### SQLite vs PostgreSQL

Learn:

- when a file-based DB is enough
- when a server DB is better

Where here:

- `backend/app/database.py`

#### Persistence design

Learn:

- loading state
- saving after mutations
- storing per-player case state
- storing per-suspect conversation state

Where here:

- `backend/app/database.py`
- `backend/app/services/game.py`

### Exercises

1. Find where player state is loaded.
2. Find where a conversation is saved after talking to a suspect.
3. Find where a theory submission is saved.

### Checkpoint

You should be able to explain:

- what data lives in the DB
- what data lives on disk in files
- why both storage styles exist in this project

---

## Module 7: Authentication and Authorization

### Goal

Understand how the app knows who the user is and what they are allowed to do.

### Learn These Topics

- authentication
- authorization
- passwords
- hashing
- sessions
- bearer tokens
- HMAC signing
- role-based access
- protected routes

### Where It Appears Here

- `backend/app/auth.py`
- `backend/app/services/accounts.py`
- `backend/app/dependencies.py`
- `backend/app/main.py`
- `frontend/src/api.ts`
- `frontend/src/views/AuthView.tsx`

### Important Subtopics

#### Register/login flow

Learn:

- how account creation works
- how login works
- how sessions are restored

#### Roles

This app has only:

- `player`
- `admin`

Where here:

- `backend/app/models.py`
- `backend/app/services/accounts.py`
- `frontend/src/App.tsx`

### Exercises

1. Trace the register flow from frontend to backend.
2. Trace the login flow from frontend to backend.
3. Explain how admin access is enforced.

### Checkpoint

You should be able to explain:

- the difference between auth and authorization
- how the app restores a session after reload
- how admin-only routes are protected

---

## Module 8: Filesystem Content and Authoring Systems

### Goal

Understand how this app treats mystery cases as editable content bundles.

### Learn These Topics

- filesystem-based content storage
- JSON config files
- Markdown documents with front matter
- prompt files
- asset folders
- authoring bundles
- content editing workflows

### Where It Appears Here

- `cases/`
- `backend/app/case_loader.py`
- `backend/app/services/authoring.py`
- `frontend/src/AuthoringStudio.tsx`

### Important Subtopics

#### Case loading

Learn:

- how case JSON is loaded
- how suspect files are loaded
- how archive docs are read
- how asset URLs are resolved

Where here:

- `backend/app/case_loader.py`

#### Authoring systems

Learn:

- scaffold creation
- bundle editing
- saving prompts and Markdown
- asset uploads
- draft review

Where here:

- `backend/app/services/authoring.py`
- `frontend/src/AuthoringStudio.tsx`

### Exercises

1. Open `cases/case-001/`.
2. Explain what each file/folder is for.
3. Follow the code path for saving an authoring bundle.

### Checkpoint

You should be able to explain:

- what a case bundle is
- why this system is data-driven
- how a non-programmer could create a case using authoring tools

---

## Module 9: Search and Retrieval Foundations

### Goal

Understand how the system finds relevant evidence from unlocked documents and source text.

### Learn These Topics

- tokenization
- text normalization
- chunking
- lexical scoring
- entity-tag boosts
- hybrid retrieval
- reranking
- retrieval caches

### Where It Appears Here

- `backend/app/services/retrieval.py`
- `backend/app/services/source_ingestion.py`

### Important Subtopics

#### Chunking

Learn:

- why long text is broken into chunks
- why chunk ids matter
- why chunk-level retrieval is more precise than whole-document retrieval

#### Hybrid retrieval

Learn:

- lexical shortlist
- embedding rerank
- why both are useful together

Where here:

- `backend/app/services/retrieval.py`

### Exercises

1. Explain how archive search works for a normal player query.
2. Explain how raw source text gets chunked during ingestion.
3. Identify where chunk embedding caching is implemented.

### Checkpoint

You should be able to explain:

- why search does not just scan whole documents directly
- how chunk-based retrieval improves relevance
- why retrieval is central to this app

---

## Module 10: AI and LLM Foundations

### Goal

Build the conceptual foundation needed to understand Ollama, prompts, and generation.

### Learn These Topics

- AI vs ML
- inference
- deep learning at a high level
- transformers at a high level
- LLMs
- tokens
- prompts
- chat models
- local model serving

### Where It Appears Here

- `backend/app/services/dialogue.py`
- `backend/app/services/source_ingestion.py`
- `backend/app/services/retrieval.py`
- `backend/app/config.py`

### Important Subtopics

#### Ollama

Learn:

- local model server
- chat endpoint
- embedding endpoint
- model selection
- timeouts and fallbacks

#### Prompt design

Learn:

- system prompt
- user prompt
- structured payload
- output restrictions

Where here:

- `backend/app/services/dialogue.py`
- `backend/app/services/source_ingestion.py`

### Exercises

1. Find where the app calls Ollama for chat.
2. Find where the app calls Ollama for embeddings.
3. Explain why the app still needs fallback logic.

### Checkpoint

You should be able to explain:

- what an LLM is
- what inference means
- what Ollama is doing for this app

---

## Module 11: Embeddings and Semantic Search

### Goal

Understand one of the most important AI ideas used in this project.

### Learn These Topics

- embeddings
- vectors
- semantic similarity
- cosine similarity
- lexical vs semantic search
- hybrid retrieval
- reranking

### Where It Appears Here

- `backend/app/services/retrieval.py`
- `backend/app/services/source_ingestion.py`

### Important Subtopics

#### Embeddings

Simple idea:

- text in
- vector out
- similar meaning -> similar vector direction

#### Cosine similarity

Learn:

- how vector similarity is measured
- why cosine similarity is common in embedding search

### Exercises

1. Find the cosine similarity functions in the repo.
2. Explain in plain English how a query and a chunk are compared semantically.
3. Explain why embeddings help even when the words do not match exactly.

### Checkpoint

You should be able to explain:

- what embeddings are
- why embeddings are useful
- how this repo uses embeddings in both retrieval and ingestion

---

## Module 12: RAG and Grounded Generation

### Goal

Understand the domain this project now fits into most clearly.

### Learn These Topics

- retrieval-augmented generation
- retrieve-then-generate flow
- grounding
- chunk citations
- confidence labels
- structured extraction
- fallback extraction
- source ingestion

### Where It Appears Here

- `backend/app/services/source_ingestion.py`
- `backend/app/services/retrieval.py`
- `backend/app/services/dialogue.py`
- `backend/app/models.py`
- `frontend/src/AuthoringStudio.tsx`

### Important Subtopics

#### Raw-source ingestion

Learn:

- pasted source text
- chunking
- field-specific retrieval
- Ollama JSON extraction
- Pydantic validation
- heuristic fallback
- grounding metadata

#### Grounding metadata

Learn:

- generated field
- generated value
- supporting chunk ids
- extraction method
- confidence label

Where here:

- `SourceGrounding` in `backend/app/models.py`

#### Retrieval-grounded dialogue

Learn:

- retrieve small relevant snippets
- pass them into the LLM
- keep visible speech clean
- keep product logic deterministic

Where here:

- `backend/app/services/game.py`
- `backend/app/services/dialogue.py`

### Exercises

1. Trace the raw-source ingestion flow from request to draft bundle.
2. Explain where Ollama extraction is used and where heuristics still remain.
3. Explain how the review modal helps a creator inspect what was grounded vs guessed.

### Checkpoint

You should be able to explain:

- what RAG means in general
- how this repo uses RAG-like patterns
- why grounding is important
- why fallback paths still matter

---

## Module 13: Dialogue Systems and Product Logic

### Goal

Understand how the app combines natural language interaction with reliable gameplay state.

### Learn These Topics

- conversational state
- memory summaries
- grounding for dialogue
- deterministic state updates
- unlock systems
- fallbacks
- streaming replies

### Where It Appears Here

- `backend/app/services/game.py`
- `backend/app/services/dialogue.py`
- `frontend/src/views/InterrogationView.tsx`

### Important Subtopics

#### Deterministic logic vs model wording

This is a very important product design idea.

Learn:

- the LLM can generate the wording
- the backend should still own trust, guardedness, suspicion, unlocks, and progress

Where here:

- `backend/app/services/dialogue.py`
- `backend/app/services/game.py`

#### Interrogation sessions

Learn:

- transcript
- memory summary
- reopen session behavior
- grounded follow-up context

### Exercises

1. Trace what happens when a player asks a suspect a question.
2. Trace what happens when a player reopens the same suspect later.
3. Explain where progression is updated after a conversation.

### Checkpoint

You should be able to explain:

- how the conversation system works
- how the app preserves context across sessions
- why the AI is not allowed to directly control game state

---

## Module 14: Testing, Debugging, and Reliability

### Goal

Learn how to trust and improve a project like this safely.

### Learn These Topics

- unit testing
- integration testing
- regression testing
- fallback-path testing
- debugging backend logic
- validating frontend builds
- reading stack traces

### Where It Appears Here

- `backend/tests/test_game_flow.py`
- `backend/tests/test_streaming.py`
- `backend/tests/test_authoring_service.py`
- `backend/tests/test_auth.py`

### Important Subtopics

#### Reliability through fallback behavior

Learn:

- what happens when Ollama is down
- why tests should cover that

#### Streaming correctness

Learn:

- why saved text should match streamed text
- why double-calling an LLM can cause subtle bugs

Where here:

- `backend/tests/test_streaming.py`

### Exercises

1. Run the backend tests and explain what each suite protects.
2. Intentionally break one behavior in a local branch and predict which test should fail.
3. Read one fallback-related test and explain why it matters.

### Checkpoint

You should be able to explain:

- why tests matter here
- what kinds of failures this repo already guards against
- how you would add a regression test for a future bug

---

## Module 15: Deployment and Production Readiness

### Goal

Understand the practical work needed to run an app like this outside your laptop.

### Learn These Topics

- environment variables
- secrets
- frontend build output
- static serving
- Docker basics
- cloud deployment basics
- SQLite vs Postgres in production
- persistent storage
- logs
- startup commands

### Where It Appears Here

- `backend/app/config.py`
- `Dockerfile`
- `.dockerignore`
- `AZURE_DEPLOY.md`
- `startup.sh`
- `.env.example`

### Important Subtopics

#### Production tradeoffs

Learn:

- cheap demo deployment vs proper production
- App Service + SQLite vs App Service + Postgres
- local Ollama vs hosted model endpoints

#### Operational constraints

Learn:

- timeouts
- latency
- fallback behavior
- persistent storage requirements

### Exercises

1. Explain the simplest local run path.
2. Explain the simplest portfolio deployment path.
3. Explain what breaks if persistent storage is missing.

### Checkpoint

You should be able to explain:

- how this app is configured
- how it can be deployed
- what would need to change before larger-scale production use

---

## Capstone Milestones

These are the practical milestones that show whether you really learned the material.

### Milestone 1: Explain The App Cleanly

You should be able to explain:

- what the app does
- how the frontend and backend interact
- how cases are stored
- how players and admins differ

### Milestone 2: Trace One Full Request

You should be able to trace:

- user action in the browser
- frontend API call
- backend route
- service logic
- persistence update
- response back to UI

### Milestone 3: Explain The AI Layer Honestly

You should be able to explain:

- what Ollama is doing
- what embeddings are
- how retrieval works
- how this project uses RAG-like patterns
- what is deterministic and what is model-generated

### Milestone 4: Modify The Project Safely

You should be able to make one small change such as:

- add a new grounding field
- add a new archive document type
- change a search/rerank behavior
- improve a dialogue prompt

### Milestone 5: Build A Tiny Clone Feature Yourself

Try building one small subsystem from scratch, for example:

- a mini archive search endpoint
- a mini structured extraction endpoint
- a tiny role-based draft approval flow

This is where learning becomes real.

## Suggested Weekly Study Plan

If you want a structured schedule:

### Week 1

- Modules 1 and 2
- Read:
  - `README.md`
  - `backend/app/main.py`
  - `frontend/src/api.ts`

### Week 2

- Modules 3 and 4
- Read:
  - `frontend/src/App.tsx`
  - `frontend/src/context/GameContext.tsx`
  - `backend/app/services/game.py`

### Week 3

- Modules 5, 6, and 7
- Read:
  - `backend/app/models.py`
  - `backend/app/database.py`
  - `backend/app/auth.py`
  - `backend/app/services/accounts.py`

### Week 4

- Modules 8 and 9
- Read:
  - `backend/app/case_loader.py`
  - `backend/app/services/authoring.py`
  - `backend/app/services/retrieval.py`

### Week 5

- Modules 10 and 11
- Read:
  - `backend/app/services/dialogue.py`
  - `backend/app/services/retrieval.py`
  - `INTERVIEW_README.md`

### Week 6

- Modules 12 and 13
- Read:
  - `backend/app/services/source_ingestion.py`
  - `frontend/src/AuthoringStudio.tsx`
  - `frontend/src/views/InterrogationView.tsx`

### Week 7

- Modules 14 and 15
- Read:
  - `backend/tests/*.py`
  - `Dockerfile`
  - `AZURE_DEPLOY.md`

## Best Readings For This Domain

These are the topics you should search and study externally:

### Software and web

- Python basics
- TypeScript basics
- React fundamentals
- FastAPI fundamentals
- SQL fundamentals
- REST API design
- authentication and authorization basics

### AI and retrieval

- LLM basics
- transformer overview
- tokens and context windows
- embeddings
- cosine similarity
- semantic search
- hybrid retrieval
- RAG
- structured output from LLMs
- prompt engineering
- local inference with Ollama

### Systems and product

- content management systems
- workflow design
- draft/review/publish flows
- test design
- fallback system design
- cloud deployment basics

## If You Want To Go Even Deeper

After this curriculum, the next deeper topics are:

- vector databases
- evaluation of retrieval quality
- LLM output evaluation
- prompt testing
- ranking metrics
- advanced chunking strategies
- query rewriting
- reranking models
- model serving at scale
- security hardening
- rate limiting
- observability and monitoring

These are not required to understand this repo well, but they are the next level.

## Final Standard

This curriculum is deep enough if, by the end, you can do these three things:

1. Explain the system clearly.
2. Change the system safely.
3. Rebuild the core ideas in a smaller project on your own.

If you cannot do those yet, keep going.

That is the real test.
