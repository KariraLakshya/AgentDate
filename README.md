# Agentic Dating

Every person is represented by an AI agent. The agent reads the person's LinkedIn and public Instagram, builds an evidence-backed profile, dates every other agent on their behalf in simulated dates, and returns a ranked list of best matches.

```
LinkedIn (public) + Instagram (public)
   -> Analyst agent      profile with evidence quotes + confidence
   -> Profile page       needs, hobbies, interests, values, humor, energy, lifestyle, partner wants
   -> Agents date        plan / speak / reflect loop, 8-10 turns, live over SSE
   -> Rankings           mutual fit, heatmap, stable pairings, post-date briefing
```

**Try it without any setup:** run the frontend and open `/demo`. It serves a pre-run result for 25 clearly labelled *synthetic* personas (300 dates) from static JSON and needs no backend.

## Rules the code enforces

1. **Consent gate.** `POST /api/people` requires `consent=true`; otherwise it returns 403 before any row or job is created.
2. **Public data only.** Cookie-free Apify actors only. A private or login-walled page becomes `not_readable`; no other route is tried. Empty actor results are never cached.
3. **No sensitive inference.** The analyst never infers religion, sexual orientation, gender identity, health, politics or ethnicity (prompt rule plus a post-filter with tests). Rankings use compatibility only.
4. **Evidence for every claim.** Each profile field carries a literal quote from the source text and a confidence score; claims whose quote is not in the source are dropped.
5. **Demo data is synthetic.** No real, named people are simulated.
6. **Data handling.** Only fields the analyst needs are kept, raw scrape payloads are purged after analysis, scraped URLs are cached for 24h, and `DELETE /api/people/{id}` (the "Delete my data" button) removes everything.

## Layout

```
frontend/         Next.js (App Router, TypeScript, Tailwind)
backend/
  api/            FastAPI routes, SSE, rate limit, jobs
  ingestion/      Apify provider, URL validation, normalisation, identity cross-check, 24h cache
  agents/         analyst, persona dating agent, referee, briefing, mock LLM handlers
  ranking/        weighted mutual fit, best moments, Gale-Shapley / Irving stable matching
  workers/        RQ-compatible jobs
  scripts/        round_robin.py (builds data/demo)
  db/             schema.sql, migrations, memory + Postgres stores, seed
  common/         shared pydantic contracts, LLM clients, config
data/personas/    25 synthetic personas (source-shaped fixtures)
data/demo/        pre-run 25-person result
```

Contracts live in `backend/common/models.py` and are mirrored in `frontend/lib/types.ts`; change them together.

## Run locally (mock mode, free)

```bash
# backend (in-memory store, deterministic mock LLM)
cd backend
pip install -r requirements.txt
ALLOW_FIXTURE_URLS=1 SEED_ON_START=1 uvicorn api.main:app --port 8000

# frontend
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

`ALLOW_FIXTURE_URLS=1` lets you submit `fixture://p01` ... `fixture://p25` instead of real links. Or run everything with Postgres, Redis and an RQ worker:

```bash
cp .env.example .env     # then edit
docker compose up --build
```

## Real mode

Put keys in `.env` (git-ignored) and set `LLM_MODE=groq`:

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY_STRONG` | analyst, referee, briefing |
| `GROQ_API_KEY_FAST` | dates (each key fails over to the other on rate limits) |
| `GROQ_MODEL_STRONG` / `GROQ_MODEL_FAST` | default `openai/gpt-oss-120b` / `openai/gpt-oss-20b` |
| `APIFY_TOKEN` | scraping |
| `LINKEDIN_ACTOR_ID` | `harvestapi~linkedin-profile-scraper` (no cookies, email search is never requested) |
| `INSTAGRAM_ACTOR_ID` | `apify~instagram-profile-scraper` |
| `DATABASE_URL`, `REDIS_URL` | Postgres / RQ; empty means in-memory and threads |
| `IP_HASH_SALT`, `CORS_ORIGINS` | set both in production |

`LLM_MODE=anthropic` with `ANTHROPIC_API_KEY` is also supported. Real runs cost money or free-tier quota: the full 300-date round-robin is thousands of model calls, so run it in mock mode (`python -m scripts.round_robin`) unless you mean to.

## Deploy

- **Frontend (Vercel):** import the repo, set **Root Directory** to `frontend`. `/demo` works with no environment variables. For the live features set `NEXT_PUBLIC_API_URL` to the hosted backend.
- **Backend:** needs a long-running host with Postgres and Redis (it streams SSE and runs a worker), so it does not fit Vercel. `backend/Dockerfile` and `docker-compose.yml` are ready for Railway, Render or Fly.

## Tests

```bash
cd backend && python -m pytest -q     # API, ingestion, agents, ranking, LLM client
cd frontend && npm test               # re-weighting logic and view smoke tests
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/people` | `linkedin_url`, `instagram_url`, `consent`; 403 without consent; rate limited |
| GET / DELETE | `/api/people/{id}` | status and profile / delete all data |
| POST | `/api/people/{id}/date-pool` | date the person against the pool |
| GET | `/api/dates/{id}`, `/api/dates/{id}/stream` | transcript, scores, flags / SSE |
| GET | `/api/people/{id}/rankings`, `/briefing` | ranked matches / post-date briefing |
| POST | `/api/people/{id}/ask` | "ask my agent why" |
| GET | `/api/pool/matrix`, `/api/demo` | mutual-fit matrix and stable pairings / demo bundle |
