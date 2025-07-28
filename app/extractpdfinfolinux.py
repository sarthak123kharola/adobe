import os
import json
from pathlib import Path
import fitz  # PyMuPDF
from collections import Counter, defaultdict
import re

def extract_title(pdf_path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    blocks = page.get_text("dict")["blocks"]
    candidates = []

    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text or span["bbox"][1] > 200:
                    continue
                if text.lower().startswith(("table of contents", "index", "1.", "abstract")):
                    continue
                if not any(c.isalnum() for c in text):
                    continue
                candidates.append({
                    "text": text,
                    "font_size": span["size"],
                    "font_name": span.get("font", ""),
                    "x0": span["bbox"][0],
                    "y0": span["bbox"][1],
                    "x1": span["bbox"][2],
                    "y1": span["bbox"][3],
                    "page_number": 1
                })

    candidates.sort(key=lambda c: (-c["font_size"], c["y0"]))
    return candidates[0] if candidates else None

def extract_blocks(pdf_path):
    doc = fitz.open(pdf_path)
    all_lines = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    all_lines.append({
                        "text": text,
                        "font_size": round(span["size"], 2),
                        "font_name": span.get("font", "unknown"),
                        "is_bold": "bold" in span.get("font", "").lower(),
                        "x0": round(span["bbox"][0], 2),
                        "y0": round(span["bbox"][1], 2),
                        "x1": round(span["bbox"][2], 2),
                        "y1": round(span["bbox"][3], 2),
                        "page_number": page_num + 1
                    })

    return all_lines

def extract_outline(pdf_path, title_line=None):
    lines = extract_blocks(pdf_path)
    by_page = defaultdict(list)
    for line in lines:
        by_page[line["page_number"]].append(line)

    headings = []
    for page, lines in by_page.items():
        font_sizes = [line["font_size"] for line in lines]
        common_size = Counter(font_sizes).most_common(1)[0][0]

        for line in lines:
            text = line["text"]
            if len(text) < 3 or line["font_size"] < common_size:
                continue
            if title_line and line["page_number"] == title_line["page_number"] and abs(line["y0"] - title_line["y0"]) < 1:
                continue
            if re.search(r"(https?://|www\.)", text.lower()):
                continue
            headings.append(line)

    return headings

def assign_heading_levels(lines):
    if not lines:
        return []
    font_sizes = sorted({line["font_size"] for line in lines}, reverse=True)
    font_size_to_level = {fs: i + 1 for i, fs in enumerate(font_sizes)}

    for line in lines:
        line["level"] = font_size_to_level[line["font_size"]]
        match = re.match(r"^(\d+(\.\d+){0,5})", line["text"])
        if match:
            line["level"] = min(match.group(1).count('.') + 1, 6)

    return [
        {
            "level": f"H{line['level']}",
            "text": line["text"].strip(),
            "page": line["page_number"]
        }
        for line in lines
    ]

def process_pdfs(input_dir="/app/input", output_dir="/app/output"):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for pdf_file in input_path.glob("*.pdf"):
        print(f"📄 Processing: {pdf_file.name}")
        title_line = extract_title(pdf_file)
        raw_headings = extract_outline(pdf_file, title_line=title_line)
        structured_headings = assign_heading_levels(raw_headings)

        output_data = {
            "title": title_line["text"].strip() if title_line else "",
            "outline": structured_headings
        }

        output_file = output_path / f"{pdf_file.stem}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved to {output_file}")

if __name__ == "__main__":
    process_pdfs()
