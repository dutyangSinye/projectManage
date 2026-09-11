"""v3.0.65：已下线菜单的历史授权不再阻断角色权限保存。

回归背景：菜单停用后界面上看不到，用户无法取消勾选，但历史授权行仍在；
保存时前端把它们原样回传，后端判为非法菜单并拒绝整单提交，
导致该角色的权限永远改不动。
"""

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.main as m
from app.db.models import Menu, Role, RoleDataScope, RolePermission, User, UserRole
from app.db.session import SessionLocal


def _grant_retired_menu(db, role: Role, code: str) -> Menu:
    """给角色补一条已下线菜单的历史授权（先清同键行，避免唯一约束冲突）。"""
    menu = db.scalar(select(Menu).where(Menu.code == code))
    db.query(RolePermission).filter(RolePermission.role_id == role.id, RolePermission.menu_id == menu.id).delete(synchronize_session=False)
    db.query(RoleDataScope).filter(RoleDataScope.role_id == role.id, RoleDataScope.resource == code).delete(synchronize_session=False)
    db.add(RolePermission(role_id=role.id, menu_id=menu.id, actions='["VIEW"]'))
    db.add(RoleDataScope(role_id=role.id, resource=code, scope_type="ALL", department_id=None))
    db.commit()
    return menu


def _ensure_admin_user(db) -> int | None:
    """确保存在一个拥有管理员权限的用户，返回其 id。"""
    user = db.scalar(select(User).where(User.employment_status == "ACTIVE").order_by(User.id))
    if user is None:
        user = User(feishu_user_id="regression-admin", name="回归管理员", employment_status="ACTIVE")
        db.add(user)
        db.flush()
    role = db.scalar(select(Role).where(Role.code == "system_admin"))
    if role is None:
        return None
    exists = db.scalar(select(UserRole.id).where(UserRole.user_id == user.id, UserRole.role_id == role.id))
    if not exists:
        db.add(UserRole(user_id=user.id, role_id=role.id, is_active=True))
    db.commit()
    return user.id


class RetiredMenuGrantTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        m.upgrade_schema()
        db = SessionLocal()
        try:
            m.seed_rbac(db)
            m.disable_retired_menus(db)
            db.commit()
        finally:
            db.close()

    def setUp(self) -> None:
        self.db = SessionLocal()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()

    def test_budget_templates_is_retired(self):
        self.assertIn("budget_templates", m.RETIRED_MENU_SEED)
        self.assertIn("personnel_costs", m.RETIRED_MENU_SEED)
        menu = self.db.scalar(select(Menu).where(Menu.code == "budget_templates"))
        self.assertIsNotNone(menu)
        self.assertFalse(menu.is_active)

    def test_drop_retired_menu_grants_cleans_history_rows(self):
        db = self.db
        role = db.scalar(select(Role).order_by(Role.id))
        self.assertIsNotNone(role)
        retired = _grant_retired_menu(db, role, "personnel_costs")

        m.drop_retired_menu_grants(db)
        db.commit()

        left_permissions = db.scalar(
            select(RolePermission.id).where(RolePermission.role_id == role.id, RolePermission.menu_id == retired.id)
        )
        left_scopes = db.scalar(
            select(RoleDataScope.id).where(RoleDataScope.role_id == role.id, RoleDataScope.resource == retired.code)
        )
        self.assertIsNone(left_permissions)
        self.assertIsNone(left_scopes)

    def test_role_permissions_view_hides_retired_menus(self):
        db = self.db
        role = db.scalar(select(Role).order_by(Role.id))
        self.assertIsNotNone(role)
        retired = _grant_retired_menu(db, role, "approval_workflows")

        view = m.role_permissions_view(db, role)
        self.assertNotIn(retired.code, [item.menu_code for item in view.permissions])
        self.assertNotIn(retired.code, [item.resource for item in view.scopes])

        m.drop_retired_menu_grants(db)
        db.commit()

    def test_saving_role_permissions_with_retired_menu_is_not_rejected(self):
        user_id = _ensure_admin_user(self.db)
        if not user_id:
            self.skipTest("临时库缺少系统管理员角色，跳过接口级回归")

        headers = {"x-demo-user-id": str(user_id)}
        with TestClient(m.app) as client:
            created = client.post(
                "/api/v1/admin/roles",
                headers=headers,
                json={"code": "tmp_retired_role", "name": "停用菜单回归角色", "description": "回归用例", "is_active": True},
            )
            self.assertIn(created.status_code, (200, 201), created.text)
            role_id = created.json()["id"]

            retired_code = self.db.scalar(select(Menu.code).where(Menu.code == "personnel_costs"))
            payload = {
                "permissions": [
                    {"menu_code": retired_code, "actions": ["VIEW"]},
                    {"menu_code": "projects", "actions": ["VIEW"]},
                ],
                "scopes": [
                    {"resource": retired_code, "scope_type": "OWNED_PROJECTS", "department_id": None},
                    {"resource": "projects", "scope_type": "OWNED_PROJECTS", "department_id": None},
                ],
            }
            saved = client.patch(f"/api/v1/admin/roles/{role_id}/permissions", headers=headers, json=payload)
            self.assertEqual(saved.status_code, 200, saved.text)
            body = saved.json()
            self.assertEqual([item["menu_code"] for item in body["permissions"]], ["projects"])
            self.assertEqual([item["resource"] for item in body["scopes"]], ["projects"])

            client.delete(f"/api/v1/admin/roles/{role_id}", headers=headers)
