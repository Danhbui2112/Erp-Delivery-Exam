from odoo import fields, models


class ProjectMilestone(models.Model):
    _inherit = "project.milestone"

    is_mandatory_for_golive = fields.Boolean(
        string="Mandatory for Go-Live",
        default=False,
        index=True,
        groups="erp_delivery_core.group_erp_delivery_manager",
    )