from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class HRDisciplinaryAppeal(models.Model):
    _name = "hr.disciplinary.appeal"
    _description = "Disciplinary Appeal"
    _inherit = ["mail.thread"]
    _order = "submission_date desc"

    case_id = fields.Many2one("hr.disciplinary.case", required=True, ondelete="cascade")
    employee_id = fields.Many2one(related="case_id.employee_id", store=True, readonly=True)
    action_id = fields.Many2one(
        "hr.disciplinary.action", string="Action Being Appealed",
        domain="[('case_id', '=', case_id)]"
    )

    # ─────────────────────────────────────────────
    # Appeal Details
    # ─────────────────────────────────────────────
    submission_date = fields.Date(required=True, default=fields.Date.today)
    grounds = fields.Text(required=True, string="Grounds for Appeal")

    # Ethiopian law: employee has 15 working days from incident
    employee_deadline = fields.Date(
        string="Employee Filing Deadline (15 WD)",
        compute="_compute_employee_deadline", store=True
    )
    is_late_filing = fields.Boolean(compute="_compute_is_late_filing", store=True)

    # ─────────────────────────────────────────────
    # Appeal Stage
    # ─────────────────────────────────────────────
    stage = fields.Selection([
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('hearing_scheduled', 'Hearing Scheduled'),
        ('decided', 'Decided'),
        ('closed', 'Closed'),
    ], default='submitted', tracking=True)

    hearing_date = fields.Date(string="Hearing Date")
    hearing_notes = fields.Text(string="Hearing Notes")

    # ─────────────────────────────────────────────
    # Decision
    # ─────────────────────────────────────────────
    decision = fields.Text(string="Appeal Decision / Reasoning")
    outcome = fields.Selection([
        ('upheld', 'Appeal Upheld - Action Overturned'),
        ('partially_upheld', 'Partially Upheld - Action Modified'),
        ('dismissed', 'Appeal Dismissed - Action Stands'),
    ], tracking=True)
    approved_by = fields.Many2one("res.users", string="Decided By")
    decision_date = fields.Date(string="Decision Date")

    @api.depends('case_id.incident_date')
    def _compute_employee_deadline(self):
        for rec in self:
            if rec.case_id.incident_date:
                rec.employee_deadline = rec.case_id.incident_date + timedelta(days=21)
            else:
                rec.employee_deadline = False

    @api.depends('submission_date', 'employee_deadline')
    def _compute_is_late_filing(self):
        for rec in self:
            rec.is_late_filing = bool(
                rec.submission_date and rec.employee_deadline
                and rec.submission_date > rec.employee_deadline
            )

    def action_start_review(self):
        self.write({'stage': 'under_review'})
        self.message_post(body=_("Appeal is under review."))

    def action_schedule_hearing(self):
        if not self.hearing_date:
            raise ValidationError("Please set a hearing date before scheduling.")
        self.write({'stage': 'hearing_scheduled'})
        self.message_post(body=_("Hearing scheduled for %s.") % self.hearing_date)

    def action_decide(self):
        if not self.outcome:
            raise ValidationError(
                "Please select an Outcome (Upheld / Partially Upheld / Dismissed) before recording the decision."
            )
        if not self.decision:
            raise ValidationError(
                "Please enter the Decision reasoning in the Decision field before recording."
            )
        self.write({
            'stage': 'decided',
            'approved_by': self.env.user.id,
            'decision_date': date.today(),
        })
        # Update the linked action and case based on outcome
        if self.action_id:
            if self.outcome == 'upheld':
                self.action_id.write({'stage': 'revoked', 'revoked_by': self.env.user.id, 'revoked_date': date.today()})
                self.case_id.write({'state': 'closure'})
            elif self.outcome == 'partially_upheld':
                self.action_id.write({'stage': 'approved'})
        self.message_post(body=_(
            "Appeal decided: %s"
        ) % dict(self._fields['outcome'].selection).get(self.outcome))

    def action_close(self):
        self.write({'stage': 'closed'})
        if self.case_id.state == 'appeal':
            self.case_id.write({'state': 'closure'})