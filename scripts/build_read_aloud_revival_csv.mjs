import fs from "node:fs/promises";
import path from "node:path";
import { Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const dataDir = path.join(root, "data");
const rawDir = path.join(dataDir, "raw", "read-aloud-revival");
const output = path.join(dataDir, "read-aloud-revival-books.csv");
const files = (await fs.readdir(rawDir))
  .filter(name => /^read-aloud-revival-page-\d+\.json$/.test(name))
  .sort((a, b) => Number(a.match(/\d+/)[0]) - Number(b.match(/\d+/)[0]));

const records = (await Promise.all(files.map(async name =>
  JSON.parse(await fs.readFile(path.join(rawDir, name), "utf8"))
))).flat();
const byUrl = new Map();
for (const record of records) {
  if (!byUrl.has(record.source_url)) byUrl.set(record.source_url, record);
}
const unique = [...byUrl.values()];
const withAuthor = unique.filter(record => String(record.author ?? "").trim()).length;
const withIsbn = unique.filter(record => String(record.isbn ?? "").trim()).length;
const fields = ["title", "author", "series", "isbn", "source_url", "Source", "archive_page"];
const quote = value => {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
const csv = [fields.join(","), ...unique.map(record => fields.map(field => quote(record[field])).join(","))].join("\n") + "\n";
await fs.writeFile(output, csv, "utf8");

const workbook = await Workbook.fromCSV(csv, { sheetName: "Books" });
console.log((await workbook.inspect({
  kind: "table", range: "Books!A1:G8", include: "values",
  tableMaxRows: 8, tableMaxCols: 7, maxChars: 8000,
})).ndjson);
console.log((await workbook.inspect({
  kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 }, summary: "CSV error scan",
})).ndjson);
console.log(JSON.stringify({
  capturedPages: files.length,
  displayedRows: records.length,
  uniqueBooks: unique.length,
  duplicateRowsRemoved: records.length - unique.length,
  withAuthor,
  withIsbn,
  output,
}, null, 2));
