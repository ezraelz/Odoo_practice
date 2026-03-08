{
    "name": "Project Management",
    "version": "1.0",
    "author": 'Esrael Zerihun',
    "summary": "Manage projects and their lifecycle",
    "category": "Projects",
    "website": "https://www.odoo.com/app/projects",
    "depends": ["base", "contacts", "mail"],
    "data": [
        'security/ir.model.access.csv',
        'security/security.xml',
        'security/ir_rule.xml',
        'data/essential_data.xml',
        'views/project_views.xml',
        'views/project_task_view.xml',
    ],
    'demo': [                          # Demo data - only loads in demo databases
        'data/demo_data.xml',
    ],
    "application": True,
    "license": 'LGPL-3',
    "auto_install": False,
    "installable": True,
}