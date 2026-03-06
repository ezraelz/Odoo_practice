# python
from odoo import models, fields, api, exceptions

class SfkProgram(models.Model):
    _name = "sfk.program"
    _description = "Program"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    course_ids = fields.Many2many('sfk_operation.course', string='Available Courses', required=True, tracking=True)
    program_type = fields.Selection([('center','Center-based'), ('school','School-based')], default='center', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Branch', default=lambda self: self.env.company, tracking=True)
    start_date = fields.Date(required=True, tracking=True)
    end_date = fields.Date(required=True, tracking=True)
    
    coach_id = fields.Many2one('hr.employee', string='Coach', tracking=True)
    manager_id = fields.Many2one('res.users', string='Manager', tracking=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('closed', 'Closed')
    ], default='draft', string="Status", tracking=True)

    max_student_capacity = fields.Integer(string="Maximum Student Capacity")
    default_room_id = fields.Many2one('sfk.room', string="Default Room")
    age_group = fields.Char(string="Age Group")

    school_name = fields.Char(string="School Name")
    school_location = fields.Char(string="School Location")
    grade_based_indicator = fields.Boolean(string="Grade-Based", default=True)

    # Program Level Evaluation (Supervisor)
    prog_eval_consistency = fields.Text(string="Session Consistency")
    prog_eval_attendance_reliability = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string="Attendance Reliability")
    prog_eval_course_progression = fields.Selection([
        ('behind', 'Behind Schedule'),
        ('on_track', 'On Track'),
        ('ahead', 'Ahead of Schedule')
    ], string="Course Progression")
    prog_eval_operational_discipline = fields.Text(string="Operational Discipline")
    
    prog_evaluation_state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved')
    ], default='draft', string="Program Evaluation Status")

    student_ids = fields.One2many('sfk.student', 'program_id')
    enrollment_ids = fields.One2many('sfk.enrollment', 'program_id')
    session_ids = fields.One2many('sfk.session', 'program_id')
    term_ids = fields.One2many('sfk.term', 'program_id', string="Terms")
    permanent_schedule_ids = fields.One2many('sfk.permanent.schedule', 'program_id')

    student_count = fields.Integer(compute='_compute_counts', string="Students")
    session_count = fields.Integer(compute='_compute_counts', string="Sessions")
    class_count = fields.Integer(compute='_compute_counts', string="Classes")

    def _compute_counts(self):
        for rec in self:
            enrolled_students = rec.enrollment_ids.filtered(
                lambda e: e.status == 'active' and e.student_id and e.student_id.status == 'active'
            ).mapped('student_id')
            rec.student_count = len(enrolled_students) if enrolled_students else len(rec.student_ids)
            rec.session_count = len(rec.session_ids)
            rec.class_count = len(rec.permanent_schedule_ids)

    def action_view_registered_students(self):
        self.ensure_one()
        students = self.enrollment_ids.filtered(
            lambda e: e.status == 'active' and e.student_id and e.student_id.status == 'active'
        ).mapped('student_id')
        action = self.env.ref('sfk_operation.sfk_operation_student_action').read()[0]
        action['domain'] = [('id', 'in', students.ids)]
        action['context'] = {
            'default_program_id': self.id,
        }
        return action

    @api.constrains('name', 'company_id')
    def _check_unique_program_name(self):
        for rec in self:
            if not rec.name:
                continue
            name = rec.name.strip()
            domain = [
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('name', '=ilike', name),
            ]
            if self.search_count(domain):
                raise exceptions.ValidationError(
                    "A program with this name already exists in this branch."
                )

    # def write(self, vals):
    #     if any(rec.state != 'draft' for rec in self) and any(key not in ['state'] for key in vals.keys()):
    #         raise exceptions.UserError("Program can only be edited in 'Draft' state.")
    #     return super().write(vals)

    def action_run(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_manager'):
            raise exceptions.AccessError("Only Operation Managers can start a program.")
        for program in self:
            if not program.permanent_schedule_ids:
                raise exceptions.UserError("Cannot start a program with no permanent schedules defined.")
            for schedule in program.permanent_schedule_ids:
                if program.program_type == 'school':
                    if not schedule.term_id:
                        raise exceptions.UserError(f"Term is required for school-based schedule: {schedule.display_name}")
                    schedule.generate_sessions(schedule.term_id.start_date, schedule.term_id.end_date)
                else:
                    # Center-based: Use Program dates if no term
                    s_date = schedule.term_id.start_date if schedule.term_id else program.start_date
                    e_date = schedule.term_id.end_date if schedule.term_id else program.end_date
                    schedule.generate_sessions(s_date, e_date)
            program.write({'state': 'running'})

    def action_close(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_manager'):
            raise exceptions.AccessError("Only Operation Managers can close a program.")
        for program in self:
            future_sessions = self.env['sfk.session'].search([
                ('program_id', '=', program.id),
                ('start_datetime', '>', fields.Datetime.now()),
                ('state', '!=', 'cancelled')
            ])
            future_sessions.write({'state': 'cancelled'})
            program.write({'state': 'closed'})

    def action_submit_prog_evaluation(self):
        self.write({'prog_evaluation_state': 'submitted'})

    def action_approve_prog_evaluation(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_coach_manager'):
            raise exceptions.AccessError("Only Coach Managers can approve program evaluations.")
        self.write({'prog_evaluation_state': 'approved'})

class SfkEnrollment(models.Model):
    _name = "sfk.enrollment"
    _description = "Student Enrollment"

    student_id = fields.Many2one('sfk.student', required=True, ondelete='cascade')
    program_id = fields.Many2one('sfk.program', required=True, ondelete='cascade')
    center_id = fields.Many2one('res.company', string="Center/Branch", required=True, default=lambda self: self.env.company)
    
    # Made optional for center-based
    term_id = fields.Many2one('sfk.term', string="Term", domain="[('program_id', '=', program_id)]")
    
    course_id = fields.Many2one('sfk_operation.course', required=True)
    available_course_ids = fields.Many2many(
        'sfk_operation.course',
        compute='_compute_available_course_ids',
        string="Available Courses"
    )
    enrollment_date = fields.Date(default=fields.Date.context_today)
    status = fields.Selection([('active','Active'),('withdrawn','Withdrawn'),('completed','Completed')], default='active')

    @api.onchange('student_id')
    def _onchange_student_id(self):
        if self.student_id and self.student_id.program_id:
            self.program_id = self.student_id.program_id
            self.center_id = self.student_id.program_id.company_id

    def _sync_student_registration(self, vals=None):
        for rec in self:
            student = rec.student_id
            if not student:
                continue
            updates = {}
            if rec.program_id and student.program_id != rec.program_id:
                updates['program_id'] = rec.program_id.id
            if updates:
                student.write(updates)
            if rec.course_id and rec.course_id not in student.course_ids:
                student.write({'course_ids': [(4, rec.course_id.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_student_registration(vals_list)
        return records

    def write(self, vals):
        result = super().write(vals)
        if any(k in vals for k in ('student_id', 'program_id', 'course_id')):
            self._sync_student_registration(vals)
        return result

    @api.depends('program_id')
    def _compute_available_course_ids(self):
        all_courses = self.env['sfk_operation.course'].search([])
        for rec in self:
            rec.available_course_ids = rec.program_id.course_ids or all_courses

    _sql_constraints = [
        ('student_course_unique_if_no_term', 'CHECK(1=1)', 'Constraint managed via Python for conditional term logic.')
    ]

    @api.constrains('student_id', 'program_id', 'term_id', 'course_id')
    def _check_unique_enrollment(self):
        for rec in self:
            domain = [
                ('id', '!=', rec.id),
                ('student_id', '=', rec.student_id.id),
                ('program_id', '=', rec.program_id.id),
                ('course_id', '=', rec.course_id.id),
                ('term_id', '=', rec.term_id.id)
            ]
            if self.search_count(domain) > 0:
                raise exceptions.ValidationError("Student is already enrolled in this course for this term/program.")

    @api.constrains('program_id')
    def _check_capacity(self):
        for rec in self:
            if rec.program_id.program_type == 'center' and rec.program_id.max_student_capacity > 0:
                current_count = self.search_count([
                    ('program_id', '=', rec.program_id.id),
                    ('status', '=', 'active')
                ])
                if current_count > rec.program_id.max_student_capacity:
                    raise exceptions.ValidationError(f"Program capacity reached! (Max: {rec.program_id.max_student_capacity})")
