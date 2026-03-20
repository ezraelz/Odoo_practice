# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


# ---------------------------------------------------------
# Task Stages
# ---------------------------------------------------------
class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    is_completed = fields.Boolean(
        string="Completed Stage",
        help="Task is finished and waiting for approval."
    )

    is_done = fields.Boolean(
        string="Done Stage",
        help="Final approved stage."
    )

    project_ids = fields.Many2many(
        'project.project',
        string='Projects'
    )

    weight = fields.Integer(
        string='Weight',
        help='Custom field to determine stage order and progression logic.',
        default=10,
    )

    @api.constrains('is_completed', 'is_done')
    def _check_stage_flags(self):
        for stage in self:
            if stage.is_completed and stage.is_done:
                raise UserError(
                    _("A stage cannot be both Completed and Done.")
                )


# ---------------------------------------------------------
# Project
# ---------------------------------------------------------
class Project(models.Model):
    _inherit = 'project.project'

    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        domain="[('is_company', '=', True)]",
        tracking=True
    )

    task_progress = fields.Float(
        string='Progress (%)',
        compute='_compute_task_progress',
        store=True
    )

    state = fields.Selection(
        [
            ('open', 'In Progress'),
            ('done', 'Done'),
        ],
        compute='_compute_project_state',
        store=True,
        tracking=True
    )

    @api.model
    def create_default_stages(self, project):
        """Create default stages for a new project if they don't exist."""
        TaskType = self.env['project.task.type']

        # Define stages with flags
        default_stages = [
            {'name': 'Backlog', 'sequence': 10, 'fold': False, 'is_completed': False, 'is_done': False, 'weight': 10},
            {'name': 'In Progress', 'sequence': 20, 'fold': False, 'is_completed': False, 'is_done': False, 'weight': 20},
            {'name': 'On Hold', 'sequence': 30, 'fold': True, 'is_completed': False, 'is_done': False, 'weight': 30},
            {'name': 'Completed', 'sequence': 40, 'fold': True, 'is_completed': True, 'is_done': False, 'weight': 40},
            {'name': 'Done', 'sequence': 50, 'fold': True, 'is_completed': False, 'is_done': True, 'weight': 50},
        ]

        for stage_vals in default_stages:
            # Ensure unique stage per project
            stage = TaskType.search([
                ('name', '=', stage_vals['name']),
                ('project_ids', '=', project.id)
            ], limit=1)
            if not stage:
                TaskType.create({
                    **stage_vals,
                    'project_ids': [(4, project.id)]
                })


    @api.model
    def create(self, vals):
        project = super().create(vals)
        # Create default stages for this new project
        self.create_default_stages(project)
        return project
    
    # -----------------------------
    # COMPUTES
    # -----------------------------
    @api.depends('task_ids.stage_id.is_done', 'task_ids.stage_id.weight')
    def _compute_project_state(self):
        for project in self:
            if project.task_ids and all(t.stage_id.is_done for t in project.task_ids):
                project.state = 'done'
            elif project.task_ids and all(t.stage_id.weight < 40 for t in project.task_ids):
                project.state = 'open'
            else:
                project.state = 'open'

    @api.depends('task_ids.stage_id.weight')
    def _compute_task_progress(self):
        for project in self:
            tasks = project.task_ids
            if not tasks:
                project.task_progress = 0.0
                continue

            # Total weight of all tasks based on stage
            total_weight = sum(t.stage_id.weight for t in tasks)
            # Maximum possible weight per task
            stage = project.env['project.task.type'].search([], order='weight desc', limit=1)
            max_weight = stage.weight if stage else 50
            max_total_weight = len(tasks) * max_weight

            project.task_progress = (total_weight / max_total_weight) * 100


