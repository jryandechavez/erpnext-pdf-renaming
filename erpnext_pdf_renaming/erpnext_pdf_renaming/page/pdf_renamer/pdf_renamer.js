frappe.pages["pdf-renamer"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("PDF Renamer"),
    single_column: true,
  });

  const stylesheetId = "erpnext-pdf-renamer-styles";
  const stylesheetUrl = "/assets/erpnext_pdf_renaming/css/pdf_renamer.css?v=0.4.3";
  let link = document.getElementById(stylesheetId);
  if (!link) {
    link = document.createElement("link");
    link.id = stylesheetId;
    link.rel = "stylesheet";
    document.head.appendChild(link);
  }
  if (link.getAttribute("href") !== stylesheetUrl) link.href = stylesheetUrl;

  new ERPNextPDFRenamer(page.body);
};

class ERPNextPDFRenamer {
  constructor(container) {
    this.container = container;
    this.file = null;
    this.previews = [];
    this.values = { si: "", dr: "", po: "" };
    this.pdfjs = null;
    this.render();
    this.bind_events();
  }

  render() {
    this.container.html(`
      <div class="pdf-renamer-app">
        <section class="renamer-hero">
          <div class="renamer-eyebrow">PRIVATE PDF TOOL</div>
          <h1>Rename invoices. <em>Keep files private.</em></h1>
          <p>Upload a two-page PDF, extract the Charge Invoice, Delivery Receipt, and PO numbers, then download it with the correct name.</p>
        </section>

        <section class="renamer-card">
          <div class="renamer-steps" aria-label="Progress">
            <div class="renamer-step active" data-step="1"><b>1</b><span>Choose PDF</span></div><i></i>
            <div class="renamer-step" data-step="2"><b>2</b><span>Read numbers</span></div><i></i>
            <div class="renamer-step" data-step="3"><b>3</b><span>Review & download</span></div>
          </div>

          <div class="renamer-view" data-view="upload">
            <div class="renamer-dropzone" tabindex="0" role="button" aria-label="Choose a two-page PDF">
              <input type="file" accept="application/pdf,.pdf" hidden>
              <div class="renamer-file-icon"><span>PDF</span></div>
              <h2>Drop your two-page PDF here</h2>
              <p>or choose a file from your computer</p>
              <button class="btn btn-default renamer-choose" type="button">Choose PDF</button>
              <small>PDF only · exactly 2 pages · maximum 15 MB</small>
            </div>
            <div class="renamer-alert renamer-error hidden" role="alert"></div>
            <button class="btn btn-primary renamer-process hidden" type="button">Read document numbers →</button>
          </div>

          <div class="renamer-view hidden" data-view="processing" aria-live="polite">
            <div class="renamer-processing">
              <div class="renamer-scan-document"><div class="renamer-scan-line"></div><span>PDF</span><i></i><i></i><i></i></div>
              <h2>Reading your document</h2>
              <p class="renamer-status">Opening your PDF…</p>
              <div class="renamer-progress"><span></span></div>
              <small><b>0</b>% · No permanent server copy is created</small>
            </div>
          </div>

          <div class="renamer-view hidden" data-view="review">
            <div class="renamer-alert renamer-result" role="status"></div>
            <div class="renamer-review-grid">
              <div class="renamer-preview">
                <div><strong>Document preview</strong><span>Review each page independently</span></div>
                <div class="renamer-preview-pages">
                  <figure><figcaption>Page 1</figcaption><div><img data-preview="0" alt="Preview of uploaded PDF page 1"></div></figure>
                  <figure><figcaption>Page 2</figcaption><div><img data-preview="1" alt="Preview of uploaded PDF page 2"></div></figure>
                </div>
              </div>
              <div class="renamer-review-form">
                <div class="renamer-fields">
                  <label>Charge Invoice number<input data-field="si" inputmode="numeric" placeholder="e.g. 65532"></label>
                  <label>Delivery Receipt number<input data-field="dr" inputmode="numeric" placeholder="e.g. 66584"></label>
                  <label>PO number<input data-field="po" placeholder="e.g. POR00116530"></label>
                </div>
                <div class="renamer-filename"><span>NEW FILENAME</span><strong></strong></div>
                <div class="renamer-actions">
                  <button class="btn btn-default renamer-reset" type="button">Start over</button>
                  <button class="btn btn-primary renamer-download" type="button" disabled>Download renamed PDF ↓</button>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="renamer-trust">
          <div><b>01</b><span><strong>Nothing is retained</strong>The temporary upload is discarded after OCR.</span></div>
          <div><b>02</b><span><strong>You stay in control</strong>Review every value before download.</span></div>
          <div><b>03</b><span><strong>No Frappe File</strong>No attachment or database record is created.</span></div>
        </section>
      </div>
    `);
  }

