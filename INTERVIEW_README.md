# Interview Prep README

This file is a study guide for understanding this repository before interviews.
It is written for someone who may know React and backend development, but is still new to AI, ML, LLMs, embeddings, and RAG.

The goal is not just to describe the project, but to help you understand:

- what the project does
- how the code is structured
- what AI terms mean in plain language
- which AI ideas are actually used in this repo
- what to say honestly in an interview
- what to study next

## 1. Project in one paragraph

This project is a full-stack investigation platform built with a React frontend and a FastAPI backend. Case content is stored on disk as JSON, Markdown, prompt text files, and image assets. The backend loads that content, stores each player's progress, searches documents using keyword and embedding-based matching, retrieves supporting archive snippets to ground suspect dialogue, streams suspect replies from Ollama, and unlocks new content based on authored rules. The frontend now starts with a searchable case library, supports `player` and `admin` session roles, and includes an in-app authoring studio plus an admin review flow for pending draft cases.

## 2. Simple project summary for interviews

If you need a short answer, use this:

> "This is a full-stack AI-assisted case investigation platform. The frontend is built in React and the backend is built in FastAPI. Cases are data-driven and loaded from JSON, Markdown, prompts, and images on disk. The backend handles search, user progress, retrieval-grounded AI responses, streaming, draft approval, and content authoring, while the frontend manages a searchable case library, shared gameplay state, interrogation, theory building, and admin review flows."

## 3. Big picture architecture

The project has three main parts:

1. Content layer
- Cases are stored on disk under `cases/<case-id>/`.
- A case includes `case.json`, `suspects.json`, Markdown evidence files, prompt text files, and assets.

2. Backend layer
- FastAPI exposes routes.
- Services handle game logic, retrieval, dialogue, authoring, and persistence.
- SQLite or PostgreSQL stores user state and submissions.
- Ollama provides chat and embedding APIs.

3. Frontend layer
- React + TypeScript + Vite powers the UI.
- Shared state is stored in a `Context + useReducer` setup.
- Route-based views render the home/library, archive, interrogation, board, submission, community, and authoring screens.

## 4. Repo map

### Backend

- `backend/app/main.py`
  API routes and FastAPI app setup
- `backend/app/models.py`
  Pydantic models for cases, suspects, documents, requests, responses, state, and bundles
- `backend/app/case_loader.py`
  Loads case files from disk
- `backend/app/database.py`
  Shared persistence layer for SQLite and PostgreSQL
- `backend/app/auth.py`
  Signed token generation, verification, and role resolution
- `backend/app/dependencies.py`
  Dependency injection and auth extraction
- `backend/app/services/accounts.py`
  Registration, login, password verification, and admin-code checks
- `backend/app/services/game.py`
  Main gameplay/business logic
- `backend/app/services/retrieval.py`
  Search, chunking, context extraction, embeddings
- `backend/app/services/dialogue.py`
  LLM calls, reply sanitization, heuristic fallback, and streaming replies
- `backend/app/services/authoring.py`
  Case scaffolding, editing, document saving, asset upload

### Frontend

- `frontend/src/App.tsx`
  Main shell, home screen routing, and role-aware navigation
- `frontend/src/api.ts`
  API client and token handling
- `frontend/src/context/GameContext.tsx`
  Shared app state and reducer
- `frontend/src/context/useGameActions.ts`
  Async state-changing actions
- `frontend/src/views/*.tsx`
  Individual screens
- `frontend/src/AuthoringStudio.tsx`
  In-app case editing UI

### Content

- `cases/case-001/case.json`
  High-level case structure
- `cases/case-001/suspects.json`
  Suspect public and private data
- `cases/case-001/archive/*.md`
  Evidence documents with front matter
- `cases/case-001/prompts/*.txt`
  Prompt templates
- `cases/case-001/assets/*`
  Images

## 5. AI/ML basics from zero

If you are new to AI terms, start here.

