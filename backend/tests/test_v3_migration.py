import os
import tempfile
import unittest
import uuid
from unittest.mock import patch
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace


_temp_dir = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_temp_dir.name) / 'v3-test.db'}"
os.environ["FEISHU_MODE"] = "mock"
os.environ["SYSTEM_ADMIN_USER_IDS"] = "1"

from sqlalchemy import func, inspect, select

from app.db.session import SessionLocal, engine
from fastapi import HTTPException

from app.db.models import AdminPermission, ApprovalPosition, ApprovalPositionMember, ApprovalTask, ConfigOption, Department, Notification, NotificationPolicy, Payment, Project, ProjectBudgetItem, ProjectCostEntry, ProjectExpense, ProjectExpenseAttachment, ProjectExpensePayment, ProjectLedgerEntry, Role, RoleDataScope, RolePermission, SystemNotification, User, UserRole, UserRoleScope, WorkflowTask, Worklog
from app.main import (
    activate_contract,
    approve_payment,
    approve_receipt,
    create_contract,
    create_contract_stage,
    create_payment,
    create_receipt,
    create_supplier,
    create_worklog,
    create_project,
    create_project_expense,
    create_project_cost_entry,
    delete_project,
    demo_seed_enabled,
    get_role_permissions,
    get_effective_permissions,
    list_project_board,
    list_project_board_options,
    list_payment_attachments,
    list_projects_page,
    project_finance_summary,
    project_view,
    project_expense_view,
    approve_workflow_task,
    confirm_expense_payment,
    list_workflow_tasks,
    submit_worklog,
    submit_project_expense,
    submit_project_cost_entry,
    submit_payment,
    run_stage_reminder_scan_once,
    send_cash_approval_notifications,
    seed_data,
    update_user_roles,
    create_role,
    FIRST_FEISHU_ADMIN_MARKER,
    initialize_first_feishu_admin,
    ensure_oauth_user,
    system_admin_user_ids,
    reset_rbac_configuration,
    reject_payment,
    retry_integration_notification,
    update_role_permissions,
    update_notification_policies,
    update_project,
    update_payment,
    upgrade_schema,
    workbench_overview,
)
from app.schemas import CashRejectAction, ContractCreate, ContractStageCreate, DataScopeInput, NotificationPolicyBatchItem, NotificationPolicyBatchUpdate, PaymentCreate, PaymentUpdate, ProjectCreate, ProjectCostEntryCreate, ProjectExpenseCreate, ProjectExpensePaymentAction, ProjectUpdate, ReceiptCreate, RoleCreate, RolePermissionInput, RolePermissionsUpdate, SupplierCreate, UserRoleUpdate, WorkflowTaskAction, WorklogCreate


