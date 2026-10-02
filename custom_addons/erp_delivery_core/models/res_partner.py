from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    _erp_customer_code_company_uniq = models.Constraint(
        "unique(company_id, erp_customer_code)",
        "ERP customer code must be unique per company.",
    )

    is_erp_customer = fields.Boolean(string="ERP Customer", index=True)
    erp_customer_code = fields.Char(
        string="ERP Customer Code",
        copy=False,
        index=True,
    )
    erp_tier = fields.Selection(
        selection=[
            ("tier_1", "Tier 1"),
            ("tier_2", "Tier 2"),
            ("tier_3", "Tier 3"),
        ],
        string="ERP Customer Tier",
    )
    contract_expiry_date = fields.Date(string="Contract Expiry Date")
    expected_user_count = fields.Integer(string="Expected User Count")
    erp_currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_erp_currency_id",
    )
    subscription_value = fields.Monetary(
        string="Subscription Value",
        currency_field="erp_currency_id",
        groups="erp_delivery_core.group_erp_delivery_manager",
    )
    erp_project_ids = fields.One2many(
        comodel_name="project.project",
        inverse_name="partner_id",
        string="ERP Projects",
    )

    @api.depends("company_id")
    @api.depends_context("company")
    def _compute_erp_currency_id(self) -> None:
        for partner in self:
            company = partner.company_id or self.env.company
            partner.erp_currency_id = company.currency_id