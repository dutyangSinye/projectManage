import unittest
from datetime import datetime

from app.schemas import ReportView


class ReportSchemaRegressionTest(unittest.TestCase):
    def test_project_without_cost_budget_accepts_null_usage_rate(self):
        report = ReportView.model_validate(
            {
                "scope": {
                    "period_start": "2026-08-01",
                    "period_end": "2026-08-28",
                    "department_name": "全部部门",
                    "department_options": [],
                    "status": ["APPROVED", "LOCKED"],
                },
                "metrics": {"total_days": 0},
                "breakdowns": {
                    "by_project_budget_actual": [
                        {
                            "name": "未配置成本预算的项目",
                            "unit": "DAY",
                            "budget_days": 10,
                            "actual_days": 0,
                            "budget_cost": 0,
                            "actual_cost": 0,
                            "remaining_cost": 0,
                            "cost_usage_rate": None,
                        }
                    ]
                },
                "generated_at": datetime.now(),
            }
        )
        self.assertIsNone(report.breakdowns["by_project_budget_actual"][0]["cost_usage_rate"])


if __name__ == "__main__":
    unittest.main()
