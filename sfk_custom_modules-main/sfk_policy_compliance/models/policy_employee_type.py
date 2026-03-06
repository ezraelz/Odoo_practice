from odoo import fields, models


class PolicyEmployeeType(models.Model):
    _name = 'policy.employee.type'
    _description = 'Policy Employee Type'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('policy_employee_type_code_uniq', 'unique(code)', 'Employee type code must be unique.'),
    ]
