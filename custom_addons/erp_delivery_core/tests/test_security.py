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

    def test_manager_sees_all_projects_in_allowed_company(self):
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