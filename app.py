# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     FAKE NEWS DETECTOR  –  app.py                          ║
║         Powered by IBM watsonx.ai  •  Llama 3.3 70B Instruct               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  AGENT INSTRUCTIONS  (edit this block to customise behaviour)               ║
║──────────────────────────────────────────────────────────────────────────── ║
║  TONE          : Neutral, factual, careful. Never alarmist or dismissive.  ║
║  LANGUAGE STYLE: Plain language, short sentences. Explain jargon simply.   ║
║  CLASSIFICATION: Three labels only — REAL, SUSPICIOUS, FAKE                ║
║                  • REAL       – credible language, verifiable claims        ║
║                  • SUSPICIOUS – exaggerated, unverified, emotional bait     ║
║                  • FAKE       – clear misinformation signals, fabricated    ║
║  CONFIDENCE    : Express as a percentage (0–100). Be honest about limits.  ║
║  EXPLANATION   : 2–4 concise bullet points explaining the decision.        ║
║  SIGNALS       : Return up to 6 suspicious keywords / phrases from text.   ║
║  CHECKLIST     : Always output a 5-point credibility checklist result.     ║
║  LANGUAGE      : Detect input language. Reply fully in that language.      ║
║                  Supported: English, Hindi.                                 ║
║  SAFETY RULES  : • Never accuse real people directly.                      ║
║                  • Always note that AI analysis has limits.                 ║
║                  • Do not make political endorsements.                      ║
║                  • When uncertain, lean toward SUSPICIOUS, not FAKE.       ║
║  COMPARE MODE  : When comparing two texts, explain differences clearly.    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import sqlite3
import re
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template, g
from flask_cors import CORS
from dotenv import load_dotenv
import requests as http_requests
from bs4 import BeautifulSoup
import bleach

from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.foundation_models.schema import TextGenParameters

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()

IBM_API_KEY      = os.getenv("IBM_API_KEY", "")
IBM_PROJECT_ID   = os.getenv("IBM_PROJECT_ID", "")
IBM_WATSONX_URL  = os.getenv("IBM_WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
MAX_HISTORY      = int(os.getenv("MAX_HISTORY", "50"))

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
CORS(app)

# ── Database setup ────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "data" / "history.db"
DB_PATH.parent.mkdir(exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    input_text  TEXT    NOT NULL,
    input_url   TEXT,
    label       TEXT    NOT NULL,
    confidence  INTEGER NOT NULL,
    explanation TEXT    NOT NULL,
    signals     TEXT,
    checklist   TEXT,
    language    TEXT    DEFAULT 'en'
);
"""

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(str(DB_PATH))
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        conn = sqlite3.connect(str(DB_PATH))
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

init_db()

# ── watsonx.ai SDK client (lazy-initialised) ─────────────────────────────────
_wx_model: ModelInference | None = None

def get_wx_model() -> ModelInference:
    """Return a cached ModelInference instance, creating it on first call."""
    global _wx_model
    if _wx_model is None:
        creds = Credentials(
            url=IBM_WATSONX_URL,
            api_key=IBM_API_KEY,
        )
        _wx_model = ModelInference(
            model_id="meta-llama/llama-3-3-70b-instruct",
            credentials=creds,
            project_id=IBM_PROJECT_ID,
        )
    return _wx_model


def call_granite(prompt: str, max_tokens: int = 800) -> str:
    """Call the IBM watsonx.ai Granite model via the official SDK."""
    model  = get_wx_model()
    params = TextGenParameters(
        decoding_method="greedy",
        max_new_tokens=max_tokens,
        min_new_tokens=20,
        stop_sequences=["###END###"],
        repetition_penalty=1.1,
    )
    response = model.generate_text(prompt=prompt, params=params)
    # SDK returns the generated string directly
    if isinstance(response, str):
        return response.strip()
    # Fallback: dict shape from older SDK versions
    return response["results"][0]["generated_text"].strip()


# ── Prompt builder ────────────────────────────────────────────────────────────
SYSTEM_CONTEXT = """You are NewsIQ, a careful and neutral AI misinformation detector.
Your job is to analyse news headlines or short articles and classify them.
Be factual, unbiased, and careful. Never accuse real people. When uncertain, prefer SUSPICIOUS over FAKE.
Always note that AI analysis has limits.
"""

def build_analysis_prompt(text: str, language_hint: str = "auto") -> str:
    lang_instruction = (
        "Detect the language of the input and reply fully in that language (English or Hindi)."
        if language_hint == "auto"
        else f"Reply fully in {language_hint}."
    )

    return f"""{SYSTEM_CONTEXT}
{lang_instruction}

Analyse the following news text and respond ONLY with a valid JSON object — no prose, no markdown fences.

News text:
\"\"\"{text}\"\"\"

Return exactly this JSON structure:
{{
  "label": "<REAL|SUSPICIOUS|FAKE>",
  "confidence": <integer 0-100>,
  "language": "<en|hi>",
  "summary": "<one sentence verdict in detected language>",
  "explanation": [
    "<bullet point 1>",
    "<bullet point 2>",
    "<bullet point 3>"
  ],
  "signals": ["<suspicious word or phrase>", ...],
  "checklist": {{
    "credible_source": <true|false|null>,
    "verifiable_claims": <true|false|null>,
    "emotional_language": <true|false>,
    "author_named": <true|false|null>,
    "consistent_facts": <true|false|null>
  }},
  "simple_explanation": "<plain one-paragraph explanation for non-experts in detected language>"
}}
###END###"""


def build_compare_prompt(text_a: str, text_b: str) -> str:
    return f"""{SYSTEM_CONTEXT}
Compare these two news texts and reply ONLY with valid JSON — no prose, no markdown.

Text A:
\"\"\"{text_a}\"\"\"

Text B:
\"\"\"{text_b}\"\"\"

Return exactly this JSON structure:
{{
  "text_a": {{
    "label": "<REAL|SUSPICIOUS|FAKE>",
    "confidence": <0-100>,
    "summary": "<one sentence>"
  }},
  "text_b": {{
    "label": "<REAL|SUSPICIOUS|FAKE>",
    "confidence": <0-100>,
    "summary": "<one sentence>"
  }},
  "comparison": "<2-3 sentences comparing credibility of A vs B>",
  "more_credible": "<A|B|EQUAL>"
}}
###END###"""


# ── URL scraper ───────────────────────────────────────────────────────────────
def fetch_article_text(url: str) -> str:
    """Fetch and extract main text from a URL (best-effort)."""
    try:
        resp = http_requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (NewsIQ Bot)"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Remove script / style / nav / footer noise
        for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
            tag.decompose()
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(" ", strip=True) for p in paragraphs[:30])
        return text[:4000]  # cap for prompt length
    except Exception as exc:
        return f"[Could not fetch URL: {exc}]"


