# python
from odoo import models, fields, api, exceptions
from datetime import datetime

class SfkSession(models.Model):
    _name = "sfk.session"
    _description = "Program Session"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(required=True, tracking=True)
    program_id = fields.Many2one('sfk.program', required=True, ondelete='cascade', tracking=True)
    program_type = fields.Selection(related='program_id.program_type', store=True)
    center_id = fields.Many2one('res.company', string="Center/Branch", required=True, tracking=True)
    
    # Made optional
    term_id = fields.Many2one('sfk.term', string="Term", tracking=True)
    
    course_id = fields.Many2one('sfk_operation.course', required=True, tracking=True)
    grade = fields.Char(string="Grade (for School-based)", tracking=True)

    start_datetime = fields.Datetime(required=True, tracking=True)
    end_datetime = fields.Datetime(required=True, tracking=True)
    room_id = fields.Many2one('sfk.room', tracking=True)
    lead_instructor_id = fields.Many2one('hr.employee', string="Lead Instructor", tracking=True)
    assistant_instructor_id = fields.Many2one('hr.employee', string="Assistant Instructor", tracking=True)
    manager_id = fields.Many2one('res.users', string='Manager', tracking=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor', tracking=True)
    
    attendance_ids = fields.One2many('sfk.attendance', 'session_id')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)

    execution_state = fields.Selection([
        ('conducted', 'Conducted'),
        ('not_conducted', 'Not Conducted'),
        ('rescheduled', 'Rescheduled')
    ], string="Execution Status", default='conducted', tracking=True)
    reason_not_conducted = fields.Text(string="Reason (if not conducted)", tracking=True)
    school_student_count = fields.Integer(string="Total Students Present (School-based)", help="Use this to track headcount for school-based programs", tracking=True)

    lead_instructor_status = fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('substituted', 'Substituted')
    ], string="Lead Instructor Status", default='present', tracking=True)
    lead_substitute_id = fields.Many2one('hr.employee', string="Lead Substitute", tracking=True)
    
    assistant_instructor_status = fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('substituted', 'Substituted')
    ], string="Assistant Instructor Status", default='present', tracking=True)
    assistant_substitute_id = fields.Many2one('hr.employee', string="Assistant Substitute", tracking=True)

    # Workflow Fields
    attendance_state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved')
    ], default='draft', string="Attendance Status", tracking=True)

    # Lead Instructor Class Assessment (Class Level)
    class_lesson_completion = fields.Selection([
        ('full', 'Fully Completed'),
        ('partial', 'Partially Completed'),
        ('not_covered', 'Not Covered')
    ], string="Lesson Completion")
    class_engagement_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string="Student Engagement")
    class_topic_coverage = fields.Text(string="Topic Coverage Details")
    class_challenges = fields.Text(string="Challenges Faced")
    class_understanding = fields.Selection([
        ('poor', 'Poor'),
        ('fair', 'Fair'),
        ('good', 'Good'),
        ('excellent', 'Excellent')
    ], string="General Class Understanding")

    # Supervisor Evaluation (Instructor & Session Level)
    eval_effectiveness = fields.Selection([
        ('needs_improvement', 'Needs Improvement'),
        ('satisfactory', 'Satisfactory'),
        ('exceeds_expectations', 'Exceeds Expectations')
    ], string="Instructional Effectiveness")
    eval_punctuality = fields.Selection([
        ('on_time', 'On Time'),
        ('late', 'Late'),
        ('very_late', 'Very Late')
    ], string="Punctuality")
    eval_professionalism = fields.Selection([
        ('poor', 'Poor'),
        ('good', 'Good'),
        ('excellent', 'Excellent')
    ], string="Professionalism")
    eval_curriculum_adherence = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string="Curriculum Adherence")
    eval_delivery_standards = fields.Text(string="Overall Delivery Standards")

    evaluation_state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved')
    ], default='draft', string="Evaluation Status")

    is_validated = fields.Boolean(string="Validated by Coach Manager", default=False, copy=False)
    
    is_future_session = fields.Boolean(compute='_compute_is_future_session', string="Is Future Session")

    @api.depends('start_datetime')
    def _compute_is_future_session(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_future_session = bool(rec.start_datetime and rec.start_datetime.date() > today)

    requested_lead_instructor_id = fields.Many2one('hr.employee', string="Requested Lead Instructor")
    requested_assistant_instructor_id = fields.Many2one('hr.employee', string="Requested Assistant Instructor")

    attendance_count = fields.Integer(compute='_compute_attendance_count', string="Present Count")
    attendance_total = fields.Integer(compute='_compute_attendance_count', string="Total Students")
    attendance_progress = fields.Float(compute='_compute_attendance_count', string="Attendance Progress")

    @api.depends('attendance_ids.status')
    def _compute_attendance_count(self):
        for rec in self:
            rec.attendance_total = len(rec.attendance_ids)
            rec.attendance_count = len(rec.attendance_ids.filtered(lambda a: a.status == 'present'))
            rec.attendance_progress = (rec.attendance_count / rec.attendance_total * 100) if rec.attendance_total > 0 else 0.0

    @api.constrains('start_datetime','end_datetime','room_id','lead_instructor_id', 'assistant_instructor_id')
    def _check_conflicts(self):
        for rec in self:
            if rec.start_datetime >= rec.end_datetime:
                raise exceptions.ValidationError("Session end must be after start.")
            if rec.room_id:
                overlapping = self.search([
                    ('id', '!=', rec.id),
                    ('room_id', '=', rec.room_id.id),
                    ('start_datetime', '<', rec.end_datetime),
                    ('end_datetime', '>', rec.start_datetime),
                    ('state', '!=', 'cancelled'),
                ], limit=1)
                if overlapping:
                    raise exceptions.ValidationError("Room is occupied for another session during this time.")
            
            instructors = []
            if rec.lead_instructor_id:
                instructors.append(rec.lead_instructor_id)
            if rec.assistant_instructor_id:
                instructors.append(rec.assistant_instructor_id)
            
            for instr in instructors:
                conflict = self.search([
                    ('id', '!=', rec.id),
                    '|',
                    ('lead_instructor_id', '=', instr.id),
                    ('assistant_instructor_id', '=', instr.id),
                    ('start_datetime', '<', rec.end_datetime),
                    ('end_datetime', '>', rec.start_datetime),
                    ('state', '!=', 'cancelled'),
                ], limit=1)
                if conflict:
                    raise exceptions.ValidationError(f"Instructor {instr.name} has another session at this time.")

    def action_load_students(self):
        self.ensure_one()
        if self.program_type != 'center':
            return
            
        Attendance = self.env['sfk.attendance']
        Enrollment = self.env['sfk.enrollment']
        # Load active students registered in this program via enrollment.
        students = Enrollment.search([
            ('program_id', '=', self.program_id.id),
            ('status', '=', 'active'),
            ('student_id.status', '=', 'active'),
        ]).mapped('student_id')
        # Backward-compatible fallback for old data with no enrollment lines.
        if not students:
            students = self.env['sfk.student'].search([
                ('program_id', '=', self.program_id.id),
                ('status', '=', 'active')
            ])
        
        for student in students:
            existing = Attendance.search([
                ('session_id', '=', self.id),
                ('student_id', '=', student.id)
            ], limit=1)
            if not existing:
                Attendance.create({
                    'session_id': self.id,
                    'student_id': student.id,
                    'status': 'absent'
                })

    def write(self, vals):
        # Prevent instructor modification by non-managers directly if enforced strictly
        # But here we rely on UI readonly.
        
        if any(rec.state == 'done' for rec in self):
            forbidden = set(vals.keys()) - {'notes', 'execution_state', 'reason_not_conducted'}
            if forbidden:
                raise exceptions.UserError("Cannot modify sessions in state 'done'.")
        return super().write(vals)

    def action_confirm(self):
        for rec in self:
            if not rec.start_datetime:
                raise exceptions.UserError("Session start time is required before confirmation.")
            if rec.start_datetime.date() > fields.Date.today():
                raise exceptions.UserError("You cannot confirm or load attendance for a session before its scheduled date.")
        self.write({'state': 'confirmed'})
        for rec in self:
            if rec.program_type == 'center':
                rec.action_load_students()

    def action_submit_attendance(self):
        for rec in self:
            if not rec.start_datetime:
                raise exceptions.UserError("Session start time is required before attendance submission.")
            if rec.start_datetime.date() > fields.Date.today():
                raise exceptions.UserError("You cannot submit attendance for a session before its scheduled date.")
            if rec.program_type == 'school' and not self.env.user.has_group('sfk_operation.group_sfk_coach_manager'):
                raise exceptions.AccessError("Only Coach Managers can manage attendance for school-based programs.")
            
            rec.attendance_state = 'submitted'
            # If a supervisor submits, it needs validation from Coach Manager
            if self.env.user.has_group('sfk_operation.group_sfk_supervisor') and not self.env.user.has_group('sfk_operation.group_sfk_coach_manager'):
                rec.is_validated = False
            else:
                rec.is_validated = True

    def action_approve_attendance(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_coach_manager'):
            raise exceptions.AccessError("Only Coach Managers can approve attendance.")
        self.write({'attendance_state': 'approved', 'is_validated': True})

    def action_submit_evaluation(self):
        for rec in self:
            if not all([rec.class_lesson_completion, rec.class_engagement_level, rec.class_topic_coverage, rec.class_understanding]):
                raise exceptions.UserError("Please complete all Lead Instructor Class Assessment fields before submitting.")
        self.write({'evaluation_state': 'submitted'})

    def action_approve_evaluation(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_coach_manager'):
            raise exceptions.AccessError("Only Coach Managers can approve evaluations.")
        self.write({'evaluation_state': 'approved'})

    def action_validate(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_coach_manager'):
            raise exceptions.AccessError("Only Coach Managers can validate actions.")
        self.write({'is_validated': True})

    def action_approve_instructor_change(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_manager'):
            raise exceptions.AccessError("Only Operation Managers can approve instructor changes.")
        for rec in self:
            updates = {}
            if rec.requested_lead_instructor_id:
                updates['lead_instructor_id'] = rec.requested_lead_instructor_id.id
                updates['requested_lead_instructor_id'] = False
            if rec.requested_assistant_instructor_id:
                updates['assistant_instructor_id'] = rec.requested_assistant_instructor_id.id
                updates['requested_assistant_instructor_id'] = False
            if updates:
                rec.write(updates)

    def action_reject_instructor_change(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_manager'):
            raise exceptions.AccessError("Only Operation Managers can reject instructor changes.")
        self.write({
            'requested_lead_instructor_id': False,
            'requested_assistant_instructor_id': False
        })

    def action_done(self):
        for rec in self:
            if rec.program_type == 'center' and rec.attendance_state != 'approved':
                raise exceptions.UserError("Attendance must be approved by the Coach Manager before marking session as Done.")
            
            if not rec.is_validated and not self.env.user.has_group('sfk_operation.group_sfk_coach_manager'):
                raise exceptions.UserError("This session requires validation by a Coach Manager before it can be finalized.")
                
        self.write({'state': 'done', 'is_validated': True})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
