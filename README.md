# Price Tracker Agent

Full-stack demo using FastAPI, SQLite, React/Vite, Anthropic Claude, and Slack Incoming Webhooks.

## Features
- Add product URLs and target prices.
- Best-effort price extraction from accessible pages (JSON-LD and common price metadata).
- SQLite price history, manual checks, scheduled checks, and Slack alerts.
- Claude summaries based on recorded price history.
- React dashboard with history chart.
- Demo mode for testing without live retailer access.

## Limitations
Amazon/Flipkart API keys are not used. Retail websites may block automated access, require JavaScript, or change markup. Extraction is not guaranteed; failed or ambiguous prices are reported instead of guessed. Respect site terms and access restrictions. Claude and Slack are optional integrations.

## Setup (macOS)
### Backend
```bash
cd price-tracker-agent/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env to configure optional Claude and Slack credentials
uvicorn app.main:app --reload --port 8001
```
API docs: http://127.0.0.1:8001/docs

### Frontend (another Terminal tab)
```bash
cd price-tracker-agent/frontend
npm install
cp .env.example .env
npm run dev
```
Open the Vite URL, usually http://localhost:5173.

## Demo mode
Set `DEMO_MODE=true` in `backend/.env`, restart the backend, then click “Load demo product” in the dashboard. Demo mode uses a sample price and does not claim to represent a live retailer price.

## Keys
- Claude: `ANTHROPIC_API_KEY` from https://console.anthropic.com/
- Slack: Incoming Webhook URL from https://api.slack.com/apps
Keep both private and never commit `.env`.
