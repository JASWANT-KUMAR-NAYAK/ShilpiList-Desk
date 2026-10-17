"""Consistent SQLite backup plus photo retention. Run nightly (cron, or a Render cron job).

    python -m scripts.backup --keep 7 --purge-days 30
"""
import argparse
import sqlite3
import time
from contextlib import closing

from app import db


def backup(keep: int) -> str:
    src = db.db_path()
    dest_dir = src.parent / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"shilpilist-{time.strftime('%Y%m%d-%H%M%S')}.sqlite3"
    # The sqlite backup API copies a consistent snapshot even while the app is writing.
    with closing(sqlite3.connect(src)) as s, closing(sqlite3.connect(dest)) as d:
        s.backup(d)
    for old in sorted(dest_dir.glob("shilpilist-*.sqlite3"))[:-keep]:
        old.unlink()
    return str(dest)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=7, help="backups to keep")
    ap.add_argument("--purge-days", type=int, default=30, help="delete photos older than this")
    args = ap.parse_args()
    print("backup:", backup(args.keep))
    print("photos deleted:", db.purge_old_images(args.purge_days))


if __name__ == "__main__":
    main()
