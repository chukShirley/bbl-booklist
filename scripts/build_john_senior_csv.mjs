import fs from "node:fs/promises";
import path from "node:path";
import { Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const input = path.join(root, "data", "raw", "john-senior", "john-senior-capture.json");
const output = path.join(root, "data", "john-senior-thousand-good-books.csv");
const records = JSON.parse(await fs.readFile(input, "utf8"));
const fields = ["title", "author", "section", "age_range", "notes", "raw_recommendation", "source_page", "Source"];
const quote = value => {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
const csv = [fields.join(","), ...records.map(row => fields.map(field => quote(row[field])).join(","))].join("\n") + "\n";
await fs.writeFile(output, csv, "utf8");

const workbook = await Workbook.fromCSV(csv, { sheetName: "Books" });
console.log((await workbook.inspect({
  kind: "table", range: "Books!A1:H10", include: "values",
  tableMaxRows: 10, tableMaxCols: 8, maxChars: 10000,
})).ndjson);
console.log((await workbook.inspect({
  kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 }, summary: "CSV error scan",
})).ndjson);
const key = row => `${row.title.toLocaleLowerCase()}|${row.author.toLocaleLowerCase()}`;
const duplicates = records.length - new Set(records.map(key)).size;
console.log(JSON.stringify({
  rows: records.length,
  sections: Object.fromEntries([...new Set(records.map(row => row.section))].map(section => [section, records.filter(row => row.section === section).length])),
  exactTitleAuthorDuplicates: duplicates,
  output,
}, null, 2));
