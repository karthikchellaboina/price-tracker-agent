import sqlite3
from contextlib import contextmanager
from .config import DATABASE_PATH

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL,
            target_price REAL, current_price REAL, currency TEXT NOT NULL DEFAULT 'INR',
            last_checked TEXT, last_error TEXT, created_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
            price REAL NOT NULL, checked_at TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'page',
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE)""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_history_product_time ON price_history(product_id, checked_at)")
