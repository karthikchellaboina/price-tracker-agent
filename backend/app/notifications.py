
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_FILE)


def send_slack_message(message: str) -> dict:
    """Send a Slack message and return its status."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()

    if not webhook_url:
        print("Slack notification skipped: webhook is not configured.")
        return {
            "sent": False,
            "reason": "Slack webhook is not configured.",
        }

    if not webhook_url.startswith("https://hooks.slack.com/"):
        return {"sent": False, "reason": "Invalid Slack webhook URL."}

    try:
        response = requests.post(
            webhook_url,
            json={"text": message},
            timeout=15,
        )
        response.raise_for_status()

        if response.text.strip() != "ok":
            return {"sent": False, "reason": "Unexpected Slack response."}

        print("Slack notification sent successfully!")
        return {"sent": True, "reason": "Notification sent."}

    except requests.RequestException as exc:
        print(f"Slack notification failed: {exc}")
        return {"sent": False, "reason": str(exc)}


def send_slack_notification(message: str) -> bool:
    """Compatibility wrapper for existing notification tests."""
    return send_slack_message(message)["sent"]


def price_alert(
    product_name: str,
    product_url: str,
    old_price: float | None,
    current_price: float,
    target_price: float | None,
) -> str | None:
    """Create an alert when the price drops or reaches its target."""
    messages = []

    if old_price is not None and current_price < float(old_price):
        messages.append(
            f"Price drop for {product_name}\n"
            f"Previous price: ₹{float(old_price):,.2f}\n"
            f"Current price: ₹{current_price:,.2f}"
        )

    if target_price is not None and current_price <= float(target_price):
        messages.append(
            f"Target price reached for {product_name}\n"
            f"Current price: ₹{current_price:,.2f}\n"
            f"Target price: ₹{float(target_price):,.2f}"
        )

    if not messages:
        return None

    return "\n\n".join(messages) + f"\nProduct link: {product_url}"
