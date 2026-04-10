# Agro Mind – Kisan App

A full-stack farming assistant: **Python/Flask backend + single-page HTML frontend** served together from one process.

## Features

| Endpoint | Description |
|---|---|
| `GET /` | Serves the frontend (index.html) |
| `POST /api/dashboard` | Farm overview – field statuses & alerts |
| `POST /api/irrigation/schedule` | AI-powered irrigation schedule |
| `POST /api/irrigation/run` | Log irrigation start |
| `POST /api/irrigation/stop` | Log irrigation stop |
| `POST /api/disease/analyze` | Leaf disease detection via Claude Vision |
| `POST /api/chat` | Kisan AI conversational assistant |
| `POST /api/crop-advisor` | AI crop recommendations |

## Prerequisites

* Python 3.11+
* An [Anthropic API key](https://console.anthropic.com/) (for AI features)

## Deploy Online (Render.com – free tier)

1. **Push this repo to GitHub** (if not already done)
2. Go to [https://render.com](https://render.com) and sign up / log in
3. Click **New → Web Service** → connect your GitHub repo
4. Render auto-detects `render.yaml` — click **Apply**
5. In the **Environment** tab, add:
   - `ANTHROPIC_API_KEY` = `sk-ant-...` (your key from https://console.anthropic.com/)
6. Click **Deploy** — your app will be live at `https://agrocloud.onrender.com` (or similar URL)

That's it — the same URL serves both the frontend and the API.

---

## Deploy Online (Railway.app – alternative)

1. Go to [https://railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project → Deploy from GitHub repo** → select this repo
3. Add environment variable `ANTHROPIC_API_KEY` in the **Variables** tab
4. Railway detects the `Procfile` and deploys automatically

---

## Local Development

```bash
# 1. Clone the repository (if you haven't already)
git clone https://github.com/ayush045-cloud/agrocloud.git
cd agrocloud

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."   # macOS / Linux
set ANTHROPIC_API_KEY=sk-ant-...        # Windows CMD

# 5. Start the server
python app.py
```

The server starts at **http://localhost:5000** and serves both the frontend and the API.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (for AI endpoints) | Anthropic API key for Claude |
| `PORT` | No | Override the default port (5000) |
| `FLASK_DEBUG` | No | Set to `1` to enable debug mode (development only) |

## Data Storage

Irrigation run/stop events are persisted in a local **SQLite** database (`agrocloud.db`) that is created automatically when the server starts. No external database setup is required.

## API Reference

### `POST /api/dashboard`
```json
{ "farmer": { "name": "Ramesh", "village": "Ludhiana", ... } }
```
Returns field statuses, alerts, and next irrigation info.

---

### `POST /api/irrigation/schedule`
```json
{
  "farmer": { ... },
  "entries": [{ "field": "Field A", "last_watered": "2024-06-01" }]
}
```
Returns an AI-generated irrigation plan per field.

---

### `POST /api/irrigation/run`
```json
{ "started_at": "2024-06-05T08:00:00Z", "duration_minutes": 60, "field": "Field A", "farmer": { ... } }
```

---

### `POST /api/irrigation/stop`
No body required. Marks the most recent open run as stopped.

---

### `POST /api/disease/analyze`
```json
{ "image": "data:image/jpeg;base64,...", "farmer": { ... } }
```
Uses **Claude 3.5 Sonnet** vision to identify plant diseases.

---

### `POST /api/chat`
```json
{ "message": "Which fertiliser for wheat?", "history": [], "farmer": { ... } }
```
Returns `{ "reply": "..." }`.

---

### `POST /api/crop-advisor`
```json
{ "soil": "Sandy loam", "season": "Rabi", "water": "Canal", "farmer": { ... } }
```
Returns a JSON array: `[{ "name": "Wheat", "emoji": "🌾", "why": "..." }]`.
