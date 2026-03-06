from odoo import models, fields, api
from datetime import date


class HRDisciplinaryInvestigation(models.Model):
    _name = "hr.disciplinary.investigation"
    _description = "Disciplinary Investigation"
    _order = "start_date desc"

    case_id = fields.Many2one("hr.disciplinary.case", required=True, ondelete="cascade")
    employee_id = fields.Many2one(related="case_id.employee_id", store=True, readonly=True)

    investigating_officer_id = fields.Many2one("hr.employee", required=True, string="Investigating Officer")
    start_date = fields.Date(required=True, default=fields.Date.today)
    end_date = fields.Date()
    findings = fields.Text()
    witnesses = fields.Text(string="Witnesses / Evidence")

    state = fields.Selection([
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('suspended', 'Suspended'),
    ], default='ongoing')

    is_overdue = fields.Boolean(compute="_compute_is_overdue", store=True)

    @api.depends("end_date", "state")
    def _compute_is_overdue(self):
        today = date.today()
        for rec in self:
            rec.is_overdue = bool(
                rec.end_date and rec.end_date < today and rec.state == 'ongoing'
            )

    def action_complete(self):
        self.write({'state': 'completed'})