# python
from odoo import models, fields, api, exceptions

class SfkRoom(models.Model):
    _name = "sfk.room"
    _description = "Room"

    name = fields.Char(required=True)
    capacity = fields.Integer(default=20)
    company_id = fields.Many2one('res.company', string='Branch/Center', default=lambda self: self.env.company)

    @api.constrains('capacity')
    def _check_capacity_positive(self):
        for r in self:
            if r.capacity <= 0:
                raise exceptions.ValidationError("Room capacity must be positive.")
