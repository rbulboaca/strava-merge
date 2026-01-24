# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Strava Activity Merger — merges multiple Strava activities into a single TCX file and uploads it back to Strava. The project has two interfaces:

1. **CLI script** (`strava_merge.py`) — standalone Python script for local use
2. **Web app** (`src/`) — full-stack app with FastAPI backend + React frontend, deployed to Azure

## Commands

### CLI Script (Root)
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python strava_merge.py
```

### Backend API (`src/api/`)
```bash
pip install -r src/api/requirements.txt
# Run locally with Azure Functions:
cd src/api && func host start --port 3100 --cors '*'
```

### Frontend (`src/web/`)
```bash
cd src/web && npm install
npm run dev          # Vite dev server on http://localhost:5173
npm run build        # tsc + vite build
npm run lint         # ESLint (strict, zero warnings allowed)
```

### Tests
```bash
# API unit tests (requires AZURE_COSMOS_CONNECTION_STRING):
cd src/api && pip install -r requirements-test.txt && pytest

# E2E tests (Playwright):
cd tests && npm install && npx playwright install && npx playwright test
npx playwright test --headed    # with browser UI
npx playwright test --debug     # debug mode
```

### Azure Deployment
```bash
azd up    # provision infrastructure + deploy all services
```

## Architecture

### Backend (`src/api/todo/`)
- **FastAPI** app running as an Azure Function (`catchAllFunction/` wraps it)
- **Beanie ODM** (async MongoDB) with Azure Cosmos DB (MongoDB API)
- **Settings** loaded from env vars or Azure Key Vault (secrets named with dashes map to `UPPER_SNAKE_CASE` attributes)
- **Auth flow**: OAuth 2.0 with Strava → tokens stored in `user_tokens` MongoDB collection
- **Merge logic** (`routes.py`): fetches activity streams (time, latlng, distance, altitude, HR, cadence, watts), concatenates points with cumulative distance offset, generates TCX XML, uploads via Strava API

Key env vars: `AZURE_COSMOS_CONNECTION_STRING`, `AZURE_COSMOS_DATABASE_NAME`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REDIRECT_URI`, `API_ALLOW_ORIGINS`, `API_ENVIRONMENT` (set to "develop" to disable CORS)

### Frontend (`src/web/`)
- **React 18** + **TypeScript** + **Vite** + **Fluent UI** (dark theme)
- Routes: HomePage (activity list/merge UI), CallbackPage (OAuth redirect handler)
- State: Redux-style reducers + context
- API client via Axios, base URL from `VITE_API_BASE_URL` (defaults to `http://localhost:3100`)

### Infrastructure (`infra/`)
- Azure Bicep templates provisioning: Azure Functions, Static Web App, Cosmos DB, Key Vault, Application Insights
- CI/CD via GitHub Actions (`.github/workflows/azure-dev.yml`) using Azure Developer CLI

### API Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/auth/url` | Get Strava OAuth authorization URL |
| GET | `/auth/callback?code=...` | Exchange auth code for tokens |
| GET | `/auth/status` | Check if user is authenticated |
| GET | `/activities` | List user's activities (last 30 days, max 50) |
| POST | `/merge` | Merge activities by ID, upload merged TCX to Strava |

### Data Flow (Merge)
1. Frontend sends `POST /merge` with `{activity_ids, name, description}`
2. Backend fetches each activity's streams from Strava API
3. Points are created with timestamps, lat/lng, distance, altitude, HR, cadence, watts
4. Distances are offset cumulatively for each subsequent activity
5. All points sorted by time → TCX XML generated → uploaded to Strava