### What is AI?

AI is the broad idea of making software do tasks that feel "intelligent", like answering questions, recognizing patterns, generating text, or making predictions.

### What is ML?

ML stands for machine learning.

Instead of writing fixed rules for every situation, you train a model on data so it can learn patterns and then make predictions or generate outputs later.

Examples:
- spam detection
- recommendation systems
- text classification
- handwriting recognition
- image recognition

### What is deep learning?

Deep learning is a subset of machine learning that uses large neural networks. Many modern AI systems, especially language models, are deep learning models.

### What is NLP?

NLP stands for natural language processing. It is the area of AI/ML focused on understanding and generating human language.

Examples:
- translation
- summarization
- question answering
- chatbots
- sentiment analysis

### What is generative AI?

Generative AI is AI that creates outputs such as:
- text
- images
- code
- audio

LLMs are one kind of generative AI.

### What is an LLM?

LLM stands for large language model.

An LLM is a model trained on a lot of text and used to generate or transform language. It predicts text one token at a time.

Examples:
- GPT-style models
- Llama-family models
- Qwen-family models
- Gemma-family models

### What is a token?

A token is a small unit of text a model processes.

It is not always a full word.
For example:
- a short word may be one token
- a long word may be split into multiple tokens
- spaces and punctuation affect tokenization too

Why it matters:
- models read prompts as tokens
- models generate outputs as tokens
- context limits are measured in tokens

### What is inference?

Inference means using a trained model to produce an output.

In this project:
- asking Ollama for a suspect reply is inference
- asking Ollama for embeddings is also inference

### What is a prompt?

A prompt is the input you send to a language model.

In this repo, prompts include:
- system prompts from `prompts/interrogation_system.txt`
- structured JSON-like payloads containing suspect, conversation, and state information

### What are embeddings?

Embeddings are lists of numbers that represent the meaning of text.

Simple way to think about them:
- text in -> vector of numbers out
- similar meanings -> vectors that are closer together

Why embeddings are useful:
- they help search find relevant text even when the wording is different
- they power semantic similarity

Example:
- query: "private hotel meeting"
- document: "suite booking arranged quietly"

The exact words are different, but embeddings may still show they are related.

### What is semantic search?

Semantic search means searching by meaning, not only exact words.

Keyword search:
- looks for matching words

Semantic search:
- looks for related meaning

This project uses both.

### What is chunking?

Chunking means breaking a long document into smaller pieces before search.

In this repo:
- documents are split into paragraph-like chunks
- each chunk is scored separately

Why chunking helps:
- smaller chunks are easier to match to a query
- results can show more focused snippets

### What is RAG?

RAG stands for retrieval-augmented generation.

Basic idea:
1. retrieve useful external text
2. give that text to a language model
3. generate an answer grounded in that retrieved text

Why people use RAG:
- LLMs may not know private or recent data
- retrieved documents can ground the answer
- answers can become more accurate and more tied to source material

### Very important nuance for this repo

This project now uses retrieval ideas, embeddings, and document search more directly in dialogue, but it is still not a textbook RAG chatbot in the strictest sense.

Why:
- the archive search uses retrieval over documents
- rescans and progression use discovered contexts
- interrogation can retrieve top archive snippets and pass them into dialogue grounding
- confrontation can pass selected evidence into dialogue
- but the system is still not a general-purpose "retrieve from a large knowledge base for every answer with formal citations" chatbot

So the safest way to describe it is:

> "This project uses retrieval and embedding-based document search alongside LLM-powered dialogue, and suspect replies are grounded in retrieved archive snippets. It is closer to RAG than before, but still not a classic end-to-end general-purpose RAG question-answering system."

That is a very honest and interview-safe description.

## 6. What AI concepts this repo actually uses

### Used directly

- LLM chat generation through Ollama
- token streaming from Ollama
- embeddings through Ollama
- keyword search
- entity-tag matching
- semantic similarity with cosine similarity
- retrieval-grounded dialogue prompts
- heuristic fallback logic when the model is unavailable

