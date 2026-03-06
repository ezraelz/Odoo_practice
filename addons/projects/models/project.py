from odoo import models, fields, api
from odoo.exceptions import UserError

class Project(models.Model):
    _name = 'project.project'
    _description = 'Project'

    name = fields.Char(required=True)
    description = fields.Text()
    customer_id = fields.Many2one('res.partner', string='Customer')
    start_date = fields.Date()
    end_date = fields.Date()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ], default='draft')
    is_locked = fields.Boolean(default=False)

    def write(self, vals):
        for record in self:
            if record.is_locked:
                # allow only creator or superuser (id=1)
                if self.env.uid not in (record.create_uid.id, 1):
                    raise UserError("This project record is locked and cannot be modified.")
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.is_locked and self.env.uid not in (record.create_uid.id, 1):
                raise UserError("This project record is locked and cannot be deleted.")
        return super().unlink()
    