# ---------------------------------------------------------
# Task
# ---------------------------------------------------------
class ProjectTask(models.Model):
    _inherit = 'project.task'

    description = fields.Text(
        string='Admin Description',
        help="Admins can describe the task here."
    )

    progress = fields.Float(
        string='Progress (%)',
        help="Progress of the task, editable by admins only.",
        compute='_compute_progress',
        readonly=True,
        store=True
    )

    previous_stage_id = fields.Many2one(
        'project.task.type',
        string='Previous Stage',
        compute='_compute_previous_stage',
        store=True
    )

    stage_weight = fields.Integer(
        string='Stage Weight',
        help="Weight for this task (default from stage, editable by admin)",
        compute='_compute_stage_weight',
        inverse='_inverse_stage_weight',
        store=True
    )

    # -----------------------------
    # COMPUTES
    # -----------------------------
    @api.depends('stage_id')
    def _compute_previous_stage(self):
        for task in self:
            task.previous_stage_id = task.stage_id

    @api.depends('stage_id', 'stage_id.weight')
    def _compute_stage_weight(self):
        for task in self:
            # Default: use stage weight
            task.stage_weight = task.stage_id.weight if task.stage_id else 0

    def _inverse_stage_weight(self):
        for task in self:
            stage = self.env['project.task.type'].search([], order='weight desc', limit=1)
            max_weight = stage.weight if stage else 50
            task.progress = (task.stage_weight / max_weight) * 100

    @api.depends('stage_weight')
    def _compute_progress(self):
        stage = self.env['project.task.type'].search([], order='weight desc', limit=1)
        max_weight = stage.weight if stage else 50
        for task in self:
            task.progress = (task.stage_weight / max_weight) * 100

    # -----------------------------
    # HELPERS
    # -----------------------------
    def _is_admin_or_manager(self):
        user = self.env.user
        return (
            user.has_group('project.group_project_manager') or
            user.has_group('base.group_system')
        )

    # -----------------------------
    # WRITE OVERRIDE
    # -----------------------------
    def write(self, vals):
        if 'description' in vals:
            for task in self:
                if not self._is_admin_or_manager():
                    raise UserError(_("Only administrators or task creators can edit the description."))

        if 'stage_id' in vals:
            for task in self:
                new_stage = self.env['project.task.type'].browse(vals['stage_id'])
                old_stage = task.stage_id
                user = self.env.user

                is_admin = task._is_admin_or_manager()
                is_assigner = (task.create_uid == user)

                # 🚫 No backward movement
                if (
                    not is_admin
                    and old_stage
                    and new_stage.sequence < old_stage.sequence
                ):
                    raise UserError(_("You cannot move a task backward."))

                # 🚫 Must pass through Completed before Done
                if (
                    new_stage.is_done
                    and not is_admin
                    and (not old_stage or not old_stage.is_completed)
                ):
                    raise UserError(
                        _("Tasks must be in the Completed stage before moving to Done.")
                    )

                # 🚫 Only assigner or admin can approve Done
                if (
                    old_stage
                    and old_stage.is_completed
                    and new_stage.is_done
                    and not (is_assigner or is_admin)
                ):
                    raise UserError(
                        _("Only the task assigner (%s) can approve this task.")
                        % task.create_uid.name
                    )

                # 🚫 Only assigned users can move tasks
                if not is_admin and user not in task.user_ids:
                    raise UserError(
                        _("You can only move tasks assigned to you.")
                    )

                # Update task-level weight only if it was equal to old stage weight
                if task.stage_weight == (old_stage.weight if old_stage else 0):
                    task.stage_weight = new_stage.weight

                # Update progress
                stage = self.env['project.task.type'].search([], order='weight desc', limit=1)
                max_weight = stage.weight if stage else 50
                task.progress = (task.stage_weight / max_weight) * 100

        return super().write(vals)

    # -----------------------------
    # APPROVAL ACTION
    # -----------------------------
    def action_approve_done(self):
        done_stage = self.env['project.task.type'].search(
            [('is_done', '=', True)],
            limit=1
        )
        if not done_stage:
            raise UserError(_("Done stage is not configured."))

        for task in self:
            if not task.stage_id.is_completed:
                raise UserError(_("Task must be in the Completed stage."))

            if task.create_uid != self.env.user:
                raise UserError(_("Only the task assigner can approve this task."))

            task.stage_id = done_stage.id
