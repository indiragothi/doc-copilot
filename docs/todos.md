# Document Copilot — implementation checklist

Work top to bottom. Each phase unlocks the next. Check items off as you go.

## Where to start: backend, frontend, or both?

**Start with foundation, then backend-led vertical slices.**

| Order | Why |
| ----- | --- |
| 1. Supabase + sample data | Everything persists here; you need a project and a corpus to test against. |
| 2. Backend schema + migrations | Auth, chat, retrieval, and citations all depend on the data model. |
| 3. Thin vertical slices | Wire auth, then a stubbed chat stream, then real RAG — each slice touches frontend + backend together. |
| 4. Frontend in parallel (lightly) | Scaffold the SPA early, but don't build citation UI or chat polish until the backend can return real grounded answers. |

The critical path is **data model → ingestion → retrieval → LLM → citations**. The frontend is mostly a streaming chat shell with auth and citation display — it shouldn't get far ahead of working APIs.

---

## Phase 0 — Prerequisites & foundation

- ✅ Install toolchain: Python 3.12+, `uv`, Node 20+, `pnpm` (see [README](../README.md))
- ✅ Create Supabase project and collect credentials ([supabase-setup](guides/supabase-setup.md))
- ✅ Create API keys: NVIDIA (embeddings) and Gemini (chat), both free and card-free. OpenRouter was dropped because its free NVIDIA models were unavailable (504) and slow
- ✅ Set `USER_AGENT` in `data/download.py` and download sample 10-K corpus:
  ```bash
  uv run data/download.py
  ```
- ✅ Confirm `data/downloads/manifest.json` lists AAPL, MSFT, NVDA, AMZN, GOOGL filings (2021–2025)

---

## Phase 1 — Backend scaffold & database

Goal: a running FastAPI service with a migrated Supabase schema.

- ✅ Init backend deps and project layout ([backend-setup](guides/backend-setup.md))
- ✅ `app/config.py` — settings module, fail fast on missing env vars
- ✅ `app/main.py` — FastAPI app, CORS, health check (`GET /health`)
- ✅ SQLAlchemy models in `app/database/models/`:
  - ✅ `users`
  - ✅ `source_documents`
  - ✅ `document_chunks` (embedding + generated `tsvector`)
  - ✅ `chat_threads`
  - ✅ `chat_messages`
  - ✅ `message_citations`
- ✅ Alembic init + first migration:
  - ✅ `create extension if not exists vector`
  - ✅ `vector(1536)` embedding column (changed to `vector(1024)` in migration `0002`)
  - ✅ generated `tsvector` column on chunks
  - ✅ HNSW index (vector) + GIN index (full-text)
  - ✅ RLS policies (users see only their own chats)
- ✅ `uv run alembic upgrade head` against Supabase direct connection
- ✅ `app/database/supabase.py` — user-scoped and service-role clients
- ✅ Verify: `uv run uvicorn app.main:app --reload` → health check returns 200

---

## Phase 2 — Auth (full stack)

Goal: analysts can sign in with email; backend rejects unauthenticated requests.

**Backend**

- ✅ `app/auth/dependencies.py` — verify `Authorization: Bearer <supabase_jwt>`, expose `get_current_user`
- ✅ Reject missing/expired tokens with `401` before any chat or retrieval work

**Frontend**

