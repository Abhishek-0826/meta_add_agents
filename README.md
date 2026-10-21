# AdPilot Backend

AI-powered Meta (Facebook/Instagram/WhatsApp) ads campaign generation.
Built from the design doc: FastAPI + LangGraph agent pipeline + Gemini Flash
+ PostgreSQL + Redis/RQ + Meta Marketing API.

**The one rule everything else serves:** no ad is ever created in ACTIVE
status. Ever. Every campaign is created PAUSED, surfaced to a human for
review, and only goes live on an explicit second action. See
`app/agents/budget_guard.py`.

This package covers the **backend and agent pipeline only** (no React
frontend) and assumes you've already done the Meta setup checklist
(design doc §9) and have your own PostgreSQL instance ready.

## What's inside

```
app/
  models/       SQLAlchemy models — one file per table in the design doc's data model
  schemas/      Pydantic request/response schemas
  agents/       The LangGraph pipeline: research -> strategy -> copywriter ->
                translation (conditional) -> creative -> compliance -> assembly
                -> budget_guard
  services/     LLM client (Gemini/Groq/Ollama via LiteLLM), Meta API wrapper,
                token encryption, idempotency helper
  worker/       RQ background tasks (pipeline run, Meta publish, activation)
  api/routes/   auth, clients, meta_oauth, briefs, jobs, campaigns, insights
  main.py       FastAPI app
alembic/        DB migrations (0001_initial creates every table)
tests/          pytest — includes full coverage of the Budget Guard
docker-compose.yml, Dockerfile, Caddyfile
```

## 1. Configure

```bash
cp .env.example .env
```

Fill in:
- `DATABASE_URL` — point at your existing Postgres (you said this is already provisioned)
- `GEMINI_API_KEY` — from Google AI Studio (free tier)
- `META_APP_ID` / `META_APP_SECRET` — from your Meta Developer App (design doc §9)
- `FERNET_KEY` — generate with:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `SECRET_KEY` — any long random string, used to sign JWTs

`GROQ_API_KEY` and `OLLAMA_BASE_URL` are optional fallbacks — the LLM
client tries Gemini first, then Groq, then Ollama, in that order, using
whichever ones you've configured.

## 2. Run with Docker (recommended)

```bash
docker compose up --build
```

This starts `api` (port 8000), `worker`, `redis`, `postgres`, and `caddy`.
If you already have your own Postgres, remove the `postgres` service block
from `docker-compose.yml` and just point `DATABASE_URL` at it.

Then run migrations:

```bash
docker compose exec api alembic upgrade head
```

API docs: http://localhost:8000/docs

## 3. Run locally without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

alembic upgrade head

# terminal 1
uvicorn app.main:app --reload

# terminal 2
python -m app.worker.run_worker
```

You'll need Postgres and Redis running locally (or reachable via `.env`).

## 4. Run tests

```bash
pytest
```

`tests/test_budget_guard.py` covers the safety-critical ceiling logic —
this is the one test file worth reading even if you skim everything else.

## 5. End-to-end flow (matches design doc §7)

1. `POST /api/auth/signup` — creates your org + first user, returns a JWT
2. `POST /api/clients` — onboard a client
3. `GET /api/meta/oauth/start?client_id=...` — get the Meta OAuth dialog URL,
   redirect the client to it
4. Meta redirects to `/api/meta/oauth/callback` automatically — token gets
   stored encrypted
5. `POST /api/meta/assets?client_id=...` — client picks their Ad Account/Page
6. `PUT /api/clients/{id}/guard-rails` — set spend ceilings (must be ≤ the
   system-wide `MAX_DAILY_BUDGET_INR` / `MAX_CAMPAIGN_LIFETIME_INR`)
7. `POST /api/briefs` — submit the intake form; returns a `job_id` immediately
8. `GET /api/jobs/{job_id}` — poll until `status = awaiting_review`
9. `GET /api/campaigns/{draft_id}` — see what the pipeline produced
10. `PATCH /api/campaigns/{draft_id}` — edit copy/budget if needed
11. `POST /api/campaigns/{draft_id}/approve` — publishes to Meta as **PAUSED**
    (spends nothing, just proves the payload is valid)
12. `POST /api/campaigns/{draft_id}/activate` — the only route that goes
    live; requires typing the exact daily budget back as confirmation

## Notes / things you still need to decide

These are called out as open questions in the design doc and are left as
explicit stubs rather than fake-implemented:

- **AI image generation** (`app/agents/creative_agent.py`) — not wired up.
  The agent currently requires client-uploaded assets and halts the
  pipeline if `creative_choice=generate` is requested. Plug in your
  preferred image model where marked.
- **Scheduled jobs** (token refresh, insights sync, DB backup, weekly
  report — design doc §11) — the insights sync function
  (`app/api/routes/insights.py::sync_all_insights`) and a manual
  `POST /api/insights/sync` trigger exist, but you'll need to wire actual
  cron (e.g. a `cron` container, GitHub Actions scheduled workflow, or
  APScheduler) to call it daily. Same for token refresh — there's no
  auto-refresh cron included yet.
- **Meta App Review / Business Verification** — required before you can
  onboard a second (external) client. Start this in parallel; dev mode
  works against your own ad account meanwhile.
