# -*- coding: utf-8 -*-
{
    'name': 'Sfk Operation',
    'version': '1.0',
    'summary': 'Brief description of the module',
    'description': '''
      The STEM Operations module is a custom Odoo 18 module that manages the operational delivery of coaching programs at STEM for Kids Ethiopia. 
      It provides a structured workflow to create and manage programs, define permanent class schedules, 
      assign instructors per session, enroll students (center-based), 
      track attendance, and manage rooms, while enforcing conflict controls and audit rules.
    ''',
    'category': 'Operations',
    'author': 'Besufikad',
    'company': 'Steam for kids',
    'website': 'https://www.odoo.com',
    'depends': ['base', 'mail', 'web', 'calendar', 'hr'],
    'data': [
        'security/sfk_groups.xml',
        'security/ir.model.access.csv',
        'security/sfk_security_rules.xml',
        'views/course_views.xml',
        'views/term_views.xml',
        'views/student_views.xml',
        'views/session_views.xml',
        'views/permanent_schedule_views.xml',
        'views/attendance_views.xml',
        'views/room_views.xml',
        'views/program_views.xml',
        'views/menu_views.xml',
        'views/quality_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
