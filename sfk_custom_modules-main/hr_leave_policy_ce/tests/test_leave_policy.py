from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install")
class TestLeavePolicy(TransactionCase):

    def setUp(self):
        super().setUp()
        self.employee = self.env["hr.employee"].create({"name": "Policy Employee"})
        self.hire_date = fields.Date.today() - relativedelta(years=4)
        self.env["hr.contract"].create({
            "name": "Policy Contract",
            "employee_id": self.employee.id,
            "date_start": self.hire_date,
            "wage": 1000,
            "state": "open",
        })
        self.employee.invalidate_recordset(["contract_hire_date"])

        self.annual_type = self.env.ref("hr_leave_policy_ce.leave_type_annual")
        self.unpaid_type = self.env.ref("hr_leave_policy_ce.leave_type_unpaid")

    def _create_leave(self, leave_type, date_from, date_to):
        return self.env["hr.leave"].create({
            "employee_id": self.employee.id,
            "holiday_status_id": leave_type.id,
            "request_date_from": date_from,
            "request_date_to": date_to,
            "name": "Test leave",
        })

    def test_entitlement_tier_formula(self):
        entitlement_model = self.env["hr.leave.annual.entitlement"]
        entitlement = entitlement_model._get_service_entitlement(self.hire_date, fields.Date.today())
        self.assertEqual(entitlement, 17.0, "4th service year should grant 17 days")

    def test_annual_probation_restriction(self):
        probation_start = self.hire_date
        probation_end = probation_start + relativedelta(months=6)
        with self.assertRaises(ValidationError):
            self._create_leave(
                self.annual_type,
                probation_start + relativedelta(days=1),
                probation_start + relativedelta(days=2),
            )

        leave = self._create_leave(
            self.annual_type,
            probation_end,
            probation_end + relativedelta(days=1),
        )
        self.assertTrue(leave)

    def test_annual_split_limit(self):
        start = fields.Date.today().replace(month=8, day=1)
        self._create_leave(self.annual_type, start, start + relativedelta(days=1))
        self._create_leave(self.annual_type, start + relativedelta(months=1), start + relativedelta(months=1, days=1))
        with self.assertRaises(ValidationError):
            self._create_leave(self.annual_type, start + relativedelta(months=2), start + relativedelta(months=2, days=1))

    def test_unpaid_max_instances(self):
        start = fields.Date.today().replace(month=2, day=1)
        self._create_leave(self.unpaid_type, start, start + relativedelta(days=1))
        self._create_leave(self.unpaid_type, start + relativedelta(months=1), start + relativedelta(months=1, days=1))
        with self.assertRaises(ValidationError):
            self._create_leave(self.unpaid_type, start + relativedelta(months=2), start + relativedelta(months=2, days=1))
