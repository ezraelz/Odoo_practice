{
    "name": "Equipment Tracker",
    "version": "1.0",
    "author": 'Esrael Zerihun',
    "summary": "Track customer equipment",
    "category": "Operations",
    "website": "https://www.odoo.com/app/equipment_tracker",
    "depends": ["base", "contacts"],
    "data": [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/equipment_views.xml',
    ],
    "application": True,
    "license": 'LGPL-3',
    "auto_install": False,
    "installable": True,
}