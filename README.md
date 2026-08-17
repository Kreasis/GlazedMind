# GlazedMind

GlazedMind is an AI Help Desk operations environment built for the Shipley Do-Nuts hackathon. It does more than search documentation: it reads live requests, retrieves verified procedures, communicates with customers, updates Monday, follows up by priority, and records measurable operational activity.

## Quick start for the Help Desk team

This repository is designed for teammates who do not work with code. You only need **Docker Desktop**, your company Ollama API key, and your Monday API token.

1. Download this private repository as a ZIP and extract it.
2. Install and open [Docker Desktop](https://www.docker.com/products/docker-desktop/).
3. Double-click `START_GLAZEDMIND.cmd`.
4. The first time only, paste your Ollama API key and Monday API token when requested.
5. Wait while GlazedMind builds, indexes the verified guides, and opens http://localhost:3000.

Your credentials are stored only in a local `.env` file on your computer. Git ignores this file, so it is never included in a commit. Later launches only require double-clicking `START_GLAZEDMIND.cmd` again.

To stop the application safely, double-click `STOP_GLAZEDMIND.cmd`. PostgreSQL data and your local configuration are preserved.

> **Private repository only:** this project includes internal runbooks and escalation contacts. Do not make the repository public without company approval.

## What the demo proves

GlazedMind implements a practical **Know → Act → Learn** workflow:

- **Know:** DOCX runbooks are extracted, embedded with `nomic-embed-text`, stored in PostgreSQL/pgvector, and returned with their documented steps and screenshots.
- **Act:** New Monday tickets receive a personalized acknowledgment and move from `New Reply` to `In Progress`. Tickets awaiting a customer receive priority-based follow-ups and can be resolved after three unanswered attempts.
- **Learn:** Interactive onboarding records readiness, mistakes, and skill gaps. The automatic knowledge-learning loop is intentionally planned for the next phase.

## Active modules

| Module | Purpose | State |
| --- | --- | --- |
| Monday Intake & Acknowledgment | Detect tickets, draft a contextual first response, and update status | Active |
| Workspace Troubleshooting | Return the complete verified procedure for the selected Monday ticket | Active |
| Documentation Chatbot | Hold a basic conversation and answer support questions from the Knowledge Base | Active |
| Dynamic Knowledge Base | Upload DOCX guides and index them immediately for Workspace and Chatbot | Active |
| Priority Follow-up Automation | Follow up by priority and resolve after three unanswered attempts | Active |
| Customer Portal | Create or link a customer request with Monday | Active |
| Escalation Directory | Present the verified contacts from the escalation guide | Active |
| Onboarding & Skill Gaps | Interactive training, assessment, and local readiness metrics | Demo |
| Impact Dashboard | Show persisted workflow actions and estimated time saved | Demo |
| Similar Resolved Cases | Retrieve evidence from historical resolved tickets | Planned |
| Knowledge Learning Loop | Draft new KB articles from resolved undocumented cases | Planned |

The live module manifest is available at `GET /api/v1/modules`.

## Technology

- Frontend: Next.js 16, React 19, TypeScript
- Backend: FastAPI, Python 3.12
- Ticketing: Monday GraphQL API
- Models: Ollama OpenAI-compatible API; `qwen3.5:4b` for language tasks and `nomic-embed-text` for embeddings
- Knowledge: DOCX extraction plus PostgreSQL 16 with pgvector
- Runtime: Docker Compose

The agents are separated by responsibility in `backend/app/agents`. They are coordinated by Python services rather than an external agent framework.

## Run the complete demo

The launcher above is the recommended team experience. Developers can also start it manually:

1. Copy `.env.example` to `.env`.
2. Add `MONDAY_API_TOKEN` and `OLLAMA_API_KEY`. The company server, models, and board are already configured in the template.
3. From the project root, run:

```powershell
docker compose up --build
```

4. On the first manual launch, index the bundled DOCX guides:

```powershell
docker compose exec backend python scripts/build_knowledge_index.py
```

5. Open:

- App: http://localhost:3000
- API documentation: http://localhost:8000/docs
- Health and runtime mode: http://localhost:8000/health

Docker builds the frontend and serves it with the Next.js production server. The backend waits for PostgreSQL and exposes its own health check before the frontend starts.

## Hackathon demo mode

`DEMO_MODE=true` permits `AUTO_FOLLOWUP_TIME_UNIT=minutes`. This compresses the production priority rules so all three follow-ups can be demonstrated in minutes:

- High priority: every 1 minute in demo; every 1 day in standard mode
- Medium priority: every 2 minutes in demo; every 2 days in standard mode
- Low priority: every 3 minutes in demo; every 3 days in standard mode

If `DEMO_MODE` is false or missing, the backend always uses days even when the environment requests minutes. The Impact page displays a visible notice whenever accelerated demo timing is active.

## Knowledge Base

Verified `.docx` files live in `backend/knowledge-base`. A document uploaded from the Knowledge Base page is:

1. saved permanently in that directory;
2. parsed into structured procedure entries and linked screenshots;
3. embedded with Ollama;
4. inserted or replaced in pgvector;
5. available immediately to Workspace and Chatbot.

There is no static JSON search index and no Excel ticket source.

## Local development

Backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm ci
npm run dev
```

## Verification

```powershell
cd backend
python -m unittest discover -s tests

cd ..\frontend
npm run build
```

## Project layout

```text
frontend/                 Next.js user experience
backend/app/agents/       Specialized agent responsibilities
backend/app/services/     Monday, knowledge, model, automation, and portal services
backend/prompts/          Agent-specific behavior policies
backend/knowledge-base/   Permanent verified DOCX sources
backend/data/             Local hackathon workflow state and extracted screenshots
docker-compose.yml        Frontend, backend, and pgvector runtime
START_GLAZEDMIND.cmd      One-click Windows launcher
STOP_GLAZEDMIND.cmd       Safe local shutdown
scripts/                  Team startup automation
```

## Scope and known limitations

This is a local hackathon build, so authentication, multi-tenancy, rate limiting, distributed workers, and multi-user training persistence are outside the current scope. Operational automation state is stored in local JSON files and is suitable for a single backend process. Similar resolved-case retrieval and the knowledge-learning loop are shown as planned, not active.

## Repository safety

The repository intentionally excludes `.env`, local tickets, customer portal cases, acknowledgment state, follow-up state, activity logs, generated screenshots, caches, dependencies, and database volumes. Never use `git add -f` to force any of those files into source control. Share credentials only through an approved company channel.
