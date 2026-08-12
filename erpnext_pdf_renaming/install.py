import frappe


MODULE_NAME = "ERPNext PDF Renaming"
APP_NAME = "erpnext_pdf_renaming"


def ensure_module_def():
    """Repair sites where the app is registered but its Module Def is missing."""
    from frappe.installer import add_module_defs

    add_module_defs(APP_NAME, ignore_if_duplicate=True)
    module = frappe.get_doc("Module Def", MODULE_NAME)
    if module.app_name != APP_NAME or module.custom:
        module.app_name = APP_NAME
        module.custom = 0
        module.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()
    return MODULE_NAME


def verify_installation():
    missing = []
    if not frappe.db.exists("Module Def", MODULE_NAME):
        missing.append(f"Module Def {MODULE_NAME}")
    if not frappe.db.exists("Page", "pdf-renamer"):
        missing.append("Page pdf-renamer")
    if missing:
        frappe.throw("Installation verification failed; missing: " + ", ".join(missing))
    return {"module": MODULE_NAME, "page": "pdf-renamer", "status": "ready"}


def after_install():
    ensure_module_def()
