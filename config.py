from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv(encoding="utf-8-sig")


def env_value(name: str, default: str | None = None) -> str | None:
    return os.getenv(name) or os.getenv(f"\ufeff{name}") or default


OCR_PROVIDER = env_value("OCR_PROVIDER", "paddleocr")
LLM_PROVIDER = env_value("LLM_PROVIDER", "deepseek")

DEEPSEEK_API_KEY = env_value("DEEPSEEK_API_KEY") or env_value("OPENAI_API_KEY")
DEEPSEEK_BASE_URL = env_value("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = env_value("DEEPSEEK_MODEL", "deepseek-v4-flash")
LLM_TIMEOUT = float(env_value("LLM_TIMEOUT", env_value("OPENAI_TIMEOUT", "120")))
LLM_MAX_RETRIES = int(env_value("LLM_MAX_RETRIES", env_value("OPENAI_MAX_RETRIES", "2")))

ASR_PROVIDER = (env_value("ASR_PROVIDER", "") or "").lower()
ASR_API_KEY = env_value("ASR_API_KEY") or env_value("OPENAI_API_KEY")
ASR_BASE_URL = (env_value("ASR_BASE_URL", "https://api.openai.com/v1") or "").rstrip("/")
ASR_MODEL = env_value("ASR_MODEL", "gpt-4o-mini-transcribe")
ASR_TIMEOUT = float(env_value("ASR_TIMEOUT", "300") or "300")

OCR_MODEL_SIZE = (env_value("OCR_MODEL_SIZE", "mobile") or "mobile").lower()
OCR_MAX_SIDE = int(env_value("OCR_MAX_SIDE", "1800") or "1800")
OCR_CPU_THREADS = int(env_value("OCR_CPU_THREADS", "4") or "4")
OCR_OMP_THREADS = int(env_value("OCR_OMP_THREADS", "1") or "1")
OCR_RECOGNITION_BATCH_SIZE = int(env_value("OCR_RECOGNITION_BATCH_SIZE", "4") or "4")
