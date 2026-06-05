from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "static",
    ROOT / "app.py",
    ROOT / "storage.py",
    ROOT / "document_parser.py",
    ROOT / "markdown_writer.py",
    ROOT / "README.md",
]
SUFFIXES = {".py", ".js", ".html", ".css", ".md", ".json"}
MOJIBAKE_TOKENS = ("????", "???", "锛", "鑺", "�")


def iter_files() -> list[Path]:
    files: list[Path] = []
    for target in TARGETS:
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            files.extend(path for path in target.rglob("*") if path.suffix.lower() in SUFFIXES)
    return sorted(set(files))


def suspicious_line(line: str) -> bool:
    if any(token in line for token in ("锛", "鑺", "�")):
        return True
    # Ignore valid JS operators and URL query strings; flag only human-visible runs.
    compact = line.replace("??", "").replace("?.", "").replace("?ids=", "")
    return "???" in compact or "????" in compact


def main() -> int:
    findings: list[str] = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            findings.append(f"{path.relative_to(ROOT)}: not utf-8: {exc}")
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if suspicious_line(line):
                safe = line[:180].encode("ascii", "backslashreplace").decode("ascii")
                findings.append(f"{path.relative_to(ROOT)}:{line_no}: {safe}")
    if findings:
        print("Encoding check failed:")
        print("\n".join(findings))
        return 1
    print("Encoding check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
