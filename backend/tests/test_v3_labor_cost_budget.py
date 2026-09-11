"""v3.0.67：人工成本结转固定归集到「人工费用」预算项，不再依赖界面选择。"""
import unittest

from fastapi import HTTPException

import app.main as m


class _FakeItem:
    """只提供 labor_budget_item 用到的字段。"""

    def __init__(self, name: str, code: str, source_kind: str, is_active: bool = True, sort_order: int = 0) -> None:
        self.name = name
        self.code = code
        self.source_kind = source_kind
        self.is_active = is_active
        self.sort_order = sort_order
        self.id = sort_order


class _FakeResult:
    def __init__(self, rows: list[_FakeItem]) -> None:
        self._rows = rows

    def all(self) -> list[_FakeItem]:
        return self._rows


class _FakeDb:
    """labor_budget_item 只用到 db.scalars(...).all()。"""

    def __init__(self, rows: list[_FakeItem]) -> None:
        self._rows = rows

    def scalars(self, _query):  # noqa: ANN001
        return _FakeResult(self._rows)


class LaborBudgetItemTest(unittest.TestCase):
    def test_prefers_labor_cost_code(self):
        rows = [
            _FakeItem("材料、设备采购", "MATERIAL_COST", "PROJECT_EXPENSE", sort_order=1),
            _FakeItem("人工费用", "LABOR_COST", "LABOR", sort_order=2),
        ]
        picked = m.labor_budget_item(_FakeDb(rows), 1)
        self.assertIs(picked, rows[1])

    def test_falls_back_to_labor_source_kind(self):
        rows = [
            _FakeItem("材料、设备采购", "MATERIAL_COST", "PROJECT_EXPENSE", sort_order=1),
            _FakeItem("人工成本", "CUSTOM_01", "LABOR", sort_order=2),
        ]
        picked = m.labor_budget_item(_FakeDb(rows), 1)
        self.assertIs(picked, rows[1])

    def test_falls_back_to_name(self):
        rows = [
            _FakeItem("材料、设备采购", "MATERIAL_COST", "PROJECT_EXPENSE", sort_order=1),
            _FakeItem("人工费", "CUSTOM_02", "PROJECT_EXPENSE", sort_order=2),
        ]
        picked = m.labor_budget_item(_FakeDb(rows), 1)
        self.assertIs(picked, rows[1])

    def test_prefers_active_item(self):
        rows = [
            _FakeItem("人工费用", "LABOR_COST", "LABOR", is_active=False, sort_order=1),
            _FakeItem("人工成本", "CUSTOM_01", "LABOR", is_active=True, sort_order=2),
        ]
        picked = m.labor_budget_item(_FakeDb(rows), 1)
        self.assertIs(picked, rows[1])

    def test_returns_none_without_items(self):
        self.assertIsNone(m.labor_budget_item(_FakeDb([]), 1))


class ResolveCostEntryBudgetItemTest(unittest.TestCase):
    def test_personnel_cost_ignores_submitted_budget_item(self):
        rows = [
            _FakeItem("材料、设备采购", "MATERIAL_COST", "PROJECT_EXPENSE", sort_order=1),
            _FakeItem("人工费用", "LABOR_COST", "LABOR", sort_order=2),
        ]
        picked = m.resolve_cost_entry_budget_item(_FakeDb(rows), "PERSONNEL_COST", 1, 999)
        self.assertIs(picked, rows[1])

    def test_personnel_cost_without_labor_item_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            m.resolve_cost_entry_budget_item(_FakeDb([]), "PERSONNEL_COST", 1, None)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "LABOR_BUDGET_ITEM_MISSING")


if __name__ == "__main__":
    unittest.main()
