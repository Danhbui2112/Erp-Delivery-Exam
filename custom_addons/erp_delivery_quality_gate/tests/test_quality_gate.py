from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestErpDeliveryQualityGate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Quality Gate Customer"}
        )
        cls.solution = cls.env["erp.solution"].create(
            {
                "name": "Quality Gate Solution",
                "code": "QUALITY-GATE",
                "category": "custom",
            }
        )

    def _create_project(self):
        project = self.env["project.project"].create(
            {
                "name": "Quality Gate Project",
                "company_id": self.env.company.id,
                "partner_id": self.partner.id,
                "user_id": self.env.user.id,
            }
        )
        self.env["project.erp.module"].create(
            {"project_id": project.id, "solution_id": self.solution.id}
        )
        return project

    def test_quality_gate_addon_does_not_require_sales(self):
        if "sale.order" in self.env.registry.models:
            self.skipTest("Sales is installed in this database.")
        project = self._create_project()
        gate = self.env["project.quality.gate"].create(
            {"project_id": project.id, "score": 85.0}
        )
        self.assertTrue(gate.is_passed)

    def test_go_live_requires_a_passing_quality_gate(self):
        project = self._create_project()
        with self.assertRaises(UserError):
            project.action_golive()

        gate = self.env["project.quality.gate"].create(
            {"project_id": project.id, "score": 79.0}
        )
        self.assertFalse(gate.is_passed)
        with self.assertRaises(UserError):
            project.action_golive()

        gate.write({"score": 80.0})
        self.assertTrue(gate.is_passed)
        self.assertTrue(project.action_golive())