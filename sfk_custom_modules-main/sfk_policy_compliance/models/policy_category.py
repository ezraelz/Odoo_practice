from odoo import fields, models


class PolicyCategory(models.Model):
    _name = 'policy.category'
    _description = 'Policy Category'
    _order = 'name'

    name = fields.Char(required=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    policy_count = fields.Integer(compute='_compute_policy_count')

    def _compute_policy_count(self):
        document_model = self.env['policy.document']
        for category in self:
            category.policy_count = document_model.search_count([('category_id', '=', category.id)])
