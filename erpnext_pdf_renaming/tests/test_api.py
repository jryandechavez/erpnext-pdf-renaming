from erpnext_pdf_renaming.api import extract_values


def test_extracts_sample_ocr_variations():
    pages = [
        "DELIVERY 147 Sumilang RECEIPT Ne 66584 Name POR0D116530",
        "CHARGE 147 Sumilang INVOICE PO: POR00116530 Nouly O165532",
    ]

    assert extract_values(pages) == {
        "si": "55532",
        "dr": "66584",
        "po": "POR00116530",
    }
