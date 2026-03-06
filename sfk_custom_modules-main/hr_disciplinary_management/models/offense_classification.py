from odoo import models, fields, api
from odoo.exceptions import UserError


class HROffenseClassification(models.Model):
    _name = "hr.offense.classification"
    _description = "Offense Classification"
    _order = "severity_level, name"

    name = fields.Char(required=True)
    description = fields.Html()

    severity_level = fields.Selection([
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('serious', 'Serious'),
        ('gross', 'Gross Misconduct'),
    ], required=True, default='minor',
        help="Minor → Verbal warning; Moderate → Written warning; Serious → Final warning; Gross → Termination")

    approval_level = fields.Selection([
        ('hr', 'HR Officer'),
        ('manager', 'HR Manager'),
        ('executive', 'Executive Management'),
    ], required=True, default='hr')

    investigation_required = fields.Boolean(default=True)

    is_immediate_dismissal = fields.Boolean(
        string="Immediate Dismissal (Art. 27)",
        help="Offenses under Article 27 that allow termination without notice"
    )

    default_action_type = fields.Selection([
        ('verbal_warning', 'Verbal Warning'),
        ('written_warning', 'Written Warning'),
        ('final_warning', 'Final Warning'),
        ('suspension', 'Suspension'),
        ('termination', 'Termination'),
    ], string="Default Action", compute="_compute_default_action", store=True)

    active = fields.Boolean(default=True)
    created_by = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user)
    updated_by = fields.Many2one('res.users', readonly=True)

    @api.depends('severity_level', 'is_immediate_dismissal')
    def _compute_default_action(self):
        mapping = {
            'minor': 'verbal_warning',
            'moderate': 'written_warning',
            'serious': 'final_warning',
            'gross': 'termination',
        }
        for rec in self:
            if rec.is_immediate_dismissal:
                rec.default_action_type = 'termination'
            else:
                rec.default_action_type = mapping.get(rec.severity_level, 'verbal_warning')

    @api.model
    def create(self, vals):
        # env.su is True during module install/upgrade — allow it
        if not self.env.su and not self.env.user.has_group(
                'hr_disciplinary_management.group_hr_disciplinary_manager'):
            raise UserError("Only HR Managers can create offense classifications.")
        return super().create(vals)

    def write(self, vals):
        if not self.env.su and not self.env.user.has_group(
                'hr_disciplinary_management.group_hr_disciplinary_manager'):
            raise UserError("Only HR Managers can update offense classifications.")
        vals['updated_by'] = self.env.user.id
        return super().write(vals)