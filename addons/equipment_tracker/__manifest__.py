{
    "name": "Equipment Tracker",
    "version": "1.0",
    "summary": "Track customer equipment",
    "category": "Operations",
    "depends": ["base", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/equipment_views.xml",
    ],
    "application": True,
    "installable": True,
}