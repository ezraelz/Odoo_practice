{
    "name": "HR Complaint",
    "version": "18.0.1.0.0",
    "summary": "Private complaint workflow between employees and HR",
    "description": """
Allow employees to submit complaints securely and privately.
Track complaint lifecycle with HR responses and status notifications.
    """,
    "category": "Human Resources",
    "author": "Custom",
    "depends": ["hr", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "security/complaint_security.xml",
        "views/complaint_views.xml",
        "views/complaint_employee_views.xml",
        "views/complaint_manager_views.xml",
        "reports/complaint_report.xml",
        "views/menus/menu.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
