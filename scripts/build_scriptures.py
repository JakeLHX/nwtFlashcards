#!/usr/bin/env python3
"""Build cleaned scripture flashcard data from LFF extracts and NWT RTF."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RTF_CONTROL_WORD = re.compile(r"\\[a-z]+\d* ?")
RTF_UNICODE = re.compile(r"\\u(-?\d+)\??")
RTF_HEX_CHAR = re.compile(r"\\'([0-9a-fA-F]{2})")


def decode_rtf_text(raw: str) -> str:
    def replace_unicode(match: re.Match[str]) -> str:
        code = int(match.group(1))
        if code < 0:
            code += 65536
        return chr(code)

    text = RTF_UNICODE.sub(replace_unicode, raw)

    def replace_hex(match: re.Match[str]) -> str:
        return bytes.fromhex(match.group(1)).decode("latin-1")

    text = RTF_HEX_CHAR.sub(replace_hex, text)
    text = RTF_CONTROL_WORD.sub("", text)
    return text.strip()


def clean_verse_text(raw: str) -> str:
    text = re.sub(r"\}\{([^}]*)\}", r" \1", raw)
    text = text.replace("}", " ").replace("{", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_code(bible_code: str) -> tuple[int, int, int]:
    code = bible_code.split("-", 1)[0]
    book = int(code[:2])
    chapter = int(code[2:5])
    verse = int(code[5:8])
    if verse == 0:
        verse = 1
    return book, chapter, verse


def normalize_bible_code(bible_code: str) -> str:
    book, chapter, verse = parse_code(bible_code)
    return f"{book:02d}{chapter:03d}{verse:03d}"


def trim_url(url: str, bible_code: str) -> str:
    return re.sub(
        r"bible=[^&]+",
        f"bible={bible_code}",
        url,
    )


def default_url(bible_code: str) -> str:
    return (
        f"https://www.jw.org/finder?pub=nwtsty&bible={bible_code}"
        "&wtlocale=E&srcid=share"
    )


INCLUDE_REFERENCE = re.compile(
    r"^([1-3]?\s?[A-Za-z]+(?:\s[A-Za-z]+)?)\s+(\d+):(.+)$"
)

BOOK_ALIASES = {
    "Psalm": "Psalms",
}


def expand_verse_list(verses_part: str) -> list[int]:
    verses: list[int] = []
    for part in re.split(r",\s*", verses_part.strip()):
        if "-" in part:
            start, end = part.split("-", 1)
            verses.extend(range(int(start), int(end) + 1))
        else:
            verses.append(int(part))
    return verses


def parse_include_file(include_path: Path) -> list[tuple[str, int, int]]:
    """Parse include.txt into (book_name, chapter, verse) tuples."""
    text = include_path.read_text(encoding="utf-8")
    results: list[tuple[str, int, int]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = INCLUDE_REFERENCE.match(line)
        if not match:
            continue
        book = BOOK_ALIASES.get(match.group(1), match.group(1))
        chapter = int(match.group(2))
        for verse in expand_verse_list(match.group(3)):
            results.append((book, chapter, verse))
    return results


def resolve_book_number(library: NwtLibrary, book_name: str) -> int | None:
    name = BOOK_ALIASES.get(book_name, book_name)
    for book in range(1, 67):
        if library.book_name(book) == name:
            return book
    return None


def merge_include_scriptures(
    seen: dict[str, dict],
    include_path: Path,
    library: NwtLibrary,
    missing_text: list[str],
) -> int:
    if not include_path.is_file():
        return 0

    added = 0
    for book_name, chapter, verse in parse_include_file(include_path):
        book = resolve_book_number(library, book_name)
        if not book:
            missing_text.append(f"{book_name} {chapter}:{verse} (unknown book)")
            continue

        bible_code = f"{book:02d}{chapter:03d}{verse:03d}"
        if bible_code in seen:
            continue

        scripture = library.verse_text(bible_code)
        reference = library.reference(bible_code)
        if not scripture:
            missing_text.append(reference)

        seen[bible_code] = {
            "text": reference,
            "scripture": scripture or "",
            "url": default_url(bible_code),
            "bible_code": bible_code,
        }
        added += 1

    return added


def load_book_names(nwt_dir: Path) -> list[str]:
    content = (nwt_dir / "nwt_101_E.rtf").read_text(encoding="utf-8", errors="replace")
    decoded = decode_rtf_text(content)
    books: list[str] = []
    for part in decoded.split("Name of Book:")[1:]:
        match = re.match(r"\s*\}?\s*\{?\s*([^}{]+)", part)
        if match:
            name = re.sub(r"\s+", " ", match.group(1).strip().rstrip("}"))
            books.append(name)
    if len(books) != 66:
        raise RuntimeError(f"Expected 66 book names, found {len(books)}")
    return books


def parse_segment(text: str, start_chapter: int) -> dict[int, dict[int, str]]:
    chapters: dict[int, dict[int, str]] = {}
    current_ch = start_chapter
    last_verse = 0

    header = re.match(r"(?:\}\{)?Chapter \}\{(\d+)\}\{1\}\{", text)
    rest = text[header.end() :] if header else text

    verse_one_end = re.search(r"-432\{2\}\{|\{2\}\{", rest)
    if verse_one_end:
        chapters.setdefault(current_ch, {})[1] = clean_verse_text(
            rest[: verse_one_end.start()]
        )
        if rest[verse_one_end.start() :].startswith("-432"):
            rest = rest[verse_one_end.end() :]
        else:
            rest = rest[verse_one_end.start() :]

    for match in re.finditer(
        r"\{(\d+)\}\{(.+?)(?=\{\d+\}\{|-432\{|-560\{|\Z)", rest, re.DOTALL
    ):
        verse = int(match.group(1))
        if verse == 1 and last_verse > 1:
            current_ch += 1
        chapters.setdefault(current_ch, {})[verse] = clean_verse_text(match.group(2))
        last_verse = verse

    return chapters


def parse_standard_chapters(content: str) -> dict[int, dict[int, str]]:
    decoded = decode_rtf_text(content)
    body_start = decoded.find("Chapter }{1}{1}{")
    if body_start >= 0:
        body = decoded[body_start:]
        markers = list(re.finditer(r"(?:^|\}\{)Chapter \}\{(\d+)\}\{(\d+)\}\{", body))
        if markers:
            chapters: dict[int, dict[int, str]] = {}
            for index, marker in enumerate(markers):
                start_chapter = int(marker.group(1))
                end = markers[index + 1].start() if index + 1 < len(markers) else len(body)
                segment = body[marker.start() : end]
                chapters.update(parse_segment(segment, start_chapter))
            return chapters

    outline = decoded.find("Outline of Contents")
    search_from = outline if outline >= 0 else len(decoded) // 4
    match = re.search(r"\{1\}\{", decoded[search_from:])
    if not match:
        return {}

    rest = decoded[search_from + match.end() :]
    segment = "Chapter }{1}{1}{" + rest
    return parse_segment(segment, 1)


PSALM_HEADER = re.compile(r"(?:\}\{)?Psalm \}\{(\d+)\}(?:\}\{|-432\{)")


def parse_psalm_section(section: str) -> dict[int, str]:
    marker = re.search(r"-432\{1\}\{|\{1\}\{", section)
    if not marker:
        return {}

    rest = section[marker.end() :]
    verses: dict[int, str] = {}
    verse_one_end = re.search(r"\{2\}\{", rest)
    if verse_one_end:
        verses[1] = clean_verse_text(rest[: verse_one_end.start()])
        rest = rest[verse_one_end.start() :]

    for match in re.finditer(
        r"\{(\d+)\}\{(.+?)(?=\{\d+\}\{|-432\{|-560\{|\Z)", rest, re.DOTALL
    ):
        verses[int(match.group(1))] = clean_verse_text(match.group(2))

    return verses


def parse_psalm_block(block: str, start_psalm: int, end_psalm: int) -> dict[int, dict[int, str]]:
    header = PSALM_HEADER.match(block.lstrip("}{"))
    rest = block[header.end() :] if header else block

    marker = re.search(r"-432\{1\}\{|\{1\}\{", rest)
    if not marker:
        return {}

    rest = rest[marker.end() :]
    psalms: dict[int, dict[int, str]] = {}
    current_psalm = start_psalm
    last_verse = 0

    verse_one_end = re.search(r"\{2\}\{", rest)
    if verse_one_end:
        psalms.setdefault(current_psalm, {})[1] = clean_verse_text(
            rest[: verse_one_end.start()]
        )
        rest = rest[verse_one_end.start() :]
        last_verse = 1

    for match in re.finditer(
        r"\{(\d+)\}\{(.+?)(?=\{\d+\}\{|-432\{|-560\{|\Z)", rest, re.DOTALL
    ):
        verse = int(match.group(1))
        if verse == 1 and last_verse > 1:
            current_psalm += 1
            if current_psalm > end_psalm:
                break
        psalms.setdefault(current_psalm, {})[verse] = clean_verse_text(match.group(2))
        last_verse = verse

    return psalms


def parse_psalms(content: str) -> dict[int, dict[int, str]]:
    decoded = decode_rtf_text(content)
    markers = list(PSALM_HEADER.finditer(decoded))
    psalms: dict[int, dict[int, str]] = {}

    for index, marker in enumerate(markers):
        psalm_num = int(marker.group(1))
        end = markers[index + 1].start() if index + 1 < len(markers) else len(decoded)
        block = decoded[marker.start() : end]
        if index + 1 < len(markers):
            next_psalm = int(markers[index + 1].group(1))
        elif psalm_num < 150:
            next_psalm = 151
        else:
            next_psalm = psalm_num

        if next_psalm == psalm_num + 1:
            verses = parse_psalm_section(block)
            if verses:
                psalms[psalm_num] = verses
        else:
            psalms.update(parse_psalm_block(block, psalm_num, next_psalm - 1))

    return psalms


class NwtLibrary:
    def __init__(self, nwt_dir: Path) -> None:
        self._nwt_dir = nwt_dir
        self._book_names = load_book_names(nwt_dir)
        self._files = self._index_files()
        self._cache: dict[int, dict[int, dict[int, str]]] = {}

    def _index_files(self) -> dict[int, Path]:
        files: dict[int, Path] = {}
        for path in self._nwt_dir.glob("nwt_*_*_E.rtf"):
            match = re.match(r"nwt_(\d+)_", path.name)
            if match:
                files[int(match.group(1))] = path
        return files

    def book_name(self, book: int) -> str:
        return self._book_names[book - 1]

    def _load_book(self, book: int) -> dict[int, dict[int, str]]:
        if book in self._cache:
            return self._cache[book]

        path = self._files.get(book)
        if not path:
            self._cache[book] = {}
            return {}

        content = path.read_text(encoding="utf-8", errors="replace")
        if book == 19:
            parsed = parse_psalms(content)
        else:
            parsed = parse_standard_chapters(content)

        self._cache[book] = parsed
        return parsed

    def verse_text(self, bible_code: str) -> str | None:
        book, chapter, verse = parse_code(bible_code)
        chapters = self._load_book(book)
        return chapters.get(chapter, {}).get(verse)

    def reference(self, bible_code: str) -> str:
        book, chapter, verse = parse_code(bible_code)
        return f"{self.book_name(book)} {chapter}:{verse}"


def build_scriptures(
    extracted_path: Path,
    nwt_dir: Path,
    include_path: Path | None = None,
) -> tuple[list[dict], dict]:
    library = NwtLibrary(nwt_dir)
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    entries = [entry for entry in payload["entries"] if entry["type"] == "scripture"]

    seen: dict[str, dict] = {}
    missing_text: list[str] = []

    for entry in entries:
        raw_code = entry.get("bible_code")
        if not raw_code:
            continue

        bible_code = normalize_bible_code(raw_code)
        if bible_code in seen:
            continue

        scripture = library.verse_text(bible_code)
        reference = library.reference(bible_code)

        if not scripture:
            missing_text.append(reference)

        seen[bible_code] = {
            "text": reference,
            "scripture": scripture or "",
            "url": trim_url(entry["url"], bible_code),
            "bible_code": bible_code,
        }

    include_added = 0
    if include_path:
        include_added = merge_include_scriptures(seen, include_path, library, missing_text)

    scriptures = sorted(seen.values(), key=lambda item: item["text"])
    stats = {
        "total_entries": len(entries),
        "unique_verses": len(scriptures),
        "with_text": sum(1 for item in scriptures if item["scripture"]),
        "from_include": include_added,
        "missing_text": missing_text,
    }
    return scriptures, stats


def filter_by_include(
    all_scriptures: list[dict],
    include_path: Path,
    library: NwtLibrary,
) -> tuple[list[dict], list[str]]:
    """Return scriptures from the full set that appear in include.txt."""
    by_code = {item["bible_code"]: item for item in all_scriptures}
    filtered: list[dict] = []
    seen: set[str] = set()
    missing: list[str] = []

    if not include_path.is_file():
        return filtered, missing

    for book_name, chapter, verse in parse_include_file(include_path):
        book = resolve_book_number(library, book_name)
        if not book:
            missing.append(f"{book_name} {chapter}:{verse} (unknown book)")
            continue

        bible_code = f"{book:02d}{chapter:03d}{verse:03d}"
        if bible_code in seen:
            continue
        seen.add(bible_code)

        if bible_code in by_code:
            filtered.append(by_code[bible_code])
        else:
            missing.append(library.reference(bible_code))

    return filtered, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Build scripture flashcard JSON.")
    parser.add_argument(
        "--extracted",
        type=Path,
        default=Path(__file__).parent / "extracted_scriptures.json",
    )
    parser.add_argument(
        "--nwt-dir",
        type=Path,
        default=Path(__file__).parent / "nwt_E.rtf",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(__file__).parent.parent / "src" / "data" / "scriptures.json",
        help="Filtered output: verses listed in include.txt",
    )
    parser.add_argument(
        "--full-output",
        type=Path,
        default=Path(__file__).parent.parent / "src" / "data" / "430_scriptures.json",
        help="Full catalog of all course scriptures",
    )
    parser.add_argument(
        "--include",
        type=Path,
        default=Path(__file__).parent / "include.txt",
        help="Scripture references to include in the filtered output",
    )
    args = parser.parse_args()

    if not args.extracted.is_file():
        print(f"Extracted data not found: {args.extracted}", file=sys.stderr)
        return 1
    if not args.nwt_dir.is_dir():
        print(f"NWT RTF directory not found: {args.nwt_dir}", file=sys.stderr)
        return 1

    all_scriptures, stats = build_scriptures(args.extracted, args.nwt_dir, args.include)
    library = NwtLibrary(args.nwt_dir)
    filtered, missing_from_full = filter_by_include(all_scriptures, args.include, library)

    args.full_output.parent.mkdir(parents=True, exist_ok=True)
    args.full_output.write_text(
        json.dumps(all_scriptures, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    args.output.write_text(
        json.dumps(filtered, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        f"Built {stats['unique_verses']} full verses -> {args.full_output}",
        file=sys.stderr,
    )
    print(
        f"Filtered {len(filtered)} verses from include.txt -> {args.output}",
        file=sys.stderr,
    )
    if stats["missing_text"]:
        print(
            f"Warning: {len(stats['missing_text'])} full-set verses missing NWT text:",
            file=sys.stderr,
        )
        for reference in stats["missing_text"][:10]:
            print(f"  - {reference}", file=sys.stderr)
        if len(stats["missing_text"]) > 10:
            print(f"  ... and {len(stats['missing_text']) - 10} more", file=sys.stderr)
    if missing_from_full:
        print(
            f"Warning: {len(missing_from_full)} include.txt verses not in full set:",
            file=sys.stderr,
        )
        for reference in missing_from_full[:10]:
            print(f"  - {reference}", file=sys.stderr)
        if len(missing_from_full) > 10:
            print(f"  ... and {len(missing_from_full) - 10} more", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
