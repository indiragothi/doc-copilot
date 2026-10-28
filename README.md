# Document Copilot

An internal AI chatbot that lets analysts query a corpus of documents in plain English and get sourced, citable answers.

## The client

**Driftwood Capital** — fictional independent investment research firm. Their analysts spend half their week reading 10-Ks and 10-Qs before they can produce any original analysis. Document Copilot eats that intake work so they can skip straight to insight.

Full brief: [docs/client-brief.md](docs/client-brief.md)

## Stack

| Layer              | Choice                                               |
| ------------------ | ---------------------------------------------------- |
| Backend            | Python + FastAPI                                     |
| Frontend           | Vite + React SPA + TypeScript                        |
| Database           | Supabase Postgres (users, chats, documents, chunks)  |
| Migrations         | SQLAlchemy models + Alembic                          |
| Retrieval          | Supabase `pgvector` + Postgres full-text search      |
| Auth               | Supabase Auth (email only)                           |
| Hosting            | Railway                                              |
| LLM                | Google Gemini (free tier)                            |
| Embeddings         | NVIDIA Nemotron embed 1B (OpenAI-compatible API)     |

## Repo layout

```text
document-copilot/
├── CLAUDE.md           # agent instructions (read first)
├── README.md           # this file
├── data/               # local corpus + download script (payloads gitignored)
├── docs/
│   └── client-brief.md # the client one-pager
├── backend/            # FastAPI service
└── frontend/           # React SPA (Vite)
```

## Prerequisites

Install these before setting up `backend/` or `frontend/`:

| Tool | Version | Used for | Install |
| ---- | ------- | -------- | ------- |
| [Python](https://www.python.org/downloads/) | 3.12+ | Backend runtime | OS package manager or python.org |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Backend deps + `data/download.py` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Node.js](https://nodejs.org/) | 20+ (LTS) | Frontend toolchain | nodejs.org or `nvm install --lts` |
| [pnpm](https://pnpm.io/installation) | latest | Frontend package manager | `corepack enable && corepack prepare pnpm@latest --activate` |

You also need accounts/keys for external services once the app is wired up. Start with [docs/guides/supabase-setup.md](docs/guides/supabase-setup.md) (account + project), then create a [Gemini API key](https://aistudio.google.com/apikey) (`GEMINI_API_KEY`, chat model `gemini-3.1-flash-lite`) and an [NVIDIA API key](https://build.nvidia.com) (`NVIDIA_API_KEY`, embeddings `nvidia/nemotron-3.5-embed-1b`, 1024 dimensions). Both have free tiers and need no card.

## Running locally

To be added during the build. Setup guides:

- [Supabase](docs/guides/supabase-setup.md) — account, hosted project (dashboard or CLI)
- [Backend](docs/guides/backend-setup.md)
- [Frontend](docs/guides/frontend-setup.md)

## Sample SEC data

Use the standalone downloader to fetch a small local 10-K sample from SEC EDGAR.
Edit the params at the top of `data/download.py`, especially `USER_AGENT`, then run:

```bash
uv run data/download.py
```

By default this downloads the latest 5 10-K filings for AAPL, MSFT, NVDA, AMZN, and GOOGL into year folders under `data/downloads/` and writes a `manifest.json`.
`data/convert_to_markdown.py` then converts them to Markdown and Docling JSON, and the `backend/ingest/` scripts load them into Supabase. The current build ingests all 25 filings: Apple, Microsoft, NVIDIA, Amazon and Alphabet, FY2021–2025 (4,530 chunks).
Downloaded files are gitignored; the `data/` folder itself stays in git for the script and notes.

To add or refresh filings in Supabase, run from `backend/` (needs `DATABASE_URL` and `NVIDIA_API_KEY`):

```bash
uv run python -m ingest.load_documents   # source_documents rows, idempotent
uv run python -m ingest.load_chunks      # chunk + embed; skips filings already loaded
```

`load_chunks` takes `--dry-run` (count chunks and tokens, no embedding calls). Never run two ingestions at once.
