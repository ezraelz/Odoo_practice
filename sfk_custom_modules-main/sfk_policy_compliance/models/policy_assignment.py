from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PolicyAssignment(models.Model):
    _name = 'policy.assignment'
    _description = 'Policy Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'due_date asc, id desc'

    version_id = fields.Many2one('policy.version', required=True, ondelete='cascade', index=True, tracking=True)
    document_id = fields.Many2one(related='version_id.document_id', store=True, index=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, tracking=True)
    employee_user_id = fields.Many2one(related='employee_id.user_id', store=True, index=True)
    required = fields.Boolean(default=True, tracking=True)
    status = fields.Selection([
        ('informational', 'Informational'),
        ('pending', 'Pending'),
        ('acknowledged', 'Acknowledged'),
        ('overdue', 'Overdue'),
    ], default='pending', index=True, tracking=True)
    assigned_date = fields.Date(default=fields.Date.context_today, required=True)
    due_date = fields.Date(index=True)
    acknowledged_date = fields.Date(tracking=True)
    accepted_version = fields.Char(readonly=True)
    last_reminder_date = fields.Date(readonly=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True, index=True)
    job_id = fields.Many2one(related='employee_id.job_id', store=True, index=True)
    employee_type = fields.Selection(related='employee_id.employee_type', store=True, index=True)

    _sql_constraints = [
        ('policy_assignment_unique', 'unique(version_id, employee_id)', 'Each employee can only have one assignment per policy version.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_status()
        records._notify_assignment()
        return records

    def write(self, vals):
        if not self.env.user.has_group('hr.group_hr_user'):
            allowed_fields = {'acknowledged_date', 'accepted_version', 'status'}
            if set(vals.keys()) - allowed_fields:
                raise UserError(_('You can only acknowledge your assigned policies.'))
            if any(assignment.employee_user_id != self.env.user for assignment in self):
                raise UserError(_('You can only update your own policy assignments.'))
        res = super().write(vals)
        if {'required', 'due_date', 'acknowledged_date'} & set(vals.keys()):
            self._sync_status()
        return res

    def _sync_status(self):
        today = fields.Date.context_today(self)
        for assignment in self:
            if assignment.acknowledged_date:
                status = 'acknowledged'
            elif not assignment.required:
                status = 'informational'
            elif assignment.due_date and assignment.due_date < today:
                status = 'overdue'
            else:
                status = 'pending'
            if assignment.status != status:
                assignment.with_context(skip_status_sync=True).write({'status': status})

    def _notify_assignment(self):
        for assignment in self:
            user = assignment.employee_user_id
            if not user:
                continue
            summary = _('Policy acknowledgment required: %s', assignment.document_id.name)
            if not assignment.required:
                summary = _('Policy shared for information: %s', assignment.document_id.name)
            assignment.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=summary,
                note=_('Policy version %(version)s has been assigned to you.', version=assignment.version_id.version_number),
                date_deadline=assignment.due_date,
            )

    def action_acknowledge(self):
        today = fields.Date.context_today(self)
        hr_manager = self.env.user.has_group('hr.group_hr_user')
        for assignment in self:
            if assignment.status == 'acknowledged':
                continue
            is_owner = assignment.employee_user_id == self.env.user
            if not (is_owner or hr_manager):
                raise UserError(_('You can only acknowledge policies assigned to you.'))
            assignment.write({
                'acknowledged_date': today,
                'accepted_version': assignment.version_id.version_number,
            })
            assignment.activity_feedback(['mail.mail_activity_data_todo'])

    @api.model
    def cron_update_overdue_and_send_reminders(self):
        today = fields.Date.context_today(self)
        pending = self.search([
            ('required', '=', True),
            ('acknowledged_date', '=', False),
        ])

        overdue = pending.filtered(lambda a: a.due_date and a.due_date < today and a.status != 'overdue')
        if overdue:
            overdue.write({'status': 'overdue'})

        remindable = pending.filtered(
            lambda a: a.employee_user_id and (not a.last_reminder_date or a.last_reminder_date < today)
        )
        for assignment in remindable:
            assignment.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=assignment.employee_user_id.id,
                summary=_('Reminder: policy acknowledgment pending'),
                note=_(
                    'Please acknowledge %(policy)s (version %(version)s).',
                    policy=assignment.document_id.name,
                    version=assignment.version_id.version_number,
                ),
                date_deadline=assignment.due_date,
            )
            assignment.last_reminder_date = today

    def action_mark_pending(self):
        for assignment in self.filtered(lambda a: not a.acknowledged_date and a.required):
            assignment.write({'status': 'pending'})
