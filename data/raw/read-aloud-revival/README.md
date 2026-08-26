# Read-Aloud Revival raw captures

These JSON files are page-level source captures from the Read-Aloud Revival
book archive. They are retained for auditing, targeted recapture, and rebuilding
the consolidated catalog.

The Android app should use the consolidated output at
`data/read-aloud-revival-books.csv`, not these intermediate files.

Rebuild the CSV from the repository root with:

```sh
node scripts/build_read_aloud_revival_csv.mjs
```
