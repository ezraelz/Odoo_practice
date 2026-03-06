from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PolicyVersion(models.Model):
    _name = 'policy.version'
    _description = 'Policy Version'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'effective_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    document_id = fields.Many2one('policy.document', required=True, ondelete='cascade', tracking=True)
    category_id = fields.Many2one(related='document_id.category_id', store=True)
    version_number = fields.Char(required=True, tracking=True)
    effective_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ], default='draft', required=True, tracking=True)
    change_summary = fields.Text(tracking=True)
    policy_file = fields.Binary(attachment=True)
    filename = fields.Char()

    mandatory_ack = fields.Boolean(default=True, string='Mandatory Acknowledgment', tracking=True)
    ack_deadline_days = fields.Integer(default=7, string='Acknowledgment Deadline (Days)', tracking=True)

    target_scope = fields.Selection([
        ('all', 'All Employees'),
        ('department', 'Departments'),
        ('job', 'Job Positions'),
        ('employment_type', 'Employment Types'),
    ], default='all', required=True, tracking=True)
    department_ids = fields.Many2many('hr.department', string='Departments')
    job_ids = fields.Many2many('hr.job', string='Job Positions')
    employment_type_ids = fields.Many2many('policy.employee.type', string='Employment Types')

    assignment_ids = fields.One2many('policy.assignment', 'version_id', string='Assignments')
    assignment_count = fields.Integer(compute='_compute_assignment_stats')
    pending_count = fields.Integer(compute='_compute_assignment_stats')
    overdue_count = fields.Integer(compute='_compute_assignment_stats')
    acknowledged_count = fields.Integer(compute='_compute_assignment_stats')

    _sql_constraints = [
        ('policy_version_unique', 'unique(document_id, version_number)', 'Version number must be unique per policy.'),
    ]

    @api.depends('document_id', 'version_number')
    def _compute_name(self):
        for version in self:
            doc_name = version.document_id.name or ''
            if version.version_number:
                version.name = f"{doc_name} - v{version.version_number}"
            else:
                version.name = doc_name

    def _compute_assignment_stats(self):
        for version in self:
            assignments = version.assignment_ids
            version.assignment_count = len(assignments)
            version.pending_count = len(assignments.filtered(lambda a: a.status == 'pending'))
            version.overdue_count = len(assignments.filtered(lambda a: a.status == 'overdue'))
            version.acknowledged_count = len(assignments.filtered(lambda a: a.status == 'acknowledged'))

    def _get_target_domain(self):
        self.ensure_one()
        domain = [('active', '=', True)]
        if self.target_scope == 'department':
            domain.append(('department_id', 'in', self.department_ids.ids))
        elif self.target_scope == 'job':
            domain.append(('job_id', 'in', self.job_ids.ids))
        elif self.target_scope == 'employment_type':
            domain.append(('employee_type', 'in', self.employment_type_ids.mapped('code')))
        return domain

    def _employee_matches_scope(self, employee):
        self.ensure_one()
        if self.target_scope == 'all':
            return True
        if self.target_scope == 'department':
            return employee.department_id in self.department_ids
        if self.target_scope == 'job':
            return employee.job_id in self.job_ids
        if self.target_scope == 'employment_type':
            return employee.employee_type in self.employment_type_ids.mapped('code')
        return False

    def _prepare_assignment_vals(self, employee):
        self.ensure_one()
        due_date = False
        if self.mandatory_ack and self.ack_deadline_days >= 0:
            due_date = self.effective_date + timedelta(days=self.ack_deadline_days)
        return {
            'version_id': self.id,
            'employee_id': employee.id,
            'required': self.mandatory_ack,
            'assigned_date': fields.Date.context_today(self),
            'due_date': due_date,
        }

    def _assign_employees(self, employees=None):
        assignment_model = self.env['policy.assignment']
        for version in self:
            target_employees = employees if employees is not None else self.env['hr.employee'].search(version._get_target_domain())
            if not target_employees:
                continue
            existing = assignment_model.search([
                ('version_id', '=', version.id),
                ('employee_id', 'in', target_employees.ids),
            ])
            existing_employee_ids = set(existing.mapped('employee_id').ids)
            create_vals = [
                version._prepare_assignment_vals(employee)
                for employee in target_employees
                if employee.id not in existing_employee_ids
            ]
            if create_vals:
                assignment_model.create(create_vals)

    def action_activate(self):
        for version in self:
            if version.state == 'active':
                continue
            siblings = self.search([
                ('document_id', '=', version.document_id.id),
                ('state', '=', 'active'),
                ('id', '!=', version.id),
            ])
            if siblings:
                siblings.write({'state': 'archived'})
            version.write({'state': 'active'})
            version._assign_employees()

    def action_archive(self):
        self.write({'state': 'archived'})

    def action_assign_now(self):
        for version in self:
            if version.state != 'active':
                raise UserError(_('Only active policies can be assigned.'))
            version._assign_employees()

    def write(self, vals):
        tracked_fields = {'mandatory_ack', 'ack_deadline_days', 'target_scope', 'department_ids', 'job_ids', 'employment_type_ids'}
        res = super().write(vals)

        changed = tracked_fields & set(vals.keys())
        if changed:
            for version in self.filtered(lambda v: v.state == 'active'):
                if {'mandatory_ack', 'ack_deadline_days'} & changed:
                    due_date = False
                    if version.mandatory_ack and version.ack_deadline_days >= 0:
                        due_date = version.effective_date + timedelta(days=version.ack_deadline_days)
                    updatable = version.assignment_ids.filtered(lambda a: not a.acknowledged_date)
                    if updatable:
                        updatable.write({'required': version.mandatory_ack, 'due_date': due_date})
                if {'target_scope', 'department_ids', 'job_ids', 'employment_type_ids'} & changed:
                    version._assign_employees()

        if vals.get('state') == 'active':
            self._assign_employees()

        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered(lambda v: v.state == 'active')._assign_employees()
        return records
