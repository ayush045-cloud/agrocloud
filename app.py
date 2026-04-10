"""
Agro Mind - Kisan App  |  Flask Backend
Run:  python app.py
API:  http://127.0.0.1:5000
"""

import os
import json
import base64
import sqlite3
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Database (SQLite – single file, created automatically)
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "agrocloud.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS irrigation_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                field       TEXT,
                started_at  TEXT,
                stopped_at  TEXT,
                duration_minutes REAL,
                farmer_name TEXT
            )
            """
        )
        conn.commit()


init_db()

# ---------------------------------------------------------------------------
# Anthropic client (reads ANTHROPIC_API_KEY from environment)
# ---------------------------------------------------------------------------
_anthropic_client = None


def get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )
    return _anthropic_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
WATER_STATUS_KEYWORDS = {"drip", "sprinkler", "canal", "well", "rain", "bore"}


def _parse_fields(farmer: dict) -> list[dict]:
    """Return a list of {name, crop} dicts from farmerData."""
    names = [n.strip() for n in (farmer.get("fieldnames") or "").split(",") if n.strip()]
    crops = [c.strip() for c in (farmer.get("crops") or "").split(",") if c.strip()]
    result = []
    for i, name in enumerate(names):
        crop = crops[i] if i < len(crops) else (crops[0] if crops else "")
        result.append({"name": name, "crop": crop})
    return result


# ---------------------------------------------------------------------------
# 1. Dashboard
# ---------------------------------------------------------------------------
@app.route("/api/dashboard", methods=["POST"])
def dashboard():
    data = request.get_json(silent=True) or {}
    farmer = data.get("farmer") or {}

    fields_raw = _parse_fields(farmer)

    # Decide status for each field (simple rule: first field = good, rest rotate)
    statuses = ["good", "water", "critical"]
    fields_out = []
    for i, f in enumerate(fields_raw):
        fields_out.append(
            {
                "name": f["name"],
                "status": statuses[i % len(statuses)],
                "crop": f["crop"],
            }
        )

    first_field = fields_raw[0]["name"] if fields_raw else "Your field"

    alerts = []
    water_src = (farmer.get("water") or "").lower()
    if any(kw in water_src for kw in ["rain", "canal"]):
        alerts.append(
            {
                "type": "blue",
                "icon": "ℹ️",
                "message": "Weather Update",
                "sub": "Monitor rainfall before next irrigation cycle",
            }
        )
    else:
        alerts.append(
            {
                "type": "green",
                "icon": "✅",
                "message": "Irrigation Source OK",
                "sub": f"Water source: {farmer.get('water') or 'Not specified'}",
            }
        )

    return jsonify(
        {
            "next_irrigation": {"field": first_field, "when": "Tomorrow"},
            "alerts": alerts,
            "fields": fields_out,
        }
    )


# ---------------------------------------------------------------------------
# 2. Irrigation Schedule
# ---------------------------------------------------------------------------
@app.route("/api/irrigation/schedule", methods=["POST"])
def irrigation_schedule():
    data = request.get_json(silent=True) or {}
    farmer = data.get("farmer") or {}
    entries = data.get("entries") or []

    fields_raw = _parse_fields(farmer)

    # Build a map of last_watered dates from the submitted entries
    last_watered_map: dict[str, str] = {}
    for e in entries:
        if e.get("field") and e.get("last_watered"):
            last_watered_map[e["field"]] = e["last_watered"]

    today = datetime.date.today()
    fields_out = []
    for f in fields_raw:
        lw_str = last_watered_map.get(f["name"])
        days_since = None
        if lw_str:
            try:
                lw_date = datetime.date.fromisoformat(lw_str)
                days_since = (today - lw_date).days
            except ValueError:
                pass

        if days_since is None:
            status, when, water_needed, crop_stage = "water", "Today", "High", "Vegetative"
        elif days_since >= 7:
            status, when, water_needed, crop_stage = "urgent", "Immediately", "Critical", "Vegetative"
        elif days_since >= 4:
            status, when, water_needed, crop_stage = "water", "Today", "High", "Vegetative"
        elif days_since >= 2:
            status, when, water_needed, crop_stage = "good", "In 2 days", "Moderate", "Growing"
        else:
            status, when, water_needed, crop_stage = "done", "Next week", "Low", "Growing"

        fields_out.append(
            {
                "name": f["name"],
                "status": status,
                "crop": f["crop"],
                "when": when,
                "water_needed": water_needed,
                "crop_stage": crop_stage,
            }
        )

    # Build a concise AI suggestion using Claude
    ai_suggestion = ""
    urgent = [f for f in fields_out if f["status"] in ("urgent", "water")]
    try:
        field_summary = "; ".join(
            f"{f['name']} ({f['crop']}, last watered: {last_watered_map.get(f['name'], 'unknown')})"
            for f in fields_raw
        )
        prompt = (
            f"You are an expert agronomist advising a farmer in India.\n"
            f"Farmer: {farmer.get('name', 'Unknown')}, Village: {farmer.get('village', 'Unknown')}, "
            f"Water source: {farmer.get('water', 'unknown')}.\n"
            f"Fields: {field_summary}.\n"
            f"Today is {today.isoformat()}.\n"
            "Give a single short paragraph (2-3 sentences) of personalised irrigation advice."
        )
        msg = get_anthropic().messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        ai_suggestion = msg.content[0].text.strip()
    except Exception:
        if urgent:
            ai_suggestion = f"Water {urgent[0]['name']} as soon as possible — moisture levels are low."
        else:
            ai_suggestion = "Your fields look well-watered. Monitor soil moisture and water when the top 2 cm feels dry."

    return jsonify({"ai_suggestion": ai_suggestion, "fields": fields_out})


# ---------------------------------------------------------------------------
# 3. Run & Stop Irrigation
# ---------------------------------------------------------------------------
@app.route("/api/irrigation/run", methods=["POST"])
def irrigation_run():
    data = request.get_json(silent=True) or {}
    farmer = data.get("farmer") or {}
    with get_db() as conn:
        conn.execute(
            "INSERT INTO irrigation_runs (field, started_at, duration_minutes, farmer_name) VALUES (?,?,?,?)",
            (
                data.get("field", ""),
                data.get("started_at", datetime.datetime.utcnow().isoformat()),
                data.get("duration_minutes"),
                farmer.get("name", ""),
            ),
        )
        conn.commit()
    return jsonify({"success": True})


@app.route("/api/irrigation/stop", methods=["POST"])
def irrigation_stop():
    stopped_at = datetime.datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE irrigation_runs SET stopped_at=? WHERE stopped_at IS NULL",
            (stopped_at,),
        )
        conn.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# 4. Disease Analysis (Claude Vision)
# ---------------------------------------------------------------------------
@app.route("/api/disease/analyze", methods=["POST"])
def disease_analyze():
    data = request.get_json(silent=True) or {}
    farmer = data.get("farmer") or {}
    image_data: str = data.get("image", "")

    # Strip the data-URL prefix if present  (e.g. "data:image/jpeg;base64,...")
    if "," in image_data:
        header, image_data = image_data.split(",", 1)
        media_type = "image/jpeg"
        if "png" in header:
            media_type = "image/png"
        elif "gif" in header:
            media_type = "image/gif"
        elif "webp" in header:
            media_type = "image/webp"
    else:
        media_type = "image/jpeg"

    if not image_data:
        return jsonify({"type": "healthy", "title": "No image provided", "treatment": "", "noAlert": True})

    prompt = (
        "You are a plant pathologist AI. Carefully examine this leaf image.\n"
        "Identify any disease, pest damage, or nutrient deficiency visible.\n"
        f"Context: farmer from {farmer.get('village', 'India')} grows {farmer.get('crops', 'crops')}.\n\n"
        "Respond ONLY with a JSON object (no markdown) in this exact schema:\n"
        '{"type": "<healthy|warning|danger>", "title": "<short disease name or Healthy Crop>", '
        '"treatment": "<practical treatment advice in 2-3 sentences>", "noAlert": <true|false>}\n'
        'Set noAlert to true only when the crop is healthy.'
    )

    try:
        msg = get_anthropic().messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        raw = msg.content[0].text.strip()
        # Strip potential markdown fences
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        # Validate / sanitise
        result["type"] = result.get("type", "warning")
        if result["type"] not in ("healthy", "warning", "danger"):
            result["type"] = "warning"
        result.setdefault("title", "Analysis Complete")
        result.setdefault("treatment", "Consult your local agriculture officer.")
        result.setdefault("noAlert", result["type"] == "healthy")
        return jsonify(result)
    except json.JSONDecodeError:
        # Claude returned text but not parseable JSON — extract key info
        return jsonify(
            {
                "type": "warning",
                "title": "Disease Detected",
                "treatment": raw[:400] if raw else "Please consult your local agriculture officer.",
                "noAlert": False,
            }
        )
    except Exception as exc:
        return jsonify(
            {
                "type": "warning",
                "title": "Analysis Unavailable",
                "treatment": "Could not analyse the image. Please ensure ANTHROPIC_API_KEY is set and try again.",
                "noAlert": True,
            }
        ), 500


# ---------------------------------------------------------------------------
# 5a. Kisan AI Chat
# ---------------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    farmer = data.get("farmer") or {}
    message: str = data.get("message", "").strip()
    history: list = data.get("history") or []

    if not message:
        return jsonify({"reply": ""}), 400

    system_prompt = (
        "You are Kisan AI, a friendly and knowledgeable smart farming assistant for Indian farmers. "
        "Speak in simple, encouraging language. "
        "You can switch between English and Hindi if the farmer prefers. "
        f"The farmer's name is {farmer.get('name', 'the farmer')}, "
        f"from {farmer.get('village', 'their village')}. "
        f"They grow {farmer.get('crops', 'various crops')} on {farmer.get('acres', 'their')} acres "
        f"and use {farmer.get('water', 'an unspecified')} water source. "
        "Help them with crop advice, pest control, irrigation, weather, and market prices."
    )

    messages = []
    for h in history[-10:]:  # keep last 10 turns to stay within token limits
        role = h.get("role", "user")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})

    try:
        msg = get_anthropic().messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=600,
            system=system_prompt,
            messages=messages,
        )
        reply = msg.content[0].text.strip()
        return jsonify({"reply": reply})
    except Exception as exc:
        return jsonify({"reply": "Sorry, I am unable to respond right now. Please check your internet connection and try again."}), 500


# ---------------------------------------------------------------------------
# 5b. Crop Advisor
# ---------------------------------------------------------------------------
@app.route("/api/crop-advisor", methods=["POST"])
def crop_advisor():
    data = request.get_json(silent=True) or {}
    farmer = data.get("farmer") or {}
    soil: str = data.get("soil", "").strip()
    season: str = data.get("season", "").strip()
    water: str = data.get("water", farmer.get("water", "")).strip()

    if not soil or not season:
        return jsonify([]), 400

    prompt = (
        f"You are an expert Indian agronomist.\n"
        f"Farmer details — Village: {farmer.get('village', 'India')}, "
        f"Land: {farmer.get('acres', 'unknown')} acres, "
        f"Current crops: {farmer.get('crops', 'unknown')}.\n"
        f"Soil type: {soil}. Season: {season}. Water availability: {water or 'moderate'}.\n\n"
        "Recommend the 4 best crops to grow. "
        "Respond ONLY with a JSON array (no markdown) matching this schema exactly:\n"
        '[{"name": "CropName", "emoji": "🌱", "why": "One sentence reason"}]\n'
        "Use appropriate crop emojis."
    )

    try:
        msg = get_anthropic().messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        crops = json.loads(raw)
        if not isinstance(crops, list):
            crops = []
        # Ensure each item has required keys
        clean = []
        for c in crops:
            if isinstance(c, dict) and c.get("name"):
                clean.append(
                    {
                        "name": c.get("name", ""),
                        "emoji": c.get("emoji", "🌱"),
                        "why": c.get("why", ""),
                    }
                )
        return jsonify(clean)
    except json.JSONDecodeError:
        return jsonify([{"name": "Wheat", "emoji": "🌾", "why": "Widely suitable for most Indian soil types."}])
    except Exception:
        return jsonify([]), 500


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)
