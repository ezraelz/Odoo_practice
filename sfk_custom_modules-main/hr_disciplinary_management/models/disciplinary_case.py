import base64
import subprocess
import tempfile
import os
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta


class HRDisciplinaryCase(models.Model):
    _name = "hr.disciplinary.case"
    _description = "Disciplinary Case"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "incident_date desc"

    # ─────────────────────────────────────────────
    # Identification
    # ─────────────────────────────────────────────
    name = fields.Char(default="New", readonly=True, copy=False, tracking=True, string="Case Reference")
    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    department_id = fields.Many2one(related="employee_id.department_id", store=True, readonly=True)
    position = fields.Char(related="employee_id.job_title", store=True, readonly=True)
    manager_id = fields.Many2one(related="employee_id.parent_id", store=True, readonly=True, string="Direct Manager")

    # ─────────────────────────────────────────────
    # Incident Details
    # ─────────────────────────────────────────────
    incident_date = fields.Date(required=True, tracking=True)
    reported_date = fields.Date(default=fields.Date.today, required=True)
    description = fields.Text(required=True, string="Incident Description")
    offense_classification_id = fields.Many2one("hr.offense.classification", required=True, tracking=True)
    severity_level = fields.Selection(related="offense_classification_id.severity_level", store=True, readonly=True)
    is_immediate_dismissal = fields.Boolean(related="offense_classification_id.is_immediate_dismissal", store=True, readonly=True)
    labour_law_article = fields.Selection([
        ('art_27', 'Article 27 - Termination Without Notice'),
        ('art_28', 'Article 28 - Termination With Notice'),
        ('progressive', 'Progressive Discipline'),
    ], string="Labour Law Basis", tracking=True)

    # ─────────────────────────────────────────────
    # Workflow State
    # ─────────────────────────────────────────────
    state = fields.Selection([
        ('notified',      'Notified'),
        ('show_cause',    'Show Cause'),
        ('investigation', 'Investigation'),
        ('hearing',       'Hearing'),
        ('decision',      'Decision'),
        ('appeal',        'Appeal'),
        ('closed',        'Closed'),
    ], default='notified', tracking=True, string="Stage")

    # ─────────────────────────────────────────────
    # Employee Acknowledgment
    # ─────────────────────────────────────────────
    acknowledgment_state = fields.Selection([
        ('pending',      'Awaiting Response'),
        ('acknowledged', 'Acknowledged'),
        ('contested',    'Contested'),
    ], default='pending', tracking=True, string="Employee Response")
    acknowledged_date = fields.Date(readonly=True)
    contest_reason = fields.Text(string="Contest Statement")
    contest_date = fields.Date(readonly=True)

    # ─────────────────────────────────────────────
    # Show Cause
    # ─────────────────────────────────────────────
    show_cause_issued_date = fields.Date()
    show_cause_deadline = fields.Date(string="Response Deadline")
    show_cause_response = fields.Text(string="Employee Written Response")
    show_cause_responded = fields.Boolean(default=False)

    # ─────────────────────────────────────────────
    # Hearing
    # ─────────────────────────────────────────────
    hearing_date = fields.Date()
    hearing_notes = fields.Text()
    hearing_officer_id = fields.Many2one("hr.employee", string="Presiding Officer")

    # ─────────────────────────────────────────────
    # Decision
    # ─────────────────────────────────────────────
    decision_date = fields.Date(readonly=True)
    decision_by = fields.Many2one("res.users", readonly=True, string="Decision By")
    decision_outcome = fields.Selection([
        ('cleared',         'Cleared / No Action'),
        ('verbal_warning',  'Verbal Warning'),
        ('written_warning', 'Written Warning'),
        ('final_warning',   'Final Warning'),
        ('suspension',      'Suspension'),
        ('demotion',        'Demotion'),
        ('termination',     'Termination'),
    ], tracking=True, string="Decision Outcome")
    decision_rationale = fields.Text(string="Decision Rationale")
    suspension_days = fields.Integer(string="Suspension Duration (days)")
    suspension_with_pay = fields.Boolean(string="With Pay?", default=False)
    termination_type = fields.Selection([
        ('without_notice', 'Without Notice (Art. 27)'),
        ('with_notice',    'With Notice (Art. 28)'),
    ], string="Termination Type")
    notice_period_months = fields.Integer(string="Notice Period (months)")
    warning_expiry_date = fields.Date(string="Warning Expiry Date")
    decision_served = fields.Boolean(default=False, tracking=True, string="Decision Served?")
    decision_served_date = fields.Date(string="Served On")
    decision_served_method = fields.Selection([
        ('personal',     'Personal Delivery with Signature'),
        ('refused',      'Refused — Witness Noted'),
        ('postal',       'Sent to Last Known Address'),
        ('notice_board', 'Posted on Notice Board (10 days)'),
    ], string="Delivery Method")

    # Generated letter
    decision_letter = fields.Binary(string="Decision Letter", attachment=True)
    decision_letter_filename = fields.Char(string="Letter Filename")
    decision_letter_generated = fields.Boolean(default=False, string="Letter Generated?")

    # ─────────────────────────────────────────────
    # Notice Delivery (Art. 14)
    # ─────────────────────────────────────────────
    notice_delivery_method = fields.Selection([
        ('personal',     'Personal Delivery with Signature'),
        ('refused',      'Refused — Witness Noted'),
        ('postal',       'Sent to Last Known Address'),
        ('notice_board', 'Posted on Notice Board (10 days)'),
    ], string="Initial Notice Delivery")
    notice_witness_id = fields.Many2one("res.users", string="Witness")
    notice_board_posted_date = fields.Date()
    notice_board_removal_date = fields.Date(compute="_compute_notice_board_removal", store=True)

    # ─────────────────────────────────────────────
    # Time Limits (Art. 18)
    # ─────────────────────────────────────────────
    employer_knowledge_date = fields.Date(string="Date Employer Became Aware")
    employer_deadline = fields.Date(compute="_compute_employer_deadline", store=True, string="Employer Action Deadline")
    is_time_barred = fields.Boolean(compute="_compute_is_time_barred", store=True)

    # ─────────────────────────────────────────────
    # Absence Tracking (Art. 27)
    # ─────────────────────────────────────────────
    unauthorized_absence_days = fields.Integer(string="Unauthorized Absence Days (last 6 months)")
    late_arrival_count = fields.Integer(string="Late Arrivals (last 6 months)")
    absence_warnings_issued = fields.Boolean(string="Written Warnings Issued for Each Absence?")

    # ─────────────────────────────────────────────
    # Related Records
    # ─────────────────────────────────────────────
    investigation_ids = fields.One2many("hr.disciplinary.investigation", "case_id", string="Investigations")
    appeal_ids = fields.One2many("hr.disciplinary.appeal", "case_id", string="Appeals")

    # ─────────────────────────────────────────────
    # Progressive Discipline
    # ─────────────────────────────────────────────
    prior_case_count = fields.Integer(compute="_compute_prior_cases", string="Prior Cases")
    verbal_warning_count = fields.Integer(compute="_compute_warning_counts")
    written_warning_count = fields.Integer(compute="_compute_warning_counts")
    final_warning_count = fields.Integer(compute="_compute_warning_counts")
    recommended_action = fields.Selection([
        ('verbal_warning',        'Verbal Warning'),
        ('written_warning',       'Written Warning'),
        ('final_warning',         'Final Warning'),
        ('suspension',            'Suspension'),
        ('termination_notice',    'Termination with Notice (Art. 28)'),
        ('termination_no_notice', 'Termination without Notice (Art. 27)'),
    ], compute="_compute_recommended_action", store=True, string="Recommended Action")

    # ─────────────────────────────────────────────
    # Closure
    # ─────────────────────────────────────────────
    closure_date = fields.Date()
    closure_summary = fields.Text()
    final_payment_due_date = fields.Date(compute="_compute_final_payment_due", store=True)
    final_payment_completed = fields.Boolean(default=False)
    employment_certificate_issued = fields.Boolean(default=False)
    severance_applicable = fields.Boolean(default=False)
    severance_amount = fields.Float()

    # ─────────────────────────────────────────────
    # Computed
    # ─────────────────────────────────────────────
    @api.depends('notice_board_posted_date')
    def _compute_notice_board_removal(self):
        for rec in self:
            rec.notice_board_removal_date = (
                rec.notice_board_posted_date + timedelta(days=10)
                if rec.notice_board_posted_date else False)

    @api.depends('employer_knowledge_date')
    def _compute_employer_deadline(self):
        for rec in self:
            rec.employer_deadline = (
                rec.employer_knowledge_date + timedelta(days=42)
                if rec.employer_knowledge_date else False)

    @api.depends('employer_deadline', 'state')
    def _compute_is_time_barred(self):
        today = date.today()
        open_states = ['notified', 'show_cause', 'investigation', 'hearing']
        for rec in self:
            rec.is_time_barred = bool(
                rec.employer_deadline and rec.employer_deadline < today
                and rec.state in open_states)

    @api.depends('closure_date', 'state')
    def _compute_final_payment_due(self):
        for rec in self:
            rec.final_payment_due_date = (
                rec.closure_date + timedelta(days=10)
                if rec.closure_date and rec.state == 'closed' else False)

    def _compute_prior_cases(self):
        for rec in self:
            rec.prior_case_count = self.search_count([
                ('employee_id', '=', rec.employee_id.id),
                ('id', '!=', rec.id),
                ('state', '=', 'closed'),
            ])

    def _compute_warning_counts(self):
        for rec in self:
            prior = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('id', '!=', rec.id),
                ('state', '=', 'closed'),
                ('decision_outcome', '!=', False),
            ])
            rec.verbal_warning_count = len(prior.filtered(lambda c: c.decision_outcome == 'verbal_warning'))
            rec.written_warning_count = len(prior.filtered(lambda c: c.decision_outcome == 'written_warning'))
            rec.final_warning_count = len(prior.filtered(lambda c: c.decision_outcome == 'final_warning'))

    @api.depends('severity_level', 'is_immediate_dismissal',
                 'verbal_warning_count', 'written_warning_count', 'final_warning_count',
                 'unauthorized_absence_days', 'late_arrival_count', 'absence_warnings_issued')
    def _compute_recommended_action(self):
        for rec in self:
            if rec.is_immediate_dismissal:
                rec.recommended_action = 'termination_no_notice'
            elif rec.unauthorized_absence_days >= 5 and rec.absence_warnings_issued:
                rec.recommended_action = 'termination_no_notice'
            elif rec.late_arrival_count >= 8 and rec.absence_warnings_issued:
                rec.recommended_action = 'termination_no_notice'
            elif rec.final_warning_count >= 1:
                rec.recommended_action = 'termination_notice'
            elif rec.written_warning_count >= 1:
                rec.recommended_action = 'final_warning'
            elif rec.verbal_warning_count >= 1:
                rec.recommended_action = 'written_warning'
            elif rec.severity_level == 'gross':
                rec.recommended_action = 'termination_no_notice'
            elif rec.severity_level == 'serious':
                rec.recommended_action = 'final_warning'
            elif rec.severity_level == 'moderate':
                rec.recommended_action = 'written_warning'
            else:
                rec.recommended_action = 'verbal_warning'

    # ─────────────────────────────────────────────
    # HR Workflow Actions
    # ─────────────────────────────────────────────
    def action_issue_show_cause(self):
        self.ensure_one()
        if self.is_time_barred:
            raise UserError("This case is time-barred (30 working-day limit exceeded, Article 18).")
        self.write({
            'state': 'show_cause',
            'show_cause_issued_date': date.today(),
            'show_cause_deadline': date.today() + timedelta(days=5),
        })
        self.message_post(body=_("Show Cause Notice issued. Employee must respond by <b>%s</b>.") % self.show_cause_deadline)

    def action_record_show_cause_response(self):
        self.ensure_one()
        if not self.show_cause_response:
            raise UserError("Please record the employee's written response before confirming.")
        self.write({'show_cause_responded': True})
        self.message_post(body=_("Employee show cause response recorded."))

    def action_start_investigation(self):
        self.ensure_one()
        if self.is_time_barred:
            raise UserError("This case is time-barred (30 working-day limit exceeded, Article 18).")
        self.write({'state': 'investigation'})
        self.message_post(body=_("Case moved to Investigation."))

    def action_schedule_hearing(self):
        self.ensure_one()
        if not self.hearing_date:
            raise UserError("Please set a Hearing Date before scheduling the hearing.")
        self.write({'state': 'hearing'})
        self.message_post(body=_("Disciplinary hearing scheduled for <b>%s</b>.") % self.hearing_date)

    def action_move_to_decision(self):
        self.ensure_one()
        self.write({'state': 'decision'})
        self.message_post(body=_("Case moved to Decision stage."))

    def action_record_decision(self):
        self.ensure_one()
        if not self.decision_outcome:
            raise UserError("Please select a Decision Outcome before recording.")
        if not self.decision_rationale:
            raise UserError("Please provide the Decision Rationale before recording.")
        if self.decision_outcome == 'termination' and not self.termination_type:
            raise UserError("Please specify the termination type (with or without notice).")
        self.write({
            'decision_date': date.today(),
            'decision_by': self.env.user.id,
        })
        self.message_post(body=_("Decision recorded by <b>%s</b>: <b>%s</b>") % (
            self.env.user.name,
            dict(self._fields['decision_outcome'].selection).get(self.decision_outcome)))

    def action_serve_decision(self):
        self.ensure_one()
        if not self.decision_outcome:
            raise UserError("Please record the decision before serving it.")
        if not self.decision_served_method:
            raise UserError("Please select the delivery method.")
        self.write({
            'decision_served': True,
            'decision_served_date': date.today(),
        })
        self.message_post(body=_("Decision served to employee on <b>%s</b>. Appeal window now open.") % date.today())

    def action_close_case(self):
        self.ensure_one()
        if not self.decision_outcome:
            raise UserError("A decision must be recorded before closing the case.")
        self.write({'state': 'closed', 'closure_date': date.today()})
        self.message_post(body=_("Case closed on %s.") % date.today())

    def action_open_appeal(self):
        self.ensure_one()
        if not self.decision_served:
            raise UserError("The decision must be served to the employee before an appeal can be filed.")
        if self.decision_outcome == 'cleared':
            raise UserError("The employee was cleared. There is no decision to appeal.")
        self.write({'state': 'appeal'})
        self.message_post(body=_("Case moved to Appeal stage."))

    # ─────────────────────────────────────────────
    # Employee Actions
    # ─────────────────────────────────────────────
    def action_employee_acknowledge(self):
        self.ensure_one()
        self.sudo().write({
            'acknowledgment_state': 'acknowledged',
            'acknowledged_date': date.today(),
        })
        self.message_post(body=_("Employee <b>%s</b> acknowledged receipt on %s.") % (
            self.employee_id.name, date.today()))

    def action_employee_contest(self):
        self.ensure_one()
        contest_text = self.sudo().contest_reason
        if not contest_text:
            raise UserError("Please write your contest statement before clicking 'Contest This Case'.")
        self.sudo().write({
            'acknowledgment_state': 'contested',
            'contest_date': date.today(),
        })
        self.message_post(body=_("Employee <b>%s</b> contested this case on %s.<br/><b>Statement:</b> %s") % (
            self.employee_id.name, date.today(), contest_text))

    # ─────────────────────────────────────────────
    # Decision Letter Generation
    # ─────────────────────────────────────────────
    def action_generate_decision_letter(self):
        self.ensure_one()
        if not self.decision_outcome:
            raise UserError("Please select the Decision Outcome before generating the letter.")
        if not self.decision_rationale:
            raise UserError("Please provide the Decision Rationale before generating the letter.")

        employee = self.employee_id
        company = self.env.company
        outcome_labels = {
            'cleared': 'Cleared / No Action', 'verbal_warning': 'Verbal Warning',
            'written_warning': 'Written Warning', 'final_warning': 'Final Warning',
            'suspension': 'Suspension', 'demotion': 'Demotion', 'termination': 'Termination',
        }
        outcome_label = outcome_labels.get(self.decision_outcome, self.decision_outcome)
        appeal_deadline = ""
        if self.incident_date:
            appeal_deadline = (self.incident_date + timedelta(days=21)).strftime("%B %d, %Y")
        warning_expiry = ""
        if self.warning_expiry_date:
            warning_expiry = self.warning_expiry_date.strftime("%B %d, %Y")

        data = {
            "org_name": company.name or "Stem for Kids Ethiopia",
            "org_address": company.street or "Addis Ababa, Ethiopia",
            "org_phone": company.phone or "",
            "org_email": company.email or "",
            "ref_number": self.name,
            "letter_date": date.today().strftime("%B %d, %Y"),
            "employee_name": employee.name,
            "employee_id": str(employee.barcode or employee.id or ""),
            "employee_position": employee.job_title or (employee.job_id.name if employee.job_id else "") or "",
            "employee_department": employee.department_id.name if employee.department_id else "",
            "incident_date": self.incident_date.strftime("%B %d, %Y") if self.incident_date else "",
            "offense": self.offense_classification_id.name if self.offense_classification_id else "",
            "decision_outcome": outcome_label,
            "rationale": self.decision_rationale or "",
            "warning_expiry": warning_expiry,
            "appeal_deadline": appeal_deadline,
            "hr_name": self.env.user.name,
            "hr_title": "Human Resources Manager",
            "witness_name": self.hearing_officer_id.name if self.hearing_officer_id else "________________",
            "witness_title": (self.hearing_officer_id.job_title or "Witness") if self.hearing_officer_id else "Witness",
            "termination_type": dict(self._fields['termination_type'].selection).get(
                self.termination_type, "") if self.termination_type else "",
            "notice_period": (str(self.notice_period_months) + " months") if self.notice_period_months else "",
            "suspension_days": str(self.suspension_days) if self.suspension_days else "",
            "suspension_with_pay": "with pay" if self.suspension_with_pay else "without pay",
        }

        output_path = tempfile.mktemp(suffix=".docx")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as jf:
            json.dump(data, jf, ensure_ascii=False)
            json_path = jf.name

        js_content = self._get_letter_js()
        js_content = js_content.replace('__OUTPUT_PATH__', output_path).replace('__JSON_PATH__', json_path)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as jsf:
            jsf.write(js_content)
            js_path = jsf.name

        # Ensure docx npm package is available inside the container
        npm_dir = '/tmp/docx_npm'
        npm_check = subprocess.run(
            ['node', '-e', "require('/tmp/docx_npm/node_modules/docx')"],
            capture_output=True, text=True)
        if npm_check.returncode != 0:
            os.makedirs(npm_dir, exist_ok=True)
            install = subprocess.run(
                ['npm', 'install', '--prefix', npm_dir, 'docx'],
                capture_output=True, text=True, timeout=120, cwd=npm_dir)
            if install.returncode != 0:
                raise UserError("Failed to install docx package: %s" % install.stderr)

        try:
            result = subprocess.run(['node', js_path], capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise UserError("Letter generation failed: %s" % (result.stderr or result.stdout))
            with open(output_path, 'rb') as f:
                docx_bytes = f.read()
            filename = "Decision_Letter_%s_%s.docx" % (
                self.name.replace('/', '_'), employee.name.replace(' ', '_'))
            self.write({
                'decision_letter': base64.b64encode(docx_bytes),
                'decision_letter_filename': filename,
                'decision_letter_generated': True,
            })
        finally:
            for p in [json_path, js_path, output_path]:
                try:
                    os.unlink(p)
                except Exception:
                    pass

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/hr.disciplinary.case/%d/decision_letter/%s?download=true' % (self.id, filename),
            'target': 'self',
        }

    def _get_letter_js(self):
        # Read the JS template from a file next to this Python file
        js_path = os.path.join(os.path.dirname(__file__), 'letter_template.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            return f.read()

    # ─────────────────────────────────────────────
    # Create / Constraints
    # ─────────────────────────────────────────────
    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("hr.disciplinary.case") or "New"
        return super().create(vals)

    @api.constrains('incident_date', 'reported_date')
    def _check_dates(self):
        for rec in self:
            if rec.reported_date and rec.incident_date and rec.reported_date < rec.incident_date:
                raise ValidationError("Reported date cannot be before the incident date.")

    @api.onchange('decision_outcome')
    def _onchange_decision_outcome(self):
        if self.decision_outcome != 'termination':
            self.termination_type = False
            self.notice_period_months = 0
        if self.decision_outcome != 'suspension':
            self.suspension_days = 0
        if self.decision_outcome == 'termination' and self.employee_id.first_contract_date:
            years = (date.today() - self.employee_id.first_contract_date).days / 365
            self.notice_period_months = 1 if years < 1 else (2 if years <= 9 else 3)