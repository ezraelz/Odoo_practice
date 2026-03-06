# -*- coding: utf-8 -*-

from odoo import models, fields

class Course(models.Model):
    _name = 'sfk_operation.course'
    _description = 'Course'

    name = fields.Char(string='Name', required=True)
