#!/usr/bin/env python3
import csv
from pathlib import Path
from urllib.parse import urljoin

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "raw" / "biblioguides" / "biblioguides-source-manifest.tsv"
OUTPUT = ROOT / "data" / "biblioguides-books.csv"
BASE_URL = "https://www.biblioguides.com"
FIELDS = [
    "book_id",
    "title",
    "author",
    "illustrator",
    "publisher",
    "reading_level",
    "year",
    "member_status",
    "source_url",
    "alphabet_section",
    "Source",
]


def clean(value):
    return " ".join((value or "").split())


def linked_names(cell):
    if cell is None:
        return ""
    names = [clean("".join(link.itertext())) for link in cell.xpath('.//a[contains(@href, "/pub/author/")]')]
    return "; ".join(dict.fromkeys(name for name in names if name))


def labeled_cell(cells, prefix):
    for cell in cells:
        if (cell.get("data-label") or "").strip().lower().startswith(prefix):
            return cell
    return None


def parse_source(letter, source):
    document = html.fromstring(Path(source).read_text(encoding="utf-8"))
    rows = document.xpath('//table[@id="booklist"]//tbody/tr[contains(@class,"odd") or contains(@class,"even")]')
    parsed = []
    for row in rows:
        cells = row.xpath("./td")
        book_links = row.xpath('.//a[contains(@href, "/pub/book/")]')
        if not cells or not book_links:
            continue
        source_path = book_links[0].get("href")
        title = clean("".join(book_links[-1].itertext()))
        if not title:
            images = row.xpath('.//img[contains(@src, "/images/covers/")]')
            title = clean(images[0].get("alt")) if images else ""
        id_values = row.xpath('.//input[@name="bookselect"]/@value')
        if not id_values:
            id_values = row.xpath('./td[contains(@class,"memberstatus")]/@id')
        book_id = id_values[0].lstrip("b") if id_values else ""
        author_cell = labeled_cell(cells, "author")
        illustrator_cell = labeled_cell(cells, "illustrator")
        publisher_cell = labeled_cell(cells, "publisher")
        reading_cell = labeled_cell(cells, "reading level")
        year_cell = labeled_cell(cells, "sort year")
        if year_cell is None and cells:
            year_cell = cells[-1]
        status_cells = row.xpath('./td[contains(@class,"memberstatus")]')
        status = clean(" ".join(status_cells[0].itertext())) if status_cells else ""
        if not status and status_cells:
            status = "; ".join(dict.fromkeys(status_cells[0].xpath('.//img[@alt]/@alt')))
        parsed.append({
            "book_id": book_id,
            "title": title,
            "author": linked_names(author_cell),
            "illustrator": linked_names(illustrator_cell),
            "publisher": clean("".join(publisher_cell.itertext())) if publisher_cell is not None else "",
            "reading_level": clean(reading_cell.get("data-order") or "".join(reading_cell.itertext())) if reading_cell is not None else "",
            "year": clean("".join(year_cell.itertext())) if year_cell is not None else "",
            "member_status": status,
            "source_url": urljoin(BASE_URL, source_path),
            "alphabet_section": letter,
            "Source": "Biblioguides",
        })
    return parsed


def main():
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        manifest = list(csv.DictReader(handle, delimiter="\t"))
    if {row["letter"] for row in manifest} != set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        missing = sorted(set("ABCDEFGHIJKLMNOPQRSTUVWXYZ") - {row["letter"] for row in manifest})
        raise SystemExit(f"Manifest is missing letters: {missing}")

    all_rows = []
    for entry in manifest:
        rows = parse_source(entry["letter"], entry["attachment"])
        unique_urls = {row["source_url"] for row in rows}
        expected_rows = int(entry["rows"])
        expected_unique = int(entry["unique_books"])
        if len(rows) != expected_rows or len(unique_urls) != expected_unique:
            raise SystemExit(
                f"{entry['letter']} failed reconciliation: parsed {len(rows)}/{len(unique_urls)}, "
                f"expected {expected_rows}/{expected_unique}"
            )
        all_rows.extend(rows)

    deduplicated = {}
    for row in all_rows:
        key = row["source_url"]
        if key not in deduplicated:
            deduplicated[key] = row
    final_rows = list(deduplicated.values())
    expected_total = sum(int(entry["unique_books"]) for entry in manifest)
    if len(final_rows) != expected_total:
        raise SystemExit(f"Global reconciliation failed: got {len(final_rows)}, expected {expected_total}")
    if any(not row["title"] or not row["source_url"] for row in final_rows):
        raise SystemExit("One or more output rows is missing a title or source URL")

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(final_rows)

    print(f"Wrote {len(final_rows)} books to {OUTPUT}")
    print(f"Missing author: {sum(not row['author'] for row in final_rows)}")
    print(f"Missing reading level: {sum(not row['reading_level'] for row in final_rows)}")
    print(f"Missing year: {sum(not row['year'] for row in final_rows)}")


if __name__ == "__main__":
    main()
