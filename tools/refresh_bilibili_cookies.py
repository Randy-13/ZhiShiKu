from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "auth" / "bilibili.cookies.txt"


def ytdlp_command() -> list[str]:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    script = Path(sys.executable).resolve().parent / ("yt-dlp.exe" if sys.platform.startswith("win") else "yt-dlp")
    if script.exists():
        return [str(script)]
    return [sys.executable, "-m", "yt_dlp"]


def export_cookies(browser: str, output: Path) -> subprocess.CompletedProcess[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            *ytdlp_command(),
            "--cookies-from-browser",
            browser,
            "--cookies",
            str(output),
            "--skip-download",
            "--no-warnings",
            "https://www.bilibili.com",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh Bilibili cookies for yt-dlp.")
    parser.add_argument("--browser", default="edge", help="Browser profile source, for example edge, chrome, or firefox.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Netscape cookies output path.")
    args = parser.parse_args()

    output = Path(args.output).resolve()
    completed = export_cookies(args.browser, output)
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "yt-dlp failed to export cookies.").strip()
        print(message[-1200:])
        print()
        print("Tip: close Edge/Chrome completely, make sure Bilibili is logged in, then run this script again.")
        return completed.returncode or 1

    if not output.exists() or output.stat().st_size <= 0:
        print(f"yt-dlp finished but did not create cookies file: {output}")
        return 1

    text = output.read_text(encoding="utf-8", errors="ignore")
    required = ("SESSDATA", "DedeUserID", "bili_jct")
    missing = [name for name in required if name not in text]
    if missing:
        print(f"Cookies exported to {output}, but missing Bilibili login keys: {', '.join(missing)}")
        print("Open Bilibili in the browser, log in again, then rerun this script.")
        return 1

    print(f"Refreshed Bilibili cookies: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
