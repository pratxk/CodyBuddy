---
title: AppSmith API
emoji: 🔨
colorFrom: orange
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# AppSmith API (CodyBuddy engine)

A LangGraph build agent: **planner → architect → coder**, plus VibeEngineer,
OnCall auto-repair, IntakeAgent, per-user Neon persistence, and a 7-provider
$0 model fallback chain. Serves the AppSmith frontend over FastAPI + SSE.

> Configuration (API keys, POSTGRES_URL, JWT_SECRET, GOOGLE_CLIENT_ID,
> ALLOWED_ORIGINS) is provided via **Space secrets**, never committed.

## Usage

```bash
uv run main.py "Build a colourful calculator app in html css and js"
uv run main.py            # prompts interactively
```

## How it works

1. **Planner** — turns the request into a JSON plan (name, tech stack, features, file list).
2. **Architect** — breaks the plan into ordered, self-contained per-file tasks.
3. **Coder** — generates **all files concurrently** and writes them to `generated_project/`.

## Why it's fast & reliable

Designed after the NourishBot backend pattern:

- **OpenAI-compatible client directly** — no LangChain `with_structured_output`
  (which forces fragile tool/json-schema mode). We prompt for JSON / raw text and
  parse robustly, with a validation-retry loop on the structured steps.
- **Groq by default** — LPU inference is ≈5–10× faster per token than NVIDIA NIM.
- **Parallel coder** — files are generated concurrently (ThreadPoolExecutor), so
  wall-clock ≈ the slowest single file, not the sum of all of them.
- **Bounded `max_tokens`** on every call.

> Reference build (3-file calculator) went from **~15 min (and failing)** to **~9 s**.

## Configuration (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `groq` if `GROQ_API_KEY` set, else `nvidia` | `groq` \| `nvidia` |
| `GROQ_API_KEY` | — | required for Groq |
| `NVIDIA_API_KEY` | — | required for NVIDIA NIM |
| `PLANNER_MODEL` | provider default | e.g. `llama-3.3-70b-versatile` |
| `CODER_MODEL` | provider default | override for a stronger coder model |

Provider defaults: Groq → `llama-3.3-70b-versatile`, NVIDIA → `meta/llama-3.1-70b-instruct`.

### Going even faster

- Set `CODER_MODEL=llama-3.1-8b-instant` (Groq) for near-instant small apps.
- Bump `MAX_CONCURRENCY` in `agent/graph.py` if your provider rate limits allow.
