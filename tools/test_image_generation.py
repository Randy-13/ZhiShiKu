from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def image_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/images/generations"):
        return base
    return base + "/images/generations"


def write_image(first: dict[str, Any], output_path: Path, timeout: float) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if first.get("b64_json"):
        output_path.write_bytes(base64.b64decode(str(first["b64_json"])))
        return "b64_json"

    url = str(first.get("url") or "")
    if url.startswith("data:image/"):
        _header, _sep, data = url.partition(",")
        output_path.write_bytes(base64.b64decode(data))
        return "data_url"

    if url:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            output_path.write_bytes(response.read())
        return "url"

    raise RuntimeError("response data[0] has neither b64_json nor url")


def request_image(args: argparse.Namespace, api_key: str, response_format: str = "") -> dict[str, Any]:
    endpoint = image_endpoint(args.base_url)
    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt,
        "n": 1,
        "size": args.size,
    }
    if args.quality:
        payload["quality"] = args.quality
    if response_format:
        payload["response_format"] = response_format

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        summary = {
            "endpoint": endpoint,
            "model": payload.get("model"),
            "size": payload.get("size"),
            "quality": payload.get("quality", ""),
            "response_format": payload.get("response_format", ""),
        }
        raise RuntimeError(f"HTTP {exc.code}: {detail}; request={json.dumps(summary, ensure_ascii=False)}") from exc

    data = json.loads(raw)
    first = (data.get("data") or [{}])[0]
    return {"endpoint": endpoint, "payload": payload, "data": data, "first": first}


def main() -> int:
    parser = argparse.ArgumentParser(description="Test OpenAI-compatible image generation and save a local image.")
    parser.add_argument("--base-url", default="https://fiveeeee.cn/v1")
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--quality", default="auto")
    parser.add_argument("--response-format", default="", choices=["", "b64_json"])
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--prompt", default="一张简洁的测试图，白色背景，中心有中文文字：知识酷图片测试")
    parser.add_argument("--output-dir", default=str(Path("writer") / "_api_tests"))
    args = parser.parse_args()

    api_key = os.environ.get("IMAGE_API_KEY", "").strip()
    if not api_key:
        print("Missing IMAGE_API_KEY environment variable.", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    stamp = time.strftime("%Y%m%d%H%M%S")
    output_path = output_dir / f"direct_image_test_{stamp}.png"

    result = request_image(args, api_key, args.response_format)
    return_mode = write_image(result["first"], output_path, args.timeout)

    print(
        json.dumps(
            {
                "ok": True,
                "endpoint": result["endpoint"],
                "model": result["payload"].get("model"),
                "size": result["payload"].get("size"),
                "quality": result["payload"].get("quality", ""),
                "response_format": result["payload"].get("response_format", ""),
                "return_mode": return_mode,
                "output_path": str(output_path.resolve()),
                "bytes": output_path.stat().st_size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
