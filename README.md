# Book Scout

Book Scout is an offline-first Android app for checking second-hand books against
one or more private lending-library wish lists. It scans ISBN barcodes, supports
title/author search, identifies every matching source list, and stores owned status
on the phone.

## MVP features

- Fully offline catalog stored in SQLite
- Prebuilt catalog loaded from `app/src/main/assets/book-scout.db`
- ISBN barcode scanning with an on-device ML Kit model
- Title, author, ISBN, and list-name search
- Fuzzy matching for imperfect titles
- Source-list badges and notes
- Persistent "mark owned" status

## Run on a Mac

1. Install the current stable Android Studio.
2. Open this repository as a project.
3. Allow Gradle to sync and install Android SDK 35 if prompted.
4. Run the `app` configuration on an Android phone or emulator running Android 8+
   (API 26).

For realistic barcode and offline testing, use a physical Android phone. The first
Gradle sync needs internet access; the app itself does not.

## Rebuild the catalog

The source lists remain as CSV files in `data/`. Build the searchable SQLite asset with:

```sh
python3 scripts/build_catalog_db.py
```

The importer preserves original source rows, connects each canonical book to every
source list, and merges only by ISBN or an exact normalized title-and-author match.
It writes a summary to `data/catalog-import-report.json`. The current LibraryThing
collection export in `data/raw/inventory/` populates the separate inventory tables.
During development, clear the app's storage or uninstall it to load a newly rebuilt
database asset.
