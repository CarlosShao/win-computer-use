"""Optional OCR via Tesseract.

Tesseract itself (``tesseract.exe``) is **not** installed by pip -- users
must install it from
https://github.com/UB-Mannheim/tesseract/wiki and add it to PATH.
If the binary is missing, every function in this module returns
``None`` rather than raising, so the rest of the skill keeps working
without OCR.

Set ``TESSDATA_PREFIX`` or pass ``tesseract_cmd`` to point at a custom
install location.  Chinese models (``chi_sim`` / ``chi_tra``) require
the matching ``.traineddata`` file in the ``tessdata`` folder.
"""

from __future__ import annotations

import shutil
from typing import Any, Dict, List, Optional, Tuple

import screen


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


def ocr_text(
    region: Optional[Tuple[int, int, int, int]] = None,
    *,
    lang: str = "chi_sim+eng",
    tesseract_cmd: Optional[str] = None,
) -> Optional[str]:
    """Run OCR on a (optionally) cropped region of the screen.

    Returns ``None`` if Tesseract is unavailable.
    """
    pytesseract, err = _ensure_pytesseract()
    if pytesseract is None:
        return None
    if not _resolve_tesseract(pytesseract, tesseract_cmd):
        return None
    info = screen.screenshot(region=region, return_base64=False)
    from PIL import Image  # type: ignore

    text = pytesseract.image_to_string(Image.open(info["path"]), lang=lang)
    return text


def ocr_words(
    region: Optional[Tuple[int, int, int, int]] = None,
    *,
    lang: str = "chi_sim+eng",
    tesseract_cmd: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Run OCR and return per-word bounding boxes.

    Coordinates are absolute screen pixels (i.e. ``region`` offset is
    added back onto each box).  Returns ``None`` when Tesseract is
    unavailable.
    """
    pytesseract, err = _ensure_pytesseract()
    if pytesseract is None:
        return None
    if not _resolve_tesseract(pytesseract, tesseract_cmd):
        return None
    info = screen.screenshot(region=region, return_base64=False)
    from PIL import Image  # type: ignore

    data = pytesseract.image_to_data(
        Image.open(info["path"]),
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