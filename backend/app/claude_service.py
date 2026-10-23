
from anthropic import Anthropic
from .config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from .agent import get_product, history
from datetime import datetime


def _parse_timestamp(value):
    """Convert a history timestamp to a datetime when possible."""
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def summarize_product(product_id):
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "Claude is not configured. Add ANTHROPIC_API_KEY to backend/.env."
        )

    product = get_product(product_id)
    if not product:
        raise LookupError("Product not found.")

    records = history(product_id)
    if not records:
        raise RuntimeError("No price history is available yet.")

    # Normalize records and identify records with usable prices.
    valid_records = []
    for record in records:
        try:
            price = float(record["price"])
        except (KeyError, TypeError, ValueError):
            continue

        if price <= 0:
            continue

        valid_records.append({
            "price": price,
            "checked_at": record.get("checked_at"),
            "source": record.get("source", "unknown"),
        })

    if not valid_records:
        raise RuntimeError("No valid price records are available.")

    # Sort chronologically where timestamps are available.
    valid_records.sort(
        key=lambda r: _parse_timestamp(r["checked_at"])
        or datetime.min
    )

    prices = [r["price"] for r in valid_records]
    first_record = valid_records[0]
    latest_record = valid_records[-1]

    first_time = _parse_timestamp(first_record["checked_at"])
    latest_time = _parse_timestamp(latest_record["checked_at"])

    # Summarize all available records, not just the latest 30.
    price_change = prices[-1] - prices[0]
    change_percent = (
        (price_change / prices[0]) * 100 if prices[0] else 0
    )

    timestamps = [
        _parse_timestamp(r["checked_at"])
        for r in valid_records
    ]
    timestamps = [t for t in timestamps if t is not None]

    if timestamps:
        earliest_time = min(timestamps)
        latest_time_available = max(timestamps)
        duration = latest_time_available - earliest_time
        duration_text = str(duration)
    else:
        duration_text = "Unknown because timestamps are unavailable"

    # Include recent detailed records to show the latest movements.
    recent_records = valid_records[-100:]

    # Include a compact chronological sample from the entire history.
    # This helps retain older trends without sending every raw row.
    sample_limit = 100
    if len(valid_records) <= sample_limit:
        history_sample = valid_records
    else:
        indexes = sorted({
            round(i * (len(valid_records) - 1) / (sample_limit - 1))
            for i in range(sample_limit)
        })
        history_sample = [valid_records[i] for i in indexes]

    prompt = f"""
Analyze the available price history for this product.

Use only the supplied data. Do not invent prices, dates, promotions,
seasonal patterns, or forecasts. Clearly distinguish observed facts
from possible interpretations.

PRODUCT
Title: {product.get('title')}
URL: {product.get('url')}
Target price: {product.get('target_price')}
Total valid price records: {len(valid_records)}
Earliest recorded price: {first_record['price']}
Earliest record timestamp: {first_record['checked_at']}
Latest recorded price: {latest_record['price']}
Latest record timestamp: {latest_record['checked_at']}
Minimum recorded price: {min(prices)}
Maximum recorded price: {max(prices)}
Change from first to latest price: {price_change:.2f}
Percentage change from first to latest price: {change_percent:.2f}%
Available observation period: {duration_text}

CHRONOLOGICAL SAMPLE ACROSS THE FULL HISTORY
{history_sample}

LATEST DETAILED RECORDS
{recent_records}

INSTRUCTIONS
1. State the actual number of records and observation period.
2. Explain the overall price movement from the first record to the latest.
3. Mention the minimum and maximum recorded prices.
4. Compare the latest price with the target price when the target is available.
5. Use recent records to describe recent movement.
6. Do not claim seasonal or promotional patterns unless the data supports them.
7. If timestamps are missing or inconsistent, disclose that limitation.
8. Keep the answer concise, clear, and useful.
"""

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}],
    )

    return "\n".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    )
