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
        self.env["project.erp.module"].create(
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
        self.env["project.task"].create(
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