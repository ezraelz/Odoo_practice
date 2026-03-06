from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrLeaveAnnualEntitlement(models.Model):
    _name = "hr.leave.annual.entitlement"
    _description = "Annual Leave Entitlement"
    _order = "grant_date asc, id asc"

    name = fields.Char(compute="_compute_name", store=True)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade", index=True)
    leave_type_id = fields.Many2one("hr.leave.type", required=True, ondelete="cascade", index=True)
    grant_date = fields.Date(required=True, index=True)
    expiry_date = fields.Date(required=True, index=True)
    days_granted = fields.Float(required=True, digits=(16, 2))
    days_used = fields.Float(default=0.0, digits=(16, 2))
    remaining_days = fields.Float(compute="_compute_remaining_days", digits=(16, 2), store=True)
    state = fields.Selection(
        [("active", "Active"), ("expired", "Expired")],
        default="active",
        required=True,
        index=True,
    )

    _sql_constraints = [
        (
            "employee_type_grant_unique",
            "unique(employee_id, leave_type_id, grant_date)",
            "Only one annual leave entitlement is allowed per employee and grant date.",
        ),
    ]

    @api.depends("employee_id", "grant_date", "days_granted")
    def _compute_name(self):
        for record in self:
            if record.employee_id and record.grant_date:
                record.name = "%s - %s (%.2f days)" % (
                    record.employee_id.name,
                    record.grant_date,
                    record.days_granted,
                )
            else:
                record.name = "Annual Leave Entitlement"

    @api.depends("days_granted", "days_used")
    def _compute_remaining_days(self):
        for record in self:
            record.remaining_days = max(record.days_granted - record.days_used, 0.0)

    @api.model
    def _get_annual_leave_type(self):
        leave_type = self.env.ref("hr_leave_policy_ce.leave_type_annual", raise_if_not_found=False)
        if leave_type:
            return leave_type
        return self.env["hr.leave.type"].search([("policy_code", "=", "annual")], limit=1)

    @api.model
    def _get_service_entitlement(self, hire_date, as_of_date):
        if not hire_date or not as_of_date:
            return 0.0
        if isinstance(hire_date, str):
            hire_date = fields.Date.from_string(hire_date)
        if isinstance(as_of_date, str):
            as_of_date = fields.Date.from_string(as_of_date)

        if as_of_date < hire_date:
            return 0.0

        years_of_service = relativedelta(as_of_date, hire_date).years + 1
        increments = max((years_of_service - 1) // 2, 0)
        return float(16 + increments)

    @api.model
    def _compute_expiry_date(self, grant_date):
        if isinstance(grant_date, str):
            grant_date = fields.Date.from_string(grant_date)
        return date(grant_date.year + 2, 7, 7)

    @api.model
    def _get_available_balance(self, employee, on_date=None):
        on_date = on_date or fields.Date.today()
        leave_type = self._get_annual_leave_type()
        if not leave_type:
            return 0.0
        domain = [
            ("employee_id", "=", employee.id),
            ("leave_type_id", "=", leave_type.id),
            ("state", "=", "active"),
            ("grant_date", "<=", on_date),
            ("expiry_date", ">=", on_date),
        ]
        entitlements = self.search(domain)
        return sum(entitlements.mapped("remaining_days"))

    @api.model
    def _generate_employee_entitlements(self, employee, upto_date=None):
        if not employee.contract_hire_date:
            return self.browse()

        leave_type = self._get_annual_leave_type()
        if not leave_type:
            return self.browse()

        upto_date = upto_date or fields.Date.today()
        hire_date = employee.contract_hire_date
        created_records = self.browse()

        grant_date = hire_date
        while grant_date <= upto_date:
            existing = self.search([
                ("employee_id", "=", employee.id),
                ("leave_type_id", "=", leave_type.id),
                ("grant_date", "=", grant_date),
            ], limit=1)
            if not existing:
                created_records |= self.create({
                    "employee_id": employee.id,
                    "leave_type_id": leave_type.id,
                    "grant_date": grant_date,
                    "expiry_date": self._compute_expiry_date(grant_date),
                    "days_granted": self._get_service_entitlement(hire_date, grant_date),
                })
            grant_date = grant_date + relativedelta(years=1)

        return created_records

    @api.model
    def _cron_generate_annual_entitlements(self):
        employees = self.env["hr.employee"].search([("contract_hire_date", "!=", False)])
        for employee in employees:
            self._generate_employee_entitlements(employee)

    @api.model
    def _cron_expire_annual_leave(self):
        today = fields.Date.today()
        to_expire = self.search([
            ("state", "=", "active"),
            ("expiry_date", "<=", today),
        ])
        to_expire.write({"state": "expired"})


class HrLeaveAnnualUsage(models.Model):
    _name = "hr.leave.annual.usage"
    _description = "Annual Leave Usage"

    leave_id = fields.Many2one("hr.leave", required=True, ondelete="cascade", index=True)
    entitlement_id = fields.Many2one("hr.leave.annual.entitlement", required=True, ondelete="cascade", index=True)
    days = fields.Float(required=True, digits=(16, 2))
