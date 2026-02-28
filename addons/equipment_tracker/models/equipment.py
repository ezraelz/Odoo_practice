from odoo import models, fields

class EquipmentTracker(models.Model):
    _name = 'equipment.tracker'
    _description = 'Customer Equipment'

    name = fields.Char(required=True)
    serial_number = fields.Char()
    customer_id = fields.Many2one('res.partner', string='Customer')
    purchase_date = fields.Date()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('returned', 'Returned')
    ], default='draft')