from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    erp_solution_id = fields.Many2one(
        comodel_name="erp.solution",
        string="ERP Solution",
        ondelete="restrict",
        check_company=True,
        index=True,
    )