### Used indirectly or partially

- retrieval concepts
- prompt engineering
- meaning-based search
- grounded evidence-assisted conversation in some flows

### Not really used here

- model training
- fine-tuning
- reinforcement learning
- vector databases
- large-scale data pipelines
- GPU training infrastructure
- agent frameworks

That distinction matters in interviews. You should not present this as a model-training project.

## 7. Backend walkthrough

### `backend/app/main.py`

This is the FastAPI entry point.

What it does:
- creates the app
- sets CORS
- mounts static case assets
- exposes gameplay routes
- exposes authoring routes
- creates `/auth/register`, `/auth/login`, and `/session`
- exposes the admin-only pending-case review route
- exposes the streaming interrogation endpoint

Important routes:
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
- authoring endpoints under `/authoring/...`

### `backend/app/models.py`

This file defines the system's data shapes.

Important models:
- `CaseConfig`
  overall case definition
- `SuspectConfig`
  full suspect definition, including private truth and authored personality voice
- `PublicSuspect`
  safe subset sent to players
- `CaseDocument`
  evidence document
- `PlayerCaseState`
  unlocked docs, unlocked suspects, pinned evidence, board links, contexts, objective
- `ConversationState`
  transcript, trust, guardedness, revealed facts
- `LoadedCase`
  runtime object combining config, suspects, documents, and prompts
- `SessionPrincipal`
  the signed session identity containing alias and role

### `backend/app/case_loader.py`

This loads cases from disk.

It:
- reads case metadata from JSON
- reads suspects from JSON
- reads evidence docs from Markdown with YAML front matter
- reads prompt text files
- turns relative asset paths into URLs served by FastAPI

This is what makes the project data-driven.

### `backend/app/services/game.py`

This is the main business logic layer.

Responsibilities:
- load and reload cases
- create default player state
- search the current case
- rescan based on discovered context
- manage suspect conversations
- stream suspect dialogue
- validate theory-board links
- pin evidence
- save submissions
- compute community stats

If asked "where does the main logic live?", this is the answer.

### `backend/app/services/retrieval.py`

This handles search.

Important functions and ideas:
- `_tokenize()`
  simple tokenization
- `_extract_context_candidates()`
  regex-based extraction of names/locations
- `_cosine_similarity()`
  semantic similarity between vectors
- `build_chunks()`
  breaks evidence into paragraph chunks
- `search()`
  scores chunks using keyword overlap, entity matches, and embeddings
- `surface_from_context()`
  reruns search based on contexts
- `derive_contexts()`
  pulls likely useful entities or terms from text

Important point:
- embeddings are optional
- if Ollama embeddings fail, the search still works using keyword/entity logic

### `backend/app/services/dialogue.py`

This handles suspect replies.

It has two paths:

1. Ollama path
- build a prompt payload
- call `/api/chat`
- expect strict JSON in normal mode
- parse reply and state deltas

2. Fallback path
- use pressure triggers
- compare user message to evidence or trigger terms
- reveal facts in sequence
- update trust, guardedness, suspicion, and context deterministically

Important methods:
- `generate()`
- `stream_reply()`
- `score_reply()`
- `_heuristic_response()`

### `backend/app/database.py`

This handles persistence.

Main design:
- shared logic in `BaseDatabase`
- `SQLiteDatabase` and `PostgresDatabase` only override dialect-specific behavior

Stored data:
- player state
- conversations
- theory submissions

Database detail worth understanding:
- SQLite stores JSON-like fields as text
- PostgreSQL stores them as `JSONB`
- UPSERT is used to update player and conversation state

### `backend/app/auth.py`

This issues and verifies signed tokens.

How it works:
- user registers or logs in with alias and password
- admin aliases also require a configured secret code
- the issued token payload contains alias, role, and timestamp
- payload is base64-encoded
- HMAC-SHA256 signs it with the server secret
- later requests verify the signature before trusting the alias

