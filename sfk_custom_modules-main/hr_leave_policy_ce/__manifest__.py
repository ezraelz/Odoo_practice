{
    "name": "HR Leave Policy CE",
    "version": "18.0.1.0.0",
    "summary": "Contract-based annual leave, probation, split rules, and statutory leave policies",
    "category": "Human Resources",
    "author": "Besufikad",
    "license": "LGPL-3",
    "depends": ["hr", "hr_contract", "hr_holidays"],
    "data": [
        "security/ir.model.access.csv",
        "security/hr_leave_policy_security.xml",
        "data/hr_leave_type_data.xml",
        "data/hr_leave_accrual_data.xml",
        "data/ir_cron_data.xml",
        "views/hr_employee_views.xml",
        "views/hr_leave_type_views.xml",
        "views/hr_leave_views.xml",
        "views/hr_leave_entitlement_views.xml"
    ],
    "installable": True,
    "application": False,
}