  bind_events() {
    const root = this.container[0];
    this.root = root;
    this.input = root.querySelector('input[type="file"]');
    this.dropzone = root.querySelector(".renamer-dropzone");
    root.querySelector(".renamer-choose").addEventListener("click", () => this.input.click());
    this.dropzone.addEventListener("click", (event) => {
      if (!event.target.closest("button")) this.input.click();
    });
    this.dropzone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") this.input.click();
    });
    this.input.addEventListener("change", () => this.select_file(this.input.files[0]));
    ["dragenter", "dragover"].forEach((name) => this.dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      this.dropzone.classList.add("is-dragging");
    }));
    ["dragleave", "drop"].forEach((name) => this.dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      this.dropzone.classList.remove("is-dragging");
    }));
    this.dropzone.addEventListener("drop", (event) => this.select_file(event.dataTransfer.files[0]));
    root.querySelector(".renamer-process").addEventListener("click", () => this.process());
    root.querySelector(".renamer-reset").addEventListener("click", () => this.reset());
    root.querySelector(".renamer-download").addEventListener("click", () => this.download());
    root.querySelectorAll("[data-field]").forEach((input) => input.addEventListener("input", () => {
      const field = input.dataset.field;
      const cleaned = input.value.toUpperCase().replace(field === "po" ? /[^A-Z0-9]/g : /\D/g, "");
      input.value = cleaned.slice(0, field === "po" ? 24 : 12);
      this.values[field] = input.value;
      this.refresh_filename();
    }));
  }

  select_file(file) {
    this.hide_error();
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) return this.show_error(__("Please choose a PDF file."));
    if (file.size > 15 * 1024 * 1024) return this.show_error(__("The PDF must be 15 MB or smaller."));
    this.file = file;
    this.dropzone.querySelector("h2").textContent = file.name;
    this.dropzone.querySelector("p").textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB · Ready to process`;
    this.dropzone.querySelector(".renamer-choose").textContent = __("Choose another file");
    this.root.querySelector(".renamer-process").classList.remove("hidden");
  }

  async process() {
    if (!this.file) return;
    this.show_view("processing");
    this.set_step(2);
    this.set_progress(15, __("Uploading the PDF temporarily…"));
    try {
      const form = new FormData();
      form.append("file", this.file, this.file.name);
      const response = await this.upload_pdf(form);
      this.set_progress(85, __("Checking the extracted numbers…"));
      const payload = response.payload;
      if (response.status < 200 || response.status >= 300 || payload.exc) {
        let message = payload.message || __("The PDF could not be processed.");
        if (payload._server_messages) {
          try {
            const messages = JSON.parse(payload._server_messages).map((item) => JSON.parse(item).message);
            message = messages.filter(Boolean).join(" ") || message;
          } catch (_) {}
        }
        throw new Error(message);
      }
      this.values = payload.message.values;
      this.previews = payload.message.previews || [];
      this.set_progress(100, __("Temporary upload discarded."));
      this.show_review();
    } catch (error) {
      this.show_view("upload");
      this.set_step(1);
      this.show_error(error.message || __("The PDF could not be processed."));
    }
  }

  upload_pdf(form) {
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open("POST", "/api/method/erpnext_pdf_renaming.api.process_pdf", true);
      if (typeof frappe.csrf_token === "string" && frappe.csrf_token) {
        request.setRequestHeader("X-Frappe-CSRF-Token", frappe.csrf_token);
      }
      request.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = 15 + Math.round((event.loaded / event.total) * 25);
          this.set_progress(percent, __("Uploading the PDF temporarily…"));
        }
      };
      request.upload.onload = () => {
        this.set_progress(45, __("Reading the two document headers…"));
      };
      request.onerror = () => reject(new Error(__("The temporary upload could not reach ERPNext.")));
      request.onload = () => {
        let payload;
        try {
          payload = JSON.parse(request.responseText || "{}");
        } catch (_) {
          reject(new Error(__("ERPNext returned an unreadable response.")));
          return;
        }
        resolve({ status: request.status, payload });
      };
      request.send(form);
    });
  }

  async render_ocr_crop(page) {
    const viewport = page.getViewport({ scale: 2.5 });
    const source = document.createElement("canvas");
    source.width = Math.ceil(viewport.width);
    source.height = Math.ceil(viewport.height);
    const context = source.getContext("2d", { willReadFrequently: true });
    await page.render({ canvas: source, canvasContext: context, viewport }).promise;
    const crop = document.createElement("canvas");
    const x = Math.floor(source.width * 0.1);
    const y = Math.floor(source.height * 0.08);
    crop.width = Math.floor(source.width * 0.8);
    crop.height = Math.floor(source.height * 0.48);
    const cropContext = crop.getContext("2d", { willReadFrequently: true });
    cropContext.drawImage(source, x, y, crop.width, crop.height, 0, 0, crop.width, crop.height);
    const image = cropContext.getImageData(0, 0, crop.width, crop.height);
    for (let index = 0; index < image.data.length; index += 4) {
      const luminance = 0.299 * image.data[index] + 0.587 * image.data[index + 1] + 0.114 * image.data[index + 2];
      const value = luminance < 224 ? 0 : 255;
      image.data[index] = value;
      image.data[index + 1] = value;
      image.data[index + 2] = value;
    }
    cropContext.putImageData(image, 0, 0);
    return crop;
  }

  extract_values(pageTexts) {
    const pages = pageTexts.map((text) => text.toUpperCase().replace(/[|]/g, "I").replace(/\s+/g, " ").trim());
    const findNumber = (text, label) => {
      const match = label.exec(text);
      if (!match) return "";
      const nearby = text.slice(match.index + match[0].length, match.index + match[0].length + 100);
      const marked = nearby.match(/N[O0E°º.,]*\s*[,.:]*\s*([0-9]{4,10})/);
      if (marked) return marked[1];
      return nearby.match(/(?:^|\s)([0-9]{4,6})(?:\s|$)/)?.[1] || "";
    };
    const findPO = (text) => {
      const match = text.match(/\bP[O0]\s*[:.-]?\s*(P[O0]R\s*[0-9ODIL]{6,14})\b/) || text.match(/\b(P[O0]R\s*[0-9ODIL]{6,14})\b/);
      if (!match) return "";
      const raw = match[1].replace(/\s/g, "").replace(/^P0R/, "POR");
      return raw.slice(0, 3) + raw.slice(3).replace(/[OD]/g, "0").replace(/[IL]/g, "1");
    };
    let si = "";
    let dr = "";
    const purchaseOrders = [];
    pages.forEach((page) => {
      si ||= findNumber(page, /CHARGE.{0,120}?INVOICE/);
      dr ||= findNumber(page, /DELIVERY.{0,120}?RECEIPT/);
      const po = findPO(page);
      if (po) purchaseOrders.push(po);
    });
    const po = purchaseOrders.sort((a, b) => purchaseOrders.filter((item) => item === b).length - purchaseOrders.filter((item) => item === a).length)[0] || "";
    return { si, dr, po };
  }

  show_review() {
    this.show_view("review");
    this.set_step(3);
    this.root.querySelectorAll("[data-preview]").forEach((image) => {
      image.src = this.previews[Number(image.dataset.preview)] || "";
    });
    Object.entries(this.values).forEach(([field, value]) => {
      const input = this.root.querySelector(`[data-field="${field}"]`);
      input.value = value;
      input.classList.toggle("is-missing", !value);
    });
    const complete = Object.values(this.values).every(Boolean);
    const result = this.root.querySelector(".renamer-result");
    result.className = `renamer-alert renamer-result ${complete ? "is-success" : "is-warning"}`;
    result.textContent = complete
      ? __("Review the extracted values, then download your renamed PDF.")
      : __("One or more values need your help. Complete the highlighted fields before downloading.");
    this.refresh_filename();
  }

  refresh_filename() {
    const complete = Object.values(this.values).every(Boolean);
    const filename = complete ? `SI_${this.values.si}_AND_DR_${this.values.dr}_PO_${this.values.po}.pdf` : "";
    this.root.querySelector(".renamer-filename strong").textContent = filename || __("Complete all fields to generate the filename");
    this.root.querySelector(".renamer-download").disabled = !filename;
  }

  download() {
    if (!this.file || !Object.values(this.values).every(Boolean)) return;
    const name = `SI_${this.values.si}_AND_DR_${this.values.dr}_PO_${this.values.po}.pdf`;
    const url = URL.createObjectURL(this.file);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  reset() {
    this.previews = [];
    this.file = null;
    this.values = { si: "", dr: "", po: "" };
    this.input.value = "";
    this.dropzone.querySelector("h2").textContent = __("Drop your two-page PDF here");
    this.dropzone.querySelector("p").textContent = __("or choose a file from your computer");
    this.dropzone.querySelector(".renamer-choose").textContent = __("Choose PDF");
    this.root.querySelector(".renamer-process").classList.add("hidden");
    this.hide_error();
    this.show_view("upload");
    this.set_step(1);
  }

  set_progress(percent, status) {
    this.root.querySelector(".renamer-progress span").style.width = `${percent}%`;
    this.root.querySelector(".renamer-processing small b").textContent = percent;
    this.root.querySelector(".renamer-status").textContent = status;
  }

  show_view(name) {
    this.root.querySelectorAll(".renamer-view").forEach((view) => view.classList.toggle("hidden", view.dataset.view !== name));
  }

  set_step(number) {
    this.root.querySelectorAll(".renamer-step").forEach((step) => {
      const value = Number(step.dataset.step);
      step.classList.toggle("active", value === number);
      step.classList.toggle("done", value < number);
    });
  }

  show_error(message) {
    const alert = this.root.querySelector(".renamer-error");
    alert.textContent = message;
    alert.classList.remove("hidden");
  }

  hide_error() {
    const alert = this.root.querySelector(".renamer-error");
    alert.textContent = "";
    alert.classList.add("hidden");
  }
}
