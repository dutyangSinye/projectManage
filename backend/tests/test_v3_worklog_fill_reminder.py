"""v3.0.64 工时填报定时提醒的策略配置与扫描逻辑。"""

from datetime import date, datetime
import unittest

from fastapi import HTTPException

from app.db.models import NotificationPolicy
from app.db.session import SessionLocal, engine
from app.main import (
    WORKLOG_FILL_REMINDER_DEFAULT_TIME,
    WORKLOG_FILL_REMINDER_TYPE,
    _policy_id_list,
    has_worklog_on,
    upgrade_schema,
    parse_reminder_times,
    validated_schedule_time,
    validated_target_ids,
    worklog_fill_reminder_due,
    worklog_reminder_recipients,
)
from app.services.feishu import FeishuAdapter


def build_policy(**overrides) -> NotificationPolicy:
    policy = NotificationPolicy(
        notification_type=WORKLOG_FILL_REMINDER_TYPE,
        label="工时填报提醒",
        enabled=True,
        send_channel="mock",
        remind_days_before=0,
        schedule_time="09:00,17:30",
        target_scope="ALL",
        target_ids=None,
        only_unfilled=True,
    )
    for key, value in overrides.items():
        setattr(policy, key, value)
    return policy


class WorklogFillReminderPolicyTest(unittest.TestCase):
    def test_parse_reminder_times_accepts_mixed_separators(self):
        self.assertEqual(parse_reminder_times("09:00,17:30"), ["09:00", "17:30"])
        self.assertEqual(parse_reminder_times("9:00， 18：05"), ["09:00", "18:05"])

    def test_parse_reminder_times_drops_invalid_slots(self):
        self.assertEqual(parse_reminder_times("24:00, 09:60, abc, 08:30"), ["08:30"])
        self.assertEqual(parse_reminder_times(""), [])
        self.assertEqual(parse_reminder_times(None), [])

    def test_due_matches_slot_window_on_workday(self):
        policy = build_policy()
        self.assertEqual(worklog_fill_reminder_due(policy, datetime(2026, 9, 14, 9, 0)), "09:00")
        self.assertEqual(worklog_fill_reminder_due(policy, datetime(2026, 9, 14, 9, 9)), "09:00")
        self.assertIsNone(worklog_fill_reminder_due(policy, datetime(2026, 9, 14, 9, 10)))
        self.assertEqual(worklog_fill_reminder_due(policy, datetime(2026, 9, 14, 17, 35)), "17:30")

    def test_due_skips_weekend(self):
        policy = build_policy()
        self.assertIsNone(worklog_fill_reminder_due(policy, datetime(2026, 9, 12, 9, 0)))
        self.assertIsNone(worklog_fill_reminder_due(policy, datetime(2026, 9, 13, 9, 0)))

    def test_due_falls_back_to_default_time(self):
        policy = build_policy(schedule_time="")
        self.assertEqual(worklog_fill_reminder_due(policy, datetime(2026, 9, 14, 9, 1)), WORKLOG_FILL_REMINDER_DEFAULT_TIME)

    def test_policy_id_list_reads_json_ids(self):
        self.assertEqual(_policy_id_list("[3, 1]"), [3, 1])
        self.assertEqual(_policy_id_list("bad json"), [])
        self.assertEqual(_policy_id_list(None), [])
        self.assertEqual(_policy_id_list('{"a": 1}'), [])

    def test_schedule_time_validation(self):
        self.assertEqual(validated_schedule_time("09:00"), "09:00")
        self.assertEqual(validated_schedule_time(""), "")
        self.assertIsNone(validated_schedule_time(None))
        with self.assertRaises(HTTPException):
            validated_schedule_time("25:00")
        with self.assertRaises(HTTPException):
            validated_schedule_time("明天早上")

    def test_target_ids_validation(self):
        self.assertEqual(validated_target_ids("[1,2]"), "[1, 2]")
        self.assertEqual(validated_target_ids(""), "[]")
        with self.assertRaises(HTTPException):
            validated_target_ids("[1, \"two\"]")
        with self.assertRaises(HTTPException):
            validated_target_ids("not json")

    def test_recipients_scope_filters_need_ids(self):
        # 没有会话时不查库，只保证空目标直接返回空集合，避免全量误发。
        class _FakeSession:
            def scalars(self, *_args, **_kwargs):  # pragma: no cover - 不该被调用
                raise AssertionError("空目标集合不应查询数据库")

        self.assertEqual(worklog_reminder_recipients(_FakeSession(), build_policy(target_scope="USER", target_ids="[]")), [])
        self.assertEqual(
            worklog_reminder_recipients(_FakeSession(), build_policy(target_scope="DEPARTMENT", target_ids=None)),
            [],
        )

    def test_has_worklog_on_matches_date_range(self):
        upgrade_schema()
        db = SessionLocal()
        try:
            self.assertFalse(has_worklog_on(db, -1, date(2026, 9, 14)))
        finally:
            db.close()
            engine.dispose()


class WorklogFillReminderFeishuTest(unittest.TestCase):
    def test_mock_channel_returns_sent(self):
        adapter = FeishuAdapter()
        adapter.notification_mode = "mock"
        result = adapter.notify_worklog_fill_reminder("张三", "2026-09-14（周一）", "http://localhost:8088/?page=worklogs")
        self.assertEqual(result.status, "SENT")
        self.assertTrue((result.message_id or "").startswith("MOCK-WORKLOG-FILL-"))

    def test_app_channel_requires_open_id(self):
        adapter = FeishuAdapter()
        adapter.app_id = "cli_test"
        adapter.app_secret = "secret_test"
        result = adapter.notify_worklog_fill_reminder("张三", "2026-09-14（周一）", "http://localhost:8088/?page=worklogs", None, channel="app")
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_message, "FEISHU_APP_RECIPIENT_OPEN_ID_MISSING")


if __name__ == "__main__":
    unittest.main()
