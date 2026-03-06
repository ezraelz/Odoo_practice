from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    has_damaged = fields.Boolean(string='Damaged')
    has_missing = fields.Boolean(string='Missing Items')

    damaged_qty = fields.Integer(string='Damaged Qty', default=0)
    missing_qty = fields.Integer(string='Missing Qty', default=0)

    needs_review = fields.Boolean(
        string='Needs Review',
        compute='_compute_needs_review',
        store=True,
        tracking=True,
    )
    status_tag = fields.Selection(
        [
            ('good', 'Good'),
            ('damaged', 'Damaged'),
            ('missing', 'Missing'),
            ('both', 'Damaged & Missing'),
        ],
        string="Items Status",
        compute="_compute_status_tag",
        store=True,
        tracking=True,
    )

    @api.depends('has_damaged', 'has_missing')
    def _compute_status_tag(self):
        for rec in self:
            if rec.has_damaged and rec.has_missing:
                rec.status_tag = 'both'
            elif rec.has_damaged:
                rec.status_tag = 'damaged'
            elif rec.has_missing:
                rec.status_tag = 'missing'
            else:
                rec.status_tag = 'good'

    # Onchange Logic

    @api.onchange('has_damaged')
    def _onchange_has_damaged(self):
        for rec in self:
            if not rec.has_damaged:
                rec.damaged_qty = 0

    @api.onchange('has_missing')
    def _onchange_has_missing(self):
        for rec in self:
            if not rec.has_missing:
                rec.missing_qty = 0


    # Constraint Validation

    @api.constrains('has_damaged', 'has_missing', 'damaged_qty', 'missing_qty')
    def _check_items_status_counts(self):
        for rec in self:

            if rec.has_damaged and rec.damaged_qty <= 0:
                raise ValidationError(
                    _('Damaged quantity must be greater than zero when Damaged is checked.')
                )

            if rec.has_missing and rec.missing_qty <= 0:
                raise ValidationError(
                    _('Missing quantity must be greater than zero when Missing Items is checked.')
                )

            if not rec.has_damaged and rec.damaged_qty > 0:
                raise ValidationError(
                    _('You cannot enter damaged quantity unless Damaged is checked.')
                )

            if not rec.has_missing and rec.missing_qty > 0:
                raise ValidationError(
                    _('You cannot enter missing quantity unless Missing Items is checked.')
                )

    # Compute Review

    @api.depends('has_damaged', 'has_missing', 'damaged_qty', 'missing_qty')
    def _compute_needs_review(self):
        for rec in self:
            rec.needs_review = (
                rec.has_damaged
                or rec.has_missing
                or rec.damaged_qty > 0
                or rec.missing_qty > 0
            )

    # Create Override

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        if rec.needs_review:
            rec.message_post(
                body=_('This picking needs review due to damaged or missing items.')
            )
        return rec
