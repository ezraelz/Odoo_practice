{
    "name": "Projects",
    "version": "1.0",
    "author": "Esrael Zerihun",
    "summary": "Manage projects and their lifecycle",
    "depends": ["project"],
    "data": [
        "security/ir.model.access.csv",  # Model access rights
        # "views/project_views.xml",
        "views/project_task_view.xml"
    ],
    "installable": True,
    'application': True,
}