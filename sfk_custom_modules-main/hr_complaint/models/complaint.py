import json
import re

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_datetime
import logging

_logger = logging.getLogger(__name__)


class HrComplaint(models.Model):
    _name = "hr.complaint"
    _description = "HR Complaint"
    _rec_name = "subject"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    _EMPLOYEE_EDITABLE_FIELDS = {
        "subject",
        "description",
        "body_text",
        "complaint_type",
        "attachment",
        "attachment_filename",
        "created_on",
    }

    @api.model
    def _default_employee_id(self):
        return self.env["hr.employee"].search([("user_id", "=", self.env.uid)], limit=1)

    subject = fields.Char(required=True, tracking=True)
    description = fields.Text(required=True)
    complaint_type = fields.Selection(
        [
            ("harassment", "Harassment"),
            ("discrimination", "Discrimination"),
            ("workplace", "Workplace Conflict"),
            ("policy", "Policy Violation"),
            ("compensation", "Compensation"),
            ("other", "Other"),
        ],
        default="other",
        required=True,
        tracking=True,
    )
    attachment = fields.Binary(attachment=True)
    attachment_filename = fields.Char()

    employee_id = fields.Many2one(
        "hr.employee",
        required=True,
        default=_default_employee_id,
        ondelete="cascade",
        tracking=True,
    )
    employee_user_id = fields.Many2one(
        "res.users",
        related="employee_id.user_id",
        store=True,
        readonly=True,
        index=True,
    )

    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("in_review", "In Review"),
            ("resolved", "Resolved"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    hr_response = fields.Text(tracking=True)
    body_text = fields.Text(string="Report Body")
    rendered_body_html = fields.Html(string="Rendered Body", compute="_compute_rendered_body_html", sanitize=False)
    created_on = fields.Datetime(
        string="Created On",
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    submitted_on = fields.Datetime(readonly=True, tracking=True)
    closed_on = fields.Datetime(readonly=True, tracking=True)
    preview_nonce = fields.Integer(string="Preview Nonce", default=0)
    preview_pdf_html = fields.Html(string="Print Preview", compute="_compute_preview_pdf_html", sanitize=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self.env.user.has_group("hr.group_hr_manager"):
                continue

            employee = self._default_employee_id()
            if not employee:
                raise ValidationError(
                    _("No employee record is linked to your user. Contact HR to complete your employee profile.")
                )

            if vals.get("employee_id") and vals["employee_id"] != employee.id:
                raise ValidationError(_("You can only create complaints for yourself."))

            vals["employee_id"] = employee.id

            if not vals.get("created_on"):
                vals["created_on"] = fields.Datetime.now()

        return super().create(vals_list)

    @api.constrains("subject", "description")
    def _check_required_text_content(self):
        for rec in self:
            if not (rec.subject or "").strip():
                raise ValidationError(_("Subject cannot be empty."))
            if not (rec.description or "").strip():
                raise ValidationError(_("Description cannot be empty."))

    @api.constrains("created_on")
    def _check_created_on_not_far_future(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.created_on and rec.created_on > now:
                raise ValidationError(_("Created On cannot be in the future."))

    def write(self, vals):
        """Public write: employees can only edit draft complaints, never change status."""
        if self.env.user.has_group("hr.group_hr_manager"):
            return super().write(vals)

        for rec in self:
            if rec.employee_user_id != self.env.user:
                raise ValidationError(_("You can only edit your own complaints."))

            if "employee_id" in vals:
                raise ValidationError(_("You cannot change the employee."))

            if "status" in vals:
                raise ValidationError(_("Use the Submit button to change status."))

            if rec.status != "draft":
                raise ValidationError(_("Only draft complaints can be edited."))

            illegal = set(vals.keys()) - self._EMPLOYEE_EDITABLE_FIELDS
            if illegal:
                raise ValidationError(_("You cannot modify: %s") % ", ".join(sorted(illegal)))

        return super().write(vals)

    def _submit_complaint(self):
        """Private method: perform submission with side effects."""
        self.ensure_one()
        
        if self.employee_user_id != self.env.user and not self.env.user.has_group("hr.group_hr_manager"):
            raise ValidationError(_("You can only submit your own complaint."))
        
        if self.status != "draft":
            raise ValidationError(_("Only draft complaints can be submitted."))
        
        super(HrComplaint, self).write({
            "status": "submitted",
            "submitted_on": fields.Datetime.now(),
        })

        self._safe_message_post(_("Complaint submitted."))

        self._notify_hr_submission()

    def unlink(self):
        for rec in self:
            if rec.status not in ("draft", "rejected"):
                raise ValidationError(_("Cannot delete complaints that are submitted or resolved."))
            if not self.env.user.has_group("hr.group_hr_manager") and rec.employee_user_id != self.env.user:
                raise ValidationError(_("You can only delete your own complaints."))
        return super().unlink()

    def _send_email(self, recipients, subject, body_html):
        emails = ",".join(recipients.filtered("email").mapped("email"))
        if not emails:
            return
        email_from = (
            self.env.user.email_formatted
            or self.env.company.email
            or self.env["ir.config_parameter"].sudo().get_param("mail.default.from")
            or "noreply@example.com"
        )
        try:
            self.env["mail.mail"].sudo().create(
                {
                    "subject": subject,
                    "body_html": body_html,
                    "email_to": emails,
                    "email_from": email_from,
                }
            ).send(raise_exception=False)
        except Exception:
            _logger.exception("Failed to send complaint notification email")

    def _safe_message_post(self, body):
        for rec in self:
            try:
                rec.message_post(body=body)
            except Exception:
                _logger.exception("Failed to post complaint chatter message")

    def _notify_hr_submission(self):
        group = self.env.ref("hr.group_hr_manager", raise_if_not_found=False)
        if not group:
            return

        for rec in self:
            rec._send_email(
                group.users.mapped("partner_id"),
                subject=_("New HR Complaint Submitted: %s") % rec.subject,
                body_html=(
                    "<p>%s</p>"
                    "<p><strong>%s:</strong> %s</p>"
                    "<p><strong>%s:</strong> %s</p>"
                    "<p><strong>%s:</strong> %s</p>"
                )
                % (
                    _("A new complaint has been submitted."),
                    _("Employee"),
                    rec.employee_id.name,
                    _("Subject"),
                    rec.subject,
                    _("Type"),
                    dict(rec._fields["complaint_type"].selection).get(rec.complaint_type),
                ),
            )

    def _notify_employee_status(self):
        status_label = dict(self._fields["status"].selection)
        for rec in self:
            partner = rec.employee_user_id.partner_id
            if not partner:
                continue
            rec._send_email(
                partner,
                subject=_("Complaint Status Updated: %s") % rec.subject,
                body_html=(
                    "<p>%s</p>"
                    "<p><strong>%s:</strong> %s</p>"
                    "<p><strong>%s:</strong> %s</p>"
                    "<p><strong>%s:</strong> %s</p>"
                )
                % (
                    _("Your complaint status has been updated."),
                    _("Subject"),
                    rec.subject,
                    _("Status"),
                    status_label.get(rec.status),
                    _("HR Response"),
                    rec.hr_response or _("No response yet."),
                ),
            )

    def action_submit(self):
        """Public action: submit complaint with full validation and side effects."""
        for rec in self:
            rec._submit_complaint()

    def action_in_review(self):
        if not self.env.user.has_group("hr.group_hr_manager"):
            raise ValidationError(_("Only HR Managers can review complaints."))
        for rec in self:
            if rec.status != "submitted":
                raise ValidationError(_("Only submitted complaints can be moved to In Review."))
            super(HrComplaint, rec).write({"status": "in_review"})
            rec._safe_message_post(_("Complaint moved to In Review."))
            rec._notify_employee_status()

    def action_resolve(self):
        if not self.env.user.has_group("hr.group_hr_manager"):
            raise ValidationError(_("Only HR Managers can resolve complaints."))
        for rec in self:
            if rec.status not in ("submitted", "in_review"):
                raise ValidationError(_("Only submitted or in-review complaints can be resolved."))
            super(HrComplaint, rec).write({"status": "resolved", "closed_on": fields.Datetime.now()})
            rec._safe_message_post(_("Complaint resolved."))
            rec._notify_employee_status()

    def action_reject(self):
        if not self.env.user.has_group("hr.group_hr_manager"):
            raise ValidationError(_("Only HR Managers can reject complaints."))
        for rec in self:
            if rec.status not in ("submitted", "in_review"):
                raise ValidationError(_("Only submitted or in-review complaints can be rejected."))
            super(HrComplaint, rec).write({"status": "rejected", "closed_on": fields.Datetime.now()})
            rec._safe_message_post(_("Complaint rejected."))
            rec._notify_employee_status()

    def action_open_reject_wizard(self):
        self.ensure_one()
        return {
            "name": _("Reject Complaint"),
            "type": "ir.actions.act_window",
            "res_model": "hr.complaint.reject.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("hr_complaint.view_hr_complaint_reject_wizard").id,
            "target": "new",
            "context": {"default_complaint_id": self.id},
        }

    def action_print(self):
        self.ensure_one()
        self.preview_nonce += 1
        return self.action_refresh_print_preview()

    def action_download_pdf(self):
        self.ensure_one()
        return self._get_report_action_hr_complaint()

    def action_refresh_print_preview(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.complaint",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("hr_complaint.view_hr_complaint_form").id,
            "target": "current",
        }

    def _get_report_action_hr_complaint(self):
        self.ensure_one()
        report = self.env.ref("hr_complaint.action_report_hr_complaint", raise_if_not_found=False)
        if not report:
            report = self.env["ir.actions.report"].sudo().search(
                [
                    ("model", "=", "hr.complaint"),
                    ("report_name", "=", "hr_complaint.report_hr_complaint_document"),
                ],
                limit=1,
            )
        if not report:
            raise ValidationError(_("Report not found: hr_complaint.action_report_hr_complaint"))
        return report.report_action(self)

    @api.depends(
        "body_text",
        "subject",
        "employee_id",
        "complaint_type",
        "status",
        "created_on",
        "submitted_on",
        "closed_on",
        "description",
        "hr_response",
    )
    def _compute_rendered_body_html(self):
        for rec in self:
            rec.rendered_body_html = rec._render_dynamic_body_html(rec.body_text or "")

    def _render_dynamic_body_html(self, text):
        if not text:
            return ""
        rendered_text = self._render_dynamic_text(text)
        safe_text = escape(rendered_text)
        return Markup("<br/>").join(safe_text.splitlines())

    def _render_dynamic_text(self, text):
        values = self._dynamic_values()

        def _replace(match):
            token = (match.group(1) or "").strip()
            return str(values.get(token, ""))

        return re.sub(r"{{\s*([a-zA-Z0-9_]+)\s*}}", _replace, text)

    def _dynamic_values(self):
        self.ensure_one()
        type_label = dict(self._fields["complaint_type"].selection).get(self.complaint_type, "")
        status_label = dict(self._fields["status"].selection).get(self.status, "")
        return {
            "subject": self.subject or "",
            "employee_name": self.employee_id.name or "",
            "department": self.employee_id.department_id.name or "",
            "complaint_type": type_label,
            "status": status_label,
            "created_on": format_datetime(self.env, self.created_on) if self.created_on else "",
            "submitted_on": format_datetime(self.env, self.submitted_on) if self.submitted_on else "",
            "closed_on": format_datetime(self.env, self.closed_on) if self.closed_on else "",
            "description": self.description or "",
            "hr_response": self.hr_response or "",
            "company_name": self.env.company.name or "",
        }

    @api.depends("preview_nonce", "write_date")
    def _compute_preview_pdf_html(self):
        for rec in self:
            if not rec.id:
                rec.preview_pdf_html = "<div style='padding:12px;'>Save complaint to render preview.</div>"
                continue
            report_name = "hr_complaint.report_hr_complaint_document"
            write_stamp = int(rec.write_date.timestamp()) if rec.write_date else 0
            pdf_url = f"/report/pdf/{report_name}/{rec.id}?_preview={rec.preview_nonce}&_ts={write_stamp}"
            rec.preview_pdf_html = (
                "<div style='height:760px; border:1px solid #d8dde6; background:#fff;'>"
                f"<iframe src='{pdf_url}' style='width:100%; height:100%; border:0;' title='Complaint PDF Preview'></iframe>"
                "</div>"
            )


class HrComplaintRejectWizard(models.TransientModel):
    _name = "hr.complaint.reject.wizard"
    _description = "Reject Complaint Wizard"

    complaint_id = fields.Many2one("hr.complaint", required=True, ondelete="cascade")
    reason = fields.Text(string="Reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        complaint = self.complaint_id
        if not self.env.user.has_group("hr.group_hr_manager"):
            raise ValidationError(_("Only HR Managers can reject complaints."))
        complaint.write({"hr_response": self.reason})
        complaint.action_reject()
        return {"type": "ir.actions.act_window_close"}


class HrComplaintPrintWizard(models.TransientModel):
    _name = "hr.complaint.print.wizard"
    _description = "Complaint Print Wizard"

    complaint_id = fields.Many2one("hr.complaint", required=True, ondelete="cascade")

    logo = fields.Binary(string="Company Logo")
    logo_filename = fields.Char(string="Logo Filename")
    use_company_logo = fields.Boolean(string="Use Company Logo", default=True)

    primary_color = fields.Char(string="Primary Color", default="#000000")
    secondary_color = fields.Char(string="Secondary Color", default="#666666")
    background_color = fields.Char(string="Background Color", default="#FFFFFF")

    background_image = fields.Binary(string="Background Image")
    background_filename = fields.Char(string="Background Filename")

    layout_style = fields.Selection(
        [
            ("clean", "Clean"),
            ("boxed", "Boxed"),
            ("classic", "Classic"),
        ],
        string="Layout Style",
        default="clean",
    )
    layout_template = fields.Selection(
        [
            ("standard", "Standard"),
            ("executive", "Executive"),
            ("minimal", "Minimal"),
            ("cards", "Cards"),
            ("split", "Split Panel"),
        ],
        string="Layout Template",
        default="standard",
    )
    theme_preset = fields.Selection(
        [
            ("clean_light", "Clean Light"),
            ("ocean_glass", "Ocean Glass"),
            ("sunset_blend", "Sunset Blend"),
            ("forest_mist", "Forest Mist"),
            ("slate_modern", "Slate Modern"),
        ],
        string="Theme Preset",
        default="clean_light",
    )

    font_family = fields.Selection(
        [
            ("Helvetica", "Helvetica (Default)"),
            ("Arial", "Arial"),
            ("Times", "Times New Roman"),
            ("Courier", "Courier"),
        ],
        string="Font Family",
        default="Helvetica",
    )

    paper_format_id = fields.Many2one(
        "report.paperformat",
        string="Paper Format",
        default=lambda self: self.env.ref("base.paperformat_euro", raise_if_not_found=False),
    )

    header_text = fields.Char(string="Report Title", default="HR Complaint Report")
    show_address = fields.Boolean(string="Show Company Address", default=True)
    footer_text = fields.Char(string="Custom Footer")
    header_right_1 = fields.Char(string="Header Right Line 1")
    header_right_2 = fields.Char(string="Header Right Line 2")
    header_right_3 = fields.Char(string="Header Right Line 3")

    show_signature_line = fields.Boolean(string="Show Signature Lines", default=True)
    show_watermark = fields.Boolean(string="Show Draft Watermark", default=False)
    watermark_text = fields.Char(string="Watermark Text", default="DRAFT")

    def _defaults_param_key(self):
        return "hr_complaint.print_wizard_defaults.user_%s" % self.env.user.id

    def _serialize_defaults(self):
        self.ensure_one()
        return {
            "use_company_logo": bool(self.use_company_logo),
            "logo": self.logo or False,
            "logo_filename": self.logo_filename or "",
            "primary_color": self.primary_color or "#000000",
            "secondary_color": self.secondary_color or "#666666",
            "background_color": self.background_color or "#FFFFFF",
            "background_image": self.background_image or False,
            "background_filename": self.background_filename or "",
            "layout_style": self.layout_style or "clean",
            "layout_template": self.layout_template or "standard",
            "theme_preset": self.theme_preset or "clean_light",
            "font_family": self.font_family or "Helvetica",
            "paper_format_id": self.paper_format_id.id if self.paper_format_id else False,
            "header_text": self.header_text or "HR Complaint Report",
            "show_address": bool(self.show_address),
            "footer_text": self.footer_text or "",
            "header_right_1": self.header_right_1 or "",
            "header_right_2": self.header_right_2 or "",
            "header_right_3": self.header_right_3 or "",
            "show_signature_line": bool(self.show_signature_line),
            "show_watermark": bool(self.show_watermark),
            "watermark_text": self.watermark_text or "DRAFT",
        }

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)

        raw = self.env["ir.config_parameter"].sudo().get_param(self._defaults_param_key())
        if raw:
            try:
                saved = json.loads(raw)
            except Exception:
                saved = {}

            if saved:
                paper_format_id = saved.get("paper_format_id")
                if paper_format_id and not self.env["report.paperformat"].sudo().browse(paper_format_id).exists():
                    saved["paper_format_id"] = False
                values.update(saved)
        return values

    def _wizard_context(self, preview_mode=False):
        self.ensure_one()
        return {
            "wizard_primary_color": self.primary_color or "#000000",
            "wizard_secondary_color": self.secondary_color or "#666666",
            "wizard_background_color": self.background_color or "#FFFFFF",
            "wizard_layout_style": self.layout_style or "clean",
            "wizard_layout_template": self.layout_template or "standard",
            "wizard_theme_preset": self.theme_preset or "clean_light",
            "wizard_font_family": self.font_family or "Helvetica",
            "wizard_header": self.header_text or "HR Complaint Report",
            "wizard_footer": self.footer_text or "",
            "wizard_show_address": self.show_address,
            "wizard_header_right_1": self.header_right_1 or "",
            "wizard_header_right_2": self.header_right_2 or "",
            "wizard_header_right_3": self.header_right_3 or "",
            "wizard_show_signature": self.show_signature_line,
            "wizard_show_watermark": self.show_watermark,
            "wizard_watermark_text": self.watermark_text or "DRAFT",
            "wizard_preview_mode": preview_mode,
        }

    def action_preview(self):
        self.ensure_one()
        return self.action_print_now(preview_mode=True)

    def action_print_now(self, preview_mode=False):
        self.ensure_one()
        report = self.env.ref("hr_complaint.action_report_hr_complaint", raise_if_not_found=False)
        if not report:
            raise ValidationError(_("Report not found: hr_complaint.action_report_hr_complaint"))

        context = self._wizard_context(preview_mode=preview_mode)
        context["wizard_id"] = self.id
        action = report.with_context(**context).report_action(self.complaint_id)
        if self.paper_format_id:
            action["paperformat_id"] = self.paper_format_id.id
        return action

    def action_save_as_default(self):
        self.ensure_one()
        self.env["ir.config_parameter"].sudo().set_param(
            self._defaults_param_key(),
            json.dumps(self._serialize_defaults()),
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Saved"),
                "message": _("Your print layout defaults were saved."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
