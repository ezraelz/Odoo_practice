from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = "hr.leave.type"

    policy_code = fields.Selection(
        selection=[
            ("annual", "Annual Leave"),
            ("sick", "Sick Leave"),
            ("maternity", "Maternity Leave"),
            ("paternity", "Paternity Leave"),
            ("compassionate", "Compassionate Leave"),
            ("marriage", "Marriage Leave"),
            ("court", "Court Leave"),
            ("unpaid", "Unpaid Leave"),
            ("other", "Other"),
        ],
        default="other",
        required=True,
    )
    has_custom_limit = fields.Boolean(
        string="Has Limit",
        help="If disabled, only generic rules apply and no policy cap is enforced.",
    )
    max_days = fields.Float(
        string="Max Days",
        digits=(16, 2),
        help="Maximum days allowed in the rolling period for this leave type.",
    )
    period_months = fields.Integer(
        string="Rolling Period (Months)",
        default=12,
    )
    max_instances = fields.Integer(
        string="Max Instances / Year",
        help="Maximum number of approved requests per calendar year.",
    )
    max_split_per_year = fields.Integer(
        string="Max Annual Splits / Year",
        default=2,
        help="Annual leave plans can be split into this many requests each year.",
    )
