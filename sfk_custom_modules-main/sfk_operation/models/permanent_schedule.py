# python
from odoo import models, fields, api, exceptions
from datetime import timedelta, datetime

class SfkPermanentSchedule(models.Model):
    _name = "sfk.permanent.schedule"
    _description = "Permanent Class Schedule (template)"
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name')
    name = fields.Char(string="Reference", required=False)
    program_id = fields.Many2one('sfk.program', required=True, ondelete='cascade')
    program_type = fields.Selection(related='program_id.program_type')
    
    # Made optional for center-based
    term_id = fields.Many2one('sfk.term', string="Term", domain="[('program_id', '=', program_id)]")
    
    grade = fields.Char(string="Grade/Class")
    course_id = fields.Many2one('sfk_operation.course', string="Course", compute='_compute_course_id', store=True, readonly=False)
    available_course_ids = fields.Many2many(
        'sfk_operation.course',
        compute='_compute_available_course_ids',
        string="Available Courses"
    )
    
    lead_instructor_id = fields.Many2one('hr.employee', string="Lead Instructor", required=True)
    assistant_instructor_id = fields.Many2one('hr.employee', string="Assistant Instructor")

    student_count = fields.Integer(string="Number of Students")
    center_id = fields.Many2one('res.company', string="Center", default=lambda self: self.env.company)
    
    weekday = fields.Selection([
        ('0','Monday'),('1','Tuesday'),('2','Wednesday'),('3','Thursday'),
        ('4','Friday'),('5','Saturday'),('6','Sunday')
    ], required=True)
    start_time = fields.Float(string="Start Time", help="e.g. 14.5 for 14:30")
    end_time = fields.Float(string="End Time", help="e.g. 16.5 for 16:30")
    duration_hours = fields.Float(string="Duration", compute='_compute_duration', store=True, readonly=False)
    
    room_id = fields.Many2one('sfk.room', domain="[('company_id', '=', center_id)]")

    @api.depends('program_id')
    def _compute_available_course_ids(self):
        all_courses = self.env['sfk_operation.course'].search([])
        for rec in self:
            rec.available_course_ids = rec.program_id.course_ids or all_courses

    @api.depends('term_id', 'grade', 'program_type')
    def _compute_course_id(self):
        for rec in self:
            if rec.program_type == 'school':
                if rec.term_id and rec.grade:
                    mapping = self.env['sfk.term.course'].search([
                        ('term_id', '=', rec.term_id.id),
                        ('grade', '=', rec.grade)
                    ], limit=1)
                    rec.course_id = mapping.course_id if mapping else False
                else:
                    rec.course_id = False

    @api.depends('course_id', 'grade', 'weekday', 'program_type')
    def _compute_display_name(self):
        for rec in self:
            day = dict(self._fields['weekday'].selection).get(rec.weekday, '')
            if rec.program_type == 'school':
                rec.display_name = f"{rec.grade or ''} - {rec.course_id.name or 'No Course'} ({day})"
            else:
                rec.display_name = f"{rec.course_id.name or 'New Schedule'} ({day})"

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            if rec.end_time and rec.start_time:
                rec.duration_hours = rec.end_time - rec.start_time
            else:
                rec.duration_hours = 0.0

    @api.onchange('start_time', 'duration_hours')
    def _onchange_end_time(self):
        if self.start_time and self.duration_hours:
            self.end_time = self.start_time + self.duration_hours

    def _next_date_from_weekday(self, start_dt, weekday_int):
        days_ahead = (weekday_int - start_dt.weekday() + 7) % 7
        return start_dt + timedelta(days=days_ahead)

    def generate_sessions(self, start_date, end_date):
        Session = self.env['sfk.session']
        start_dt = fields.Date.to_date(start_date) if isinstance(start_date, str) else start_date
        end_dt = fields.Date.to_date(end_date) if isinstance(end_date, str) else end_date
        
        for tmpl in self:
            if not tmpl.course_id:
                continue
            
            weekday_int = int(tmpl.weekday)
            current = tmpl._next_date_from_weekday(start_dt, weekday_int)
            while current <= end_dt:
                hour = int(tmpl.start_time)
                minute = int((tmpl.start_time - hour) * 60)
                start_datetime = fields.Datetime.to_datetime(datetime.combine(current, datetime.min.time())) \
                                 .replace(hour=hour, minute=minute)
                end_datetime = start_datetime + timedelta(hours=tmpl.duration_hours)
                
                exists = Session.search([
                    ('program_id', '=', tmpl.program_id.id),
                    ('course_id', '=', tmpl.course_id.id),
                    ('start_datetime', '=', start_datetime),
                    ('room_id', '=', tmpl.room_id.id),
                ], limit=1)
                
                if not exists:
                    Session.create({
                        'name': f"{tmpl.course_id.name} - {current.isoformat()}",
                        'program_id': tmpl.program_id.id,
                        'center_id': tmpl.center_id.id,
                        'term_id': tmpl.term_id.id if tmpl.program_type == 'school' else False,
                        'course_id': tmpl.course_id.id,
                        'grade': tmpl.grade,
                        'start_datetime': start_datetime,
                        'end_datetime': end_datetime,
                        'room_id': tmpl.room_id.id,
                        'manager_id': tmpl.program_id.manager_id.id,
                        'supervisor_id': tmpl.program_id.supervisor_id.id,
                        'lead_instructor_id': tmpl.lead_instructor_id.id,
                        'assistant_instructor_id': tmpl.assistant_instructor_id.id,
                    })
                current = current + timedelta(days=7)
