import re

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.tools import format_date
from odoo.exceptions import UserError


class JobOffer(models.Model):
    _name = "job.offer"
    _description = "Job Offer"
    _order = "create_date desc, id desc"

    name = fields.Char(string="Title", required=True, default="New Offer")

    applicant_id = fields.Many2one("hr.applicant", string="Applicant", required=True)

    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True)

    job_position = fields.Many2one("hr.job", string="Job Position")
    work_location = fields.Char(string="Work Location")

    offer_date = fields.Date(string="Offer Date", default=fields.Date.context_today)
    start_date = fields.Date(string="Effective Start Date")

    salary = fields.Monetary(string="Salary", currency_field="currency_id")
    salary_type = fields.Selection(
        [("monthly", "Monthly"), ("yearly", "Yearly")],
        string="Salary Type",
        default="yearly",
        required=True,
    )
    contract_type_id = fields.Many2one("hr.contract.type", string="Contract Type")
    working_schedule = fields.Char(string="Working Schedule")

    benefits = fields.Text(string="Benefits")
    additional_terms = fields.Text(string="Additional Terms")
    body_text = fields.Text(string="Offer Body")
    rendered_body_html = fields.Html(string="Rendered Body", compute="_compute_rendered_body_html", sanitize=False)
    notes = fields.Text(string="Notes")

    template = fields.Selection(
        [
            ("template_1", "Template 1 - Classic"),
            ("template_2", "Template 2 - Modern"),
            ("template_3", "Template 3 - Minimal"),
            ("template_4", "Template 4 - Formal"),
            ("template_5", "Template 5 - Corporate"),
        ],
        string="PDF Template",
        default="template_1",
        required=True,
    )
    is_generated = fields.Boolean(string="Generated", default=False, readonly=True)
    preview_nonce = fields.Integer(string="Preview Nonce", default=0)
    preview_pdf_html = fields.Html(string="PDF Preview", compute="_compute_preview_pdf_html", sanitize=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        applicant = self.env["hr.applicant"]
        if self._context.get("active_model") == "hr.applicant" and self._context.get("active_id"):
            applicant = self.env["hr.applicant"].browse(self._context["active_id"])
        elif self._context.get("default_applicant_id"):
            applicant = self.env["hr.applicant"].browse(self._context["default_applicant_id"])

        if applicant:
            partner = applicant.partner_id

            salary_value = 0.0
            if "salary_expected" in applicant._fields:
                salary_value = applicant.salary_expected or 0.0
            elif "expected_salary" in applicant._fields:
                salary_value = applicant.expected_salary or 0.0
            contract_type_id = False
            employee = self.env["hr.employee"]
            if "emp_id" in applicant._fields and applicant.emp_id:
                employee = applicant.emp_id
            elif partner and "employee_ids" in partner._fields and partner.employee_ids:
                employee = partner.employee_ids[0]

            if employee:
                if "contract_id" in employee._fields and employee.contract_id and "contract_type_id" in employee.contract_id._fields:
                    contract_type_id = employee.contract_id.contract_type_id.id
                elif "hr.contract" in self.env.registry.models:
                    contract = self.env["hr.contract"].search(
                        [("employee_id", "=", employee.id)],
                        order="date_start desc, id desc",
                        limit=1,
                    )
                    if contract and "contract_type_id" in contract._fields:
                        contract_type_id = contract.contract_type_id.id

            res.update(
                {
                    "name": f"Offer for {applicant.partner_name or applicant.name}",
                    "applicant_id": applicant.id,
                    "job_position": applicant.job_id.id,
                    "salary": salary_value,
                    "contract_type_id": contract_type_id,
                }
            )
        return res

    def action_generate_offer(self):
        self.ensure_one()
        self.is_generated = True
        self.preview_nonce += 1
        return self.action_refresh_offer_preview()

    def action_download_offer_pdf(self):
        self.ensure_one()
        report_xmlid = self._template_report_xmlid()
        report = self.env.ref(report_xmlid, raise_if_not_found=False)
        if not report:
            report_name = report_xmlid.replace("report_", "")
            report = self.env["ir.actions.report"].search(
                [("report_name", "=", report_name)],
                limit=1,
            )
        if not report:
            raise UserError("Offer report action is missing. Please upgrade the Job Offer module.")
        return report.report_action(self)

    def action_refresh_offer_preview(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "job.offer",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("job_offer.view_job_offer_form").id,
            "target": "current",
        }

    def _template_report_xmlid(self):
        mapping = {
            "template_1": "job_offer.report_offer_template_1",
            "template_2": "job_offer.report_offer_template_2",
            "template_3": "job_offer.report_offer_template_3",
            "template_4": "job_offer.report_offer_template_4",
            "template_5": "job_offer.report_offer_template_5",
        }
        return mapping.get(self.template, "job_offer.report_offer_template_1")

    @api.depends(
        "body_text",
        "name",
        "applicant_id",
        "job_position",
        "company_id",
        "offer_date",
        "start_date",
        "salary",
        "salary_type",
        "contract_type_id",
        "work_location",
        "working_schedule",
        "benefits",
        "additional_terms",
        "notes",
    )
    def _compute_rendered_body_html(self):
        for offer in self:
            offer.rendered_body_html = offer._render_dynamic_body_html(offer.body_text or "")

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
        contract_type_label = self.contract_type_id.name or ""
        salary_period = "monthly" if self.salary_type == "monthly" else "yearly"
        salary_value = f"{self.salary:,.2f} {self.currency_id.name or ''}".strip() if self.salary else ""
        return {
            "title": self.name or "",
            "applicant_name": self.applicant_id.partner_name or self.applicant_id.name or "",
            "job_position": self.job_position.name or "",
            "company_name": self.company_id.name or "",
            "offer_date": format_date(self.env, self.offer_date) if self.offer_date else "",
            "start_date": format_date(self.env, self.start_date) if self.start_date else "",
            "salary": salary_value,
            "salary_type": salary_period,
            "contract_type": contract_type_label,
            "work_location": self.work_location or "",
            "working_schedule": self.working_schedule or "",
            "benefits": self.benefits or "",
            "additional_terms": self.additional_terms or "",
            "notes": self.notes or "",
        }

    @api.depends("template", "preview_nonce", "write_date")
    def _compute_preview_pdf_html(self):
        for offer in self:
            if not offer.id:
                offer.preview_pdf_html = "<div style='padding:12px;'>Save the offer to render PDF preview.</div>"
                continue
            report_name = offer._template_report_xmlid().replace("job_offer.report_", "job_offer.")
            pdf_url = f"/report/pdf/{report_name}/{offer.id}?_preview={offer.preview_nonce}"
            offer.preview_pdf_html = (
                "<div style='height:760px; border:1px solid #d8dde6; background:#fff;'>"
                f"<iframe src='{pdf_url}' style='width:100%; height:100%; border:0;' title='Offer PDF Preview'></iframe>"
                "</div>"
            )
