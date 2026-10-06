from odoo import _, fields, models
from odoo.exceptions import AccessError


class ProjectErpModule(models.Model):
    _name = "project.erp.module"
    _description = "ERP Project Module"
    _order = "project_id, id"
    _check_company_auto = True

    _project_solution_uniq = models.Constraint(
        "unique(project_id, solution_id)",
        "A solution can only be added once to a project.",
    )

    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Project",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="project_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    solution_id = fields.Many2one(
        comodel_name="erp.solution",
        string="Solution",
        required=True,
        ondelete="restrict",
        index=True,
        check_company=True,
    )
    lead_consultant_id = fields.Many2one(
        comodel_name="res.users",
        string="Lead Consultant",
        check_company=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="project_id.currency_id",
        readonly=True,
    )
    planned_effort = fields.Float(string="Planned Effort")
    actual_effort = fields.Float(string="Actual Effort")
    price = fields.Monetary(string="Price", currency_field="currency_id")
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("planned", "Planned"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    def write(self, vals):
        is_consultant = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_consultant"
        )
        is_manager = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_manager"
        )
        if is_consultant and not is_manager and set(vals) & {
            "project_id",
            "solution_id",
        }:
            raise AccessError(
                _("Consultants cannot change a module's project or solution.")
            )
        return super().write(vals)