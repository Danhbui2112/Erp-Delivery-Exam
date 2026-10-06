from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestErpDeliverySaleIntegration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "ERP Sale Integration Customer"}
        )
        cls.solution = cls.env["erp.solution"].create(
            {
                "name": "Sales Integration Solution",
                "code": "SALE-ERP",
                "category": "sales",
                "standard_effort": 4.0,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "ERP Implementation Service",
                "list_price": 125.0,
            }
        )

    def _create_order(self, state="draft"):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.env.company.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 2.0,
                            "price_unit": 125.0,
                            "erp_solution_id": self.solution.id,
                        }
                    )
                ],
            }
        )
        if state == "sale":
            order.action_confirm()
        return order

    def test_confirmed_order_creates_linked_project_and_solution_module(self):
        order = self._create_order(state="sale")

        action = order.action_create_erp_project()

        project = self.env["project.project"].browse(action["res_id"])
        self.assertEqual(action["res_model"], "project.project")
        self.assertEqual(project.sale_order_id, order)
        self.assertEqual(project.partner_id, order.partner_id)
        self.assertAlmostEqual(project.contract_value, order.amount_total)
        self.assertEqual(order.erp_project_id, project)
        self.assertEqual(order.erp_project_count, 1)
        self.assertEqual(len(project.erp_module_ids), 1)
        self.assertEqual(project.erp_module_ids.solution_id, self.solution)
        self.assertEqual(project.erp_module_ids.planned_effort, 8.0)
        self.assertAlmostEqual(
            project.erp_module_ids.price,
            order.order_line.price_subtotal,
        )

    def test_draft_order_cannot_create_project(self):
        order = self._create_order()

        with self.assertRaises(UserError):
            order.action_create_erp_project()

        self.assertFalse(order.erp_project_ids)

    def test_duplicate_project_creation_is_rejected(self):
        order = self._create_order(state="sale")
        order.action_create_erp_project()

        with self.assertRaises(UserError):
            order.action_create_erp_project()

        self.assertEqual(order.erp_project_count, 1)

    def test_sale_project_passes_core_commercial_golive_conditions(self):
        order = self._create_order(state="sale")
        order.action_create_erp_project()
        project = order.erp_project_id

        self.assertTrue(project.partner_id)
        self.assertTrue(project.user_id)
        self.assertTrue(project.erp_module_ids)
        if "quality_gate_ids" in project._fields:
            self.env["project.quality.gate"].create(
                {"project_id": project.id, "score": 100.0}
            )
        self.assertTrue(project.action_golive())
        self.assertEqual(project.delivery_state, "golive")

    def test_go_live_requires_the_linked_sales_order_to_remain_confirmed(self):
        order = self._create_order(state="sale")
        order.action_create_erp_project()
        project = order.erp_project_id
        order.action_cancel()

        with self.assertRaises(UserError):
            project.action_golive()

    def test_quality_gate_and_sales_checks_compose_when_quality_is_installed(self):
        if "quality_gate_ids" not in self.env["project.project"]._fields:
            self.skipTest("ERP Delivery Quality Gate is not installed.")

        order = self._create_order(state="sale")
        order.action_create_erp_project()
        project = order.erp_project_id
        with self.assertRaises(UserError):
            project.action_golive()

        self.env["project.quality.gate"].create(
            {"project_id": project.id, "score": 90.0}
        )
        order.action_cancel()
        with self.assertRaises(UserError):
            project.action_golive()