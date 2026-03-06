from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    policy_pending_ack_count = fields.Integer(compute='_compute_policy_compliance')
    policy_onboarding_complete = fields.Boolean(compute='_compute_policy_compliance')

    def _compute_policy_compliance(self):
        assignment_model = self.env['policy.assignment']
        for employee in self:
            pending = assignment_model.search_count([
                ('employee_id', '=', employee.id),
                ('version_id.state', '=', 'active'),
                ('required', '=', True),
                ('status', 'in', ['pending', 'overdue']),
            ])
            employee.policy_pending_ack_count = pending
            employee.policy_onboarding_complete = pending == 0

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        active_versions = self.env['policy.version'].search([('state', '=', 'active')])
        for version in active_versions:
            target = employees.filtered(lambda emp: version._employee_matches_scope(emp))
            if target:
                version._assign_employees(employees=target)
        return employees

    def action_open_policy_assignments(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('sfk_policy_compliance.action_policy_assignment')
        action['domain'] = [('employee_id', '=', self.id)]
        return action
