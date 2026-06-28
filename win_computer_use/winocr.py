"""Windows native OCR via Windows.Media.Ocr (winrt).

Dual-engine OCR strategy:
1. Windows.Media.Ocr (fast, ~0.5s) — used when English OCR pack is available
2. RapidOCR (slower, ~5s cropped / ~12s full) — fallback for Chinese-heavy content

Auto-detects Chinese text ratio to pick the best engine.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import screen


# ---------------------------------------------------------------------------
# Windows.Media.Ocr (native, fast)
# ---------------------------------------------------------------------------

def _win_ocr_available() -> bool:
    """Check if English Windows.Media.Ocr is available (fast path)."""
    try:
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.globalization import Language
        langs = list(OcrEngine.available_recognizer_languages)
        for lang in langs:
            tag = lang.language_tag.lower()
            # We need English-capable OCR (en-US, en-GB, etc.)
            if tag.startswith("en-") or tag.startswith("zh-"):
                return True
        return False
    except Exception:
        return False


def _chinese_ratio(text: str) -> float:
    """Return the ratio of CJK characters in the given text."""
    if not text:
        return 0.0
    cjk = sum(1 for c in text if ord(c) > 0x4E00)
    return cjk / len(text)


async def _win_ocr_words_async(image_path: str) -> Optional[List[Dict[str, Any]]]:
    """Run Windows.Media.Ocr on an image and return word-level results.

    Returns list of::
        [{"text": "...", "x": int, "y": int, "w": int, "h": int}, ...]
    """
    try:
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.storage import StorageFile
        from winrt.windows.storage.streams import RandomAccessStreamReference

        file = await StorageFile.get_file_from_path_async(image_path)
        stream_ref = RandomAccessStreamReference.create_from_file(file)
        stream = await stream_ref.open_read_async()
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()

        # Try English first, fall back to whatever is available
        langs = list(OcrEngine.available_recognizer_languages)
        engine = None
        for lang in langs:
            tag = lang.language_tag.lower()
            if tag.startswith("en-"):
                engine = OcrEngine.try_create_from_language(lang)
                break
        if not engine and langs:
            engine = OcrEngine.try_create_from_language(langs[0])

        if not engine:
            return None

        result = await engine.recognize_async(bitmap)

        out: List[Dict[str, Any]] = []
        for line in result.lines:
            text = line.text.strip()
            if not text:
                continue
            words = line.words
            for word in words:
                rect = word.bounding_rect
                out.append({
                    "text": word.text.strip(),
                    "x": int(rect.x),
                    "y": int(rect.y),
                    "w": int(rect.width),
                    "h": int(rect.height),
                    "conf": 1.0,
                })

        return out if out else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# RapidOCR (accurate but slower)
# ---------------------------------------------------------------------------

def _rapid_ocr_words(image_path: str) -> Optional[List[Dict[str, Any]]]:
    """Run RapidOCR on an image and return word-level results."""
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
        result = ocr(image_path)
        out: List[Dict[str, Any]] = []
        if result and result[0]:
            for line in result[0]:
                if len(line) >= 3 and line[1]:
                    poly = line[0]
                    xs = [p[0] for p in poly]
                    ys = [p[1] for p in poly]
                    out.append({
                        "text": str(line[1]),
                        "x": int(min(xs)),
                        "y": int(min(ys)),
                        "w": int(max(xs) - min(xs)),
                        "h": int(max(ys) - min(ys)),
                        "conf": float(line[2]) if len(line) > 2 else 0.0,
                    })
        return out if out else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API: smart OCR
# ---------------------------------------------------------------------------

def ocr_words_smart(
    image_path: str,
    *,
    crop_rect: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Run OCR with auto-engine selection and optional crop.

    Args:
        image_path: Path to the screenshot image.
        crop_rect: Optional (left, top, right, bottom) to crop before OCR.
                   Coordinates are in the original image's coordinate system.

    Returns list of word dicts with keys: text, x, y, w, h, conf
    Coordinates are in the ORIGINAL (uncropped) image's coordinate system.
    """
    target_path = image_path
    offset_x = 0
    offset_y = 0

    # Crop the image if requested (reduces OCR area → faster)
    if crop_rect:
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is not None:
                l, t, r, b = crop_rect
                cropped = img[t:b, l:r]
                # Save to temp file
                fd, tmp_path = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                cv2.imwrite(tmp_path, cropped, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                target_path = tmp_path
                offset_x, offset_y = l, t
        except Exception:
            pass  # fall through to full-image OCR

    # Strategy 1: Try Windows native OCR first (fast, ~0.5s)
    if _win_ocr_available():
        try:
            words = asyncio.run(_win_ocr_words_async(target_path))
            if words:
                text = " ".join(w["text"] for w in words)
                cjk_ratio = _chinese_ratio(text)

                # If mostly Chinese, re-run with RapidOCR for better accuracy
                if cjk_ratio > 0.15:
                    rapid_words = _rapid_ocr_words(target_path)
                    if rapid_words:
                        words = rapid_words
                        print(f"[ocr] WinOCR had {cjk_ratio:.0%} Chinese → re-ran RapidOCR", flush=True)
                    else:
                        print(f"[ocr] WinOCR had {cjk_ratio:.0%} Chinese (using WinOCR)", flush=True)
                else:
                    print(f"[ocr] WinOCR: {len(words)} words ({cjk_ratio:.0%} Chinese)", flush=True)

                # Translate coordinates back to original image
                if offset_x or offset_y:
                    for w in words:
                        w["x"] += offset_x
                        w["y"] += offset_y
                if target_path != image_path:
                    try:
                        os.unlink(target_path)
                    except Exception:
                        pass
                return words
        except Exception:
            pass

    # Strategy 2: Fallback to RapidOCR
    words = _rapid_ocr_words(target_path)
    text = " ".join(w["text"] for w in words) if words else ""
    cjk_ratio = _chinese_ratio(text)
    print(f"[ocr] RapidOCR: {len(words) if words else 0} words ({cjk_ratio:.0%} Chinese)", flush=True)

    # Translate coordinates back to original image
    if words and (offset_x or offset_y):
        for w in words:
            w["x"] += offset_x
            w["y"] += offset_y

    # Cleanup temp file
    if target_path != image_path:
        try:
            os.unlink(target_path)
        except Exception:
            pass

    return words