# ── JSON parse helper ─────────────────────────────────────────────────────────
def safe_parse_json(raw: str) -> dict:
    """Try to parse JSON from model output; fall back gracefully."""
    # strip markdown fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract a JSON block
        match = re.search(r"\{[\s\S]+\}", raw)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    # Return a fallback structure
    return {
        "label": "SUSPICIOUS",
        "confidence": 50,
        "language": "en",
        "summary": "Analysis could not be fully parsed.",
        "explanation": ["The model returned an unexpected format.", "Please try again."],
        "signals": [],
        "checklist": {
            "credible_source": None,
            "verifiable_claims": None,
            "emotional_language": False,
            "author_named": None,
            "consistent_facts": None,
        },
        "simple_explanation": raw[:400],
    }


# ── Keyword highlighter ───────────────────────────────────────────────────────
KNOWN_RED_FLAGS = [
    r"\bbreaking\b", r"\bshocking\b", r"\bexclusive\b", r"\bthey don'?t want you to know\b",
    r"\bconspiracy\b", r"\bplandemic\b", r"\bdeep state\b", r"\bsecret\b",
    r"\bunbelievable\b", r"\bmiracle\b", r"\bcure\b", r"\bhoax\b",
    r"\bbig pharma\b", r"\bfake media\b", r"\bsuppressed\b", r"\bwake up\b",
    r"\bglobalist\b", r"\balert\b", r"\burgent\b", r"\bexposed\b",
    r"\bसाजिश\b", r"\bझूठ\b", r"\bफर्जी\b", r"\bवायरल\b", r"\bसच्चाई\b",
]

def highlight_text(text: str, signals: list) -> str:
    """Return HTML-escaped text with suspicious words wrapped in <mark>."""
    safe = bleach.clean(text)
    patterns = list(KNOWN_RED_FLAGS)
    for sig in signals:
        if sig:
            patterns.append(re.escape(sig.strip()))
    combined = "|".join(patterns)
    if not combined:
        return safe
    highlighted = re.sub(
        combined,
        lambda m: f'<mark class="highlight">{m.group()}</mark>',
        safe,
        flags=re.IGNORECASE,
    )
    return highlighted


