import os
import unittest
from datetime import date, datetime
from unittest.mock import patch

from pydantic import ValidationError
from fastapi import HTTPException

from app.db.models import OrgSyncLog
from app.main import app, attachment_preview_kind, validate_worklog_quantity, worklog_workday_count
from app.schemas import CashDocumentAttachmentView, IntegrationNotificationView, OrgSyncLogView, ProjectCreate, ProjectList, ProjectView, WorklogCreate
from app.services.feishu import FeishuAdapter


class V3ProjectSchemaTest(unittest.TestCase):
    def project_payload(self) -> dict:
        return {
            "code": "SS-2026-008",
            "name": "智慧工地机器人协同平台",
            "project_type": "IMPLEMENTATION_PROJECT",
            "owner_user_id": 1,
            "department_id": 1,
            "approver_user_id": 2,
            "leader_user_id": 3,
            "customer_id": 7,
            "start_date": "2026-03-01",
            "planned_end_date": "2026-12-31",
            "description": "施工现场机器人协同调度与状态监测。",
            "budget_days": 50,
            "budget_cost": 680000,
            "status": "ACTIVE",
            "allow_worklog": True,
        }

    def test_project_create_accepts_confirmed_master_fields(self):
        project = ProjectCreate.model_validate(self.project_payload())
        self.assertEqual(project.customer_id, 7)
        self.assertEqual(project.start_date, date(2026, 3, 1))
        self.assertEqual(project.planned_end_date, date(2026, 12, 31))
        self.assertIn("机器人", project.description)

    def test_project_dates_must_be_ordered(self):
        payload = self.project_payload()
        payload["start_date"] = "2026-12-31"
        payload["planned_end_date"] = "2026-03-01"
        with self.assertRaises(ValidationError):
            ProjectCreate.model_validate(payload)

    def test_project_list_has_server_side_pagination(self):
        project = ProjectView.model_validate(
            {
                **self.project_payload(),
                "id": 1,
                "owner_name": "杨阳",
                "approver_name": "樊公海",
                "leader_name": "陈总",
                "department_name": "信息化中心",
                "department_path": "产品研发部 / 信息化中心",
                "customer_name": "四川华西集团",
                "actual_days": 36,
                "personnel_cost": 36000,
                "owner_user_id": 1,
                "approver_user_id": 2,
                "leader_user_id": 3,
            }
        )
        result = ProjectList(items=[project], total=28, page=2, page_size=20, page_count=2)
        self.assertEqual(result.total, 28)
        self.assertEqual(result.page_count, 2)

    def test_worklog_quantity_requires_integer_date_span(self):
        payload = {
            "project_id": 1,
            "stage": "开发",
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "quantity": 1.5,
            "unit": "DAY",
            "description": "日期天数校验",
        }
        with self.assertRaises(ValidationError):
            WorklogCreate.model_validate(payload)

        validate_worklog_quantity(date(2026, 9, 1), date(2026, 9, 3), 3)
        with self.assertRaises(HTTPException) as context:
            validate_worklog_quantity(date(2026, 9, 1), date(2026, 9, 3), 2)
        self.assertEqual(context.exception.detail, "WORKLOG_QUANTITY_MISMATCH")

    def test_worklog_quantity_counts_weekdays_only(self):
        self.assertEqual(worklog_workday_count(date(2026, 9, 4), date(2026, 9, 7)), 2)
        self.assertEqual(worklog_workday_count(date(2026, 9, 5), date(2026, 9, 6)), 0)
        with self.assertRaises(HTTPException) as context:
            validate_worklog_quantity(date(2026, 9, 5), date(2026, 9, 6), 1)
        self.assertEqual(context.exception.detail, "WORKLOG_NO_WORKDAY")


class V310IntegrationCenterTest(unittest.TestCase):
    def test_notification_policy_channel_overrides_environment_default(self):
        with patch.dict(os.environ, {"FEISHU_NOTIFICATION_MODE": "app", "FEISHU_APP_ID": "", "FEISHU_APP_SECRET": ""}, clear=False):
            adapter = FeishuAdapter()
            result = adapter.notify_project_warning("负责人", "测试项目", "预算预警", "成本接近上限", "http://localhost", channel="mock")
        self.assertEqual(result.status, "SENT")
        self.assertTrue((result.message_id or "").startswith("MOCK-PROJECT-WARNING-"))

    def test_org_sync_log_view_accepts_orm_record(self):
        item = OrgSyncLog(
            id=1,
            status="SUCCESS",
            mode="app",
            user_count=22,
            department_count=12,
            created_at=datetime(2026, 9, 1, 10, 0, 0),
        )
        view = OrgSyncLogView.model_validate(item)
        self.assertEqual(view.user_count, 22)
        self.assertEqual(view.department_count, 12)

    def test_notification_log_contract_contains_retry_and_business_context(self):
        item = IntegrationNotificationView.model_validate({
            "id": 1,
            "notification_type": "SETTLEMENT_APPROVED",
            "source_type": "payment",
            "source_id": 8,
            "source_label": "PAY-20260901-0008",
            "recipient_name": "杨阳",
            "channel": "app",
            "status": "FAILED",
            "error_message": "FEISHU_APP_RECIPIENT_OPEN_ID_MISSING",
            "retry_count": 2,
            "created_at": "2026-09-01T10:00:00",
        })
        self.assertEqual(item.source_label, "PAY-20260901-0008")
        self.assertEqual(item.retry_count, 2)
        self.assertEqual(item.status, "FAILED")

    def test_integration_center_routes_are_registered(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/api/v1/integrations/overview", paths)
        self.assertIn("/api/v1/integrations/notifications", paths)
        self.assertIn("/api/v1/integrations/notifications/{notification_id}", paths)
        self.assertIn("/api/v1/integrations/notifications/{notification_id}/retry", paths)
        self.assertIn("/api/v1/integrations/sync-logs", paths)
        self.assertIn("/api/v1/admin/worklogs/export", paths)


class ContractAttachmentPreviewTest(unittest.TestCase):
    def test_legacy_and_modern_office_files_are_previewable_types(self):
        self.assertEqual(attachment_preview_kind("合同.doc"), "word")
        self.assertEqual(attachment_preview_kind("合同.docx"), "word")
        self.assertEqual(attachment_preview_kind("清单.xls"), "excel")
        self.assertEqual(attachment_preview_kind("清单.xlsx"), "excel")
        self.assertEqual(attachment_preview_kind("汇报.ppt"), "powerpoint")
        self.assertEqual(attachment_preview_kind("汇报.pptx"), "powerpoint")

    def test_cash_attachment_routes_and_response_contract_are_available(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/api/v1/receipts/{receipt_id}/attachments", paths)
        self.assertIn("/api/v1/payments/{payment_id}/attachments", paths)
        self.assertIn("/api/v1/cash-attachments/{attachment_id}/preview", paths)
        self.assertIn("/api/v1/cash-attachments/{attachment_id}/download", paths)
        self.assertIn("/api/v1/cash-attachments/{attachment_id}", paths)
        view = CashDocumentAttachmentView.model_validate({
            "document_type": "PAYMENT",
            "document_id": 8,
            "id": 2,
            "file_name": "付款回单.pdf",
            "mime_type": "application/pdf",
            "file_size": 128,
            "uploaded_by": 1,
            "uploaded_by_name": "杨阳",
            "created_at": "2026-09-01T10:00:00",
            "can_preview": True,
            "preview_kind": "pdf",
        })
        self.assertEqual(view.document_type, "PAYMENT")
        self.assertTrue(view.can_preview)


if __name__ == "__main__":
    unittest.main()
