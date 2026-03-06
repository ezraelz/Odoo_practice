from odoo import models, fields, api
from odoo.exceptions import UserError

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
    is_locked = fields.Boolean(default=False)

    def write(self, vals):
        for record in self:
            if record.is_locked:
                # allow only creator or superuser (id=1)
                if self.env.uid not in (record.create_uid.id, 1):
                    raise UserError("This equipment record is locked and cannot be modified.")
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.is_locked and self.env.uid not in (record.create_uid.id, 1):
                raise UserError("This equipment record is locked and cannot be deleted.")
        return super().unlink()
    