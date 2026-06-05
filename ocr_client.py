from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import config
from schemas import OcrResult


CACHE_DIR = Path(__file__).resolve().parent / ".paddle_cache"
CACHE_DIR.mkdir(exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(CACHE_DIR)
os.environ["PADDLE_HOME"] = str(CACHE_DIR / "paddle")
os.environ["PADDLEOCR_HOME"] = str(CACHE_DIR / "paddleocr")
os.environ["PADDLE_PDX_CACHE_HOME"] = str(CACHE_DIR / "paddlex")
os.environ["PADDLE_PDX_MODEL_SOURCE"] = os.getenv("PADDLE_PDX_MODEL_SOURCE", "bos")
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = os.getenv(
    "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True"
)
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = os.getenv(
    "PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False"
)
os.environ["PADDLE_PDX_CPU_NUM_THREADS"] = str(config.OCR_CPU_THREADS)
os.environ["OMP_NUM_THREADS"] = str(config.OCR_OMP_THREADS)

OCR_INPUT_DIR = CACHE_DIR / "ocr_inputs"
OCR_INPUT_DIR.mkdir(exist_ok=True)


def _ocr_model_names() -> tuple[str, str]:
    if config.OCR_MODEL_SIZE == "server":
        return "PP-OCRv5_server_det", "PP-OCRv5_server_rec"
    return "PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec"


@lru_cache(maxsize=1)
def paddle_ocr():
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError(
            "PaddleOCR is not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install paddleocr paddlepaddle"
        ) from exc
    det_model, rec_model = _ocr_model_names()
    init_kwargs = {
        "text_detection_model_name": det_model,
        "text_recognition_model_name": rec_model,
        "text_recognition_batch_size": config.OCR_RECOGNITION_BATCH_SIZE,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
    }
    try:
        return PaddleOCR(**init_kwargs)
    except TypeError:
        return PaddleOCR(lang="ch", use_angle_cls=False)
    except ValueError as exc:
        if "Unknown argument" in str(exc):
            return PaddleOCR(lang="ch")
        raise


def prepare_image_for_ocr(image_path: Path) -> Path:
    if config.OCR_MAX_SIDE <= 0:
        return image_path
    try:
        from PIL import Image
    except ImportError:
        return image_path

    try:
        with Image.open(image_path) as image:
            width, height = image.size
            max_side = max(width, height)
            if max_side <= config.OCR_MAX_SIDE:
                return image_path

            scale = config.OCR_MAX_SIDE / max_side
            resized_size = (max(1, round(width * scale)), max(1, round(height * scale)))
            resample = getattr(Image, "Resampling", Image).LANCZOS
            if image.mode in {"RGBA", "LA"}:
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            resized = image.resize(resized_size, resample)
            output_path = OCR_INPUT_DIR / f"{image_path.stem}_{config.OCR_MAX_SIDE}.png"
            resized.save(output_path, format="PNG")
            return output_path
    except Exception:
        return image_path


def _extract_text_lines(node) -> list[str]:
    if node is None:
        return []

    if isinstance(node, dict):
        lines: list[str] = []
        for key in ("rec_texts", "texts"):
            value = node.get(key)
            if isinstance(value, list):
                lines.extend(str(item).strip() for item in value if str(item).strip())
        value = node.get("text")
        if isinstance(value, str) and value.strip():
            lines.append(value.strip())
        if lines:
            return lines
        nested_lines: list[str] = []
        for value in node.values():
            nested_lines.extend(_extract_text_lines(value))
        return nested_lines

    if isinstance(node, (list, tuple)):
        if (
            len(node) >= 2
            and isinstance(node[1], (list, tuple))
            and node[1]
            and isinstance(node[1][0], str)
            and node[1][0].strip()
        ):
            return [node[1][0].strip()]
        lines: list[str] = []
        for item in node:
            lines.extend(_extract_text_lines(item))
        return lines

    return []


def _explain_ocr_error(exc: Exception) -> RuntimeError:
    text = str(exc)
    if "No available model hosting platforms" in text or "download" in text.lower():
        return RuntimeError(
            "PaddleOCR 模型下载失败。请确认本机可以访问 Paddle 模型源，或预先下载 OCR 模型。"
            "当前程序已强制使用 BOS 模型源并跳过可用性探测。原始错误："
            + text
        )
    if "Permission" in text or "Access is denied" in text:
        return RuntimeError(
            "PaddleOCR 缓存目录没有写入权限。请检查项目目录下 .paddle_cache 的权限。原始错误："
            + text
        )
    return RuntimeError("PaddleOCR 识别失败：" + text)


def recognize_screenshot(image_path: Path) -> OcrResult:
    try:
        ocr = paddle_ocr()
        prepared_path = prepare_image_for_ocr(image_path)
        if hasattr(ocr, "predict"):
            result = ocr.predict(str(prepared_path))
        else:
            result = ocr.ocr(str(prepared_path), cls=False)
    except Exception as exc:
        raise _explain_ocr_error(exc) from exc

    lines = _extract_text_lines(result)

    cleaned_text = "\n".join(lines).strip() or "No usable text recognized."
    title_hint = lines[0][:80] if lines else image_path.stem
    return OcrResult(title_hint=title_hint, topic_hint="", cleaned_text=cleaned_text)


def recognize_screenshots(image_paths: list[Path]) -> str:
    if not image_paths:
        raise ValueError("No screenshots were provided")
    blocks = []
    for index, image_path in enumerate(image_paths, start=1):
        ocr = recognize_screenshot(image_path)
        blocks.append(
            f"[Screenshot {index}]\n"
            f"Title hint: {ocr.title_hint}\n"
            f"Topic hint: {ocr.topic_hint or 'unknown'}\n"
            f"Recognized text:\n{ocr.cleaned_text}"
        )
    return "\n\n---\n\n".join(blocks)
