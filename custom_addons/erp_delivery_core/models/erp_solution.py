from odoo import api, fields, models


class ErpSolution(models.Model):
    _name = "erp.solution"
    _description = "ERP Solution"
    _order = "name, id"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", required=True, index=True)
    category = fields.Selection(
        selection=[
            ("sales", "Sales"),
            ("crm", "CRM"),
            ("purchase", "Purchase"),
            ("inventory", "Inventory"),
            ("accounting", "Accounting"),
            ("mrp", "Manufacturing"),
            ("hr", "Human Resources"),
            ("custom", "Custom"),
        ],
        string="Category",
        required=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        index=True,
        help="Leave empty to share this solution across companies.",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_currency_id",
    )
    standard_effort = fields.Float(string="Standard Effort")
    service_price = fields.Monetary(
        string="Service Price",
        currency_field="currency_id",
    )
    internal_cost = fields.Float(
        string="Internal Cost",
        company_dependent=True,
        groups="erp_delivery_core.group_erp_delivery_manager",
    )

    @api.depends_context("company")
    def _compute_currency_id(self) -> None:
        for solution in self:
            solution.currency_id = self.env.company.currency_id