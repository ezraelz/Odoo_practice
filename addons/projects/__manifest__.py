{
    "name": "Project Management",
    "version": "1.0",
    "author": 'Esrael Zerihun',
    "summary": "Manage projects and their lifecycle",
    "category": "Projects",
    "website": "https://www.odoo.com/app/projects",
    "depends": ["base", "contacts"],
    "data": [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/project_views.xml',
    ],
    "application": True,
    "license": 'LGPL-3',
    "auto_install": False,
    "installable": True,
}