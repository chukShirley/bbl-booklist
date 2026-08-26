import fs from "node:fs/promises";
import { Workbook } from "@oai/artifact-tool";

const input = new URL("../data/biblioguides-books.csv", import.meta.url);
const csvText = await fs.readFile(input, "utf8");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "Books" });
const check = await workbook.inspect({
  kind: "table",
  range: "Books!A1:K8",
  include: "values",
  tableMaxRows: 8,
  tableMaxCols: 11,
  maxChars: 8000,
});
console.log(check.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 },
  summary: "CSV error scan",
});
console.log(errors.ndjson);
