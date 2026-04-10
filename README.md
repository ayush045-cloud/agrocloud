# Agro Mind – Kisan App · Backend

A Python/Flask backend for the **Agro Mind - Kisan App** single-page farming assistant.

## Features

| Endpoint | Description |
|---|---|
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

## Quick Start

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

The server starts at **http://127.0.0.1:5000**.

Open `index.html` in your browser (or serve it with a local HTTP server) and the frontend will automatically connect to the backend.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (for AI endpoints) | Anthropic API key for Claude |
| `PORT` | No | Override the default port (5000) |

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
