from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ProjectQualityGate(models.Model):
    _name = "project.quality.gate"
    _description = "ERP Project Quality Gate"
    _order = "project_id, id"
    _check_company_auto = True

    _project_quality_gate_uniq = models.Constraint(
        "unique(project_id)",
        "Each ERP project can have only one quality gate.",
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
    name = fields.Char(required=True, default="Go-Live Quality Gate")
    score = fields.Float(string="Quality Score", default=0.0, required=True)
    threshold = fields.Float(
        string="Minimum Passing Score",
        default=80.0,
        required=True,
        groups="erp_delivery_core.group_erp_delivery_manager",
    )
    is_passed = fields.Boolean(
        string="Passed",
        compute="_compute_is_passed",
        store=True,
        compute_sudo=True,
        index=True,
    )

    @api.depends("score", "threshold")
    def _compute_is_passed(self) -> None:
        for gate in self:
            gate.is_passed = gate.score >= gate.threshold

    @api.constrains("score")
    def _check_score_range(self) -> None:
        if any(gate.score < 0.0 or gate.score > 100.0 for gate in self):
            raise ValidationError(_("Quality scores must be between 0 and 100."))

    @api.constrains("threshold")
    def _check_threshold_range(self) -> None:
        if any(gate.threshold < 0.0 or gate.threshold > 100.0 for gate in self):
            raise ValidationError(
                _("Quality thresholds must be between 0 and 100.")
            )

    def write(self, vals):
        is_consultant = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_consultant"
        )
        is_manager = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_manager"
        )
        if is_consultant and not is_manager and "project_id" in vals:
            raise AccessError(_("Consultants cannot move a quality gate to another project."))
        return super().write(vals)