Role handling:
- aliases in `INVESTIGATION_ADMIN_ALIASES` become `admin`
- every other alias becomes `player`
- the app has a real local account table, but authorization is still intentionally lightweight with only two roles: `player` and `admin`

### `backend/app/dependencies.py`

This contains dependency injection and auth extraction.

Important detail:
- `get_player()` reads the bearer token from `Authorization`
- invalid or missing tokens return `401`
- successful auth returns a principal object with both alias and role

### `backend/app/services/authoring.py`

This makes the system reusable instead of fixed to one case.

It supports:
- creating a new case scaffold
- generating a draft case from a pasted case brief
- saving case config
- saving suspect config
- rewriting archive Markdown files
- rewriting prompt text files
- saving uploaded assets into case folders
- assigning template images for generated cases
- auto-generating unique draft case IDs from the case title when the author leaves the ID blank
- approving draft cases when the current user is an admin

Suspects can also carry authored voice information such as:
- personality traits
- speaking style
- catchphrase
- verbal tells
- outward goal
- protective target and reason

### `backend/app/services/dialogue.py`

This file is where most of the AI-specific behavior lives.

Current behavior:
- the backend asks Ollama for the visible suspect reply text
- the backend uses retrieved archive snippets as grounding context
- streamed interrogation replies come directly from Ollama token output when available
- non-stream replies also try Ollama first, but use deterministic backend logic for trust, guardedness, suspicion, and revealed facts
- if Ollama fails, times out, or returns awkward metadata-heavy text, the backend sanitizes it or falls back to a cleaner heuristic reply

Why this matters:
- the user usually gets model-generated dialogue
- game progression remains stable because state updates do not depend entirely on fragile model JSON output
- bad outputs like raw "speaking style" narration are less likely to reach the UI

## 8. Frontend walkthrough

### `frontend/src/App.tsx`

This is the routed shell.

It:
- loads cases
- resolves whether the current session is a `player` or `admin`
- renders the searchable home/library screen
- sets up route-based views
- renders navigation rails
- manages modal media preview
- wires views to shared state and async actions

Routes include:
- `/`
- `/intake`
- `/archive`
- `/interrogation`
- `/board`
- `/submission`
- `/community`
- `/authoring`

### `frontend/src/context/GameContext.tsx`

This is the main client-side state store.

It keeps:
- alias and alias draft
- session role
- cases
- pending cases
- selected case, suspect, and document
- case detail and save state
- conversations
- search query and results
- rescan results
- community stats
- derived UI fields like board nodes, pinned docs, contradiction items, clue cards, prompts

Why this matters:
- the app avoids scattered local state
- one reducer keeps UI state consistent across views

### `frontend/src/context/useGameActions.ts`

This is the async action layer.

It:
- calls the backend API
- updates the reducer
- refreshes state after mutations
- implements streaming talk logic

The streaming flow:
1. append detective turn
2. append empty suspect turn
3. read stream chunks
4. keep updating the suspect bubble
5. refresh final saved state

### `frontend/src/api.ts`

This is the frontend API wrapper.

It:
- obtains a signed session token on demand
- caches the resolved session role
- caches that token in memory and `localStorage`
- attaches auth headers
- normalizes case asset URLs
- exposes typed methods for all endpoints

### `frontend/src/views/*.tsx`

Views are split by user workflow:

- `HomeView.tsx`
  searchable case library and admin pending-review list
- `IntakeView.tsx`
  opening case overview
- `ArchiveView.tsx`
  document reading, search, rescan, evidence pinning
- `InterrogationView.tsx`
  questioning, confrontation, streamed transcript
- `BoardView.tsx`
  graph-based evidence linking with React Flow
- `SubmissionView.tsx`
  final theory submission
- `CommunityView.tsx`
  aggregate results

