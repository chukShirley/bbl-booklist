# Book Scout

Book Scout is an offline-first app for checking second-hand books against one or
more private lending-library wish lists. The recommended client is an installable
Progressive Web App (PWA); the original native Android client remains available.
Both support ISBN lookup, title/author search, source-list identification, and
persistent owned status.

## Run the web app locally

Rebuild the browser catalog, start a local server, and open the displayed address:

```sh
python3 scripts/build_catalog_db.py
python3 scripts/build_web_catalog.py
python3 -m http.server 4173 --directory web
```

Then visit [http://localhost:4173](http://localhost:4173). Browsers allow service
workers on `localhost`, so offline behavior can be tested locally. In Chrome DevTools,
use **Application → Service Workers → Offline** to verify searches without a network.

To install it on an Android phone, deploy the contents of `web/` to an HTTPS static
host such as GitHub Pages or Cloudflare Pages. Open the site once in Chrome, allow the
catalog to finish loading, and choose **Add to Home screen** or the in-app **Install**
button. After that first load, the catalog and interface work offline. Ownership
changes are kept in IndexedDB on that phone and survive catalog refreshes.

The repository deploys `web/` automatically through `.github/workflows/deploy-pages.yml`
whenever `main` is updated. The published app is available at
[https://chukshirley.github.io/bbl-booklist/](https://chukshirley.github.io/bbl-booklist/).

The PWA includes:

- A 28,000+ book catalog stored in the browser cache
- Per-word title, author, ISBN, and list searching
- Offline ownership overrides stored in IndexedDB
- Installable home-screen manifest and offline service worker
- Camera ISBN scanning through Android Chrome's Barcode Detection API, with manual
  ISBN entry when that browser API is unavailable

## Native Android client

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


## Reviewed ISBN additions (2026-11-18)

Book Scout retains all 28,609 original records, list memberships, primary ISBNs,
ownership flags, and stable ownership keys. A new `isbns` array supports searching
all accepted ISBN-10/13 and alternate editions. Native SQLite search already
supports these identifiers; existing Android installations need a rebuilt APK.

The reviewed public supplement `data/supported-isbn-additions.json` adds 119,660
identifiers to 10,863 records. ISBN coverage rises from 5,659 to 14,537 books;
14,072 remain without. It reuses accepted BBL Recommends research without
importing its owned-book recommendation policy. No ownership claims change.
The 1,134 ambiguous transfer groups remain in the website workspace for review;
no identifier reassignment or duplicate merges are applied here.

Every rebuild validates target ID/title/author, ISBN checksums and conflicts.
Original primary ISBNs determine ownership keys, so enrichment preserves saved
ownership choices. Private research queues, inventory and notes are excluded.
Aggregate verification: `data/isbn-enrichment-report.json`. Rollback: revert the
update commit and rebuild/deploy.

Validation: `python3 tests/isbn_enrichment.py` tests mappings and conflicts;
`node tests/isbn_search.cjs` checks all 128,279 ISBN searches using client search
functions, plus legacy and hyphenated ISBN queries.
