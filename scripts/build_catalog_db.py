#!/usr/bin/env python3
"""Build the offline Book Scout SQLite catalog from the source CSV files."""

import csv, json, re, sqlite3, unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "app" / "src" / "main" / "assets" / "book-scout.db"
REPORT = DATA / "catalog-import-report.json"
INVENTORY = DATA / "raw" / "inventory" / "librarything_BeautifulBooksLib_202608261531.json"
SOURCES = [
    ("Biblioguides", DATA / "biblioguides-books.csv", "author", "source_url", "book_id"),
    ("John Senior - The Thousand Good Books", DATA / "john-senior-thousand-good-books.csv", "author", "", ""),
    ("Plumfield Living Library", DATA / "plumfield-living-library-books.csv", "author", "source_urls", "work_id"),
    ("Read-Aloud Revival", DATA / "read-aloud-revival-books.csv", "author", "source_url", ""),
    ("Reshelving Alexandria", DATA / "reshelving-alexandria-books.csv", "author_illustrator", "source_url", "notion_page_id"),
]

def normalize_text(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

def normalize_isbn(value):
    value = re.sub(r"[^0-9Xx]", "", value or "").upper()
    return value if len(value) in (10, 13) else ""

def isbn13(value):
    value = normalize_isbn(value)
    if len(value) == 13: return value
    if len(value) != 10: return ""
    stem = "978" + value[:9]
    check = (10 - sum((1 if i % 2 == 0 else 3) * int(n) for i, n in enumerate(stem)) % 10) % 10
    return stem + str(check)

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE lists(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE);
CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT NOT NULL,normalized_title TEXT NOT NULL,author TEXT NOT NULL DEFAULT '',normalized_author TEXT NOT NULL DEFAULT '');
CREATE TABLE book_lists(book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,PRIMARY KEY(book_id,list_id));
CREATE TABLE book_identifiers(book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,scheme TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(scheme,value));
CREATE TABLE source_records(id INTEGER PRIMARY KEY,book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,source_key TEXT,source_url TEXT,raw_json TEXT NOT NULL);
CREATE TABLE inventory(book_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity>=0),isbn TEXT,notes TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE inventory_records(id INTEGER PRIMARY KEY,book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,librarything_book_id TEXT NOT NULL UNIQUE,barcode TEXT,raw_json TEXT NOT NULL);
CREATE TABLE import_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE INDEX books_title_index ON books(normalized_title);
CREATE INDEX books_author_index ON books(normalized_author);
CREATE INDEX source_records_book_index ON source_records(book_id);
CREATE INDEX source_records_list_index ON source_records(list_id);
"""

def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.unlink(missing_ok=True)
    db = sqlite3.connect(OUTPUT)
    db.executescript(SCHEMA)
    list_ids = {name: db.execute("INSERT INTO lists(name) VALUES(?)", (name,)).lastrowid for name, *_ in SOURCES}
    isbn_books, title_author_books, title_only_books, counts = {}, {}, {}, Counter()
    with db:
        for list_name, path, author_field, url_field, key_field in SOURCES:
            with path.open(newline="", encoding="utf-8-sig") as stream:
                for row in csv.DictReader(stream):
                    counts["source_records"] += 1
                    title, author = (row.get("title") or "").strip(), (row.get(author_field) or "").strip()
                    if not title:
                        counts["skipped_missing_title"] += 1; continue
                    nt, na = normalize_text(title), normalize_text(author)
                    raw_isbn = normalize_isbn(row.get("isbn") or row.get("isbn13") or "")
                    canonical_isbn, key = isbn13(raw_isbn), (nt, na)
                    book_id = isbn_books.get(canonical_isbn) if canonical_isbn else None
                    book_id = book_id or title_author_books.get(key)
                    if book_id is None:
                        book_id = db.execute("INSERT INTO books(title,normalized_title,author,normalized_author) VALUES(?,?,?,?)", (title, nt, author, na)).lastrowid
                        counts["books"] += 1
                    title_author_books.setdefault(key, book_id)
                    title_only_books.setdefault(nt, set()).add(book_id)
                    if canonical_isbn:
                        isbn_books[canonical_isbn] = book_id
                        db.execute("INSERT OR IGNORE INTO book_identifiers VALUES(?,'ISBN13',?)", (book_id, canonical_isbn))
                    if raw_isbn and raw_isbn != canonical_isbn:
                        db.execute("INSERT OR IGNORE INTO book_identifiers VALUES(?,'ISBN10',?)", (book_id, raw_isbn))
                    list_id = list_ids[list_name]
                    db.execute("INSERT OR IGNORE INTO book_lists VALUES(?,?)", (book_id, list_id))
                    db.execute("INSERT INTO source_records(book_id,list_id,source_key,source_url,raw_json) VALUES(?,?,?,?,?)", (book_id, list_id, row.get(key_field, "") if key_field else "", row.get(url_field, "") if url_field else "", json.dumps(row, ensure_ascii=False, separators=(",", ":"))))
        inventory_rows = json.loads(INVENTORY.read_text(encoding="utf-8-sig"))
        for external_id, row in inventory_rows.items():
            counts["inventory_records"] += 1
            title = (row.get("title") or "").strip()
            authors = row.get("authors") or []
            first_author = authors[0] if authors and isinstance(authors[0], dict) else {}
            author = (row.get("primaryauthor") or first_author.get("lf", "")).strip()
            nt, na = normalize_text(title), normalize_text(author)
            isbn_values = row.get("isbn") or {}
            if isinstance(isbn_values, dict): isbn_values = list(isbn_values.values())
            candidates = [isbn13(value) for value in isbn_values if isbn13(value)]
            book_id = next((isbn_books.get(value) for value in candidates if isbn_books.get(value)), None)
            if book_id is None: book_id = title_author_books.get((nt, na))
            if book_id is None:
                book_id = db.execute("INSERT INTO books(title,normalized_title,author,normalized_author) VALUES(?,?,?,?)", (title, nt, author, na)).lastrowid
                title_author_books[(nt, na)] = book_id
                counts["inventory_only_books"] += 1
            else:
                counts["inventory_matched_books"] += 1
            for value in candidates:
                isbn_books.setdefault(value, book_id)
                db.execute("INSERT OR IGNORE INTO book_identifiers VALUES(?,'ISBN13',?)", (book_id, value))
            quantity = max(1, int(row.get("copies") or 1))
            db.execute("INSERT INTO inventory(book_id,quantity,isbn) VALUES(?,?,?) ON CONFLICT(book_id) DO UPDATE SET quantity=quantity+excluded.quantity", (book_id, quantity, candidates[0] if candidates else None))
            barcode = row.get("barcode") or {}
            if isinstance(barcode, dict): barcode = next(iter(barcode.values()), "")
            db.execute("INSERT INTO inventory_records(book_id,librarything_book_id,barcode,raw_json) VALUES(?,?,?,?)", (book_id, str(external_id), str(barcode or ""), json.dumps(row, ensure_ascii=False, separators=(",", ":"))))
        db.executemany("INSERT INTO import_metadata VALUES(?,?)", [("schema_version", "1"), ("deduplication", "ISBN-13, then exact normalized title and author"), ("inventory_source", INVENTORY.name)])
    report = {
        "database": str(OUTPUT), "source_rows": counts["source_records"], "books": counts["books"],
        "memberships": db.execute("SELECT COUNT(*) FROM book_lists").fetchone()[0],
        "isbn_identifiers": db.execute("SELECT COUNT(*) FROM book_identifiers").fetchone()[0],
        "skipped_missing_title": counts["skipped_missing_title"],
        "inventory_records": counts["inventory_records"],
        "inventory_matched_records": counts["inventory_matched_books"],
        "inventory_only_books": counts["inventory_only_books"],
        "owned_books": db.execute("SELECT COUNT(*) FROM inventory").fetchone()[0],
        "owned_copies": db.execute("SELECT COALESCE(SUM(quantity),0) FROM inventory").fetchone()[0],
        "normalized_titles_with_multiple_book_records": sum(len(ids)>1 for ids in title_only_books.values()),
        "lists": dict(db.execute("SELECT l.name,COUNT(*) FROM book_lists bl JOIN lists l ON l.id=bl.list_id GROUP BY l.id")),
    }
    db.close()
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__": main()
