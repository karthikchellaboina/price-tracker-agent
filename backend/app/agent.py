
from .database import get_db
from .pricing import extract_price, utc_now
from .notifications import price_alert, send_slack_message
from .config import DEMO_MODE


def get_product(product_id):
    """Return one product from the database."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        return dict(row) if row else None


def add_product(url, target_price=None, title=None):
    """Add a product and notify Slack after saving it."""
    details = (
        {
            "title": title or "Demo Wireless Headphones",
            "price": 999.0,
            "currency": "INR",
            "source": "demo",
        }
        if DEMO_MODE
        else extract_price(url)
    )

    now = utc_now()

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO products
                (title, url, target_price, current_price, currency,
                 last_checked, last_error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title or details["title"],
                url,
                target_price,
                details["price"],
                details["currency"],
                now,
                None,
                now,
            ),
        )

        product_id = cursor.lastrowid

        db.execute(
            """
            INSERT INTO price_history
                (product_id, price, checked_at, source)
            VALUES (?, ?, ?, ?)
            """,
            (product_id, details["price"], now, details["source"]),
        )

    product = get_product(product_id)

    # Slack failure must not undo a successfully saved product.
    try:
        current_price = product["current_price"]
        price_text = (
            f"₹{float(current_price):,.2f}"
            if current_price is not None
            else "Unavailable"
        )
        target = product["target_price"]
        target_text = (
            f"₹{float(target):,.2f}" if target is not None else "Not set"
        )

        message = (
            "🆕 Product added to Price Tracker!\n"
            f"📦 Product: {product['title']}\n"
            f"💰 Current price: {price_text}\n"
            f"🎯 Target price: {target_text}\n"
            f"🔗 Product link: {product['url']}"
        )
        send_slack_message(message)
    except Exception as exc:
        print(f"Product-added Slack notification failed: {exc}")

    return product


def check_product(product_id):
    """Check price, save history, and notify Slack when appropriate."""
    product = get_product(product_id)

    if not product:
        raise LookupError("Product not found.")

    now = utc_now()

    try:
        details = (
            {
                "title": product["title"],
                "price": product["current_price"] or 999.0,
                "currency": product["currency"],
                "source": "demo",
            }
            if DEMO_MODE
            else extract_price(product["url"])
        )

        new_price = float(details["price"])
        old_price = product["current_price"]
        target_price = product["target_price"]

        with get_db() as db:
            db.execute(
                """
                UPDATE products
                SET current_price = ?, currency = ?,
                    last_checked = ?, last_error = NULL
                WHERE id = ?
                """,
                (new_price, details["currency"], now, product_id),
            )

            db.execute(
                """
                INSERT INTO price_history
                    (product_id, price, checked_at, source)
                VALUES (?, ?, ?, ?)
                """,
                (product_id, new_price, now, details["source"]),
            )

        # Only alert on the transition from above target to at/below target.
        # The initial saved price is included in history.
        target_reached = (
            target_price is not None
            and new_price <= float(target_price)
            and (
                old_price is None
                or float(old_price) > float(target_price)
            )
        )

        messages = []

        # Keep the existing price-drop notification behavior.
        if old_price is not None and new_price < float(old_price):
            messages.append(
                f"📉 Price drop for {product['title']}\n"
                f"Previous price: ₹{float(old_price):,.2f}\n"
                f"Current price: ₹{new_price:,.2f}"
            )

        if target_reached:
            messages.append(
                f"🎯 Target price reached for {product['title']}\n"
                f"Current price: ₹{new_price:,.2f}\n"
                f"Target price: ₹{float(target_price):,.2f}\n"
                f"🔗 Product link: {product['url']}"
            )

        notification = {
            "sent": False,
            "reason": "No alert condition met.",
        }

        if messages:
            try:
                notification = send_slack_message("\n\n".join(messages))
            except Exception as exc:
                notification = {
                    "sent": False,
                    "reason": f"Slack notification failed: {exc}",
                }

        return {
            "product": get_product(product_id),
            "previous_price": old_price,
            "new_price": new_price,
            "notification": notification,
        }

    except Exception as exc:
        with get_db() as db:
            db.execute(
                """
                UPDATE products
                SET last_checked = ?, last_error = ?
                WHERE id = ?
                """,
                (now, str(exc)[:1000], product_id),
            )
        raise


def list_products():
    """Return all tracked products."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM products ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def delete_product(product_id):
    """Delete a product and its associated price history."""
    with get_db() as db:
        db.execute(
            "DELETE FROM price_history WHERE product_id = ?",
            (product_id,),
        )
        cursor = db.execute(
            "DELETE FROM products WHERE id = ?",
            (product_id,),
        )
        return cursor.rowcount > 0


def update_target(product_id, target_price):
    """Update the target price for a tracked product."""
    with get_db() as db:
        cursor = db.execute(
            "UPDATE products SET target_price = ? WHERE id = ?",
            (target_price, product_id),
        )
        if cursor.rowcount == 0:
            return None

    return get_product(product_id)


def history(product_id):
    """Return saved price history in chronological order."""
    with get_db() as db:
        rows = db.execute(
            """
            SELECT price, checked_at, source
            FROM price_history
            WHERE product_id = ?
            ORDER BY checked_at ASC
            """,
            (product_id,),
        ).fetchall()
        return [dict(row) for row in rows]
