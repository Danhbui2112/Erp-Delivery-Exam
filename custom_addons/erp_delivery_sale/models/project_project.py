from odoo import _, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = "project.project"

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sales Order",
        readonly=True,
        copy=False,
        ondelete="set null",
        check_company=True,
        index=True,
    )

    _sale_order_project_uniq = models.Constraint(
        "unique(sale_order_id)",
        "A sales order can only be linked to one ERP delivery project.",
    )

    def action_view_sale_order(self) -> dict:
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_("This project is not linked to a sales order."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Sales Order"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
            "target": "current",
        }

    def _validate_golive_conditions(self) -> None:
        super()._validate_golive_conditions()
        projects_with_unconfirmed_orders = self.filtered(
            lambda project: project.sale_order_id
            and project.sale_order_id.state not in ("sale", "done")
        )
        if projects_with_unconfirmed_orders:
            raise UserError(
                _("A linked sales order must remain confirmed before Go-Live.")
            )