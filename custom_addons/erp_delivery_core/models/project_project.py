from typing import Any

from odoo import api, fields, models
from odoo.exceptions import UserError


CLOSED_TASK_STATES = ("1_done", "1_canceled")


class ProjectProject(models.Model):
    _inherit = "project.project"

    project_code = fields.Char(
        string="Project Code",
        readonly=True,
        copy=False,
        index=True,
        default="New",
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
    )
    go_live_expected_date = fields.Date(
        string="Expected Go-Live Date",
        tracking=True,
    )
    go_live_actual_date = fields.Date(
        string="Actual Go-Live Date",
        tracking=True,
        copy=False,
    )
    contract_value = fields.Monetary(
        string="Contract Value",
        currency_field="currency_id",
        tracking=True,
    )
    erp_member_ids = fields.Many2many(
        comodel_name="res.users",
        relation="project_project_erp_member_rel",
        column1="project_id",
        column2="user_id",
        string="ERP Delivery Members",
        check_company=True,
    )
    erp_module_ids = fields.One2many(
        comodel_name="project.erp.module",
        inverse_name="project_id",
        string="ERP Modules",
    )
    customer_code = fields.Char(
        string="Customer Code",
        related="partner_id.erp_customer_code",
        store=True,
        readonly=True,
    )
    duration_days = fields.Integer(
        string="Duration (Days)",
        compute="_compute_duration_days",
        inverse="_inverse_duration_days",
        store=True,
    )
    module_count = fields.Integer(
        string="ERP Module Count",
        compute="_compute_module_metrics",
        store=True,
    )
    planned_effort_total = fields.Float(
        string="Planned Effort Total",
        compute="_compute_module_metrics",
        store=True,
    )
    actual_effort_total = fields.Float(
        string="Actual Effort Total",
        compute="_compute_module_metrics",
        store=True,
    )
    mandatory_task_count = fields.Integer(
        string="Mandatory Task Count",
        compute="_compute_task_metrics",
        store=True,
    )
    mandatory_task_done_count = fields.Integer(
        string="Mandatory Tasks Done",
        compute="_compute_task_metrics",
        store=True,
    )
    progress_rate = fields.Float(
        string="Mandatory Task Progress (%)",
        compute="_compute_task_metrics",
        store=True,
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
    )

    @api.model_create_multi
    def create(self, vals_list: list[dict[str, Any]]) -> models.Model:
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

    def _validate_golive_conditions(self) -> None:
        projects_without_customer = self.filtered(lambda project: not project.partner_id)
        projects_without_manager = self.filtered(lambda project: not project.user_id)
        projects_without_modules = self.filtered(lambda project: not project.erp_module_ids)
        problems = []
        if projects_without_customer:
            problems.append("Every project must have a customer.")
        if projects_without_manager:
            problems.append("Every project must have a project manager.")
        if projects_without_modules:
            problems.append("Every project must include at least one ERP module.")

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

    def action_golive(self) -> bool:
        self._validate_golive_conditions()
        self.write(
            {
                "delivery_state": "golive",
                "go_live_actual_date": fields.Date.context_today(self),
            }
        )
        return True