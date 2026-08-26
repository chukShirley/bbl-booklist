import json
import re
from pathlib import Path

import pdfplumber

PDF = Path("/Users/adamshirley/Downloads/John Senior The Thousand Good Books List (1).pdf")
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "john-senior" / "john-senior-capture.json"

HEADINGS = {
    "THE NURSERY (Ages 2 – 7)": ("The Nursery", "Ages 2-7"),
    "SCHOOL DAYS (Ages 7 – 12)": ("School Days", "Ages 7-12"),
    "ADOLESCENCE (Ages 12 – 16)": ("Adolescence", "Ages 12-16"),
    "YOUTH (Ages 16 – 20)": ("Youth", "Ages 16-20"),
    "SPIRITUAL READING (All ages)": ("Spiritual Reading", "All ages"),
    "MUSIC": ("Music", "All ages"),
    "ART": ("Art", "All ages"),
}
SPECIAL_STARTS = (
    "Arabian Nights.", "Gesta Romanorum.", "Mother Goose ",
    "Til Eulenspiegel ", "The Bible.", "The Kenneth Clark series ",
)
PROSE_STARTS = (
    "Literary experience begins", "while they look", "which they already",
    "Avoiding extremes", "distinction between", "work only", "until the repeated",
    "few works", "for neophytes", "With an opera", "and play it", "or German",
    "whole opera", "to have two", "(Most important", "and the text",
)


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def is_entry_start(line):
    if line.startswith(("Protestants the King James", "Both are literary masterpieces")):
        return False
    if line.startswith(SPECIAL_STARTS):
        return True
    if line.startswith(("de la Mare,", "de Sales,", "Marryat, Frederick,")):
        return True
    return bool(re.match(r"^[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’ .:-]*(?:, [A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’ .-]*)?[.:]\.?\s+", line))


def split_semicolons(text):
    parts, current, depth = [], [], 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        if char == ";" and depth == 0:
            parts.append(normalize("".join(current)))
            current = []
        else:
            current.append(char)
    parts.append(normalize("".join(current)))
    return [part for part in parts if part]


def parse_entry(raw, section, age_range, page):
    raw = normalize(raw)
    if raw.startswith("The Kenneth Clark series "):
        rows = [{"author": "Clark, Kenneth", "title": "Civilisation", "notes": raw}]
    else:
        special = next((prefix for prefix in ("Arabian Nights", "Gesta Romanorum", "Mother Goose", "Til Eulenspiegel", "The Bible") if raw.startswith(prefix)), None)
        if special:
            rows = [{"author": "", "title": special, "notes": raw[len(special):].lstrip(". :")}]
        else:
            match = re.match(r"^(.*?)(?:\.\.?|:)\s+(.*)$", raw)
            if not match and raw.startswith("Marryat, Frederick,"):
                match = re.match(r"^(Marryat, Frederick),\s+(.*)$", raw)
            if not match:
                rows = [{"author": "", "title": raw.rstrip("."), "notes": ""}]
            else:
                author, works = normalize(match.group(1)).rstrip(":"), normalize(match.group(2))
                parts = split_semicolons(works)
                rows = []
                trailing_note = ""
                for part in parts:
                    part = part.strip().rstrip(".")
                    if not part:
                        continue
                    if re.fullmatch(r"(?:and )?(?:many )?others(?: in the series)?", part, re.I) or re.fullmatch(r"and (?:poems|plays)", part, re.I):
                        trailing_note = part
                        if rows:
                            rows[-1]["notes"] = normalize("; ".join(filter(None, [rows[-1]["notes"], part])))
                        continue
                    note_parts = re.findall(r"\([^()]*\)", part)
                    title = normalize(re.sub(r"\s*\([^()]*\)\s*", " ", part)).rstrip(" ,")
                    sentence_note = re.match(r"^(.*?)(?:\.\s+)(Illustrated by|Translated by|All illustrated by)(.*)$", title, re.I)
                    note = normalize(" ".join(note_parts))
                    if sentence_note:
                        title = sentence_note.group(1).rstrip(" .")
                        note = normalize("; ".join(filter(None, [note, sentence_note.group(2) + sentence_note.group(3)])))
                    rows.append({"author": author, "title": title, "notes": note})
                if not rows:
                    rows = [{"author": author, "title": works.rstrip("."), "notes": trailing_note}]
    for row in rows:
        row.update({
            "section": section,
            "age_range": age_range,
            "raw_recommendation": raw,
            "source_page": page,
            "Source": "John Senior - The Thousand Good Books",
        })
    return rows


entries = []
section = age_range = None
current = None
current_page = None

with pdfplumber.open(PDF) as pdf:
    for page_number in range(4, 11):
        text = pdf.pages[page_number - 1].extract_text() or ""
        for original_line in text.splitlines():
            line = normalize(original_line)
            if not line or line == "SENIOR’S INCOMPLETE LIFE-LONG READING LIST":
                continue
            if line in HEADINGS:
                if current:
                    entries.extend(parse_entry(current, section, age_range, current_page))
                    current = None
                section, age_range = HEADINGS[line]
                continue
            if section is None or line.startswith(PROSE_STARTS):
                continue
            if is_entry_start(line):
                if current:
                    entries.extend(parse_entry(current, section, age_range, current_page))
                current, current_page = line, page_number
            elif current:
                current += " " + line
    if current:
        entries.extend(parse_entry(current, section, age_range, current_page))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"rows": len(entries), "output": str(OUT)}, indent=2))
