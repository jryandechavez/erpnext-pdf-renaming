from __future__ import annotations

import re
from threading import Lock

import frappe
import pymupdf
from frappe import _
from rapidocr import RapidOCR

MAX_FILE_SIZE = 15 * 1024 * 1024
_engine = None
_engine_lock = Lock()


def _get_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = RapidOCR()
    return _engine


@frappe.whitelist()
def process_pdf() -> dict:
    """OCR one request-held PDF without creating a Frappe File or disk copy."""
    uploaded = frappe.request.files.get("file")
    if not uploaded or not (uploaded.filename or "").lower().endswith(".pdf"):
        frappe.throw(_("Please upload a PDF file."))

    content = uploaded.read(MAX_FILE_SIZE + 1)
    if not content:
        frappe.throw(_("The uploaded PDF is empty."))
    if len(content) > MAX_FILE_SIZE:
        frappe.throw(_("The PDF must be 15 MB or smaller."))

    document = None
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
        if document.needs_pass:
            frappe.throw(_("Password-protected PDFs are not supported."))
        if document.page_count != 2:
            frappe.throw(
                _("This PDF has {0} page(s). Please upload exactly two pages.").format(
                    document.page_count
                )
            )

        engine = _get_engine()
        page_texts = []
        for page in document:
            selectable = page.get_text("text") or ""
            if re.search(
                r"CHARGE.{0,120}?INVOICE|DELIVERY.{0,120}?RECEIPT",
                selectable,
                re.IGNORECASE | re.DOTALL,
            ):
                page_texts.append(selectable)
                continue

            rect = page.rect
            clip = pymupdf.Rect(
                rect.x0 + rect.width * 0.08,
                rect.y0 + rect.height * 0.06,
                rect.x1 - rect.width * 0.08,
                rect.y0 + rect.height * 0.58,
            )
            image = page.get_pixmap(dpi=220, colorspace=pymupdf.csRGB, clip=clip, alpha=False)
            # ONNX sessions are reused within each web worker. Serialize calls
            # to avoid overlapping mutable OCR pipeline state under gevent.
            with _engine_lock:
                result = engine(image.tobytes("png"))
            page_texts.append(" ".join(result.txts or ()))

        values = extract_values(page_texts)
        return {"values": values, "complete": all(values.values())}
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Temporary PDF OCR failed")
        frappe.throw(_("The PDF could not be read. Please verify the scan and try again."))
    finally:
        if document is not None:
            document.close()
        # Drop the only application-level reference to the request body. Frappe
        # never creates a File document and no document bytes are written here.
        content = b""


def extract_values(page_texts: list[str]) -> dict[str, str]:
    pages = [re.sub(r"\s+", " ", text.upper().replace("|", "I")).strip() for text in page_texts]

    def nearby_number(text: str, label: str) -> str:
        match = re.search(label, text)
        if not match:
            return ""
        nearby = text[match.end() : match.end() + 120]
        marked = re.search(r"\bN[A-Z°º.,: ]{0,10}?[O0]?\s*([0-9]{5,10})", nearby)
        if marked:
            # Dates printed beneath the red serial can touch the number in a
            # scan (for example OCR may return ``O165532``). These forms use a
            # five-digit SI/DR serial, so keep the rightmost five digits.
            return marked.group(1)[-5:]
        fallback = re.search(r"(?:^|\s)([0-9]{4,6})(?:\s|$)", nearby)
        return fallback.group(1) if fallback else ""

    def purchase_order(text: str) -> str:
        match = re.search(r"\bP[O0]\s*[:.-]?\s*(P[O0]R\s*[0-9ODIL]{6,14})\b", text)
        if not match:
            match = re.search(r"\b(P[O0]R\s*[0-9ODIL]{6,14})\b", text)
        if not match:
            return ""
        raw = re.sub(r"\s", "", match.group(1)).replace("P0R", "POR", 1)
        suffix = raw[3:].translate(str.maketrans({"O": "0", "D": "0", "I": "1", "L": "1"}))
        return raw[:3] + suffix

    si = ""
    dr = ""
    purchase_orders = []
    for page in pages:
        si = si or nearby_number(page, r"CHARGE.{0,120}?INVOICE")
        dr = dr or nearby_number(page, r"DELIVERY.{0,120}?RECEIPT")
        po = purchase_order(page)
        if po:
            purchase_orders.append(po)

    po = max(set(purchase_orders), key=purchase_orders.count) if purchase_orders else ""
    return {"si": si, "dr": dr, "po": po}
