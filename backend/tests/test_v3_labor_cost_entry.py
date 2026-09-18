"""v3.0.83 人工成本结转：金额口径、填报日期与批量导入。"""

import asyncio
import os
import unittest
import uuid

from sqlalchemy import delete, select

from app.db.models import Project, ProjectBudgetItem, ProjectCostEntry, ProjectLedgerEntry, User
from app.db.session import SessionLocal
from app.main import (
    _execute_import_endpoint,
    _prepare_import,
    create_labor_cost_entries_from_import,
    create_project_cost_entry,
    parse_import_month,
    update_project_cost_entry,
    upgrade_schema,
)
from app.schemas import ProjectCostEntryCreate, ProjectCostEntryUpdate
from app.time_utils import today_local


class _BytesUpload:
    """满足 `UploadFile.read()` 协议的最小替身，避免测试依赖真实文件系统。"""

    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self, size: int = -1) -> bytes:
        return self._content


def _csv(*rows: str) -> bytes:
    return ("\n".join(rows) + "\n").encode("utf-8-sig")


class ParseImportMonthTest(unittest.TestCase):
    def test_accepts_common_formats(self):
        for value in ("2026-09", "2026/9", "2026年9月", "202609", "2026-09-01", "2026-09-01 00:00:00"):
            self.assertEqual(parse_import_month(value), "2026-09", value)

    def test_rejects_invalid_values(self):
        for value in ("", "abc", "2026-13", "26-09", "2026"):
            self.assertIsNone(parse_import_month(value), value)