# ── DB helpers ────────────────────────────────────────────────────────────────
def save_analysis(data: dict):
    db = get_db()
    db.execute(
        """INSERT INTO analyses
           (created_at, input_text, input_url, label, confidence,
            explanation, signals, checklist, language)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            datetime.utcnow().isoformat(timespec="seconds"),
            data.get("input_text", "")[:1000],
            data.get("input_url"),
            data.get("label", "SUSPICIOUS"),
            data.get("confidence", 50),
            json.dumps(data.get("explanation", []), ensure_ascii=False),
            json.dumps(data.get("signals", []), ensure_ascii=False),
            json.dumps(data.get("checklist", {}), ensure_ascii=False),
            data.get("language", "en"),
        ),
    )
    db.commit()
    # Trim to MAX_HISTORY
    db.execute(
        f"""DELETE FROM analyses WHERE id NOT IN
            (SELECT id FROM analyses ORDER BY id DESC LIMIT {MAX_HISTORY})"""
    )
    db.commit()


def get_history(limit: int = 20) -> list:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM analyses ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["explanation"] = json.loads(item["explanation"] or "[]")
        item["signals"]     = json.loads(item["signals"] or "[]")
        item["checklist"]   = json.loads(item["checklist"] or "{}")
        result.append(item)
    return result


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyse", methods=["POST"])
def analyse():
    """Main analysis endpoint."""
    body = request.get_json(force=True) or {}
    text     = bleach.clean(str(body.get("text", "")).strip())
    url      = bleach.clean(str(body.get("url", "")).strip())
    language = body.get("language", "auto")

    # If URL provided and text is short/empty, try to fetch article
    article_text = text
    if url and (not text or len(text) < 30):
        article_text = fetch_article_text(url)

    if not article_text or len(article_text) < 5:
        return jsonify({"error": "Please provide text or a valid article URL."}), 400

    # Truncate very long inputs
    article_text = article_text[:3000]

    try:
        prompt   = build_analysis_prompt(article_text, language)
        raw      = call_granite(prompt, max_tokens=800)
        parsed   = safe_parse_json(raw)
    except Exception as exc:
        app.logger.error(f"Granite call failed: {exc}")
        return jsonify({"error": f"AI model error: {str(exc)}"}), 502

    # Add highlighted HTML
    parsed["highlighted_text"] = highlight_text(
        article_text[:600], parsed.get("signals", [])
    )
    parsed["input_text"] = article_text[:600]
    parsed["input_url"]  = url or None

    # Persist
    save_analysis(parsed)

    return jsonify(parsed)


@app.route("/api/compare", methods=["POST"])
def compare():
    """Compare two news texts."""
    body   = request.get_json(force=True) or {}
    text_a = bleach.clean(str(body.get("text_a", "")).strip())[:2000]
    text_b = bleach.clean(str(body.get("text_b", "")).strip())[:2000]

    if not text_a or not text_b:
        return jsonify({"error": "Both text_a and text_b are required."}), 400

    try:
        prompt  = build_compare_prompt(text_a, text_b)
        raw     = call_granite(prompt, max_tokens=500)
        parsed  = safe_parse_json(raw)
    except Exception as exc:
        app.logger.error(f"Compare call failed: {exc}")
        return jsonify({"error": f"AI model error: {str(exc)}"}), 502

    return jsonify(parsed)


@app.route("/api/history", methods=["GET"])
def history():
    limit = min(int(request.args.get("limit", 20)), MAX_HISTORY)
    return jsonify(get_history(limit))


@app.route("/api/history/<int:item_id>", methods=["DELETE"])
def delete_history_item(item_id):
    db = get_db()
    db.execute("DELETE FROM analyses WHERE id = ?", (item_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/history", methods=["DELETE"])
def clear_history():
    db = get_db()
    db.execute("DELETE FROM analyses")
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/fetch-url", methods=["POST"])
def fetch_url():
    """Preview the text extracted from a URL."""
    body = request.get_json(force=True) or {}
    url  = bleach.clean(str(body.get("url", "")).strip())
    if not url:
        return jsonify({"error": "URL required"}), 400
    text = fetch_article_text(url)
    return jsonify({"text": text[:1500], "length": len(text)})


@app.route("/api/status", methods=["GET"])
def status():
    configured = bool(IBM_API_KEY and IBM_PROJECT_ID)
    return jsonify({
        "status": "ok",
        "watsonx_configured": configured,
        "model": "meta-llama/llama-3-3-70b-instruct",
    })


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug)
