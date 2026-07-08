# NewsIQ — Fake News Detector
### Powered by IBM watsonx.ai · Granite Model

👉 **Live Demo:** [https:////NewsIQ.ai/](https://newsiq-production.up.railway.app/)
A production-ready web application that classifies news headlines and articles as **REAL**, **SUSPICIOUS**, or **FAKE** using IBM watsonx.ai Granite models, with keyword highlighting, confidence scores, credibility checklists, history, and compare mode.

---

## 📁 Project Structure

```
fakenews_detector/
├── app.py                  # Flask backend + watsonx.ai integration
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── data/
│   └── history.db          # SQLite history (auto-created)
├── static/
│   ├── css/style.css       # Premium dark theme
│   └── js/main.js          # Frontend logic
└── templates/
    └── index.html          # Single-page UI
```

---

## ⚡ Quick Start (Local)

### 1. Clone / navigate to the project folder
```bash
cd fakenews_detector
```

### 2. Create and activate a virtual environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure credentials
```bash
cp .env.example .env
```
Edit `.env` and fill in:
| Variable | Where to find it |
|---|---|
| `IBM_API_KEY` | IBM Cloud → Manage → Access (IAM) → API keys |
| `IBM_PROJECT_ID` | IBM watsonx.ai → Project → Manage → General |
| `IBM_WATSONX_URL` | watsonx.ai region endpoint (default: `https://us-south.ml.cloud.ibm.com`) |

### 5. Run the app
```bash
python app.py
```
Open **http://localhost:5000** in your browser.

---

## 🔑 Getting IBM Credentials

1. **Create an IBM Cloud account** at [cloud.ibm.com](https://cloud.ibm.com)
2. **Provision Watson Machine Learning** service (Lite plan is free)
3. **Create a watsonx.ai project** at [dataplatform.cloud.ibm.com](https://dataplatform.cloud.ibm.com)
4. **Generate an API key**: IBM Cloud → Manage → Access (IAM) → API keys → Create
5. **Copy your Project ID**: watsonx.ai → your project → Manage tab → General → Project ID

---

## 🌐 Deploy to IBM Cloud (Cloud Foundry)

### Prerequisites
- IBM Cloud CLI: `ibmcloud login`
- CF plugin: `ibmcloud cf install-plugin`

### 1. Create `manifest.yml`
```yaml
applications:
  - name: newsiq-fakenews
    memory: 256M
    instances: 1
    buildpacks:
      - python_buildpack
    command: gunicorn app:app --bind 0.0.0.0:$PORT
    env:
      IBM_API_KEY: "YOUR_KEY_HERE"
      IBM_PROJECT_ID: "YOUR_PROJECT_ID"
      IBM_WATSONX_URL: "https://us-south.ml.cloud.ibm.com"
      FLASK_SECRET_KEY: "YOUR_SECRET_KEY"
```

### 2. Add gunicorn to requirements
```
gunicorn==22.0.0
```

### 3. Deploy
```bash
ibmcloud login --sso
ibmcloud target --cf
ibmcloud cf push
```

---

## 🐳 Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "2"]
```

```bash
docker build -t newsiq .
docker run -p 5000:5000 --env-file .env newsiq
```

---

## 🎛️ Customising Agent Behaviour

Open `app.py` and edit the **AGENT INSTRUCTIONS** block at the top and the `SYSTEM_CONTEXT` string to change:

| Setting | Where |
|---|---|
| Tone & style | `SYSTEM_CONTEXT` string |
| Classification labels | `build_analysis_prompt()` |
| Red-flag keywords | `KNOWN_RED_FLAGS` list |
| Max history stored | `MAX_HISTORY` in `.env` |
| Model used | `model_id` in `call_granite()` |
| Max input length | truncation in `/api/analyse` route |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serve the UI |
| `POST` | `/api/analyse` | Analyse text/URL |
| `POST` | `/api/compare` | Compare two texts |
| `GET` | `/api/history` | Get analysis history |
| `DELETE` | `/api/history` | Clear all history |
| `DELETE` | `/api/history/<id>` | Delete one record |
| `POST` | `/api/fetch-url` | Extract article text from URL |
| `GET` | `/api/status` | Check API configuration |

### `/api/analyse` request body
```json
{
  "text": "Breaking: Miracle drug cures all diseases!",
  "url": "https://optional-article-url.com",
  "language": "auto"
}
```

### `/api/analyse` response
```json
{
  "label": "FAKE",
  "confidence": 91,
  "language": "en",
  "summary": "This headline uses classic misinformation patterns.",
  "explanation": ["Exaggerated miracle claims", "No named source", "Clickbait structure"],
  "signals": ["Miracle", "cures all"],
  "checklist": {
    "credible_source": false,
    "verifiable_claims": false,
    "emotional_language": true,
    "author_named": false,
    "consistent_facts": null
  },
  "simple_explanation": "This looks like fake news because...",
  "highlighted_text": "Breaking: <mark class='highlight'>Miracle</mark> drug..."
}
```

---

## ✅ Features Checklist

- [x] Classify text as REAL / SUSPICIOUS / FAKE
- [x] Confidence score with animated progress bar
- [x] Explanation in bullet points
- [x] Plain-language simple explanation
- [x] Keyword / phrase highlighting
- [x] Credibility checklist (5 factors)
- [x] Analysis history with SQLite (configurable max)
- [x] Compare two headlines side-by-side
- [x] URL fetching and article extraction
- [x] English + Hindi language support
- [x] Dark mode premium UI (Bootstrap 5)
- [x] Mobile responsive
- [x] Fact-check resource links
- [x] Customisable agent instructions

---

## ⚠️ Disclaimer

This tool assists human judgement — it is not infallible. AI analysis has inherent limits. Always verify important information with multiple trusted sources and professional fact-checkers.
