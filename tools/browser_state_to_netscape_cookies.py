from __future__ import annotations

import json
import sys
from pathlib import Path


DOMAIN_FILTERS = {
    "bilibili": ("bilibili.com",),
    "douyin": ("douyin.com", "iesdouyin.com", "bytedance.com"),
}


def bool_flag(value: object) -> str:
    return "TRUE" if bool(value) else "FALSE"


def domain_flag(domain: str) -> str:
    return "TRUE" if domain.startswith(".") else "FALSE"


def expiry_value(cookie: dict) -> str:
    expires = cookie.get("expires")
    if expires in (None, "", -1):
        return "0"
    try:
        return str(int(float(expires)))
    except (TypeError, ValueError):
        return "0"


def cookies_from_state(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        if isinstance(payload.get("cookies"), list):
            return payload["cookies"]
        if isinstance(payload.get("state"), dict) and isinstance(payload["state"].get("cookies"), list):
            return payload["state"]["cookies"]
    if isinstance(payload, list):
        return payload
    return []


def convert(input_path: Path, output_path: Path, platform: str = "bilibili") -> int:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    cookies = cookies_from_state(payload)
    domains = DOMAIN_FILTERS.get(platform, (platform,))
    selected_cookies = [
        cookie
        for cookie in cookies
        if any(domain in str(cookie.get("domain") or "") for domain in domains)
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Netscape HTTP Cookie File",
        "# Generated locally from agent-browser state for yt-dlp. Keep this file private.",
    ]
    for cookie in selected_cookies:
        domain = str(cookie.get("domain") or "")
        path = str(cookie.get("path") or "/")
        secure = bool_flag(cookie.get("secure"))
        expires = expiry_value(cookie)
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        if not domain or not name:
            continue
        lines.append("\t".join([domain, domain_flag(domain), path, secure, expires, name, value]))
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(selected_cookies)


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print("Usage: python tools/browser_state_to_netscape_cookies.py <state.json> <cookies.txt> [platform]")
        return 2
    platform = sys.argv[3] if len(sys.argv) == 4 else "bilibili"
    count = convert(Path(sys.argv[1]), Path(sys.argv[2]), platform)
    print(f"Wrote {count} {platform} cookies to {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
