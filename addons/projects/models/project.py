from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import date_utils

class Project(models.Model):
    _name = 'pro.project'
    _description = 'Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, start_date desc, id desc'

    name = fields.Char(required=True, tracking=True)
    description = fields.Text(tracking=True)

    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        domain="[('is_company', '=', True)]",
        tracking=True
    )

    task_ids = fields.One2many(
        'pro.task',
        'project_id',
        string="Tasks"
    )
    
    sequence = fields.Integer(default=10)

    start_date = fields.Date(
        default=fields.Date.context_today,
        tracking=True
    )
    end_date = fields.Date(tracking=True)
    
    duration_days = fields.Integer(
        string='Duration (Days)',
        compute='_compute_duration',
        store=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ], default='draft', string='Status', tracking=True)

    is_locked = fields.Boolean(string='Locked', default=False, tracking=True)

    # Progress calculation from tasks
    task_progress = fields.Float(
        string='Progress',
        compute='_compute_task_progress',
        store=True,
        group_operator="avg"
    )

    color = fields.Integer(string='Color Index')

    # Compute duration between start and end date
    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for project in self:
            if project.start_date and project.end_date:
                delta = project.end_date - project.start_date
                project.duration_days = delta.days
            else:
                project.duration_days = 0

    # Compute progress based on completed tasks
    @api.depends('task_ids.is_completed')
    def _compute_task_progress(self):
        for project in self:
            if project.task_ids:
                completed_tasks = project.task_ids.filtered('is_completed')
                project.task_progress = (len(completed_tasks) / len(project.task_ids)) * 100
            else:
                project.task_progress = 0

    # Prevent modification if locked
    def write(self, vals):
        for record in self:
            if record.is_locked and 'is_locked' not in vals:
                if not (self.env.user == record.create_uid or self.env.is_superuser()):
                    raise UserError("This project is locked and cannot be modified.")
        return super().write(vals)

    # Prevent deletion if locked
    def unlink(self):
        for record in self:
            if record.is_locked:
                if not (self.env.user == record.create_uid or self.env.is_superuser()):
                    raise UserError("This project is locked and cannot be deleted.")
        return super().unlink()

    # Action methods
    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})


class ProjectTask(models.Model):
    _name = 'pro.task'
    _description = 'Project Task'
    _order = 'project_id, sequence, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    description = fields.Text(tracking=True)

    sequence = fields.Integer(default=10)

    project_id = fields.Many2one(
        'pro.project',
        string='Project',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    assigned_to = fields.Many2one(
        'res.users',
        string='Assigned To',
        default=lambda self: self.env.user,
        tracking=True
    )

    parent_task_id = fields.Many2one(
        'pro.task', 
        string='Parent Task',
        index=True
    )
    
    child_task_ids = fields.One2many(
        'pro.task', 
        'parent_task_id', 
        string='Subtasks'
    )

    due_date = fields.Date(tracking=True)

    # FIXED: stage_id field with proper group_expand
    stage_id = fields.Many2one(
        'pro.task.stage',
        string="Stage",
        default=lambda self: self._get_default_stage_id(),
        group_expand='_read_group_stage_ids',  # This references the method
        tracking=True,
        required=False
    )

    is_completed = fields.Boolean(
        string="Completed",
        compute="_compute_is_completed",
        store=True,
        tracking=True
    )

    color = fields.Integer(string='Color Index')

    @api.model
    def create(self, vals):
        """Ensure at least one stage exists when creating first task"""
        if not self.env['pro.task.stage'].search_count([]):
            # Create default stages if none exist
            self.env['pro.task.stage'].create([
                {'name': 'To Do', 'sequence': 10, 'fold': False, 'is_done': False},
                {'name': 'In Progress', 'sequence': 20, 'fold': False, 'is_done': False},
                {'name': 'Done', 'sequence': 30, 'fold': True, 'is_done': True},
            ])
        return super().create(vals)

    def _get_default_stage_id(self):
        """Safely get default stage - returns False if no stages exist"""
        try:
            stage = self.env['pro.task.stage'].search([], order='sequence', limit=1)
            return stage.id if stage else False
        except:
            return False

    # SIMPLIFIED: This method MUST be here and have the correct signature
    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return self.env['pro.task.stage'].search([], order='sequence')
    
    @api.depends('stage_id')
    def _compute_is_completed(self):
        for task in self:
            task.is_completed = task.stage_id.is_done if task.stage_id else False

    def write(self, vals):
        for record in self:
            if record.project_id and record.project_id.is_locked:
                if not (self.env.user == record.project_id.create_uid or self.env.is_superuser()):
                    raise UserError("The project is locked. You cannot modify tasks in a locked project.")
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.project_id and record.project_id.is_locked:
                if not (self.env.user == record.project_id.create_uid or self.env.is_superuser()):
                    raise UserError("The project is locked. You cannot delete tasks from a locked project.")
        return super().unlink()
    
    def action_assign_to_me(self):
        """Assign the current user to the task"""
        for record in self:
            if not record.project_id.is_locked:
                record.write({'assigned_to': self.env.uid})
            else:
                raise UserError("Cannot assign task: The project is locked.")
        return True

    def action_mark_completed(self):
        """Mark task as completed by moving to done stage"""
        done_stage = self.env['pro.task.stage'].search([('is_done', '=', True)], limit=1)
        if not done_stage:
            raise UserError("No 'Completed' stage found. Please configure task stages first.")
        
        for record in self:
            if not record.project_id.is_locked:
                record.write({'stage_id': done_stage.id})
            else:
                raise UserError("Cannot complete task: The project is locked.")
        return True
    
class ProjectTaskStage(models.Model):
    _name = 'pro.task.stage'
    _description = 'Task Stage'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    
    description = fields.Text(translate=True)

    sequence = fields.Integer(default=10)

    fold = fields.Boolean(
        string="Folded in Kanban",
        help="This stage will be folded in kanban view when there are no records."
    )

    is_done = fields.Boolean(
        string="Completed Stage",
        help="Tasks in this stage are considered completed."
    )
    
    color = fields.Integer(string='Color Index')
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    # Add constraint to ensure at least one stage exists
    #_sql_constraints = [
    #    ('name_uniq', 'unique (name)', 'Stage name must be unique!')
    #]