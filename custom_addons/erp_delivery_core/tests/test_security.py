from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestErpDeliverySecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env["res.company"].create({"name": "ERP Security A"})
        cls.company_b = cls.env["res.company"].create({"name": "ERP Security B"})
        cls.partner = cls.env["res.partner"].create({"name": "ERP Security Customer"})
        cls.user_group = cls.env.ref("erp_delivery_core.group_erp_delivery_user")
        cls.consultant_group = cls.env.ref(
            "erp_delivery_core.group_erp_delivery_consultant"
        )
        cls.manager_group = cls.env.ref("erp_delivery_core.group_erp_delivery_manager")
        cls.solution = cls.env["erp.solution"].create(
            {
                "name": "ERP Security Solution",
                "code": "ERP-SECURITY",
                "category": "custom",
                "company_id": cls.company_a.id,
            }
        )

        cls.consultant = cls._create_user(
            "erp_security_consultant",
            cls.company_a,
            cls.consultant_group,
        )
        cls.manager = cls._create_user(
            "erp_security_manager",
            cls.company_a,
            cls.manager_group,
        )
        cls.company_a_user = cls._create_user(
            "erp_security_company_a_user",
            cls.company_a,
            cls.user_group,
        )

        cls.consultant_project = cls._create_project(
            "Consultant Project",
            cls.company_a,
            user_id=cls.consultant.id,
        )
        cls.member_project = cls._create_project(
            "Member Project",
            cls.company_a,
            erp_member_ids=[Command.link(cls.consultant.id)],
        )
        cls.other_project = cls._create_project("Other Project", cls.company_a)
        cls.company_b_project = cls._create_project(
            "Company B Project",
            cls.company_b,
        )

    @classmethod
    def _create_user(cls, login, company, group):
        return cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": login,
                "login": login,
                "company_id": company.id,
                "company_ids": [Command.set([company.id])],
                "group_ids": [Command.set(group.ids)],
            }
        )

    @classmethod
    def _create_project(cls, name, company, **values):
        return cls.env["project.project"].create(
            {
                "name": name,
                "company_id": company.id,
                "partner_id": cls.partner.id,
                "privacy_visibility": "portal",
                **values,
            }
        )

    def test_consultant_only_reads_and_writes_assigned_projects(self):
        Project = self.env["project.project"].with_user(self.consultant).with_context(
            allowed_company_ids=[self.company_a.id]
        )
        visible_projects = Project.search(
            [
                (
                    "id",
                    "in",
                    [
                        self.consultant_project.id,
                        self.member_project.id,
                        self.other_project.id,
                    ],
                )
            ]
        )
        self.assertEqual(
            set(visible_projects.ids),
            {self.consultant_project.id, self.member_project.id},
        )

        hidden_project = self.other_project.with_user(self.consultant).with_context(
            allowed_company_ids=[self.company_a.id]
        )
        with self.assertRaises(AccessError):
            hidden_project.read(["name"])
        with self.assertRaises(AccessError):
            hidden_project.write({"name": "Unauthorized edit"})
        with self.assertRaises(AccessError):
            self.consultant_project.with_user(self.consultant).unlink()
        with self.assertRaises(AccessError):
            self.consultant_project.with_user(self.consultant).write(
                {"privacy_visibility": "followers"}
            )

    def test_consultant_task_and_module_scope_matches_project_scope(self):
        own_task = self.env["project.task"].create(
            {"name": "Assigned Task", "project_id": self.consultant_project.id}
        )
        other_task = self.env["project.task"].create(
            {"name": "Unassigned Task", "project_id": self.other_project.id}
        )
        own_module = self.env["project.erp.module"].create(
            {
                "project_id": self.consultant_project.id,
                "solution_id": self.solution.id,
            }
        )
        other_module = self.env["project.erp.module"].create(
            {
                "project_id": self.other_project.id,
                "solution_id": self.solution.id,
            }
        )
        company_b_task = self.env["project.task"].create(
            {"name": "Company B Task", "project_id": self.company_b_project.id}
        )
        company_b_solution = self.env["erp.solution"].create(
            {
                "name": "Company B Solution",
                "code": "ERP-SECURITY-B",
                "category": "custom",
                "company_id": self.company_b.id,
            }
        )
        company_b_module = self.env["project.erp.module"].create(
            {
                "project_id": self.company_b_project.id,
                "solution_id": company_b_solution.id,
            }
        )

        task_model = self.env["project.task"].with_user(self.consultant).with_context(
            allowed_company_ids=[self.company_a.id]
        )
        module_model = self.env["project.erp.module"].with_user(
            self.consultant
        ).with_context(allowed_company_ids=[self.company_a.id])
        self.assertEqual(
            task_model.search(
                [
                    (
                        "id",
                        "in",
                        [own_task.id, other_task.id, company_b_task.id],
                    )
                ]
            ).ids,
            [own_task.id],
        )
        self.assertEqual(
            module_model.search(
                [
                    (
                        "id",
                        "in",
                        [own_module.id, other_module.id, company_b_module.id],
                    )
                ]
            ).ids,
            [own_module.id],
        )
        with self.assertRaises(AccessError):
            other_task.with_user(self.consultant).read(["name"])
        with self.assertRaises(AccessError):
            company_b_task.with_user(self.consultant).read(["name"])
        with self.assertRaises(AccessError):
            other_module.with_user(self.consultant).read(["planned_effort"])
        with self.assertRaises(AccessError):
            company_b_module.with_user(self.consultant).read(["planned_effort"])
        with self.assertRaises(AccessError):
            own_task.with_user(self.consultant).unlink()
        with self.assertRaises(AccessError):
            own_module.with_user(self.consultant).unlink()
        with self.assertRaises(AccessError):
            own_module.with_user(self.consultant).write(
                {"project_id": self.other_project.id}
            )

        own_task.with_user(self.consultant).write({"risk_level": "high"})
        self.assertEqual(own_task.risk_level, "high")

    def test_internal_cost_is_restricted_to_delivery_manager(self):
        for user in (self.consultant, self.company_a_user):
            with self.assertRaises(AccessError):
                self.solution.with_user(user).read(["internal_cost"])

        manager_solution = self.solution.with_user(self.manager).with_company(
            self.company_a
        )
        manager_solution.write({"internal_cost": 875.0})
        self.assertEqual(manager_solution.internal_cost, 875.0)

    def test_delivery_read_only_role_cannot_gain_write_from_project_group(self):
        self.company_a_user.write(
            {
                "group_ids": [
                    Command.link(self.env.ref("project.group_project_manager").id)
                ]
            }
        )
        project = self.consultant_project.with_user(self.company_a_user)

        with self.assertRaises(AccessError):
            project.write({"delivery_state": "analysis"})
        with self.assertRaises(AccessError):
            project.unlink()
        with self.assertRaises(AccessError):
            project.action_golive()
        with self.assertRaises(AccessError):
            self.env["project.project"].with_user(self.company_a_user).create(
                {"name": "Unauthorized Delivery Project", "company_id": self.company_a.id}
            )

    def test_standard_project_group_cannot_read_delivery_fields_without_erp_role(self):
        project_manager = self._create_user(
            "erp_security_project_manager_only",
            self.company_a,
            self.env.ref("project.group_project_manager"),
        )
        with self.assertRaises(AccessError):
            self.consultant_project.with_user(project_manager).read(
                ["delivery_state"]
            )

    def test_manager_sees_all_projects_in_allowed_company(self):
        self.assertTrue(
            self.manager.has_group("erp_delivery_core.group_erp_delivery_consultant")
        )
        visible_ids = self.env["project.project"].with_user(self.manager).with_context(
            allowed_company_ids=[self.company_a.id]
        ).search(
            [
                (
                    "id",
                    "in",
                    [
                        self.consultant_project.id,
                        self.member_project.id,
                        self.other_project.id,
                    ],
                )
            ]
        ).ids
        self.assertEqual(
            set(visible_ids),
            {
                self.consultant_project.id,
                self.member_project.id,
                self.other_project.id,
            },
        )
        self.assertFalse(
            self.env["project.project"]
            .with_user(self.manager)
            .with_context(allowed_company_ids=[self.company_a.id])
            .search([("id", "=", self.company_b_project.id)])
        )

    def test_user_cannot_query_projects_from_another_company(self):
        Project = self.env["project.project"].with_user(self.company_a_user).with_context(
            allowed_company_ids=[self.company_a.id]
        )
        self.assertFalse(
            Project.search([("id", "=", self.company_b_project.id)])
        )
        with self.assertRaises(AccessError):
            self.company_b_project.with_user(self.company_a_user).with_context(
                allowed_company_ids=[self.company_a.id]
            ).read(["name"])