- ✅ Scaffold Vite + React + TypeScript + Tailwind + shadcn ([frontend-setup](guides/frontend-setup.md))
- ✅ `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- ✅ `src/lib/supabase.ts` — browser Supabase client
- ✅ `src/lib/http.ts` + `src/lib/api.ts` — fetch wrapper with automatic bearer token
- ✅ Sign-in / sign-up pages (email only, no SSO)
- ✅ Protected routes — redirect unauthenticated users to login
- ✅ Verify: sign up, sign in, token reaches backend on a test authenticated endpoint

---

## Phase 3 — Chat shell (vertical slice, stubbed)

Goal: end-to-end chat UI streaming from FastAPI, no real retrieval yet.

**Backend**

- ✅ Chat thread CRUD: list threads, create thread, load message history
- ✅ `POST /chat/stream` — accepts AI SDK message format, streams a stubbed assistant reply
- ✅ Persist user + assistant messages to `chat_messages` after stream completes
- ✅ `403` when user accesses another user's thread

**Frontend**

- ✅ React Router: login, chat list, chat thread routes
- ✅ AI SDK chat primitives pointed at `POST /chat/stream` with Supabase bearer token
- ✅ Thread sidebar (past conversations)
- ✅ Basic message list + input + streaming indicator
- ✅ Verify: create thread, send message, see streamed stub response, reload and see history

---

## Phase 4 — Ingestion pipeline

Goal: SEC filings in the corpus are parsed, chunked, embedded, and stored in Supabase.

**Scope:** all five companies, 25 filings, FY2021–2025. Apple was loaded first while the OpenRouter free tier (50 embedding requests a day) was the limit; after the move to NVIDIA's own API the other four were loaded in one session with no quota problem. To add or refresh filings, run `uv run python -m ingest.load_documents` and then `uv run python -m ingest.load_chunks` (resumable; do not run two at once).

Flow: `data/download.py` → `data/convert_to_markdown.py` (HTML → Markdown + Docling JSON) → `ingest.load_documents` (`source_documents`) → `ingest.load_chunks` (chunk, embed, `document_chunks`).

- ✅ `data/convert_to_markdown.py` — Docling converts every filing to Markdown (`data/markdown/`) and Docling JSON (`data/docling/`), same year folders and manifest
- ✅ Audit conversion: tables and narrative text spot-checked against the source HTML (no data loss; see known gaps below)
- ✅ `ingest/load_documents.py` — `source_documents` rows with filing metadata + full Markdown (idempotent; all 25 filings)
- ✅ `ingest/chunking.py` — Docling `HybridChunker`, 512-token cap, compact table rows, "Item N." section headings
- ✅ `ingest/embeddings.py` — NVIDIA `nvidia/nemotron-3.5-embed-1b`, 1024 dims requested from the API, `input_type` `passage` for chunks (searches use `query`). The earlier 8B model was unavailable, so the 714 Apple chunks were deleted and re-embedded
- ✅ `ingest/load_chunks.py` — `--dry-run`, `--test`, full run; per-filing transaction, idempotent re-run
- ✅ Generated `tsvector` populated for full-text search (verified on the test chunk)
- ✅ Unit tests: chunking, table rows, section headings, embedding dimension handling (`tests/ingest/`)
- ✅ Dry run: 4,530 chunks / ~1.84M tokens / 284 embedding requests across 25 filings
- ✅ One-chunk test: Apple FY2025 revenue table stored, 1024 dims, similarity 0.615 (relevant) vs 0.027 (unrelated)
- ✅ Run ingestion on the Apple corpus first: 5 filings, 714 chunks, all with 1024-dim embeddings
- ✅ Verify: chunk counts match the dry run; Apple revenue table found by full-text and vector search
- ✅ Ingested MSFT (995 chunks), NVDA (960), AMZN (864) and GOOGL (997): 25 filings, 4,530 chunks in total, all 1024-dim with a populated `search_vector`; a re-run skips every filing
- ✅ Verify: `scripts.smoke_retrieval` returns the right chunks for each of the five tickers and for an unfiltered cross-company question (export controls → NVIDIA risk factors)

Known gaps: `page` is empty (the HTML has no page numbers; page footers remain as text lines); only Item-level sections are captured, not sub-headings.

---

## Phase 5 — Retrieval

Goal: a user question returns ranked, relevant source passages.

- ✅ `retrieval/queries.py` — pgvector semantic search over `document_chunks`
- ✅ `retrieval/queries.py` — Postgres full-text search over `search_vector`
- ✅ `retrieval/fusion.py` — Reciprocal Rank Fusion in Python
- ✅ `retrieval/retriever.py` — query → fused ranked passages + neighbor chunks
- ✅ Unit tests: fusion ranking, query assembly (mock DB)
- ✅ Integration test (`@pytest.mark.integration`): real query against ingested corpus (written; not yet run)
- ✅ Verify: `scripts.smoke_retrieval` on the re-embedded Apple corpus returns the right chunks (revenue-mix table in Item 7, manufacturing-concentration risk factor in Item 1A, FY2025 segment note in Item 8)

---

## Phase 6 — LLM agent & grounding

Goal: grounded answers with enforced citations — the core product contract.

- ✅ `assistant/instructions.md` — product contract (cite everything, refuse to invent, no stock picks)
- ✅ PydanticAI agent (`assistant/agent.py`) with typed deps (`DocumentAgentDeps`) and output (`GroundedAnswer`: answer, `[n]` citations, `insufficient_evidence`)
- ✅ Agent tools: `search_filings`, `read_chunk`, `read_surrounding_chunks`; every returned passage is recorded in `deps.retrieved`, the allow-list for citations
- ✅ `chat/orchestrator.py` — one turn: agent (retrieve → answer → validate, up to two corrective retries) → verified answer; fails closed with a fixed message
- ✅ `grounding/validator.py` — every citation maps to a retrieved passage, quotes appear verbatim in the chunk, markers match the text; runs as the agent's output validator
- ✅ `chat/streaming.py` — AI SDK-compatible stream (text deltas + `data-citation` parts). The verified answer is streamed after validation, not token by token
- ✅ Persist `message_citations` linked to assistant messages (admin client: users have read-only RLS on that table); citation parts are also stored in the message's `parts`
- ✅ Unit tests: citation validation, grounding enforcement (fake models), message conversion, streaming, routes (`tests/grounding/`, `tests/assistant/`, `tests/chat/`)
- ✅ Validator also rejects empty answers, citations on an insufficient-evidence answer, and marker gaps (must be 1..N)
- ✅ Retrieval tuning (`retrieval_top_k`, `retrieval_candidate_k`, `retrieval_rrf_k`, `retrieval_neighbor_radius`) in `app/config.py`, env-overridable
- ✅ Batch `read_chunks` tool and tool-usage rules in the instructions (fewer model rounds)
- ✅ Per-tool timing and per-turn token usage in structlog events (`assistant/progress.py`, `turn_complete`)
- ✅ Smoke scripts: `scripts/smoke_retrieval.py` (Phase 5 check) and `scripts/smoke_assistant.py <query-key>` (Phase 6 check; keys: apple-mix, apple-suppliers, amazon-aws, q10-refusal, underspecified)
- ✅ Verify against [client-brief example questions](client-brief.md#example-analyst-questions) on Gemini `gemini-3.1-flash-lite` (`page` is empty, so "pages" means filing and section). Live smoke runs: `apple-mix` and `apple-suppliers` grounded with citations; `amazon-aws` and `q10-refusal` get correct "filings do not support this" answers; `underspecified` asks which company
  - ✅ Answers cite specific filings and sections
  - ✅ Under-specified questions get a clarifying question instead of a guess
  - ✅ Question 10 (generative AI margins) refuses to infer beyond filings
- ✅ Chat model moved from OpenRouter to Gemini (native Google client; 503s are retried, a 429 quota error fails fast with a "usage limit" message) after the NVIDIA-hosted models were slow (88 s to 15 min per answer, mostly reasoning tokens) or ignored the citation format
- ✅ Search passages shortened to 500 characters; the validator also checks exact figures against the cited chunks, accepts `...` in quotes and typographic quote variants, and rejects `[1, 2]`
- [ ] Known gaps: no LLM judge (claims are not checked against their quotes beyond figures); the model's own arithmetic is unchecked; answers took 4–16 s in the browser check but can take up to 3 min under Gemini free-tier load

---

## Phase 7 — Trust UI (citations & source passages)

Goal: analysts can verify every claim in one click — this is what makes the product usable.

- ✅ Citation chips/links on assistant messages (company, filing type, date, page/section)
- ✅ Source passage panel — show underlying excerpt for selected citation
- ✅ Empty states (no threads, no corpus match)
- ✅ Error states (auth expired, retrieval failure, grounding failure, network/CORS)
- ✅ Loading/streaming status during assistant run
- ✅ Assistant answers render as Markdown (tables, bold, lists) via `react-markdown` + `remark-gfm`; `[n]` chips work inside tables
- ✅ Sidebar is a drawer on small screens
- ✅ Verify in the browser: click a citation → see the exact passage from the filing with the quote highlighted; vague and out-of-corpus questions get a clarifying question or a refusal; mobile width works

---

## Phase 8 — Pilot readiness

Goal: 5 senior analysts can use it for a week and report ≥3 hours saved per analyst per week.

- ✅ README "Running locally" section — copy-paste commands for backend + frontend + env vars
- ✅ Seed or document how to ingest/update the corpus (README, "Sample SEC data")
- ✅ Smoke-test all 10 example questions from the client brief: most pass grounded with citations (single-company and risk-factor questions in 25–55 s); the heaviest multi-company questions (capex, geographic) sometimes hit Gemini's free-tier limit of 250K input tokens per minute (HTTP 429) or need a retry for citation format. A paid or multi-key Gemini setup removes the 429s
- ✅ Confirm chat history persists across sessions
- ✅ Delete a conversation: trash icon on hover in the sidebar (always visible on touch screens), `DELETE /chat/threads/{id}` (owner only; messages and citations cascade)
- [ ] Confirm ~40-user scale assumptions (no hardcoded single-user shortcuts)
- ✅ Basic structured logging on backend (`structlog`): `tool_finished`, `turn_complete`, `grounding_failed`
- [ ] Review latency: streaming starts within a few seconds for typical queries

---

## Phase 9 — Deployment (Railway)

- ✅ Dockerize: `backend/Dockerfile`, `frontend/Dockerfile` (nginx), `docker-compose.yml`; both images build, containers start, `/health` is 200, SPA deep links and CORS work
- [ ] Railway: backend service (Uvicorn, env vars, `ALLOWED_ORIGINS`)
- [ ] Railway: frontend service (Vite build, `VITE_*` env vars at build time)
- [ ] Supabase: re-enable email confirmation for production if disabled during dev
- [ ] Run `alembic upgrade head` against production Supabase (direct connection)
- [ ] Run ingestion against production database
- [ ] End-to-end test on deployed URLs with a real Driftwood-style email account

---

## Quick reference

| Doc | Purpose |
| --- | ------- |
| [client-brief.md](client-brief.md) | What Driftwood needs and example questions |
| [architecture.md](architecture.md) | System design, data model, streaming contract |
| [guides/supabase-setup.md](guides/supabase-setup.md) | Hosted Postgres + Auth |
| [guides/backend-setup.md](guides/backend-setup.md) | FastAPI + Alembic commands |
| [guides/frontend-setup.md](guides/frontend-setup.md) | Vite + React scaffold commands |