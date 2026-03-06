# python
from odoo import models, fields, api, exceptions

class SfkAttendance(models.Model):
    _name = "sfk.attendance"
    _description = "Student Attendance"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    session_id = fields.Many2one('sfk.session', required=True, ondelete='cascade', tracking=True)
    student_id = fields.Many2one('sfk.student', required=True, tracking=True)
    status = fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused')
    ], string="Status", default='absent', tracking=True)
    notes = fields.Char(string="Notes", tracking=True)
    checked_by = fields.Many2one('res.users', string="Recorded By")
    checked_date = fields.Datetime(string="Recorded On")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('checked_by', self.env.uid)
            vals.setdefault('checked_date', fields.Datetime.now())
            self._check_student_eligibility(vals.get('session_id'), vals.get('student_id'))
        return super().create(vals_list)

    def write(self, vals):
        if 'student_id' in vals or 'session_id' in vals:
            for rec in self:
                sid = vals.get('session_id', rec.session_id.id)
                stid = vals.get('student_id', rec.student_id.id)
                self._check_student_eligibility(sid, stid)
        return super().write(vals)

    def _check_student_eligibility(self, session_id, student_id):
        if not session_id or not student_id:
            return
        session = self.env['sfk.session'].browse(session_id)
        if not session.start_datetime:
            raise exceptions.ValidationError("Session start time is missing; attendance cannot be recorded.")
        if session.start_datetime.date() > fields.Date.today():
            raise exceptions.ValidationError("Attendance cannot be recorded or modified before the session's scheduled date.")
            
        if session.program_type == 'center':
            # Center-based: Just check if the student belongs to the program
            student = self.env['sfk.student'].search([
                ('id', '=', student_id),
                ('program_id', '=', session.program_id.id),
                ('status', '=', 'active')
            ], limit=1)
            if not student:
                student_obj = self.env['sfk.student'].browse(student_id)
                raise exceptions.ValidationError(
                    f"Student {student_obj.name} is not an active student of the program: {session.program_id.name}"
                )
