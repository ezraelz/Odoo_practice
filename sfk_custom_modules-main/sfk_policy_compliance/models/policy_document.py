from odoo import fields, models


class PolicyDocument(models.Model):
    _name = 'policy.document'
    _description = 'Policy Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    description = fields.Text(tracking=True)
    category_id = fields.Many2one('policy.category', required=True, tracking=True)
    active = fields.Boolean(default=True)
    version_ids = fields.One2many('policy.version', 'document_id', string='Versions')
    current_version_id = fields.Many2one('policy.version', compute='_compute_current_version', store=False)
    current_status = fields.Selection(related='current_version_id.state', string='Current Status')
    compliance_rate = fields.Float(compute='_compute_compliance_rate', string='Compliance %')

    def _compute_current_version(self):
        for document in self:
            document.current_version_id = self.env['policy.version'].search([
                ('document_id', '=', document.id),
                ('state', '=', 'active'),
            ], order='effective_date desc, id desc', limit=1)

    def _compute_compliance_rate(self):
        for document in self:
            version = document.current_version_id
            if not version:
                document.compliance_rate = 0.0
                continue
            required_assignments = version.assignment_ids.filtered(lambda a: a.required)
            if not required_assignments:
                document.compliance_rate = 100.0
                continue
            acknowledged = len(required_assignments.filtered(lambda a: a.status == 'acknowledged'))
            document.compliance_rate = (acknowledged / len(required_assignments)) * 100.0

    def action_open_current_compliance(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('sfk_policy_compliance.action_policy_assignment')
        action['domain'] = [('version_id', '=', self.current_version_id.id)]
        return action
