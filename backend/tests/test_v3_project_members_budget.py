"""v3.0.100 项目人员与项目人天预算控制。"""

from datetime import date
import os
import unittest
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.db.models import ApprovalTask, AuditLog, Notification, Project, ProjectMember, User, Worklog
from app.db.session import SessionLocal
from app.main import (
    add_project_members,
    backfill_project_members,
    list_worklog_project_options,
    project_workday_budget_view,
    remove_project_member,
    seed_data,
    submit_item,
    update_project_workday_budget,
    validate_worklog_budget,
    worklog_project_for_payload,
)
from app.schemas import ProjectMemberBatchAdd, ProjectWorkdayBudgetUpdate


class ProjectMembersBudgetTest(unittest.TestCase):
    def setUp(self) -> None:
        seed_data()
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:8]
        self._admin_env = os.environ.get("SYSTEM_ADMIN_USER_IDS")
        self.actor = self._user("管理员")
        self.owner = self._user("负责人")
        self.approver = self._user("审批人")
        self.member = self._user("成员")
        self.outsider = self._user("非成员")
        self.project = Project(
            code=f"RND-MEMBER-{self.suffix}",
            name=f"成员预算测试-{self.suffix}",
            project_type="RND_PROJECT",
            owner_name=self.owner.name,
            owner_user_id=self.owner.id,
            approver_name=self.approver.name,
            approver_user_id=self.approver.id,
            leader_name=self.approver.name,
            leader_user_id=self.approver.id,
            status="ACTIVE",
            allow_worklog=True,
            budget_days=2,
        )
        self.business_project = Project(
            code=f"BIZ-MEMBER-{self.suffix}",
            name=f"技术服务测试-{self.suffix}",
            project_type="BUSINESS_PROJECT",
            owner_name=self.actor.name,
            owner_user_id=self.actor.id,
            approver_name=self.approver.name,
            approver_user_id=self.approver.id,
            leader_name=self.approver.name,
            leader_user_id=self.approver.id,
            status="ACTIVE",
            allow_worklog=True,
            budget_days=10,
        )
        self.db.add_all([self.project, self.business_project])
        self.db.flush()
        backfill_project_members(self.db)
        self.db.add(ProjectMember(project_id=self.project.id, user_id=self.member.id, status="ACTIVE"))
        self.db.add(ProjectMember(project_id=self.business_project.id, user_id=self.member.id, status="ACTIVE"))
        self.db.commit()
        os.environ["SYSTEM_ADMIN_USER_IDS"] = str(self.actor.id)

    def tearDown(self) -> None:
        project_ids = [self.project.id, self.business_project.id]
        worklog_ids = list(self.db.scalars(select(Worklog.id).where(Worklog.project_id.in_(project_ids))).all())
        task_ids = list(self.db.scalars(select(ApprovalTask.id).where(ApprovalTask.worklog_id.in_(worklog_ids))).all()) if worklog_ids else []
        if task_ids:
            self.db.execute(delete(Notification).where(Notification.approval_task_id.in_(task_ids)))
            self.db.execute(delete(ApprovalTask).where(ApprovalTask.id.in_(task_ids)))
        if worklog_ids:
            self.db.execute(delete(Worklog).where(Worklog.id.in_(worklog_ids)))
        self.db.execute(delete(ProjectMember).where(ProjectMember.project_id.in_(project_ids)))
        self.db.execute(delete(AuditLog).where(AuditLog.object_type == "project", AuditLog.object_id.in_(project_ids)))
        self.db.execute(delete(Project).where(Project.id.in_(project_ids)))
        self.db.execute(delete(User).where(User.feishu_user_id.like(f"test-{self.suffix}-%")))
        self.db.commit()
        self.db.close()
        if self._admin_env is None:
            os.environ.pop("SYSTEM_ADMIN_USER_IDS", None)
        else:
            os.environ["SYSTEM_ADMIN_USER_IDS"] = self._admin_env

    def _user(self, label: str) -> User:
        user = User(
            feishu_user_id=f"test-{self.suffix}-{label}",
            name=f"{label}-{self.suffix}",
            employment_status="ACTIVE",
        )
        self.db.add(user)
        self.db.flush()
        return user

    def _worklog(
        self,
        *,
        user: User | None = None,
        project: Project | None = None,
        status: str = "DRAFT",
        work_date: date = date(2026, 10, 20),
    ) -> Worklog:
        target_user = user or self.member
        target_project = project or self.project
        item = Worklog(
            user_id=target_user.id,
            user_name_snapshot=target_user.name,
            project_id=target_project.id,
            project_name_snapshot=target_project.name,
            stage="开发",
            work_type="RND_PROJECT_WORK" if target_project.project_type == "RND_PROJECT" else "TECH_SERVICE_WORK",
            work_status="LOCAL",
            fill_date=work_date,
            start_date=work_date,
            end_date=work_date,
            quantity=1,
            unit="DAY",
            description="项目成员与预算测试记录",
            status=status,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def test_owner_backfill_and_owner_cannot_be_removed(self) -> None:
        owner_member = self.db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == self.project.id,
                ProjectMember.user_id == self.owner.id,
            )
        )
        self.assertIsNotNone(owner_member)
        self.assertEqual(owner_member.member_role, "OWNER")
        self.assertEqual(owner_member.status, "ACTIVE")
        with self.assertRaises(HTTPException) as raised:
            remove_project_member(self.project.id, self.owner.id, self.actor.id, self.db)
        self.assertEqual(raised.exception.detail, "PROJECT_OWNER_CANNOT_REMOVE")

    def test_batch_add_is_idempotent_and_reactivates_member(self) -> None:
        member = self.db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == self.project.id,
                ProjectMember.user_id == self.member.id,
            )
        )
        member.status = "INACTIVE"
        self.db.commit()
        result = add_project_members(
            self.project.id,
            ProjectMemberBatchAdd(user_ids=[self.member.id, self.outsider.id, self.outsider.id]),
            self.actor.id,
            self.db,
        )
        self.assertEqual(result.reactivated_count, 1)
        self.assertEqual(result.added_count, 1)
        again = add_project_members(
            self.project.id,
            ProjectMemberBatchAdd(user_ids=[self.member.id, self.outsider.id]),
            self.actor.id,
            self.db,
        )
        self.assertEqual(again.existing_count, 2)

    def test_project_options_are_member_and_type_filtered(self) -> None:
        rnd = list_worklog_project_options("RND_PROJECT_WORK", self.member.id, self.db)
        technical = list_worklog_project_options("TECH_SERVICE_WORK", self.member.id, self.db)
        self.assertIn(self.project.id, {item.project_id for item in rnd})
        self.assertNotIn(self.business_project.id, {item.project_id for item in rnd})
        self.assertIn(self.business_project.id, {item.project_id for item in technical})
        outsider_options = list_worklog_project_options("RND_PROJECT_WORK", self.outsider.id, self.db)
        self.assertNotIn(self.project.id, {item.project_id for item in outsider_options})

    def test_non_member_cannot_save_project_worklog(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            worklog_project_for_payload(self.db, "RND_PROJECT_WORK", self.project.id, self.outsider.id)
        self.assertEqual(raised.exception.detail, "PROJECT_MEMBERSHIP_REQUIRED")

    def test_pending_occupies_budget_and_rejection_releases_it(self) -> None:
        pending = self._worklog(status="PENDING_APPROVAL")
        summary = project_workday_budget_view(self.db, self.project)
        self.assertEqual(summary.occupied_days, 1)
        self.assertEqual(summary.actual_days, 0)
        validate_worklog_budget(self.db, self.project, 1)
        with self.assertRaises(HTTPException) as raised:
            validate_worklog_budget(self.db, self.project, 2)
        self.assertEqual(raised.exception.detail, "WORKDAY_BUDGET_EXCEEDED")
        pending.status = "REJECTED"
        self.db.commit()
        self.assertEqual(project_workday_budget_view(self.db, self.project).occupied_days, 0)

    def test_submit_blocks_unconfigured_and_exceeded_budget(self) -> None:
        draft = self._worklog()
        self.project.budget_days = 0
        self.db.commit()
        with self.assertRaises(HTTPException) as raised:
            submit_item(self.db, draft, self.member)
        self.assertEqual(raised.exception.detail, "WORKDAY_BUDGET_NOT_CONFIGURED")
        self.db.rollback()
        self.project = self.db.get(Project, self.project.id)
        self.project.budget_days = 1
        self.db.commit()
        first = self.db.get(Worklog, draft.id)
        submit_item(self.db, first, self.db.get(User, self.member.id))
        second = self._worklog(work_date=date(2026, 10, 21))
        with self.assertRaises(HTTPException) as raised:
            submit_item(self.db, second, self.db.get(User, self.member.id))
        self.assertEqual(raised.exception.detail, "WORKDAY_BUDGET_EXCEEDED")
        self.db.rollback()

    def test_budget_cannot_be_reduced_below_occupied(self) -> None:
        self._worklog(status="APPROVED")
        with self.assertRaises(HTTPException) as raised:
            update_project_workday_budget(
                self.project.id,
                ProjectWorkdayBudgetUpdate(budget_days=0.5),
                self.actor.id,
                self.db,
            )
        self.assertEqual(raised.exception.detail, "WORKDAY_BUDGET_BELOW_OCCUPIED")


if __name__ == "__main__":
    unittest.main()
