from odoo import Command
from odoo.exceptions import AccessError, UserError
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
        cls.consultant_group = cls.env.ref(
            "erp_delivery_core.group_erp_delivery_consultant"
        )
        cls.consultant = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "Quality Gate Consultant",
                "login": "quality_gate_consultant",
                "company_id": cls.env.company.id,
                "company_ids": [Command.set([cls.env.company.id])],
                "group_ids": [Command.set(cls.consultant_group.ids)],
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

    def test_consultant_can_update_score_but_not_read_or_change_threshold(self):
        project = self._create_project()
        project.write({"erp_member_ids": [Command.link(self.consultant.id)]})
        gate = self.env["project.quality.gate"].create(
            {"project_id": project.id, "score": 70.0}
        )
        consultant_gate = gate.with_user(self.consultant).with_context(
            allowed_company_ids=[self.env.company.id]
        )

        with self.assertRaises(AccessError):
            consultant_gate.read(["threshold"])
        with self.assertRaises(AccessError):
            consultant_gate.write({"threshold": 90.0})

        consultant_gate.write({"score": 85.0})
        self.assertTrue(consultant_gate.is_passed)