{
    "name": "HR Disciplinary Management",
    "version": "18.0.2.0.0",
    "category": "Human Resources",
    "summary": "Ethiopian Labour Law Compliant Disciplinary Case Management (Proclamation No. 1156/2019)",
    "author": "Soez technologies",
    "depends": ["hr", "mail"],
    "data": [
        # 1. Groups first (referenced by security rules and CSV)
        "security/groups.xml",
        "security/security.xml",
        "security/ir.model.access.csv",

        # 2. Master data (sequences + demo offense classifications)
        "data/sequence.xml",

        # 3. Views (each file defines its own actions)
        "views/offense_views.xml",
        "views/case_views.xml",
        "views/action_views.xml",
        "views/appeal_views.xml",

        # 4. Menus last — all actions must exist before this loads
        "views/menu.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}