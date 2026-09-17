"""v3.0.81 工时补填提醒（T-1）与提醒范围包含子部门。"""

from datetime import date, datetime, timedelta
import unittest
from unittest.mock import patch

from sqlalchemy import delete, select

from app.db.models import Department, NotificationPolicy, SystemNotification, User, Worklog
from app.db.session import SessionLocal, engine
from app.main import (
    WORKLOG_FILL_REMINDER_T1_DEFAULT_TIME,
    WORKLOG_FILL_REMINDER_T1_TYPE,
    expand_department_ids,
    previous_workday,
    run_worklog_fill_reminder_t1_scan_once,
    seed_notification_policies,
    upgrade_schema,
    worklog_reminder_recipients,
)
from app.services.feishu import FeishuAdapter
from app.time_utils import today_local


def _clear_reminder_data(db) -> None:
    for model in (SystemNotification, Worklog, NotificationPolicy, User, Department):
        db.execute(delete(model))
    db.commit()
    # 策略是全局共享数据，清完立刻补回，避免影响后续用例。
    seed_notification_policies(db)
    db.commit()


def _policy_of(db) -> NotificationPolicy:
    return db.scalar(
        select(NotificationPolicy).where(NotificationPolicy.notification_type == WORKLOG_FILL_REMINDER_T1_TYPE)
    )


class PreviousWorkdayTest(unittest.TestCase):
    def test_previous_workday_skips_weekend(self):
        # 2026-09-14 是周一，上一个工作日应为上周五 2026-09-11。
        self.assertEqual(previous_workday(date(2026, 9, 14)), date(2026, 9, 11))
        self.assertEqual(previous_workday(date(2026, 9, 13)), date(2026, 9, 11))
        self.assertEqual(previous_workday(date(2026, 9, 12)), date(2026, 9, 11))

    def test_previous_workday_inside_week(self):
        self.assertEqual(previous_workday(date(2026, 9, 16)), date(2026, 9, 15))
        self.assertLess(previous_workday(date(2026, 9, 16)).weekday(), 5)


class ReminderDepartmentScopeTest(unittest.TestCase):
    def setUp(self):
        upgrade_schema()
        self.db = SessionLocal()
        _clear_reminder_data(self.db)
        self.root = Department(feishu_department_id="T-ROOT", name="测试一级部门", parent_feishu_department_id=None)
        self.child = Department(feishu_department_id="T-CHILD", name="测试二级部门", parent_feishu_department_id="T-ROOT")
        self.grandchild = Department(feishu_department_id="T-GC", name="测试三级部门", parent_feishu_department_id="T-CHILD")
        self.other = Department(feishu_department_id="T-OTHER", name="无关部门", parent_feishu_department_id=None)
        self.db.add_all([self.root, self.child, self.grandchild, self.other])
        self.db.flush()
        self.child_user = User(
            name="子部门成员", feishu_user_id="t-child", department_id=self.child.id,
            employment_status="ACTIVE",
        )
        self.grandchild_user = User(
            name="孙部门成员", feishu_user_id="t-gc", department_id=self.grandchild.id,
            employment_status="ACTIVE",
        )
        self.outsider = User(
            name="无关成员", feishu_user_id="t-other", department_id=self.other.id,
            employment_status="ACTIVE",
        )
        self.resigned = User(
            name="已离职成员", feishu_user_id="t-resigned", department_id=self.child.id,
            employment_status="RESIGNED",
        )
        self.db.add_all([self.child_user, self.grandchild_user, self.outsider, self.resigned])
        self.db.commit()

    def tearDown(self):
        _clear_reminder_data(self.db)
        self.db.close()
        engine.dispose()

    def build_policy(self, **overrides) -> NotificationPolicy:
        policy = NotificationPolicy(
            notification_type=WORKLOG_FILL_REMINDER_T1_TYPE,
            label="工时补填提醒（T-1）",
            enabled=True,
            send_channel="mock",
            remind_days_before=0,
            schedule_time=WORKLOG_FILL_REMINDER_T1_DEFAULT_TIME,
            target_scope="DEPARTMENT",
            target_ids=str([self.root.id]),
            only_unfilled=True,
        )
        for key, value in overrides.items():
            setattr(policy, key, value)
        return policy

    def test_expand_department_ids_includes_descendants(self):
        expanded = expand_department_ids(self.db, [self.root.id])
        self.assertIn(self.root.id, expanded)
        self.assertIn(self.child.id, expanded)
        self.assertIn(self.grandchild.id, expanded)
        self.assertNotIn(self.other.id, expanded)

    def test_expand_department_ids_handles_unknown(self):
        self.assertEqual(expand_department_ids(self.db, []), [])
        # 部门已被组织架构同步删除时按空集合处理，避免范围失效后误发。
        self.assertEqual(expand_department_ids(self.db, [99999]), [])

    def test_recipients_include_sub_department_members(self):
        names = {item.name for item in worklog_reminder_recipients(self.db, self.build_policy())}
        self.assertEqual(names, {"子部门成员", "孙部门成员"})

    def test_recipients_scope_user_stays_exact(self):
        policy = self.build_policy(target_scope="USER", target_ids=str([self.outsider.id]))
        names = {item.name for item in worklog_reminder_recipients(self.db, policy)}
        self.assertEqual(names, {"无关成员"})