### `frontend/src/AuthoringStudio.tsx`

This is an internal editor for the content system.

It lets users:
- create case scaffolds
- generate draft cases from pasted briefs
- edit case metadata
- edit archive domains and location dossiers
- edit suspects
- edit evidence documents
- edit prompts
- upload assets
- edit advanced rules as JSON

This is one of the strongest "systems design" features in the repo.

## 9. End-to-end flow

### A. App startup

1. frontend restores or creates a signed session
2. backend resolves that session as `player` or `admin`
3. frontend loads approved public cases
4. if the session is `admin`, frontend also loads pending draft cases
5. user selects a case from the home screen
6. backend returns case detail and save state
7. if no player state exists, backend creates a default one

### B. Role-based access flow

1. players can only see approved cases in the public library
2. admins can see approved cases plus pending draft cases
3. draft cases remain privately playable for their owner/admin path on the backend
4. only admins can approve a case
5. once approved, the case appears in the public home screen and `GET /cases`

### C. Archive search flow

1. user enters query
2. backend searches unlocked documents only
3. documents are chunked into paragraphs
4. each chunk is scored by keywords, entity tags, and optional embeddings
5. top results are returned
6. contexts discovered from the query/results may be saved

### D. Rescan flow

1. user triggers rescan
2. backend checks discovered contexts
3. matching `rescan_rules` unlock new docs/suspects
4. updated state is stored
5. surfaced results are returned

### E. Dialogue flow

1. user asks a suspect a question
2. frontend opens the stream endpoint
3. backend streams reply tokens from Ollama
4. backend retrieves supporting snippets from unlocked archive documents
5. frontend updates the reply live
6. backend saves the exact reply that was streamed
7. trust/guardedness/suspicion/context are updated

### F. Evidence board flow

1. user proposes a link between two nodes
2. backend checks against authored valid links
3. a correct link may unlock more content
4. frontend adds visual edges to the graph

### G. Submission flow

1. user selects culprit
2. user writes motive and timeline
3. backend requires minimum evidence count
4. submission is saved
5. aggregate community stats are updated

### H. Draft generation and approval flow

1. a creator or admin opens the authoring studio
2. they either scaffold a blank case or paste a semi-structured case brief
3. if they leave the case ID blank, the backend generates a unique draft ID automatically from the title
4. the backend parses the brief, extracts structure, and generates a draft case bundle
5. the generated case starts as `draft`
6. template suspect/evidence/location images are assigned automatically
7. the draft can be edited and tested privately
8. an admin reviews and approves it
9. the case becomes publicly visible in the home screen

## 10. How search works in plain language

This project does not use a large search engine or vector database.
Instead, it uses a smaller local retrieval approach:

1. break docs into chunks
2. compare query words to chunk words
3. boost chunks whose entity tags match
4. if embeddings are available, compare meanings too
5. sort and return best chunks

That means the search is:
- lightweight
- local
- understandable
- good enough for a small authored corpus

## 11. How embeddings are used here

Embeddings are mainly used in the retrieval layer.

What happens:
- the query is embedded
- a chunk may also be embedded
- cosine similarity estimates semantic closeness
- that score is added to the keyword/entity score

Important interview-safe point:

> "Embeddings in this project improve document search by helping the system find related meaning, not just exact matching words."

## 12. How Ollama is used here

Ollama is a local model server.

In this repo it is used for:

1. Chat generation
- suspect dialogue replies through `/api/chat`

2. Streaming generation
- token-by-token replies through `/api/chat` with streaming enabled

3. Embeddings
- text vectors through `/api/embed`

4. Retrieval-grounded interrogation
- retrieved archive snippets are passed into dialogue prompts so suspect replies can be tied more closely to case material
- suspect replies are now hardened so the system tries to surface plain speech instead of authoring metadata or narrator-style prose

Important practical point:
- the app does not train models
- it calls already-available local models through Ollama's API

## 13. Security and correctness improvements already present

