from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    is_mandatory_for_golive = fields.Boolean(
        string="Mandatory for Go-Live",
        index=True,
    )
    risk_level = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Risk Level",
        index=True,
    )
    progress_weight = fields.Float(string="Progress Weight", default=1.0)
    acceptance_state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ],
        string="Acceptance Status",
        default="pending",
        required=True,
    )
    erp_module_id = fields.Many2one(
        comodel_name="project.erp.module",
        string="ERP Module",
        ondelete="set null",
        check_company=True,
        index=True,
    )