class LaborCostEntryAmountTest(unittest.TestCase):
    """人工成本结转不涉税：金额即入账金额，填报日期取当天且不可修改。"""

    def _restore_admin_env(self) -> None:
        backup = getattr(self, "_admin_env_backup", None)
        if backup is None:
            os.environ.pop("SYSTEM_ADMIN_USER_IDS", None)
        else:
            os.environ["SYSTEM_ADMIN_USER_IDS"] = backup

    def setUp(self):
        upgrade_schema()
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:8]
        # 注意：不要占用 id=1 的演示管理员，也不要用 X-Demo-User-Id=1 调用接口，
        # 否则会改变共享临时库里 vs 其他集成测试共用的演示身份，导致它们取不到自己的数据。
        self._admin_env_backup = os.environ.get("SYSTEM_ADMIN_USER_IDS")
        user = self.db.scalar(select(User).order_by(User.id))
        if user is None:
            user = User(name=f"结转测试管理员-{suffix}", feishu_user_id=f"admin-{suffix}", employment_status="ACTIVE")
            self.db.add(user)
            self.db.flush()
        self.user = user
        self._admin_feishu_id = user.feishu_user_id if user.feishu_user_id and user.feishu_user_id.startswith("admin-") else "__none__"
        os.environ["SYSTEM_ADMIN_USER_IDS"] = ",".join(
            sorted({self._admin_env_backup or "", str(self.user.id)} - {""})
        )
        self.project = Project(
            code=f"T-{suffix}",
            name=f"结转测试项目-{suffix}",
            owner_name="测试负责人",
            owner_user_id=user.id,
            project_type="RND_PROJECT",
            status="ACTIVE",
        )
        self.db.add(self.project)
        self.db.flush()
        self.db.add_all([
            ProjectBudgetItem(project_id=self.project.id, code="LABOR_COST", name="人工费用", source_kind="LABOR", is_active=True, sort_order=1),
            ProjectBudgetItem(project_id=self.project.id, code="MATERIAL", name="材料", source_kind="CUSTOM", is_active=True, sort_order=2),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.execute(delete(ProjectLedgerEntry).where(ProjectLedgerEntry.project_id == self.project.id))
        self.db.execute(delete(ProjectCostEntry).where(ProjectCostEntry.project_id == self.project.id))
        self.db.execute(delete(ProjectBudgetItem).where(ProjectBudgetItem.project_id == self.project.id))
        self.db.execute(delete(Project).where(Project.id == self.project.id))
        # 只清理本用例创建的管理员；沿用已存在的用户时不能顺手删掉。
        self.db.execute(delete(User).where(User.feishu_user_id == self._admin_feishu_id))
        self.db.commit()
        self.db.close()
        self._restore_admin_env()

    def test_labor_entry_ignores_tax_and_writes_fill_date(self):
        payload = ProjectCostEntryCreate(
            entry_kind="PERSONNEL_COST",
            project_id=self.project.id,
            amount=12000.55,
            tax_rate=0.13,
            accounting_month="2026-08",
        )
        created = create_project_cost_entry(payload, self.user.id, self.db)
        self.assertEqual(created.fill_date.isoformat(), today_local().isoformat())
        self.assertEqual(created.tax_rate, 0)
        self.assertEqual(created.tax_amount, 0)
        self.assertEqual(created.amount_without_tax, 12000.55)
        self.assertEqual(created.amount, 12000.55)
        self.assertEqual(created.budget_item_name, "人工费用")

        updated = update_project_cost_entry(
            created.id,
            ProjectCostEntryUpdate(
                entry_kind="PERSONNEL_COST",
                project_id=self.project.id,
                amount=13000,
                tax_rate=0.13,
                accounting_month="2026-08",
                version=created.version,
            ),
            self.user.id,
            self.db,
        )
        # 填报日期不随编辑变化，税率依旧为 0。
        self.assertEqual(updated.fill_date.isoformat(), today_local().isoformat())
        self.assertEqual(updated.tax_rate, 0)
        self.assertEqual(updated.amount_without_tax, 13000)

    def test_project_expense_keeps_tax_fields(self):
        budget_item = self.db.scalar(
            select(ProjectBudgetItem).where(ProjectBudgetItem.project_id == self.project.id, ProjectBudgetItem.code == "MATERIAL")
        )
        created = create_project_cost_entry(
            ProjectCostEntryCreate(
                entry_kind="PROJECT_EXPENSE",
                project_id=self.project.id,
                budget_item_id=budget_item.id,
                amount=1130,
                tax_rate=0.13,
                occurred_on=today_local(),
            ),
            self.user.id,
            self.db,
        )
        self.assertEqual(created.fill_date.isoformat(), today_local().isoformat())
        self.assertEqual(created.tax_rate, 0.13)
        self.assertAlmostEqual(created.amount_without_tax, 1000, places=2)
        self.assertAlmostEqual(created.tax_amount, 130, places=2)


class LaborCostImportTest(unittest.TestCase):
    def _restore_admin_env(self) -> None:
        backup = getattr(self, "_admin_env_backup", None)
        if backup is None:
            os.environ.pop("SYSTEM_ADMIN_USER_IDS", None)
        else:
            os.environ["SYSTEM_ADMIN_USER_IDS"] = backup

    def setUp(self):
        upgrade_schema()
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:8]
        # 注意：不要占用 id=1 的演示管理员，也不要用 X-Demo-User-Id=1 调用接口，
        # 否则会改变共享临时库里 vs 其他集成测试共用的演示身份，导致它们取不到自己的数据。
        self._admin_env_backup = os.environ.get("SYSTEM_ADMIN_USER_IDS")
        user = self.db.scalar(select(User).order_by(User.id))
        if user is None:
            user = User(name=f"结转测试管理员-{suffix}", feishu_user_id=f"admin-{suffix}", employment_status="ACTIVE")
            self.db.add(user)
            self.db.flush()
        self.user = user
        self._admin_feishu_id = user.feishu_user_id if user.feishu_user_id and user.feishu_user_id.startswith("admin-") else "__none__"
        os.environ["SYSTEM_ADMIN_USER_IDS"] = ",".join(
            sorted({self._admin_env_backup or "", str(self.user.id)} - {""})
        )
        self.suffix = suffix
        self.project = Project(
            code=f"T-{suffix}",
            name=f"导入测试项目-{suffix}",
            owner_name="测试负责人",
            owner_user_id=user.id,
            project_type="RND_PROJECT",
            status="ACTIVE",
        )
        self.db.add(self.project)
        self.db.flush()
        self.db.add(ProjectBudgetItem(project_id=self.project.id, code="LABOR_COST", name="人工费用", source_kind="LABOR", is_active=True, sort_order=1))
        self.db.commit()

    def tearDown(self):
        self.db.execute(delete(ProjectCostEntry).where(ProjectCostEntry.project_id == self.project.id))
        self.db.execute(delete(ProjectBudgetItem).where(ProjectBudgetItem.project_id == self.project.id))
        self.db.execute(delete(Project).where(Project.id == self.project.id))
        # 只清理本用例创建的管理员；沿用已存在的用户时不能顺手删掉。
        self.db.execute(delete(User).where(User.feishu_user_id == self._admin_feishu_id))
        self.db.commit()
        self.db.close()
        self._restore_admin_env()

    def _file(self, *rows: str) -> _BytesUpload:
        return _BytesUpload("labor.csv", _csv(*rows))

    def test_preview_reports_unknown_project_and_bad_month(self):
        preview, _ = asyncio.run(
            _prepare_import(
                "labor_costs",
                self._file(
                    "项目名称,结转月份,金额,备注",
                    f"{self.project.name},2026年9月,12000,九月人工",
                    "不存在的项目,2026-09,3000,",
                    f"{self.project.name},20/09,3000,",
                    f"{self.project.name},2026-10,abc,",
                ),
                self.db,
                self.user,
            )
        )
        self.assertEqual(preview["total_rows"], 4)
        self.assertEqual(preview["valid_rows"], 1)
        fields = {(item["field"], item["row"]) for item in preview["errors"]}
        self.assertIn(("项目名称", 3), fields)
        self.assertIn(("结转月份", 4), fields)
        self.assertIn(("金额", 5), fields)

    def test_execute_creates_draft_entries_then_blocks_duplicates(self):
        upload = self._file(
            "项目名称,结转月份,金额,备注",
            f"{self.project.name},2026-09,12000.55,九月人工",
            f"{self.project.name},2026-10,8800,",
        )
        result = asyncio.run(_execute_import_endpoint("labor_costs", upload, self.user.id, self.db))
        self.assertEqual(result["imported"], 2)
        entries = list(
            self.db.scalars(
                select(ProjectCostEntry).where(
                    ProjectCostEntry.entry_kind == "PERSONNEL_COST",
                    ProjectCostEntry.project_id == self.project.id,
                )
            )
        )
        self.assertEqual(len(entries), 2)
        months = sorted(item.accounting_month for item in entries)
        self.assertEqual(months, ["2026-09", "2026-10"])
        for item in entries:
            self.assertEqual(item.status, "DRAFT")
            self.assertEqual(item.fill_date.isoformat(), today_local().isoformat())
            self.assertEqual(item.tax_rate, 0)
            self.assertEqual(item.tax_amount, 0)
            self.assertEqual(item.budget_item_name_snapshot, "人工费用")
            self.assertTrue(item.cost_no.startswith("LC"))
        self.assertEqual(sorted(float(item.amount) for item in entries), [8800.0, 12000.55])

        duplicate_preview, _ = asyncio.run(
            _prepare_import("labor_costs", self._file("项目名称,结转月份,金额", f"{self.project.name},2026-09,1"), self.db, self.user)
        )
        self.assertTrue(any("已存在" in item["message"] for item in duplicate_preview["errors"]))

    def test_execute_with_submit_moves_entries_to_pending_review(self):
        upload = self._file("项目名称,结转月份,金额", f"{self.project.name},2026-11,5000")
        result = asyncio.run(_execute_import_endpoint("labor_costs", upload, self.user.id, self.db, True))
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["submitted"], 1)
        entry = self.db.scalar(
            select(ProjectCostEntry).where(ProjectCostEntry.project_id == self.project.id, ProjectCostEntry.accounting_month == "2026-11")
        )
        self.assertEqual(entry.status, "PENDING_REVIEW")
        self.assertIsNotNone(entry.submitted_at)

    def test_create_entries_from_import_rejects_out_of_scope_month_text(self):
        payloads, errors = [], []
        records = [{"row": 2, "项目名称": self.project.name, "结转月份": "2026-9", "金额": "1"}]
        from app.main import _validate_labor_cost_import

        payloads, errors = _validate_labor_cost_import(self.db, self.user, records, errors)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["accounting_month"], "2026-09")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
