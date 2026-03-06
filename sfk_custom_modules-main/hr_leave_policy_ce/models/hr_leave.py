from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrLeave(models.Model):
    _inherit = "hr.leave"

    annual_available_balance = fields.Float(
        string="Annual Balance",
        compute="_compute_policy_details",
        digits=(16, 2),
    )
    policy_pay_note = fields.Char(
        string="Pay Rule",
        compute="_compute_policy_details",
    )
    annual_usage_ids = fields.One2many("hr.leave.annual.usage", "leave_id", readonly=True)

    @api.depends("holiday_status_id", "employee_id", "request_date_from", "number_of_days")
    def _compute_policy_details(self):
        entitlement_model = self.env["hr.leave.annual.entitlement"]
        for leave in self:
            leave.annual_available_balance = 0.0
            leave.policy_pay_note = False
            if not leave.holiday_status_id:
                continue

            if leave.holiday_status_id.policy_code == "annual" and leave.employee_id:
                leave_date = leave.request_date_from or fields.Date.today()
                leave.annual_available_balance = entitlement_model._get_available_balance(
                    leave.employee_id,
                    leave_date,
                )

            if leave.holiday_status_id.policy_code == "sick":
                leave.policy_pay_note = "1 month full pay, 2 months half pay, 3 months no pay (max 6 months/12 months)."
            elif leave.holiday_status_id.policy_code == "maternity":
                leave.policy_pay_note = "120 consecutive calendar days, fully paid."
            elif leave.holiday_status_id.policy_code == "paternity":
                leave.policy_pay_note = "3 consecutive working days, fully paid. Birth certificate required."
            elif leave.holiday_status_id.policy_code == "unpaid":
                leave.policy_pay_note = "No salary or benefits during unpaid leave."

    def _get_employee_hire_date(self):
        self.ensure_one()
        return self.employee_id.contract_hire_date

    def _get_leave_days_value(self):
        self.ensure_one()
        return max(self.number_of_days or 0.0, 0.0)

    def _is_annual_leave(self):
        self.ensure_one()
        return self.holiday_status_id.policy_code == "annual"

    def _validate_general_limits(self):
        for leave in self:
            leave_type = leave.holiday_status_id
            if not leave_type or not leave.employee_id:
                continue

            if leave.request_date_from and leave.request_date_to and leave.request_date_to < leave.request_date_from:
                raise ValidationError(_("Leave end date must be after the start date."))

            if leave_type.has_custom_limit and leave_type.max_days > 0 and leave_type.period_months > 0 and leave.request_date_from:
                period_end = leave.request_date_to or leave.request_date_from
                period_start = period_end + relativedelta(months=-leave_type.period_months)
                domain = [
                    ("id", "!=", leave.id),
                    ("employee_id", "=", leave.employee_id.id),
                    ("holiday_status_id", "=", leave_type.id),
                    ("state", "in", ["confirm", "validate1", "validate"]),
                    ("request_date_from", "<=", period_end),
                    ("request_date_to", ">=", period_start),
                ]
                used = sum(self.search(domain).mapped("number_of_days")) + leave._get_leave_days_value()
                if used > leave_type.max_days:
                    raise ValidationError(_(
                        "%(type)s is limited to %(max)s days in a %(months)s-month period.",
                        type=leave_type.name,
                        max=leave_type.max_days,
                        months=leave_type.period_months,
                    ))

            if leave_type.max_instances > 0 and leave.request_date_from:
                year_start = leave.request_date_from.replace(month=1, day=1)
                year_end = leave.request_date_from.replace(month=12, day=31)
                count_domain = [
                    ("id", "!=", leave.id),
                    ("employee_id", "=", leave.employee_id.id),
                    ("holiday_status_id", "=", leave_type.id),
                    ("state", "in", ["confirm", "validate1", "validate"]),
                    ("request_date_from", ">=", year_start),
                    ("request_date_from", "<=", year_end),
                ]
                instances = self.search_count(count_domain) + 1
                if instances > leave_type.max_instances:
                    raise ValidationError(_(
                        "%(type)s allows only %(max)s requests per calendar year.",
                        type=leave_type.name,
                        max=leave_type.max_instances,
                    ))

    def _validate_annual_policy(self):
        entitlement_model = self.env["hr.leave.annual.entitlement"]
        for leave in self.filtered(lambda l: l.holiday_status_id.policy_code == "annual"):
            hire_date = leave._get_employee_hire_date()
            if not hire_date:
                raise ValidationError(_("Date Hired is required from contracts before requesting annual leave."))

            probation_end = hire_date + relativedelta(months=6)
            if leave.request_date_from and leave.request_date_from < probation_end:
                raise ValidationError(_(
                    "Annual leave is available only after probation. Eligible from %(date)s.",
                    date=probation_end,
                ))

            # Annual leave planning can be split into at most 2 requests per year.
            year_ref = leave.request_date_from or fields.Date.today()
            year_start = year_ref.replace(month=1, day=1)
            year_end = year_ref.replace(month=12, day=31)
            split_limit = leave.holiday_status_id.max_split_per_year or 2
            split_domain = [
                ("id", "!=", leave.id),
                ("employee_id", "=", leave.employee_id.id),
                ("holiday_status_id", "=", leave.holiday_status_id.id),
                ("state", "in", ["confirm", "validate1", "validate"]),
                ("request_date_from", ">=", year_start),
                ("request_date_from", "<=", year_end),
            ]
            annual_parts = self.search_count(split_domain) + 1
            if annual_parts > split_limit:
                raise ValidationError(_("Annual leave can be split into at most %(limit)s parts per year.", limit=split_limit))

            leave_date = leave.request_date_from or fields.Date.today()
            entitlement_model._generate_employee_entitlements(leave.employee_id, leave_date)
            available = entitlement_model._get_available_balance(leave.employee_id, leave_date)

            reserved_domain = [
                ("id", "!=", leave.id),
                ("employee_id", "=", leave.employee_id.id),
                ("holiday_status_id", "=", leave.holiday_status_id.id),
                ("state", "in", ["confirm", "validate1"]),
            ]
            reserved = sum(self.search(reserved_domain).mapped("number_of_days"))
            requested = leave._get_leave_days_value()
            if requested > max(available - reserved, 0.0):
                raise ValidationError(_(
                    "Insufficient annual leave balance. Available: %(available).2f days, Reserved: %(reserved).2f days, Requested: %(requested).2f days.",
                    available=available,
                    reserved=reserved,
                    requested=requested,
                ))

    def _validate_named_policy_requirements(self):
        for leave in self:
            leave_type = leave.holiday_status_id
            if not leave_type:
                continue

            requested_days = leave._get_leave_days_value()
            consecutive_days = 0
            if leave.request_date_from and leave.request_date_to:
                consecutive_days = (leave.request_date_to - leave.request_date_from).days + 1

            if leave_type.policy_code == "sick":
                end_date = leave.request_date_to or leave.request_date_from
                if end_date:
                    start_period = end_date + relativedelta(months=-12)
                    domain = [
                        ("id", "!=", leave.id),
                        ("employee_id", "=", leave.employee_id.id),
                        ("holiday_status_id", "=", leave_type.id),
                        ("state", "in", ["confirm", "validate1", "validate"]),
                        ("request_date_from", "<=", end_date),
                        ("request_date_to", ">=", start_period),
                    ]
                    used = sum(self.search(domain).mapped("number_of_days")) + requested_days
                    if used > 180:
                        raise ValidationError(_("Sick leave cannot exceed 6 months (180 days) in any rolling 12-month period."))

            if leave_type.policy_code == "maternity" and consecutive_days and consecutive_days != 120:
                raise ValidationError(_("Maternity leave must be exactly 120 consecutive calendar days."))

            if leave_type.policy_code == "paternity":
                if requested_days and requested_days != 3:
                    raise ValidationError(_("Paternity leave must be exactly 3 consecutive working days."))
                if not leave.supported_attachment_ids:
                    raise ValidationError(_("Birth certificate document is required for paternity leave."))

            if leave_type.policy_code in ("compassionate", "marriage") and requested_days and requested_days > 3:
                raise ValidationError(_("%(type)s is limited to 3 days.", type=leave_type.name))

            if leave_type.policy_code == "unpaid":
                if requested_days and requested_days > 5:
                    raise ValidationError(_("Unpaid leave is limited to 5 days per request."))

                if leave.request_date_from:
                    year_start = leave.request_date_from.replace(month=1, day=1)
                    year_end = leave.request_date_from.replace(month=12, day=31)
                    domain = [
                        ("id", "!=", leave.id),
                        ("employee_id", "=", leave.employee_id.id),
                        ("holiday_status_id", "=", leave_type.id),
                        ("state", "in", ["confirm", "validate1", "validate"]),
                        ("request_date_from", ">=", year_start),
                        ("request_date_from", "<=", year_end),
                    ]
                    instances = self.search_count(domain) + 1
                    if instances > 2:
                        raise ValidationError(_("Unpaid leave can be used at most 2 times per year."))

    @api.constrains("holiday_status_id", "employee_id", "request_date_from", "request_date_to", "number_of_days", "state")
    def _check_leave_policy_constraints(self):
        managed_states = {"confirm", "validate1", "validate"}
        to_check = self.filtered(lambda l: l.state in managed_states)
        if not to_check:
            return
        to_check._validate_general_limits()
        to_check._validate_annual_policy()
        to_check._validate_named_policy_requirements()

    def _consume_annual_entitlements(self):
        entitlement_model = self.env["hr.leave.annual.entitlement"]
        usage_model = self.env["hr.leave.annual.usage"]

        for leave in self.filtered(lambda l: l._is_annual_leave() and not l.annual_usage_ids and l.state == "validate"):
            leave_date = leave.request_date_from or fields.Date.today()
            entitlement_model._generate_employee_entitlements(leave.employee_id, leave_date)
            needed = leave._get_leave_days_value()
            entitlements = entitlement_model.search([
                ("employee_id", "=", leave.employee_id.id),
                ("leave_type_id", "=", leave.holiday_status_id.id),
                ("state", "=", "active"),
                ("grant_date", "<=", leave_date),
                ("expiry_date", ">=", leave_date),
                ("remaining_days", ">", 0),
            ], order="grant_date asc, id asc")

            for entitlement in entitlements:
                if needed <= 0:
                    break
                use_days = min(entitlement.remaining_days, needed)
                if use_days <= 0:
                    continue
                usage_model.create({
                    "leave_id": leave.id,
                    "entitlement_id": entitlement.id,
                    "days": use_days,
                })
                entitlement.days_used += use_days
                needed -= use_days

            if needed > 0:
                raise ValidationError(_("Not enough annual leave entitlement to validate this request."))

    def _release_annual_entitlements(self):
        for leave in self.filtered(lambda l: l.annual_usage_ids):
            for usage in leave.annual_usage_ids:
                usage.entitlement_id.days_used = max(usage.entitlement_id.days_used - usage.days, 0.0)
            leave.annual_usage_ids.unlink()

    def action_validate(self):
        res = super().action_validate()
        self._consume_annual_entitlements()
        return res

    def action_refuse(self):
        to_release = self.filtered(lambda l: l.state == "validate")
        res = super().action_refuse()
        to_release._release_annual_entitlements()
        return res

    def action_cancel(self):
        to_release = self.filtered(lambda l: l.state == "validate")
        res = super().action_cancel()
        to_release._release_annual_entitlements()
        return res

    def action_reset_confirm(self):
        to_release = self.filtered(lambda l: l.state == "validate")
        res = super().action_reset_confirm()
        to_release._release_annual_entitlements()
        return res
