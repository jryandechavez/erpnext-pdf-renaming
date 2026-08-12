from __future__ import annotations

import base64
import fcntl
import gc
import os
import re
import tempfile
from contextlib import contextmanager
from threading import Lock

import frappe
import pymupdf
from frappe import _
from rapidocr import RapidOCR

MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_PAGE_COUNT = 100
UPLOAD_CHUNK_SIZE = 1024 * 1024
_engine_lock = Lock()
OCR_LOCK_PATH = "/tmp/erpnext-pdf-renaming-ocr.lock"


@contextmanager
def _single_ocr_worker():
    """Prevent multiple Gunicorn workers from loading OCR models together."""
    with open(OCR_LOCK_PATH, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _ocr_pair(pair_document) -> tuple[dict[str, str], list[str]]:
    with _single_ocr_worker():
        engine = RapidOCR(
            params={
                "Global.use_cls": False,
                "Global.max_side_len": 1600,
                "EngineConfig.onnxruntime.intra_op_num_threads": 1,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                "EngineConfig.onnxruntime.enable_cpu_mem_arena": False,
            }
        )
        try:
            page_texts = []
            previews = []
            pair_pages = [pair_document[0], pair_document[1]]
            for page in pair_pages:
                preview = page.get_pixmap(dpi=110, colorspace=pymupdf.csRGB, alpha=False)
                previews.append(
                    "data:image/jpeg;base64,"
                    + base64.b64encode(preview.tobytes("jpeg")).decode("ascii")
                )
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
                    rect.x0 + rect.width * 0.22,
                    rect.y0 + rect.height * 0.12,
                    rect.x1 - rect.width * 0.06,
                    rect.y0 + rect.height * 0.46,
                )
                image = page.get_pixmap(
                    dpi=180, colorspace=pymupdf.csRGB, clip=clip, alpha=False
                )
                with _engine_lock:
                    result = engine(image.tobytes("png"), use_cls=False)
                page_texts.append(" ".join(result.txts or ()))

            values = extract_values(page_texts)
            if not values["si"]:
                for page, text in zip(pair_pages, page_texts):
                    if re.search(r"CHARGE.{0,160}?INVOICE", text, re.IGNORECASE):
                        values["si"] = _read_charge_serial(page, engine)
                        if values["si"]:
                            break
            return values, previews
        finally:
            engine = None
            gc.collect()


@frappe.whitelist()
def process_pdf() -> dict:
    """OCR one page pair and return that pair without retaining the source PDF."""
    uploaded = frappe.request.files.get("file")
    if not uploaded or not (uploaded.filename or "").lower().endswith(".pdf"):
        frappe.throw(_("Please upload a PDF file."))

    document = None
    pair_document = None
    source_path = None
    try:
        source_size = 0
        with tempfile.NamedTemporaryFile(prefix="pdf-renamer-", suffix=".pdf", delete=False) as source:
            source_path = source.name
            while chunk := uploaded.read(UPLOAD_CHUNK_SIZE):
                source_size += len(chunk)
                if source_size > MAX_FILE_SIZE:
                    frappe.throw(_("The PDF must be 50 MB or smaller."))
                source.write(chunk)
        if not source_size:
            frappe.throw(_("The uploaded PDF is empty."))

        document = pymupdf.open(source_path)
        if document.needs_pass:
            frappe.throw(_("Password-protected PDFs are not supported."))
        if document.page_count < 2 or document.page_count % 2:
            frappe.throw(
                _("This PDF has {0} page(s). Please upload an even number of pages.").format(
                    document.page_count
                )
            )
        if document.page_count > MAX_PAGE_COUNT:
            frappe.throw(
                _("This PDF has too many pages. The maximum is {0} pages.").format(
                    MAX_PAGE_COUNT
                )
            )

        try:
            pair_index = int(frappe.form_dict.get("pair_index") or 0)
        except (TypeError, ValueError):
            frappe.throw(_("The requested page pair is invalid."))
        pair_count = document.page_count // 2
        if pair_index < 0 or pair_index >= pair_count:
            frappe.throw(_("The requested page pair is outside this PDF."))
        page_start = pair_index * 2

        # Copy the requested pages first, then release the potentially large
        # source PDF before loading the OCR engine or rendering any images.
        pair_document = pymupdf.open()
        pair_document.insert_pdf(document, from_page=page_start, to_page=page_start + 1)
        pair_bytes = pair_document.tobytes(garbage=3, deflate=True)
        document.close()
        document = None
        os.unlink(source_path)
        source_path = None

        values, previews = _ocr_pair(pair_document)
        pair_pdf = base64.b64encode(pair_bytes).decode("ascii")

        return {
            "values": values,
            "complete": all(values.values()),
            "previews": previews,
            "pair_pdf": pair_pdf,
            "pair_index": pair_index,
            "pair_count": pair_count,
            "page_numbers": [page_start + 1, page_start + 2],
        }
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Temporary PDF OCR failed")
        frappe.throw(_("The PDF could not be read. Please verify the scan and try again."))
    finally:
        if document is not None:
            document.close()
        if pair_document is not None:
            pair_document.close()
        if source_path and os.path.exists(source_path):
            os.unlink(source_path)


def _read_charge_serial(page, engine) -> str:
    """Run a high-resolution OCR pass over the top-right serial area."""
    rect = page.rect
    clip = pymupdf.Rect(
        rect.x0 + rect.width * 0.43,
        rect.y0 + rect.height * 0.16,
        rect.x0 + rect.width * 0.92,
        rect.y0 + rect.height * 0.43,
    )
    image = page.get_pixmap(dpi=320, colorspace=pymupdf.csRGB, clip=clip, alpha=False)
    with _engine_lock:
        result = engine(image.tobytes("png"), use_cls=False)

    translations = str.maketrans({"O": "0", "D": "0", "I": "1", "L": "1"})
    lines = [str(line).upper() for line in (result.txts or ())]
    for index, line in enumerate(lines):
        if not re.search(r"\bN[O0°º.]?\b", line):
            continue
        context = " ".join(lines[index : index + 3]).translate(translations)
        candidates = re.findall(r"(?<!\d)\d{5,8}(?!\d)", context)
        if candidates:
            return candidates[0][-5:]

    for line in lines:
        if "POR" in line or re.search(r"P[O0]\s*:", line):
            continue
        normalized = line.translate(translations)
        candidates = re.findall(r"(?<!\d)\d{5,8}(?!\d)", normalized)
        candidates = [value for value in candidates if len(set(value[-5:])) > 1]
        if candidates:
            return candidates[0][-5:]
    return ""


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
        without_po = re.sub(r"P[O0]R\s*[0-9ODIL]{6,14}", " ", nearby)
        normalized = without_po.translate(
            str.maketrans({"O": "0", "D": "0", "I": "1", "L": "1"})
        )
        candidates = re.findall(r"(?<!\d)(\d{5,8})(?!\d)", normalized)
        return candidates[0][-5:] if candidates else ""

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
