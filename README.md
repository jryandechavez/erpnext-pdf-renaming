# ERPNext PDF Renaming

A Frappe/ERPNext v15 custom app that adds a **PDF Renamer** Desk page. Users select a two-page PDF, the browser extracts the Charge Invoice, Delivery Receipt, and PO numbers, and downloads the original PDF with a standardized filename:

```text
SI_65532_AND_DR_66584_PO_POR00116530.pdf
```

## Privacy design

All PDF rendering, OCR, review, and renaming happen in the browser. The app does not create a Frappe `File`, call a PDF-processing server endpoint, or retain document content. Reloading or closing the Desk page clears the selected PDF from memory.

## Install

```bash
cd /path/to/frappe-bench
bench get-app https://github.com/jryandechavez/erpnext-pdf-renaming.git
bench --site your-site.example install-app erpnext_pdf_renaming
bench --site your-site.example migrate
bench build --app erpnext_pdf_renaming
bench --site your-site.example clear-cache
bench restart
```

Open **PDF Renamer** from the ERPNext search bar, or navigate to `/app/pdf-renamer`.

## Validation rules

- PDF format only
- Exactly two pages
- Maximum file size of 15 MB
- Users can correct all extracted values before download
- Download stays disabled until SI, DR, and PO values are present

## Supported layout

The OCR and extraction rules are tuned for the supplied Tic & Terry two-page Charge Invoice and Delivery Receipt layout. The PO is cross-checked across both pages when OCR finds it twice.

