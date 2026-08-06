# ERPNext PDF Renaming

A Frappe/ERPNext v15 custom app that adds a **PDF Renamer** Desk page. Users select a two-page PDF, the browser extracts the Charge Invoice, Delivery Receipt, and PO numbers, and downloads the original PDF with a standardized filename:

```text
SI_65532_AND_DR_66584_PO_POR00116530.pdf
```

The GitHub repository is named `erpnext-pdf-renaming`, but the Frappe/Python app
name is `erpnext_pdf_renaming`. Always use the underscore name with
`install-app`, `build --app`, and `list-apps`.

## Privacy design

All PDF rendering, OCR, review, and renaming happen in the browser. The app does not create a Frappe `File`, call a PDF-processing server endpoint, or retain document content. Reloading or closing the Desk page clears the selected PDF from memory.

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
`sites/apps.txt` entry or reinstalling the app on the site.

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
bench --site your-site.example migrate
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
bench --site your-site.example migrate
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
