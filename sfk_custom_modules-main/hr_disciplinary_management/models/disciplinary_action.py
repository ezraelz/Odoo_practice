from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date


class HRDisciplinaryAction(models.Model):
    _name = "hr.disciplinary.action"
    _description = "Disciplinary Action"
    _inherit = ["mail.thread"]
    _order = "effective_date desc"

    case_id = fields.Many2one("hr.disciplinary.case", required=True, ondelete="cascade")
    employee_id = fields.Many2one(related="case_id.employee_id", store=True, readonly=True)

    # ─────────────────────────────────────────────
    # Action Type & Stage
    # ─────────────────────────────────────────────
    action_type = fields.Selection([
        ('verbal_warning', 'Verbal Warning'),
        ('written_warning', 'Written Warning'),
        ('final_warning', 'Final Warning'),
        ('suspension', 'Suspension'),
        ('demotion', 'Demotion'),
        ('fine', 'Fine'),
        ('termination', 'Termination'),
    ], required=True, tracking=True)

    stage = fields.Selection([
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved / Active'),
        ('served', 'Served to Employee'),
        ('completed', 'Completed'),
        ('revoked', 'Revoked'),
        ('appealed', 'Under Appeal'),
    ], default='draft', tracking=True, string="Stage")

    # ─────────────────────────────────────────────
    # Details
    # ─────────────────────────────────────────────
    justification = fields.Text(required=True)
    approval_user_id = fields.Many2one("res.users", string="Approved By")
    approved_date = fields.Date(string="Approval Date")

    effective_date = fields.Date(required=True, default=fields.Date.today)

    # Expiry — only relevant for warnings/suspension
    has_expiry = fields.Boolean(
        string="Has Expiry Date?",
        default=False,
        help="Enable if this action expires after a set period (e.g. warning active for 6 months)"
    )
    expiry_date = fields.Date(
        string="Expiry Date",
        help="After this date the action is no longer active"
    )

    # Suspension specific
    suspension_days = fields.Integer(string="Suspension Duration (days)")
    suspension_with_pay = fields.Boolean(default=False, string="With Pay?")

    # Fine specific
    fine_amount = fields.Float(string="Fine Amount")
    fine_currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )

    # Termination specific
    notice_period_months = fields.Integer(
        string="Notice Period (months)",
        help="Art. 28: 1 month (<1yr service), 2 months (1-9 yrs), 3 months (>9 yrs)"
    )
    termination_type = fields.Selection([
        ('without_notice', 'Without Notice (Art. 27)'),
        ('with_notice', 'With Notice (Art. 28)'),
    ], string="Termination Type")

    # Notice delivery
    notice_served_date = fields.Date(string="Notice Served Date")
    notice_delivery_method = fields.Selection([
        ('personal', 'Personal Delivery with Signature'),
        ('refused', 'Refused - Witness Noted'),
        ('postal', 'Sent to Last Known Address'),
        ('notice_board', 'Posted on Notice Board (10 days)'),
    ], string="Notice Delivery Method")

    # ─────────────────────────────────────────────
    # Revocation
    # ─────────────────────────────────────────────
    revoke_reason = fields.Text()
    revoked_by = fields.Many2one("res.users", readonly=True)
    revoked_date = fields.Date(readonly=True)

    # ─────────────────────────────────────────────
    # Computed
    # ─────────────────────────────────────────────
    is_expired = fields.Boolean(
        compute="_compute_is_expired", store=True,
        string="Expired?"
    )
    is_active_warning = fields.Boolean(
        compute="_compute_is_active_warning", store=True
    )

    @api.depends("expiry_date", "has_expiry")
    def _compute_is_expired(self):
        today = date.today()
        for rec in self:
            if rec.has_expiry and rec.expiry_date:
                rec.is_expired = rec.expiry_date < today
            else:
                rec.is_expired = False

    @api.depends("stage", "is_expired", "action_type")
    def _compute_is_active_warning(self):
        warning_types = ('verbal_warning', 'written_warning', 'final_warning')
        for rec in self:
            rec.is_active_warning = (
                rec.action_type in warning_types
                and rec.stage in ('approved', 'served', 'completed')
                and not rec.is_expired
            )

    # ─────────────────────────────────────────────
    # Workflow Buttons
    # ─────────────────────────────────────────────
    def action_submit_for_approval(self):
        self.write({'stage': 'pending_approval'})
        self.message_post(body=_("Action submitted for approval."))

    def action_approve(self):
        self.write({
            'stage': 'approved',
            'approval_user_id': self.env.user.id,
            'approved_date': date.today(),
        })
        self.message_post(body=_("Action approved by %s.") % self.env.user.name)

    def action_mark_served(self):
        self.write({
            'stage': 'served',
            'notice_served_date': date.today(),
        })
        self.message_post(body=_("Notice served to employee on %s.") % date.today())

    def action_complete(self):
        self.write({'stage': 'completed'})
        self.message_post(body=_("Action marked as completed."))

    def action_revoke(self):
        if not self.revoke_reason:
            raise ValidationError("Please provide a revocation reason before revoking.")
        self.write({
            'stage': 'revoked',
            'revoked_by': self.env.user.id,
            'revoked_date': date.today(),
        })
        self.message_post(body=_("Action revoked. Reason: %s") % self.revoke_reason)

    def action_mark_appealed(self):
        self.write({'stage': 'appealed'})

    # Auto compute notice period from employee service length
    @api.onchange('action_type', 'case_id')
    def _onchange_compute_notice_period(self):
        if self.action_type == 'termination' and self.case_id.employee_id:
            employee = self.case_id.employee_id
            if employee.first_contract_date:
                years = (date.today() - employee.first_contract_date).days / 365
                if years < 1:
                    self.notice_period_months = 1
                elif years <= 9:
                    self.notice_period_months = 2
                else:
                    self.notice_period_months = 3

    @api.onchange('has_expiry')
    def _onchange_has_expiry(self):
        if not self.has_expiry:
            self.expiry_date = False

    @api.constrains('action_type', 'termination_type')
    def _check_termination_fields(self):
        for rec in self:
            if rec.action_type == 'termination' and not rec.termination_type:
                raise ValidationError(
                    "Please specify whether termination is with notice (Art. 28) "
                    "or without notice (Art. 27)."
                )

    @api.constrains('has_expiry', 'expiry_date', 'effective_date')
    def _check_expiry_date(self):
        for rec in self:
            if rec.has_expiry and not rec.expiry_date:
                raise ValidationError("Please set an expiry date.")
            if rec.has_expiry and rec.expiry_date and rec.expiry_date <= rec.effective_date:
                raise ValidationError("Expiry date must be after the effective date.")