from typing import Any

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


CLOSED_TASK_STATES = ("1_done", "1_canceled")
CONSULTANT_PROJECT_WRITE_FIELDS = frozenset(
    {"delivery_state", "go_live_expected_date", "duration_days", "erp_module_ids"}
)


class ProjectProject(models.Model):
    _inherit = "project.project"

    project_code = fields.Char(
        string="Project Code",
        readonly=True,
        copy=False,
        index=True,
        default="New",
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    delivery_state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("analysis", "Analysis"),
            ("development", "Development"),
            ("uat", "UAT"),
            ("ready_golive", "Ready for Go-Live"),
            ("golive", "Go-Live"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Delivery Status",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
        index=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    go_live_expected_date = fields.Date(
        string="Expected Go-Live Date",
        tracking=True,
        index=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    go_live_actual_date = fields.Date(
        string="Actual Go-Live Date",
        tracking=True,
        copy=False,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    contract_value = fields.Monetary(
        string="Contract Value",
        currency_field="currency_id",
        tracking=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    erp_member_ids = fields.Many2many(
        comodel_name="res.users",
        relation="project_project_erp_member_rel",
        column1="project_id",
        column2="user_id",
        string="ERP Delivery Members",
        check_company=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    erp_module_ids = fields.One2many(
        comodel_name="project.erp.module",
        inverse_name="project_id",
        string="ERP Modules",
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    customer_code = fields.Char(
        string="Customer Code",
        related="partner_id.erp_customer_code",
        store=True,
        readonly=True,
        index=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    duration_days = fields.Integer(
        string="Duration (Days)",
        compute="_compute_duration_days",
        inverse="_inverse_duration_days",
        store=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    module_count = fields.Integer(
        string="ERP Module Count",
        compute="_compute_module_metrics",
        store=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    planned_effort_total = fields.Float(
        string="Planned Effort Total",
        compute="_compute_module_metrics",
        store=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    actual_effort_total = fields.Float(
        string="Actual Effort Total",
        compute="_compute_module_metrics",
        store=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    mandatory_task_count = fields.Integer(
        string="Mandatory Task Count",
        compute="_compute_task_metrics",
        store=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    mandatory_task_done_count = fields.Integer(
        string="Mandatory Tasks Done",
        compute="_compute_task_metrics",
        store=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    progress_rate = fields.Float(
        string="Mandatory Task Progress (%)",
        compute="_compute_task_metrics",
        store=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )
    health_status = fields.Selection(
        selection=[
            ("green", "Healthy"),
            ("amber", "At Risk"),
            ("red", "Critical"),
        ],
        string="Delivery Health",
        compute="_compute_health_status",
        store=True,
        index=True,
        groups="erp_delivery_core.group_erp_delivery_user",
    )

    @api.model_create_multi
    def create(self, vals_list: list[dict[str, Any]]) -> models.Model:
        is_delivery_user = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_user"
        )
        is_consultant = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_consultant"
        )
        is_manager = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_manager"
        )
        if any(vals.get("delivery_state") == "golive" for vals in vals_list):
            raise UserError(_("Use the Go-Live action after project setup."))
        if is_delivery_user and not is_manager:
            if not is_consultant:
                raise AccessError(_("ERP Delivery users have read-only access."))
            protected_fields = {
                "privacy_visibility",
                "allow_milestones",
                "alias_name",
                "alias_domain_id",
                "project_code",
            }
            if any(protected_fields.intersection(vals) for vals in vals_list):
                raise AccessError(
                    _("Consultants cannot set project configuration on creation.")
                )
        for vals in vals_list:
            if vals.get("project_code") in (False, "New"):
                vals["project_code"] = (
                    self.env["ir.sequence"].next_by_code("erp.delivery.project")
                    or "New"
                )
        return super().create(vals_list)

    @api.depends("date_start", "go_live_expected_date")
    def _compute_duration_days(self) -> None:
        for project in self:
            if project.date_start and project.go_live_expected_date:
                project.duration_days = (
                    project.go_live_expected_date - project.date_start
                ).days
            else:
                project.duration_days = 0
    
    @api.constrains("date_start", "go_live_expected_date")
    def _check_go_live_date_order(self) -> None:
        for project in self:
            if (
                project.date_start
                and project.go_live_expected_date
                and project.go_live_expected_date < project.date_start
            ):
                raise ValidationError(
                    _("Expected Go-Live date cannot be earlier than project start date.")
                )

    def _inverse_duration_days(self) -> None:
        for project in self:
            start_date = project.date_start or fields.Date.context_today(project)
            project.go_live_expected_date = fields.Date.add(
                start_date,
                days=project.duration_days,
            )

    @api.depends(
        "erp_module_ids",
        "erp_module_ids.planned_effort",
        "erp_module_ids.actual_effort",
    )
    def _compute_module_metrics(self) -> None:
        grouped_modules = self.env["project.erp.module"]._read_group(
            [("project_id", "in", self.ids)],
            ["project_id"],
            ["__count", "planned_effort:sum", "actual_effort:sum"],
        )
        metrics = {
            project.id: (count, planned_effort or 0.0, actual_effort or 0.0)
            for project, count, planned_effort, actual_effort in grouped_modules
        }
        for project in self:
            count, planned_effort, actual_effort = metrics.get(
                project.id,
                (0, 0.0, 0.0),
            )
            project.module_count = count
            project.planned_effort_total = planned_effort
            project.actual_effort_total = actual_effort

    @api.depends(
        "tasks.is_mandatory_for_golive",
        "tasks.progress_weight",
        "tasks.state",
    )
    def _compute_task_metrics(self) -> None:
        grouped_tasks = self.env["project.task"]._read_group(
            [
                ("project_id", "in", self.ids),
                ("is_mandatory_for_golive", "=", True),
            ],
            ["project_id", "state"],
            ["__count", "progress_weight:sum"],
        )
        metrics: dict[int, list[float]] = {}
        for project, state, count, total_weight in grouped_tasks:
            project_metrics = metrics.setdefault(project.id, [0, 0, 0.0, 0.0])
            project_metrics[0] += count
            project_metrics[2] += total_weight or 0.0
            if state == "1_done":
                project_metrics[1] += count
                project_metrics[3] += total_weight or 0.0

        for project in self:
            count, done_count, total_weight, done_weight = metrics.get(
                project.id,
                [0, 0, 0.0, 0.0],
            )
            project.mandatory_task_count = count
            project.mandatory_task_done_count = done_count
            project.progress_rate = (
                done_weight / total_weight * 100.0 if total_weight else 0.0
            )

    @api.depends(
        "date_start",
        "delivery_state",
        "go_live_expected_date",
        "go_live_actual_date",
        "mandatory_task_count",
        "progress_rate",
        "tasks.risk_level",
        "tasks.state",
    )
    def _compute_health_status(self) -> None:
        grouped_risks = self.env["project.task"]._read_group(
            [
                ("project_id", "in", self.ids),
                ("state", "not in", CLOSED_TASK_STATES),
                ("risk_level", "in", ("medium", "high", "critical")),
            ],
            ["project_id", "risk_level"],
            ["__count"],
        )
        risks_by_project: dict[int, set[str]] = {}
        for project, risk_level, _count in grouped_risks:
            risks_by_project.setdefault(project.id, set()).add(risk_level)

        today = fields.Date.today()
        for project in self:
            risks = risks_by_project.get(project.id, set())
            has_open_critical_task = "critical" in risks
            is_late = bool(
                project.go_live_expected_date
                and project.go_live_expected_date < today
                and (
                    not project.go_live_actual_date
                    or project.go_live_actual_date > project.go_live_expected_date
                )
            )
            if has_open_critical_task or is_late:
                project.health_status = "red"
                continue

            is_behind_schedule = False
            if (
                project.mandatory_task_count
                and project.date_start
                and project.go_live_expected_date
                and project.go_live_expected_date > project.date_start
            ):
                planned_days = (
                    project.go_live_expected_date - project.date_start
                ).days
                elapsed_days = min(
                    max((today - project.date_start).days, 0),
                    planned_days,
                )
                expected_progress = elapsed_days / planned_days * 100.0
                is_behind_schedule = project.progress_rate < expected_progress

            if is_behind_schedule or risks.intersection(("medium", "high")):
                project.health_status = "amber"
            else:
                project.health_status = "green"

    @api.model
    def _cron_refresh_health_status(self) -> None:
        last_id = 0
        batch_size = 500
        while True:
            projects = self.sudo().search(
                [("id", ">", last_id)],
                order="id",
                limit=batch_size,
            )
            if not projects:
                break
            projects._compute_health_status()
            projects.flush_recordset(["health_status"])
            last_id = projects[-1].id

    def _validate_golive_conditions(self) -> None:
        projects_without_customer = self.filtered(lambda project: not project.partner_id)
        projects_without_manager = self.filtered(lambda project: not project.user_id)
        projects_without_modules = self.filtered(lambda project: not project.erp_module_ids)
        projects_without_expected_date = self.filtered(
            lambda project: not project.go_live_expected_date
        )
        problems = []
        if projects_without_customer:
            problems.append("Every project must have a customer.")
        if projects_without_manager:
            problems.append("Every project must have a project manager.")
        if projects_without_modules:
            problems.append("Every project must include at least one ERP module.")
        if projects_without_expected_date:
            problems.append("Every project must have an expected Go-Live date.")
        project_ids = self.ids
        open_mandatory = self.env["project.task"]._read_group(
            [
                ("project_id", "in", project_ids),
                ("is_mandatory_for_golive", "=", True),
                ("state", "not in", CLOSED_TASK_STATES),
            ],
            ["project_id"],
            ["__count"],
        )
        projects_with_open_mandatory = {
            project.id for project, _count in open_mandatory
        }
        if projects_with_open_mandatory:
            problems.append("All mandatory go-live tasks must be closed.")

        open_critical = self.env["project.task"]._read_group(
            [
                ("project_id", "in", project_ids),
                ("risk_level", "=", "critical"),
                ("state", "not in", CLOSED_TASK_STATES),
            ],
            ["project_id"],
            ["__count"],
        )
        if open_critical:
            problems.append("Critical open tasks must be resolved before go-live.")

        if problems:
            raise UserError("\n".join(problems))

    def write(self, vals: dict[str, Any]) -> bool:
        is_delivery_user = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_user"
        )
        is_consultant = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_consultant"
        )
        is_manager = self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_manager"
        )
        if is_delivery_user and not is_manager and not is_consultant:
            raise AccessError(_("ERP Delivery users have read-only access."))
        if is_consultant and not is_manager:
            if set(vals) - CONSULTANT_PROJECT_WRITE_FIELDS:
                raise AccessError(
                    _("Consultants can only update ERP delivery project fields.")
                )
        if (
            vals.get("delivery_state") == "golive"
            and not self.env.context.get("erp_delivery_golive_action")
        ):
            raise UserError(_("Use the Go-Live action to validate this transition."))
        return super().write(vals)

    def action_golive(self) -> bool:
        if not self.env.su and not self.env.user.has_group(
            "erp_delivery_core.group_erp_delivery_consultant"
        ):
            raise AccessError(_("Only ERP Delivery Consultants or Managers can Go-Live."))
        self._validate_golive_conditions()
        self.with_context(erp_delivery_golive_action=True).write(
            {
                "delivery_state": "golive",
                "go_live_actual_date": fields.Date.context_today(self),
            }
        )
        return True