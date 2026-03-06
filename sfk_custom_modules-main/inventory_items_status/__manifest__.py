# -*- coding: utf-8 -*-
{
    'name': 'Inventory Items Status',
    'version': '1.0',
    'summary': 'Brief description of the module',
    'description': '''
        Detailed description of the module
    ''',
    'category': 'Inventory',
    'author': 'Besufikad',
    'company': 'SFK',
    'depends': ['base','stock', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}