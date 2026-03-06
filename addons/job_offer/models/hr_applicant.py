from odoo import fields, models


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    can_generate_offer = fields.Boolean(compute="_compute_can_generate_offer")
    offer_count = fields.Integer(string="Offers", compute="_compute_offer_count")

    def _compute_can_generate_offer(self):
        for applicant in self:
            stage_name = (applicant.stage_id.name or "").strip().lower()
            applicant.can_generate_offer = stage_name in {
                "contract proposal",
                "offer",
                "offer proposal",
            }

    def _compute_offer_count(self):
        grouped = self.env["job.offer"].read_group(
            domain=[("applicant_id", "in", self.ids), ("is_generated", "=", True)],
            fields=["applicant_id"],
            groupby=["applicant_id"],
        )
        count_map = {data["applicant_id"][0]: data["applicant_id_count"] for data in grouped}
        for applicant in self:
            applicant.offer_count = count_map.get(applicant.id, 0)

    def action_open_job_offer(self):
        self.ensure_one()
        offer = (
            self.env["job.offer"]
            .with_context(
                active_model="hr.applicant",
                active_id=self.id,
                default_applicant_id=self.id,
            )
            .create({})
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Job Offer",
            "res_model": "job.offer",
            "view_mode": "form",
            "view_id": self.env.ref("job_offer.view_job_offer_form").id,
            "res_id": offer.id,
            "target": "current",
        }

    def action_view_job_offers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Offers",
            "res_model": "job.offer",
            "view_mode": "list,form",
            "domain": [("applicant_id", "=", self.id), ("is_generated", "=", True)],
            "context": {"default_applicant_id": self.id},
            "target": "current",
        }
