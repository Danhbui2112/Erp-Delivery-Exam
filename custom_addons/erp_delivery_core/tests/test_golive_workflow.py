from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestErpDeliveryGoLive(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Go-Live Customer"}
        )
        cls.solution = cls.env["erp.solution"].create(
            {
                "name": "Go-Live Solution",
                "code": "GO-LIVE",
                "category": "custom",
            }
        )

    def _create_project(self, **overrides):
        with_module = overrides.pop("with_module", True)
        values = {
            "name": "Go-Live Test Project",
            "company_id": self.env.company.id,
            "partner_id": self.partner.id,
            "user_id": self.env.user.id,
        }
        values.update(overrides)
        project = self.env["project.project"].create(values)
        if with_module:
            self.env["project.erp.module"].create(
                {
                    "project_id": project.id,
                    "solution_id": self.solution.id,
                }
            )
        return project

    def _assert_golive_blocked(self, project):
        with self.assertRaises(UserError):
            project.action_golive()
        self.assertNotEqual(project.delivery_state, "golive")

    def test_golive_requires_project_manager(self):
        project = self._create_project(user_id=False)
        self._assert_golive_blocked(project)

    def test_golive_requires_customer(self):
        project = self._create_project(partner_id=False)
        self._assert_golive_blocked(project)

    def test_golive_requires_at_least_one_erp_module(self):
        project = self._create_project(with_module=False)
        self._assert_golive_blocked(project)

    def test_golive_requires_all_mandatory_tasks_closed(self):
        project = self._create_project()
        self.env["project.task"].create(
            {
                "name": "Open Mandatory Task",
                "project_id": project.id,
                "is_mandatory_for_golive": True,
            }
        )
        self._assert_golive_blocked(project)

    def test_golive_rejects_open_critical_risk(self):
        project = self._create_project()
        self.env["project.task"].create(
            {
                "name": "Open Critical Task",
                "project_id": project.id,
                "risk_level": "critical",
            }
        )
        self._assert_golive_blocked(project)

    def test_golive_succeeds_and_records_actual_date(self):
        project = self._create_project()
        self.env["project.task"].create(
            {
                "name": "Accepted Mandatory Task",
                "project_id": project.id,
                "is_mandatory_for_golive": True,
                "state": "1_done",
            }
        )

        result = project.action_golive()

        self.assertTrue(result)
        self.assertEqual(project.delivery_state, "golive")
        self.assertEqual(project.go_live_actual_date, fields.Date.context_today(self))