from odoo import models, fields,_

class HrEmployee(models.Model):
   _inherit='hr.employee'

   tax_id=fields.Char(string='Tax ID')
   pension_id=fields.Char(string='Pension Id')