# python
from odoo import models, fields, api
from datetime import date

class SfkStudent(models.Model):
    _name = "sfk.student"
    _description = "Student"
    _rec_name = 'name'

    name = fields.Char(string="Full Name", required=True)
    date_of_birth = fields.Date(string="Date of Birth", required=True)
    age = fields.Integer(string="Age", compute='_compute_age')
    parent_name = fields.Char(string="Parent/Guardian Name")
    parent_phone = fields.Char(string="Parent/Guardian Phone")
    program_id = fields.Many2one('sfk.program', ondelete='cascade', string="Program")
    course_ids = fields.Many2many('sfk_operation.course', string='Enrolled Courses')
    enrollment_date = fields.Date(default=fields.Date.context_today)
    status = fields.Selection([('active','Active'),('withdrawn','Withdrawn'),('completed','Completed')], string="Stage", default='active')
    enrollment_ids = fields.One2many('sfk.enrollment', 'student_id', string="Enrollments")

    def action_set_active(self):
        self.write({'status': 'active'})

    def action_set_withdrawn(self):
        self.write({'status': 'withdrawn'})

    def action_set_completed(self):
        self.write({'status': 'completed'})

    @api.depends('date_of_birth')
    def _compute_age(self):
        for rec in self:
            if rec.date_of_birth:
                today = date.today()
                rec.age = today.year - rec.date_of_birth.year - ((today.month, today.day) < (rec.date_of_birth.month, rec.date_of_birth.day))
            else:
                rec.age = 0
