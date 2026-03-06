from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    contract_hire_date = fields.Date(
        string="Date Hired",
        compute="_compute_contract_hire_date",
        store=True,
        help="Earliest contract start date used by leave entitlement rules.",
    )
    annual_leave_balance = fields.Float(
        string="Annual Leave Balance",
        compute="_compute_annual_leave_balance",
        digits=(16, 2),
    )
    annual_leave_entitlement = fields.Float(
        string="Annual Entitlement",
        compute="_compute_annual_leave_balance",
        digits=(16, 2),
    )
    annual_leave_probation_end = fields.Date(
        string="Annual Leave Eligible From",
        compute="_compute_annual_leave_balance",
    )

    @api.depends("contract_ids.date_start", "first_contract_date")
    def _compute_contract_hire_date(self):
        for employee in self:
            starts = employee.contract_ids.filtered(lambda c: c.date_start).mapped("date_start")
            employee.contract_hire_date = min(starts) if starts else employee.first_contract_date

    @api.depends("contract_hire_date")
    def _compute_annual_leave_balance(self):
        entitlement_model = self.env["hr.leave.annual.entitlement"]
        for employee in self:
            hire_date = employee.contract_hire_date
            employee.annual_leave_probation_end = hire_date + relativedelta(months=6) if hire_date else False
            if not hire_date:
                employee.annual_leave_balance = 0.0
                employee.annual_leave_entitlement = 0.0
                continue
            employee.annual_leave_entitlement = entitlement_model._get_service_entitlement(
                hire_date,
                fields.Date.today(),
            )
            employee.annual_leave_balance = entitlement_model._get_available_balance(
                employee,
                fields.Date.today(),
            )