class V3MigrationIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        upgrade_schema()
        upgrade_schema()
        seed_data()

    @classmethod
    def tearDownClass(cls):
        engine.dispose()
        _temp_dir.cleanup()

    def test_query_indexes_are_created_by_schema_upgrade(self):
        inspector = inspect(engine)
        expected = {
            "worklogs": {"ix_worklogs_user_date", "ix_worklogs_project_status_date", "ix_worklogs_user_fill_date"},
            "approval_tasks": {"ix_approval_tasks_approver_status"},
            "contracts": {"ix_contracts_project_type_status"},
            "receipts": {"ix_receipts_project_status_date"},
            "payments": {"ix_payments_project_status_date"},
            "project_expenses": {"ix_project_expenses_project_status"},
            "workflow_tasks": {"ix_workflow_tasks_assignee_status"},
            "project_cost_entries": {"ix_project_cost_entries_project_kind_status"},
        }
        for table, index_names in expected.items():
            existing = {item["name"] for item in inspector.get_indexes(table)}
            self.assertTrue(index_names.issubset(existing), f"{table} missing {index_names - existing}")

    def test_worklog_fill_date_is_saved_and_defaults_to_start_date(self):
        db = SessionLocal()
        created_ids: list[int] = []
        try:
            project = db.scalar(select(Project).where(Project.status == "ACTIVE", Project.allow_worklog == True).order_by(Project.id))
            self.assertIsNotNone(project)
            start = date(date.today().year + 5, 1, 6)
            while start.weekday() >= 5:
                start += timedelta(days=1)
            explicit_fill_date = start - timedelta(days=2)
            created = create_worklog(
                WorklogCreate(
                    project_id=project.id,
                    stage="开发",
                    work_type="PROJECT",
                    work_status="LOCAL",
                    fill_date=explicit_fill_date,
                    start_date=start,
                    end_date=start,
                    quantity=1,
                    unit="DAY",
                    description="填报日期显式保存回归测试",
                    submit=False,
                ),
                x_demo_user_id=1,
                db=db,
            )
            created_ids.append(created.id)
            self.assertEqual(created.fill_date, explicit_fill_date)

            default_start = start + timedelta(days=7)
            created_default = create_worklog(
                WorklogCreate(
                    project_id=project.id,
                    stage="开发",
                    work_type="PROJECT",
                    work_status="LOCAL",
                    start_date=default_start,
                    end_date=default_start,
                    quantity=1,
                    unit="DAY",
                    description="填报日期默认开始日期回归测试",
                    submit=False,
                ),
                x_demo_user_id=1,
                db=db,
            )
            created_ids.append(created_default.id)
            self.assertEqual(created_default.fill_date, default_start)
        finally:
            if created_ids:
                db.query(Worklog).filter(Worklog.id.in_(created_ids)).delete(synchronize_session=False)
                db.commit()
            db.close()

    def create_payment_fixture(self, db, suffix: str, *, stage_amount: float = 1000, payment_amount: float = 600):
        supplier = create_supplier(
            SupplierCreate(code=f"SUP-PAY-{suffix}", name=f"付款流程供应商-{suffix}", status="ACTIVE"),
            x_demo_user_id=1,
            db=db,
        )
        project = db.scalar(select(Project).where(Project.status != "DELETED").order_by(Project.id))
        contract = create_contract(
            ContractCreate(
                contract_no=f"CT-PAY-{suffix}",
                name=f"付款流程合同-{suffix}",
                project_id=project.id,
                contract_type="EXPENSE",
                counterparty_type="SUPPLIER",
                counterparty_id=supplier.id,
                amount=stage_amount,
                status="ACTIVE",
            ),
            x_demo_user_id=1,
            db=db,
        )
        stage = create_contract_stage(
            contract.id,
            ContractStageCreate(name="付款阶段", amount=stage_amount, planned_date="2030-09-30"),
            x_demo_user_id=1,
            db=db,
        )
        payment = create_payment(
            PaymentCreate(
                contract_id=contract.id,
                stage_id=stage.id,
                amount=payment_amount,
                payment_date="2026-09-07",
                payee_name=supplier.name,
                payee_bank_name="测试银行",
                payee_bank_account="6222000012345678",
            ),
            x_demo_user_id=1,
            db=db,
        )
        return project, contract, stage, payment

    def grant_cost_review_position(self, db, user_id: int):
        """把费用复核岗位成员收敛为指定用户，用于验证一级费用复核的授权边界。"""
        position = db.scalar(select(ApprovalPosition).where(ApprovalPosition.code == "COST_REVIEWER"))
        self.assertIsNotNone(position, "费用复核岗位未初始化")
        db.query(ApprovalPositionMember).delete(synchronize_session=False)
        db.add(ApprovalPositionMember(position_id=position.id, user_id=user_id))
        db.commit()
        return position

    def test_project_cost_entry_can_submit_without_attachment(self):
        db = SessionLocal()
        try:
            suffix = uuid.uuid4().hex[:8]
            department = db.scalar(select(Department).order_by(Department.id))
            self.assertIsNotNone(department)
            project = create_project(
                ProjectCreate(
                    code=f"PRJ-NOATT-{suffix}",
                    name=f"无附件项目费用测试-{suffix}",
                    project_type="BUSINESS_PROJECT",
                    owner_user_id=1,
                    department_id=department.id,
                    approver_user_id=1,
                    leader_user_id=1,
                    start_date="2026-09-01",
                    planned_end_date="2026-12-31",
                    description="验证项目费用新增时附件可选。",
                    budget_days=10,
                    budget_cost=100000,
                    status="ACTIVE",
                    allow_worklog=True,
                ),
                x_demo_user_id=1,
                db=db,
            )
            budget_item = db.scalar(
                select(ProjectBudgetItem).where(
                    ProjectBudgetItem.project_id == project.id,
                    ProjectBudgetItem.code != "LABOR_COST",
                    ProjectBudgetItem.is_active == True,
                ).order_by(ProjectBudgetItem.sort_order, ProjectBudgetItem.id)
            )
            self.assertIsNotNone(budget_item)
            self.grant_cost_review_position(db, 2)
            entry = create_project_cost_entry(
                ProjectCostEntryCreate(
                    entry_kind="PROJECT_EXPENSE",
                    project_id=project.id,
                    budget_item_id=budget_item.id,
                    amount=1280,
                    occurred_on=date.today(),
                    description="无附件提交复核测试",
                ),
                x_demo_user_id=1,
                db=db,
            )
            self.assertEqual(entry.attachments, [])
            notify_result = SimpleNamespace(status="SENT", message_id="msg-cost-no-attachment", error_message=None)
            with patch("app.main.feishu.notify_cash_approval_submitted", return_value=notify_result):
                submitted = submit_project_cost_entry(entry.id, x_demo_user_id=1, db=db)
            self.assertEqual(submitted.status, "PENDING_REVIEW")
            self.assertEqual(db.get(ProjectCostEntry, entry.id).status, "PENDING_REVIEW")
            task = db.scalar(select(SystemNotification).where(
                SystemNotification.source_type == "project_cost_project_expense",
                SystemNotification.source_id == entry.id,
            ))
            self.assertIsNotNone(task)
        finally:
            db.close()

    def test_upgrade_is_idempotent_and_adds_v3_columns(self):
        project_columns = {column["name"] for column in inspect(engine).get_columns("projects")}
        permission_columns = {column["name"] for column in inspect(engine).get_columns("admin_permissions")}
        payment_columns = {column["name"] for column in inspect(engine).get_columns("payments")}
        self.assertTrue({"customer_id", "start_date", "planned_end_date", "description"}.issubset(project_columns))
        self.assertTrue({"can_manage_contracts", "can_approve_cash", "project_data_scope"}.issubset(permission_columns))
        self.assertTrue({"current_workflow_instance_id", "version"}.issubset(payment_columns))

    def test_app_mode_does_not_seed_demo_data_by_default(self):
        with patch.dict(os.environ, {"SEED_DEMO_DATA": "false"}), patch("app.main.feishu.mode", "app"):
            self.assertFalse(demo_seed_enabled())
        with patch.dict(os.environ, {"SEED_DEMO_DATA": "true"}), patch("app.main.feishu.mode", "app"):
            self.assertTrue(demo_seed_enabled())

    def test_first_feishu_login_initializes_admin_once(self):
        db = SessionLocal()
        try:
            first_user = db.get(User, 2)
            second_user = db.get(User, 3)
            with patch.dict(os.environ, {"SYSTEM_ADMIN_USER_IDS": ""}), patch("app.main.feishu.mode", "app"):
                self.assertTrue(initialize_first_feishu_admin(db, first_user))
                db.commit()
                marker = db.scalar(select(ConfigOption).where(ConfigOption.category == "system_internal", ConfigOption.value == FIRST_FEISHU_ADMIN_MARKER))
                self.assertIsNotNone(marker)
                self.assertEqual(marker.label, str(first_user.id))
                self.assertFalse(initialize_first_feishu_admin(db, second_user))
                self.assertEqual({first_user.id}, system_admin_user_ids(db))
            db.delete(marker)
            db.commit()
        finally:
            db.close()

    def test_stale_environment_admin_id_does_not_block_first_login(self):
        db = SessionLocal()
        try:
            first_user = db.get(User, 2)
            marker = db.scalar(select(ConfigOption).where(ConfigOption.category == "system_internal", ConfigOption.value == FIRST_FEISHU_ADMIN_MARKER))
            if marker:
                db.delete(marker)
                db.commit()
            with patch.dict(os.environ, {"SYSTEM_ADMIN_USER_IDS": "999999"}), patch("app.main.feishu.mode", "app"):
                self.assertTrue(initialize_first_feishu_admin(db, first_user))
                db.commit()
                self.assertEqual({first_user.id}, system_admin_user_ids(db))
            marker = db.scalar(select(ConfigOption).where(ConfigOption.category == "system_internal", ConfigOption.value == FIRST_FEISHU_ADMIN_MARKER))
            db.delete(marker)
            db.commit()
        finally:
            db.close()

    def test_oauth_user_bootstraps_before_organization_sync(self):
        db = SessionLocal()
        try:
            profile = {"user_id": "ou_oauth_bootstrap", "open_id": "ou_oauth_bootstrap_open", "name": "OAuth 用户", "email": "oauth@example.com"}
            user = ensure_oauth_user(db, profile)
            db.commit()
            self.assertEqual(user.name, "OAuth 用户")
            self.assertIsNone(user.department_id)
            self.assertEqual(user.employment_status, "ACTIVE")
            again = ensure_oauth_user(db, profile)
            self.assertEqual(again.id, user.id)
            self.assertEqual(db.query(User).filter(User.feishu_user_id == "ou_oauth_bootstrap").count(), 1)
        finally:
            db.close()

    def test_oauth_user_does_not_reactivate_inactive_user(self):
        db = SessionLocal()
        try:
            user = User(feishu_user_id="ou_oauth_inactive", open_id="ou_oauth_inactive_open", name="停用用户", employment_status="INACTIVE")
            db.add(user)
            db.commit()
            result = ensure_oauth_user(db, {"user_id": "ou_oauth_inactive", "open_id": "ou_oauth_inactive_open", "name": "停用用户"})
            self.assertEqual(result.employment_status, "INACTIVE")
        finally:
            db.close()

    def test_notification_policies_support_atomic_batch_update(self):
        db = SessionLocal()
        try:
            policies = db.scalars(select(NotificationPolicy).order_by(NotificationPolicy.id)).all()
            payload = NotificationPolicyBatchUpdate(
                items=[
                    NotificationPolicyBatchItem(
                        notification_type=item.notification_type,
                        enabled=item.enabled,
                        send_channel=item.send_channel,
                        remind_days_before=item.remind_days_before,
                    )
                    for item in policies
                ]
            )
            result = update_notification_policies(payload, 1, db)
            self.assertEqual(
                [item.notification_type for item in result.items],
                [item.notification_type for item in policies],
            )
        finally:
            db.close()

    def test_timezone_migration_marker_is_idempotent(self):
        with engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("PRAGMA user_version").scalar(), 1)
        upgrade_schema()
        with engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("PRAGMA user_version").scalar(), 1)

    def test_project_board_options_follow_board_scope(self):
        db = SessionLocal()
        try:
            all_options = list_project_board_options("ALL", 1, db)
            owned_options = list_project_board_options("OWNED", 1, db)
            self.assertTrue(all_options)
            self.assertTrue(
                {item.id for item in owned_options}.issubset(
                    {item.id for item in all_options}
                )
            )
            self.assertTrue(all(hasattr(item, "name") for item in all_options))
            board_rows = list_project_board(
                keyword=None,
                project_id=None,
                project_type=None,
                status=None,
                department_id=None,
                owner_user_id=None,
                customer_id=None,
                data_scope="ALL",
                x_demo_user_id=1,
                db=db,
            )
            self.assertTrue(board_rows)
            required_fields = ("budget_days", "actual_days", "personnel_cost", "actual_expense_cost", "expense_budget", "actual_cost")
            self.assertTrue(all(hasattr(item, field) for item in board_rows for field in required_fields))
        finally:
            db.close()

    def test_department_scope_without_fixed_department_is_valid_for_role_and_user_authorization(self):
        db = SessionLocal()
        role = None
        try:
            role = create_role(
                RoleCreate(code="test_department_scope_role", name="测试部门范围角色"),
                1,
                db,
            )
            update_role_permissions(
                role.id,
                RolePermissionsUpdate(
                    permissions=[RolePermissionInput(menu_code="worklogs", actions=["VIEW"])],
                    scopes=[DataScopeInput(resource="worklogs", scope_type="DEPARTMENT_AND_CHILDREN")],
                ),
                1,
                db,
            )

            role_permissions = get_role_permissions(role.id, 1, db)
            worklog_scope = next(item for item in role_permissions.scopes if item.resource == "worklogs")
            self.assertEqual(worklog_scope.scope_type, "DEPARTMENT_AND_CHILDREN")
            self.assertIsNone(worklog_scope.department_id)

            result = update_user_roles(
                2,
                UserRoleUpdate(
                    role_ids=[role.id],
                    scopes=[DataScopeInput(resource="worklogs", scope_type="DEPARTMENT_AND_CHILDREN")],
                ),
                1,
                db,
            )
            self.assertEqual(result.data_scopes.get("worklogs"), "DEPARTMENT_AND_CHILDREN")
        finally:
            db.query(UserRoleScope).filter(UserRoleScope.user_id == 2).delete(synchronize_session=False)
            db.query(UserRole).filter(UserRole.user_id == 2).delete(synchronize_session=False)
            if role:
                db.query(RolePermission).filter(RolePermission.role_id == role.id).delete(synchronize_session=False)
                db.query(RoleDataScope).filter(RoleDataScope.role_id == role.id).delete(synchronize_session=False)
                db.delete(db.get(Role, role.id))
            db.commit()
            db.close()

    def test_custom_role_permissions_authorization_and_admin_boundary(self):
        db = SessionLocal()
        role = None
        try:
            role = create_role(
                RoleCreate(code="test_rbac_role", name="测试角色", description="回归测试角色"),
                1,
                db,
            )
            saved = update_role_permissions(
                role.id,
                RolePermissionsUpdate(
                    permissions=[RolePermissionInput(menu_code="projects", actions=["VIEW", "EDIT"])],
                    scopes=[DataScopeInput(resource="projects", scope_type="OWNED_PROJECTS")],
                ),
                1,
                db,
            )
            self.assertEqual(saved.permissions[0].actions, ["VIEW", "EDIT"])

            assigned = update_user_roles(2, UserRoleUpdate(role_ids=[role.id]), 1, db)
            self.assertIn("测试角色", assigned.role_names)
            effective = get_effective_permissions(2, 1, db)
            project_menu = next(item for item in effective.menus if item.menu_code == "projects")
            self.assertEqual(project_menu.actions, ["VIEW", "EDIT"])

            with self.assertRaises(HTTPException) as error:
                get_role_permissions(role.id, 2, db)
            self.assertEqual(error.exception.status_code, 403)
        finally:
            db.query(UserRoleScope).filter(UserRoleScope.user_id == 2).delete(synchronize_session=False)
            db.query(UserRole).filter(UserRole.user_id == 2).delete(synchronize_session=False)
            if role:
                db.query(RolePermission).filter(RolePermission.role_id == role.id).delete(synchronize_session=False)
                db.query(RoleDataScope).filter(RoleDataScope.role_id == role.id).delete(synchronize_session=False)
                db.delete(db.get(Role, role.id))
            db.commit()
            db.close()

    def test_rbac_reset_keeps_only_system_admin_for_reconfiguration(self):
        db = SessionLocal()
        extra_role = Role(code="extra_role_for_reset", name="待清理角色", is_builtin=False, is_active=True)
        db.add(extra_role)
        db.flush()
        db.add(UserRole(user_id=2, role_id=extra_role.id, is_active=True))
        db.add(AdminPermission(user_id=2, can_manage_projects=True))
        db.commit()

        reset_rbac_configuration(db, force=True)
        db.commit()

        self.assertIsNone(db.scalar(select(Role).where(Role.code == "extra_role_for_reset")))
        self.assertEqual(db.scalars(select(Role).where(Role.code != "system_admin")).all(), [])
        self.assertIsNotNone(db.scalar(select(Role).where(Role.code == "system_admin")))
        self.assertIsNone(db.scalar(select(AdminPermission).where(AdminPermission.user_id == 2)))
        self.assertEqual(db.scalars(select(UserRole)).all(), [])
        db.close()

    def test_cash_approval_notification_targets_all_cash_approvers(self):
        db = SessionLocal()
        cashier_role = None
        try:
            candidate = db.scalar(select(User).where(User.id != 1).order_by(User.id))
            self.assertIsNotNone(candidate)
            cashier_role = create_role(
                RoleCreate(code="test_cash_approver_role", name="测试出纳角色"),
                1,
                db,
            )
            update_role_permissions(
                cashier_role.id,
                RolePermissionsUpdate(
                    permissions=[RolePermissionInput(menu_code="cash_approval", actions=["VIEW", "APPROVE"])],
                    scopes=[DataScopeInput(resource="cash_approval", scope_type="OWNED_PROJECTS")],
                ),
                1,
                db,
            )
            db.add(UserRole(user_id=candidate.id, role_id=cashier_role.id, is_active=True))
            policy = db.scalar(select(NotificationPolicy).where(NotificationPolicy.notification_type == "PENDING_RECEIPT"))
            policy.send_channel = "mock"
            db.commit()
            sent = send_cash_approval_notifications(
                db,
                "receipt",
                900001,
                "收款单",
                "RC-TEST-900001",
                "出纳通知测试项目",
                12345,
                "杨阳",
            )
            db.commit()
            rows = db.scalars(
                select(SystemNotification).where(
                    SystemNotification.source_type == "receipt",
                    SystemNotification.source_id == 900001,
                )
            ).all()
            self.assertEqual(sent, 2)
            self.assertEqual({row.recipient_user_id for row in rows}, {1, candidate.id})
            self.assertTrue(all(row.notification_type == "PENDING_RECEIPT" and row.status == "SENT" for row in rows))
            self.assertEqual(
                send_cash_approval_notifications(
                    db,
                    "receipt",
                    900001,
                    "收款单",
                    "RC-TEST-900001",
                    "出纳通知测试项目",
                    12345,
                    "杨阳",
                ),
                0,
            )
        finally:
            if candidate:
                db.query(UserRole).filter(UserRole.user_id == candidate.id).delete(synchronize_session=False)
            if cashier_role:
                db.query(RolePermission).filter(RolePermission.role_id == cashier_role.id).delete(synchronize_session=False)
                db.query(RoleDataScope).filter(RoleDataScope.role_id == cashier_role.id).delete(synchronize_session=False)
                db.delete(db.get(Role, cashier_role.id))
            db.commit()
            db.close()

    def test_worklog_approval_notification_links_to_task_detail(self):
        db = SessionLocal()
        worklog_id = None
        try:
            project = db.scalar(
                select(Project).where(Project.status == "ACTIVE", Project.allow_worklog == True).order_by(Project.id)
            )
            approver = db.scalar(select(User).where(User.id != 1, User.employment_status == "ACTIVE").order_by(User.id))
            self.assertIsNotNone(project)
            self.assertIsNotNone(approver)
            project.approver_user_id = approver.id
            db.commit()

            worklog = create_worklog(
                WorklogCreate(
                    project_id=project.id,
                    stage="开发",
                    work_type="PROJECT",
                    work_status="LOCAL",
                    start_date="2030-10-01",
                    end_date="2030-10-01",
                    quantity=1,
                    unit="DAY",
                    description="工时审批深链回归测试",
                    submit=False,
                ),
                x_demo_user_id=1,
                db=db,
            )
            worklog_id = worklog.id
            notify_result = SimpleNamespace(status="SENT", message_id="msg-worklog-detail", error_message=None)
            with patch.dict(os.environ, {"SYSTEM_PUBLIC_URL": "http://example.test:8088"}), patch(
                "app.main.feishu.notify_approval_submitted",
                return_value=notify_result,
            ) as notify_mock:
                task = submit_worklog(worklog.id, x_demo_user_id=1, db=db)

            self.assertEqual(
                notify_mock.call_args.args[8],
                f"http://example.test:8088/?page=approvalDetail&id={task.id}",
            )
        finally:
            if worklog_id:
                task_ids = [item.id for item in db.scalars(select(ApprovalTask).where(ApprovalTask.worklog_id == worklog_id)).all()]
                if task_ids:
                    db.query(Notification).filter(Notification.approval_task_id.in_(task_ids)).delete(synchronize_session=False)
                    db.query(ApprovalTask).filter(ApprovalTask.id.in_(task_ids)).delete(synchronize_session=False)
                db.query(Worklog).filter(Worklog.id == worklog_id).delete(synchronize_session=False)
                db.commit()
            db.close()

    def test_project_page_returns_owned_projects(self):
        db = SessionLocal()
        try:
            result = list_projects_page(
                page=1,
                page_size=20,
                keyword=None,
                project_type=None,
                status=None,
                department_id=None,
                owner_user_id=None,
                customer_id=None,
                data_scope="OWNED",
                x_demo_user_id=1,
                db=db,
            )
        finally:
            db.close()
        self.assertGreaterEqual(result.total, 1)
        self.assertTrue(all(item.owner_user_id == 1 for item in result.items))

    def test_project_crud_round_trip(self):
        db = SessionLocal()
        try:
            department = db.execute(
                select(Department).where(Department.name == "研发中心")
            ).scalar_one()
            payload = ProjectCreate(
                code="PRJ-TEST-CRUD-001",
                name="CRUD 回归测试项目",
                project_type="RND_PROJECT",
                owner_user_id=1,
                department_id=department.id,
                approver_user_id=2,
                leader_user_id=3,
                customer_id=1,
                start_date="2026-08-01",
                planned_end_date="2026-09-30",
                description="用于验证项目新增、编辑和删除接口。",
                budget_days=20,
                budget_cost=120000,
                status="ACTIVE",
                allow_worklog=True,
            )
            created = create_project(payload, x_demo_user_id=1, db=db)
            self.assertEqual(created.name, payload.name)
            self.assertEqual(created.customer_name, "示例客户")
            self.assertEqual(created.budget_days, 20)

            update_payload = ProjectUpdate(
                code=created.code,
                name="CRUD 回归测试项目（已更新）",
                project_type=payload.project_type,
                owner_user_id=1,
                department_id=department.id,
                approver_user_id=2,
                leader_user_id=3,
                customer_id=None,
                start_date="2026-08-01",
                planned_end_date="2026-10-31",
                description="编辑后的项目说明。",
                budget_days=25,
                budget_cost=150000,
                status="ACTIVE",
                allow_worklog=False,
            )
            updated = update_project(created.id, update_payload, x_demo_user_id=1, db=db)
            self.assertEqual(updated.name, update_payload.name)
            self.assertEqual(updated.budget_days, 25)
            self.assertIsNone(updated.customer_name)
            self.assertFalse(updated.allow_worklog)

            page = list_projects_page(
                page=1,
                page_size=20,
                keyword="CRUD 回归测试项目",
                project_type=None,
                status=None,
                department_id=None,
                owner_user_id=None,
                customer_id=None,
                data_scope="ALL",
                x_demo_user_id=1,
                db=db,
            )
            self.assertEqual(page.total, 1)
            self.assertEqual(page.items[0].id, created.id)

            delete_project(created.id, x_demo_user_id=1, db=db)
            page_after_delete = list_projects_page(
                page=1,
                page_size=20,
                keyword="CRUD 回归测试项目",
                project_type=None,
                status=None,
                department_id=None,
                owner_user_id=None,
                customer_id=None,
                data_scope="ALL",
                x_demo_user_id=1,
                db=db,
            )
            self.assertEqual(page_after_delete.total, 0)
        finally:
            db.close()

    def test_contract_receipt_payment_approval_flow(self):
        db = SessionLocal()
        try:
            supplier = create_supplier(
                SupplierCreate(code="SUP-TEST-001", name="测试供应商", status="ACTIVE"),
                x_demo_user_id=1,
                db=db,
            )
            project = list_projects_page(
                page=1,
                page_size=20,
                keyword=None,
                project_type=None,
                status=None,
                department_id=None,
                owner_user_id=None,
                customer_id=None,
                data_scope="OWNED",
                x_demo_user_id=1,
                db=db,
            ).items[0]
            income_contract = create_contract(
                ContractCreate(
                    contract_no="CT-TEST-IN-001",
                    name="收入合同测试",
                    project_id=project.id,
                    contract_type="INCOME",
                    counterparty_type="CUSTOMER",
                    counterparty_id=1,
                    amount=100000,
                    status="ACTIVE",
                ),
                x_demo_user_id=1,
                db=db,
            )
            stage = create_contract_stage(
                income_contract.id,
                ContractStageCreate(name="首付款", amount=100000, planned_date="2026-08-01"),
                x_demo_user_id=1,
                db=db,
            )
            receipt = create_receipt(
                ReceiptCreate(
                    contract_id=income_contract.id,
                    stage_id=stage.id,
                    amount=60000,
                    receipt_date="2026-08-15",
                    payer_name="示例客户",
                ),
                x_demo_user_id=1,
                db=db,
            )
            self.assertEqual(receipt.status, "PENDING")
            approved_receipt = approve_receipt(receipt.id, x_demo_user_id=1, db=db)
            self.assertEqual(approved_receipt.status, "APPROVED")
            receipt_ledger_count = db.scalar(
                select(func.count())
                .select_from(ProjectLedgerEntry)
                .where(
                    ProjectLedgerEntry.source_type == "RECEIPT",
                    ProjectLedgerEntry.source_id == receipt.id,
                    ProjectLedgerEntry.entry_type == "RECEIPT",
                )
            )
            self.assertEqual(receipt_ledger_count, 1)

            expense_contract = create_contract(
                ContractCreate(
                    contract_no="CT-TEST-EX-001",
                    name="支出合同测试",
                    project_id=project.id,
                    contract_type="EXPENSE",
                    counterparty_type="SUPPLIER",
                    counterparty_id=supplier.id,
                    amount=50000,
                    status="ACTIVE",
                ),
                x_demo_user_id=1,
                db=db,
            )
            expense_stage = create_contract_stage(
                expense_contract.id,
                ContractStageCreate(name="到货款", amount=50000, planned_date="2026-08-20"),
                x_demo_user_id=1,
                db=db,
            )
            payment = create_payment(
                PaymentCreate(
                    contract_id=expense_contract.id,
                    stage_id=expense_stage.id,
                    amount=50000,
                    payment_date="2026-08-20",
                    payee_name="测试供应商",
                ),
                x_demo_user_id=1,
                db=db,
            )
            self.assertEqual(payment.status, "DRAFT")
            # 一级费用复核：单据只挂一个费用复核节点，任一人通过即完成。
            self.grant_cost_review_position(db, 3)
            submitted_payment = submit_payment(payment.id, x_demo_user_id=1, db=db)
            self.assertEqual(submitted_payment.status, "PENDING_REVIEW")
            self.assertIsNone(submitted_payment.current_workflow_instance_id)
            self.assertEqual([node.node_name for node in submitted_payment.approval_path], ["费用复核"])
            self.assertEqual(submitted_payment.approval_path[0].status, "CURRENT")
            self.assertEqual(submitted_payment.approval_path[0].approval_mode, "ANY")
            self.assertEqual(int(db.scalar(select(func.count()).select_from(ProjectLedgerEntry).where(
                ProjectLedgerEntry.source_type == "PAYMENT",
                ProjectLedgerEntry.source_id == payment.id,
                ProjectLedgerEntry.entry_type == "PAYMENT",
            )) or 0), 0)
            approved_payment = approve_payment(payment.id, x_demo_user_id=3, db=db)
            self.assertEqual(approved_payment.status, "APPROVED")
            payment_ledger_count = db.scalar(
                select(func.count())
                .select_from(ProjectLedgerEntry)
                .where(
                    ProjectLedgerEntry.source_type == "PAYMENT",
                    ProjectLedgerEntry.source_id == payment.id,
                    ProjectLedgerEntry.entry_type == "PAYMENT",
                )
            )
            self.assertEqual(payment_ledger_count, 1)

            finance = project_finance_summary(db, project)
            self.assertEqual(finance["contract_income"], 100000)
            self.assertEqual(finance["contract_expense"], 50000)
            self.assertEqual(finance["received"], 60000)
            self.assertEqual(finance["paid"], 50000)
            self.assertEqual(finance["receivable"], 40000)
            self.assertEqual(finance["payable"], 0)
            self.assertEqual(finance["gross_profit"], 10000)

            project_record = db.get(Project, project.id)
            project_record.budget_cost = 100000
            db.flush()
            budget_view = project_view(db, project_record)
            self.assertEqual(budget_view.actual_contract_cost, 50000)
            self.assertEqual(
                budget_view.remaining_cost,
                round(100000 - budget_view.personnel_cost - 50000, 2),
            )

            board = list_project_board(
                keyword=None,
                project_id=None,
                project_type=None,
                status=None,
                department_id=None,
                owner_user_id=None,
                customer_id=None,
                data_scope="ALL",
                x_demo_user_id=1,
                db=db,
            )
            row = next(item for item in board if item.id == project.id)
            self.assertEqual(row.receivable, 40000)
            self.assertEqual(row.warning, "应收未收")
        finally:
            db.close()

    def test_receivable_excludes_future_income_stages(self):
        db = SessionLocal()
        try:
            project = db.scalars(
                select(Project)
                .where(Project.owner_user_id == 1, Project.status != "DELETED")
                .order_by(Project.id)
            ).first()
            self.assertIsNotNone(project)
            income_contract = create_contract(
                ContractCreate(
                    contract_no="CT-TEST-IN-FUTURE-001",
                    name="未来收入阶段测试",
                    project_id=project.id,
                    contract_type="INCOME",
                    counterparty_type="CUSTOMER",
                    counterparty_id=1,
                    amount=50000,
                    status="ACTIVE",
                ),
                x_demo_user_id=1,
                db=db,
            )
            create_contract_stage(
                income_contract.id,
                ContractStageCreate(
                    name="未来阶段",
                    amount=50000,
                    planned_date="2026-09-30",
                ),
                x_demo_user_id=1,
                db=db,
            )

            before_due = project_finance_summary(db, project, as_of=date(2026, 8, 31))
            after_due = project_finance_summary(db, project, as_of=date(2026, 10, 1))
            self.assertEqual(after_due["receivable"] - before_due["receivable"], 50000)

            expense_contract = create_contract(
                ContractCreate(
                    contract_no="CT-TEST-EX-FUTURE-001",
                    name="未来支出阶段测试",
                    project_id=project.id,
                    contract_type="EXPENSE",
                    counterparty_type="SUPPLIER",
                    counterparty_id=1,
                    amount=40000,
                    status="ACTIVE",
                ),
                x_demo_user_id=1,
                db=db,
            )
            create_contract_stage(
                expense_contract.id,
                ContractStageCreate(
                    name="未来付款阶段",
                    amount=40000,
                    planned_date="2026-09-30",
                ),
                x_demo_user_id=1,
                db=db,
            )
            before_expense_due = project_finance_summary(db, project, as_of=date(2026, 8, 31))
            after_expense_due = project_finance_summary(db, project, as_of=date(2026, 10, 1))
            self.assertEqual(after_expense_due["payable"] - before_expense_due["payable"], 40000)
        finally:
            db.close()

    def test_workbench_overview_returns_owned_projects_and_reminders(self):
        db = SessionLocal()
        try:
            overview = workbench_overview(x_demo_user_id=1, db=db)
            self.assertGreaterEqual(overview.metrics["project_count"], 1)
            self.assertTrue(all(row.owner_name == "杨阳" for row in overview.owned_projects))
            reminder = next(
                (item for item in overview.reminders if "RECEIVABLE" in item.kind),
                None,
            )
            self.assertIsNotNone(reminder)
            self.assertGreater(reminder.remaining, 0)
        finally:
            db.close()

    def test_workbench_reminders_are_limited_to_thirty_days(self):
        db = SessionLocal()
        try:
            project = db.scalars(
                select(Project)
                .where(Project.owner_user_id == 1, Project.status != "DELETED")
                .order_by(Project.id)
            ).first()
            self.assertIsNotNone(project)
            income_contract = create_contract(
                ContractCreate(
                    contract_no="CT-TEST-REMINDER-WINDOW-001",
                    name="提醒窗口测试合同",
                    project_id=project.id,
                    contract_type="INCOME",
                    counterparty_type="CUSTOMER",
                    counterparty_id=1,
                    amount=70000,
                    status="ACTIVE",
                ),
                x_demo_user_id=1,
                db=db,
            )
            create_contract_stage(
                income_contract.id,
                ContractStageCreate(
                    name="窗口内阶段",
                    amount=30000,
                    planned_date=date.today() + timedelta(days=30),
                ),
                x_demo_user_id=1,
                db=db,
            )
            create_contract_stage(
                income_contract.id,
                ContractStageCreate(
                    name="窗口外阶段",
                    amount=40000,
                    planned_date=date.today() + timedelta(days=31),
                ),
                x_demo_user_id=1,
                db=db,
            )

            overview = workbench_overview(x_demo_user_id=1, db=db)
            reminder_names = {item.stage_name for item in overview.reminders}
            self.assertIn("窗口内阶段", reminder_names)
            self.assertNotIn("窗口外阶段", reminder_names)
        finally:
            db.close()

    def test_reminder_scan_is_idempotent(self):
        first = run_stage_reminder_scan_once()
        second = run_stage_reminder_scan_once()
        self.assertGreaterEqual(first["scanned"], 1)
        self.assertEqual(second["sent"], 0)

    def test_contract_requires_stage_sum_before_activation(self):
        db = SessionLocal()
        try:
            project = list_projects_page(
                page=1,
                page_size=20,
                keyword=None,
                project_type=None,
                status=None,
                department_id=None,
                owner_user_id=None,
                customer_id=None,
                data_scope="OWNED",
                x_demo_user_id=1,
                db=db,
            ).items[0]
            contract = create_contract(
                ContractCreate(
                    contract_no="CT-TEST-ACTIVATE-001",
                    name="激活校验合同",
                    project_id=project.id,
                    contract_type="INCOME",
                    counterparty_type="CUSTOMER",
                    counterparty_id=1,
                    amount=1000,
                    status="DRAFT",
                ),
                x_demo_user_id=1,
                db=db,
            )
            create_contract_stage(
                contract.id,
                ContractStageCreate(name="一期", amount=600),
                x_demo_user_id=1,
                db=db,
            )
            with self.assertRaises(Exception):
                activate_contract(contract.id, x_demo_user_id=1, db=db)
            create_contract_stage(
                contract.id,
                ContractStageCreate(name="二期", amount=400),
                x_demo_user_id=1,
                db=db,
            )
            activated = activate_contract(contract.id, x_demo_user_id=1, db=db)
            self.assertEqual(activated.status, "ACTIVE")
        finally:
            db.close()

    def test_project_expense_workflow_confirms_cost_before_cash(self):
        db = SessionLocal()
        try:
            project = db.scalar(select(Project).where(Project.status != "DELETED").order_by(Project.id))
            project.expense_budget = 50_000
            for position in db.scalars(select(ApprovalPosition)).all():
                db.query(ApprovalPositionMember).filter(ApprovalPositionMember.position_id == position.id).delete()
                db.add(ApprovalPositionMember(position_id=position.id, user_id=3))
            db.commit()
            created = create_project_expense(
                ProjectExpenseCreate(
                    expense_type="TRAVEL",
                    project_id=project.id,
                    occurred_on=date.today(),
                    amount=3600,
                    cost_amount=3600,
                    requires_payment=True,
                    payee_name="测试收款人",
                    payee_bank_name="测试银行",
                    payee_bank_account="6222000011112222",
                    purpose="测试差旅费用完整审批链路",
                    detail={"destination": "成都"},
                ),
                x_demo_user_id=1,
                db=db,
            )
            db.add(ProjectExpenseAttachment(expense_id=created.id, file_name="receipt.pdf", storage_name=f"test-receipt-{created.id}.pdf", mime_type="application/pdf", file_size=16, uploaded_by=1))
            db.commit()
            with patch.dict(os.environ, {"SYSTEM_ADMIN_USER_IDS": "1,2,3"}):
                notify_result = SimpleNamespace(status="SENT", message_id="msg-expense-flow", error_message=None)
                with patch("app.main.feishu.notify_cash_approval_submitted", return_value=notify_result) as notify_mock:
                    submit_project_expense(created.id, x_demo_user_id=1, db=db)
                self.assertTrue(any(f"page=expenseDetail&id={created.id}&task=" in str(call) for call in notify_mock.call_args_list))
                approval_notification = db.scalar(select(SystemNotification).where(
                    SystemNotification.notification_type == "EXPENSE_APPROVAL",
                    SystemNotification.source_type == "project_expense",
                    SystemNotification.source_id == created.id,
                ))
                self.assertIsNotNone(approval_notification)
                self.assertEqual(approval_notification.status, "SENT")
                expense_row = db.get(ProjectExpense, created.id)
                while True:
                    task = db.scalar(select(WorkflowTask).where(WorkflowTask.workflow_instance_id == expense_row.current_workflow_instance_id, WorkflowTask.status == "PENDING").order_by(WorkflowTask.node_sequence))
                    self.assertIsNotNone(task)
                    if task.node_name == "出纳支付":
                        break
                    with patch("app.main.feishu.notify_cash_approval_submitted", return_value=notify_result), patch("app.main.feishu.notify_settlement_result", return_value=notify_result):
                        approve_workflow_task(task.id, WorkflowTaskAction(comment="同意"), x_demo_user_id=task.assignee_user_id, db=db)
                before_payment = project_view(db, project)
                self.assertEqual(before_payment.actual_expense_cost, 3600)
                self.assertEqual(
                    before_payment.expense_budget_remaining,
                    50_000 - before_payment.actual_contract_cost - before_payment.actual_expense_cost,
                )
                self.assertEqual(int(db.scalar(select(func.count()).select_from(ProjectExpensePayment)) or 0), 0)
                payment_notification = db.scalar(select(SystemNotification).where(
                    SystemNotification.notification_type == "EXPENSE_PAYMENT",
                    SystemNotification.source_type == "project_expense",
                    SystemNotification.source_id == created.id,
                    SystemNotification.recipient_user_id == task.assignee_user_id,
                ))
                self.assertIsNotNone(payment_notification)
                self.assertEqual(payment_notification.status, "SENT")
                payment_notification.status = "FAILED"
                payment_notification.error_message = "TEST_EXPENSE_PAYMENT_RETRY"
                db.commit()
                with patch("app.main.feishu.notify_cash_approval_submitted", return_value=notify_result):
                    retried_payment_notification = retry_integration_notification(payment_notification.id, record_kind="system", x_demo_user_id=1, db=db)
                self.assertEqual(retried_payment_notification.status, "SENT")
                self.assertEqual(retried_payment_notification.retry_count, 1)
                approval_result_notification = db.scalar(select(SystemNotification).where(
                    SystemNotification.notification_type == "EXPENSE_RESULT",
                    SystemNotification.source_type == "project_expense",
                    SystemNotification.source_id == created.id,
                ).order_by(SystemNotification.id.desc()))
                self.assertIsNotNone(approval_result_notification)
                self.assertEqual(approval_result_notification.status, "SENT")
                with patch("app.main.feishu.notify_settlement_result", return_value=notify_result):
                    paid = confirm_expense_payment(task.id, ProjectExpensePaymentAction(payment_date=date.today(), amount=3600, company_account="公司基本户", comment="已支付"), x_demo_user_id=task.assignee_user_id, db=db)
            self.assertEqual(paid.status, "PAID")
            self.assertGreaterEqual(int(db.scalar(select(func.count()).select_from(SystemNotification).where(
                SystemNotification.notification_type == "EXPENSE_RESULT",
                SystemNotification.source_type == "project_expense",
                SystemNotification.source_id == created.id,
            )) or 0), 2)
            self.assertEqual(int(db.scalar(select(func.count()).select_from(ProjectLedgerEntry).where(ProjectLedgerEntry.entry_type == "PROJECT_EXPENSE_COST", ProjectLedgerEntry.source_id == created.id)) or 0), 1)
            self.assertEqual(int(db.scalar(select(func.count()).select_from(ProjectLedgerEntry).where(ProjectLedgerEntry.entry_type == "EXPENSE_PAYMENT")) or 0), 1)
            self.assertGreaterEqual(project_finance_summary(db, project)["paid"], 3600)
        finally:
            db.close()

    def test_expense_approver_without_approve_permission_can_process_task(self):
        db = SessionLocal()
        try:
            suffix = uuid.uuid4().hex[:8]
            approver = User(
                feishu_user_id=f"auto-approver-{suffix}",
                open_id=f"ou_auto_approver_{suffix}",
                name="自动授权审批人",
                employment_status="ACTIVE",
            )
            db.add(approver)
            db.flush()
            department = db.scalar(select(Department).order_by(Department.id))
            project = create_project(
                ProjectCreate(
                    code=f"PRJ-AUTO-{suffix}",
                    name=f"费用自动授权项目-{suffix}",
                    project_type="RND_PROJECT",
                    owner_user_id=1,
                    department_id=department.id,
                    approver_user_id=approver.id,
                    leader_user_id=1,
                    start_date="2026-09-01",
                    planned_end_date="2026-12-31",
                    description="验证被指派审批人无需审批菜单权限。",
                    budget_days=20,
                    budget_cost=100000,
                    status="ACTIVE",
                    allow_worklog=True,
                ),
                x_demo_user_id=1,
                db=db,
            )
            for position in db.scalars(select(ApprovalPosition)).all():
                db.query(ApprovalPositionMember).filter(ApprovalPositionMember.position_id == position.id).delete()
                db.add(ApprovalPositionMember(position_id=position.id, user_id=1))
            db.commit()
            expense = create_project_expense(
                ProjectExpenseCreate(
                    expense_type="OTHER",
                    project_id=project.id,
                    occurred_on=date.today(),
                    amount=800,
                    cost_amount=800,
                    requires_payment=True,
                    payee_name="自动授权收款人",
                    payee_bank_name="测试银行",
                    payee_bank_account="6222000099998888",
                    purpose="测试被指派审批人无需审批权限",
                ),
                x_demo_user_id=1,
                db=db,
            )
            db.add(ProjectExpenseAttachment(
                expense_id=expense.id,
                file_name="auto-receipt.pdf",
                storage_name=f"auto-receipt-{expense.id}.pdf",
                mime_type="application/pdf",
                file_size=16,
                uploaded_by=1,
            ))
            db.commit()
            notify_result = SimpleNamespace(status="SENT", message_id="msg-expense-auto-approver", error_message=None)
            with patch("app.main.feishu.notify_cash_approval_submitted", return_value=notify_result):
                submit_project_expense(expense.id, x_demo_user_id=1, db=db)
            task = db.scalar(select(WorkflowTask).where(
                WorkflowTask.assignee_user_id == approver.id,
                WorkflowTask.status == "PENDING",
            ))
            self.assertIsNotNone(task)
            pending = list_workflow_tasks(page=1, page_size=20, status="PENDING", x_demo_user_id=approver.id, db=db)
            self.assertEqual(pending.total, 1)
            self.assertEqual(pending.items[0].assignee_user_id, approver.id)
            with patch("app.main.feishu.notify_cash_approval_submitted", return_value=notify_result), patch("app.main.feishu.notify_settlement_result", return_value=notify_result):
                approved = approve_workflow_task(task.id, WorkflowTaskAction(comment="同意"), x_demo_user_id=approver.id, db=db)
            self.assertEqual(approved.status, "PENDING_APPROVAL")
            view = project_expense_view(db, db.get(ProjectExpense, expense.id), viewer_id=approver.id)
            labels = [entry.action for entry in view.approval_logs]
            self.assertEqual(labels[:2], ["提交审批", "节点通过"])
        finally:
            db.close()

    def test_payment_rejection_result_retry_and_resubmission_keeps_single_path(self):
        db = SessionLocal()
        try:
            _project, contract, stage, payment = self.create_payment_fixture(db, "RESUBMIT")
            self.grant_cost_review_position(db, 3)
            submit_payment(payment.id, x_demo_user_id=1, db=db)
            submitted_row = db.get(Payment, payment.id)
            self.assertEqual(submitted_row.status, "PENDING_REVIEW")
            self.assertIsNone(submitted_row.current_workflow_instance_id)
            first_version = submitted_row.version
            reviewer = db.get(User, 3)

            rejected = reject_payment(payment.id, CashRejectAction(reason="付款资料不完整"), x_demo_user_id=3, db=db)
            self.assertEqual(rejected.status, "REJECTED")
            self.assertTrue(any(event.event.startswith("审批驳回") for event in rejected.approval_timeline))

            result_notification = db.scalar(select(SystemNotification).where(
                SystemNotification.notification_type == "COST_REVIEW_RESULT",
                SystemNotification.source_id == payment.id,
            ))
            self.assertIsNotNone(result_notification)
            result_notification.status = "FAILED"
            result_notification.error_message = "TEST_RETRY"
            db.commit()
            before_count = int(db.scalar(select(func.count()).select_from(SystemNotification).where(
                SystemNotification.notification_type == "COST_REVIEW_RESULT",
                SystemNotification.source_id == payment.id,
            )) or 0)
            retry_result = SimpleNamespace(status="SENT", message_id="msg-result-retry", error_message=None)
            with patch("app.main.feishu.notify_settlement_result", return_value=retry_result) as result_mock:
                retried = retry_integration_notification(result_notification.id, record_kind="system", x_demo_user_id=1, db=db)
            self.assertEqual(retried.status, "SENT")
            self.assertEqual(retried.retry_count, 1)
            self.assertEqual(result_mock.call_args.kwargs["approver_name"], reviewer.name)
            self.assertEqual(int(db.scalar(select(func.count()).select_from(SystemNotification).where(
                SystemNotification.notification_type == "COST_REVIEW_RESULT",
                SystemNotification.source_id == payment.id,
            )) or 0), before_count)

            updated = update_payment(
                payment.id,
                PaymentUpdate(
                    contract_id=contract.id,
                    stage_id=stage.id,
                    amount=550,
                    payment_date="2026-09-08",
                    payee_name="付款流程供应商-RESUBMIT",
                    payee_bank_name="测试银行",
                    payee_bank_account="6222000012345678",
                ),
                x_demo_user_id=1,
                db=db,
            )
            self.assertEqual(updated.status, "REJECTED")
            resubmitted = submit_payment(payment.id, x_demo_user_id=1, db=db)
            self.assertEqual(resubmitted.status, "PENDING_REVIEW")
            self.assertIsNone(resubmitted.current_workflow_instance_id)
            self.assertEqual(resubmitted.version, first_version + 1)
        finally:
            db.close()

    def test_payment_review_blocks_unassigned_user_and_notifies_deep_link(self):
        db = SessionLocal()
        try:
            _project, _contract, _stage, payment = self.create_payment_fixture(db, "FLOW")
            self.grant_cost_review_position(db, 2)
            notify_result = SimpleNamespace(status="SENT", message_id="msg-payment-flow", error_message=None)
            with patch("app.main.feishu.notify_cash_approval_submitted", return_value=notify_result) as notify_mock:
                submitted = submit_payment(payment.id, x_demo_user_id=1, db=db)
            self.assertEqual(submitted.status, "PENDING_REVIEW")
            self.assertTrue(any(f"page=paymentDetail&id={payment.id}" in str(call) for call in notify_mock.call_args_list))

            pending_notification = db.scalar(select(SystemNotification).where(
                SystemNotification.notification_type == "PENDING_PAYMENT_REVIEW",
                SystemNotification.source_id == payment.id,
                SystemNotification.recipient_user_id == 2,
            ))
            self.assertIsNotNone(pending_notification)
            pending_notification.status = "FAILED"
            pending_notification.error_message = "TEST_RETRY"
            db.commit()
            before_notification_count = int(db.scalar(select(func.count()).select_from(SystemNotification).where(
                SystemNotification.notification_type == "PENDING_PAYMENT_REVIEW",
                SystemNotification.source_id == payment.id,
            )) or 0)
            with patch("app.main.feishu.notify_cash_approval_submitted", return_value=notify_result):
                retried = retry_integration_notification(pending_notification.id, record_kind="system", x_demo_user_id=1, db=db)
            self.assertEqual(retried.status, "SENT")
            self.assertEqual(retried.retry_count, 1)
            self.assertEqual(int(db.scalar(select(func.count()).select_from(SystemNotification).where(
                SystemNotification.notification_type == "PENDING_PAYMENT_REVIEW",
                SystemNotification.source_id == payment.id,
            )) or 0), before_notification_count)

            # 3 号用户既不是费用复核岗位成员也不是系统管理员，必须被拒绝。
            with self.assertRaises(HTTPException) as denied:
                approve_payment(payment.id, x_demo_user_id=3, db=db)
            self.assertEqual(denied.exception.status_code, 403)
            self.assertEqual(db.get(Payment, payment.id).status, "PENDING_REVIEW")

            approved = approve_payment(payment.id, x_demo_user_id=2, db=db)
            self.assertEqual(approved.status, "APPROVED")
            self.assertEqual(approved.approved_by, 2)
            ledger_filter = (
                ProjectLedgerEntry.entry_type == "PAYMENT",
                ProjectLedgerEntry.source_type == "PAYMENT",
                ProjectLedgerEntry.source_id == payment.id,
            )
            self.assertEqual(int(db.scalar(select(func.count()).select_from(ProjectLedgerEntry).where(*ledger_filter)) or 0), 1)
            # 复核通过后再次复核应被拒绝，且不会重复记账。
            with self.assertRaises(HTTPException):
                approve_payment(payment.id, x_demo_user_id=2, db=db)
            self.assertEqual(int(db.scalar(select(func.count()).select_from(ProjectLedgerEntry).where(*ledger_filter)) or 0), 1)
            self.assertEqual(list_payment_attachments(payment.id, x_demo_user_id=1, db=db), [])
        finally:
            db.close()

    def test_payment_submission_reserves_stage_amount_and_legacy_pending_still_works(self):
        db = SessionLocal()
        try:
            _project, contract, stage, first = self.create_payment_fixture(db, "RESERVE", stage_amount=1000, payment_amount=600)
            self.grant_cost_review_position(db, 3)
            submit_payment(first.id, x_demo_user_id=1, db=db)
            second = create_payment(
                PaymentCreate(
                    contract_id=contract.id,
                    stage_id=stage.id,
                    amount=500,
                    payment_date="2026-09-09",
                    payee_name="付款流程供应商-RESERVE",
                    payee_bank_name="测试银行",
                    payee_bank_account="6222000099999999",
                ),
                x_demo_user_id=1,
                db=db,
            )
            with self.assertRaises(HTTPException) as exceeded:
                submit_payment(second.id, x_demo_user_id=1, db=db)
            self.assertEqual(exceeded.exception.detail, "STAGE_REMAINING_INSUFFICIENT")
            self.assertEqual(db.get(Payment, second.id).status, "DRAFT")

            # 历史在途单据（迁移前为 PENDING / PENDING_APPROVAL）跑完迁移后仍可被一级复核处理。
            _project, _legacy_contract, _legacy_stage, legacy = self.create_payment_fixture(db, "LEGACY", stage_amount=700, payment_amount=700)
            legacy_row = db.get(Payment, legacy.id)
            legacy_row.status = "PENDING_APPROVAL"
            legacy_row.submitted_by = 1
            legacy_row.submitted_at = legacy_row.created_at
            db.commit()
            upgrade_schema()
            db.expire_all()
            migrated = db.get(Payment, legacy.id)
            self.assertEqual(migrated.status, "PENDING_REVIEW")
            self.assertIsNone(migrated.current_workflow_instance_id)
            approved = approve_payment(legacy.id, x_demo_user_id=3, db=db)
            self.assertEqual(approved.status, "APPROVED")
            self.assertIsNone(approved.current_workflow_instance_id)
            self.assertEqual(int(db.scalar(select(func.count()).select_from(ProjectLedgerEntry).where(
                ProjectLedgerEntry.entry_type == "PAYMENT",
                ProjectLedgerEntry.source_type == "PAYMENT",
                ProjectLedgerEntry.source_id == legacy.id,
            )) or 0), 1)
        finally:
            db.close()

    def test_payment_defaults_payee_from_supplier_bank_account(self):
        db = SessionLocal()
        try:
            supplier = create_supplier(
                SupplierCreate(
                    code="SUP-PAY-DEFAULT",
                    name="默认收款方供应商",
                    status="ACTIVE",
                    bank_name="招商银行",
                    bank_branch="深圳分行",
                    bank_account="6225888888888888",
                ),
                x_demo_user_id=1,
                db=db,
            )
            project = db.scalar(select(Project).where(Project.status != "DELETED").order_by(Project.id))
            contract = create_contract(
                ContractCreate(
                    contract_no="CT-PAY-DEFAULT",
                    name="默认收款方合同",
                    project_id=project.id,
                    contract_type="EXPENSE",
                    counterparty_type="SUPPLIER",
                    counterparty_id=supplier.id,
                    amount=1000,
                    status="ACTIVE",
                ),
                x_demo_user_id=1,
                db=db,
            )
            stage = create_contract_stage(
                contract.id,
                ContractStageCreate(name="默认阶段", amount=1000, planned_date="2030-09-30"),
                x_demo_user_id=1,
                db=db,
            )
            payment = create_payment(
                PaymentCreate(contract_id=contract.id, stage_id=stage.id, amount=300, payment_date="2026-09-10"),
                x_demo_user_id=1,
                db=db,
            )
            self.assertEqual(payment.payee_name, supplier.name)
            self.assertEqual(payment.payee_bank_name, supplier.bank_branch or supplier.bank_name)
            self.assertEqual(payment.payee_bank_account, supplier.bank_account)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
