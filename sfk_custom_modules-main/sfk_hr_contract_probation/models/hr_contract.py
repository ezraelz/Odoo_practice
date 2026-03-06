from datetime import datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrContract(models.Model):
    _inherit = 'hr.contract'

    is_probation = fields.Boolean(
        string='Is Probation',
        tracking=True,
        help='Enable to run the probation process for this contract.',
    )
    probation_extension_working_days = fields.Integer(
        string='Probation Extension Working Days',
        default=0,
        copy=False,
        help='Internal counter used to extend probation in working days.',
    )

    def _get_probation_deadline(self, working_days):
        self.ensure_one()

        if not self.date_start:
            return False

        start_dt = datetime.combine(self.date_start, time.min)
        calendar = self.resource_calendar_id or self.company_id.resource_calendar_id

        if calendar:
            planned_dt = calendar.plan_days(working_days, start_dt, compute_leaves=True)
            if planned_dt:
                return fields.Date.to_date(planned_dt)

        # Fallback for contracts without a working schedule.
        return self.date_start + timedelta(days=max(working_days - 1, 0))

    def _sync_probation_deadline(self):
        for contract in self:
            if not contract.is_probation or not contract.date_start:
                continue
            total_working_days = 60 + contract.probation_extension_working_days
            deadline = contract._get_probation_deadline(total_working_days)
            if deadline and contract.date_end != deadline:
                contract.with_context(skip_probation_sync=True).write({'date_end': deadline})

    @api.onchange('is_probation', 'date_start', 'resource_calendar_id', 'probation_extension_working_days')
    def _onchange_probation_deadline(self):
        for contract in self:
            if contract.is_probation and contract.date_start:
                total_working_days = 60 + contract.probation_extension_working_days
                contract.date_end = contract._get_probation_deadline(total_working_days)
            elif not contract.is_probation and contract.probation_extension_working_days:
                contract.probation_extension_working_days = 0

    def _sync_employee_probation_tag(self, employees=None):
        tag = self.env.ref('sfk_hr_contract_probation.employee_tag_probation', raise_if_not_found=False)
        if not tag:
            return

        employees_to_sync = (employees or self.mapped('employee_id')).exists()
        for employee in employees_to_sync:
            in_probation = bool(self.search_count([
                ('employee_id', '=', employee.id),
                ('is_probation', '=', True),
                ('state', 'in', ['draft', 'open']),
            ]))
            if in_probation and tag not in employee.category_ids:
                employee.write({'category_ids': [(4, tag.id)]})
            elif not in_probation and tag in employee.category_ids:
                employee.write({'category_ids': [(3, tag.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        contracts.filtered('is_probation')._sync_probation_deadline()
        contracts._sync_employee_probation_tag()
        return contracts

    def write(self, vals):
        employees_before = self.mapped('employee_id')
        if vals.get('is_probation') is False and 'probation_extension_working_days' not in vals:
            vals['probation_extension_working_days'] = 0
        if vals.get('is_probation') is False and 'date_end' not in vals:
            vals['date_end'] = False
        res = super().write(vals)
        if not self.env.context.get('skip_probation_sync') and (
            {'is_probation', 'date_start', 'resource_calendar_id', 'company_id', 'employee_id', 'probation_extension_working_days'}
            & set(vals.keys())
        ):
            self._sync_probation_deadline()
        if not self.env.context.get('skip_probation_sync') and (
            {'is_probation', 'state', 'employee_id', 'active'} & set(vals.keys())
        ):
            self._sync_employee_probation_tag(employees_before | self.mapped('employee_id'))
        return res

    def action_confirm_probation(self):
        self.write({
            'is_probation': False,
            'probation_extension_working_days': 0,
            'date_end': False,
        })

    def action_extend_probation(self):
        for contract in self:
            if not contract.is_probation:
                raise UserError(_('Only contracts in probation can be extended.'))
            contract.write({
                'probation_extension_working_days': contract.probation_extension_working_days + 30,
            })

    def action_terminate_during_probation(self):
        today = fields.Date.context_today(self)
        for contract in self:
            if not contract.is_probation:
                raise UserError(_('Only contracts in probation can be terminated with this action.'))

            end_date = max(today, contract.date_start) if contract.date_start else today
            vals = {
                'is_probation': False,
                'probation_extension_working_days': 0,
                'state': 'close',
            }
            if not contract.date_end or contract.date_end > end_date:
                vals['date_end'] = end_date
            contract.write(vals)