class WorklogFillReminderT1ScanTest(unittest.TestCase):
    def setUp(self):
        upgrade_schema()
        self.db = SessionLocal()
        _clear_reminder_data(self.db)
        self.department = Department(feishu_department_id="T1-DEPT", name="补漏测试部门", parent_feishu_department_id=None)
        self.db.add(self.department)
        self.db.flush()
        self.user = User(
            name="补漏对象", feishu_user_id="t1-user", department_id=self.department.id,
            employment_status="ACTIVE",
        )
        self.db.add(self.user)
        self.db.commit()
        policy = _policy_of(self.db)
        policy.enabled = True
        policy.send_channel = "mock"
        policy.schedule_time = WORKLOG_FILL_REMINDER_T1_DEFAULT_TIME
        policy.target_scope = "DEPARTMENT"
        policy.target_ids = str([self.department.id])
        policy.only_unfilled = True
        self.db.commit()

    def tearDown(self):
        _clear_reminder_data(self.db)
        self.db.close()
        engine.dispose()

    def test_force_scan_sends_once_then_skips(self):
        target_day = previous_workday(today_local())
        # 固定时刻，保证两次手动运行落在同一个幂等键上。
        fixed_now = datetime(2026, 9, 16, 10, 5, 0)
        with patch("app.main.now_local", return_value=fixed_now):
            first = run_worklog_fill_reminder_t1_scan_once(force=True)
            self.assertEqual(first["scanned"], 1)
            self.assertEqual(first["sent"], 1)
            keys = list(
                self.db.scalars(
                    select(SystemNotification.idempotency_key).where(
                        SystemNotification.notification_type == WORKLOG_FILL_REMINDER_T1_TYPE
                    )
                )
            )
            self.assertEqual(len(keys), 1)
            self.assertEqual(keys[0], f"worklog-fill-reminder-t1:{self.user.id}:{target_day.isoformat()}:manual1005")
            second = run_worklog_fill_reminder_t1_scan_once(force=True)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(second["skipped"], 1)

    def test_scan_skips_member_who_filled_previous_workday(self):
        target_day = previous_workday(today_local())
        self.db.add(
            Worklog(
                user_id=self.user.id, user_name_snapshot=self.user.name, project_id=0,
                project_name_snapshot="测试项目", stage="测试", work_type="测试", work_status="正常",
                fill_date=target_day, start_date=target_day, end_date=target_day, quantity=1,
                unit="DAY", description="补填", status="DRAFT",
            )
        )
        self.db.commit()
        result = run_worklog_fill_reminder_t1_scan_once(force=True)
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped"], 1)

    def test_disabled_policy_sends_nothing(self):
        _policy_of(self.db).enabled = False
        self.db.commit()
        result = run_worklog_fill_reminder_t1_scan_once(force=True)
        self.assertEqual(result, {"scanned": 0, "sent": 0, "failed": 0, "skipped": 0})


class WorklogFillReminderT1FeishuTest(unittest.TestCase):
    def test_mock_channel_returns_sent(self):
        adapter = FeishuAdapter()
        adapter.notification_mode = "mock"
        result = adapter.notify_worklog_fill_reminder_t1("张三", "2026-09-16（周三）", "http://localhost:8088/?page=worklogs")
        self.assertEqual(result.status, "SENT")
        self.assertTrue((result.message_id or "").startswith("MOCK-WORKLOG-FILL-T1-"))

    def test_app_channel_requires_open_id(self):
        adapter = FeishuAdapter()
        adapter.app_id = "cli_test"
        adapter.app_secret = "secret_test"
        result = adapter.notify_worklog_fill_reminder_t1(
            "张三", "2026-09-16（周三）", "http://localhost:8088/?page=worklogs", None, channel="app"
        )
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_message, "FEISHU_APP_RECIPIENT_OPEN_ID_MISSING")


if __name__ == "__main__":
    unittest.main()
