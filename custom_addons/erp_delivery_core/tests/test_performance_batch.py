from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase


class TestErpDeliveryBatchPerformance(TransactionCase):
    def test_project_aggregates_use_bounded_queries_for_50_projects(self):
        company = self.env.company
        partner = self.env["res.partner"].create({"name": "Batch Customer"})
        solution = self.env["erp.solution"].create(
            {
                "name": "Batch Solution",
                "code": "BATCH",
                "category": "custom",
                "standard_effort": 2.0,
            }
        )
        projects = self.env["project.project"].create(
            [
                {
                    "name": f"Batch Project {index}",
                    "company_id": company.id,
                    "partner_id": partner.id,
                    "user_id": self.env.user.id,
                }
                for index in range(50)
            ]
        )
        modules = self.env["project.erp.module"].create(
            [
                {
                    "project_id": project.id,
                    "solution_id": solution.id,
                    "planned_effort": 2.0,
                    "actual_effort": 1.0,
                }
                for project in projects
            ]
        )
        tasks = self.env["project.task"].create(
            [
                {
                    "name": f"Task {project_index}-{task_index}",
                    "project_id": project.id,
                    "is_mandatory_for_golive": True,
                    "progress_weight": 1.0,
                }
                for project_index, project in enumerate(projects)
                for task_index in range(10)
            ]
        )
        self.env.flush_all()

        query_count_before = self.cr.sql_log_count
        projects._compute_module_metrics()
        projects._compute_task_metrics()
        projects._compute_health_status()
        self.env.flush_all()
        query_count = self.cr.sql_log_count - query_count_before

        self.assertLessEqual(
            query_count,
            20,
            f"Expected batched aggregate queries, got {query_count} queries for 50 projects.",
        )
        self.assertEqual(projects.mapped("module_count"), [1] * 50)
        self.assertEqual(projects.mapped("mandatory_task_count"), [10] * 50)
        self.assertEqual(projects.mapped("progress_rate"), [0.0] * 50)

        modules.write({"actual_effort": 3.0})
        tasks.write({"risk_level": "high"})
        self.env.flush_all()

        self.assertEqual(projects.mapped("actual_effort_total"), [3.0] * 50)
        self.assertEqual(projects.mapped("health_status"), ["amber"] * 50)

    def test_stored_metrics_recompute_when_source_records_change(self):
        company = self.env.company
        partner = self.env["res.partner"].create({"name": "Recompute Customer"})
        solution = self.env["erp.solution"].create(
            {
                "name": "Recompute Solution",
                "code": "RECOMPUTE",
                "category": "custom",
            }
        )
        project = self.env["project.project"].create(
            {
                "name": "Recompute Project",
                "company_id": company.id,
                "partner_id": partner.id,
                "user_id": self.env.user.id,
            }
        )
        module = self.env["project.erp.module"].create(
            {
                "project_id": project.id,
                "solution_id": solution.id,
                "planned_effort": 4.0,
                "actual_effort": 1.0,
            }
        )
        task = self.env["project.task"].create(
            {
                "name": "Risk Tracking Task",
                "project_id": project.id,
                "is_mandatory_for_golive": True,
                "risk_level": "low",
            }
        )
        self.assertEqual(project.actual_effort_total, 1.0)
        self.assertEqual(project.health_status, "green")

        module.write({"actual_effort": 3.0})
        task.write({"risk_level": "high"})

        self.assertEqual(project.actual_effort_total, 3.0)
        self.assertEqual(project.health_status, "amber")

    def test_health_cron_refreshes_status_when_go_live_date_passes(self):
        today = fields.Date.today()
        project = self.env["project.project"].create(
            {
                "name": "Overdue Health Project",
                "company_id": self.env.company.id,
                "partner_id": self.env["res.partner"].create(
                    {"name": "Overdue Health Customer"}
                ).id,
                "user_id": self.env.user.id,
                "date_start": fields.Date.add(today, days=-10),
                "go_live_expected_date": fields.Date.add(today, days=1),
            }
        )
        self.env["project.task"].create(
            {
                "name": "Overdue Health Task",
                "project_id": project.id,
                "is_mandatory_for_golive": True,
                "progress_weight": 1.0,
            }
        )
        self.assertEqual(project.health_status, "amber")

        day_after_go_live = fields.Date.add(project.go_live_expected_date, days=1)
        with patch.object(fields.Date, "today", return_value=day_after_go_live):
            self.env["project.project"]._cron_refresh_health_status()

        self.assertEqual(project.health_status, "red")