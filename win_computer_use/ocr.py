"""Optional OCR module.

Supports three backends (auto-selected in order):

1. **RapidOCR** (default) — Uses ONNXRuntime, no external Tesseract
   installation needed.  Models auto-download on first use (~40MB).
   Install: `pip install rapidocr-onnxruntime`

2. **Tesseract** (fallback) — Requires `tesseract.exe` in PATH.
   Install: `pip install pytesseract` + download Tesseract binary.

3. **tesserocr** (fallback) — Uses bundled DLL, no exe needed.
   Install: `pip install tesserocr`

Set ``TESSDATA_PREFIX`` or pass ``tesseract_cmd`` to point at a custom
install location.  Chinese models (``chi_sim`` / ``chi_tra``) require
the matching ``.traineddata`` file in the ``tessdata`` folder.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import screen


# ---------------------------------------------------------------------------
# RapidOCR backend (default)
# ---------------------------------------------------------------------------

def _ensure_rapid_ocr():
    """Lazily import and cache a RapidOCR instance."""
    try:
        from rapidocr_onnxruntime import RapidOCR
        # Cache on module level so we only create it once
        if not hasattr(_ensure_rapid_ocr, "_cache"):
            # RapidOCR will auto-download models on first init
            _ensure_rapid_ocr._cache = RapidOCR()  # noqa: PLW0603
        return _ensure_rapid_ocr._cache, None
    except ImportError as exc:
        return None, exc


def _rapid_ocr_text(image_path: str, lang: str = "ch_sim+en") -> Optional[str]:
    """Run RapidOCR and return concatenated text."""
    ocr, err = _ensure_rapid_ocr()
    if ocr is None:
        return None
    try:
        result = ocr(image_path)
        # result format: [[[poly_points], text, conf], ...]
        texts = []
        if result and result[0]:
            for line in result[0]:
                if len(line) >= 2 and line[1]:
                    texts.append(str(line[1]))
        return "\n".join(texts) if texts else None
    except Exception:
        return None


def _rapid_ocr_words(image_path: str, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[List[Dict[str, Any]]]:
    """Run RapidOCR and return per-word bounding boxes."""
    ocr, err = _ensure_rapid_ocr()
    if ocr is None:
        return None
    try:
        result = ocr(image_path)
        out: List[Dict[str, Any]] = []
        off_x = region[0] if region else 0
        off_y = region[1] if region else 0
        if result and result[0]:
            for line in result[0]:
                if len(line) >= 3 and line[1]:
                    # line[0] is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    poly = line[0]
                    xs = [p[0] for p in poly]
                    ys = [p[1] for p in poly]
                    out.append({
                        "text": str(line[1]),
                        "x": int(min(xs)) + int(off_x),
                        "y": int(min(ys)) + int(off_y),
                        "w": int(max(xs) - min(xs)),
                        "h": int(max(ys) - min(ys)),
                        "conf": float(line[2]) if len(line) > 2 else 0.0,
                    })
        return out if out else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tesseract backend (fallback)
# ---------------------------------------------------------------------------

def _ensure_pytesseract():
    try:
        import pytesseract  # type: ignore
    except ImportError as _exc:  # pragma: no cover
        return None, _exc
    return pytesseract, None


def _resolve_tesseract(pytesseract, tesseract_cmd: Optional[str]) -> bool:
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd  # type: ignore[attr-defined]
    cmd = pytesseract.pytesseract.tesseract_cmd  # type: ignore[attr-defined]
    if cmd and shutil.which(cmd) is None and not __import__("os").path.isfile(cmd):
        return False
    return True


def _ocr_fallback(path: str, lang: str) -> Optional[str]:
    """Fallback OCR using tesserocr (bundled DLL, no Tesseract exe needed)."""
    try:
        import tesserocr
        from PIL import Image
        api = tesserocr.PyTessBaseAPI()
        try:
            api.SetImage(Image.open(path))
            text = api.GetUTF8Text()
            return text.strip() or None
        finally:
            api.End()
    except Exception:
        return None


def _ocr_words_fallback(path: str, lang: str, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[List[Dict[str, Any]]]:
    """Fallback OCR words using tesserocr."""
    try:
        import tesserocr
        from PIL import Image
        api = tesserocr.PyTessBaseAPI()
        try:
            api.SetImage(Image.open(path))
            boxes = api.GetComponentImages(tesserocr.RIL.TEXTLINE, True)
            out: List[Dict[str, Any]] = []
            off_x = region[0] if region else 0
            off_y = region[1] if region else 0
            for box in boxes:
                text = api.GetUTF8Text()
                if text and text.strip():
                    out.append({
                        "text": text.strip(),
                        "x": int(box[0]["x"]) + int(off_x),
                        "y": int(box[0]["y"]) + int(off_y),
                        "w": int(box[0]["w"]),
                        "h": int(box[0]["h"]),
                        "conf": 90.0,
                    })
            return out
        finally:
            api.End()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ocr_text(
    region: Optional[Tuple[int, int, int, int]] = None,
    *,
    lang: str = "chi_sim+eng",
    tesseract_cmd: Optional[str] = None,
    backend: str = "auto",
) -> Optional[str]:
    """Run OCR on a (optionally) cropped region of the screen.

    Args:
        backend: "auto" (try RapidOCR → Tesseract → tesserocr),
                 "rapidocr", "tesseract", or "tesserocr"

    Returns ``None`` if no OCR backend is available.
    """
    info = screen.screenshot(region=region, return_base64=False)
    path = info["path"]

    if backend in ("auto", "rapidocr"):
        text = _rapid_ocr_text(path, lang)
        if text is not None:
            return text

    if backend in ("auto", "tesseract"):
        pytesseract, err = _ensure_pytesseract()
        if pytesseract is not None and _resolve_tesseract(pytesseract, tesseract_cmd):
            try:
                from PIL import Image  # type: ignore
                text = pytesseract.image_to_string(Image.open(path), lang=lang)
                return text
            except Exception:
                pass

    if backend in ("auto", "tesserocr"):
        return _ocr_fallback(path, lang)

    return None


def ocr_words(
    region: Optional[Tuple[int, int, int, int]] = None,
    *,
    lang: str = "chi_sim+eng",
    tesseract_cmd: Optional[str] = None,
    backend: str = "auto",
) -> Optional[List[Dict[str, Any]]]:
    """Run OCR and return per-word bounding boxes.

    Coordinates are absolute screen pixels (i.e. ``region`` offset is
    added back onto each box).  Returns ``None`` when no OCR backend is
    available.
    """
    info = screen.screenshot(region=region, return_base64=False)
    path = info["path"]

    if backend in ("auto", "rapidocr"):
        words = _rapid_ocr_words(path, region)
        if words is not None:
            return words

    if backend in ("auto", "tesseract"):
        pytesseract, err = _ensure_pytesseract()
        if pytesseract is not None and _resolve_tesseract(pytesseract, tesseract_cmd):
            try:
                from PIL import Image  # type: ignore
                data = pytesseract.image_to_data(
                    Image.open(path),
                    lang=lang,
                    output_type=pytesseract.Output.DICT,
                )
                out: List[Dict[str, Any]] = []
                off_x = region[0] if region else 0
                off_y = region[1] if region else 0
                n = len(data.get("text", []))
                for i in range(n):
                    txt = data["text"][i].strip()
                    if not txt:
                        continue
                    try:
                        conf = float(data.get("conf", [0] * n)[i])
                    except Exception:
                        conf = -1.0
                    out.append(
                        {
                            "text": txt,
                            "x": int(data["left"][i]) + int(off_x),
                            "y": int(data["top"][i]) + int(off_y),
                            "w": int(data["width"][i]),
                            "h": int(data["height"][i]),
                            "conf": conf,
                        }
                    )
                return out
            except Exception:
                pass

    if backend in ("auto", "tesserocr"):
        return _ocr_words_fallback(path, lang, region)

    return None
