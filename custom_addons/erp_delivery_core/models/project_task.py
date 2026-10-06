from odoo import _, api, fields, models
from odoo.exceptions import AccessError


CONSULTANT_TASK_WRITE_FIELDS = frozenset(
    {
        "name",
        "description",
        "user_ids",
        "date_deadline",
        "priority",
        "stage_id",
        "state",
        "risk_level",
        "acceptance_state",
        "erp_module_id",
    }
)
CONSULTANT_TASK_CREATE_FIELDS = CONSULTANT_TASK_WRITE_FIELDS | {"project_id"}


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
        index=True,
    )
    erp_module_id = fields.Many2one(
        comodel_name="project.erp.module",
        string="ERP Module",
        ondelete="set null",
        check_company=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_consultant"
        ) and not self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_manager"
        ):
            if any(set(vals) - CONSULTANT_TASK_CREATE_FIELDS for vals in vals_list):
                raise AccessError(
                    _("Consultants cannot change task configuration on creation.")
                )
        return super().create(vals_list)

    def write(self, vals):
        is_consultant = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_consultant"
        )
        is_manager = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_manager"
        )
        if is_consultant and not is_manager:
            if set(vals) - CONSULTANT_TASK_WRITE_FIELDS:
                raise AccessError(
                    _("Consultants cannot change task configuration fields.")
                )
        return super().write(vals)