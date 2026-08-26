import fs from "node:fs/promises";
import path from "node:path";
import { Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const input = path.join(root, "data", "raw", "reshelving-alexandria", "reshelving-alexandria-notion-capture.json");
const output = path.join(root, "data", "reshelving-alexandria-books.csv");

const records = JSON.parse(await fs.readFile(input, "utf8"));
const unique = [...new Map(records.map(record => [record.notion_page_id, record])).values()]
  .sort((a, b) => a.title.localeCompare(b.title, "en", { sensitivity: "base" }));

const fields = [
  "title", "author_illustrator", "series", "isbn", "selected_by", "read_by",
  "genres", "target_audience", "page_count", "tags", "affiliate_url",
  "source_url", "notion_page_id", "Source",
];
const quote = value => {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
const csv = [
  fields.join(","),
  ...unique.map(record => fields.map(field => quote(record[field])).join(",")),
].join("\n") + "\n";
await fs.writeFile(output, csv, "utf8");

const workbook = await Workbook.fromCSV(csv, { sheetName: "Books" });
console.log((await workbook.inspect({
  kind: "table", range: "Books!A1:N8", include: "values",
  tableMaxRows: 8, tableMaxCols: 14, maxChars: 12000,
})).ndjson);
console.log((await workbook.inspect({
  kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 }, summary: "CSV error scan",
})).ndjson);

console.log(JSON.stringify({
  capturedRecords: records.length,
  uniqueBooks: unique.length,
  withAuthorIllustrator: unique.filter(record => record.author_illustrator).length,
  withIsbn: unique.filter(record => record.isbn).length,
  withGenres: unique.filter(record => record.genres).length,
  withTargetAudience: unique.filter(record => record.target_audience).length,
  output,
}, null, 2));
