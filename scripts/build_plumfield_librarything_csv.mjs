import fs from "node:fs/promises";
import path from "node:path";
import { Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const input = path.join(root, "data", "raw", "plumfield-living-library", "plumfield-librarything-capture.json");
const output = path.join(root, "data", "plumfield-living-library-books.csv");
const editions = JSON.parse(await fs.readFile(input, "utf8"));

const splitValues = value => String(value ?? "").split(",").map(part => part.trim()).filter(Boolean);
const works = new Map();
for (const edition of editions) {
  const key = edition.work_id || edition.book_id || edition.source_url;
  if (!works.has(key)) {
    works.set(key, {
      title: edition.title,
      author: edition.author,
      series: edition.series,
      tags: new Set(),
      media: new Set(),
      barcodes: new Set(),
      work_id: edition.work_id,
      book_ids: new Set(),
      source_urls: new Set(),
      Source: "Plumfield Living Library",
    });
  }
  const work = works.get(key);
  if (!work.title && edition.title) work.title = edition.title;
  if (!work.author && edition.author) work.author = edition.author;
  if (!work.series && edition.series) work.series = edition.series;
  splitValues(edition.tags).forEach(value => work.tags.add(value));
  if (edition.media) work.media.add(edition.media);
  if (edition.barcode) work.barcodes.add(edition.barcode);
  if (edition.book_id) work.book_ids.add(edition.book_id);
  if (edition.source_url) work.source_urls.add(edition.source_url);
}

const records = [...works.values()].map(work => ({
  title: work.title,
  author: /^(?:=|-{1,2}|-Author-)$/.test(work.author) ? "" : work.author,
  series: work.series,
  tags: [...work.tags].join("; "),
  media: [...work.media].join("; "),
  edition_count: work.book_ids.size,
  work_id: work.work_id,
  book_ids: [...work.book_ids].join("; "),
  barcodes: [...work.barcodes].join("; "),
  source_urls: [...work.source_urls].join("; "),
  Source: work.Source,
})).sort((a, b) => a.title.localeCompare(b.title, "en", { sensitivity: "base" }));

const fields = ["title", "author", "series", "tags", "media", "edition_count", "work_id", "book_ids", "barcodes", "source_urls", "Source"];
const quote = value => {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
const csv = [fields.join(","), ...records.map(record => fields.map(field => quote(record[field])).join(","))].join("\n") + "\n";
await fs.writeFile(output, csv, "utf8");

const workbook = await Workbook.fromCSV(csv, { sheetName: "Books" });
console.log((await workbook.inspect({
  kind: "table", range: "Books!A1:K8", include: "values",
  tableMaxRows: 8, tableMaxCols: 11, maxChars: 12000,
})).ndjson);
console.log((await workbook.inspect({
  kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 }, summary: "CSV error scan",
})).ndjson);
console.log(JSON.stringify({
  capturedEditions: editions.length,
  uniqueWorks: records.length,
  duplicateEditionsConsolidated: editions.length - records.length,
  withAuthor: records.filter(record => record.author).length,
  withSeries: records.filter(record => record.series).length,
  withTags: records.filter(record => record.tags).length,
  output,
}, null, 2));
