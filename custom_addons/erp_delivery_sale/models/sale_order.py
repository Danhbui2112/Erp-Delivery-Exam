from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    erp_project_ids = fields.One2many(
        comodel_name="project.project",
        inverse_name="sale_order_id",
        string="ERP Delivery Projects",
        copy=False,
    )
    erp_project_id = fields.Many2one(
        comodel_name="project.project",
        string="ERP Delivery Project",
        compute="_compute_erp_projects",
        readonly=True,
    )
    erp_project_count = fields.Integer(
        string="ERP Delivery Projects",
        compute="_compute_erp_projects",
    )

    @api.depends("erp_project_ids")
    def _compute_erp_projects(self) -> None:
        grouped_projects = self.env["project.project"]._read_group(
            [("sale_order_id", "in", self.ids)],
            ["sale_order_id"],
            ["id:recordset"],
        )
        projects_by_order = {
            order.id: projects for order, projects in grouped_projects
        }
        for order in self:
            projects = projects_by_order.get(order.id, self.env["project.project"])
            order.erp_project_id = projects[:1]
            order.erp_project_count = len(projects)

    def action_create_erp_project(self) -> dict:
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_consultant"
        ):
            raise AccessError(
                _("Only ERP Delivery Consultants or Managers can create delivery projects.")
            )
        if self.state not in ("sale", "done"):
            raise UserError(_("An ERP project can only be created from a confirmed sales order."))
        if self.env["project.project"].sudo().search_count(
            [("sale_order_id", "=", self.id)]
        ):
            raise UserError(_("This sales order already has an ERP delivery project."))

        project = self._create_erp_delivery_project()
        return {
            "type": "ir.actions.act_window",
            "name": _("ERP Delivery Project"),
            "res_model": "project.project",
            "view_mode": "form",
            "res_id": project.id,
            "target": "current",
        }

    def _create_erp_delivery_project(self):
        self.ensure_one()
        project = self.env["project.project"].create(
            {
                "name": _("%(order)s - %(customer)s", order=self.name, customer=self.partner_id.display_name),
                "is_erp_delivery": True,
                "company_id": self.company_id.id,
                "partner_id": self.partner_id.id,
                "user_id": self.user_id.id or self.env.user.id,
                "erp_member_ids": [(4, self.env.uid)],
                "sale_order_id": self.id,
                "contract_value": self._amount_in_project_currency(
                    self.amount_total,
                    self.currency_id,
                ),
            }
        )
        self._create_erp_project_modules(project)
        return project

    def _get_erp_conversion_date(self):
        self.ensure_one()
        return (
            fields.Date.to_date(self.date_order)
            if self.date_order
            else fields.Date.context_today(self)
        )

    def _amount_in_project_currency(self, amount, source_currency):
        self.ensure_one()
        target_currency = self.company_id.currency_id
        return source_currency._convert(
            amount,
            target_currency,
            self.company_id,
            self._get_erp_conversion_date(),
        )

    def _create_erp_project_modules(self, project) -> None:
        self.ensure_one()
        module_values_by_solution = {}
        lines = self.order_line.filtered(
            lambda line: line.erp_solution_id
            and not line.display_type
            and not line.is_downpayment
        )
        for line in lines:
            solution = line.erp_solution_id
            values = module_values_by_solution.setdefault(
                solution.id,
                {
                    "project_id": project.id,
                    "solution_id": solution.id,
                    "planned_effort": 0.0,
                    "price": 0.0,
                },
            )
            values["planned_effort"] += solution.standard_effort * line.product_uom_qty
            values["price"] += self._amount_in_project_currency(
                line.price_subtotal,
                line.currency_id,
            )
        if module_values_by_solution:
            self.env["project.erp.module"].create(
                list(module_values_by_solution.values())
            )

    def action_view_erp_project(self) -> dict:
        self.ensure_one()
        projects = self.erp_project_ids
        if len(projects) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("ERP Delivery Project"),
                "res_model": "project.project",
                "view_mode": "form",
                "res_id": projects.id,
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("ERP Delivery Projects"),
            "res_model": "project.project",
            "view_mode": "list,form",
            "domain": [("sale_order_id", "=", self.id)],
            "target": "current",
        }