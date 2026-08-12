import frappe


MODULE_NAME = "ERPNext PDF Renaming"
APP_NAME = "erpnext_pdf_renaming"


def ensure_module_def():
    """Repair sites where the app is registered but its Module Def is missing."""
    if frappe.db.exists("Module Def", MODULE_NAME):
        return

    frappe.get_doc(
        {
            "doctype": "Module Def",
            "module_name": MODULE_NAME,
            "app_name": APP_NAME,
            "custom": 0,
        }
    ).insert(ignore_permissions=True)
    frappe.db.commit()


def after_install():
    ensure_module_def()
