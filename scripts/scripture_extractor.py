#!/usr/bin/env python3
"""Extract scripture references and hyperlinks from Enjoy Life Forever RTF files."""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HYPERLINK_PATTERN = re.compile(
    r'\\field\{\\\*\\fldinst \{HYPERLINK "([^"]+)" \}\}\{\\fldrslt\{(.+?)\}\}\}',
    re.DOTALL,
)
RTF_CONTROL_WORD = re.compile(r"\\[a-z]+\d* ?")
RTF_UNICODE = re.compile(r"\\u(-?\d+)\??")
RTF_HEX_CHAR = re.compile(r"\\'([0-9a-fA-F]{2})")


def decode_rtf_text(raw: str) -> str:
    """Strip RTF control codes and decode unicode escapes from display text."""
    text = raw

    def replace_unicode(match: re.Match[str]) -> str:
        code = int(match.group(1))
        if code < 0:
            code += 65536
        return chr(code)

    text = RTF_UNICODE.sub(replace_unicode, text)

    def replace_hex(match: re.Match[str]) -> str:
        return bytes.fromhex(match.group(1)).decode("latin-1")

    text = RTF_HEX_CHAR.sub(replace_hex, text)
    text = RTF_CONTROL_WORD.sub("", text)
    return text.strip()


def classify_link(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if "bible" in params:
        return "scripture"
    if any("VIDEO" in value for value in params.get("lank", [])):
        return "video"
    if "docid" in params:
        return "article"
    return "other"


def extract_bible_code(url: str) -> str | None:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    bible_values = params.get("bible")
    return bible_values[0] if bible_values else None


def extract_lesson_number(filename: str) -> int | None:
    match = re.search(r"lff_E_(\d+)\.rtf$", filename)
    return int(match.group(1)) if match else None


def extract_from_rtf(content: str, source_file: str) -> list[dict]:
    lesson = extract_lesson_number(source_file)
    results: list[dict] = []

    for url, display_raw in HYPERLINK_PATTERN.findall(content):
        display_text = decode_rtf_text(display_raw)
        link_type = classify_link(url)
        entry: dict = {
            "source_file": source_file,
            "lesson": lesson,
            "type": link_type,
            "text": display_text,
            "url": url,
        }
        if link_type == "scripture":
            entry["bible_code"] = extract_bible_code(url)
        results.append(entry)

    return results


def iter_rtf_files(rtf_dir: Path) -> list[Path]:
    return sorted(rtf_dir.glob("*.rtf"), key=lambda path: path.name)


def extract_all(rtf_dir: Path) -> list[dict]:
    all_entries: list[dict] = []
    for rtf_path in iter_rtf_files(rtf_dir):
        content = rtf_path.read_text(encoding="utf-8", errors="replace")
        all_entries.extend(extract_from_rtf(content, rtf_path.name))
    return all_entries


def summarize(entries: list[dict]) -> dict:
    by_type: dict[str, int] = {}
    scriptures: set[str] = set()
    for entry in entries:
        by_type[entry["type"]] = by_type.get(entry["type"], 0) + 1
        if entry["type"] == "scripture":
            scriptures.add(entry["text"])
    return {
        "total_hyperlinks": len(entries),
        "by_type": by_type,
        "unique_scriptures": len(scriptures),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract scriptures and hyperlinks from LFF RTF files."
    )
    parser.add_argument(
        "--rtf-dir",
        type=Path,
        default=Path(__file__).parent / "lff_E.rtf",
        help="Directory containing lff_E_*.rtf files",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write JSON output to this file (default: stdout)",
    )
    parser.add_argument(
        "--scriptures-only",
        action="store_true",
        help="Include only scripture hyperlinks (bible= URLs)",
    )
    args = parser.parse_args()

    if not args.rtf_dir.is_dir():
        print(f"RTF directory not found: {args.rtf_dir}", file=sys.stderr)
        return 1

    entries = extract_all(args.rtf_dir)
    if args.scriptures_only:
        entries = [entry for entry in entries if entry["type"] == "scripture"]

    summary = summarize(entries)
    output = {"summary": summary, "entries": entries}
    json_text = json.dumps(output, indent=2, ensure_ascii=False)

    if args.output:
        args.output.write_text(json_text, encoding="utf-8")
        print(
            f"Extracted {summary['total_hyperlinks']} hyperlinks "
            f"({summary['unique_scriptures']} unique scriptures) "
            f"from {len(list(iter_rtf_files(args.rtf_dir)))} files "
            f"-> {args.output}",
            file=sys.stderr,
        )
    else:
        print(json_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
