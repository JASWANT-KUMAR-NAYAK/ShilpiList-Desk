import json
import sqlite3
from pathlib import Path

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL DEFAULT '',
    craft TEXT NOT NULL,
    material TEXT NOT NULL,
    dimensions TEXT NOT NULL,
    maker TEXT NOT NULL DEFAULT '',
    village TEXT NOT NULL DEFAULT '',
    gi TEXT NOT NULL DEFAULT '',
    image_paths TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    tone TEXT NOT NULL,
    content_json TEXT NOT NULL,
    model TEXT,
    latency_ms INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL REFERENCES listings(id),
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    would_pay INTEGER,
    edited_text TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def db_path() -> Path:
    p = Path(settings.data_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p / "shilpilist.sqlite3"



def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # Add product_name to existing databases if missing
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(products)").fetchall()
    }
    if "product_name" not in columns:
        conn.execute(
            "ALTER TABLE products ADD COLUMN product_name TEXT NOT NULL DEFAULT ''"
        )
        conn.commit()

    return conn




def add_product(facts: dict, image_paths: list[str]) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO products "
            "(product_name, craft, material, dimensions, maker, village, gi, image_paths) "
            "VALUES (:product_name, :craft, :material, :dimensions, :maker, :village, :gi, :image_paths)",
            {**facts, "image_paths": json.dumps(image_paths)},
        )
        return cur.lastrowid



def get_product(product_id: int):
    with connect() as c:
        return c.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()


def add_listing(product_id: int, tone: str, content: dict, meta: dict) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO listings (product_id, tone, content_json, model, latency_ms, "
            "prompt_tokens, completion_tokens) VALUES (?,?,?,?,?,?,?)",
            (
                product_id,
                tone,
                json.dumps(content, ensure_ascii=False),
                meta.get("model"),
                meta.get("latency_ms"),
                meta.get("prompt_tokens"),
                meta.get("completion_tokens"),
            ),
        )
        return cur.lastrowid


def _listing_dict(row) -> dict:
    d = dict(row)
    d["content"] = json.loads(d.pop("content_json"))
    return d


def get_listing(listing_id: int):
    with connect() as c:
        row = c.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    return _listing_dict(row) if row else None


def list_listings(limit: int = 50) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM listings ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_listing_dict(r) for r in rows]


def purge_old_images(days: int) -> int:
    """Delete uploaded photos older than `days` and mark those products as purged.

    A purged product keeps its listings (text) but has image_paths '[]', so it cannot be
    regenerated until new photos are uploaded. Returns the number of files deleted.
    """
    deleted = 0
    with connect() as c:
        rows = c.execute(
            "SELECT id, image_paths FROM products "
            "WHERE image_paths != '[]' AND created_at < datetime('now', ?)",
            (f"-{int(days)} days",),
        ).fetchall()
        for row in rows:
            for p in json.loads(row["image_paths"]):
                try:
                    Path(p).unlink()
                    deleted += 1
                except FileNotFoundError:
                    pass
            c.execute("UPDATE products SET image_paths='[]' WHERE id=?", (row["id"],))
    return deleted


def add_feedback(listing_id: int, rating, would_pay, edited_text) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO feedback (listing_id, rating, would_pay, edited_text) VALUES (?,?,?,?)",
            (listing_id, rating, None if would_pay is None else int(would_pay), edited_text),
        )
        return cur.lastrowid
