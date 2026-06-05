from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


AGENT_BROWSER = r"C:\Users\Bo Yang\AppData\Roaming\npm\agent-browser.cmd"


def run_agent_browser(*args: str) -> dict:
    completed = subprocess.run(
        [AGENT_BROWSER, "--auto-connect", *args, "--json"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return json.loads(completed.stdout)


def latest_detail_request_id(video_id: str) -> str:
    payload = run_agent_browser(
        "network",
        "requests",
        "--filter",
        "aweme/v1/web/aweme/detail",
        "--type",
        "xhr",
        "--status",
        "200",
    )
    requests = payload.get("data", {}).get("requests", [])
    matches = [item for item in requests if video_id in item.get("url", "")]
    if not matches:
        raise RuntimeError(
            f"No captured Douyin aweme/detail response found for {video_id}. "
            "Open the Douyin video in Chrome first and wait until it finishes loading."
        )
    return matches[-1]["requestId"]


def import_detail(video_id: str, output_dir: Path) -> Path:
    request_id = latest_detail_request_id(video_id)
    payload = run_agent_browser("network", "request", request_id)
    body = payload.get("data", {}).get("responseBody")
    if not body:
        raise RuntimeError(f"Captured request {request_id} has no response body.")
    data = json.loads(body)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{video_id}.json"
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python tools/import_douyin_detail_from_agent_browser.py <douyin_video_id>")
        return 2
    output = import_detail(sys.argv[1], Path("media") / "douyin_detail")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
