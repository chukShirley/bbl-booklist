#!/usr/bin/env python3
"""Export the SQLite catalog into the compact JSON consumed by the Book Scout PWA."""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "app" / "src" / "main" / "assets" / "book-scout.db"
OUTPUT = ROOT / "web" / "catalog.json"


def main():
    db = sqlite3.connect(DATABASE)
    rows = db.execute(
        "SELECT id,title,normalized_title,author,normalized_author "
        "FROM books ORDER BY title COLLATE NOCASE,author COLLATE NOCASE"
    ).fetchall()
    isbns = dict(db.execute(
        "SELECT book_id,value FROM book_identifiers WHERE scheme='ISBN13' ORDER BY book_id"
    ))
    owned_ids = {row[0] for row in db.execute("SELECT book_id FROM inventory")}
    memberships = {}
    for book_id, name in db.execute(
        "SELECT bl.book_id,l.name FROM book_lists bl JOIN lists l ON l.id=bl.list_id ORDER BY l.name"
    ):
        memberships.setdefault(book_id, []).append(name)

    books = []
    for book_id, title, normalized_title, author, normalized_author in rows:
        isbn = isbns.get(book_id, "")
        list_names = memberships.get(book_id, [])
        stable_key = f"isbn:{isbn}" if isbn else f"book:{normalized_title}|{normalized_author}"
        books.append({
            "k": stable_key,
            "t": title,
            "a": author,
            "i": isbn or "",
            "l": list_names,
            "o": book_id in owned_ids,
            "s": " ".join([normalized_title, normalized_author, " ".join(list_names).lower(), isbn or ""]),
        })

    payload = {"version": 1, "count": len(books), "books": books}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(books)} books to {OUTPUT} ({OUTPUT.stat().st_size / 1024 / 1024:.1f} MiB)")
    db.close()


if __name__ == "__main__":
    main()