These are strong interview talking points:

- Private suspect truth is hidden from normal case-detail responses.
- Signed bearer tokens replace a spoofable plain alias header.
- Case reload uses a lock, so in-memory cases are not swapped unsafely during concurrent requests.
- Streamed reply persistence was fixed so the saved text matches exactly what the user saw.
- Embedding cache size is capped to avoid unlimited growth.
- CORS is configurable.

## 14. What this project is good at

- data-driven case loading
- clean separation between retrieval, dialogue, persistence, and authoring
- lightweight semantic search
- live streaming UI updates
- reusable authoring system
- local-first AI integration through Ollama

## 15. Honest limitations

These are safe to admit in interviews:

- It is not a large-scale search system.
- It does not use a vector database.
- It does not train or fine-tune models.
- The fallback dialogue logic is simple and rule-based.
- Non-stream suspect dialogue still depends on local-model latency and output quality.
- Search is tuned for a small authored document set, not huge corpora.
- It is not a classical always-grounded RAG chatbot.

## 16. How to describe the AI part honestly

Safest phrasing:

> "The project integrates LLM-powered dialogue and embedding-based document search through Ollama. It also retrieves relevant archive snippets to ground suspect replies, so it is retrieval-assisted and partially RAG-like, though not a strict textbook RAG chatbot."

If you want something even simpler:

> "The AI part is mainly local model inference through Ollama for chat and embeddings, plus retrieval over authored documents to ground suspect dialogue."

## 17. Interview questions and strong answers

### "What is the main idea of the project?"

> "It is a full-stack case investigation platform where the frontend lets users explore evidence and question suspects, while the backend loads authored cases, stores player progress, searches documents, streams AI replies, and unlocks new content based on rules."

### "Where is most of the logic?"

> "The main logic is in `backend/app/services/game.py`. That service coordinates case state, search, rescans, dialogue, board links, and submissions."

### "What AI is actually used?"

> "Ollama is used for two main AI tasks: generating suspect replies and generating embeddings for better search. The backend also retrieves relevant archive snippets to ground dialogue, and it has a fallback path so the app still works if the model is unavailable."

### "How does search work?"

> "The backend splits unlocked documents into paragraph-sized chunks, scores them with keyword overlap and matching entity tags, and optionally adds an embedding similarity score. Then it returns the best results with snippets."

### "What are embeddings?"

> "Embeddings are number-based representations of text. They let the system compare meaning between a query and document chunks, so search is not limited to exact word matches."

### "Is this a RAG system?"

> "It uses retrieval and embeddings, but I would describe it as retrieval-assisted rather than a pure textbook RAG chatbot. Search and discovered context influence progression and evidence handling, but the app is not always retrieving top passages and injecting them into every response."

### "How does streaming work?"

> "The frontend calls a streaming endpoint and reads chunks as they arrive. The backend yields tokens from Ollama, and the frontend updates the current suspect message live. The backend then stores the final streamed text exactly as shown."

### "How are new cases added?"

> "A case is mostly data. There is a case config file, suspect config file, archive Markdown documents, prompt files, and assets. The authoring studio can scaffold and edit those files without changing the core app logic."

## 18. What to study first before an interview

If you only have 30 to 45 minutes:

1. Read `backend/app/main.py`
2. Read `backend/app/services/game.py`
3. Read `backend/app/services/retrieval.py`
4. Read `backend/app/services/dialogue.py`
5. Read `frontend/src/context/GameContext.tsx`
6. Read `frontend/src/context/useGameActions.ts`
7. Read `frontend/src/App.tsx`
8. Read `frontend/src/AuthoringStudio.tsx`
9. Read `cases/case-001/case.json`
10. Read `cases/case-001/archive/doc-001-incident-summary.md`

## 19. Longer study roadmap for AI/ML/LLMs

If you are starting from zero, study in this order:

### Stage 1: AI and ML basics

