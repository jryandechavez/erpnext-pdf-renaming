# ERPNext PDF Renaming

A Frappe/ERPNext v15 custom app that adds a **PDF Renamer** Desk page. Users select one multi-page PDF containing consecutive two-page document pairs. The app processes pages 1–2, 3–4, 5–6, and so on; lets the user review each pair's Charge Invoice, Delivery Receipt, and PO numbers; then downloads each pair as a separate PDF with a standardized filename:

```text
SI_65532_AND_DR_66584_PO_POR00116530.pdf
```

The GitHub repository is named `erpnext-pdf-renaming`, but the Frappe/Python app
name is `erpnext_pdf_renaming`. Always use the underscore name with
`install-app`, `build --app`, and `list-apps`.

## Temporary processing design

The browser sends the selected PDF directly to one authenticated Frappe API
request. The server holds the request body only while extracting the document
numbers and returns JSON. The app does not create a Frappe `File`, attachment,
database record, or permanent PDF copy. The browser keeps the original PDF in
memory and requests only one page pair at a time. The server returns a temporary
two-page PDF for the current pair, which is released from browser memory after
it is downloaded or skipped.

PDF rendering and OCR use Python dependencies installed automatically with the
app (`PyMuPDF`, `RapidOCR`, and ONNX Runtime). There are no browser PDF workers,
WebAssembly files, language-data assets, external OCR services, or manual
system-package installs.

## Install

### Recommended production installer

Run this as `root` or as the Linux user that owns the Bench. The installer
switches from `root` to the Bench owner automatically, validates the site,
uses the safe `--skip-assets` sequence, registers the app before building,
and can be rerun later to update an existing installation.

```bash
curl -fsSL \
  https://raw.githubusercontent.com/jryandechavez/erpnext-pdf-renaming/main/install.sh \
  -o /tmp/install-erpnext-pdf-renaming.sh

# Review the installer before running it.
less /tmp/install-erpnext-pdf-renaming.sh

bash /tmp/install-erpnext-pdf-renaming.sh \
  --site your-site.example \
  --bench /home/frappe/frappe-bench
```

The same command updates an existing installation without duplicating the
`sites/apps.txt` entry or reinstalling the app on the site. It also creates and
verifies the app's `sites/assets/erpnext_pdf_renaming` link explicitly, avoiding
the missing-public-assets behavior found in some Frappe v15 Bench releases.

### Manual installation

```bash
cd /path/to/frappe-bench
# Skip the automatic asset build until Bench has registered the app.
bench get-app --skip-assets https://github.com/jryandechavez/erpnext-pdf-renaming.git

# Ensure apps.txt ends with a newline and contains the app exactly once.
printf '\n' >> sites/apps.txt
grep -qxF erpnext_pdf_renaming sites/apps.txt || \
  printf '%s\n' erpnext_pdf_renaming >> sites/apps.txt

bench --site your-site.example install-app erpnext_pdf_renaming
bench build --app erpnext_pdf_renaming
bench --site your-site.example clear-cache
bench restart
```

### Recover from an interrupted `get-app`

If `bench get-app` already downloaded and installed the Python package but failed
during `bench build` with `paths[0] ... Received undefined`, do not run
`get-app` again. Register the existing checkout and continue:

```bash
cd /path/to/frappe-bench
printf '\n' >> sites/apps.txt
grep -qxF erpnext_pdf_renaming sites/apps.txt || \
  printf '%s\n' erpnext_pdf_renaming >> sites/apps.txt
bench build --app erpnext_pdf_renaming
bench --site your-site.example install-app erpnext_pdf_renaming
bench --site your-site.example clear-cache
bench restart
```

Open **PDF Renamer** from the ERPNext search bar, or navigate to `/app/pdf-renamer`.

## Validation rules

- PDF format only
- An even number of pages (up to 100)
- Maximum source PDF size of 50 MB
- Users can correct all extracted values before download
- Consecutive pages are paired: 1–2, 3–4, 5–6, and so on
- OCR runs on only the current two-page pair
- **Download & next** downloads that pair and advances automatically
- **Skip & next** continues without downloading the current pair
- Progress shows downloaded, skipped, and remaining pairs
- The review step keeps Page 1 on the left and Page 2 on the right in separate,
  independently scrollable preview frames
- Download stays disabled until SI, DR, and PO values are present

## Supported layout

The OCR and extraction rules are tuned for the supplied Tic & Terry two-page
Charge Invoice and Delivery Receipt layout. The PO is cross-checked across both
pages when OCR finds it twice. If the general OCR pass misses the red Charge
Invoice serial, the server performs a second high-resolution pass over its
expected top-right document area.

For normal scans, OCR is limited to the document header at 180 DPI and skips
orientation classification because the supported two-page layout is upright.
This substantially reduces processing time while preserving SI, DR, and PO
accuracy. The larger 320 DPI pass runs only when the Charge Invoice serial is
still missing.
