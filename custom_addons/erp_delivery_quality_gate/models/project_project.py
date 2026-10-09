from odoo import _, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = "project.project"

    quality_gate_ids = fields.One2many(
        comodel_name="project.quality.gate",
        inverse_name="project_id",
        string="Quality Gate",
        readonly=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )

    def _validate_golive_conditions(self) -> None:
        super()._validate_golive_conditions()
        passed_gates = self.env["project.quality.gate"]._read_group(
            [
                ("project_id", "in", self.ids),
                ("is_passed", "=", True),
            ],
            ["project_id"],
            ["__count"],
        )
        passed_project_ids = {
            project.id for project, count in passed_gates if count == 1
        }
        if set(self.ids) - passed_project_ids:
            raise UserError(
                _("Every project must pass its Quality Gate before Go-Live.")
            )
        project_model = self.env["project.project"]
        if "sale_order_id" not in project_model._fields:
            return
        
        projects_with_customer_mismatch = self.filltered(
            lambda project: project.sale_order_id
            and project.sale_order_id.partner_id != project.partner_id
        )
        if projects_witH_customer_mismatch:
            raise UserError(
                _("The project's customer must match the linked sales order customer.")
            )

    def action_open_quality_gate(self) -> dict:
        self.ensure_one()
        gate = self.env["project.quality.gate"].search(
            [("project_id", "=", self.id)],
            limit=1,
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Go-Live Quality Gate"),
            "res_model": "project.quality.gate",
            "view_mode": "form",
            "res_id": gate.id or False,
            "target": "current",
            "context": {"default_project_id": self.id},
        }