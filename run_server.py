from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def lower_windows_priority() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        below_normal_priority = 0x00004000
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel32.SetPriorityClass.restype = wintypes.BOOL
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), below_normal_priority)
    except Exception:
        pass


class Tee:
    def __init__(self, *streams):
        self.streams = [stream for stream in streams if stream is not None]

    def write(self, data: str) -> int:
        for stream in self.streams:
            try:
                stream.write(data)
                stream.flush()
            except Exception:
                pass
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            try:
                stream.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        return any(getattr(stream, "isatty", lambda: False)() for stream in self.streams)


if __name__ == "__main__":
    lower_windows_priority()
    root = Path(__file__).resolve().parent
    os.environ.setdefault("FIGURELEARNING_DB_PATH", str(root / "knowledge.db"))
    log_path = root / "server.run.log"
    log_file = log_path.open("a", encoding="utf-8")
    sys.stdout = Tee(sys.stdout, log_file)
    sys.stderr = Tee(sys.stderr, log_file)
    (root / "images").mkdir(exist_ok=True)
    (root / "documents").mkdir(exist_ok=True)
    (root / "knowledge").mkdir(exist_ok=True)
    uvicorn.run(
        "src.main:create_app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=True,
        log_config=None,
        factory=True,
    )
