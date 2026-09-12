"""v3.0.68：旧「人员成本」模块与日成本口径整体删除。

回归背景：人员成本维护页早在 v3.0.61 就被人工成本结转单取代，日成本折算当时已停用，
但菜单、接口、字段和报表折算逻辑一直残留；这里确认它们被彻底清干净且不会复活。
"""
import inspect
import unittest

from sqlalchemy import inspect as sql_inspect
from sqlalchemy import select, text

import app.main as m
from app.db.models import Menu, Role, RoleDataScope, RolePermission, User, UserRoleScope
from app.db.session import SessionLocal


class PersonnelCostRemovedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        m.upgrade_schema()
        db = SessionLocal()
        try:
            m.seed_rbac(db)
            m.disable_retired_menus(db)
            m.drop_retired_menu_grants(db)
            m.purge_personnel_cost_menu(db)
            db.commit()
        finally:
            db.close()

    def setUp(self) -> None:
        self.db = SessionLocal()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()

    def test_menu_row_is_gone(self):
        self.assertIn("personnel_costs", m.PURGED_MENU_SEED)
        self.assertNotIn("personnel_costs", m.RETIRED_MENU_SEED)
        self.assertNotIn("personnel_costs", [item[0] for item in m.RBAC_MENU_SEED])
        self.assertIsNone(self.db.scalar(select(Menu).where(Menu.code == "personnel_costs")))

    def test_history_grants_are_purged(self):
        db = self.db
        role = db.scalar(select(Role).order_by(Role.id))
        user_id = db.scalar(select(User.id).order_by(User.id))
        if role is None or user_id is None:
            self.skipTest("临时库没有可用的角色或用户")
        db.add(RoleDataScope(role_id=role.id, resource="personnel_costs", scope_type="ALL", department_id=None))
        db.add(UserRoleScope(user_id=user_id, role_id=role.id, resource="personnel_costs", scope_type="ALL", department_id=None))
        db.commit()

        m.purge_personnel_cost_menu(db)
        db.commit()

        self.assertEqual(
            db.scalar(select(RoleDataScope.id).where(RoleDataScope.resource == "personnel_costs")),
            None,
        )
        self.assertEqual(
            db.scalar(select(UserRoleScope.id).where(UserRoleScope.resource == "personnel_costs")),
            None,
        )
        # 菜单行已删除，指向它的 role_permissions 也应随之一并被清掉。
        dangling = db.execute(
            text(
                "SELECT COUNT(*) FROM role_permissions rp "
                "LEFT JOIN menus m ON m.id = rp.menu_id WHERE m.id IS NULL"
            )
        ).scalar()
        self.assertEqual(dangling, 0)
        _ = RolePermission

    def test_daily_cost_columns_are_dropped(self):
        inspector = sql_inspect(self.db.get_bind())
        expected_dropped = {
            "users": ["daily_cost"],
            "worklogs": ["daily_cost_snapshot", "cost_amount_snapshot"],
            "admin_permissions": ["can_manage_personnel_costs"],
        }
        for table, columns in expected_dropped.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for column in columns:
                self.assertNotIn(column, existing, f"{table}.{column} 仍存在")

    def test_api_routes_are_removed(self):
        paths = {route.path for route in m.app.routes}
        self.assertNotIn("/api/v1/admin/personnel-costs", paths)
        self.assertNotIn("/api/v1/admin/personnel-costs/{user_id}", paths)

    def test_workload_report_no_longer_uses_daily_cost(self):
        source = inspect.getsource(m.workload_report)
        self.assertNotIn("daily_cost", source)
        self.assertNotIn("missing_cost_user_count", source)
        # 取数改为期间内的人工成本结转流水。
        self.assertIn("PERSONNEL_COST", source)


if __name__ == "__main__":
    unittest.main()