Learn:
- what AI is
- what ML is
- what training vs inference means
- what a model is

### Stage 2: NLP and LLM basics

Learn:
- what tokens are
- what prompts are
- what transformers are
- what context windows are
- what LLMs do well and poorly

### Stage 3: Embeddings and retrieval

Learn:
- what embeddings are
- why semantic search helps
- cosine similarity
- chunking
- keyword search vs semantic search

### Stage 4: RAG

Learn:
- the standard retrieve-then-generate loop
- how external docs ground model responses
- why RAG helps with freshness and private data

### Stage 5: Map those ideas back to this repo

Understand:
- where embeddings are used
- where chat generation happens
- where fallback logic lives
- why this repo is retrieval-assisted but not a perfect textbook RAG pipeline

## 20. Further study links

These links were chosen because they are stable, well-known, and good starting points.

### AI and ML basics

- Google: What is ML?
  [https://developers.google.com/machine-learning/intro-to-ml/what-is-ml](https://developers.google.com/machine-learning/intro-to-ml/what-is-ml)
- Google Machine Learning overview
  [https://developers.google.com/machine-learning](https://developers.google.com/machine-learning)
- Google Machine Learning Glossary
  [https://developers.google.com/machine-learning/glossary](https://developers.google.com/machine-learning/glossary)

### LLM and transformer basics

- Hugging Face LLM Course introduction
  [https://huggingface.co/course](https://huggingface.co/course)
- Hugging Face: Transformers, what can they do?
  [https://huggingface.co/course/en/chapter1/3](https://huggingface.co/course/en/chapter1/3)
- Hugging Face: How do Transformers work?
  [https://huggingface.co/course/chapter1/4](https://huggingface.co/course/chapter1/4)
- Hugging Face Transformers docs
  [https://huggingface.co/docs/transformers](https://huggingface.co/docs/transformers)

### Embeddings

- OpenAI concepts page for embeddings and tokens
  [https://platform.openai.com/docs/concepts](https://platform.openai.com/docs/concepts)
- OpenAI embeddings API reference
  [https://platform.openai.com/docs/api-reference/embeddings](https://platform.openai.com/docs/api-reference/embeddings)
- Ollama embeddings capability/docs
  [https://docs.ollama.com/capabilities/embeddings](https://docs.ollama.com/capabilities/embeddings)
- Ollama embed API
  [https://docs.ollama.com/api/embed](https://docs.ollama.com/api/embed)

### Ollama

- Ollama docs home
  [https://docs.ollama.com/](https://docs.ollama.com/)
- Ollama API introduction
  [https://docs.ollama.com/api](https://docs.ollama.com/api)

### RAG

- Elastic: What is RAG?
  [https://www.elastic.co/what-is/retrieval-augmented-generation/](https://www.elastic.co/what-is/retrieval-augmented-generation/)
- Elastic RAG docs page
  [https://www.elastic.co/guide/en/elasticsearch/reference/current/_retrieval_augmented_generation.html](https://www.elastic.co/guide/en/elasticsearch/reference/current/_retrieval_augmented_generation.html)
- Original RAG paper
  [https://arxiv.org/abs/2005.11401](https://arxiv.org/abs/2005.11401)

## 21. What to memorize if you are short on time

Memorize this:

> "The project is a full-stack AI-assisted case platform. Cases are stored as structured files on disk, so the app is data-driven. The backend loads those cases, stores each player's progress, searches documents using keywords and embeddings, streams suspect replies from Ollama, and unlocks new content based on authored rules. The frontend keeps shared state in one place and supports archive search, interrogation, theory building, submission, and in-app case authoring."

And memorize this AI explanation:

> "The AI part of the project uses Ollama for text generation and embeddings. Embeddings help search find related meaning, not just exact word matches. The backend also retrieves relevant archive snippets to ground suspect dialogue, so it is retrieval-assisted and partly RAG-like, though not a strict textbook RAG chatbot."
