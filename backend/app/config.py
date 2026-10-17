import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parents[1]
_raw_db = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "price_tracker.db")))
DATABASE_PATH = _raw_db if _raw_db.is_absolute() else (BASE_DIR / _raw_db).resolve()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001").strip()
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
PRICE_CHECK_INTERVAL_MINUTES = max(15, int(os.getenv("PRICE_CHECK_INTERVAL_MINUTES", "60")))
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
