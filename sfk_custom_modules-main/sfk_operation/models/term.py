# python
from odoo import models, fields

class SfkTerm(models.Model):
    _name = "sfk.term"
    _description = "Term"
    _order = "start_date desc"

    name = fields.Char(required=True)
    program_id = fields.Many2one('sfk.program', string="Program", required=True, ondelete='cascade')
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    active = fields.Boolean(default=True)
    
    term_course_ids = fields.One2many('sfk.term.course', 'term_id', string="Courses & Instructors")

class SfkTermCourse(models.Model):
    _name = "sfk.term.course"
    _description = "Term Course Assignment"

    term_id = fields.Many2one('sfk.term', required=True, ondelete='cascade')
    course_id = fields.Many2one('sfk_operation.course', string="Course", required=True)
    
    # For School-based and general grouping
    grade = fields.Char(string="Grade/Class", required=True)

    _sql_constraints = [
        ('term_grade_unique', 'unique(term_id, grade)', 'A course is already assigned to this grade in this term.')
    ]
