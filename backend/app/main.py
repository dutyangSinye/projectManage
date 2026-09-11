"""综合项目管理系统 API 入口。"""

from datetime import date, datetime, timedelta
from contextvars import ContextVar
import csv
from html import escape as html_escape
import io
import json
import logging
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
import tempfile
import time
from collections import defaultdict
from urllib.parse import quote
import xml.etree.ElementTree as ET
import zipfile

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.background import BackgroundTask
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import and_, func, inspect, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db.models import AdminPermission, ApprovalPosition, ApprovalPositionMember, AuditLog, ApprovalTask, BudgetItemTemplate, CashDocumentAttachment, ConfigOption, Contract, ContractAttachment, ContractStage, Customer, Department, Menu, Notification, NotificationPolicy, OrgSyncLog, Payment, PermissionAudit, Project, ProjectBudgetItem, ProjectExpense, ProjectExpenseAttachment, ProjectExpensePayment, ProjectLedgerEntry, Receipt, ReminderEvent, Role, RoleDataScope, RolePermission, Supplier, SystemNotification, Timesheet, User, UserRole, UserRoleScope, WorkflowActionLog, WorkflowDefinition, WorkflowInstance, WorkflowNode, WorkflowTask, WorkflowVersion, Worklog
from .db.session import Base, SessionLocal, engine, get_db
from .time_utils import now_local, today_local
from .schemas import (
    ApprovalAction,
    ApprovalPositionUpdate,
    ApprovalPositionView,
    AdminWorklogList,
    AdminWorklogView,
    DataScopeInput,
    EffectivePermissionMenu,
    EffectivePermissionView,
    ApprovalTimelineEvent,
    ApprovalTaskView,
    AuditEntryView,
    AuthCodeRequest,
    BudgetItemTemplateCreate,
    BudgetItemTemplateUpdate,
    BudgetItemTemplateView,
    ConfigOptionCatalog,
    ConfigOptionCreate,
    ConfigOptionUpdate,
    ConfigOptionView,
    CashRejectAction,
    CashDocumentAttachmentView,
    ContractCreate,
    ContractAttachmentView,
    ContractStageCreate,
    ContractStageUpdate,
    ContractStageView,
    ContractUpdate,
    ContractView,
    CustomerCreate,
    CustomerUpdate,
    CustomerView,
    NotificationView,
    IntegrationNotificationList,
    IntegrationNotificationView,
    MenuView,
    OrgSyncLogList,
    OrgSyncLogView,
    NotificationPolicyUpdate,
    NotificationPolicyBatchUpdate,
    NotificationPolicyView,
    NotificationPolicyList,
    ProjectBoardAgingBucket,
    ProjectBoardAgingItem,
    ProjectBoardInsights,
    OrgDepartmentView,
    OrgSyncView,
    PaymentCreate,
    PaymentUpdate,
    PaymentView,
    PersonnelCostUpdate,
    PersonnelCostList,
    PersonnelCostView,
    ProjectBoardOption,
    ProjectBoardRow,
    ProjectBudgetItemUpdate,
    ProjectBudgetItemView,
    ProjectAnalysisCloseoutView,
    ProjectAnalysisContractView,
    ProjectAnalysisCostTrendView,
    ProjectAnalysisCostView,
    ProjectAnalysisSettlementView,
    ProjectAnalysisStageView,
    ProjectAnalysisView,
    ProjectAnalysisWarningView,
    ProjectFinanceView,
    OrgUserView,
    ProjectCreate,
    ProjectExpenseAttachmentView,
    ProjectExpenseCreate,
    ProjectExpenseList,
    ProjectExpensePaymentAction,
    ProjectExpenseUpdate,
    ProjectExpenseView,
    ProjectList,
    ProjectApproverUpdate,
    ProjectUpdate,
    ProjectView,
    RoleCreate,
    RoleList,
    RolePermissionInput,
    RolePermissionsUpdate,
    RolePermissionsView,
    RoleUpdate,
    RoleView,
    ReportView,
    ReceiptCreate,
    ReceiptUpdate,
    ReceiptView,
    RejectionAction,
    SupplierCreate,
    SupplierUpdate,
    SupplierView,
    TimesheetView,
    UserRoleList,
    UserRoleUpdate,
    UserRoleView,
    UserView,
    WorkflowDefinitionView,
    WorkflowPathNodeView,
    WorkflowTaskAction,
    WorkflowTaskList,
    WorkflowTaskRejectAction,
    WorkflowTaskView,
    WorkflowActionLogView,
    WorkbenchOverview,
    WorkbenchProjectRow,
    WorkbenchReminder,
    WorklogCreate,
    WorklogList,
    WorklogUpdate,
    WorklogView,
)
from .services.feishu import FeishuAdapter


API_VERSION = "3.0.60"
TIMEZONE_DATA_MIGRATION_VERSION = 1
RBAC_RESET_MARKER = "RBAC_ROLE_RESET_V3_0_24"
FIRST_FEISHU_ADMIN_MARKER = "FIRST_FEISHU_ADMIN_USER_ID"
RBAC_ACTIONS = ("VIEW", "CREATE", "EDIT", "DELETE", "APPROVE", "EXPORT", "SYNC", "CONFIGURE", "PUBLISH", "DISABLE", "REVERSE")
RBAC_SCOPE_RANK = {"SELF": 1, "OWNED_PROJECTS": 2, "DEPARTMENT_AND_CHILDREN": 3, "ALL": 4}
RBAC_SCOPE_LABELS = {
    "SELF": "仅本人",
    "OWNED_PROJECTS": "负责项目",
    "DEPARTMENT_AND_CHILDREN": "本部门及下级",
    "ALL": "全部数据",
}
RBAC_MENU_SEED = [
    ("workbench", None, "工作台", "workbench", 10, ["VIEW"]),
    ("worklogs", None, "工时管理", "worklogs", 20, ["VIEW", "CREATE", "EDIT", "DELETE", "EXPORT"]),
    ("approvals", "worklogs", "工时审批", "approvals", 21, ["VIEW", "APPROVE"]),
    ("reports", "worklogs", "工时看板", "reports", 22, ["VIEW", "EXPORT"]),
    ("projects", None, "项目管理", "projects", 30, ["VIEW", "CREATE", "EDIT", "DELETE"]),
    ("contracts", None, "项目合同", "projectContracts", 31, ["VIEW", "CREATE", "EDIT", "DELETE"]),
    ("receipts", None, "合同收款", "projectReceipts", 32, ["VIEW", "CREATE", "EDIT", "DELETE", "APPROVE", "EXPORT"]),
    ("payments", None, "合同付款", "projectPayments", 33, ["VIEW", "CREATE", "EDIT", "DELETE", "APPROVE", "EXPORT"]),
    ("project_expenses", None, "项目费用", "projectExpenses", 34, ["VIEW", "CREATE", "EDIT", "DELETE", "APPROVE", "EXPORT", "REVERSE"]),
    ("project_board", None, "项目看板", "projectBoard", 35, ["VIEW", "EXPORT"]),
    ("counterparties", None, "客户与供应商", "customers", 36, ["VIEW", "CREATE", "EDIT", "DELETE"]),
    ("cash_approval", None, "出纳审批", "projectReceipts", 37, ["VIEW", "APPROVE"]),
    ("personnel_costs", None, "人员成本", "personnelCosts", 40, ["VIEW", "EDIT", "EXPORT"]),
    ("budget_templates", None, "预算项模板", "budgetTemplates", 45, ["VIEW", "CREATE", "EDIT", "DELETE"]),
    ("integrations", None, "集成与通知", "integrations", 50, ["VIEW", "CONFIGURE", "SYNC", "EXPORT"]),
    ("admins", None, "管理员管理", "adminPermissions", 51, ["VIEW", "CONFIGURE"]),
    ("approval_positions", None, "审批岗位", "approvalPositions", 52, ["VIEW", "CONFIGURE"]),
    ("approval_workflows", None, "审批流程", "approvalWorkflows", 53, ["VIEW", "CREATE", "EDIT", "PUBLISH", "DISABLE"]),
    ("configuration", None, "基础配置", "configuration", 54, ["VIEW", "CREATE", "EDIT", "DELETE"]),
]
RBAC_ROLE_SEED = {
    "system_admin": ("系统管理员", "拥有全部菜单、操作和数据范围", {code: list(actions) for code, _, _, _, _, actions in RBAC_MENU_SEED}, "ALL"),
    "project_manager": ("项目经营管理员", "维护项目经营主数据和收付款", {code: list(actions) for code, _, _, _, _, actions in RBAC_MENU_SEED if code in {"projects", "contracts", "receipts", "payments", "project_board", "counterparties"}}, "ALL"),
    "project_owner": ("项目负责人", "管理负责项目的经营数据", {code: ["VIEW", "CREATE", "EDIT"] for code in ["projects", "contracts", "receipts", "payments"]} | {"project_board": ["VIEW"]}, "OWNED_PROJECTS"),
    "cashier": ("出纳", "处理合同收付款单据和出纳审批", {"receipts": ["VIEW", "CREATE", "EDIT", "APPROVE"], "payments": ["VIEW", "CREATE", "EDIT", "APPROVE"], "cash_approval": ["VIEW", "APPROVE"]}, "OWNED_PROJECTS"),
    "worklog_manager": ("工时管理员", "维护工时台账和工时看板", {"worklogs": ["VIEW", "EDIT", "DELETE", "EXPORT"], "reports": ["VIEW", "EXPORT"]}, "DEPARTMENT_AND_CHILDREN"),
    "worklog_approver": ("工时审批人", "处理分配给自己的工时审批", {"approvals": ["VIEW", "APPROVE"]}, "SELF"),
    "personnel_cost_manager": ("人员成本管理员", "维护人员单天成本", {"personnel_costs": ["VIEW", "EDIT", "EXPORT"]}, "DEPARTMENT_AND_CHILDREN"),
    "business_viewer": ("经营查看者", "只读查看项目经营数据", {code: ["VIEW"] for code in ["projects", "contracts", "receipts", "payments", "project_board", "counterparties"]}, "DEPARTMENT_AND_CHILDREN"),
    "integration_manager": ("集成管理员", "维护飞书集成和通知策略", {"integrations": ["VIEW", "CONFIGURE", "SYNC", "EXPORT"]}, "ALL"),
}
CONFIG_CATEGORY_LABELS = {
    "project_type": "项目类型",
    "project_stage": "项目阶段",
    "work_type": "工时类型",
    "work_status": "工作状态",
    "project_status": "项目状态",
}
DEFAULT_CONFIG_OPTIONS = {
    "project_type": [("RND_PROJECT", "研发项目"), ("TOPIC_PROJECT", "课题项目"), ("IMPLEMENTATION_PROJECT", "实施项目"), ("DEMONSTRATION_PROJECT", "观摩项目")],
    "project_stage": [("需求", "需求"), ("设计", "设计"), ("开发", "开发"), ("联调", "联调"), ("测试", "测试"), ("交付", "交付"), ("管理", "管理"), ("现场", "现场"), ("其它", "其它")],
    "work_type": [("PROJECT", "项目工时"), ("MANAGEMENT", "管理工时"), ("OTHER", "其它工时")],
    "work_status": [("LOCAL", "本地"), ("BUSINESS_TRIP", "出差"), ("REMOTE", "异地办公"), ("LEAVE", "休假")],
    "project_status": [("ACTIVE", "进行中"), ("ACCEPTANCE", "验收中"), ("PAUSED", "已暂停"), ("COMPLETED", "已完成")],
}
DEFAULT_BUDGET_ITEM_TEMPLATES = {
    "BUSINESS_PROJECT": [
        ("LABOR_COST", "人工费用", "人工费用", None, "LABOR"),
        ("MATERIAL_EQUIPMENT", "材料、设备采购", "材料、设备采购", None, "MIXED"),
        ("UTILITIES", "水、电、燃气费用", "水、电、燃气费用", None, "MIXED"),
        ("OUTSOURCING", "委托、分包、外包费用", "委托、分包、外包费用", None, "MIXED"),
        ("TRAVEL_COST", "差旅费用", "差旅费用", None, "MIXED"),
        ("PACKAGING_TRANSPORT", "包装、运输费用", "包装、运输费用", None, "MIXED"),
        ("LEASE_DEPRECIATION", "租赁费、折旧费", "租赁费、折旧费", None, "MIXED"),
        ("OTHER_COST", "其他费用", "其他费用", None, "MIXED"),
    ],
    "RND_PROJECT": [
        ("LABOR_COST", "人工费用", "人工费用", None, "LABOR"),
        ("MATERIAL_EQUIPMENT", "材料、设备采购", "材料、设备采购", None, "MIXED"),
        ("UTILITIES", "水、电、燃气费用", "水、电、燃气费用", None, "MIXED"),
        ("OUTSOURCING", "委托、分包、外包费用", "委托、分包、外包费用", None, "MIXED"),
        ("TRAVEL_COST", "差旅费用", "差旅费用", None, "MIXED"),
        ("PACKAGING_TRANSPORT", "包装、运输费用", "包装、运输费用", None, "MIXED"),
        ("LEASE_DEPRECIATION", "租赁费、折旧费", "租赁费、折旧费", None, "MIXED"),
        ("OTHER_COST", "其他费用", "其他费用", None, "MIXED"),
    ],
}
LEGACY_BUDGET_ITEM_CODE_MAP = {
    "LABOR_COST": "LABOR_COST",
    "MATERIAL_COST": "MATERIAL_EQUIPMENT",
    "EQUIPMENT_PURCHASE": "MATERIAL_EQUIPMENT",
    "TECH_SERVICE": "OUTSOURCING",
    "ENGINEERING_SUBCONTRACT": "OUTSOURCING",
    "EXTERNAL_PROCESSING": "OUTSOURCING",
    "DECLARATION_SERVICE": "OUTSOURCING",
    "LOGISTICS_PACKING": "PACKAGING_TRANSPORT",
    "NO_CONTRACT_INVOICE": "OTHER_COST",
    "TEST_EXPERIMENT": "OTHER_COST",
}
DEFAULT_NOTIFICATION_POLICIES = [
    ("WORKLOG_APPROVAL", "工时审批提醒", True, 0),
    ("SETTLEMENT_APPROVED", "合同收付款审批结果", True, 0),
    ("STAGE_UPCOMING", "合同阶段临期", True, 7),
    ("STAGE_DUE", "合同阶段到期", True, 0),
    ("STAGE_OVERDUE", "合同阶段逾期", True, 0),
    ("COST_BUDGET_NEAR", "成本预算接近上限", True, 0),
    ("COST_BUDGET_OVER", "成本预算超支", True, 0),
    ("PENDING_RECEIPT", "待审批合同收款单", True, 0),
    ("PENDING_PAYMENT", "待审批合同付款单", True, 0),
    ("PAYMENT_RESULT", "合同付款单审批结果", True, 0),
    ("EXPENSE_APPROVAL", "项目费用审批提醒", True, 0),
    ("EXPENSE_RESULT", "项目费用审批结果", True, 0),
    ("EXPENSE_PAYMENT", "项目费用支付提醒", True, 0),
]
app = FastAPI(title="综合项目管理系统 API", version=API_VERSION)


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


AUTH_TOKEN_SALT = "xinye-feishu-session-v1"
AUTH_COMPATIBILITY_HEADER = b"x-xinye-session"
logger = logging.getLogger("uvicorn.error")


def session_secret() -> str:
    """Return the shared secret used to sign browser sessions and bearer tokens."""
    return os.getenv("FEISHU_SESSION_SECRET", "")


def auth_token_max_age() -> int:
    """Return the bearer-token lifetime in seconds, matching the cookie session."""
    return max(60, int(os.getenv("FEISHU_SESSION_MAX_AGE", "28800")))


def issue_auth_token(user_id: int) -> str:
    """Issue a time-limited signed token after a successful Feishu code exchange."""
    secret = session_secret()
    if not secret:
        raise RuntimeError("FEISHU_SESSION_SECRET is not configured")
    serializer = URLSafeTimedSerializer(secret_key=secret, salt=AUTH_TOKEN_SALT)
    return serializer.dumps({"v": 1, "user_id": user_id})


def verify_auth_token(token: str) -> int | None:
    """Validate a signed bearer token and return its local user ID."""
    secret = session_secret()
    if not secret or not token:
        return None
    serializer = URLSafeTimedSerializer(secret_key=secret, salt=AUTH_TOKEN_SALT)
    try:
        payload = serializer.loads(token, max_age=auth_token_max_age())
    except BadSignature:
        return None
    if not isinstance(payload, dict) or payload.get("v") != 1:
        return None
    raw_user_id = payload.get("user_id")
    return int(raw_user_id) if str(raw_user_id).isdigit() else None


def request_auth_user_id(scope: dict) -> tuple[int | None, dict[str, bool | str]]:
    """Validate standard or WebView-compatible authentication headers."""
    headers = {key.lower(): value for key, value in scope.get("headers", [])}
    raw_header = headers.get(b"authorization", b"").decode("latin-1").strip()
    scheme, separator, token = raw_header.partition(" ")
    bearer_present = bool(raw_header)
    bearer_token = token.strip() if separator and scheme.lower() == "bearer" else ""
    compatibility_token = headers.get(AUTH_COMPATIBILITY_HEADER, b"").decode("latin-1").strip()
    user_id = verify_auth_token(bearer_token)
    source = "authorization" if user_id else ""
    if not user_id and compatibility_token:
        user_id = verify_auth_token(compatibility_token)
        source = "compatibility" if user_id else ""
    return user_id, {
        "authorization_present": bearer_present,
        "compatibility_present": bool(compatibility_token),
        "token_valid": bool(user_id),
        "source": source or "none",
    }


def bearer_user_id(scope: dict) -> int | None:
    """Backward-compatible helper returning the authenticated request user ID."""
    return request_auth_user_id(scope)[0]


session_user_id: ContextVar[int | None] = ContextVar("session_user_id", default=None)


class SessionUserMiddleware:
    """把签名会话中的本地用户 ID放入当前请求上下文，并保护 app 模式 API。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        public_path = path == "/api/v1/auth/config" or path.startswith("/api/v1/auth/feishu/") or path == "/api/v1/auth/logout"
        session = scope.get("session") or {}
        raw_user_id = session.get("user_id")
        auth_diagnostic: dict[str, bool | str] = {
            "authorization_present": False,
            "compatibility_present": False,
            "token_valid": False,
            "source": "session" if str(raw_user_id).isdigit() else "none",
        }
        if not str(raw_user_id).isdigit():
            raw_user_id, auth_diagnostic = request_auth_user_id(scope)
        if path == "/api/v1/me":
            logger.info(
                "auth_diagnostic path=/api/v1/me session=%s authorization=%s compatibility=%s token_valid=%s source=%s",
                bool(session.get("user_id")),
                auth_diagnostic["authorization_present"],
                auth_diagnostic["compatibility_present"],
                auth_diagnostic["token_valid"],
                auth_diagnostic["source"],
            )
        token = session_user_id.set(int(raw_user_id) if str(raw_user_id).isdigit() else None)
        try:
            if os.getenv("FEISHU_MODE", "mock") == "app" and path.startswith("/api/v1/") and not public_path and scope.get("method") != "OPTIONS" and not session_user_id.get():
                response = JSONResponse(status_code=401, content={"detail": "AUTH_REQUIRED"})
                await response(scope, receive, send)
                return
            await self.app(scope, receive, send)
        finally:
            session_user_id.reset(token)


# SessionMiddleware must wrap the context middleware so scope['session'] is available.
app.add_middleware(SessionUserMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("FEISHU_SESSION_SECRET", "local-development-session-secret"),
    max_age=int(os.getenv("FEISHU_SESSION_MAX_AGE", "28800")),
    same_site="lax",
    https_only=env_bool("COOKIE_SECURE", False),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
feishu = FeishuAdapter()


class DepartmentIndex:
    """统一解析飞书部门树，并为筛选提供后代部门集合。"""

    def __init__(self, departments: list[Department]):
        self.departments = departments
        self.by_id = {item.id: item for item in departments}
        self.by_feishu_id = {item.feishu_department_id: item for item in departments}
        self.children_by_parent = defaultdict(list)
        for item in departments:
            self.children_by_parent[item.parent_feishu_department_id].append(item)

    def path(self, department_id: int | None) -> str:
        department = self.by_id.get(department_id) if department_id else None
        if not department:
            return "未分配部门"
        names: list[str] = []
        visited: set[str] = set()
        current = department
        while current:
            names.append(current.name)
            current_feishu_id = current.feishu_department_id
            if current_feishu_id in visited or not current.parent_feishu_department_id:
                break
            visited.add(current_feishu_id)
            parent = self.by_feishu_id.get(current.parent_feishu_department_id)
            if not parent:
                if current.parent_name and current.parent_name not in names:
                    names.append(current.parent_name)
                break
            current = parent
        return " / ".join(reversed(names))

    def root_name(self, department_id: int | None) -> str:
        path = self.path(department_id)
        return path.split(" / ", 1)[0] if path else "未分配部门"

    def descendants(self, department_id: int) -> set[int]:
        if department_id not in self.by_id:
            return set()
        result: set[int] = set()
        pending = [department_id]
        while pending:
            current_id = pending.pop()
            if current_id in result:
                continue
            result.add(current_id)
            current = self.by_id[current_id]
            pending.extend(child.id for child in self.children_by_parent.get(current.feishu_department_id, []))
        return result

    def with_ancestors(self, department_ids: set[int]) -> set[int]:
        """补齐已有数据部门的祖先，保证父部门也能作为筛选入口。"""
        result: set[int] = set()
        for department_id in department_ids:
            current = self.by_id.get(department_id)
            visited: set[str] = set()
            while current and current.id not in result:
                result.add(current.id)
                if not current.parent_feishu_department_id or current.feishu_department_id in visited:
                    break
                visited.add(current.feishu_department_id)
                current = self.by_feishu_id.get(current.parent_feishu_department_id)
        return result

    def resolve(self, department_id: int | None, department_name: str | None) -> int | None:
        if department_id is not None:
            if department_id not in self.by_id:
                raise HTTPException(400, "INVALID_DEPARTMENT")
            return department_id
        value = department_name.strip() if department_name and department_name.strip() else ""
        if not value:
            return None
        path_matches = [item.id for item in self.departments if self.path(item.id) == value]
        if len(path_matches) == 1:
            return path_matches[0]
        name_matches = [item.id for item in self.departments if item.name == value]
        if len(name_matches) == 1:
            return name_matches[0]
        raise HTTPException(400, "INVALID_DEPARTMENT")

    def options(self, department_ids: set[int] | None = None, active_only: bool = True) -> list[str]:
        values = [item for item in self.departments if (not active_only or item.is_active) and (department_ids is None or item.id in department_ids)]
        return [self.path(item.id) for item in sorted(values, key=lambda current: (self.path(current.id), current.id))]


def config_option_rows(db: Session, category: str, active_only: bool = True) -> list[ConfigOption]:
    """按配置分类读取选项，稳定值与展示名称分离。"""
    query = select(ConfigOption).where(ConfigOption.category == category)
    if active_only:
        query = query.where(ConfigOption.is_active.is_(True))
    return list(db.scalars(query.order_by(ConfigOption.sort_order, ConfigOption.id)).all())


def validate_config_option(db: Session, category: str, value: str, *, allow_inactive: bool = False) -> ConfigOption:
    """所有业务写入都在服务端校验动态选项，避免只依赖前端过滤。"""
    if category not in CONFIG_CATEGORY_LABELS:
        raise HTTPException(400, "INVALID_CONFIG_CATEGORY")
    option = db.scalar(select(ConfigOption).where(ConfigOption.category == category, ConfigOption.value == value))
    if not option or (not option.is_active and not allow_inactive):
        raise HTTPException(400, f"INVALID_{category.upper()}")
    return option


def seed_config_options(db: Session) -> None:
    """首次启动写入默认选项；已有选项的显示名称由管理员维护。"""
    for category, values in DEFAULT_CONFIG_OPTIONS.items():
        for order, (value, label) in enumerate(values, start=1):
            option = db.scalar(select(ConfigOption).where(ConfigOption.category == category, ConfigOption.value == value))
            if not option:
                db.add(ConfigOption(category=category, value=value, label=label, sort_order=order, is_active=True, is_builtin=True))


def project_budget_category(project_type: str | None) -> str:
    """按项目类型归并预算项模板大类：研发类与经营类分开维护。"""
    normalized = (project_type or "").strip().upper()
    if normalized in {"RND_PROJECT", "TOPIC_PROJECT", "SELF_DEVELOPED_RND", "EXTERNAL_DECLARATION"}:
        return "RND_PROJECT"
    if (project_type or "").strip() in {"研发项目", "课题项目", "自主研发", "外部申报"}:
        return "RND_PROJECT"
    return "BUSINESS_PROJECT"


def budget_template_code(name: str, project_category: str) -> str:
    """为管理员新增预算项生成稳定编码，优先可读前缀，重复时由调用方补序号。"""
    ascii_code = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    if ascii_code:
        return ascii_code[:60]
    prefix = "RND" if project_category == "RND_PROJECT" else "BIZ"
    return f"{prefix}_BUDGET_ITEM"


def seed_budget_item_templates(db: Session) -> None:
    """写入经营项目和研发项目的默认预算项模板，不覆盖管理员调整。"""
    canonical_codes = {
        category: {code for code, *_ in rows}
        for category, rows in DEFAULT_BUDGET_ITEM_TEMPLATES.items()
    }
    for category, rows in DEFAULT_BUDGET_ITEM_TEMPLATES.items():
        for order, (code, name, major, minor, source_kind) in enumerate(rows, start=1):
            template = db.scalar(
                select(BudgetItemTemplate).where(
                    BudgetItemTemplate.project_category == category,
                    BudgetItemTemplate.code == code,
                )
            )
            if not template:
                db.add(
                    BudgetItemTemplate(
                        project_category=category,
                        code=code,
                        name=name,
                        cost_major=major,
                        cost_minor=minor,
                        source_kind=source_kind,
                        sort_order=order * 10,
                        is_active=True,
                        is_builtin=True,
                    )
                )
            elif template.is_builtin:
                template.name = name
                template.cost_major = major
                template.cost_minor = minor
                template.source_kind = source_kind
                template.sort_order = order * 10
                template.is_active = True
        for template in db.scalars(select(BudgetItemTemplate).where(BudgetItemTemplate.project_category == category)).all():
            if template.code not in canonical_codes[category] and template.is_builtin:
                template.is_active = False


def ensure_project_budget_items(db: Session, project: Project) -> None:
    """按项目大类补齐项目预算项，并把旧预算项幂等归并到统一 8 项。"""
    category = project_budget_category(project.project_type)
    templates = db.scalars(
        select(BudgetItemTemplate)
        .where(BudgetItemTemplate.project_category == category, BudgetItemTemplate.is_active.is_(True))
        .order_by(BudgetItemTemplate.sort_order, BudgetItemTemplate.id)
    ).all()
    existing_items = db.scalars(select(ProjectBudgetItem).where(ProjectBudgetItem.project_id == project.id)).all()
    existing_by_code = {item.code: item for item in existing_items}
    for template in templates:
        current = existing_by_code.get(template.code)
        if current:
            current.template_id = template.id
            current.name = template.name
            current.cost_major = template.cost_major
            current.cost_minor = template.cost_minor
            current.source_kind = template.source_kind
            current.sort_order = template.sort_order
            current.is_active = True
            continue
        initial_budget = 0.0
        if template.code == "LABOR_COST":
            initial_budget = 0.0
        current = ProjectBudgetItem(
                project_id=project.id,
                template_id=template.id,
                code=template.code,
                name=template.name,
                cost_major=template.cost_major,
                cost_minor=template.cost_minor,
                source_kind=template.source_kind,
                sort_order=template.sort_order,
                budget_amount=initial_budget,
                is_active=True,
        )
        db.add(current)
        db.flush()
        existing_by_code[template.code] = current

    for legacy_code, target_code in LEGACY_BUDGET_ITEM_CODE_MAP.items():
        if legacy_code == target_code:
            continue
        legacy = existing_by_code.get(legacy_code)
        target = existing_by_code.get(target_code)
        if not legacy or not target or legacy.id == target.id:
            continue
        if legacy.is_active or float(legacy.budget_amount or 0) > 0:
            target.budget_amount = round(float(target.budget_amount or 0) + float(legacy.budget_amount or 0), 2)
            for contract in db.scalars(select(Contract).where(Contract.budget_item_id == legacy.id)).all():
                apply_budget_snapshot(contract, target)
            for payment in db.scalars(select(Payment).where(Payment.budget_item_id == legacy.id)).all():
                apply_budget_snapshot(payment, target)
            for expense in db.scalars(select(ProjectExpense).where(ProjectExpense.budget_item_id == legacy.id)).all():
                apply_budget_snapshot(expense, target)
            for ledger in db.scalars(select(ProjectLedgerEntry).where(ProjectLedgerEntry.budget_item_id == legacy.id)).all():
                apply_budget_snapshot(ledger, target)
        legacy.is_active = False
        legacy.budget_amount = 0
        legacy.remark = "已按统一预算项归并"
    active_budget_total = sum(float(item.budget_amount or 0) for item in existing_by_code.values() if item.is_active)
    non_labor_budget_total = sum(float(item.budget_amount or 0) for item in existing_by_code.values() if item.is_active and item.code != "LABOR_COST")
    legacy_project_budget = float(project.budget_cost or 0)
    if active_budget_total <= 0 and legacy_project_budget > 0:
        fallback = existing_by_code.get("OTHER_COST") or next(
            (item for item in existing_by_code.values() if item.is_active and item.code != "LABOR_COST"),
            None,
        )
        if fallback:
            fallback.budget_amount = round(legacy_project_budget, 2)
            fallback.remark = fallback.remark or "由旧项目预算字段自动迁移"
            active_budget_total = legacy_project_budget
            non_labor_budget_total = legacy_project_budget
    legacy_expense_budget = float(project.expense_budget or 0)
    if non_labor_budget_total <= 0 and legacy_expense_budget > 0:
        fallback = existing_by_code.get("OTHER_COST") or next(
            (item for item in existing_by_code.values() if item.is_active and item.code != "LABOR_COST"),
            None,
        )
        if fallback:
            fallback.budget_amount = round(legacy_expense_budget, 2)
            fallback.remark = fallback.remark or "由旧非人工预算字段自动迁移"
            active_budget_total = legacy_expense_budget
    project.budget_cost = round(active_budget_total, 2)


def ensure_all_project_budget_items(db: Session) -> None:
    """启动和模板维护后为所有现有项目补齐预算项。"""
    for project in db.scalars(select(Project).where(Project.status != "DELETED")).all():
        ensure_project_budget_items(db, project)


def project_budget_total(db: Session, project_id: int) -> float:
    """项目总预算等于启用预算项金额合计。"""
    return round(float(db.scalar(
        select(func.coalesce(func.sum(ProjectBudgetItem.budget_amount), 0)).where(
            ProjectBudgetItem.project_id == project_id,
            ProjectBudgetItem.is_active.is_(True),
        )
    ) or 0), 2)


def project_labor_budget_item(db: Session, project_id: int) -> ProjectBudgetItem | None:
    """返回项目人工成本预算项；缺失时按项目类型模板补齐后重读。"""
    item = db.scalar(
        select(ProjectBudgetItem).where(
            ProjectBudgetItem.project_id == project_id,
            ProjectBudgetItem.code == "LABOR_COST",
        )
    )
    if item:
        return item
    project = db.get(Project, project_id)
    if not project:
        return None
    ensure_project_budget_items(db, project)
    db.flush()
    return db.scalar(
        select(ProjectBudgetItem).where(
            ProjectBudgetItem.project_id == project_id,
            ProjectBudgetItem.code == "LABOR_COST",
        )
    )


def default_project_budget_item(db: Session, project_id: int, source_kind: str | None = None, preferred_code: str | None = None) -> ProjectBudgetItem | None:
    """兼容旧接口：未显式传预算项时，为支出合同或费用单选择一个非人工默认项。"""
    project = db.get(Project, project_id)
    if not project:
        return None
    ensure_project_budget_items(db, project)
    db.flush()
    query = select(ProjectBudgetItem).where(
        ProjectBudgetItem.project_id == project_id,
        ProjectBudgetItem.is_active.is_(True),
        ProjectBudgetItem.code != "LABOR_COST",
    )
    if source_kind:
        query = query.where(ProjectBudgetItem.source_kind.in_((source_kind, "MIXED")))
    rows = list(db.scalars(query.order_by(ProjectBudgetItem.sort_order, ProjectBudgetItem.id)).all())
    if preferred_code:
        preferred = next((item for item in rows if item.code == preferred_code), None)
        if preferred:
            return preferred
    return rows[0] if rows else None


def resolve_project_budget_item(db: Session, project_id: int, budget_item_id: int | None, *, required: bool = True, source_kind: str | None = None) -> ProjectBudgetItem | None:
    """校验预算项属于当前项目，并可按来源类型过滤。"""
    if budget_item_id is None:
        if required:
            fallback = default_project_budget_item(db, project_id, source_kind)
            if fallback:
                return fallback
            raise HTTPException(400, "BUDGET_ITEM_REQUIRED")
        return None
    item = db.get(ProjectBudgetItem, budget_item_id)
    if not item or item.project_id != project_id:
        raise HTTPException(400, "BUDGET_ITEM_NOT_FOUND")
    if not item.is_active:
        raise HTTPException(400, "BUDGET_ITEM_INACTIVE")
    if source_kind and item.source_kind not in {source_kind, "MIXED"}:
        raise HTTPException(400, "BUDGET_ITEM_SOURCE_MISMATCH")
    return item


def apply_budget_snapshot(target: object, item: ProjectBudgetItem | None) -> None:
    """把预算项与成本大小类快照写入合同、付款、费用或流水。"""
    setattr(target, "budget_item_id", item.id if item else None)
    setattr(target, "budget_item_name_snapshot", item.name if item else None)
    setattr(target, "cost_major_snapshot", item.cost_major if item else None)
    setattr(target, "cost_minor_snapshot", item.cost_minor if item else None)


def apply_contract_budget_snapshot(db: Session, target: object, contract: Contract) -> ProjectBudgetItem | None:
    """付款单继承支出合同预算项快照，合同项仍存在时返回预算项实体供流水使用。"""
    item = db.get(ProjectBudgetItem, contract.budget_item_id) if contract.budget_item_id else None
    setattr(target, "budget_item_id", contract.budget_item_id)
    setattr(target, "budget_item_name_snapshot", contract.budget_item_name_snapshot)
    setattr(target, "cost_major_snapshot", contract.cost_major_snapshot)
    setattr(target, "cost_minor_snapshot", contract.cost_minor_snapshot)
    return item


def project_budget_item_actuals(db: Session, project_id: int) -> dict[int, float]:
    """按预算项汇总已发生成本，旧流水会尽量通过来源单据回填归类。"""
    actuals: dict[int, float] = defaultdict(float)
    ledger_rows = db.scalars(
        select(ProjectLedgerEntry).where(
            ProjectLedgerEntry.project_id == project_id,
            ProjectLedgerEntry.entry_type.in_(("PERSONNEL_COST", "PAYMENT", "PROJECT_EXPENSE_COST", "REVERSAL")),
        )
    ).all()
    labor_item = None
    for entry in ledger_rows:
        budget_item_id = entry.budget_item_id
        if not budget_item_id:
            if entry.entry_type == "PERSONNEL_COST":
                labor_item = labor_item or project_labor_budget_item(db, project_id)
                budget_item_id = labor_item.id if labor_item else None
            elif entry.entry_type == "PAYMENT":
                payment = db.get(Payment, entry.source_id)
                budget_item_id = payment.budget_item_id if payment else None
            elif entry.entry_type == "PROJECT_EXPENSE_COST":
                expense = db.get(ProjectExpense, entry.source_id)
                budget_item_id = expense.budget_item_id if expense else None
            elif entry.entry_type == "REVERSAL" and entry.source_type == "PAYMENT":
                payment = db.get(Payment, entry.source_id)
                budget_item_id = payment.budget_item_id if payment else None
            elif entry.entry_type == "REVERSAL" and entry.source_type == "PROJECT_EXPENSE":
                expense = db.get(ProjectExpense, entry.source_id)
                budget_item_id = expense.budget_item_id if expense else None
        if budget_item_id:
            direction = -1 if entry.entry_type == "REVERSAL" else 1
            actuals[int(budget_item_id)] += direction * float(entry.amount or 0)
    return {key: round(value, 2) for key, value in actuals.items()}


def project_budget_item_views(db: Session, project_id: int) -> list[ProjectBudgetItemView]:
    """返回项目预算项及已发生、剩余、使用率。"""
    project = db.get(Project, project_id)
    if project:
        ensure_project_budget_items(db, project)
        db.flush()
    actuals = project_budget_item_actuals(db, project_id)
    rows = db.scalars(
        select(ProjectBudgetItem)
        .where(ProjectBudgetItem.project_id == project_id)
        .order_by(ProjectBudgetItem.is_active.desc(), ProjectBudgetItem.sort_order, ProjectBudgetItem.id)
    ).all()
    result: list[ProjectBudgetItemView] = []
    for item in rows:
        budget = round(float(item.budget_amount or 0), 2)
        actual = round(float(actuals.get(item.id, 0)), 2)
        result.append(
            ProjectBudgetItemView(
                id=item.id,
                project_id=item.project_id,
                template_id=item.template_id,
                code=item.code,
                name=item.name,
                cost_major=item.cost_major,
                cost_minor=item.cost_minor,
                source_kind=item.source_kind,
                sort_order=item.sort_order,
                budget_amount=budget,
                actual_amount=actual,
                remaining_amount=round(budget - actual, 2),
                usage_rate=round(actual / budget * 100, 1) if budget > 0 else None,
                is_active=item.is_active,
                remark=item.remark,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
    return result


def backfill_ledger_budget_snapshots(db: Session) -> int:
    """为旧流水补预算项快照，保证历史成本能出现在预算项分析里。"""
    updated = 0
    rows = db.scalars(
        select(ProjectLedgerEntry).where(
            ProjectLedgerEntry.budget_item_id.is_(None),
            ProjectLedgerEntry.entry_type.in_(("PERSONNEL_COST", "PAYMENT", "PROJECT_EXPENSE_COST")),
        )
    ).all()
    for entry in rows:
        item: ProjectBudgetItem | None = None
        if entry.entry_type == "PERSONNEL_COST":
            item = project_labor_budget_item(db, entry.project_id)
        elif entry.entry_type == "PAYMENT":
            payment = db.get(Payment, entry.source_id)
            if payment and not payment.budget_item_id:
                contract = db.get(Contract, payment.contract_id)
                if contract:
                    apply_contract_budget_snapshot(db, payment, contract)
            item = db.get(ProjectBudgetItem, payment.budget_item_id) if payment and payment.budget_item_id else None
        elif entry.entry_type == "PROJECT_EXPENSE_COST":
            expense = db.get(ProjectExpense, entry.source_id)
            item = db.get(ProjectBudgetItem, expense.budget_item_id) if expense and expense.budget_item_id else None
        if item:
            apply_budget_snapshot(entry, item)
            updated += 1
    if updated:
        db.flush()
    return updated


def seed_notification_policies(db: Session) -> None:
    """建立业务通知策略；已存在策略只同步内置显示名，不覆盖管理员启停和渠道设置。"""
    for notification_type, label, enabled, remind_days_before in DEFAULT_NOTIFICATION_POLICIES:
        policy = db.scalar(select(NotificationPolicy).where(NotificationPolicy.notification_type == notification_type))
        if not policy:
            db.add(NotificationPolicy(notification_type=notification_type, label=label, enabled=enabled, send_channel="app", remind_days_before=remind_days_before))
        elif policy.label != label:
            policy.label = label


def _json_list(value: str | None) -> list[str]:
    """读取权限 JSON；旧数据损坏时按空权限处理，避免阻断应用启动。"""
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return [item for item in parsed if isinstance(item, str)]


def seed_rbac(db: Session) -> None:
    """初始化菜单、内置角色及其默认权限，重复启动不会覆盖管理员修改。"""
    menus_by_code: dict[str, Menu] = {}
    for code, parent_code, label, route, sort_order, actions in RBAC_MENU_SEED:
        menu = db.scalar(select(Menu).where(Menu.code == code))
        if not menu:
            menu = Menu(code=code, label=label, route=route, sort_order=sort_order, actions=json.dumps(actions, ensure_ascii=False))
            db.add(menu)
            db.flush()
        menu.label = label
        menu.route = route
        menu.sort_order = sort_order
        menu.is_active = True
        menu.actions = json.dumps(actions, ensure_ascii=False)
        menus_by_code[code] = menu
    for code, parent_code, *_ in RBAC_MENU_SEED:
        menus_by_code[code].parent_id = menus_by_code[parent_code].id if parent_code else None
    db.flush()
    for code in ("system_admin",):
        name, description, permissions, scope_type = RBAC_ROLE_SEED[code]
        role = db.scalar(select(Role).where(Role.code == code))
        if not role:
            role = Role(code=code, name=name, description=description, is_builtin=True, is_active=True)
            db.add(role)
            db.flush()
        for menu_code, actions in permissions.items():
            menu = menus_by_code.get(menu_code)
            if not menu:
                continue
            item = db.scalar(select(RolePermission).where(RolePermission.role_id == role.id, RolePermission.menu_id == menu.id))
            if not item:
                db.add(RolePermission(role_id=role.id, menu_id=menu.id, actions=json.dumps(actions)))
            elif role.is_builtin:
                item.actions = json.dumps(actions)
            scope_resource = menu_code
            scope = db.scalar(select(RoleDataScope).where(RoleDataScope.role_id == role.id, RoleDataScope.resource == scope_resource))
            if not scope:
                db.add(RoleDataScope(role_id=role.id, resource=scope_resource, scope_type=scope_type))


def seed_approval_workflows(db: Session) -> None:
    """初始化审批岗位和两套已确认流程；已有发布版本绝不覆盖。"""
    position_specs = [
        ("OPERATIONS_REVIEWER", "经营审批", "核对项目经营合理性"),
        ("OPERATIONS_VP", "经营副总", "经营条线复核"),
        ("ACCOUNTANT", "会计", "核对票据、金额和成本归属"),
        ("FINANCE_DIRECTOR", "财务总监", "财务条线终审"),
        ("GENERAL_MANAGER", "总经理", "最终经营审批"),
        ("CASHIER", "出纳", "核对账户并登记实际支付"),
    ]
    positions: dict[str, ApprovalPosition] = {}
    for code, name, description in position_specs:
        position = db.scalar(select(ApprovalPosition).where(ApprovalPosition.code == code))
        if not position:
            position = ApprovalPosition(code=code, name=name, description=description, status="ACTIVE")
            db.add(position)
            db.flush()
        positions[code] = position

    workflow_specs = [
        (
            "TRAVEL_EXPENSE",
            "差旅费用审批",
            ["PROJECT_EXPENSE_TRAVEL"],
            [
                ("PROJECT_APPROVER", "项目审批", "PROJECT_APPROVER", None, "SINGLE", False),
                ("ACCOUNTANT", "会计审核", "APPROVAL_POSITION", "ACCOUNTANT", "ANY", False),
                ("DIRECT_MANAGER", "上级领导", "DIRECT_MANAGER", None, "SINGLE", False),
                ("FINANCE_DIRECTOR", "财务总监审批", "APPROVAL_POSITION", "FINANCE_DIRECTOR", "ANY", False),
                ("GENERAL_MANAGER", "总经理审批", "APPROVAL_POSITION", "GENERAL_MANAGER", "ANY", False),
                ("CASHIER", "出纳支付", "APPROVAL_POSITION", "CASHIER", "ANY", True),
            ],
        ),
        (
            "PROJECT_PAYMENT",
            "合同付款与费用审批",
            ["PAYMENT", "PROJECT_EXPENSE_INVOICE", "PROJECT_EXPENSE_OTHER"],
            [
                ("PROJECT_APPROVER", "项目审批", "PROJECT_APPROVER", None, "SINGLE", False),
                ("ACCOUNTANT", "会计审核", "APPROVAL_POSITION", "ACCOUNTANT", "ANY", False),
                ("OPERATIONS_REVIEWER", "经营审批", "APPROVAL_POSITION", "OPERATIONS_REVIEWER", "ANY", False),
                ("DIRECT_MANAGER", "上级领导", "DIRECT_MANAGER", None, "SINGLE", False),
                ("OPERATIONS_VP", "经营副总", "APPROVAL_POSITION", "OPERATIONS_VP", "ANY", False),
                ("FINANCE_DIRECTOR", "财务总监审批", "APPROVAL_POSITION", "FINANCE_DIRECTOR", "ANY", False),
                ("GENERAL_MANAGER", "总经理审批", "APPROVAL_POSITION", "GENERAL_MANAGER", "ANY", False),
                ("CASHIER", "出纳支付", "APPROVAL_POSITION", "CASHIER", "ANY", True),
            ],
        ),
    ]
    for code, name, document_types, node_specs in workflow_specs:
        definition = db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.code == code))
        if not definition:
            definition = WorkflowDefinition(code=code, name=name, document_types=json.dumps(document_types), status="ACTIVE")
            db.add(definition)
            db.flush()
        if definition.current_version_id:
            continue
        version = WorkflowVersion(workflow_definition_id=definition.id, version=1, status="PUBLISHED", published_at=now_local())
        db.add(version)
        db.flush()
        for sequence, (node_code, node_name, resolver, position_code, mode, is_payment) in enumerate(node_specs, start=1):
            db.add(
                WorkflowNode(
                    workflow_version_id=version.id,
                    sequence=sequence,
                    code=node_code,
                    name=node_name,
                    resolver_type=resolver,
                    position_id=positions[position_code].id if position_code else None,
                    approval_mode=mode,
                    is_payment=is_payment,
                    notification_enabled=True,
                )
            )
        definition.current_version_id = version.id


def reset_rbac_configuration(db: Session, *, force: bool = False) -> bool:
    """首次启动清空角色配置，只保留系统管理员角色；完成后不重复清理。"""
    marker = db.scalar(select(ConfigOption).where(ConfigOption.category == "system_internal", ConfigOption.value == RBAC_RESET_MARKER))
    if marker and not force:
        return False
    system_role = db.scalar(select(Role).where(Role.code == "system_admin"))
    if not system_role:
        return False
    db.query(UserRoleScope).delete(synchronize_session=False)
    db.query(UserRole).delete(synchronize_session=False)
    db.query(RoleDataScope).filter(RoleDataScope.role_id != system_role.id).delete(synchronize_session=False)
    db.query(RolePermission).filter(RolePermission.role_id != system_role.id).delete(synchronize_session=False)
    db.query(Role).filter(Role.id != system_role.id).delete(synchronize_session=False)
    db.query(AdminPermission).delete(synchronize_session=False)
    if not marker:
        db.add(ConfigOption(category="system_internal", value=RBAC_RESET_MARKER, label="RBAC 角色配置已重置", sort_order=0, is_active=True, is_builtin=True))
    return True


def upgrade_schema() -> None:
    """为现有 SQLite 数据库增量补齐字段，所有操作均可重复执行。"""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    additions = {
        "users": [("open_id", "VARCHAR(128)"), ("email", "VARCHAR(200)"), ("daily_cost", "NUMERIC(10, 2)"), ("snapshot_at", "DATETIME")],
        "departments": [("parent_feishu_department_id", "VARCHAR(64)")],
        "projects": [
            ("project_type", "VARCHAR(80) NOT NULL DEFAULT 'RND_PROJECT'"),
            ("owner_user_id", "INTEGER"),
            ("owner_open_id", "VARCHAR(128)"),
            ("approver_user_id", "INTEGER"),
            ("approver_open_id", "VARCHAR(128)"),
            ("leader_user_id", "INTEGER"),
            ("leader_name", "VARCHAR(100)"),
            ("leader_open_id", "VARCHAR(128)"),
            ("department_id", "INTEGER"),
            ("budget_days", "NUMERIC(12, 2) NOT NULL DEFAULT 0"),
            ("budget_cost", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
            ("expense_budget", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
            ("customer_id", "INTEGER"),
            ("customer_name", "VARCHAR(300)"),
            ("start_date", "DATE"),
            ("planned_end_date", "DATE"),
            ("description", "TEXT"),
        ],
        "customers": [
            ("contact_name", "VARCHAR(100)"),
            ("contact_phone", "VARCHAR(60)"),
            ("contact_email", "VARCHAR(200)"),
            ("address", "VARCHAR(500)"),
            ("office_address", "VARCHAR(500)"),
            ("license_expiry_date", "DATE"),
            ("bank_name", "VARCHAR(200)"),
            ("bank_branch", "VARCHAR(200)"),
            ("bank_account", "VARCHAR(100)"),
            ("invoice_title", "VARCHAR(300)"),
            ("taxpayer_id", "VARCHAR(32)"),
            ("invoice_address", "VARCHAR(500)"),
            ("invoice_phone", "VARCHAR(60)"),
            ("notes", "TEXT"),
        ],
        "suppliers": [
            ("contact_name", "VARCHAR(100)"),
            ("contact_phone", "VARCHAR(60)"),
            ("contact_email", "VARCHAR(200)"),
            ("address", "VARCHAR(500)"),
            ("office_address", "VARCHAR(500)"),
            ("license_expiry_date", "DATE"),
            ("bank_name", "VARCHAR(200)"),
            ("bank_branch", "VARCHAR(200)"),
            ("bank_account", "VARCHAR(100)"),
            ("invoice_title", "VARCHAR(300)"),
            ("taxpayer_id", "VARCHAR(32)"),
            ("invoice_address", "VARCHAR(500)"),
            ("invoice_phone", "VARCHAR(60)"),
            ("notes", "TEXT"),
        ],
        "admin_permissions": [
            ("can_manage_configuration", "BOOLEAN NOT NULL DEFAULT 0"),
            ("can_manage_contracts", "BOOLEAN NOT NULL DEFAULT 0"),
            ("can_manage_receipts", "BOOLEAN NOT NULL DEFAULT 0"),
            ("can_manage_payments", "BOOLEAN NOT NULL DEFAULT 0"),
            ("can_view_project_board", "BOOLEAN NOT NULL DEFAULT 0"),
            ("can_manage_counterparties", "BOOLEAN NOT NULL DEFAULT 0"),
            ("can_approve_cash", "BOOLEAN NOT NULL DEFAULT 0"),
            ("project_data_scope", "VARCHAR(20) NOT NULL DEFAULT 'OWNED'"),
            ("scope_department_id", "INTEGER"),
        ],
        "contract_stages": [
            ("remind_days_before", "INTEGER NOT NULL DEFAULT 7"),
            ("reminder_paused", "BOOLEAN NOT NULL DEFAULT 0"),
        ],
        "contracts": [
            ("budget_item_id", "INTEGER"),
            ("budget_item_name_snapshot", "VARCHAR(120)"),
            ("cost_major_snapshot", "VARCHAR(120)"),
            ("cost_minor_snapshot", "VARCHAR(120)"),
        ],
        "payments": [
            ("current_workflow_instance_id", "INTEGER"),
            ("version", "INTEGER NOT NULL DEFAULT 1"),
            ("budget_item_id", "INTEGER"),
            ("budget_item_name_snapshot", "VARCHAR(120)"),
            ("cost_major_snapshot", "VARCHAR(120)"),
            ("cost_minor_snapshot", "VARCHAR(120)"),
        ],
        "project_expenses": [
            ("budget_item_id", "INTEGER"),
            ("budget_item_name_snapshot", "VARCHAR(120)"),
            ("cost_major_snapshot", "VARCHAR(120)"),
            ("cost_minor_snapshot", "VARCHAR(120)"),
        ],
        "project_ledger_entries": [
            ("budget_item_id", "INTEGER"),
            ("budget_item_name_snapshot", "VARCHAR(120)"),
            ("cost_major_snapshot", "VARCHAR(120)"),
            ("cost_minor_snapshot", "VARCHAR(120)"),
        ],
        "project_budget_items": [
            ("sort_order", "INTEGER NOT NULL DEFAULT 0"),
        ],
        "worklogs": [
            ("approver_user_id", "INTEGER"),
            ("approver_name_snapshot", "VARCHAR(100)"),
            ("submitted_at", "DATETIME"),
            ("approved_at", "DATETIME"),
            ("rejection_reason", "TEXT"),
            ("approval_comment", "TEXT"),
            ("approval_version", "INTEGER NOT NULL DEFAULT 0"),
            ("daily_cost_snapshot", "NUMERIC(10, 2)"),
            ("cost_amount_snapshot", "NUMERIC(14, 2)"),
            ("last_notified_at", "DATETIME"),
        ],
        "system_notifications": [
            ("retry_count", "INTEGER NOT NULL DEFAULT 0"),
        ],
        "org_sync_logs": [
            ("added_user_count", "INTEGER NOT NULL DEFAULT 0"),
            ("updated_user_count", "INTEGER NOT NULL DEFAULT 0"),
            ("added_department_count", "INTEGER NOT NULL DEFAULT 0"),
            ("updated_department_count", "INTEGER NOT NULL DEFAULT 0"),
            ("duration_ms", "INTEGER NOT NULL DEFAULT 0"),
        ],
    }
    legacy_datetime_columns = {
        "users": ("snapshot_at",),
        "admin_permissions": ("updated_at",),
        "customers": ("updated_at",),
        "suppliers": ("updated_at",),
        "projects": ("updated_at",),
        "worklogs": ("submitted_at", "approved_at", "last_notified_at", "created_at", "updated_at"),
        "timesheets": ("created_at", "updated_at"),
        "approval_tasks": ("submitted_at", "processed_at", "created_at"),
        "notifications": ("sent_at", "created_at"),
        "audit_logs": ("created_at",),
        "config_options": ("created_at", "updated_at"),
        "contracts": ("created_at", "updated_at"),
        "contract_attachments": ("created_at",),
        "cash_document_attachments": ("created_at",),
        "contract_stages": ("created_at", "updated_at"),
        "receipts": ("submitted_at", "approved_at", "created_at", "updated_at"),
        "payments": ("submitted_at", "approved_at", "created_at", "updated_at"),
        "project_ledger_entries": ("created_at",),
        "reminder_events": ("created_at",),
        "system_notifications": ("sent_at", "created_at"),
        "notification_policies": ("updated_at",),
        "org_sync_logs": ("created_at",),
        "budget_item_templates": ("created_at", "updated_at"),
        "project_budget_items": ("created_at", "updated_at"),
    }
    with engine.begin() as connection:
        is_sqlite = engine.dialect.name == "sqlite"
        current_timezone_migration = (
            int(connection.exec_driver_sql("PRAGMA user_version").scalar() or 0)
            if is_sqlite
            else TIMEZONE_DATA_MIGRATION_VERSION
        )
        for table, columns in additions.items():
            existing = {column["name"] for column in inspect(engine).get_columns(table)}
            for name, definition in columns:
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        if is_sqlite and current_timezone_migration < TIMEZONE_DATA_MIGRATION_VERSION:
            # 旧版本使用 datetime.utcnow() 写入无时区字段；数据库仍保持无时区格式，
            # 这里只对已有值做一次 UTC -> Asia/Shanghai 的历史修正。
            for table, columns in legacy_datetime_columns.items():
                for column in columns:
                    rows = connection.execute(
                        text(f'SELECT rowid, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL')
                    ).all()
                    for row_id, raw_value in rows:
                        try:
                            shifted_value = datetime.fromisoformat(str(raw_value)) + timedelta(hours=8)
                        except ValueError:
                            # 非标准历史值不强行改写，保留原始数据供人工核查。
                            continue
                        connection.execute(
                            text(f'UPDATE "{table}" SET "{column}" = :shifted_value WHERE rowid = :row_id'),
                            {"shifted_value": shifted_value.isoformat(sep=" "), "row_id": row_id},
                        )
            connection.exec_driver_sql(
                f"PRAGMA user_version = {TIMEZONE_DATA_MIGRATION_VERSION}"
            )
        connection.execute(text("UPDATE worklogs SET approval_version = 0 WHERE approval_version IS NULL"))
        # v3.0 人员成本快照：已审批且快照仍为 0 的历史工时按当前单天成本补齐，并同步经营流水。
        connection.execute(text("UPDATE worklogs SET daily_cost_snapshot = COALESCE((SELECT daily_cost FROM users WHERE users.id = worklogs.user_id), 0), cost_amount_snapshot = ROUND(quantity * COALESCE((SELECT daily_cost FROM users WHERE users.id = worklogs.user_id), 0), 2) WHERE status IN ('APPROVED', 'LOCKED') AND (daily_cost_snapshot IS NULL OR daily_cost_snapshot = 0)"))
        connection.execute(text("UPDATE project_ledger_entries SET amount = COALESCE((SELECT w.cost_amount_snapshot FROM worklogs w WHERE w.id = project_ledger_entries.source_id), amount), occurred_on = COALESCE((SELECT w.start_date FROM worklogs w WHERE w.id = project_ledger_entries.source_id), occurred_on) WHERE entry_type = 'PERSONNEL_COST' AND source_type = 'WORKLOG' AND (amount IS NULL OR amount = 0)"))
        connection.execute(text("INSERT INTO project_ledger_entries (project_id, entry_type, source_type, source_id, amount, occurred_on, idempotency_key, created_at) SELECT w.project_id, 'PERSONNEL_COST', 'WORKLOG', w.id, w.cost_amount_snapshot, w.start_date, 'personnel:' || w.id, datetime('now', '+8 hours') FROM worklogs w WHERE w.status IN ('APPROVED', 'LOCKED') AND w.cost_amount_snapshot IS NOT NULL AND w.cost_amount_snapshot > 0 AND NOT EXISTS (SELECT 1 FROM project_ledger_entries e WHERE e.entry_type = 'PERSONNEL_COST' AND e.source_type = 'WORKLOG' AND e.source_id = w.id)"))
        connection.execute(text("DELETE FROM project_ledger_entries WHERE entry_type = 'PERSONNEL_COST' AND source_type = 'WORKLOG' AND idempotency_key LIKE 'personnel:%' AND EXISTS (SELECT 1 FROM project_ledger_entries e2 WHERE e2.entry_type = 'PERSONNEL_COST' AND e2.source_type = 'WORKLOG' AND e2.source_id = project_ledger_entries.source_id AND e2.idempotency_key <> project_ledger_entries.idempotency_key)"))
        # 统一旧版本中文类型，避免历史项目无法匹配新的动态配置编码。
        connection.execute(text("UPDATE projects SET project_type = 'RND_PROJECT' WHERE project_type IN ('研发项目', '客户项目', '内部项目') OR project_type IS NULL OR project_type = ''"))
        connection.execute(text("UPDATE projects SET budget_cost = 0 WHERE budget_cost IS NULL"))
        connection.execute(text("UPDATE projects SET expense_budget = 0 WHERE expense_budget IS NULL"))
        connection.execute(text("UPDATE payments SET version = 1 WHERE version IS NULL OR version < 1"))
        # 旧项目类型已不再属于当前业务范围，配置记录也直接删除而非仅停用。
        connection.execute(text("DELETE FROM config_options WHERE category = 'project_type' AND (value IN ('研发项目', '客户项目', '内部项目', 'CUSTOMER_PROJECT', 'INTERNAL_PROJECT') OR label IN ('研发项目', '客户项目', '内部项目'))"))


def ensure_user(db: Session, feishu_id: str, open_id: str, name: str, department_id: int, manager_name: str | None = None) -> User:
    """创建或更新演示用户，生产环境由飞书组织同步替换。"""
    user = db.scalar(select(User).where(User.feishu_user_id == feishu_id))
    if not user:
        user = User(feishu_user_id=feishu_id, open_id=open_id, name=name, department_id=department_id, manager_name=manager_name, snapshot_at=now_local())
        db.add(user)
        db.flush()
    else:
        user.open_id = user.open_id or open_id
        user.snapshot_at = now_local()
    return user


def ensure_oauth_user(db: Session, profile: dict[str, object]) -> User:
    """绑定 OAuth 用户；组织尚未同步时创建待补全的本地组织快照。"""
    open_id = str(profile.get("open_id") or "").strip()
    feishu_user_id = str(profile.get("user_id") or "").strip()
    name = str(profile.get("name") or profile.get("en_name") or "").strip()
    email = str(profile.get("email") or "").strip() or None
    stable_id = feishu_user_id or open_id
    if not stable_id or not name:
        raise HTTPException(403, "FEISHU_USER_NOT_SYNCED")

    user = db.scalar(select(User).where(User.open_id == open_id)) if open_id else None
    user = user or db.scalar(select(User).where(User.feishu_user_id == stable_id))
    if user:
        if user.employment_status == "ACTIVE":
            user.open_id = user.open_id or open_id or None
            user.feishu_user_id = user.feishu_user_id or stable_id
            user.name = name
            user.email = email or user.email
            user.snapshot_at = now_local()
        return user

    user = User(
        feishu_user_id=stable_id,
        open_id=open_id or None,
        email=email,
        name=name,
        department_id=None,
        employment_status="ACTIVE",
        snapshot_at=now_local(),
    )
    db.add(user)
    db.flush()
    return user


def demo_seed_enabled() -> bool:
    """Only seed demonstration business data outside production app mode."""
    return feishu.mode != "app" or env_bool("SEED_DEMO_DATA", False)


def repair_legacy_approval_tasks(db: Session, fallback_approver: User | None = None) -> None:
    """Convert legacy worklog states without requiring demonstration users."""
    for item in db.scalars(select(Worklog).where(Worklog.status == "APPROVING")).all():
        item.status = "PENDING_APPROVAL"
    for item in db.scalars(select(Worklog).where(Worklog.status == "PENDING_APPROVAL")).all():
        if db.scalar(select(ApprovalTask.id).where(ApprovalTask.worklog_id == item.id, ApprovalTask.version == max(item.approval_version, 1))):
            continue
        project = db.get(Project, item.project_id)
        approver = db.get(User, item.approver_user_id) if item.approver_user_id else None
        approver = approver or (db.get(User, project.approver_user_id) if project and project.approver_user_id else None) or fallback_approver
        if not approver:
            continue
        item.approver_user_id = approver.id
        item.approver_name_snapshot = approver.name
        item.approval_version = max(item.approval_version, 1)
        item.submitted_at = item.submitted_at or now_local()
        db.add(ApprovalTask(worklog_id=item.id, version=item.approval_version, serial_no=f"WL-{item.submitted_at:%Y%m%d}-{item.id:04d}-V{item.approval_version}", submitter_user_id=item.user_id, approver_user_id=approver.id, status="PENDING", submitted_at=item.submitted_at))


def seed_data() -> None:
    """首次启动写入演示数据，并修复旧 MVP 的审批人和审批状态。"""
    upgrade_schema()
    db = SessionLocal()
    try:
        seed_config_options(db)
        seed_budget_item_templates(db)
        seed_notification_policies(db)
        seed_rbac(db)
        seed_approval_workflows(db)
        ensure_all_project_budget_items(db)
        backfill_ledger_budget_snapshots(db)
        db.flush()
        if not demo_seed_enabled():
            repair_legacy_approval_tasks(db)
            reset_rbac_configuration(db)
            ensure_all_project_budget_items(db)
            backfill_ledger_budget_snapshots(db)
            db.commit()
            return
        demo_departments = {}
        for feishu_id, name, parent_name in [("dept-demo-rd", "研发中心", "产品研发部"), ("dept-demo-pm", "项目管理部", "项目管理部")]:
            department = db.scalar(select(Department).where(Department.feishu_department_id == feishu_id))
            if not department:
                department = Department(feishu_department_id=feishu_id, name=name, parent_name=parent_name, is_active=True)
                db.add(department)
                db.flush()
            demo_departments[name] = department
        user = ensure_user(db, "ou_demo_yangyang", "ou_demo_yangyang", "杨阳", department.id, "樊公海")
        approver_fan = ensure_user(db, "ou_demo_fan", "ou_demo_fan", "樊公海", department.id, "陈总")
        approver_chen = ensure_user(db, "ou_demo_chen", "ou_demo_chen", "陈总", department.id)

        seed_demo_customer = os.getenv("SEED_DEMO_CUSTOMER", "true").lower() in {"1", "true", "yes"}
        demo_customer = db.scalar(select(Customer).where(Customer.code == "CUS-DEMO-001")) if seed_demo_customer else None
        if seed_demo_customer and not demo_customer:
            demo_customer = Customer(code="CUS-DEMO-001", name="示例客户", short_name="示例客户", status="ACTIVE")
            db.add(demo_customer)
            db.flush()

        project_specs = [
            ("PRJ-2026-001", "室内乳胶漆喷涂机器人研发与应用", "杨阳", "樊公海", "研发中心", "ACTIVE", True),
            ("PRJ-2026-004", "建筑物流搬运机器人研发与应用", "李明", "樊公海", "研发中心", "ACTIVE", True),
            ("PRJ-2026-007", "机器人集群智能调度管理系统", "杨阳", "樊公海", "研发中心", "ACTIVE", True),
            ("PRJ-2026-009", "自动化钢筋加工产线", "樊公海", "陈总", "项目管理部", "ACTIVE", True),
            ("PRJ-2025-017", "旧厂区智能改造项目", "王璐", "陈总", "项目管理部", "PAUSED", False),
        ]
        owner_users = {user.name: user, approver_fan.name: approver_fan, approver_chen.name: approver_chen}
        projects: list[Project] = []
        for code, name, owner, approver_name, department_name, status, allow_worklog in project_specs:
            project = db.scalar(select(Project).where(Project.code == code))
            if not project:
                owner_user = owner_users.get(owner)
                department = demo_departments.get(department_name)
                project = Project(code=code, name=name, owner_name=owner, owner_user_id=owner_user.id if owner_user else None, owner_open_id=owner_user.open_id if owner_user else None, approver_name=approver_name, department_id=department.id if department else None, department_name=department.name if department else department_name, status=status, allow_worklog=allow_worklog)
                db.add(project)
            elif not project.department_id:
                department = demo_departments.get(project.department_name or "")
                if department:
                    project.department_id = department.id
                    project.department_name = department.name
            if not project.owner_user_id and project.owner_name in owner_users:
                owner_user = owner_users[project.owner_name]
                project.owner_user_id = owner_user.id
                project.owner_open_id = owner_user.open_id
            if not project.approver_user_id:
                approver = approver_fan if project.approver_name == approver_fan.name else approver_chen
                project.approver_user_id = approver.id
                project.approver_open_id = approver.open_id
                project.approver_name = approver.name
            # 旧演示项目没有保存上级领导，补齐后编辑弹窗可以直接保存。
            if not project.leader_user_id and project.approver_name in {approver_fan.name, approver_chen.name}:
                leader = approver_chen
                project.leader_user_id = leader.id
                project.leader_open_id = leader.open_id
                project.leader_name = leader.name
            if project.code == "PRJ-2026-009" and not project.customer_id and demo_customer:
                project.customer_id = demo_customer.id
                project.customer_name = demo_customer.name
            projects.append(project)
        db.flush()

        if not db.scalar(select(Worklog.id).limit(1)):
            today = today_local()
            demo = [
                (projects[0], 1.0, "开发", "完成接口联调和异常重试日志字段。", "APPROVED"),
                (projects[1], 1.0, "测试", "完成现场设备测试与问题清单整理。", "PENDING_APPROVAL"),
                (projects[2], 0.5, "管理", "组织项目例会并更新风险清单。", "DRAFT"),
            ]
            for project, quantity, stage, description, status in demo:
                item = Worklog(user_id=user.id, user_name_snapshot=user.name, project_id=project.id, project_name_snapshot=project.name, stage=stage, work_type="PROJECT", work_status="LOCAL", start_date=today - timedelta(days=2), end_date=today - timedelta(days=2), quantity=quantity, unit="DAY", description=description, status=status, approved_at=now_local() if status == "APPROVED" else None)
                db.add(item)
            db.flush()

        # 旧版本把逐条明细挂在周期单上，升级时将其拆成独立本地审批任务。
        repair_legacy_approval_tasks(db, approver_fan)
        reset_rbac_configuration(db)
        ensure_all_project_budget_items(db)
        backfill_ledger_budget_snapshots(db)
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    seed_data()
    threading.Thread(target=reminder_scan_loop, daemon=True).start()


def current_user(db: Session, demo_user_id: int | None = None) -> User:
    """返回当前用户；app 模式只使用签名 Session，mock 模式保留演示身份。"""
    if feishu.mode == "app":
        configured_id = session_user_id.get()
    else:
        configured_id = demo_user_id or (int(os.getenv("DEMO_USER_ID", "1")) if os.getenv("DEMO_USER_ID", "1").isdigit() else None)
    user = db.get(User, configured_id) if configured_id else None
    if feishu.mode != "app":
        user = user or db.scalar(select(User).order_by(User.id).limit(1))
    if not user or user.employment_status != "ACTIVE":
        raise HTTPException(401, "AUTH_REQUIRED")
    return user


def system_admin_user_ids(db: Session | None = None) -> set[int]:
    """合并当前库中有效的环境管理员和首次飞书管理员。"""
    raw = os.getenv("SYSTEM_ADMIN_USER_IDS", "1" if feishu.mode == "mock" else "")
    user_ids = {int(value.strip()) for value in raw.split(",") if value.strip().isdigit()}
    if db is not None:
        if user_ids:
            user_ids = set(
                db.scalars(
                    select(User.id).where(
                        User.id.in_(user_ids),
                        User.employment_status == "ACTIVE",
                    )
                ).all()
            )
        marker = db.scalar(
            select(ConfigOption).where(
                ConfigOption.category == "system_internal",
                ConfigOption.value == FIRST_FEISHU_ADMIN_MARKER,
                ConfigOption.is_active.is_(True),
            )
        )
        if marker and marker.label.strip().isdigit():
            marker_user_id = int(marker.label.strip())
            marker_user = db.get(User, marker_user_id)
            if marker_user and marker_user.employment_status == "ACTIVE":
                user_ids.add(marker_user_id)
    return user_ids


def initialize_first_feishu_admin(db: Session, user: User) -> bool:
    """首次无环境管理员时记录飞书登录用户；唯一键保证初始化标记只产生一次。"""
    if system_admin_user_ids(db):
        return False
    marker = db.scalar(
        select(ConfigOption).where(
            ConfigOption.category == "system_internal",
            ConfigOption.value == FIRST_FEISHU_ADMIN_MARKER,
        )
    )
    if marker:
        marker.label = str(user.id)
        marker.is_active = True
        db.flush()
        return True
    try:
        with db.begin_nested():
            db.add(
                ConfigOption(
                    category="system_internal",
                    value=FIRST_FEISHU_ADMIN_MARKER,
                    label=str(user.id),
                    sort_order=0,
                    is_active=True,
                    is_builtin=True,
                )
            )
            db.flush()
    except IntegrityError:
        return False
    return True


def active_rbac_roles(db: Session, user_id: int) -> list[Role]:
    """读取用户当前启用的角色，角色停用后立即失效。"""
    return list(db.scalars(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, UserRole.is_active.is_(True), Role.is_active.is_(True))
        .order_by(Role.name, Role.id)
    ).all())


def effective_permission_details(db: Session, user_id: int) -> dict[str, dict[str, object]]:
    """合并有效角色权限，返回资源操作并集及最高数据范围。"""
    if user_id in system_admin_user_ids(db):
        return {
            code: {"actions": list(actions), "scope_type": "ALL", "scope_department_id": None, "source_roles": ["系统管理员"]}
            for code, _, _, _, _, actions in RBAC_MENU_SEED
        }
    details: dict[str, dict[str, object]] = {}
    roles = active_rbac_roles(db, user_id)
    if roles:
        role_ids = [role.id for role in roles]
        permission_rows = db.scalars(select(RolePermission).where(RolePermission.role_id.in_(role_ids))).all()
        menus = {item.id: item for item in db.scalars(select(Menu).where(Menu.is_active.is_(True))).all()}
        role_names = {role.id: role.name for role in roles}
        for item in permission_rows:
            menu = menus.get(item.menu_id)
            if not menu:
                continue
            target = details.setdefault(menu.code, {"actions": [], "scope_type": None, "scope_department_id": None, "source_roles": []})
            target["actions"] = sorted(set(target["actions"]) | set(_json_list(item.actions)), key=lambda action: RBAC_ACTIONS.index(action) if action in RBAC_ACTIONS else len(RBAC_ACTIONS))
            role_name = role_names.get(item.role_id)
            if role_name and role_name not in target["source_roles"]:
                target["source_roles"].append(role_name)
        scopes = db.scalars(select(RoleDataScope).where(RoleDataScope.role_id.in_(role_ids))).all()
        overrides = {(item.role_id, item.resource): item for item in db.scalars(select(UserRoleScope).where(UserRoleScope.user_id == user_id, UserRoleScope.role_id.in_(role_ids))).all()}
        for scope in scopes:
            if scope.resource not in details:
                continue
            override = overrides.get((scope.role_id, scope.resource))
            scope_type = override.scope_type if override else scope.scope_type
            department_id = override.department_id if override else scope.department_id
            if scope_type == "DEPARTMENT_AND_CHILDREN" and not department_id:
                # 角色默认范围不绑定固定部门，解释为被授权人员所属部门及其下级。
                department_id = db.get(User, user_id).department_id if db.get(User, user_id) else None
            target = details[scope.resource]
            current_type = target.get("scope_type")
            if current_type is None or RBAC_SCOPE_RANK.get(scope_type, 0) > RBAC_SCOPE_RANK.get(str(current_type), 0):
                target["scope_type"] = scope_type
                target["scope_department_id"] = department_id
    return details


def user_admin_permissions(db: Session, user_id: int) -> set[str]:
    """返回具备查看权限的 RBAC 资源集合，供业务兼容逻辑复用。"""
    details = effective_permission_details(db, user_id)
    permissions = {resource for resource, value in details.items() if "VIEW" in value["actions"]}
    if "APPROVE" in details.get("cash_approval", {}).get("actions", []) or any("APPROVE" in details.get(resource, {}).get("actions", []) for resource in ("receipts", "payments")):
        permissions.add("cash_approval")
    return permissions


def require_access(db: Session, resource: str, action: str = "VIEW", demo_user_id: int | None = None) -> User:
    """统一校验资源操作权限；前端隐藏按钮不能替代此服务端校验。"""
    if resource not in {item[0] for item in RBAC_MENU_SEED}:
        raise RuntimeError(f"Unknown permission resource: {resource}")
    user = current_user(db, demo_user_id)
    if action not in effective_permission_details(db, user.id).get(resource, {}).get("actions", []):
        raise HTTPException(403, "PERMISSION_REQUIRED")
    return user


def require_admin_permission(db: Session, permission: str, demo_user_id: int | None = None, action: str = "VIEW") -> User:
    """校验资源操作权限，并兼容旧调用方传入的资源与动作参数。"""
    if ":" in permission:
        permission, action = permission.split(":", 1)
    return require_access(db, permission, action, demo_user_id)


def require_system_admin(db: Session, demo_user_id: int | None = None) -> User:
    """要求具备管理员管理权限。"""
    return require_admin_permission(db, "admins", demo_user_id)


def project_view(db: Session, project: Project) -> ProjectView:
    """返回项目及已审批工时实时汇总，避免审批状态变化造成累计值过期。"""
    actual_days = db.scalar(
        select(func.coalesce(func.sum(Worklog.quantity), 0)).where(
            Worklog.project_id == project.id,
            Worklog.status.in_(("APPROVED", "LOCKED")),
        )
    ) or 0
    personnel_cost = db.scalar(
        select(func.coalesce(func.sum(ProjectLedgerEntry.amount), 0)).where(
            ProjectLedgerEntry.project_id == project.id,
            ProjectLedgerEntry.entry_type == "PERSONNEL_COST",
        )
    ) or 0
    contract_cost = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.project_id == project.id,
            Payment.status == "APPROVED",
        )
    ) or 0
    expense_cost = db.scalar(
        select(func.coalesce(func.sum(ProjectLedgerEntry.amount), 0)).where(
            ProjectLedgerEntry.project_id == project.id,
            ProjectLedgerEntry.entry_type == "PROJECT_EXPENSE_COST",
        )
    ) or 0
    expense_reversal = db.scalar(
        select(func.coalesce(func.sum(ProjectLedgerEntry.amount), 0)).where(
            ProjectLedgerEntry.project_id == project.id,
            ProjectLedgerEntry.entry_type == "REVERSAL",
            ProjectLedgerEntry.source_type == "PROJECT_EXPENSE",
        )
    ) or 0
    ensure_project_budget_items(db, project)
    budget_items = project_budget_item_views(db, project.id)
    budget_days = float(project.budget_days or 0)
    budget_cost = project_budget_total(db, project.id)
    labor_budget = next((float(item.budget_amount or 0) for item in budget_items if item.code == "LABOR_COST"), 0.0)
    expense_budget = round(sum(float(item.budget_amount or 0) for item in budget_items if item.is_active and item.code != "LABOR_COST"), 2)
    actual_days = float(actual_days)
    remaining_days = 0.0
    completion_rate = None
    personnel_cost = round(float(personnel_cost), 2)
    contract_cost = round(float(contract_cost), 2)
    expense_cost = round(max(float(expense_cost) - float(expense_reversal), 0), 2)
    actual_cost = round(personnel_cost + contract_cost + expense_cost, 2)
    remaining_cost = round(budget_cost - actual_cost, 2)
    personnel_budget_cost = labor_budget if labor_budget > 0 else None
    personnel_cost_usage_rate = (
        round(personnel_cost / personnel_budget_cost * 100, 1)
        if personnel_budget_cost and personnel_budget_cost > 0
        else None
    )
    cost_usage_rate = round(actual_cost / budget_cost * 100, 1) if budget_cost > 0 else None
    non_labor_actual = round(contract_cost + expense_cost, 2)
    expense_budget_remaining = round(expense_budget - non_labor_actual, 2)
    expense_budget_usage_rate = round(non_labor_actual / expense_budget * 100, 1) if expense_budget > 0 else None
    if budget_cost <= 0:
        cost_execution_status = "NO_BUDGET"
    elif actual_cost > budget_cost:
        cost_execution_status = "OVER_BUDGET"
    elif actual_cost / budget_cost >= 0.8:
        cost_execution_status = "NEAR_BUDGET"
    else:
        cost_execution_status = "IN_PROGRESS"
    if actual_days <= 0:
        execution_status = "NOT_STARTED"
    elif budget_days > 0 and actual_days > budget_days:
        execution_status = "OVER_BUDGET"
    elif budget_days > 0 and actual_days / budget_days >= 0.8:
        execution_status = "NEAR_BUDGET"
    else:
        execution_status = "IN_PROGRESS"
    payload = ProjectView.model_validate(project).model_dump()
    department_index = DepartmentIndex(db.scalars(select(Department)).all())
    customer = db.get(Customer, project.customer_id) if project.customer_id else None
    payload.update(
        department_path=department_index.path(project.department_id),
        customer_name=customer.name if customer else project.customer_name,
        budget_days=budget_days,
        budget_cost=budget_cost,
        expense_budget=expense_budget,
        actual_days=actual_days,
        completion_rate=completion_rate,
        remaining_days=remaining_days,
        actual_cost=actual_cost,
        personnel_cost=personnel_cost,
        actual_contract_cost=contract_cost,
        actual_expense_cost=expense_cost,
        remaining_cost=remaining_cost,
        personnel_cost_usage_rate=personnel_cost_usage_rate,
        cost_usage_rate=cost_usage_rate,
        cost_execution_status=cost_execution_status,
        expense_budget_remaining=expense_budget_remaining,
        expense_budget_usage_rate=expense_budget_usage_rate,
        execution_status=execution_status,
    )
    return ProjectView(**payload)


def project_scope_ids(db: Session, user: User, resource: str = "projects") -> set[int] | None:
    """返回指定资源的数据范围项目 ID；None 表示全部项目。"""
    if user.id in system_admin_user_ids(db):
        return None
    scope = effective_permission_details(db, user.id).get(resource) or effective_permission_details(db, user.id).get("projects")
    scope_type = str(scope.get("scope_type")) if scope else "OWNED_PROJECTS"
    if scope_type == "ALL":
        return None
    if scope_type in {"SELF", "OWNED_PROJECTS"}:
        return {project.id for project in db.scalars(select(Project).where(Project.owner_user_id == user.id, Project.status != "DELETED")).all()}
    department_id = scope.get("scope_department_id") if scope else None
    if department_id:
        index = DepartmentIndex(db.scalars(select(Department)).all())
        department_ids = index.descendants(int(department_id))
        return {project.id for project in db.scalars(select(Project).where(Project.department_id.in_(department_ids), Project.status != "DELETED")).all()}
    return set()


def contract_view(db: Session, contract: Contract) -> ContractView:
    project = db.get(Project, contract.project_id)
    stages = db.scalars(
        select(ContractStage)
        .where(ContractStage.contract_id == contract.id, ContractStage.status != "CANCELLED")
        .order_by(ContractStage.planned_date, ContractStage.sort_order, ContractStage.id)
    ).all()
    stage_count = len(stages)
    if contract.contract_type == "INCOME":
        settled_query = select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.contract_id == contract.id, Receipt.status == "APPROVED")
        document_count_query = select(func.count()).select_from(Receipt).where(Receipt.contract_id == contract.id, Receipt.status == "APPROVED")
    else:
        settled_query = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.contract_id == contract.id, Payment.status == "APPROVED")
        document_count_query = select(func.count()).select_from(Payment).where(Payment.contract_id == contract.id, Payment.status == "APPROVED")
    settled = float(db.scalar(settled_query) or 0)
    settled_document_count = int(db.scalar(document_count_query) or 0)
    contract_amount = float(contract.amount or 0)
    next_stage_date = next(
        (stage.planned_date for stage in stages if stage.planned_date and stage.status not in {"DONE", "CANCELLED"}),
        None,
    )
    counterparty = (
        db.get(Customer, contract.counterparty_id)
        if contract.counterparty_type == "CUSTOMER"
        else db.get(Supplier, contract.counterparty_id)
    )
    counterparty_name = counterparty.name if counterparty else contract.counterparty_name
    return ContractView(
        id=contract.id,
        contract_no=contract.contract_no,
        name=contract.name,
        project_id=contract.project_id,
        project_name=project.name if project else "",
        contract_type=contract.contract_type,
        counterparty_type=contract.counterparty_type,
        counterparty_id=contract.counterparty_id,
        counterparty_name=counterparty_name,
        amount=contract_amount,
        budget_item_id=contract.budget_item_id,
        budget_item_name=contract.budget_item_name_snapshot,
        cost_major=contract.cost_major_snapshot,
        cost_minor=contract.cost_minor_snapshot,
        sign_date=contract.sign_date,
        start_date=contract.start_date,
        end_date=contract.end_date,
        status=contract.status,
        description=contract.description,
        stage_count=stage_count,
        settled_amount=round(settled, 2),
        remaining_amount=round(max(contract_amount - settled, 0), 2),
        settlement_rate=round(settled / contract_amount * 100, 1) if contract_amount > 0 else None,
        settled_document_count=settled_document_count,
        next_stage_date=next_stage_date,
    )


CONTRACT_ATTACHMENT_MAX_BYTES = int(os.getenv("CONTRACT_ATTACHMENT_MAX_BYTES", str(50 * 1024 * 1024)))
CONTRACT_ATTACHMENT_EXTENSIONS = {
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def contract_attachment_root() -> Path:
    """返回合同附件持久化目录，并确保目录存在。"""
    root = Path(os.getenv("CONTRACT_ATTACHMENT_DIR", "/app/data/contract-attachments"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def cash_attachment_root() -> Path:
    """返回收付款附件持久化目录，并确保目录存在。"""
    root = Path(os.getenv("CASH_ATTACHMENT_DIR", "/app/data/cash-attachments"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def expense_attachment_root() -> Path:
    """返回项目费用附件持久化目录，并确保目录存在。"""
    root = Path(os.getenv("PROJECT_EXPENSE_ATTACHMENT_DIR", "/app/data/project-expense-attachments"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def contract_attachment_path(attachment: ContractAttachment) -> Path:
    """解析附件存储路径并阻止存储名越界。"""
    root = contract_attachment_root().resolve()
    path = (root / attachment.storage_name).resolve()
    if path.parent != root:
        raise HTTPException(500, "CONTRACT_ATTACHMENT_STORAGE_INVALID")
    return path


def cash_attachment_path(attachment: CashDocumentAttachment) -> Path:
    """解析收付款附件路径并阻止存储名越界。"""
    root = cash_attachment_root().resolve()
    path = (root / attachment.storage_name).resolve()
    if path.parent != root:
        raise HTTPException(500, "CASH_ATTACHMENT_STORAGE_INVALID")
    return path


def expense_attachment_path(attachment: ProjectExpenseAttachment) -> Path:
    """解析项目费用附件路径并阻止随机存储名越界。"""
    root = expense_attachment_root().resolve()
    path = (root / attachment.storage_name).resolve()
    if path.parent != root:
        raise HTTPException(500, "EXPENSE_ATTACHMENT_STORAGE_INVALID")
    return path


def attachment_preview_kind(file_name: str) -> str:
    """根据扩展名返回前端预览类型；Office 新旧格式均进入预览流程。"""
    suffix = Path(file_name).suffix.lower()
    if suffix in {".doc", ".docx"}:
        return "word"
    if suffix in {".xls", ".xlsx"}:
        return "excel"
    if suffix in {".ppt", ".pptx"}:
        return "powerpoint"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    return "download"


def contract_attachment_view(db: Session, attachment: ContractAttachment) -> ContractAttachmentView:
    """将附件实体转换为不暴露服务器路径的响应模型。"""
    uploader = db.get(User, attachment.uploaded_by)
    kind = attachment_preview_kind(attachment.file_name)
    return ContractAttachmentView(
        id=attachment.id,
        contract_id=attachment.contract_id,
        file_name=attachment.file_name,
        mime_type=attachment.mime_type,
        file_size=attachment.file_size,
        uploaded_by=attachment.uploaded_by,
        uploaded_by_name=uploader.name if uploader else "系统",
        created_at=attachment.created_at,
        can_preview=kind != "download",
        preview_kind=kind,
    )


def cash_attachment_view(db: Session, attachment: CashDocumentAttachment) -> CashDocumentAttachmentView:
    """将收付款附件实体转换为不暴露服务器路径的响应模型。"""
    uploader = db.get(User, attachment.uploaded_by)
    kind = attachment_preview_kind(attachment.file_name)
    return CashDocumentAttachmentView(
        document_type=attachment.document_type,
        document_id=attachment.document_id,
        id=attachment.id,
        file_name=attachment.file_name,
        mime_type=attachment.mime_type,
        file_size=attachment.file_size,
        uploaded_by=attachment.uploaded_by,
        uploaded_by_name=uploader.name if uploader else "系统",
        created_at=attachment.created_at,
        can_preview=kind != "download",
        preview_kind=kind,
    )


def expense_attachment_view(db: Session, attachment: ProjectExpenseAttachment) -> ProjectExpenseAttachmentView:
    """将费用附件实体转换为安全的前端响应。"""
    uploader = db.get(User, attachment.uploaded_by)
    kind = attachment_preview_kind(attachment.file_name)
    return ProjectExpenseAttachmentView(
        id=attachment.id,
        expense_id=attachment.expense_id,
        file_name=attachment.file_name,
        mime_type=attachment.mime_type,
        file_size=attachment.file_size,
        uploaded_by=attachment.uploaded_by,
        uploaded_by_name=uploader.name if uploader else "系统",
        created_at=attachment.created_at,
        can_preview=kind != "download",
        preview_kind=kind,
    )


def resolve_contract_attachment(db: Session, attachment_id: int) -> ContractAttachment:
    """读取附件实体，不存在时返回统一错误。"""
    attachment = db.get(ContractAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "CONTRACT_ATTACHMENT_NOT_FOUND")
    return attachment


def ensure_contract_attachment_access(db: Session, attachment: ContractAttachment, demo_user_id: int | None) -> tuple[User, Contract]:
    """校验合同管理权限及项目范围，返回当前用户和所属合同。"""
    user = require_admin_permission(db, "contracts", demo_user_id)
    contract = resolve_contract(db, attachment.contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    return user, contract


def resolve_cash_attachment(db: Session, attachment_id: int) -> CashDocumentAttachment:
    """读取收付款附件实体，不存在时返回统一错误。"""
    attachment = db.get(CashDocumentAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "CASH_ATTACHMENT_NOT_FOUND")
    if attachment.document_type not in {"RECEIPT", "PAYMENT"}:
        raise HTTPException(500, "CASH_ATTACHMENT_DOCUMENT_TYPE_INVALID")
    return attachment


def ensure_cash_attachment_access(
    db: Session,
    attachment: CashDocumentAttachment,
    demo_user_id: int | None,
    write: bool = False,
) -> tuple[User, Receipt | Payment]:
    """校验收付款附件读写权限及项目范围，审批人只读。"""
    if attachment.document_type == "RECEIPT":
        document = db.get(Receipt, attachment.document_id)
        permission = "receipts"
    else:
        document = db.get(Payment, attachment.document_id)
        permission = "payments"
    if not document:
        raise HTTPException(404, "CASH_DOCUMENT_NOT_FOUND")
    if write:
        user = require_admin_permission(db, permission, demo_user_id)
    else:
        user = current_user(db, demo_user_id)
        if attachment.document_type == "PAYMENT" and payment_workflow_assigned(db, document, user.id):
            return user, document
        permissions = user_admin_permissions(db, user.id)
        if permission not in permissions and "cash_approval" not in permissions:
            raise HTTPException(403, "ADMIN_PERMISSION_REQUIRED")
    ensure_project_in_scope(db, user, document.project_id)
    return user, document


def _zip_entry_bytes(archive: zipfile.ZipFile, name: str, max_bytes: int = 12 * 1024 * 1024) -> bytes:
    """读取受限的 Office XML 条目，避免预览阶段无界读取压缩包。"""
    info = archive.getinfo(name)
    if info.file_size > max_bytes:
        raise ValueError("office xml entry is too large")
    return archive.read(name)


IMPORT_MAX_BYTES = 5 * 1024 * 1024
IMPORT_MAX_ROWS = 5000
IMPORT_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "customers": ("客户名称",),
    "suppliers": ("供应商名称",),
    "contracts": ("合同编号", "合同名称", "项目名称", "合同类型", "往来单位名称", "合同金额"),
}


def _normalize_import_header(value: str) -> str:
    """统一模板表头格式，兼容必填标记和 CSV BOM。"""
    return value.strip().lstrip("\ufeff").rstrip("*").strip()


def _excel_column_index(reference: str) -> int | None:
    match = re.match(r"([A-Za-z]+)", reference)
    if not match:
        return None
    index = 0
    for character in match.group(1).upper():
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def _read_import_xlsx(content: bytes) -> list[tuple[int, list[str]]]:
    """读取简单 XLSX 第一工作表，保留稀疏单元格的列位置。"""
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared_root = ET.fromstring(_zip_entry_bytes(archive, "xl/sharedStrings.xml"))
                shared = [_xml_text(item, namespace) for item in shared_root.findall(f".//{{{namespace}}}si")]
            sheet_names = sorted(
                (name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)),
                key=lambda name: int(re.search(r"sheet(\d+)", name).group(1)),
            )
            if not sheet_names:
                raise ValueError("IMPORT_SHEET_MISSING")
            root = ET.fromstring(_zip_entry_bytes(archive, sheet_names[0]))
            result: list[tuple[int, list[str]]] = []
            for row in root.findall(f".//{{{namespace}}}row")[:IMPORT_MAX_ROWS + 1]:
                row_number = int(row.attrib.get("r", len(result) + 1))
                values: dict[int, str] = {}
                for cell in row.findall(f"./{{{namespace}}}c"):
                    column_index = _excel_column_index(cell.attrib.get("r", ""))
                    if column_index is None:
                        continue
                    value_node = cell.find(f"./{{{namespace}}}v")
                    inline_node = cell.find(f".//{{{namespace}}}t")
                    value = inline_node.text if inline_node is not None else (value_node.text if value_node is not None else "")
                    if cell.attrib.get("t") == "s" and value and value.isdigit() and int(value) < len(shared):
                        value = shared[int(value)]
                    values[column_index] = value or ""
                width = max(values.keys(), default=-1) + 1
                result.append((row_number, [values.get(index, "") for index in range(width)]))
            return result
    except (ET.ParseError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise HTTPException(422, "导入文件不是有效的 Excel 模板") from exc


async def _read_import_file(file: UploadFile) -> tuple[str, list[tuple[int, list[str]]]]:
    """读取导入文件并限制格式、大小和行数。"""
    filename = (file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    content = await file.read(IMPORT_MAX_BYTES + 1)
    if len(content) > IMPORT_MAX_BYTES:
        raise HTTPException(413, "导入文件不能超过 5MB")
    if suffix == ".xlsx":
        rows = _read_import_xlsx(content)
    elif suffix == ".csv":
        decoded = None
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                decoded = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise HTTPException(422, "CSV 文件编码无法识别，请使用 UTF-8 或 GB18030")
        rows = [(index, row) for index, row in enumerate(csv.reader(io.StringIO(decoded)), start=1)]
    else:
        raise HTTPException(415, "仅支持 .xlsx 或 .csv 文件")
    if len(rows) > IMPORT_MAX_ROWS + 1:
        raise HTTPException(422, "导入文件最多支持 5000 条数据")
    return filename or "未命名导入文件", rows


def _import_records(resource: str, rows: list[tuple[int, list[str]]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """按模板表头生成记录；空白行跳过并返回可定位的表头错误。"""
    required_fields = IMPORT_REQUIRED_FIELDS[resource]
    errors: list[dict[str, object]] = []
    if not rows:
        return [], [{"row": 1, "field": "文件", "message": "文件没有内容"}]
    headers = [_normalize_import_header(value) for value in rows[0][1]]
    positions: dict[str, int] = {}
    for index, header in enumerate(headers):
        if header and header not in positions:
            positions[header] = index
    for field in required_fields:
        if field not in positions:
            errors.append({"row": rows[0][0], "field": field, "message": "缺少此列"})
    if len(positions) != len([header for header in headers if header]):
        errors.append({"row": rows[0][0], "field": "表头", "message": "表头存在重复列，请保留每个字段一列"})
    records: list[dict[str, object]] = []
    for row_number, values in rows[1:]:
        padded = values + [""] * max(0, len(headers) - len(values))
        if not any(str(value).strip() for value in padded):
            continue
        record: dict[str, object] = {"row": row_number}
        for field, position in positions.items():
            record[field] = str(padded[position]).strip() if position < len(padded) else ""
        records.append(record)
    if not records and not errors:
        errors.append({"row": rows[0][0], "field": "数据", "message": "没有可导入的数据行"})
    return records, errors


def _import_preview(resource: str, filename: str, records: list[dict[str, object]], errors: list[dict[str, object]]) -> dict[str, object]:
    """组装统一导入预览结构，供前端展示。"""
    error_rows = {int(item["row"]) for item in errors if str(item.get("row", "")).isdigit()}
    return {
        "resource": resource,
        "filename": filename,
        "total_rows": len(records),
        "valid_rows": sum(1 for item in records if int(item["row"]) not in error_rows),
        "errors": errors,
        "preview": records[:10],
    }


def generate_counterparty_code(db: Session, model: type[Customer] | type[Supplier], prefix: str) -> str:
    """按日期流水生成客户或供应商编码。"""
    date_part = today_local().strftime("%Y%m%d")
    pattern = re.compile(rf"^{re.escape(prefix)}-{date_part}-(\d{{4,}})$")
    existing_codes = db.scalars(select(model.code).where(model.code.like(f"{prefix}-{date_part}-%"))).all()
    max_sequence = 0
    for code in existing_codes:
        match = pattern.match(code or "")
        if match:
            max_sequence = max(max_sequence, int(match.group(1)))
    sequence = max_sequence + 1
    while True:
        candidate = f"{prefix}-{date_part}-{sequence:04d}"
        if not db.scalar(select(model.id).where(model.code == candidate)):
            return candidate
        sequence += 1


def _validate_counterparty_import(db: Session, resource: str, records: list[dict[str, object]], errors: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """校验客户或供应商导入数据，返回 ORM 写入字段和可读错误。"""
    model = Customer if resource == "customers" else Supplier
    name_field = "客户名称" if resource == "customers" else "供应商名称"
    bank_field = "付款银行" if resource == "customers" else "收款银行"
    account_field = "付款账号" if resource == "customers" else "收款账号"
    existing = db.scalars(select(model)).all()
    names = {item.name for item in existing}
    seen_names: set[str] = set()
    payloads: list[dict[str, object]] = []
    error_rows = {int(item["row"]) for item in errors if str(item.get("row", "")).isdigit()}
    for record in records:
        row = int(record["row"])
        name = str(record.get(name_field, "")).strip()
        row_has_error = False
        if not name:
            errors.append({"row": row, "field": name_field, "message": "不能为空"})
            row_has_error = True
        elif name in names or name in seen_names:
            errors.append({"row": row, "field": name_field, "message": "名称已存在"})
            row_has_error = True
        if not row_has_error:
            seen_names.add(name)
            payloads.append({"name": name, "bank_name": str(record.get(bank_field, "")).strip() or None, "bank_account": str(record.get(account_field, "")).strip() or None, "status": "ACTIVE"})
        error_rows.add(row) if row_has_error else None
    return payloads, errors


def _validate_contract_import(db: Session, user: User, records: list[dict[str, object]], errors: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """校验合同核心字段、项目范围和收入/支出往来单位匹配关系。"""
    project_ids = project_scope_ids(db, user, "contracts")
    projects: dict[str, list[Project]] = defaultdict(list)
    for item in db.scalars(select(Project).where(Project.status != "DELETED")).all():
        if project_ids is None or item.id in project_ids:
            projects[item.name].append(item)
    customers = {item.name: item for item in db.scalars(select(Customer).where(Customer.status == "ACTIVE")).all()}
    suppliers = {item.name: item for item in db.scalars(select(Supplier).where(Supplier.status == "ACTIVE")).all()}
    contract_type_values = {
        "收入合同": "INCOME",
        "支出合同": "EXPENSE",
    }
    contract_numbers = {item.contract_no for item in db.scalars(select(Contract)).all()}
    seen_numbers: set[str] = set()
    payloads: list[dict[str, object]] = []
    for record in records:
        row = int(record["row"])
        values = {field: str(record.get(field, "")).strip() for field in IMPORT_REQUIRED_FIELDS["contracts"]}
        row_has_error = False
        for field in IMPORT_REQUIRED_FIELDS["contracts"]:
            if not values[field]:
                errors.append({"row": row, "field": field, "message": "不能为空"})
                row_has_error = True
        contract_type = contract_type_values.get(values["合同类型"])
        if values["合同类型"] and not contract_type:
            errors.append({"row": row, "field": "合同类型", "message": "请选择收入合同或支出合同"})
            row_has_error = True
        matching_projects = projects.get(values["项目名称"], [])
        if values["项目名称"] and not matching_projects:
            errors.append({"row": row, "field": "项目名称", "message": "未找到匹配的项目名称或项目不在当前数据范围，请修正后重新导入"})
            row_has_error = True
        elif len(matching_projects) > 1:
            errors.append({"row": row, "field": "项目名称", "message": "匹配到多个同名项目，请先保证项目名称唯一后重新导入"})
            row_has_error = True
        if values["合同编号"] and (values["合同编号"] in contract_numbers or values["合同编号"] in seen_numbers):
            errors.append({"row": row, "field": "合同编号", "message": "合同编号已存在"})
            row_has_error = True
        counterparty = None
        if contract_type in {"INCOME", "EXPENSE"}:
            expected = "客户" if contract_type == "INCOME" else "供应商"
            counterparty = customers.get(values["往来单位名称"]) if contract_type == "INCOME" else suppliers.get(values["往来单位名称"])
            if values["往来单位名称"] and not counterparty:
                errors.append({"row": row, "field": "往来单位名称", "message": f"未找到名称为“{values['往来单位名称']}”的启用{expected}"})
                row_has_error = True
        try:
            amount = float(values["合同金额"])
            if not math.isfinite(amount) or amount < 0:
                raise ValueError
        except ValueError:
            if values["合同金额"]:
                errors.append({"row": row, "field": "合同金额", "message": "必须是大于等于 0 的数字"})
            row_has_error = True
            amount = 0
        if not row_has_error:
            project = matching_projects[0]
            seen_numbers.add(values["合同编号"])
            payloads.append({
                "contract_no": values["合同编号"],
                "name": values["合同名称"],
                "project_id": project.id,
                "contract_type": contract_type,
                "counterparty_type": "CUSTOMER" if contract_type == "INCOME" else "SUPPLIER",
                "counterparty_id": counterparty.id,
                "counterparty_name": counterparty.name,
                "amount": amount,
                "status": "DRAFT",
            })
    return payloads, errors


async def _prepare_import(resource: str, file: UploadFile, db: Session, user: User) -> tuple[dict[str, object], list[dict[str, object]]]:
    """读取并校验导入文件，返回预览和可直接写入的字段。"""
    filename, rows = await _read_import_file(file)
    records, errors = _import_records(resource, rows)
    if resource in {"customers", "suppliers"}:
        payloads, errors = _validate_counterparty_import(db, resource, records, errors)
    else:
        payloads, errors = _validate_contract_import(db, user, records, errors)
    return _import_preview(resource, filename, records, errors), payloads


def _xml_text(node: ET.Element, namespace: str = "http://schemas.openxmlformats.org/wordprocessingml/2006/main") -> str:
    """提取 XML 节点内的纯文本，不保留 Office 标记。"""
    return "".join(item.text or "" for item in node.iter(f"{{{namespace}}}t"))


def _office_html_shell(title: str, content: str) -> str:
    """生成无脚本的附件预览页面。"""
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_escape(title)}</title><style>
body{{margin:0;background:#f5f8f7;color:#263b39;font:14px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}}
main{{max-width:1080px;margin:32px auto;padding:0 24px}}h1{{font-size:22px;margin:0 0 24px}}h2{{font-size:16px;margin:26px 0 10px}}.paper{{background:#fff;border:1px solid #dce8e5;border-radius:8px;padding:24px;box-shadow:0 3px 14px rgba(28,69,62,.06)}}
p{{margin:0 0 12px;white-space:pre-wrap}}table{{width:100%;border-collapse:collapse;margin:14px 0;font-size:13px}}td,th{{border:1px solid #d8e4e1;padding:7px 9px;text-align:left;vertical-align:top}}th{{background:#f0f7f5;font-weight:650}}.slide{{border:1px solid #d8e4e1;margin:0 0 20px;padding:20px;min-height:120px;background:#fff}}.slide-label{{color:#6b7f7b;font-size:12px;margin-bottom:10px}}
.notice{{padding:14px 16px;background:#fff8eb;border:1px solid #f1d39b;border-radius:6px}}
</style></head><body><main><h1>{html_escape(title)}</h1><div class="paper">{content}</div></main></body></html>"""


def _preview_docx(path: Path) -> str:
    """将 DOCX 的段落和表格转换为只读 HTML。"""
    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(_zip_entry_bytes(archive, "word/document.xml"))
    body = root.find(f".//{{{namespace}}}body")
    if body is None:
        return '<p class="notice">文档没有可预览的正文内容。</p>'
    blocks: list[str] = []
    for child in list(body):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name == "p":
            text = _xml_text(child, namespace).strip()
            if text:
                blocks.append(f"<p>{html_escape(text)}</p>")
        elif local_name == "tbl":
            rows: list[str] = []
            for row in child.findall(f".//{{{namespace}}}tr")[:200]:
                cells = [html_escape(_xml_text(cell, namespace).strip()) for cell in row.findall(f"./{{{namespace}}}tc")[:50]]
                if cells:
                    rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
            if rows:
                blocks.append("<table><tbody>" + "".join(rows) + "</tbody></table>")
    return "".join(blocks) or '<p class="notice">文档没有可预览的正文内容。</p>'


def _preview_xlsx(path: Path) -> str:
    """将 XLSX 工作表中的已保存单元格值转换为只读 HTML。"""
    main_namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(_zip_entry_bytes(archive, "xl/sharedStrings.xml"))
            for item in shared_root.findall(f".//{{{main_namespace}}}si"):
                shared.append(_xml_text(item, main_namespace))
        sheet_names = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)),
            key=lambda name: int(re.search(r"sheet(\d+)", name).group(1)),
        )
        blocks: list[str] = []
        for index, sheet_name in enumerate(sheet_names[:20], start=1):
            root = ET.fromstring(_zip_entry_bytes(archive, sheet_name))
            rows: list[str] = []
            for row in root.findall(f".//{{{main_namespace}}}row")[:200]:
                cells: list[str] = []
                for cell in row.findall(f"./{{{main_namespace}}}c")[:50]:
                    value = cell.find(f"./{{{main_namespace}}}v")
                    inline = cell.find(f".//{{{main_namespace}}}t")
                    text = inline.text if inline is not None else (value.text if value is not None else "")
                    if cell.attrib.get("t") == "s" and text and text.isdigit() and int(text) < len(shared):
                        text = shared[int(text)]
                    cells.append(f'<td>{html_escape(text or "")}</td>')
                if cells:
                    rows.append("<tr>" + "".join(cells) + "</tr>")
            if rows:
                table_html = "".join(rows)
                blocks.append(f"<h2>工作表 {index}</h2><table><tbody>{table_html}</tbody></table>")
        return "".join(blocks) or '<p class="notice">工作簿没有可预览的单元格内容。</p>'


def _preview_pptx(path: Path) -> str:
    """将 PPTX 每页的文本内容转换为只读 HTML。"""
    namespace = "http://schemas.openxmlformats.org/drawingml/2006/main"
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"slide(\d+)", name).group(1)),
        )
        blocks: list[str] = []
        for index, slide_name in enumerate(slide_names[:100], start=1):
            root = ET.fromstring(_zip_entry_bytes(archive, slide_name))
            texts = [html_escape((node.text or "").strip()) for node in root.iter(f"{{{namespace}}}t") if (node.text or "").strip()]
            body = "<p>" + "<br>".join(texts) + "</p>" if texts else '<p class="notice">此页没有可预览的文字。</p>'
            blocks.append(f'<section class="slide"><div class="slide-label">第 {index} 页</div>{body}</section>')
        return "".join(blocks) or '<p class="notice">演示文稿没有可预览的页面。</p>'


def _convert_office_to_pdf(path: Path) -> tuple[Path, str]:
    """用隔离的无界面 LibreOffice 配置将 Office 文件转为 PDF。"""
    executable = os.getenv("LIBREOFFICE_BIN") or shutil.which("soffice") or shutil.which("libreoffice")
    if not executable:
        raise RuntimeError("LIBREOFFICE_NOT_INSTALLED")
    output_dir = Path(tempfile.mkdtemp(prefix="contract-preview-"))
    profile_dir = output_dir / "profile"
    profile_dir.mkdir()
    try:
        result = subprocess.run(
            [
                executable,
                "--headless",
                "--safe-mode",
                "--norestore",
                "--nofirststartwizard",
                "--nodefault",
                "--nolockcheck",
                f"-env:UserInstallation={profile_dir.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        pdf_path = output_dir / f"{path.stem}.pdf"
        if result.returncode != 0 or not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            raise RuntimeError("LIBREOFFICE_CONVERSION_FAILED")
        return pdf_path, str(output_dir)
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise


def render_contract_office_preview(attachment: ContractAttachment, path: Path) -> str:
    """按 Office 扩展名生成安全 HTML，不解析宏、嵌入对象或外链。"""
    suffix = Path(attachment.file_name).suffix.lower()
    if suffix == ".docx":
        content = _preview_docx(path)
    elif suffix == ".xlsx":
        content = _preview_xlsx(path)
    elif suffix == ".pptx":
        content = _preview_pptx(path)
    else:
        content = '<p class="notice">该文件为旧版 Office 格式，系统提供下载，不执行在线预览。</p>'
    return _office_html_shell(attachment.file_name, content)


def contract_stage_view(db: Session, stage: ContractStage) -> ContractStageView:
    contract = db.get(Contract, stage.contract_id)
    contract_type = contract.contract_type if contract else "INCOME"
    if contract_type == "INCOME":
        settled_query = select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.stage_id == stage.id, Receipt.status == "APPROVED")
        document_count_query = select(func.count()).select_from(Receipt).where(Receipt.stage_id == stage.id, Receipt.status == "APPROVED")
    else:
        settled_query = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.stage_id == stage.id, Payment.status == "APPROVED")
        document_count_query = select(func.count()).select_from(Payment).where(Payment.stage_id == stage.id, Payment.status == "APPROVED")
    settled = float(db.scalar(settled_query) or 0)
    settled_document_count = int(db.scalar(document_count_query) or 0)
    stage_amount = float(stage.amount or 0)
    payload = ContractStageView.model_validate(stage).model_dump()
    payload.update(
        settled_amount=round(settled, 2),
        remaining_amount=round(max(stage_amount - settled, 0), 2),
        settlement_rate=round(settled / stage_amount * 100, 1) if stage_amount > 0 else None,
        settled_document_count=settled_document_count,
    )
    return ContractStageView(**payload)


def approval_timeline(db: Session, object_type: str, object_id: int) -> list[ApprovalTimelineEvent]:
    """将收付款审计事件转换为详情页可读的审批时间线。"""
    labels = {
        "SUBMIT": "提交审批",
        "UPDATE": "修改单据",
        "APPROVE": "审批通过",
        "REJECT": "审批驳回",
        "REVERSE": "单据冲销",
        "DELETE": "删除单据",
    }
    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.object_type == object_type, AuditLog.object_id == object_id)
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    ).all()
    actor_ids = {item.actor_user_id for item in logs if item.actor_user_id}
    actors = {item.id: item.name for item in db.scalars(select(User).where(User.id.in_(actor_ids))).all()} if actor_ids else {}
    return [
        ApprovalTimelineEvent(
            event=labels.get(item.action, item.action),
            actor_name=actors.get(item.actor_user_id, "系统") if item.actor_user_id else "系统",
            status=item.new_status,
            comment=item.comment,
            occurred_at=item.created_at,
        )
        for item in logs
    ]


def receipt_view(db: Session, receipt: Receipt) -> ReceiptView:
    project = db.get(Project, receipt.project_id)
    contract = db.get(Contract, receipt.contract_id)
    stage = db.get(ContractStage, receipt.stage_id) if receipt.stage_id else None
    submitted_by = db.get(User, receipt.submitted_by) if receipt.submitted_by else None
    approved_by = db.get(User, receipt.approved_by) if receipt.approved_by else None
    stage_amount = float(stage.amount or 0) if stage else None
    stage_settled = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.stage_id == receipt.stage_id, Receipt.status == "APPROVED")) or 0) if stage else None
    counterparty = db.get(Customer, contract.counterparty_id) if contract and contract.counterparty_type == "CUSTOMER" else None
    return ReceiptView(
        id=receipt.id,
        receipt_no=receipt.receipt_no,
        project_id=receipt.project_id,
        project_name=project.name if project else "",
        contract_id=receipt.contract_id,
        contract_name=contract.name if contract else "",
        contract_no=contract.contract_no if contract else None,
        counterparty_name=counterparty.name if counterparty else (contract.counterparty_name if contract else None),
        stage_id=receipt.stage_id,
        stage_name=stage.name if stage else None,
        amount=float(receipt.amount or 0),
        receipt_date=receipt.receipt_date,
        payer_name=receipt.payer_name,
        payer_bank_name=receipt.payer_bank_name,
        payer_bank_account=receipt.payer_bank_account,
        status=receipt.status,
        submitted_by=receipt.submitted_by,
        submitted_at=receipt.submitted_at,
        approved_by=receipt.approved_by,
        approved_at=receipt.approved_at,
        comment=receipt.comment,
        submitted_by_name=submitted_by.name if submitted_by else None,
        approved_by_name=approved_by.name if approved_by else None,
        stage_planned_amount=stage_amount,
        stage_settled_amount=round(stage_settled, 2) if stage_settled is not None else None,
        stage_remaining_amount=round(max(stage_amount - stage_settled, 0), 2) if stage_amount is not None and stage_settled is not None else None,
        stage_settlement_rate=round(stage_settled / stage_amount * 100, 1) if stage_amount and stage_settled is not None else None,
        approval_timeline=approval_timeline(db, "receipt", receipt.id),
    )


def payment_view(db: Session, payment: Payment, viewer_id: int | None = None) -> PaymentView:
    project = db.get(Project, payment.project_id)
    contract = db.get(Contract, payment.contract_id)
    stage = db.get(ContractStage, payment.stage_id) if payment.stage_id else None
    submitted_by = db.get(User, payment.submitted_by) if payment.submitted_by else None
    approved_by = db.get(User, payment.approved_by) if payment.approved_by else None
    stage_amount = float(stage.amount or 0) if stage else None
    stage_settled = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.stage_id == payment.stage_id, Payment.status == "APPROVED")) or 0) if stage else None
    counterparty = db.get(Supplier, contract.counterparty_id) if contract and contract.counterparty_type == "SUPPLIER" else None
    instance = db.get(WorkflowInstance, payment.current_workflow_instance_id) if payment.current_workflow_instance_id else None
    current_task = db.scalar(select(WorkflowTask).where(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.status == "PENDING").order_by(WorkflowTask.node_sequence).limit(1)) if instance else None
    viewer_task = db.scalar(select(WorkflowTask).where(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.status == "PENDING", WorkflowTask.assignee_user_id == viewer_id).limit(1)) if instance and viewer_id else None
    return PaymentView(
        id=payment.id,
        payment_no=payment.payment_no,
        project_id=payment.project_id,
        project_name=project.name if project else "",
        contract_id=payment.contract_id,
        contract_name=contract.name if contract else "",
        contract_no=contract.contract_no if contract else None,
        counterparty_name=counterparty.name if counterparty else (contract.counterparty_name if contract else None),
        stage_id=payment.stage_id,
        stage_name=stage.name if stage else None,
        amount=float(payment.amount or 0),
        payment_date=payment.payment_date,
        payee_name=payment.payee_name,
        payee_bank_name=payment.payee_bank_name,
        payee_bank_account=payment.payee_bank_account,
        budget_item_id=payment.budget_item_id,
        budget_item_name=payment.budget_item_name_snapshot,
        cost_major=payment.cost_major_snapshot,
        cost_minor=payment.cost_minor_snapshot,
        status=payment.status,
        submitted_by=payment.submitted_by,
        submitted_at=payment.submitted_at,
        approved_by=payment.approved_by,
        approved_at=payment.approved_at,
        comment=payment.comment,
        submitted_by_name=submitted_by.name if submitted_by else None,
        approved_by_name=approved_by.name if approved_by else None,
        stage_planned_amount=stage_amount,
        stage_settled_amount=round(stage_settled, 2) if stage_settled is not None else None,
        stage_remaining_amount=round(max(stage_amount - stage_settled, 0), 2) if stage_amount is not None and stage_settled is not None else None,
        stage_settlement_rate=round(stage_settled / stage_amount * 100, 1) if stage_amount and stage_settled is not None else None,
        approval_timeline=payment_approval_timeline(db, payment),
        current_workflow_instance_id=payment.current_workflow_instance_id,
        current_node_name=current_task.node_name if current_task else None,
        current_task_id=viewer_task.id if viewer_task else None,
        version=payment.version,
        approval_path=payment_workflow_path_views(db, payment),
        can_approve=bool(viewer_task) or bool(
            viewer_id
            and not payment.current_workflow_instance_id
            and payment.status == "PENDING"
            and "cash_approval" in user_admin_permissions(db, viewer_id)
        ),
    )


def resolve_contract(db: Session, contract_id: int) -> Contract:
    contract = db.get(Contract, contract_id)
    if not contract or contract.status == "TERMINATED":
        raise HTTPException(404, "CONTRACT_NOT_FOUND")
    return contract


def resolve_contract_stage(db: Session, stage_id: int | None, contract_id: int) -> ContractStage | None:
    if stage_id is None:
        return None
    stage = db.get(ContractStage, stage_id)
    if not stage or stage.contract_id != contract_id:
        raise HTTPException(400, "STAGE_NOT_MATCH_CONTRACT")
    return stage


def next_document_no(db: Session, model: type, prefix: str) -> str:
    current = int(db.scalar(select(func.max(model.id))) or 0)
    return f"{prefix}-{now_local():%Y%m%d}-{current + 1:04d}"


def ensure_project_in_scope(db: Session, user: User, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project or project.status == "DELETED":
        raise HTTPException(404, "PROJECT_NOT_FOUND")
    scope = project_scope_ids(db, user, "projects")
    if scope is not None and project.id not in scope:
        raise HTTPException(403, "PROJECT_OUT_OF_SCOPE")
    return project


def refresh_stage_status(db: Session, stage: ContractStage | None, contract_type: str) -> None:
    if not stage:
        return
    if contract_type == "INCOME":
        settled = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.stage_id == stage.id, Receipt.status == "APPROVED")) or 0)
    else:
        settled = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.stage_id == stage.id, Payment.status == "APPROVED")) or 0)
    if stage.amount and settled >= float(stage.amount):
        stage.status = "DONE"
    elif settled > 0:
        stage.status = "PARTIAL"
    else:
        stage.status = "PENDING"


def stage_remaining(db: Session, stage: ContractStage, contract_type: str) -> float:
    if contract_type == "INCOME":
        settled = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.stage_id == stage.id, Receipt.status == "APPROVED")) or 0)
    else:
        settled = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.stage_id == stage.id, Payment.status == "APPROVED")) or 0)
    return round(max(float(stage.amount or 0) - settled, 0), 2)


def payment_submission_remaining(db: Session, stage: ContractStage, payment_id: int) -> float:
    """返回付款提交可用额度；审批中和历史待审单据会占用阶段额度。"""
    committed = float(db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.stage_id == stage.id,
            Payment.id != payment_id,
            Payment.status.in_(("PENDING", "PENDING_APPROVAL", "APPROVED")),
        )
    ) or 0)
    return round(max(float(stage.amount or 0) - committed, 0), 2)


def project_finance_summary(db: Session, project: Project, as_of: date | None = None) -> dict[str, float]:
    """汇总项目合同额与已审批收付款，供详情和项目看板使用。

    当前应收只包含核算日当天及之前已到期的收入合同阶段；未到期阶段属于未来应收，
    由项目分析中的阶段明细单独展示。
    """
    as_of = as_of or today_local()
    contract_income = float(db.scalar(select(func.coalesce(func.sum(Contract.amount), 0)).where(Contract.project_id == project.id, Contract.contract_type == "INCOME", Contract.status != "TERMINATED")) or 0)
    contract_expense = float(db.scalar(select(func.coalesce(func.sum(Contract.amount), 0)).where(Contract.project_id == project.id, Contract.contract_type == "EXPENSE", Contract.status != "TERMINATED")) or 0)
    # 合同收付款单审批状态是事实来源，兼容早期已审批但尚未补经营流水的历史数据。
    received = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.project_id == project.id, Receipt.status == "APPROVED")) or 0)
    contract_paid = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.project_id == project.id, Payment.status == "APPROVED")) or 0)
    expense_paid = float(db.scalar(select(func.coalesce(func.sum(ProjectExpensePayment.amount), 0)).join(ProjectExpense, ProjectExpensePayment.expense_id == ProjectExpense.id).where(ProjectExpense.project_id == project.id, ProjectExpensePayment.status == "CONFIRMED")) or 0)
    paid = contract_paid + expense_paid

    due_income_stages = db.execute(
        select(ContractStage.id, ContractStage.amount)
        .join(Contract, ContractStage.contract_id == Contract.id)
        .where(
            Contract.project_id == project.id,
            Contract.contract_type == "INCOME",
            Contract.status != "TERMINATED",
            ContractStage.status != "CANCELLED",
            ContractStage.planned_date.is_not(None),
            ContractStage.planned_date <= as_of,
        )
    ).all()
    due_receipts: dict[int, float] = {}
    due_stage_ids = [stage_id for stage_id, _ in due_income_stages]
    if due_stage_ids:
        due_receipts = {
            stage_id: float(amount or 0)
            for stage_id, amount in db.execute(
                select(Receipt.stage_id, func.coalesce(func.sum(Receipt.amount), 0))
                .where(
                    Receipt.project_id == project.id,
                    Receipt.stage_id.in_(due_stage_ids),
                    Receipt.status == "APPROVED",
                )
                .group_by(Receipt.stage_id)
            ).all()
            if stage_id is not None
        }
    receivable = sum(
        max(float(stage_amount or 0) - due_receipts.get(stage_id, 0), 0)
        for stage_id, stage_amount in due_income_stages
    )
    due_expense_stages = db.execute(
        select(ContractStage.id, ContractStage.amount)
        .join(Contract, ContractStage.contract_id == Contract.id)
        .where(
            Contract.project_id == project.id,
            Contract.contract_type == "EXPENSE",
            Contract.status != "TERMINATED",
            ContractStage.status != "CANCELLED",
            ContractStage.planned_date.is_not(None),
            ContractStage.planned_date <= as_of,
        )
    ).all()
    due_payments: dict[int, float] = {}
    due_expense_stage_ids = [stage_id for stage_id, _ in due_expense_stages]
    if due_expense_stage_ids:
        due_payments = {
            stage_id: float(amount or 0)
            for stage_id, amount in db.execute(
                select(Payment.stage_id, func.coalesce(func.sum(Payment.amount), 0))
                .where(
                    Payment.project_id == project.id,
                    Payment.stage_id.in_(due_expense_stage_ids),
                    Payment.status == "APPROVED",
                )
                .group_by(Payment.stage_id)
            ).all()
            if stage_id is not None
        }
    payable = sum(
        max(float(stage_amount or 0) - due_payments.get(stage_id, 0), 0)
        for stage_id, stage_amount in due_expense_stages
    )
    expense_payable = float(db.scalar(select(func.coalesce(func.sum(ProjectExpense.amount), 0)).where(
        ProjectExpense.project_id == project.id,
        ProjectExpense.requires_payment.is_(True),
        ProjectExpense.status == "APPROVED_PENDING_PAYMENT",
        or_(ProjectExpense.payment_due_date.is_(None), ProjectExpense.payment_due_date <= as_of),
    )) or 0)
    payable += expense_payable
    return {
        "contract_income": round(contract_income, 2),
        "contract_expense": round(contract_expense, 2),
        "received": round(received, 2),
        "paid": round(paid, 2),
        "receivable": round(receivable, 2),
        "payable": round(payable, 2),
        "gross_profit": round(received - paid, 2),
    }


def project_analysis_view(db: Session, project: Project, as_of: date) -> ProjectAnalysisView:
    """组装单项目经营分析，统一返回成本、合同阶段、结项风险和可下钻来源。"""
    finance = project_finance_summary(db, project, as_of=as_of)
    project_detail = project_view(db, project)
    approved_days = float(db.scalar(select(func.coalesce(func.sum(Worklog.quantity), 0)).where(Worklog.project_id == project.id, Worklog.status.in_(("APPROVED", "LOCKED")))) or 0)
    personnel_cost = float(db.scalar(select(func.coalesce(func.sum(ProjectLedgerEntry.amount), 0)).where(ProjectLedgerEntry.project_id == project.id, ProjectLedgerEntry.entry_type == "PERSONNEL_COST")) or 0)
    personnel_cost -= float(db.scalar(select(func.coalesce(func.sum(ProjectLedgerEntry.amount), 0)).where(ProjectLedgerEntry.project_id == project.id, ProjectLedgerEntry.entry_type == "REVERSAL", ProjectLedgerEntry.source_type.in_(("WORKLOG", "PERSONNEL_COST")))) or 0)
    personnel_cost = round(max(personnel_cost, 0), 2)
    contract_cost = round(float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.project_id == project.id, Payment.status == "APPROVED")) or 0), 2)
    expense_cost = round(float(db.scalar(select(func.coalesce(func.sum(ProjectLedgerEntry.amount), 0)).where(ProjectLedgerEntry.project_id == project.id, ProjectLedgerEntry.entry_type == "PROJECT_EXPENSE_COST")) or 0), 2)
    expense_cost -= round(float(db.scalar(select(func.coalesce(func.sum(ProjectLedgerEntry.amount), 0)).where(ProjectLedgerEntry.project_id == project.id, ProjectLedgerEntry.entry_type == "REVERSAL", ProjectLedgerEntry.source_type == "PROJECT_EXPENSE")) or 0), 2)
    expense_cost = max(expense_cost, 0)
    total_cost = round(personnel_cost + contract_cost + expense_cost, 2)
    budget_item_rows = project_budget_item_views(db, project.id)
    budget_cost = round(sum(float(item.budget_amount or 0) for item in budget_item_rows if item.is_active), 2)
    expense_budget = round(sum(float(item.budget_amount or 0) for item in budget_item_rows if item.is_active and item.code != "LABOR_COST"), 2)
    non_labor_actual = round(contract_cost + expense_cost, 2)
    expense_budget_remaining = round(expense_budget - non_labor_actual, 2)
    expense_budget_usage_rate = round(non_labor_actual / expense_budget * 100, 1) if expense_budget > 0 else None
    labor_budget = next((float(item.budget_amount or 0) for item in budget_item_rows if item.code == "LABOR_COST" and item.is_active), 0.0)
    personnel_budget_base = round(labor_budget, 2) if labor_budget > 0 else None
    personnel_usage_rate = round(personnel_cost / personnel_budget_base * 100, 1) if personnel_budget_base and personnel_budget_base > 0 else None
    cost_usage_rate = round(total_cost / budget_cost * 100, 1) if budget_cost > 0 else None

    month_index = as_of.year * 12 + as_of.month - 1
    trend = {}
    for offset in range(5, -1, -1):
        current_index = month_index - offset
        year, month_zero = divmod(current_index, 12)
        trend[f"{year:04d}-{month_zero + 1:02d}"] = {"personnel_cost": 0.0, "contract_cost": 0.0, "expense_cost": 0.0}
    ledger_rows = db.scalars(select(ProjectLedgerEntry).where(ProjectLedgerEntry.project_id == project.id)).all()
    for entry in ledger_rows:
        occurred_on = entry.occurred_on or entry.created_at.date()
        key = f"{occurred_on.year:04d}-{occurred_on.month:02d}"
        if key not in trend:
            continue
        amount = float(entry.amount or 0)
        if entry.entry_type == "PERSONNEL_COST":
            trend[key]["personnel_cost"] += amount
        elif entry.entry_type == "PAYMENT":
            trend[key]["contract_cost"] += amount
        elif entry.entry_type == "PROJECT_EXPENSE_COST":
            trend[key]["expense_cost"] += amount
        elif entry.entry_type == "REVERSAL":
            if entry.source_type == "PAYMENT":
                trend[key]["contract_cost"] -= amount
            elif entry.source_type == "PROJECT_EXPENSE":
                trend[key]["expense_cost"] -= amount
            else:
                trend[key]["personnel_cost"] -= amount
    monthly_trend = [
        ProjectAnalysisCostTrendView(
            month=month,
            personnel_cost=round(max(values["personnel_cost"], 0), 2),
            contract_cost=round(max(values["contract_cost"], 0), 2),
            expense_cost=round(max(values["expense_cost"], 0), 2),
            total_cost=round(max(values["personnel_cost"] + values["contract_cost"] + values["expense_cost"], 0), 2),
        )
        for month, values in trend.items()
    ]

    contracts = db.scalars(select(Contract).where(Contract.project_id == project.id, Contract.status != "TERMINATED").order_by(Contract.contract_type, Contract.id)).all()
    contract_ids = [contract.id for contract in contracts]
    stages = db.scalars(select(ContractStage).where(ContractStage.contract_id.in_(contract_ids)).order_by(ContractStage.contract_id, ContractStage.sort_order, ContractStage.id)).all() if contract_ids else []
    stages_by_contract: dict[int, list[ContractStage]] = defaultdict(list)
    for stage in stages:
        stages_by_contract[stage.contract_id].append(stage)
    income_settled: dict[int, float] = {}
    income_counts: dict[int, int] = {}
    for stage_id, amount, count in db.execute(select(Receipt.stage_id, func.coalesce(func.sum(Receipt.amount), 0), func.count(Receipt.id)).where(Receipt.project_id == project.id, Receipt.status == "APPROVED").group_by(Receipt.stage_id)).all():
        if stage_id is not None:
            income_settled[stage_id] = float(amount or 0)
            income_counts[stage_id] = int(count or 0)
    expense_settled: dict[int, float] = {}
    expense_counts: dict[int, int] = {}
    for stage_id, amount, count in db.execute(select(Payment.stage_id, func.coalesce(func.sum(Payment.amount), 0), func.count(Payment.id)).where(Payment.project_id == project.id, Payment.status == "APPROVED").group_by(Payment.stage_id)).all():
        if stage_id is not None:
            expense_settled[stage_id] = float(amount or 0)
            expense_counts[stage_id] = int(count or 0)
    warnings: list[ProjectAnalysisWarningView] = []
    stage_views: dict[int, ProjectAnalysisStageView] = {}

    def stage_view(contract: Contract, stage: ContractStage) -> ProjectAnalysisStageView:
        if stage.id in stage_views:
            return stage_views[stage.id]
        is_income = contract.contract_type == "INCOME"
        settled = (income_settled if is_income else expense_settled).get(stage.id, 0.0)
        settled_count = (income_counts if is_income else expense_counts).get(stage.id, 0)
        planned = round(float(stage.amount or 0), 2)
        remaining = round(max(planned - settled, 0), 2)
        days_to_due = (stage.planned_date - as_of).days if stage.planned_date else None
        if stage.status == "CANCELLED":
            status = "CANCELLED"
        elif remaining <= 0:
            status = "DONE"
        elif stage.planned_date and days_to_due is not None and days_to_due < 0:
            status = "OVERDUE"
        elif settled > 0:
            status = "PARTIAL"
        elif stage.planned_date and days_to_due is not None and days_to_due <= stage.remind_days_before:
            status = "UPCOMING"
        else:
            status = "PLANNED"
        warning_level = None
        warning_type = None
        side_label = "收款" if is_income else "付款"
        settle_verb = "收" if is_income else "付"
        if remaining > 0 and stage.planned_date:
            if days_to_due is not None and days_to_due < 0:
                warning_level, warning_type = "CRITICAL", "OVERDUE"
                warnings.append(ProjectAnalysisWarningView(level="CRITICAL", warning_type="OVERDUE", title=f"{side_label}阶段“{stage.name}”已逾期", detail=f"计划日期 {stage.planned_date}，仍有 ¥{remaining:,.2f} 未{settle_verb}", amount=remaining, planned_date=stage.planned_date, source_type="CONTRACT_STAGE", source_id=stage.id))
            elif days_to_due is not None and days_to_due <= stage.remind_days_before:
                warning_level, warning_type = "WARNING", "UPCOMING"
                warnings.append(ProjectAnalysisWarningView(level="WARNING", warning_type="UPCOMING", title=f"{side_label}阶段“{stage.name}”即将到期", detail=f"距计划日期 {days_to_due} 天，仍有 ¥{remaining:,.2f} 未{settle_verb}", amount=remaining, planned_date=stage.planned_date, source_type="CONTRACT_STAGE", source_id=stage.id))
        if remaining > 0 and project.planned_end_date and stage.planned_date and stage.planned_date > project.planned_end_date:
            warning_level, warning_type = "CRITICAL", "AFTER_CLOSE"
            warnings.append(ProjectAnalysisWarningView(level="CRITICAL", warning_type="AFTER_CLOSE", title=f"{side_label}阶段“{stage.name}”晚于项目结项日期", detail=f"阶段计划 {stage.planned_date}，项目计划结项 {project.planned_end_date}", amount=remaining, planned_date=stage.planned_date, source_type="CONTRACT_STAGE", source_id=stage.id))
        if remaining > 0 and not stage.planned_date:
            warning_level, warning_type = "INFO", "UNSCHEDULED"
            warnings.append(ProjectAnalysisWarningView(level="INFO", warning_type="UNSCHEDULED", title=f"{side_label}阶段“{stage.name}”未设置计划日期", detail=f"仍有 ¥{remaining:,.2f} 未{settle_verb}，无法纳入结项计划", amount=remaining, source_type="CONTRACT_STAGE", source_id=stage.id))
        stage_views[stage.id] = ProjectAnalysisStageView(id=stage.id, name=stage.name, planned_date=stage.planned_date, planned_amount=planned, settled_amount=round(settled, 2), remaining_amount=remaining, settlement_rate=round(settled / planned * 100, 1) if planned > 0 else None, status=status, warning_level=warning_level, warning_type=warning_type, days_to_due=days_to_due, settled_document_count=settled_count)
        return stage_views[stage.id]

    def contract_view(contract: Contract) -> ProjectAnalysisContractView:
        is_income = contract.contract_type == "INCOME"
        settled = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.contract_id == contract.id, Receipt.status == "APPROVED")) if is_income else db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.contract_id == contract.id, Payment.status == "APPROVED"))) or 0
        amount = round(float(contract.amount or 0), 2)
        counterparty = db.get(Customer if contract.counterparty_type == "CUSTOMER" else Supplier, contract.counterparty_id)
        counterparty_name = counterparty.name if counterparty else contract.counterparty_name
        return ProjectAnalysisContractView(id=contract.id, contract_no=contract.contract_no, name=contract.name, contract_type=contract.contract_type, counterparty_name=counterparty_name, amount=amount, settled_amount=round(settled, 2), remaining_amount=round(max(amount - settled, 0), 2), settlement_rate=round(settled / amount * 100, 1) if amount > 0 else None, stages=[stage_view(contract, stage) for stage in stages_by_contract.get(contract.id, [])])

    income_contracts = [contract_view(contract) for contract in contracts if contract.contract_type == "INCOME"]
    expense_contracts = [contract_view(contract) for contract in contracts if contract.contract_type == "EXPENSE"]
    pending_receipt_amount = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.project_id == project.id, Receipt.status == "PENDING")) or 0)
    pending_payment_amount = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.project_id == project.id, Payment.status.in_(("PENDING", "PENDING_APPROVAL")))) or 0)
    if pending_receipt_amount > 0:
        warnings.append(ProjectAnalysisWarningView(level="INFO", warning_type="PENDING_APPROVAL", title="存在待审批合同收款单", detail=f"¥{pending_receipt_amount:,.2f} 尚未确认，不计入已收", amount=round(pending_receipt_amount, 2), source_type="RECEIPT"))
    if pending_payment_amount > 0:
        warnings.append(ProjectAnalysisWarningView(level="INFO", warning_type="PENDING_APPROVAL", title="存在待审批合同付款单", detail=f"¥{pending_payment_amount:,.2f} 尚未确认，不计入已付", amount=round(pending_payment_amount, 2), source_type="PAYMENT"))
    if budget_cost > 0 and cost_usage_rate is not None and cost_usage_rate >= 100:
        warnings.append(ProjectAnalysisWarningView(level="CRITICAL", warning_type="COST_OVER_BUDGET", title="项目总成本已超过成本预算", detail=f"已使用 {cost_usage_rate:.1f}%，超支 ¥{abs(budget_cost - total_cost):,.2f}", amount=round(total_cost - budget_cost, 2), source_type="PROJECT", source_id=project.id))
    elif budget_cost > 0 and cost_usage_rate is not None and cost_usage_rate >= 80:
        warnings.append(ProjectAnalysisWarningView(level="WARNING", warning_type="COST_NEAR_BUDGET", title="项目总成本接近成本预算", detail=f"已使用 {cost_usage_rate:.1f}%，预算剩余 ¥{max(budget_cost - total_cost, 0):,.2f}", amount=round(max(budget_cost - total_cost, 0), 2), source_type="PROJECT", source_id=project.id))

    before_close_receivable = before_close_payable = after_close_receivable = after_close_payable = unscheduled_receivable = unscheduled_payable = 0.0
    if project.planned_end_date:
        for contract in contracts:
            is_income = contract.contract_type == "INCOME"
            for stage in stages_by_contract.get(contract.id, []):
                stage_amount = stage_view(contract, stage).remaining_amount
                if stage_amount <= 0 or stage.status == "CANCELLED":
                    continue
                if stage.planned_date is None:
                    if is_income:
                        unscheduled_receivable += stage_amount
                    else:
                        unscheduled_payable += stage_amount
                elif stage.planned_date <= project.planned_end_date:
                    if is_income:
                        before_close_receivable += stage_amount
                    else:
                        before_close_payable += stage_amount
                else:
                    if is_income:
                        after_close_receivable += stage_amount
                    else:
                        after_close_payable += stage_amount
    else:
        for contract in contracts:
            is_income = contract.contract_type == "INCOME"
            for stage in stages_by_contract.get(contract.id, []):
                stage_amount = stage_view(contract, stage).remaining_amount
                if stage_amount > 0 and stage.planned_date is None:
                    if is_income:
                        unscheduled_receivable += stage_amount
                    else:
                        unscheduled_payable += stage_amount
        warnings.append(ProjectAnalysisWarningView(level="INFO", warning_type="NO_CLOSE_DATE", title="项目未设置计划结项日期", detail="无法判断结项前后的收付款风险，请先补充项目计划结项日期", source_type="PROJECT", source_id=project.id))
    days_to_close = (project.planned_end_date - as_of).days if project.planned_end_date else None
    if days_to_close is not None and days_to_close < 0 and before_close_receivable + before_close_payable > 0:
        closeout_status = "OVERDUE"
        warnings.append(ProjectAnalysisWarningView(level="CRITICAL", warning_type="CLOSEOUT_OVERDUE", title="项目已超过计划结项日期", detail=f"仍有 ¥{before_close_receivable:,.2f} 待收、¥{before_close_payable:,.2f} 待付", amount=round(before_close_receivable + before_close_payable, 2), source_type="PROJECT", source_id=project.id))
    elif days_to_close is not None and days_to_close <= 7 and before_close_receivable + before_close_payable > 0:
        closeout_status = "AT_RISK"
        warnings.append(ProjectAnalysisWarningView(level="WARNING", warning_type="CLOSEOUT_AT_RISK", title=f"距离项目结项还有 {days_to_close} 天", detail=f"结项前仍有 ¥{before_close_receivable:,.2f} 待收、¥{before_close_payable:,.2f} 待付", amount=round(before_close_receivable + before_close_payable, 2), source_type="PROJECT", source_id=project.id))
    elif days_to_close is None:
        closeout_status = "NO_DATE"
    elif before_close_receivable + before_close_payable > 0:
        closeout_status = "AT_RISK"
    else:
        closeout_status = "NORMAL"
    for warning in warnings:
        # 看板聚合预警时保留所属项目，保证待审批单据和阶段预警也能下钻。
        warning.project_id = project.id
    return ProjectAnalysisView(
        project=project_detail,
        as_of=as_of,
        kpis=ProjectFinanceView(project_id=project.id, **finance),
        cost=ProjectAnalysisCostView(personnel_cost=personnel_cost, contract_cost=contract_cost, expense_cost=expense_cost, total_cost=total_cost, budget_cost=budget_cost, expense_budget=expense_budget, expense_budget_remaining=expense_budget_remaining, expense_budget_usage_rate=expense_budget_usage_rate, remaining_cost=round(budget_cost - total_cost, 2), personnel_cost_budget_base=personnel_budget_base, personnel_cost_usage_rate=personnel_usage_rate, cost_usage_rate=cost_usage_rate, budget_items=budget_item_rows, monthly_trend=monthly_trend),
        settlement=ProjectAnalysisSettlementView(income_contracts=income_contracts, expense_contracts=expense_contracts, pending_approval_receipt_amount=round(pending_receipt_amount, 2), pending_approval_payment_amount=round(pending_payment_amount, 2)),
        closeout=ProjectAnalysisCloseoutView(planned_end_date=project.planned_end_date, days_to_close=days_to_close, before_close_receivable=round(before_close_receivable, 2), before_close_payable=round(before_close_payable, 2), after_close_receivable=round(after_close_receivable, 2), after_close_payable=round(after_close_payable, 2), unscheduled_receivable=round(unscheduled_receivable, 2), unscheduled_payable=round(unscheduled_payable, 2), status=closeout_status),
        warnings=warnings,
    )


def org_user_view(db: Session, user: User) -> OrgUserView:
    """组装组织用户选择项，部门名称来自本地组织快照。"""
    department = db.get(Department, user.department_id)
    index = DepartmentIndex(db.scalars(select(Department)).all())
    return OrgUserView(
        id=user.id,
        feishu_user_id=user.feishu_user_id,
        name=user.name,
        department_name=department.name if department else "未分配",
        department_id=department.id if department else None,
        department_path=index.path(department.id if department else None),
        employment_status=user.employment_status,
    )


def org_department_view(department: Department) -> OrgDepartmentView:
    """组装组织部门选择项，仅暴露本地组织快照字段。"""
    # 单个部门对象无法解析祖先，调用方会在批量列表中补充完整路径。
    return OrgDepartmentView(id=department.id, feishu_department_id=department.feishu_department_id, name=department.name, parent_name=department.parent_name, is_active=department.is_active)


def personnel_cost_view(db: Session, user: User) -> PersonnelCostView:
    """组装管理员人员成本维护行，成本字段不暴露给普通组织接口。"""
    department = db.get(Department, user.department_id) if user.department_id else None
    index = DepartmentIndex(db.scalars(select(Department)).all())
    return PersonnelCostView(id=user.id, name=user.name, department_name=index.path(department.id if department else None), daily_cost=float(user.daily_cost) if user.daily_cost is not None else None)


def active_org_user(db: Session, user_id: int) -> User:
    """读取可用于项目配置的启用组织用户。"""
    user = db.get(User, user_id)
    if not user or user.employment_status != "ACTIVE":
        raise HTTPException(400, "USER_NOT_ACTIVE")
    return user


def active_org_department(db: Session, department_id: int) -> Department:
    """读取可用于项目配置的启用组织部门。"""
    department = db.get(Department, department_id)
    if not department or not department.is_active:
        raise HTTPException(400, "DEPARTMENT_NOT_ACTIVE")
    return department


def active_customer(db: Session, customer_id: int | None) -> Customer | None:
    if customer_id is None:
        return None
    customer = db.get(Customer, customer_id)
    if not customer or customer.status != "ACTIVE":
        raise HTTPException(400, "CUSTOMER_NOT_ACTIVE")
    return customer


def resolve_counterparty_name(db: Session, counterparty_type: str, counterparty_id: int) -> str:
    if counterparty_type == "CUSTOMER":
        customer = db.get(Customer, counterparty_id)
        if not customer or customer.status != "ACTIVE":
            raise HTTPException(400, "CUSTOMER_NOT_ACTIVE")
        return customer.name
    supplier = db.get(Supplier, counterparty_id)
    if not supplier or supplier.status != "ACTIVE":
        raise HTTPException(400, "SUPPLIER_NOT_ACTIVE")
    return supplier.name


def apply_project_master_fields(project: Project, db: Session, payload: ProjectCreate | ProjectUpdate) -> None:
    """写入项目主信息；客户名称同时保存快照，避免主数据更名影响历史展示。"""
    customer = active_customer(db, payload.customer_id)
    project.customer_id = customer.id if customer else None
    project.customer_name = customer.name if customer else None
    project.start_date = payload.start_date
    project.planned_end_date = payload.planned_end_date
    project.description = payload.description.strip() if payload.description and payload.description.strip() else None


def apply_project_users(project: Project, db: Session, owner_user_id: int, approver_user_id: int, leader_user_id: int) -> None:
    """将三个组织用户写入项目，同时保留姓名和身份快照。"""
    owner = active_org_user(db, owner_user_id)
    approver = active_org_user(db, approver_user_id)
    leader = active_org_user(db, leader_user_id)
    project.owner_user_id = owner.id
    project.owner_name = owner.name
    project.owner_open_id = owner.open_id
    project.approver_user_id = approver.id
    project.approver_name = approver.name
    project.approver_open_id = approver.open_id
    project.leader_user_id = leader.id
    project.leader_name = leader.name
    project.leader_open_id = leader.open_id


def worklog_view(worklog: Worklog) -> WorklogView:
    return WorklogView.model_validate(worklog)


def admin_worklog_view(worklog: Worklog, serial_no: str | None, user_department_name: str, project_department_name: str) -> AdminWorklogView:
    """组装管理员工时列表行，附加组织和审批单快照。"""
    payload = worklog_view(worklog).model_dump()
    payload.update(serial_no=serial_no, user_name_snapshot=worklog.user_name_snapshot, user_department_name=user_department_name, project_department_name=project_department_name)
    return AdminWorklogView(**payload)


def audit(db: Session, object_type: str, object_id: int, action: str, actor_id: int | None, old_status: str | None, new_status: str | None, comment: str | None = None) -> None:
    """写入不可覆盖的业务审计事件。"""
    db.add(AuditLog(object_type=object_type, object_id=object_id, action=action, actor_user_id=actor_id, old_status=old_status, new_status=new_status, comment=comment))


def add_ledger_entry(
    db: Session,
    project_id: int,
    entry_type: str,
    source_type: str,
    source_id: int,
    amount: float,
    occurred_on: date | None = None,
    reversal_of_id: int | None = None,
    budget_item: ProjectBudgetItem | None = None,
) -> ProjectLedgerEntry | None:
    """追加一条项目经营流水，幂等键防止重复记账。"""
    idempotency_key = f"{entry_type}:{source_type}:{source_id}"
    existing = db.scalar(select(ProjectLedgerEntry).where(
        ProjectLedgerEntry.entry_type == entry_type,
        ProjectLedgerEntry.source_type == source_type,
        ProjectLedgerEntry.source_id == source_id,
    ).limit(1))
    if existing:
        if budget_item and not existing.budget_item_id:
            apply_budget_snapshot(existing, budget_item)
        return existing
    entry = ProjectLedgerEntry(
        project_id=project_id,
        entry_type=entry_type,
        source_type=source_type,
        source_id=source_id,
        amount=amount,
        occurred_on=occurred_on,
        reversal_of_id=reversal_of_id,
        idempotency_key=idempotency_key,
    )
    apply_budget_snapshot(entry, budget_item)
    db.add(entry)
    db.flush()
    return entry


def refresh_missing_worklog_cost(db: Session, user_id: int | None = None) -> int:
    """将已审批且成本快照仍为 0 的工时按当前单天成本补齐并同步流水。"""
    query = (
        select(Worklog, User.daily_cost)
        .join(User, Worklog.user_id == User.id)
        .where(
            Worklog.status.in_(("APPROVED", "LOCKED")),
            or_(Worklog.daily_cost_snapshot.is_(None), Worklog.daily_cost_snapshot == 0),
            User.daily_cost.is_not(None),
            User.daily_cost > 0,
        )
    )
    if user_id is not None:
        query = query.where(Worklog.user_id == user_id)
    updated = 0
    for worklog, daily_cost in db.execute(query).all():
        cost_amount = round(float(worklog.quantity) * float(daily_cost), 2)
        worklog.daily_cost_snapshot = float(daily_cost)
        worklog.cost_amount_snapshot = cost_amount
        existing = db.scalar(select(ProjectLedgerEntry).where(
            ProjectLedgerEntry.entry_type == "PERSONNEL_COST",
            ProjectLedgerEntry.source_type == "WORKLOG",
            ProjectLedgerEntry.source_id == worklog.id,
        ))
        if existing:
            existing.amount = cost_amount
            existing.occurred_on = worklog.start_date
            apply_budget_snapshot(existing, project_labor_budget_item(db, worklog.project_id))
        else:
            labor_budget_item = project_labor_budget_item(db, worklog.project_id)
            db.add(ProjectLedgerEntry(
                project_id=worklog.project_id,
                entry_type="PERSONNEL_COST",
                source_type="WORKLOG",
                source_id=worklog.id,
                amount=cost_amount,
                occurred_on=worklog.start_date,
                budget_item_id=labor_budget_item.id if labor_budget_item else None,
                budget_item_name_snapshot=labor_budget_item.name if labor_budget_item else None,
                cost_major_snapshot=labor_budget_item.cost_major if labor_budget_item else None,
                cost_minor_snapshot=labor_budget_item.cost_minor if labor_budget_item else None,
                idempotency_key=f"PERSONNEL_COST:WORKLOG:{worklog.id}",
            ))
        updated += 1
    if updated:
        db.flush()
    return updated


def notification_policy(db: Session, notification_type: str) -> NotificationPolicy | None:
    """读取单个通知策略；兼容策略表尚未初始化的旧数据库。"""
    return db.scalar(select(NotificationPolicy).where(NotificationPolicy.notification_type == notification_type))


def notification_policy_enabled(db: Session, notification_type: str) -> bool:
    """读取通知开关；策略表尚未初始化时保持现有默认发送行为。"""
    policy = notification_policy(db, notification_type)
    return True if policy is None else bool(policy.enabled)


def notification_policy_channel(db: Session, notification_type: str) -> str | None:
    """返回本次通知的策略通道；未配置策略时交由适配器使用环境默认值。"""
    policy = notification_policy(db, notification_type)
    return policy.send_channel if policy else None


def cash_approver_users(db: Session) -> list[User]:
    """返回所有启用且具备出纳审批权限的用户，系统管理员也包含在内。"""
    users = db.scalars(
        select(User).where(User.employment_status == "ACTIVE").order_by(User.id)
    ).all()
    return [user for user in users if "cash_approval" in user_admin_permissions(db, user.id)]


def send_cash_approval_notifications(
    db: Session,
    source_type: str,
    source_id: int,
    document_type_label: str,
    serial_no: str,
    project_name: str,
    amount: float,
    submitter_name: str,
    recipient_user_id: int | None = None,
) -> int:
    """向所有出纳审批人发送待审批提醒，并按单据和接收人幂等记录。"""
    notification_type = "PENDING_RECEIPT" if source_type == "receipt" else "PENDING_PAYMENT"
    if not notification_policy_enabled(db, notification_type):
        return 0
    channel = notification_policy_channel(db, notification_type)
    sent = 0
    for recipient in cash_approver_users(db):
        if recipient_user_id is not None and recipient.id != recipient_user_id:
            continue
        idempotency_key = f"cash-approval:{source_type}:{source_id}:{recipient.id}"
        notification = db.scalar(
            select(SystemNotification).where(SystemNotification.idempotency_key == idempotency_key)
        )
        if notification and notification.status == "SENT":
            continue
        result = feishu.notify_cash_approval_submitted(
            recipient.name,
            submitter_name,
            document_type_label,
            serial_no,
            project_name,
            amount,
            os.getenv("SYSTEM_PUBLIC_URL", "http://192.168.112.188:8088"),
            recipient.open_id,
            channel=channel,
        )
        if not notification:
            notification = SystemNotification(
                notification_type=notification_type,
                source_type=source_type,
                source_id=source_id,
                recipient_user_id=recipient.id,
                channel=channel or feishu.notification_mode,
                idempotency_key=idempotency_key,
            )
            db.add(notification)
        else:
            notification.recipient_user_id = recipient.id
            notification.channel = channel or feishu.notification_mode
            notification.retry_count = int(notification.retry_count or 0) + 1
        notification.status = result.status
        notification.message_id = result.message_id
        notification.error_message = result.error_message
        notification.sent_at = now_local() if result.status == "SENT" else None
        if result.status == "SENT":
            sent += 1
    db.flush()
    return sent


def send_settlement_notification(
    db: Session,
    source_type: str,
    source_id: int,
    document_type_label: str,
    serial_no: str,
    project_name: str,
    amount: float,
    recipient_user_id: int,
    approver_name: str | None = None,
) -> None:
    """审批通过后通知申请人，失败不影响单据状态。"""
    recipient = db.get(User, recipient_user_id)
    if not recipient:
        return
    if not notification_policy_enabled(db, "SETTLEMENT_APPROVED"):
        return
    idempotency_key = f"settlement:{source_type}:{source_id}"
    notification = db.scalar(select(SystemNotification).where(SystemNotification.idempotency_key == idempotency_key))
    if notification and notification.status == "SENT":
        return
    channel = notification_policy_channel(db, "SETTLEMENT_APPROVED")
    result = feishu.notify_settlement_result(
        recipient.name,
        document_type_label,
        serial_no,
        project_name,
        amount,
        "审批通过",
        os.getenv("SYSTEM_PUBLIC_URL", "http://192.168.112.188:8088"),
        recipient.open_id,
        channel=channel,
        approver_name=approver_name,
    )
    if not notification:
        notification = SystemNotification(
            notification_type="SETTLEMENT_APPROVED",
            source_type=source_type,
            source_id=source_id,
            recipient_user_id=recipient.id,
            channel=channel or feishu.notification_mode,
            idempotency_key=idempotency_key,
        )
        db.add(notification)
    else:
        notification.recipient_user_id = recipient.id
        notification.channel = channel or feishu.notification_mode
        notification.retry_count = int(notification.retry_count or 0) + 1
    notification.status = result.status
    notification.message_id = result.message_id
    notification.error_message = result.error_message
    notification.sent_at = now_local() if result.status == "SENT" else None
    db.commit()


def send_project_warning_notification(
    db: Session,
    project: Project,
    notification_type: str,
    title: str,
    detail: str,
    business_date: date,
) -> bool:
    """发送项目预警并按项目、类型和业务日期幂等；失败记录会在后续扫描重试。"""
    owner = db.get(User, project.owner_user_id) if project.owner_user_id else None
    if not owner:
        return False
    if not notification_policy_enabled(db, notification_type):
        return False
    idempotency_key = f"project-warning:{project.id}:{notification_type}:{business_date.isoformat()}"
    notification = db.scalar(select(SystemNotification).where(SystemNotification.idempotency_key == idempotency_key))
    if notification and notification.status == "SENT":
        return False
    is_retry = notification is not None
    channel = notification_policy_channel(db, notification_type)
    result = feishu.notify_project_warning(
        owner.name,
        project.name,
        title,
        detail,
        os.getenv("SYSTEM_PUBLIC_URL", "http://192.168.112.188:8088"),
        owner.open_id,
        channel=channel,
    )
    if not notification:
        notification = SystemNotification(
            notification_type=notification_type,
            source_type="PROJECT",
            source_id=project.id,
            recipient_user_id=owner.id,
            channel=channel or feishu.notification_mode,
            idempotency_key=idempotency_key,
        )
        db.add(notification)
    else:
        notification.recipient_user_id = owner.id
        notification.channel = channel or feishu.notification_mode
    notification.status = result.status
    notification.message_id = result.message_id
    notification.error_message = result.error_message
    notification.sent_at = now_local() if result.status == "SENT" else None
    if is_retry:
        notification.retry_count = int(notification.retry_count or 0) + 1
    db.flush()
    return result.status == "SENT"


def run_stage_reminder_scan_once() -> dict[str, int]:
    """扫描合同阶段、预算和待审批事项并发送业务提醒，按业务日期幂等去重。"""
    db = SessionLocal()
    try:
        today = today_local()
        stages = db.scalars(
            select(ContractStage).where(
                ContractStage.reminder_paused.is_(False),
                ContractStage.planned_date.is_not(None),
            )
        ).all()
        sent = 0
        warning_sent = 0
        for stage in stages:
            contract = db.get(Contract, stage.contract_id)
            if not contract or contract.status == "TERMINATED":
                continue
            remaining = stage_remaining(db, stage, contract.contract_type)
            if remaining <= 0:
                continue
            days = (stage.planned_date - today).days
            if stage.planned_date < today:
                reminder_type = "OVERDUE"
                business_date = today
            elif stage.planned_date == today:
                reminder_type = "DUE"
                business_date = today
            elif days <= stage.remind_days_before:
                reminder_type = "UPCOMING"
                business_date = stage.planned_date
            else:
                continue
            if not notification_policy_enabled(db, f"STAGE_{reminder_type}"):
                continue
            key = f"stage:{stage.id}:{business_date.isoformat()}:{reminder_type}"
            if db.scalar(select(ReminderEvent.id).where(ReminderEvent.idempotency_key == key)):
                continue
            project = db.get(Project, contract.project_id)
            owner = db.get(User, project.owner_user_id) if project and project.owner_user_id else None
            channel = notification_policy_channel(db, f"STAGE_{reminder_type}")
            result = feishu.notify_reminder(
                owner.name if owner else "项目负责人",
                project.name if project else "",
                contract.name,
                stage.name,
                str(stage.planned_date),
                float(stage.amount or 0),
                remaining,
                reminder_type,
                os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088"),
                owner.open_id if owner else None,
                channel=channel,
            )
            db.add(
                ReminderEvent(
                    stage_id=stage.id,
                    reminder_type=reminder_type,
                    business_date=business_date,
                    idempotency_key=key,
                    status=result.status,
                    message_id=result.message_id,
                    error_message=result.error_message,
                )
            )
            if owner:
                notification_key = f"stage-reminder:{key}"
                if not db.scalar(select(SystemNotification.id).where(SystemNotification.idempotency_key == notification_key)):
                    db.add(
                        SystemNotification(
                            notification_type=f"STAGE_{reminder_type}",
                            source_type="CONTRACT_STAGE",
                            source_id=stage.id,
                            recipient_user_id=owner.id,
                            channel=channel or feishu.notification_mode,
                            idempotency_key=notification_key,
                            status=result.status,
                            message_id=result.message_id,
                            error_message=result.error_message,
                            sent_at=now_local() if result.status == "SENT" else None,
                        )
                    )
            db.flush()
            if result.status == "SENT":
                sent += 1
        for project in db.scalars(select(Project).where(Project.status != "DELETED")).all():
            project_row = project_view(db, project)
            if project_row.cost_usage_rate is not None:
                if project_row.cost_usage_rate >= 100:
                    warning_sent += send_project_warning_notification(
                        db,
                        project,
                        "COST_BUDGET_OVER",
                        "项目总预算已超支",
                        f"总预算使用率：{project_row.cost_usage_rate:.1f}%\n实际成本：¥{project_row.actual_cost:,.2f}\n总预算：¥{project_row.budget_cost:,.2f}\n超支金额：¥{max(project_row.actual_cost - project_row.budget_cost, 0):,.2f}",
                        today,
                    )
                elif project_row.cost_usage_rate >= 80:
                    warning_sent += send_project_warning_notification(
                        db,
                        project,
                        "COST_BUDGET_NEAR",
                        "项目总预算接近上限",
                        f"总预算使用率：{project_row.cost_usage_rate:.1f}%\n实际成本：¥{project_row.actual_cost:,.2f}\n总预算：¥{project_row.budget_cost:,.2f}\n预算剩余：¥{max(project_row.budget_cost - project_row.actual_cost, 0):,.2f}",
                        today,
                    )
            pending_receipts = db.scalars(
                select(Receipt).where(Receipt.project_id == project.id, Receipt.status == "PENDING")
            ).all()
            for receipt in pending_receipts:
                submitter = db.get(User, receipt.submitted_by) if receipt.submitted_by else None
                warning_sent += send_cash_approval_notifications(
                    db,
                    "receipt",
                    receipt.id,
                    "合同收款单",
                    receipt.receipt_no,
                    project.name,
                    float(receipt.amount or 0),
                    submitter.name if submitter else "申请人",
                )
            pending_payments = db.scalars(
                select(Payment).where(Payment.project_id == project.id, Payment.status.in_(("PENDING", "PENDING_APPROVAL")))
            ).all()
            for payment in pending_payments:
                submitter = db.get(User, payment.submitted_by) if payment.submitted_by else None
                warning_sent += send_cash_approval_notifications(
                    db,
                    "payment",
                    payment.id,
                    "合同付款单",
                    payment.payment_no,
                    project.name,
                    float(payment.amount or 0),
                    submitter.name if submitter else "申请人",
                )
        db.commit()
        return {"scanned": len(stages), "sent": sent, "warning_sent": warning_sent}
    finally:
        db.close()


def reminder_scan_loop() -> None:
    """后台守护任务：按配置间隔扫描，默认每 10 分钟一次。"""
    interval = max(30, int(os.getenv("REMINDER_SCAN_INTERVAL_SECONDS", "600")))
    while True:
        try:
            run_stage_reminder_scan_once()
        except Exception:
            pass
        time.sleep(interval)


def approver_for_project(db: Session, project: Project) -> User:
    """解析并修复项目审批人；提交时必须得到稳定的启用本地用户身份。"""
    approver = None
    if project.approver_user_id:
        candidate = db.get(User, project.approver_user_id)
        if candidate and candidate.employment_status == "ACTIVE":
            approver = candidate

    if not approver and project.approver_open_id:
        candidate = db.scalar(select(User).where(
            User.open_id == project.approver_open_id,
            User.employment_status == "ACTIVE",
        ))
        if candidate:
            approver = candidate

    if not approver and project.approver_name:
        candidates = db.scalars(select(User).where(
            User.name == project.approver_name,
            User.employment_status == "ACTIVE",
        )).all()
        if len(candidates) > 1:
            raise HTTPException(400, "APPROVER_AMBIGUOUS")
        if candidates:
            approver = candidates[0]

    if not approver:
        raise HTTPException(400, "APPROVER_MISSING")

    # 组织同步可能保留旧演示/本地 ID；提交成功时把项目绑定修正为当前有效用户。
    project.approver_user_id = approver.id
    project.approver_open_id = approver.open_id
    project.approver_name = approver.name
    return approver


def resolve_approver(db: Session, project: Project, submitter: User) -> User:
    """解析当前工时的最终审批人；项目审批人是填报人时转交上级领导。"""
    approver = approver_for_project(db, project)
    if approver.id != submitter.id:
        return approver
    leader = db.get(User, project.leader_user_id) if project.leader_user_id else None
    if not leader or leader.employment_status != "ACTIVE" or leader.id == submitter.id:
        raise HTTPException(400, "APPROVER_SELF_NO_LEADER")
    return leader


def worklog_approval_detail_url(task_id: int) -> str:
    """生成工时审批任务详情深链，供飞书卡片在内置浏览器中直达单据。"""
    base = os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088").rstrip("/")
    return f"{base}/?page=approvalDetail&id={task_id}"


def notify_task(db: Session, task: ApprovalTask, item: Worklog, approver: User, submitter: User) -> Notification:
    """创建并发送提交提醒；发送失败只记录通知失败。"""
    channel = notification_policy_channel(db, "WORKLOG_APPROVAL")
    notification = Notification(approval_task_id=task.id, recipient_user_id=approver.id, channel=channel or feishu.notification_mode, idempotency_key=f"approval:{task.id}:v{task.version}")
    db.add(notification)
    db.flush()
    if not notification_policy_enabled(db, "WORKLOG_APPROVAL"):
        notification.status = "SKIPPED"
        return notification
    result = feishu.notify_approval_submitted(task.serial_no, approver.name, submitter.name, item.project_name_snapshot, item.description, str(item.start_date), float(item.quantity), item.unit, worklog_approval_detail_url(task.id), recipient_open_id=approver.open_id, channel=channel)
    notification.status = result.status
    notification.message_id = result.message_id
    notification.error_message = result.error_message
    notification.sent_at = now_local() if result.status == "SENT" else None
    if result.status == "SENT":
        item.last_notified_at = notification.sent_at
    return notification


def validate_worklog_dates(
    db: Session,
    user_id: int,
    start_date: date,
    end_date: date,
    exclude_worklog_id: int | None = None,
) -> None:
    """校验工时日期，并阻止同一人员所有项目的日期区间重叠。"""
    if end_date < start_date:
        raise HTTPException(400, "DATE_RANGE_INVALID")
    if (start_date.year, start_date.month) != (end_date.year, end_date.month):
        raise HTTPException(400, "DATE_RANGE_CROSSES_MONTH")

    query = select(Worklog).where(
        Worklog.user_id == user_id,
        Worklog.start_date <= end_date,
        Worklog.end_date >= start_date,
    )
    if exclude_worklog_id is not None:
        query = query.where(Worklog.id != exclude_worklog_id)
    conflict = db.scalar(query.order_by(Worklog.start_date.asc(), Worklog.id.asc()))
    if conflict:
        raise HTTPException(409, "WORKLOG_DATE_OVERLAP")


def worklog_workday_count(start_date: date, end_date: date) -> int:
    """计算包含首尾日期的工作日数量；当前工作日规则为周一至周五。"""
    if end_date < start_date:
        return 0
    return sum(
        (start_date + timedelta(days=offset)).weekday() < 5
        for offset in range((end_date - start_date).days + 1)
    )


def validate_worklog_quantity(start_date: date, end_date: date, quantity: int) -> None:
    """校验工时天数为日期区间内的工作日数量，禁止周末、小数或手工填写不一致的天数。"""
    expected_days = worklog_workday_count(start_date, end_date)
    if expected_days == 0:
        raise HTTPException(400, "WORKLOG_NO_WORKDAY")
    if quantity != expected_days:
        raise HTTPException(400, "WORKLOG_QUANTITY_MISMATCH")


def validate_worklog_options(db: Session, stage: str, work_type: str, work_status: str) -> None:
    validate_config_option(db, "project_stage", stage)
    validate_config_option(db, "work_type", work_type)
    validate_config_option(db, "work_status", work_status)


def task_view(db: Session, task: ApprovalTask) -> ApprovalTaskView:
    """组装审批任务、工时快照和最近通知。"""
    item = db.get(Worklog, task.worklog_id)
    notification = db.scalar(select(Notification).where(Notification.approval_task_id == task.id).order_by(Notification.id.desc()))
    return ApprovalTaskView(id=task.id, worklog_id=task.worklog_id, version=task.version, serial_no=task.serial_no, submitter_user_id=task.submitter_user_id, approver_user_id=task.approver_user_id, status=task.status, comment=task.comment, submitted_at=task.submitted_at, processed_at=task.processed_at, processed_by=task.processed_by, worklog=worklog_view(item), notification=NotificationView.model_validate(notification) if notification else None)


def submit_item(db: Session, item: Worklog, user: User) -> ApprovalTaskView:
    """提交单条工时，生成独立审批版本并发送飞书提醒。"""
    if item.user_id != user.id:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    if item.status not in ["DRAFT", "REJECTED"]:
        raise HTTPException(409, "WORKLOG_READ_ONLY")
    validate_worklog_dates(db, item.user_id, item.start_date, item.end_date, item.id)
    validate_worklog_quantity(item.start_date, item.end_date, item.quantity)
    validate_worklog_options(db, item.stage, item.work_type, item.work_status)
    project = db.get(Project, item.project_id)
    if not project or not project.allow_worklog or project.status != "ACTIVE":
        raise HTTPException(400, "PROJECT_NOT_FILLABLE")
    approver = resolve_approver(db, project, user)
    old_status = item.status
    item.status = "PENDING_APPROVAL"
    item.approver_user_id = approver.id
    item.approver_name_snapshot = approver.name
    item.approval_version = max(item.approval_version, 0) + 1
    item.submitted_at = now_local()
    item.rejection_reason = None
    item.approval_comment = None
    db.flush()
    task = ApprovalTask(worklog_id=item.id, version=item.approval_version, serial_no=f"WL-{item.submitted_at:%Y%m%d}-{item.id:04d}-V{item.approval_version}", submitter_user_id=item.user_id, approver_user_id=approver.id, status="PENDING", submitted_at=item.submitted_at)
    db.add(task)
    db.flush()
    audit(db, "approval_task", task.id, "SUBMIT", user.id, old_status, "PENDING_APPROVAL")
    notify_task(db, task, item, approver, user)
    db.commit()
    db.refresh(task)
    return task_view(db, task)


def oauth_secret() -> str:
    return session_secret()


@app.get("/api/v1/auth/config")
def auth_config(request: Request) -> dict[str, object]:
    app_mode = feishu.mode == "app"
    configured = bool(feishu.app_id and feishu.app_secret and oauth_secret())
    authenticated = bool(session_user_id.get())
    return {"mode": feishu.mode, "auth_app_id": feishu.app_id if app_mode else None, "feishu_login_enabled": app_mode and configured, "auth_required": app_mode and not authenticated, "authenticated": authenticated}


@app.post("/api/v1/auth/feishu/exchange")
def feishu_auth_exchange(payload: AuthCodeRequest, request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    if feishu.mode != "app" or not feishu.app_id or not feishu.app_secret or not oauth_secret():
        raise HTTPException(503, "FEISHU_OAUTH_NOT_CONFIGURED")
    try:
        profile = feishu.exchange_oauth_code(payload.code)
    except RuntimeError:
        raise HTTPException(401, "FEISHU_OAUTH_FAILED") from None
    user = ensure_oauth_user(db, profile)
    if user.employment_status != "ACTIVE":
        raise HTTPException(403, "FEISHU_USER_INACTIVE")
    if initialize_first_feishu_admin(db, user):
        db.commit()
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["login_at"] = int(time.time())
    return {
        "ok": True,
        "user_id": user.id,
        "access_token": issue_auth_token(user.id),
        "expires_in": auth_token_max_age(),
    }


@app.post("/api/v1/auth/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "work-hours-api", "product": "综合项目管理系统", "version": API_VERSION}


@app.get("/api/v1/me", response_model=UserView)
def get_me(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> UserView:
    user = current_user(db, x_demo_user_id)
    department = db.get(Department, user.department_id)
    roles = ["EMPLOYEE", "REPORT_VIEWER"]
    permissions = sorted(user_admin_permissions(db, user.id))
    if user.id in system_admin_user_ids(db):
        roles.append("SYSTEM_ADMIN")
    elif permissions:
        roles.append("ADMIN")
    details = effective_permission_details(db, user.id)
    menu_map = {item.code: item for item in db.scalars(select(Menu).where(Menu.is_active.is_(True))).all()}
    permission_menus = [
        EffectivePermissionMenu(
            menu_code=code,
            label=menu_map[code].label if code in menu_map else code,
            route=menu_map[code].route if code in menu_map else None,
            actions=value["actions"],
            scope_type=value.get("scope_type"),
            scope_department_id=value.get("scope_department_id"),
            source_roles=value.get("source_roles", []),
        )
        for code, value in details.items()
    ]
    return UserView(id=user.id, name=user.name, department_name=department.name if department else "未分配", roles=roles, management_permissions=permissions, permission_menus=permission_menus, data_scopes={code: str(value.get("scope_type")) for code, value in details.items() if value.get("scope_type")}, is_system_admin=user.id in system_admin_user_ids(db))


@app.get("/api/v1/demo/users")
def list_demo_users(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [org_user_view(db, user).model_dump() for user in db.scalars(select(User).where(User.employment_status == "ACTIVE").order_by(User.id)).all()]


@app.get("/api/v1/org/users", response_model=list[OrgUserView])
def list_org_users(keyword: str | None = None, active_only: bool = True, db: Session = Depends(get_db)) -> list[OrgUserView]:
    """返回飞书组织架构同步到本地的用户，供所有项目人员字段选择。"""
    query = select(User).order_by(User.name, User.id)
    if active_only:
        query = query.where(User.employment_status == "ACTIVE")
    if keyword:
        query = query.where(User.name.contains(keyword) | User.email.contains(keyword))
    return [org_user_view(db, user) for user in db.scalars(query).all()]


@app.get("/api/v1/org/departments", response_model=list[OrgDepartmentView])
def list_org_departments(active_only: bool = True, db: Session = Depends(get_db)) -> list[OrgDepartmentView]:
    """返回飞书组织架构同步到本地的部门，供项目部门字段选择。"""
    query = select(Department).order_by(Department.name, Department.id)
    if active_only:
        query = query.where(Department.is_active.is_(True))
    items = db.scalars(query).all()
    index = DepartmentIndex(db.scalars(select(Department)).all())
    return [
        OrgDepartmentView(
            id=item.id,
            feishu_department_id=item.feishu_department_id,
            name=item.name,
            parent_name=item.parent_name,
            parent_id=index.by_feishu_id.get(item.parent_feishu_department_id).id if item.parent_feishu_department_id and index.by_feishu_id.get(item.parent_feishu_department_id) else None,
            path=index.path(item.id),
            is_active=item.is_active,
        )
        for item in items
    ]


@app.post("/api/v1/org/sync", response_model=OrgSyncView)
def sync_org_users(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> OrgSyncView:
    """同步飞书组织用户和部门；失败时保留已有本地组织快照。"""
    require_admin_permission(db, "integrations", x_demo_user_id)
    require_access(db, "integrations", "SYNC", x_demo_user_id)
    started_at = time.perf_counter()
    if feishu.mode == "mock":
        synced_at = now_local()
        user_count = len(db.scalars(select(User).where(User.employment_status == "ACTIVE")).all())
        department_count = len(db.scalars(select(Department)).all())
        db.add(OrgSyncLog(status="MOCK", mode="mock", user_count=user_count, department_count=department_count, duration_ms=round((time.perf_counter() - started_at) * 1000)))
        db.commit()
        return OrgSyncView(status="MOCK", mode="mock", user_count=user_count, department_count=department_count, synced_at=synced_at)
    try:
        directory_departments, directory_users = feishu.fetch_directory()
    except RuntimeError as exc:
        message = str(exc)
        code, _, detail = message.partition(":")
        db.add(OrgSyncLog(status="FAILED", mode=feishu.mode, error_message=detail or message, duration_ms=round((time.perf_counter() - started_at) * 1000)))
        db.commit()
        raise HTTPException(503, code if code in ["FEISHU_DIRECTORY_NOT_CONFIGURED", "FEISHU_DIRECTORY_SYNC_FAILED"] else "FEISHU_DIRECTORY_SYNC_FAILED") from exc
    existing_user_ids = {item.feishu_user_id for item in db.scalars(select(User)).all()}
    existing_department_ids = {item.feishu_department_id for item in db.scalars(select(Department)).all()}
    added_user_count = 0
    updated_user_count = 0
    added_department_count = 0
    updated_department_count = 0
    db.query(User).update({User.employment_status: "INACTIVE"}, synchronize_session=False)
    db.query(Department).update({Department.is_active: False}, synchronize_session=False)
    departments_by_feishu_id: dict[str, Department] = {}
    for record in directory_departments:
        department = db.scalar(select(Department).where(Department.feishu_department_id == record.feishu_department_id))
        if not department:
            department = Department(feishu_department_id=record.feishu_department_id, name=record.name)
            db.add(department)
            added_department_count += 1
        elif record.feishu_department_id in existing_department_ids:
            updated_department_count += 1
        department.name = record.name
        department.parent_feishu_department_id = record.parent_department_id
        department.parent_name = record.parent_name
        department.is_active = record.is_active
        departments_by_feishu_id[record.feishu_department_id] = department
    db.flush()
    for record in directory_users:
        department = None
        if record.department_id:
            department = departments_by_feishu_id.get(record.department_id) or db.scalar(select(Department).where(Department.feishu_department_id == record.department_id))
            if not department:
                department = Department(feishu_department_id=record.department_id, name=record.department_name or record.department_id)
                db.add(department)
                db.flush()
            elif record.department_name:
                department.name = record.department_name
            department.is_active = True
        user = db.scalar(select(User).where(User.feishu_user_id == record.feishu_user_id))
        if not user:
            user = User(feishu_user_id=record.feishu_user_id, open_id=record.open_id, name=record.name, email=record.email, department_id=department.id if department else None)
            db.add(user)
            added_user_count += 1
        else:
            updated_user_count += 1
            user.open_id = record.open_id or user.open_id
            user.name = record.name
            user.email = record.email
            user.department_id = department.id if department else user.department_id
        user.employment_status = "ACTIVE" if record.is_active else "INACTIVE"
        user.snapshot_at = now_local()
    synced_at = now_local()
    db.add(OrgSyncLog(status="SUCCESS", mode=feishu.mode, user_count=len(directory_users), department_count=len(directory_departments), added_user_count=added_user_count, updated_user_count=updated_user_count, added_department_count=added_department_count, updated_department_count=updated_department_count, duration_ms=round((time.perf_counter() - started_at) * 1000)))
    db.commit()
    return OrgSyncView(status="SUCCESS", mode=feishu.mode, user_count=len(directory_users), department_count=len(directory_departments), synced_at=synced_at)


def role_view(db: Session, role: Role) -> RoleView:
    """组装角色摘要，附带当前授权人员数和菜单数。"""
    user_count = int(db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id, UserRole.is_active.is_(True))) or 0)
    menu_count = int(db.scalar(select(func.count()).select_from(RolePermission).where(RolePermission.role_id == role.id)) or 0)
    return RoleView(id=role.id, code=role.code, name=role.name, description=role.description, is_builtin=role.is_builtin, is_active=role.is_active, user_count=user_count, menu_count=menu_count)


def menu_view(menu: Menu) -> MenuView:
    """将菜单实体转换为权限配置资源。"""
    return MenuView(id=menu.id, code=menu.code, parent_id=menu.parent_id, label=menu.label, route=menu.route, sort_order=menu.sort_order, is_active=menu.is_active, actions=_json_list(menu.actions))


def validate_scope_input(db: Session, scope: DataScopeInput) -> None:
    """验证数据范围中的部门确实来自启用的飞书组织快照。"""
    if scope.scope_type == "DEPARTMENT_AND_CHILDREN" and scope.department_id:
        active_org_department(db, scope.department_id)


def role_permissions_view(db: Session, role: Role) -> RolePermissionsView:
    """读取角色的菜单操作和默认数据范围配置。"""
    menus = {item.id: item for item in db.scalars(select(Menu)).all()}
    permission_rows = db.scalars(select(RolePermission).where(RolePermission.role_id == role.id).order_by(RolePermission.id)).all()
    permissions = [RolePermissionInput(menu_code=menus[item.menu_id].code, actions=_json_list(item.actions)) for item in permission_rows if item.menu_id in menus and _json_list(item.actions)]
    scopes = [DataScopeInput(resource=item.resource, scope_type=item.scope_type, department_id=item.department_id) for item in db.scalars(select(RoleDataScope).where(RoleDataScope.role_id == role.id).order_by(RoleDataScope.id)).all()]
    return RolePermissionsView(role_id=role.id, permissions=permissions, scopes=scopes)


def user_role_view(db: Session, user: User) -> UserRoleView:
    """组装人员角色授权行，并实时显示最终数据范围。"""
    roles = active_rbac_roles(db, user.id)
    index = DepartmentIndex(db.scalars(select(Department)).all())
    details = effective_permission_details(db, user.id)
    scopes = {resource: str(value.get("scope_type")) for resource, value in details.items() if value.get("scope_type")}
    return UserRoleView(
        id=user.id,
        user_id=user.id,
        user_name=user.name,
        department_name=index.path(user.department_id).split(" / ")[-1] if user.department_id else "未分配部门",
        department_path=index.path(user.department_id),
        employment_status=user.employment_status,
        role_ids=[role.id for role in roles],
        role_names=[role.name for role in roles],
        data_scopes=scopes,
        is_system_admin=user.id in system_admin_user_ids(db),
    )


@app.get("/api/v1/admin/menus", response_model=list[MenuView])
def list_admin_menus(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[MenuView]:
    """返回菜单树和每个菜单支持的业务操作码。"""
    require_admin_permission(db, "admins", x_demo_user_id)
    return [menu_view(item) for item in db.scalars(select(Menu).where(Menu.is_active.is_(True)).order_by(Menu.sort_order, Menu.id)).all()]


@app.get("/api/v1/admin/roles", response_model=RoleList)
def list_roles(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> RoleList:
    """查询全部内置和自定义角色。"""
    require_admin_permission(db, "admins", x_demo_user_id)
    roles = db.scalars(select(Role).order_by(Role.is_builtin.desc(), Role.name, Role.id)).all()
    return RoleList(items=[role_view(db, role) for role in roles], total=len(roles))


@app.post("/api/v1/admin/roles", response_model=RoleView, status_code=201)
def create_role(payload: RoleCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> RoleView:
    """新增可复用的自定义角色。"""
    actor = require_admin_permission(db, "admins", x_demo_user_id, "CONFIGURE")
    if db.scalar(select(Role).where(Role.code == payload.code)):
        raise HTTPException(409, "ROLE_CODE_EXISTS")
    role = Role(code=payload.code, name=payload.name, description=payload.description, is_builtin=False, is_active=payload.is_active)
    db.add(role)
    db.flush()
    db.add(PermissionAudit(actor_id=actor.id, role_id=role.id, action="CREATE_ROLE", after_json=json.dumps(payload.model_dump(), ensure_ascii=False, default=str)))
    db.commit()
    db.refresh(role)
    return role_view(db, role)


@app.get("/api/v1/admin/roles/{role_id}", response_model=RoleView)
def get_role(role_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> RoleView:
    """读取角色基本信息。"""
    require_admin_permission(db, "admins", x_demo_user_id)
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "ROLE_NOT_FOUND")
    return role_view(db, role)


@app.patch("/api/v1/admin/roles/{role_id}", response_model=RoleView)
def update_role(role_id: int, payload: RoleUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> RoleView:
    """修改角色名称、说明和启用状态；内置角色只允许保留启用。"""
    actor = require_admin_permission(db, "admins", x_demo_user_id, "CONFIGURE")
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "ROLE_NOT_FOUND")
    if role.is_builtin and not payload.is_active:
        raise HTTPException(400, "BUILTIN_ROLE_LOCKED")
    before = {"name": role.name, "description": role.description, "is_active": role.is_active}
    role.name = payload.name
    role.description = payload.description
    role.is_active = payload.is_active
    db.add(PermissionAudit(actor_id=actor.id, role_id=role.id, action="UPDATE_ROLE", before_json=json.dumps(before, ensure_ascii=False), after_json=json.dumps(payload.model_dump(), ensure_ascii=False)))
    db.commit()
    db.refresh(role)
    return role_view(db, role)


@app.delete("/api/v1/admin/roles/{role_id}")
def delete_role(role_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """停用自定义角色，不删除授权和审计历史。"""
    actor = require_admin_permission(db, "admins", x_demo_user_id, "CONFIGURE")
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "ROLE_NOT_FOUND")
    if role.is_builtin:
        raise HTTPException(400, "BUILTIN_ROLE_LOCKED")
    role.is_active = False
    db.add(PermissionAudit(actor_id=actor.id, role_id=role.id, action="DISABLE_ROLE", before_json=json.dumps({"is_active": True}), after_json=json.dumps({"is_active": False})))
    db.commit()
    return {"deleted": True, "role_id": role.id}


@app.get("/api/v1/admin/roles/{role_id}/permissions", response_model=RolePermissionsView)
def get_role_permissions(role_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> RolePermissionsView:
    """读取角色菜单操作和默认数据范围。"""
    require_admin_permission(db, "admins", x_demo_user_id)
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "ROLE_NOT_FOUND")
    return role_permissions_view(db, role)


@app.patch("/api/v1/admin/roles/{role_id}/permissions", response_model=RolePermissionsView)
def update_role_permissions(role_id: int, payload: RolePermissionsUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> RolePermissionsView:
    """保存角色菜单操作和默认数据范围，空操作表示取消该资源授权。"""
    actor = require_admin_permission(db, "admins", x_demo_user_id, "CONFIGURE")
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "ROLE_NOT_FOUND")
    if role.is_builtin:
        raise HTTPException(400, "BUILTIN_ROLE_LOCKED")
    menus = {item.code: item for item in db.scalars(select(Menu).where(Menu.is_active.is_(True))).all()}
    before = role_permissions_view(db, role).model_dump()
    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete(synchronize_session=False)
    for item in payload.permissions:
        menu = menus.get(item.menu_code)
        if not menu:
            raise HTTPException(400, "INVALID_MENU")
        actions = sorted(set(item.actions), key=lambda value: RBAC_ACTIONS.index(value) if value in RBAC_ACTIONS else len(RBAC_ACTIONS))
        if any(action not in _json_list(menu.actions) for action in actions):
            raise HTTPException(400, "INVALID_MENU_ACTION")
        if actions:
            db.add(RolePermission(role_id=role.id, menu_id=menu.id, actions=json.dumps(actions)))
    db.query(RoleDataScope).filter(RoleDataScope.role_id == role.id).delete(synchronize_session=False)
    for scope in payload.scopes:
        if scope.resource not in menus:
            raise HTTPException(400, "INVALID_SCOPE_RESOURCE")
        validate_scope_input(db, scope)
        db.add(RoleDataScope(role_id=role.id, resource=scope.resource, scope_type=scope.scope_type, department_id=scope.department_id))
    db.add(PermissionAudit(actor_id=actor.id, role_id=role.id, action="UPDATE_ROLE_PERMISSIONS", before_json=json.dumps(before, ensure_ascii=False, default=str), after_json=json.dumps(payload.model_dump(), ensure_ascii=False, default=str)))
    db.commit()
    return role_permissions_view(db, role)


@app.get("/api/v1/admin/user-roles", response_model=UserRoleList)
def list_user_roles(keyword: str | None = None, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> UserRoleList:
    """查询已同步的组织人员及其有效角色；人员姓名只能来自飞书组织快照。"""
    require_admin_permission(db, "admins", x_demo_user_id)
    query = select(User).where(User.employment_status == "ACTIVE").order_by(User.name, User.id)
    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(User.name.contains(value) | User.email.contains(value))
    users = db.scalars(query).all()
    return UserRoleList(items=[user_role_view(db, user) for user in users], total=len(users))


@app.put("/api/v1/admin/users/{user_id}/roles", response_model=UserRoleView)
def update_user_roles(user_id: int, payload: UserRoleUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> UserRoleView:
    """保存人员多角色授权和范围覆盖，下一次请求立即生效。"""
    actor = require_admin_permission(db, "admins", x_demo_user_id, "CONFIGURE")
    target = db.get(User, user_id)
    if not target or target.employment_status != "ACTIVE":
        raise HTTPException(404, "USER_NOT_FOUND")
    roles = db.scalars(select(Role).where(Role.id.in_(payload.role_ids), Role.is_active.is_(True))).all() if payload.role_ids else []
    if len(roles) != len(set(payload.role_ids)):
        raise HTTPException(400, "ROLE_NOT_ACTIVE")
    before = user_role_view(db, target).model_dump()
    db.query(UserRoleScope).filter(UserRoleScope.user_id == target.id).delete(synchronize_session=False)
    db.query(UserRole).filter(UserRole.user_id == target.id).delete(synchronize_session=False)
    for role in roles:
        db.add(UserRole(user_id=target.id, role_id=role.id, is_active=True))
    for scope in payload.scopes:
        if scope.resource not in {item[0] for item in RBAC_MENU_SEED}:
            raise HTTPException(400, "INVALID_SCOPE_RESOURCE")
        validate_scope_input(db, scope)
        for role in roles:
            if db.scalar(select(RoleDataScope.id).where(RoleDataScope.role_id == role.id, RoleDataScope.resource == scope.resource)):
                db.add(UserRoleScope(user_id=target.id, role_id=role.id, resource=scope.resource, scope_type=scope.scope_type, department_id=scope.department_id))
    db.add(PermissionAudit(actor_id=actor.id, target_user_id=target.id, action="UPDATE_USER_ROLES", before_json=json.dumps(before, ensure_ascii=False, default=str), after_json=json.dumps(payload.model_dump(), ensure_ascii=False, default=str)))
    db.commit()
    return user_role_view(db, target)


@app.get("/api/v1/admin/users/{user_id}/effective-permissions", response_model=EffectivePermissionView)
def get_effective_permissions(user_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> EffectivePermissionView:
    """查看人员最终生效权限、数据范围和角色来源。"""
    require_admin_permission(db, "admins", x_demo_user_id)
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "USER_NOT_FOUND")
    details = effective_permission_details(db, target.id)
    menus = {item.code: item for item in db.scalars(select(Menu).where(Menu.is_active.is_(True))).all()}
    return EffectivePermissionView(
        user_id=target.id,
        user_name=target.name,
        roles=[role_view(db, role) for role in active_rbac_roles(db, target.id)],
        menus=[EffectivePermissionMenu(menu_code=code, label=menus[code].label if code in menus else code, route=menus[code].route if code in menus else None, actions=value["actions"], scope_type=value.get("scope_type"), scope_department_id=value.get("scope_department_id"), source_roles=value.get("source_roles", [])) for code, value in sorted(details.items(), key=lambda entry: menus.get(entry[0]).sort_order if menus.get(entry[0]) else 999)],
        data_scopes={code: str(value.get("scope_type")) for code, value in details.items() if value.get("scope_type")},
    )


@app.get("/api/v1/auth/me/permissions", response_model=EffectivePermissionView)
def get_my_effective_permissions(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> EffectivePermissionView:
    """返回当前用户的菜单、操作和数据范围，供前端隐藏管理菜单及业务按钮。"""
    user = current_user(db, x_demo_user_id)
    details = effective_permission_details(db, user.id)
    menus = {item.code: item for item in db.scalars(select(Menu).where(Menu.is_active.is_(True))).all()}
    return EffectivePermissionView(user_id=user.id, user_name=user.name, roles=[role_view(db, role) for role in active_rbac_roles(db, user.id)], menus=[EffectivePermissionMenu(menu_code=code, label=menus[code].label if code in menus else code, route=menus[code].route if code in menus else None, actions=value["actions"], scope_type=value.get("scope_type"), scope_department_id=value.get("scope_department_id"), source_roles=value.get("source_roles", [])) for code, value in details.items()], data_scopes={code: str(value.get("scope_type")) for code, value in details.items() if value.get("scope_type")})


def config_catalog(db: Session, active_only: bool) -> ConfigOptionCatalog:
    options = {
        category: [ConfigOptionView.model_validate(item) for item in config_option_rows(db, category, active_only)]
        for category in CONFIG_CATEGORY_LABELS
    }
    return ConfigOptionCatalog(options=options)


@app.get("/api/v1/config/options", response_model=ConfigOptionCatalog)
def list_config_options(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ConfigOptionCatalog:
    """读取启用中的业务下拉选项，供业务表单使用。"""
    current_user(db, x_demo_user_id)
    return config_catalog(db, active_only=True)


@app.get("/api/v1/admin/config/options", response_model=ConfigOptionCatalog)
def list_admin_config_options(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ConfigOptionCatalog:
    require_admin_permission(db, "configuration", x_demo_user_id)
    return config_catalog(db, active_only=False)


def config_option_usage_count(db: Session, option: ConfigOption) -> int:
    if option.category == "project_type":
        return int(db.scalar(select(func.count(Project.id)).where(Project.project_type == option.value)) or 0)
    if option.category == "project_stage":
        return int(db.scalar(select(func.count(Worklog.id)).where(Worklog.stage == option.value)) or 0)
    if option.category == "work_type":
        return int(db.scalar(select(func.count(Worklog.id)).where(Worklog.work_type == option.value)) or 0)
    if option.category == "work_status":
        return int(db.scalar(select(func.count(Worklog.id)).where(Worklog.work_status == option.value)) or 0)
    if option.category == "project_status":
        return int(db.scalar(select(func.count(Project.id)).where(Project.status == option.value)) or 0)
    return 0


@app.post("/api/v1/admin/config/options", response_model=ConfigOptionView, status_code=201)
def create_config_option(payload: ConfigOptionCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ConfigOptionView:
    admin = require_admin_permission(db, "configuration", x_demo_user_id)
    require_access(db, "configuration", "CREATE", x_demo_user_id)
    if payload.category not in CONFIG_CATEGORY_LABELS:
        raise HTTPException(400, "INVALID_CONFIG_CATEGORY")
    duplicate = db.scalar(select(ConfigOption).where(ConfigOption.category == payload.category, ConfigOption.value == payload.value))
    if duplicate:
        raise HTTPException(409, "CONFIG_OPTION_EXISTS")
    option = ConfigOption(category=payload.category, value=payload.value, label=payload.label, sort_order=payload.sort_order, is_active=payload.is_active, is_builtin=False)
    db.add(option)
    db.flush()
    audit(db, "config_option", option.id, "CREATE", admin.id, None, option.label)
    db.commit()
    db.refresh(option)
    return ConfigOptionView.model_validate(option)


@app.patch("/api/v1/admin/config/options/{option_id}", response_model=ConfigOptionView)
def update_config_option(option_id: int, payload: ConfigOptionUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ConfigOptionView:
    admin = require_admin_permission(db, "configuration", x_demo_user_id)
    require_access(db, "configuration", "EDIT", x_demo_user_id)
    option = db.get(ConfigOption, option_id)
    if not option:
        raise HTTPException(404, "CONFIG_OPTION_NOT_FOUND")
    if not payload.is_active and config_option_usage_count(db, option):
        raise HTTPException(409, "CONFIG_OPTION_IN_USE")
    old_label = option.label
    option.label = payload.label
    option.sort_order = payload.sort_order
    option.is_active = payload.is_active
    audit(db, "config_option", option.id, "UPDATE", admin.id, old_label, option.label)
    db.commit()
    db.refresh(option)
    return ConfigOptionView.model_validate(option)


@app.delete("/api/v1/admin/config/options/{option_id}")
def delete_config_option(option_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    admin = require_admin_permission(db, "configuration", x_demo_user_id)
    require_access(db, "configuration", "DELETE", x_demo_user_id)
    option = db.get(ConfigOption, option_id)
    if not option:
        raise HTTPException(404, "CONFIG_OPTION_NOT_FOUND")
    if option.is_builtin:
        raise HTTPException(409, "BUILTIN_CONFIG_OPTION_DISABLE_ONLY")
    if config_option_usage_count(db, option):
        raise HTTPException(409, "CONFIG_OPTION_IN_USE")
    db.delete(option)
    audit(db, "config_option", option_id, "DELETE", admin.id, option.label, None)
    db.commit()
    return {"deleted": True, "option_id": option_id}


@app.get("/api/v1/customers", response_model=list[CustomerView])
def list_customers(active_only: bool = True, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[CustomerView]:
    current_user(db, x_demo_user_id)
    query = select(Customer).order_by(Customer.name, Customer.id)
    if active_only:
        query = query.where(Customer.status == "ACTIVE")
    return [CustomerView.model_validate(item) for item in db.scalars(query).all()]


@app.post("/api/v1/customers", response_model=CustomerView, status_code=201)
def create_customer(payload: CustomerCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> CustomerView:
    admin = require_admin_permission(db, "counterparties", x_demo_user_id)
    require_access(db, "counterparties", "CREATE", x_demo_user_id)
    if db.scalar(select(Customer).where(Customer.name == payload.name)):
        raise HTTPException(409, "CUSTOMER_EXISTS")
    values = payload.model_dump(exclude={"code"})
    customer = Customer(code=generate_counterparty_code(db, Customer, "CUS"), **values)
    db.add(customer)
    db.flush()
    audit(db, "customer", customer.id, "CREATE", admin.id, None, customer.status)
    db.commit()
    db.refresh(customer)
    return CustomerView.model_validate(customer)


@app.patch("/api/v1/customers/{customer_id}", response_model=CustomerView)
def update_customer(customer_id: int, payload: CustomerUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> CustomerView:
    admin = require_admin_permission(db, "counterparties", x_demo_user_id)
    require_access(db, "counterparties", "EDIT", x_demo_user_id)
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "CUSTOMER_NOT_FOUND")
    duplicate = db.scalar(select(Customer).where(Customer.name == payload.name, Customer.id != customer.id))
    if duplicate:
        raise HTTPException(409, "CUSTOMER_EXISTS")
    old_status = customer.status
    for key, value in payload.model_dump(exclude={"code"}).items():
        setattr(customer, key, value)
    audit(db, "customer", customer.id, "UPDATE", admin.id, old_status, customer.status)
    db.commit()
    db.refresh(customer)
    return CustomerView.model_validate(customer)


@app.delete("/api/v1/customers/{customer_id}")
def delete_customer(customer_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    admin = require_admin_permission(db, "counterparties", x_demo_user_id)
    require_access(db, "counterparties", "DELETE", x_demo_user_id)
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "CUSTOMER_NOT_FOUND")
    if db.scalar(select(Project.id).where(Project.customer_id == customer.id, Project.status != "DELETED")):
        raise HTTPException(409, "CUSTOMER_IN_USE")
    old_status = customer.status
    customer.status = "INACTIVE"
    audit(db, "customer", customer.id, "DELETE", admin.id, old_status, "INACTIVE")
    db.commit()
    return {"deleted": True, "customer_id": customer.id}


@app.get("/api/v1/suppliers", response_model=list[SupplierView])
def list_suppliers(active_only: bool = True, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[SupplierView]:
    current_user(db, x_demo_user_id)
    query = select(Supplier).order_by(Supplier.name, Supplier.id)
    if active_only:
        query = query.where(Supplier.status == "ACTIVE")
    return [SupplierView.model_validate(item) for item in db.scalars(query).all()]


@app.post("/api/v1/suppliers", response_model=SupplierView, status_code=201)
def create_supplier(payload: SupplierCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> SupplierView:
    admin = require_admin_permission(db, "counterparties", x_demo_user_id)
    require_access(db, "counterparties", "CREATE", x_demo_user_id)
    if db.scalar(select(Supplier).where(Supplier.name == payload.name)):
        raise HTTPException(409, "SUPPLIER_EXISTS")
    values = payload.model_dump(exclude={"code"})
    supplier = Supplier(code=generate_counterparty_code(db, Supplier, "SUP"), **values)
    db.add(supplier)
    db.flush()
    audit(db, "supplier", supplier.id, "CREATE", admin.id, None, supplier.status)
    db.commit()
    db.refresh(supplier)
    return SupplierView.model_validate(supplier)


@app.patch("/api/v1/suppliers/{supplier_id}", response_model=SupplierView)
def update_supplier(supplier_id: int, payload: SupplierUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> SupplierView:
    admin = require_admin_permission(db, "counterparties", x_demo_user_id)
    require_access(db, "counterparties", "EDIT", x_demo_user_id)
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "SUPPLIER_NOT_FOUND")
    duplicate = db.scalar(select(Supplier).where(Supplier.name == payload.name, Supplier.id != supplier.id))
    if duplicate:
        raise HTTPException(409, "SUPPLIER_EXISTS")
    old_status = supplier.status
    for key, value in payload.model_dump(exclude={"code"}).items():
        setattr(supplier, key, value)
    audit(db, "supplier", supplier.id, "UPDATE", admin.id, old_status, supplier.status)
    db.commit()
    db.refresh(supplier)
    return SupplierView.model_validate(supplier)


@app.delete("/api/v1/suppliers/{supplier_id}")
def delete_supplier(supplier_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    admin = require_admin_permission(db, "counterparties", x_demo_user_id)
    require_access(db, "counterparties", "DELETE", x_demo_user_id)
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "SUPPLIER_NOT_FOUND")
    if db.scalar(select(Contract.id).where(Contract.counterparty_type == "SUPPLIER", Contract.counterparty_id == supplier.id, Contract.status != "TERMINATED")):
        raise HTTPException(409, "SUPPLIER_IN_USE")
    old_status = supplier.status
    supplier.status = "INACTIVE"
    audit(db, "supplier", supplier.id, "DELETE", admin.id, old_status, "INACTIVE")
    db.commit()
    return {"deleted": True, "supplier_id": supplier.id}


async def _preview_import_endpoint(resource: str, file: UploadFile, x_demo_user_id: int | None, db: Session) -> dict[str, object]:
    """执行导入预览；只读取和校验文件，不写入业务数据。"""
    permission = "counterparties" if resource in {"customers", "suppliers"} else "contracts"
    user = require_access(db, permission, "VIEW", x_demo_user_id)
    preview, _ = await _prepare_import(resource, file, db, user)
    return preview


async def _execute_import_endpoint(resource: str, file: UploadFile, x_demo_user_id: int | None, db: Session) -> dict[str, object]:
    """在完整校验通过后一次性导入，任一数据库异常都会整体回滚。"""
    permission = "counterparties" if resource in {"customers", "suppliers"} else "contracts"
    user = require_access(db, permission, "CREATE", x_demo_user_id)
    preview, payloads = await _prepare_import(resource, file, db, user)
    errors = preview["errors"]
    if errors:
        raise HTTPException(422, detail=errors)
    model = Customer if resource == "customers" else Supplier if resource == "suppliers" else Contract
    try:
        for payload in payloads:
            if resource == "contracts":
                item = Contract(**payload)
                db.add(item)
                db.flush()
                audit(db, "contract", item.id, "CREATE", user.id, None, item.status)
            else:
                prefix = "CUS" if resource == "customers" else "SUP"
                item = model(code=generate_counterparty_code(db, model, prefix), **payload)
                db.add(item)
                db.flush()
                audit(db, "customer" if resource == "customers" else "supplier", item.id, "CREATE", user.id, None, item.status)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(409, "导入数据写入失败，未导入任何记录") from exc
    return {"resource": resource, "filename": preview["filename"], "imported": len(payloads), "skipped": 0}


@app.post("/api/v1/imports/customers/preview")
async def preview_customer_import(file: UploadFile = File(...), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    return await _preview_import_endpoint("customers", file, x_demo_user_id, db)


@app.post("/api/v1/imports/customers")
async def execute_customer_import(file: UploadFile = File(...), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    return await _execute_import_endpoint("customers", file, x_demo_user_id, db)


@app.post("/api/v1/imports/suppliers/preview")
async def preview_supplier_import(file: UploadFile = File(...), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    return await _preview_import_endpoint("suppliers", file, x_demo_user_id, db)


@app.post("/api/v1/imports/suppliers")
async def execute_supplier_import(file: UploadFile = File(...), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    return await _execute_import_endpoint("suppliers", file, x_demo_user_id, db)


@app.post("/api/v1/imports/contracts/preview")
async def preview_contract_import(file: UploadFile = File(...), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    return await _preview_import_endpoint("contracts", file, x_demo_user_id, db)


@app.post("/api/v1/imports/contracts")
async def execute_contract_import(file: UploadFile = File(...), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    return await _execute_import_endpoint("contracts", file, x_demo_user_id, db)


@app.get("/api/v1/projects", response_model=list[ProjectView])
def list_projects(keyword: str | None = None, allow_worklog: bool | None = None, include_deleted: bool = False, db: Session = Depends(get_db)) -> list[ProjectView]:
    query = select(Project).order_by(Project.updated_at.desc())
    if not include_deleted:
        query = query.where(Project.status != "DELETED")
    if keyword:
        query = query.where(Project.name.contains(keyword) | Project.code.contains(keyword))
    if allow_worklog is not None:
        query = query.where(Project.allow_worklog == allow_worklog)
    return [project_view(db, item) for item in db.scalars(query).all()]


@app.get("/api/v1/projects/page", response_model=ProjectList)
def list_projects_page(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = None,
    project_type: str | None = None,
    status: str | None = None,
    department_id: int | None = Query(default=None, gt=0),
    owner_user_id: int | None = Query(default=None, gt=0),
    customer_id: int | None = Query(default=None, gt=0),
    data_scope: str = Query(default="OWNED", pattern="^(OWNED|ALL)$"),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ProjectList:
    """v3.0 项目主列表：服务端分页、组织树筛选和权限数据范围。"""
    user = require_access(db, "projects", "VIEW", x_demo_user_id)
    query = select(Project).where(Project.status != "DELETED")
    department_index = DepartmentIndex(db.scalars(select(Department)).all())
    system_admin = user.id in system_admin_user_ids(db)

    if data_scope == "OWNED":
        query = query.where(Project.owner_user_id == user.id)
    elif not system_admin:
        scope = project_scope_ids(db, user, "projects")
        if scope is not None:
            query = query.where(Project.id.in_(scope))

    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(Project.name.contains(value) | Project.code.contains(value))
    if project_type:
        query = query.where(Project.project_type == project_type)
    if status:
        query = query.where(Project.status == status)
    if department_id:
        department_ids = department_index.descendants(department_id)
        if not department_ids:
            raise HTTPException(400, "INVALID_DEPARTMENT")
        query = query.where(Project.department_id.in_(department_ids))
    if owner_user_id:
        query = query.where(Project.owner_user_id == owner_user_id)
    if customer_id:
        query = query.where(Project.customer_id == customer_id)

    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    items = list(db.scalars(query.order_by(Project.updated_at.desc(), Project.id.desc()).offset((page - 1) * page_size).limit(page_size)).all())
    return ProjectList(items=[project_view(db, item) for item in items], total=total, page=page, page_size=page_size, page_count=max(1, (total + page_size - 1) // page_size))


@app.post("/api/v1/projects", response_model=ProjectView, status_code=201)
def create_project(payload: ProjectCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectView:
    """新增项目；所有人员字段必须引用启用的组织用户。"""
    user = require_admin_permission(db, "projects", x_demo_user_id)
    require_access(db, "projects", "CREATE", x_demo_user_id)
    if db.scalar(select(Project).where(Project.code == payload.code)):
        raise HTTPException(409, "PROJECT_CODE_EXISTS")
    validate_config_option(db, "project_type", payload.project_type)
    validate_config_option(db, "project_status", payload.status)
    department = active_org_department(db, payload.department_id)
    project = Project(code=payload.code, name=payload.name, project_type=payload.project_type, owner_name="", department_id=department.id, department_name=department.name, budget_days=payload.budget_days, budget_cost=payload.budget_cost, expense_budget=0, status=payload.status, allow_worklog=payload.allow_worklog)
    apply_project_master_fields(project, db, payload)
    apply_project_users(project, db, payload.owner_user_id, payload.approver_user_id, payload.leader_user_id)
    db.add(project)
    db.flush()
    ensure_project_budget_items(db, project)
    audit(db, "project", project.id, "CREATE", user.id, None, project.status)
    db.commit()
    db.refresh(project)
    return project_view(db, project)


@app.get("/api/v1/admin/budget-item-templates", response_model=list[BudgetItemTemplateView])
def list_budget_item_templates(
    project_category: str | None = Query(default=None, pattern="^(BUSINESS_PROJECT|RND_PROJECT)$"),
    include_inactive: bool = False,
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[BudgetItemTemplateView]:
    """后台基础配置：按经营/研发项目大类维护预算项模板。"""
    require_access(db, "configuration", "VIEW", x_demo_user_id)
    query = select(BudgetItemTemplate)
    if project_category:
        query = query.where(BudgetItemTemplate.project_category == project_category)
    if not include_inactive:
        query = query.where(BudgetItemTemplate.is_active.is_(True))
    rows = db.scalars(query.order_by(BudgetItemTemplate.project_category, BudgetItemTemplate.sort_order, BudgetItemTemplate.id)).all()
    return [BudgetItemTemplateView.model_validate(item) for item in rows]


@app.post("/api/v1/admin/budget-item-templates", response_model=BudgetItemTemplateView, status_code=201)
def create_budget_item_template(payload: BudgetItemTemplateCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> BudgetItemTemplateView:
    """新增预算项模板；后续新建项目自动带入，现有项目可手动初始化缺失项。"""
    user = require_access(db, "configuration", "CREATE", x_demo_user_id)
    base_code = (payload.code or budget_template_code(payload.name, payload.project_category)).strip().upper()
    code = re.sub(r"[^A-Z0-9_]+", "_", base_code).strip("_")[:80] or budget_template_code(payload.name, payload.project_category)
    candidate = code
    sequence = 2
    while db.scalar(select(BudgetItemTemplate.id).where(BudgetItemTemplate.project_category == payload.project_category, BudgetItemTemplate.code == candidate)):
        suffix = f"_{sequence}"
        candidate = f"{code[:80 - len(suffix)]}{suffix}"
        sequence += 1
    template = BudgetItemTemplate(
        project_category=payload.project_category,
        code=candidate,
        name=payload.name.strip(),
        cost_major=payload.cost_major.strip(),
        cost_minor=payload.cost_minor.strip() if payload.cost_minor and payload.cost_minor.strip() else None,
        source_kind=payload.source_kind,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
        is_builtin=False,
    )
    db.add(template)
    db.flush()
    audit(db, "budget_item_template", template.id, "CREATE", user.id, None, "ACTIVE" if template.is_active else "INACTIVE", template.name)
    db.commit()
    db.refresh(template)
    return BudgetItemTemplateView.model_validate(template)


@app.patch("/api/v1/admin/budget-item-templates/{template_id}", response_model=BudgetItemTemplateView)
def update_budget_item_template(template_id: int, payload: BudgetItemTemplateUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> BudgetItemTemplateView:
    """修改预算项模板；不回写已建项目的历史快照，避免改变既有项目口径。"""
    user = require_access(db, "configuration", "EDIT", x_demo_user_id)
    template = db.get(BudgetItemTemplate, template_id)
    if not template:
        raise HTTPException(404, "BUDGET_TEMPLATE_NOT_FOUND")
    old_status = "ACTIVE" if template.is_active else "INACTIVE"
    template.project_category = payload.project_category
    template.name = payload.name.strip()
    template.cost_major = payload.cost_major.strip()
    template.cost_minor = payload.cost_minor.strip() if payload.cost_minor and payload.cost_minor.strip() else None
    template.source_kind = payload.source_kind
    template.sort_order = payload.sort_order
    template.is_active = payload.is_active
    audit(db, "budget_item_template", template.id, "UPDATE", user.id, old_status, "ACTIVE" if template.is_active else "INACTIVE", template.name)
    db.commit()
    db.refresh(template)
    return BudgetItemTemplateView.model_validate(template)


@app.delete("/api/v1/admin/budget-item-templates/{template_id}")
def delete_budget_item_template(template_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """删除未使用模板；若已有项目引用则改为停用，保留历史项目预算项快照。"""
    user = require_access(db, "configuration", "DELETE", x_demo_user_id)
    template = db.get(BudgetItemTemplate, template_id)
    if not template:
        raise HTTPException(404, "BUDGET_TEMPLATE_NOT_FOUND")
    used = bool(db.scalar(select(ProjectBudgetItem.id).where(ProjectBudgetItem.template_id == template.id).limit(1)))
    if used:
        template.is_active = False
        audit(db, "budget_item_template", template.id, "DISABLE", user.id, "ACTIVE", "INACTIVE", template.name)
        db.commit()
        return {"deleted": False, "disabled": True, "template_id": template.id}
    db.delete(template)
    audit(db, "budget_item_template", template.id, "DELETE", user.id, None, None, template.name)
    db.commit()
    return {"deleted": True, "template_id": template_id}


@app.get("/api/v1/projects/{project_id}/budget-items", response_model=list[ProjectBudgetItemView])
def list_project_budget_items(project_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[ProjectBudgetItemView]:
    """读取当前项目预算项，供项目管理操作栏、支出合同和费用单联动使用。"""
    user = require_access(db, "projects", "VIEW", x_demo_user_id)
    project = ensure_project_in_scope(db, user, project_id)
    ensure_project_budget_items(db, project)
    db.commit()
    return project_budget_item_views(db, project.id)


@app.post("/api/v1/projects/{project_id}/budget-items/initialize", response_model=list[ProjectBudgetItemView])
def initialize_project_budget_items(project_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[ProjectBudgetItemView]:
    """按后台模板补齐当前项目缺失的预算项。"""
    user = require_access(db, "projects", "EDIT", x_demo_user_id)
    project = ensure_project_in_scope(db, user, project_id)
    ensure_project_budget_items(db, project)
    audit(db, "project", project.id, "INIT_BUDGET_ITEMS", user.id, None, project.status)
    db.commit()
    return project_budget_item_views(db, project.id)


@app.patch("/api/v1/projects/{project_id}/budget-items/{item_id}", response_model=ProjectBudgetItemView)
def update_project_budget_item(project_id: int, item_id: int, payload: ProjectBudgetItemUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectBudgetItemView:
    """维护项目预算项金额、启用状态和备注；总预算自动由启用项合计。"""
    user = require_access(db, "projects", "EDIT", x_demo_user_id)
    ensure_project_in_scope(db, user, project_id)
    item = db.get(ProjectBudgetItem, item_id)
    if not item or item.project_id != project_id:
        raise HTTPException(404, "PROJECT_BUDGET_ITEM_NOT_FOUND")
    old_status = "ACTIVE" if item.is_active else "INACTIVE"
    item.budget_amount = payload.budget_amount
    item.is_active = payload.is_active
    item.remark = payload.remark.strip() if payload.remark and payload.remark.strip() else None
    project = db.get(Project, project_id)
    if project:
        project.budget_cost = project_budget_total(db, project_id)
    audit(db, "project_budget_item", item.id, "UPDATE", user.id, old_status, "ACTIVE" if item.is_active else "INACTIVE", f"{item.name}：¥{float(item.budget_amount or 0):.2f}")
    db.commit()
    return next(row for row in project_budget_item_views(db, project_id) if row.id == item_id)


@app.get("/api/v1/projects/board", response_model=list[ProjectBoardRow])
def list_project_board(
    keyword: str | None = None,
    project_id: int | None = Query(default=None, gt=0),
    project_type: str | None = None,
    status: str | None = None,
    department_id: int | None = Query(default=None, gt=0),
    owner_user_id: int | None = Query(default=None, gt=0),
    customer_id: int | None = Query(default=None, gt=0),
    data_scope: str = Query(default="OWNED", pattern="^(OWNED|ALL)$"),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[ProjectBoardRow]:
    """项目看板：按项目汇总合同、收付款和毛利，并输出应收应付预警。"""
    user = require_admin_permission(db, "project_board", x_demo_user_id)
    require_access(db, "project_board", "VIEW", x_demo_user_id)
    scope = project_scope_ids(db, user, "project_board")
    query = select(Project).where(Project.status != "DELETED")
    if data_scope == "OWNED":
        query = query.where(Project.owner_user_id == user.id)
    elif scope is not None:
        query = query.where(Project.id.in_(scope))
    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(Project.name.contains(value) | Project.code.contains(value))
    if project_id:
        query = query.where(Project.id == project_id)
    if project_type:
        query = query.where(Project.project_type == project_type)
    if status:
        query = query.where(Project.status == status)
    if department_id:
        index = DepartmentIndex(db.scalars(select(Department)).all())
        department_ids = index.descendants(department_id)
        if not department_ids:
            raise HTTPException(400, "INVALID_DEPARTMENT")
        query = query.where(Project.department_id.in_(department_ids))
    if owner_user_id:
        query = query.where(Project.owner_user_id == owner_user_id)
    if customer_id:
        query = query.where(Project.customer_id == customer_id)
    projects = db.scalars(query.order_by(Project.updated_at.desc(), Project.id.desc())).all()
    index = DepartmentIndex(db.scalars(select(Department)).all())
    rows: list[ProjectBoardRow] = []
    for project in projects:
        finance = project_finance_summary(db, project)
        detail = project_view(db, project)
        warning: str | None = None
        if finance["receivable"] > 0:
            warning = "应收未收"
        elif finance["payable"] > 0:
            warning = "应付未付"
        customer = db.get(Customer, project.customer_id) if project.customer_id else None
        rows.append(
            ProjectBoardRow(
                id=project.id,
                code=project.code,
                name=project.name,
                project_type=project.project_type,
                status=project.status,
                owner_name=project.owner_name or "",
                department_path=index.path(project.department_id),
                customer_name=customer.name if customer else project.customer_name,
                **finance,
                budget_days=detail.budget_days,
                actual_days=detail.actual_days,
                completion_rate=detail.completion_rate,
                budget_cost=detail.budget_cost,
                actual_cost=detail.actual_cost,
                actual_contract_cost=detail.actual_contract_cost,
                actual_expense_cost=detail.actual_expense_cost,
                personnel_cost=detail.personnel_cost,
                remaining_cost=detail.remaining_cost,
                cost_usage_rate=detail.cost_usage_rate,
                personnel_cost_usage_rate=detail.personnel_cost_usage_rate,
                expense_budget=detail.expense_budget,
                expense_budget_remaining=detail.expense_budget_remaining,
                expense_budget_usage_rate=detail.expense_budget_usage_rate,
                execution_status=detail.execution_status,
                cost_execution_status=detail.cost_execution_status,
                warning=warning,
            )
        )
    return rows


@app.get("/api/v1/projects/board/options", response_model=list[ProjectBoardOption])
def list_project_board_options(
    data_scope: str = Query(default="OWNED", pattern="^(OWNED|ALL)$"),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[ProjectBoardOption]:
    """返回项目看板筛选器选项，并严格复用看板的数据访问范围。"""
    user = require_admin_permission(db, "project_board", x_demo_user_id)
    require_access(db, "project_board", "VIEW", x_demo_user_id)
    query = select(Project).where(Project.status != "DELETED")
    if data_scope == "OWNED":
        query = query.where(Project.owner_user_id == user.id)
    else:
        scope = project_scope_ids(db, user, "project_board")
        if scope is not None:
            query = query.where(Project.id.in_(scope))
    projects = db.scalars(query.order_by(Project.updated_at.desc(), Project.id.desc())).all()
    return [
        ProjectBoardOption(
            id=project.id,
            code=project.code,
            name=project.name,
            owner_user_id=project.owner_user_id,
        )
        for project in projects
    ]


@app.get("/api/v1/projects/board/insights", response_model=ProjectBoardInsights)
def project_board_insights(
    keyword: str | None = None,
    project_id: int | None = Query(default=None, gt=0),
    project_type: str | None = None,
    status: str | None = None,
    department_id: int | None = Query(default=None, gt=0),
    owner_user_id: int | None = Query(default=None, gt=0),
    customer_id: int | None = Query(default=None, gt=0),
    data_scope: str = Query(default="OWNED", pattern="^(OWNED|ALL)$"),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ProjectBoardInsights:
    """返回项目看板趋势、应收应付账龄和可下钻预警。"""
    rows = list_project_board(keyword=keyword, project_id=project_id, project_type=project_type, status=status, department_id=department_id, owner_user_id=owner_user_id, customer_id=customer_id, data_scope=data_scope, x_demo_user_id=x_demo_user_id, db=db)
    project_ids = [row.id for row in rows]
    today = today_local()
    month_index = today.year * 12 + today.month - 1
    months: dict[str, dict[str, float]] = {}
    for offset in range(5, -1, -1):
        current_index = month_index - offset
        year, month_zero = divmod(current_index, 12)
        months[f"{year:04d}-{month_zero + 1:02d}"] = {"received": 0.0, "paid": 0.0}
    if project_ids:
        for item in db.scalars(select(Receipt).where(Receipt.project_id.in_(project_ids), Receipt.status == "APPROVED")).all():
            key = f"{item.receipt_date.year:04d}-{item.receipt_date.month:02d}"
            if key in months:
                months[key]["received"] += float(item.amount or 0)
        for item in db.scalars(select(Payment).where(Payment.project_id.in_(project_ids), Payment.status == "APPROVED")).all():
            key = f"{item.payment_date.year:04d}-{item.payment_date.month:02d}"
            if key in months:
                months[key]["paid"] += float(item.amount or 0)

    aging_buckets = [("未到期", None, None), ("0-30天", 0, 30), ("31-60天", 31, 60), ("61-90天", 61, 90), ("90天以上", 91, None), ("未排期", -1, -1)]
    receivable_aging = {name: {"amount": 0.0, "items": []} for name, _, _ in aging_buckets}
    payable_aging = {name: {"amount": 0.0, "items": []} for name, _, _ in aging_buckets}
    warning_items: list[ProjectAnalysisWarningView] = []
    projects = db.scalars(select(Project).where(Project.id.in_(project_ids))).all() if project_ids else []
    for project in projects:
        analysis = project_analysis_view(db, project, today)
        warning_items.extend(analysis.warnings)
        contracts = db.scalars(select(Contract).where(Contract.project_id == project.id, Contract.status != "TERMINATED")).all()
        for contract in contracts:
            stages = db.scalars(select(ContractStage).where(ContractStage.contract_id == contract.id, ContractStage.status != "CANCELLED")).all()
            for stage in stages:
                remaining = stage_remaining(db, stage, contract.contract_type)
                if remaining <= 0:
                    continue
                if not stage.planned_date:
                    bucket = "未排期"
                else:
                    days = (today - stage.planned_date).days
                    if days < 0:
                        bucket = "未到期"
                    elif days <= 30:
                        bucket = "0-30天"
                    elif days <= 60:
                        bucket = "31-60天"
                    elif days <= 90:
                        bucket = "61-90天"
                    else:
                        bucket = "90天以上"
                aging_target = receivable_aging if contract.contract_type == "INCOME" else payable_aging
                aging_target[bucket]["amount"] += remaining
                aging_target[bucket]["items"].append(
                    ProjectBoardAgingItem(
                        project_id=project.id,
                        project_name=project.name,
                        contract_id=contract.id,
                        contract_name=contract.name,
                        stage_id=stage.id,
                        stage_name=stage.name,
                        amount=round(remaining, 2),
                    )
                )
    warning_items.sort(key=lambda item: (0 if item.level == "CRITICAL" else 1 if item.level == "WARNING" else 2, item.planned_date or date.max))
    return ProjectBoardInsights(
        as_of=today,
        trend=[{"month": month, "received": round(values["received"], 2), "paid": round(values["paid"], 2)} for month, values in months.items()],
        receivable_aging=[
            ProjectBoardAgingBucket(
                name=name,
                amount=round(float(receivable_aging[name]["amount"]), 2),
                items=sorted(receivable_aging[name]["items"], key=lambda item: item.amount, reverse=True),
            )
            for name, _, _ in aging_buckets
        ],
        payable_aging=[
            ProjectBoardAgingBucket(
                name=name,
                amount=round(float(payable_aging[name]["amount"]), 2),
                items=sorted(payable_aging[name]["items"], key=lambda item: item.amount, reverse=True),
            )
            for name, _, _ in aging_buckets
        ],
        warning_items=warning_items[:100],
    )


@app.get("/api/v1/reports/projects/export")
def export_project_board(
    keyword: str | None = None,
    project_id: int | None = Query(default=None, gt=0),
    project_type: str | None = None,
    status: str | None = None,
    department_id: int | None = Query(default=None, gt=0),
    owner_user_id: int | None = Query(default=None, gt=0),
    customer_id: int | None = Query(default=None, gt=0),
    data_scope: str = Query(default="OWNED", pattern="^(OWNED|ALL)$"),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出项目经营看板明细 CSV，口径与看板接口一致。"""
    user = require_admin_permission(db, "project_board", x_demo_user_id)
    require_access(db, "project_board", "EXPORT", x_demo_user_id)
    scope = project_scope_ids(db, user, "project_board")
    query = select(Project).where(Project.status != "DELETED")
    if data_scope == "OWNED":
        query = query.where(Project.owner_user_id == user.id)
    elif scope is not None:
        query = query.where(Project.id.in_(scope))
    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(Project.name.contains(value) | Project.code.contains(value))
    if project_id:
        query = query.where(Project.id == project_id)
    if project_type:
        query = query.where(Project.project_type == project_type)
    if status:
        query = query.where(Project.status == status)
    if department_id:
        index = DepartmentIndex(db.scalars(select(Department)).all())
        department_ids = index.descendants(department_id)
        if not department_ids:
            raise HTTPException(400, "INVALID_DEPARTMENT")
        query = query.where(Project.department_id.in_(department_ids))
    if owner_user_id:
        query = query.where(Project.owner_user_id == owner_user_id)
    if customer_id:
        query = query.where(Project.customer_id == customer_id)
    projects = db.scalars(query.order_by(Project.updated_at.desc(), Project.id.desc())).all()
    index = DepartmentIndex(db.scalars(select(Department)).all())
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["项目编号", "项目名称", "项目类型", "状态", "负责人", "所属部门", "已发生人天", "总预算", "实际总成本", "人工费用", "支出合同成本", "项目费用", "总预算使用率", "非人工预算", "非人工预算剩余", "非人工预算使用率", "合同收入", "合同成本", "已收", "已付", "应收", "应付", "毛利"])
    for project in projects:
        finance = project_finance_summary(db, project)
        detail = project_view(db, project)
        writer.writerow([
            project.code,
            project.name,
            project.project_type,
            project.status,
            project.owner_name or "",
            index.path(project.department_id),
            detail.actual_days,
            detail.budget_cost,
            detail.actual_cost,
            detail.personnel_cost,
            detail.actual_contract_cost,
            detail.actual_expense_cost,
            f"{detail.cost_usage_rate}%" if detail.cost_usage_rate is not None else "",
            detail.expense_budget,
            detail.expense_budget_remaining,
            f"{detail.expense_budget_usage_rate}%" if detail.expense_budget_usage_rate is not None else "",
            finance["contract_income"],
            finance["contract_expense"],
            finance["received"],
            finance["paid"],
            finance["receivable"],
            finance["payable"],
            finance["gross_profit"],
        ])
    filename = f"xinye-project-board-{now_local():%Y%m%d-%H%M%S}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/projects/{project_id}/finance", response_model=ProjectFinanceView)
def get_project_finance(project_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectFinanceView:
    user = current_user(db, x_demo_user_id)
    project = ensure_project_in_scope(db, user, project_id)
    return ProjectFinanceView(project_id=project.id, **project_finance_summary(db, project))


@app.get("/api/v1/projects/{project_id}/analysis", response_model=ProjectAnalysisView)
def get_project_analysis(
    project_id: int,
    as_of: date | None = Query(default=None),
    include_trend: bool = Query(default=True),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ProjectAnalysisView:
    """读取单项目经营分析；统一校验项目范围并汇总可下钻的经营数据。"""
    user = current_user(db, x_demo_user_id)
    project = ensure_project_in_scope(db, user, project_id)
    result = project_analysis_view(db, project, as_of or today_local())
    if not include_trend:
        result.cost.monthly_trend = []
    return result


@app.get("/api/v1/workbench/overview", response_model=WorkbenchOverview)
def workbench_overview(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> WorkbenchOverview:
    """工作台负责人区域：返回本人负责项目的经营汇总和收付款提醒。"""
    user = current_user(db, x_demo_user_id)
    projects = db.scalars(
        select(Project)
        .where(Project.owner_user_id == user.id, Project.status != "DELETED")
        .order_by(Project.updated_at.desc(), Project.id.desc())
    ).all()
    index = DepartmentIndex(db.scalars(select(Department)).all())
    today = today_local()
    week_end = today + timedelta(days=7)
    reminder_window_end = today + timedelta(days=30)
    rows: list[WorkbenchProjectRow] = []
    reminders: list[WorkbenchReminder] = []
    receivable_due = 0
    payable_due = 0
    overdue_count = 0
    pending_worklog_count = 0
    normal_project_count = 0
    warning_project_count = 0
    over_budget_project_count = 0
    project_ids = [project.id for project in projects]
    if project_ids:
        pending_worklog_count = int(db.scalar(select(func.count()).select_from(Worklog).where(Worklog.project_id.in_(project_ids), Worklog.status == "PENDING_APPROVAL")) or 0)
    for project in projects:
        finance = project_finance_summary(db, project)
        warning: str | None = None
        if finance["receivable"] > 0:
            warning = "应收未收"
        elif finance["payable"] > 0:
            warning = "应付未付"
        project_view_row = project_view(db, project)
        rows.append(
            WorkbenchProjectRow(
                id=project.id,
                code=project.code,
                name=project.name,
                project_type=project.project_type,
                status=project.status,
                owner_name=project.owner_name or "",
                department_path=index.path(project.department_id),
                budget_days=project_view_row.budget_days,
                actual_days=project_view_row.actual_days,
                completion_rate=project_view_row.completion_rate,
                budget_cost=project_view_row.budget_cost,
                personnel_cost=project_view_row.personnel_cost,
                cost_usage_rate=project_view_row.cost_usage_rate,
                execution_status=project_view_row.execution_status,
                **finance,
                warning=warning,
            )
        )
        if project_view_row.execution_status == "OVER_BUDGET":
            over_budget_project_count += 1
        elif project_view_row.execution_status == "NEAR_BUDGET":
            warning_project_count += 1
        else:
            normal_project_count += 1
        contracts = db.scalars(select(Contract).where(Contract.project_id == project.id, Contract.status != "TERMINATED")).all()
        for contract in contracts:
            stages = db.scalars(select(ContractStage).where(ContractStage.contract_id == contract.id).order_by(ContractStage.planned_date, ContractStage.id)).all()
            for stage in stages:
                if contract.contract_type == "INCOME":
                    settled = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.stage_id == stage.id, Receipt.status == "APPROVED")) or 0)
                else:
                    settled = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.stage_id == stage.id, Payment.status == "APPROVED")) or 0)
                remaining = max(float(stage.amount or 0) - settled, 0)
                if remaining <= 0 or not stage.planned_date:
                    continue
                # 工作台提醒展示逾期事项和未来 30 天内的事项；7 天指标仍单独统计。
                if stage.planned_date > reminder_window_end:
                    continue
                kind = "RECEIVABLE" if contract.contract_type == "INCOME" else "PAYABLE"
                if stage.planned_date < today:
                    overdue_count += 1
                    kind = f"OVERDUE_{kind}"
                elif stage.planned_date <= week_end:
                    if contract.contract_type == "INCOME":
                        receivable_due += remaining
                    else:
                        payable_due += remaining
                reminders.append(
                    WorkbenchReminder(
                        kind=kind,
                        project_id=project.id,
                        project_name=project.name,
                        contract_name=contract.name,
                        stage_name=stage.name,
                        amount=float(stage.amount or 0),
                        remaining=round(remaining, 2),
                        planned_date=stage.planned_date,
                    )
                )
    return WorkbenchOverview(
        owned_projects=rows,
        metrics={
            "project_count": len(rows),
            "pending_worklog_count": pending_worklog_count,
            "receivable_due_7d": round(receivable_due, 2),
            "payable_due_7d": round(payable_due, 2),
            "overdue_count": overdue_count,
            "normal_project_count": normal_project_count,
            "warning_project_count": warning_project_count,
            "over_budget_project_count": over_budget_project_count,
        },
        reminders=reminders,
    )


@app.get("/api/v1/projects/{project_id}/audit", response_model=list[AuditEntryView])
def project_audit_log(project_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[AuditEntryView]:
    """项目详情操作记录：项目、合同、阶段、收付款和预算变更审计。"""
    user = current_user(db, x_demo_user_id)
    project = ensure_project_in_scope(db, user, project_id)
    contract_ids = select(Contract.id).where(Contract.project_id == project.id)
    stage_ids = select(ContractStage.id).where(ContractStage.contract_id.in_(contract_ids))
    receipt_ids = select(Receipt.id).where(Receipt.project_id == project.id)
    payment_ids = select(Payment.id).where(Payment.project_id == project.id)
    logs = db.scalars(
        select(AuditLog)
        .where(
            or_(
                and_(AuditLog.object_type == "project", AuditLog.object_id == project.id),
                and_(AuditLog.object_type == "contract", AuditLog.object_id.in_(contract_ids)),
                and_(AuditLog.object_type == "contract_stage", AuditLog.object_id.in_(stage_ids)),
                and_(AuditLog.object_type == "contract_attachment", AuditLog.object_id.in_(select(ContractAttachment.id).where(ContractAttachment.contract_id.in_(contract_ids)))),
                and_(AuditLog.object_type == "receipt", AuditLog.object_id.in_(receipt_ids)),
                and_(AuditLog.object_type == "payment", AuditLog.object_id.in_(payment_ids)),
            )
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(300)
    ).all()
    users = {item.id: item.name for item in db.scalars(select(User)).all()}
    def object_label(item: AuditLog) -> str:
        source = None
        if item.object_type == "project":
            source = db.get(Project, item.object_id)
            return source.name if source else f"项目 #{item.object_id}"
        if item.object_type == "contract":
            source = db.get(Contract, item.object_id)
            return source.name if source else f"合同 #{item.object_id}"
        if item.object_type == "contract_stage":
            source = db.get(ContractStage, item.object_id)
            return source.name if source else f"阶段 #{item.object_id}"
        if item.object_type == "receipt":
            source = db.get(Receipt, item.object_id)
            return source.receipt_no if source else f"合同收款单 #{item.object_id}"
        if item.object_type == "payment":
            source = db.get(Payment, item.object_id)
            return source.payment_no if source else f"合同付款单 #{item.object_id}"
        if item.object_type == "contract_attachment":
            source = db.get(ContractAttachment, item.object_id)
            return source.file_name if source else f"附件 #{item.object_id}"
        return f"{item.object_type} #{item.object_id}"
    return [
        AuditEntryView(
            id=item.id,
            object_type=item.object_type,
            object_id=item.object_id,
            action=item.action,
            actor_name=users.get(item.actor_user_id, "系统"),
            old_status=item.old_status,
            new_status=item.new_status,
            comment=item.comment,
            object_label=object_label(item),
            description=f"{item.action} · {object_label(item)}",
            created_at=item.created_at,
        )
        for item in logs
    ]


@app.get("/api/v1/projects/{project_id}", response_model=ProjectView)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectView:
    """读取项目详情。"""
    project = db.get(Project, project_id)
    if not project or project.status == "DELETED":
        raise HTTPException(404, "PROJECT_NOT_FOUND")
    return project_view(db, project)


@app.patch("/api/v1/projects/{project_id}", response_model=ProjectView)
def update_project(project_id: int, payload: ProjectUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectView:
    """编辑项目基础信息和组织人员配置，只影响后续新提交。"""
    user = require_admin_permission(db, "projects", x_demo_user_id)
    require_access(db, "projects", "EDIT", x_demo_user_id)
    project = db.get(Project, project_id)
    if not project or project.status == "DELETED":
        raise HTTPException(404, "PROJECT_NOT_FOUND")
    duplicate = db.scalar(select(Project).where(Project.code == payload.code, Project.id != project.id))
    if duplicate:
        raise HTTPException(409, "PROJECT_CODE_EXISTS")
    validate_config_option(db, "project_type", payload.project_type)
    validate_config_option(db, "project_status", payload.status)
    old_status = project.status
    project.code = payload.code
    project.name = payload.name
    project.project_type = payload.project_type
    project.budget_days = payload.budget_days
    project.budget_cost = project_budget_total(db, project.id)
    project.expense_budget = 0
    department = active_org_department(db, payload.department_id)
    project.department_id = department.id
    project.department_name = department.name
    project.status = payload.status
    project.allow_worklog = payload.allow_worklog
    apply_project_master_fields(project, db, payload)
    apply_project_users(project, db, payload.owner_user_id, payload.approver_user_id, payload.leader_user_id)
    audit(db, "project", project.id, "UPDATE", user.id, old_status, project.status)
    db.commit()
    db.refresh(project)
    return project_view(db, project)


@app.delete("/api/v1/projects/{project_id}")
def delete_project(project_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """软删除项目，保留工时、审批和审计历史。"""
    user = require_admin_permission(db, "projects", x_demo_user_id)
    require_access(db, "projects", "DELETE", x_demo_user_id)
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "PROJECT_NOT_FOUND")
    if project.status == "DELETED":
        raise HTTPException(409, "PROJECT_ALREADY_DELETED")
    old_status = project.status
    project.status = "DELETED"
    project.allow_worklog = False
    audit(db, "project", project.id, "DELETE", user.id, old_status, "DELETED")
    db.commit()
    return {"deleted": True, "project_id": project.id}


@app.patch("/api/v1/projects/{project_id}/approver", response_model=ProjectView)
def update_project_approver(project_id: int, payload: ProjectApproverUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectView:
    user = require_admin_permission(db, "projects", x_demo_user_id)
    require_access(db, "projects", "EDIT", x_demo_user_id)
    project = db.get(Project, project_id)
    approver = db.get(User, payload.approver_user_id)
    leader = db.get(User, payload.leader_user_id)
    if not project:
        raise HTTPException(404, "PROJECT_NOT_FOUND")
    if not approver or approver.employment_status != "ACTIVE" or not leader or leader.employment_status != "ACTIVE":
        raise HTTPException(400, "USER_NOT_ACTIVE")
    old = f"{project.approver_name or '未配置'} / {project.leader_name or '未配置'}"
    project.approver_user_id = approver.id
    project.approver_open_id = approver.open_id
    project.approver_name = approver.name
    project.leader_user_id = leader.id
    project.leader_open_id = leader.open_id
    project.leader_name = leader.name
    audit(db, "project", project.id, "UPDATE_APPROVAL_CHAIN", user.id, old, f"{approver.name} / {leader.name}")
    db.commit()
    db.refresh(project)
    return project_view(db, project)


@app.get("/api/v1/contracts", response_model=list[ContractView])
def list_contracts(
    project_id: int | None = Query(default=None, gt=0),
    contract_type: str | None = None,
    counterparty_id: int | None = Query(default=None, gt=0),
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    keyword: str | None = None,
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[ContractView]:
    user = current_user(db, x_demo_user_id)
    if not (user_admin_permissions(db, user.id) & {"contracts", "receipts", "payments"}):
        raise HTTPException(403, "ADMIN_PERMISSION_REQUIRED")
    scope = project_scope_ids(db, user, "contracts")
    query = select(Contract).order_by(Contract.updated_at.desc(), Contract.id.desc())
    if scope is not None:
        query = query.where(Contract.project_id.in_(scope))
    if project_id:
        query = query.where(Contract.project_id == project_id)
    if contract_type:
        query = query.where(Contract.contract_type == contract_type)
    if counterparty_id:
        query = query.where(Contract.counterparty_id == counterparty_id)
    if status:
        query = query.where(Contract.status == status)
    if start_date:
        query = query.where(or_(Contract.end_date.is_(None), Contract.end_date >= start_date))
    if end_date:
        query = query.where(or_(Contract.start_date.is_(None), Contract.start_date <= end_date))
    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(Contract.name.contains(value) | Contract.contract_no.contains(value))
    return [contract_view(db, item) for item in db.scalars(query).all()]


@app.post("/api/v1/contracts", response_model=ContractView, status_code=201)
def create_contract(payload: ContractCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ContractView:
    user = require_admin_permission(db, "contracts", x_demo_user_id)
    require_access(db, "contracts", "CREATE", x_demo_user_id)
    project = ensure_project_in_scope(db, user, payload.project_id)
    if db.scalar(select(Contract).where(Contract.contract_no == payload.contract_no)):
        raise HTTPException(409, "CONTRACT_NO_EXISTS")
    counterparty_name = resolve_counterparty_name(db, payload.counterparty_type, payload.counterparty_id)
    budget_item = resolve_project_budget_item(db, project.id, payload.budget_item_id, required=payload.contract_type == "EXPENSE", source_kind="CONTRACT_PAYMENT")
    contract = Contract(
        contract_no=payload.contract_no,
        name=payload.name,
        project_id=project.id,
        contract_type=payload.contract_type,
        counterparty_type=payload.counterparty_type,
        counterparty_id=payload.counterparty_id,
        counterparty_name=counterparty_name,
        amount=payload.amount,
        sign_date=payload.sign_date,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=payload.status,
        description=payload.description.strip() if payload.description and payload.description.strip() else None,
    )
    apply_budget_snapshot(contract, budget_item if payload.contract_type == "EXPENSE" else None)
    db.add(contract)
    db.flush()
    audit(db, "contract", contract.id, "CREATE", user.id, None, contract.status)
    db.commit()
    db.refresh(contract)
    return contract_view(db, contract)


@app.get("/api/v1/contracts/{contract_id}", response_model=ContractView)
def get_contract(contract_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ContractView:
    user = current_user(db, x_demo_user_id)
    if not (user_admin_permissions(db, user.id) & {"contracts", "receipts", "payments"}):
        raise HTTPException(403, "ADMIN_PERMISSION_REQUIRED")
    contract = resolve_contract(db, contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    return contract_view(db, contract)


@app.post("/api/v1/contracts/{contract_id}/activate", response_model=ContractView)
def activate_contract(contract_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ContractView:
    """激活合同；阶段金额合计必须等于合同金额。"""
    user = require_admin_permission(db, "contracts", x_demo_user_id)
    contract = resolve_contract(db, contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    stage_total = float(db.scalar(select(func.coalesce(func.sum(ContractStage.amount), 0)).where(ContractStage.contract_id == contract.id)) or 0)
    if round(stage_total, 2) != round(float(contract.amount or 0), 2):
        raise HTTPException(400, "CONTRACT_STAGE_SUM_MISMATCH")
    old_status = contract.status
    contract.status = "ACTIVE"
    audit(db, "contract", contract.id, "UPDATE", user.id, old_status, "ACTIVE")
    db.commit()
    db.refresh(contract)
    return contract_view(db, contract)


@app.patch("/api/v1/contracts/{contract_id}", response_model=ContractView)
def update_contract(contract_id: int, payload: ContractUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ContractView:
    user = require_admin_permission(db, "contracts", x_demo_user_id)
    require_access(db, "contracts", "EDIT", x_demo_user_id)
    contract = resolve_contract(db, contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    project = ensure_project_in_scope(db, user, payload.project_id)
    if db.scalar(select(Contract).where(Contract.contract_no == payload.contract_no, Contract.id != contract.id)):
        raise HTTPException(409, "CONTRACT_NO_EXISTS")
    counterparty_name = resolve_counterparty_name(db, payload.counterparty_type, payload.counterparty_id)
    budget_item = resolve_project_budget_item(db, project.id, payload.budget_item_id, required=payload.contract_type == "EXPENSE", source_kind="CONTRACT_PAYMENT")
    old_status = contract.status
    contract.contract_no = payload.contract_no
    contract.name = payload.name
    contract.project_id = project.id
    contract.contract_type = payload.contract_type
    contract.counterparty_type = payload.counterparty_type
    contract.counterparty_id = payload.counterparty_id
    contract.counterparty_name = counterparty_name
    contract.amount = payload.amount
    contract.sign_date = payload.sign_date
    contract.start_date = payload.start_date
    contract.end_date = payload.end_date
    contract.status = payload.status
    contract.description = payload.description.strip() if payload.description and payload.description.strip() else None
    apply_budget_snapshot(contract, budget_item if payload.contract_type == "EXPENSE" else None)
    audit(db, "contract", contract.id, "UPDATE", user.id, old_status, contract.status)
    db.commit()
    db.refresh(contract)
    return contract_view(db, contract)


@app.get("/api/v1/contracts/{contract_id}/attachments", response_model=list[ContractAttachmentView])
def list_contract_attachments(contract_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[ContractAttachmentView]:
    """查询合同附件元数据，文件路径不会返回给客户端。"""
    user = require_admin_permission(db, "contracts", x_demo_user_id)
    contract = resolve_contract(db, contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    attachments = db.scalars(
        select(ContractAttachment)
        .where(ContractAttachment.contract_id == contract.id)
        .order_by(ContractAttachment.created_at.desc(), ContractAttachment.id.desc())
    ).all()
    return [contract_attachment_view(db, item) for item in attachments]


@app.post("/api/v1/contracts/{contract_id}/attachments", response_model=ContractAttachmentView, status_code=201)
async def upload_contract_attachment(
    contract_id: int,
    file: UploadFile = File(...),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ContractAttachmentView:
    """上传合同附件并写入持久化数据卷；单文件大小默认限制 50MB。"""
    user = require_admin_permission(db, "contracts", x_demo_user_id)
    require_access(db, "contracts", "CREATE", x_demo_user_id)
    contract = resolve_contract(db, contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    original_name = Path(file.filename or "").name.strip()
    suffix = Path(original_name).suffix.lower()
    if not original_name or suffix not in CONTRACT_ATTACHMENT_EXTENSIONS:
        raise HTTPException(400, "CONTRACT_ATTACHMENT_TYPE_NOT_ALLOWED")
    stored_name = f"{secrets.token_hex(20)}{suffix}"
    destination = contract_attachment_root() / stored_name
    size = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > CONTRACT_ATTACHMENT_MAX_BYTES:
                    raise HTTPException(413, "CONTRACT_ATTACHMENT_TOO_LARGE")
                output.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(500, "CONTRACT_ATTACHMENT_STORAGE_FAILED") from exc
    finally:
        await file.close()
    if size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, "CONTRACT_ATTACHMENT_EMPTY")
    attachment = ContractAttachment(
        contract_id=contract.id,
        file_name=original_name[:300],
        storage_name=stored_name,
        mime_type=(file.content_type or CONTRACT_ATTACHMENT_EXTENSIONS[suffix])[:160],
        file_size=size,
        uploaded_by=user.id,
    )
    db.add(attachment)
    db.flush()
    audit(db, "contract_attachment", attachment.id, "CREATE", user.id, None, None, f"上传附件：{attachment.file_name}")
    db.commit()
    db.refresh(attachment)
    return contract_attachment_view(db, attachment)


@app.get("/api/v1/contract-attachments/{attachment_id}/preview", response_model=None)
def preview_contract_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> HTMLResponse | FileResponse:
    """预览 PDF/图片或 Office 文件；Office 优先转换为 PDF，失败时新版格式回退到 HTML。"""
    attachment = resolve_contract_attachment(db, attachment_id)
    ensure_contract_attachment_access(db, attachment, x_demo_user_id)
    path = contract_attachment_path(attachment)
    if not path.is_file():
        raise HTTPException(404, "CONTRACT_ATTACHMENT_FILE_NOT_FOUND")
    kind = attachment_preview_kind(attachment.file_name)
    if kind in {"word", "excel", "powerpoint"}:
        try:
            preview_path, preview_dir = _convert_office_to_pdf(path)
            return FileResponse(
                preview_path,
                media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(attachment.file_name)}.pdf"},
                background=BackgroundTask(shutil.rmtree, preview_dir, ignore_errors=True),
            )
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
            if Path(attachment.file_name).suffix.lower() in {".docx", ".xlsx", ".pptx"}:
                try:
                    return HTMLResponse(render_contract_office_preview(attachment, path))
                except (ET.ParseError, KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
                    raise HTTPException(422, "CONTRACT_ATTACHMENT_PREVIEW_FAILED") from exc
            raise HTTPException(422, "CONTRACT_ATTACHMENT_PREVIEW_FAILED") from exc
    if kind in {"pdf", "image"}:
        return FileResponse(path, media_type=attachment.mime_type, headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(attachment.file_name)}"})
    raise HTTPException(415, "CONTRACT_ATTACHMENT_PREVIEW_UNAVAILABLE")


@app.get("/api/v1/contract-attachments/{attachment_id}/download")
def download_contract_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> FileResponse:
    """下载原始合同附件。"""
    attachment = resolve_contract_attachment(db, attachment_id)
    ensure_contract_attachment_access(db, attachment, x_demo_user_id)
    path = contract_attachment_path(attachment)
    if not path.is_file():
        raise HTTPException(404, "CONTRACT_ATTACHMENT_FILE_NOT_FOUND")
    return FileResponse(path, media_type=attachment.mime_type, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.file_name)}"})


@app.delete("/api/v1/contract-attachments/{attachment_id}")
def delete_contract_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """删除合同附件元数据和文件本体。"""
    attachment = resolve_contract_attachment(db, attachment_id)
    user, _contract = ensure_contract_attachment_access(db, attachment, x_demo_user_id)
    require_access(db, "contracts", "DELETE", x_demo_user_id)
    path = contract_attachment_path(attachment)
    db.delete(attachment)
    audit(db, "contract_attachment", attachment_id, "DELETE", user.id, None, None, f"删除附件：{attachment.file_name}")
    db.commit()
    path.unlink(missing_ok=True)
    return {"deleted": True, "attachment_id": attachment_id}


async def store_cash_attachment(
    db: Session,
    document_type: str,
    document_id: int,
    file: UploadFile,
    x_demo_user_id: int | None,
) -> CashDocumentAttachmentView:
    """保存收付款附件并返回附件视图；单文件大小默认限制 50MB。"""
    attachment_document = db.get(Receipt if document_type == "RECEIPT" else Payment, document_id)
    if not attachment_document:
        raise HTTPException(404, "CASH_DOCUMENT_NOT_FOUND")
    attachment = CashDocumentAttachment(
        document_type=document_type,
        document_id=document_id,
        file_name="",
        storage_name="",
        mime_type="application/octet-stream",
        file_size=0,
        uploaded_by=0,
    )
    user = require_admin_permission(db, "receipts" if document_type == "RECEIPT" else "payments", x_demo_user_id)
    ensure_project_in_scope(db, user, attachment_document.project_id)
    original_name = Path(file.filename or "").name.strip()
    suffix = Path(original_name).suffix.lower()
    if not original_name or suffix not in CONTRACT_ATTACHMENT_EXTENSIONS:
        raise HTTPException(400, "CASH_ATTACHMENT_TYPE_NOT_ALLOWED")
    stored_name = f"{secrets.token_hex(20)}{suffix}"
    destination = cash_attachment_root() / stored_name
    size = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > CONTRACT_ATTACHMENT_MAX_BYTES:
                    raise HTTPException(413, "CASH_ATTACHMENT_TOO_LARGE")
                output.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(500, "CASH_ATTACHMENT_STORAGE_FAILED") from exc
    finally:
        await file.close()
    if size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, "CASH_ATTACHMENT_EMPTY")
    attachment.file_name = original_name[:300]
    attachment.storage_name = stored_name
    attachment.mime_type = (file.content_type or CONTRACT_ATTACHMENT_EXTENSIONS[suffix])[:160]
    attachment.file_size = size
    attachment.uploaded_by = user.id
    db.add(attachment)
    db.flush()
    audit(db, "cash_attachment", attachment.id, "CREATE", user.id, None, None, f"上传附件：{attachment.file_name}")
    db.commit()
    db.refresh(attachment)
    return cash_attachment_view(db, attachment)


@app.get("/api/v1/receipts/{receipt_id}/attachments", response_model=list[CashDocumentAttachmentView])
def list_receipt_attachments(receipt_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[CashDocumentAttachmentView]:
    """查询合同收款单附件，出纳审批人可读取附件。"""
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    user = current_user(db, x_demo_user_id)
    permissions = user_admin_permissions(db, user.id)
    if "receipts" not in permissions and "cash_approval" not in permissions:
        raise HTTPException(403, "ADMIN_PERMISSION_REQUIRED")
    ensure_project_in_scope(db, user, receipt.project_id)
    attachments = db.scalars(
        select(CashDocumentAttachment)
        .where(CashDocumentAttachment.document_type == "RECEIPT", CashDocumentAttachment.document_id == receipt.id)
        .order_by(CashDocumentAttachment.created_at.desc(), CashDocumentAttachment.id.desc())
    ).all()
    return [cash_attachment_view(db, item) for item in attachments]


@app.post("/api/v1/receipts/{receipt_id}/attachments", response_model=CashDocumentAttachmentView, status_code=201)
async def upload_receipt_attachment(
    receipt_id: int,
    file: UploadFile = File(...),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CashDocumentAttachmentView:
    """上传合同收款单附件。"""
    return await store_cash_attachment(db, "RECEIPT", receipt_id, file, x_demo_user_id)


@app.get("/api/v1/payments/{payment_id}/attachments", response_model=list[CashDocumentAttachmentView])
def list_payment_attachments(payment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[CashDocumentAttachmentView]:
    """查询合同付款单附件，付款流程任务人可只读查看。"""
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    user = current_user(db, x_demo_user_id)
    permissions = user_admin_permissions(db, user.id)
    assigned = payment_workflow_assigned(db, payment, user.id)
    if "payments" not in permissions and "cash_approval" not in permissions and not assigned:
        raise HTTPException(403, "ADMIN_PERMISSION_REQUIRED")
    if not assigned:
        ensure_project_in_scope(db, user, payment.project_id)
    attachments = db.scalars(
        select(CashDocumentAttachment)
        .where(CashDocumentAttachment.document_type == "PAYMENT", CashDocumentAttachment.document_id == payment.id)
        .order_by(CashDocumentAttachment.created_at.desc(), CashDocumentAttachment.id.desc())
    ).all()
    return [cash_attachment_view(db, item) for item in attachments]


@app.post("/api/v1/payments/{payment_id}/attachments", response_model=CashDocumentAttachmentView, status_code=201)
async def upload_payment_attachment(
    payment_id: int,
    file: UploadFile = File(...),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CashDocumentAttachmentView:
    """上传合同付款单附件。"""
    return await store_cash_attachment(db, "PAYMENT", payment_id, file, x_demo_user_id)


@app.get("/api/v1/cash-attachments/{attachment_id}/preview", response_model=None)
def preview_cash_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> HTMLResponse | FileResponse:
    """预览收付款附件；Office 转换失败时回退到新版格式 HTML 预览。"""
    attachment = resolve_cash_attachment(db, attachment_id)
    ensure_cash_attachment_access(db, attachment, x_demo_user_id)
    path = cash_attachment_path(attachment)
    if not path.is_file():
        raise HTTPException(404, "CASH_ATTACHMENT_FILE_NOT_FOUND")
    kind = attachment_preview_kind(attachment.file_name)
    if kind in {"word", "excel", "powerpoint"}:
        try:
            preview_path, preview_dir = _convert_office_to_pdf(path)
            return FileResponse(
                preview_path,
                media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(attachment.file_name)}.pdf"},
                background=BackgroundTask(shutil.rmtree, preview_dir, ignore_errors=True),
            )
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
            if Path(attachment.file_name).suffix.lower() in {".docx", ".xlsx", ".pptx"}:
                try:
                    return HTMLResponse(render_contract_office_preview(attachment, path))
                except (ET.ParseError, KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
                    raise HTTPException(422, "CASH_ATTACHMENT_PREVIEW_FAILED") from exc
            raise HTTPException(422, "CASH_ATTACHMENT_PREVIEW_FAILED") from exc
    if kind in {"pdf", "image"}:
        return FileResponse(path, media_type=attachment.mime_type, headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(attachment.file_name)}"})
    raise HTTPException(415, "CASH_ATTACHMENT_PREVIEW_UNAVAILABLE")


@app.get("/api/v1/cash-attachments/{attachment_id}/download")
def download_cash_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> FileResponse:
    """下载原始收付款附件。"""
    attachment = resolve_cash_attachment(db, attachment_id)
    ensure_cash_attachment_access(db, attachment, x_demo_user_id)
    path = cash_attachment_path(attachment)
    if not path.is_file():
        raise HTTPException(404, "CASH_ATTACHMENT_FILE_NOT_FOUND")
    return FileResponse(path, media_type=attachment.mime_type, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.file_name)}"})


@app.delete("/api/v1/cash-attachments/{attachment_id}")
def delete_cash_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """删除收付款附件元数据和文件本体；出纳审批人只读。"""
    attachment = resolve_cash_attachment(db, attachment_id)
    user, _document = ensure_cash_attachment_access(db, attachment, x_demo_user_id, write=True)
    require_access(db, "receipts" if attachment.document_type == "RECEIPT" else "payments", "DELETE", x_demo_user_id)
    path = cash_attachment_path(attachment)
    db.delete(attachment)
    audit(db, "cash_attachment", attachment_id, "DELETE", user.id, None, None, f"删除附件：{attachment.file_name}")
    db.commit()
    path.unlink(missing_ok=True)
    return {"deleted": True, "attachment_id": attachment_id}


@app.delete("/api/v1/contracts/{contract_id}")
def delete_contract(contract_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    user = require_admin_permission(db, "contracts", x_demo_user_id)
    require_access(db, "contracts", "DELETE", x_demo_user_id)
    contract = resolve_contract(db, contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    active_cash = db.scalar(select(Receipt.id).where(Receipt.contract_id == contract.id, Receipt.status.in_(("DRAFT", "PENDING", "APPROVED"))).limit(1))
    active_cash = active_cash or db.scalar(select(Payment.id).where(Payment.contract_id == contract.id, Payment.status.in_(("DRAFT", "PENDING", "PENDING_APPROVAL", "APPROVED"))).limit(1))
    if active_cash:
        raise HTTPException(409, "CONTRACT_HAS_CASH_DOCUMENTS")
    old_status = contract.status
    contract.status = "TERMINATED"
    audit(db, "contract", contract.id, "DELETE", user.id, old_status, "TERMINATED")
    db.commit()
    return {"deleted": True, "contract_id": contract.id}


@app.get("/api/v1/contracts/{contract_id}/stages", response_model=list[ContractStageView])
def list_contract_stages(contract_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[ContractStageView]:
    user = current_user(db, x_demo_user_id)
    if not (user_admin_permissions(db, user.id) & {"contracts", "receipts", "payments"}):
        raise HTTPException(403, "ADMIN_PERMISSION_REQUIRED")
    contract = resolve_contract(db, contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    stages = db.scalars(select(ContractStage).where(ContractStage.contract_id == contract.id).order_by(ContractStage.sort_order, ContractStage.id)).all()
    return [contract_stage_view(db, item) for item in stages]


@app.post("/api/v1/contracts/{contract_id}/stages", response_model=ContractStageView, status_code=201)
def create_contract_stage(contract_id: int, payload: ContractStageCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ContractStageView:
    user = require_admin_permission(db, "contracts", x_demo_user_id)
    require_access(db, "contracts", "CREATE", x_demo_user_id)
    contract = resolve_contract(db, contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    stage = ContractStage(contract_id=contract.id, **payload.model_dump())
    db.add(stage)
    db.flush()
    audit(db, "contract_stage", stage.id, "CREATE", user.id, None, stage.status)
    db.commit()
    db.refresh(stage)
    return contract_stage_view(db, stage)


@app.patch("/api/v1/contract-stages/{stage_id}", response_model=ContractStageView)
def update_contract_stage(stage_id: int, payload: ContractStageUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ContractStageView:
    user = require_admin_permission(db, "contracts", x_demo_user_id)
    require_access(db, "contracts", "EDIT", x_demo_user_id)
    stage = db.get(ContractStage, stage_id)
    if not stage:
        raise HTTPException(404, "STAGE_NOT_FOUND")
    contract = resolve_contract(db, stage.contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    old_status = stage.status
    for key, value in payload.model_dump().items():
        setattr(stage, key, value)
    audit(db, "contract_stage", stage.id, "UPDATE", user.id, old_status, stage.status)
    db.commit()
    db.refresh(stage)
    return contract_stage_view(db, stage)


@app.delete("/api/v1/contract-stages/{stage_id}")
def delete_contract_stage(stage_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    user = require_admin_permission(db, "contracts", x_demo_user_id)
    require_access(db, "contracts", "DELETE", x_demo_user_id)
    stage = db.get(ContractStage, stage_id)
    if not stage:
        raise HTTPException(404, "STAGE_NOT_FOUND")
    contract = resolve_contract(db, stage.contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    if db.scalar(select(Receipt.id).where(Receipt.stage_id == stage.id).limit(1)) or db.scalar(select(Payment.id).where(Payment.stage_id == stage.id).limit(1)):
        raise HTTPException(409, "STAGE_HAS_CASH_DOCUMENTS")
    db.delete(stage)
    audit(db, "contract_stage", stage.id, "DELETE", user.id, stage.status, None)
    db.commit()
    return {"deleted": True, "stage_id": stage.id}


@app.get("/api/v1/receipts", response_model=list[ReceiptView])
def list_receipts(
    project_id: int | None = Query(default=None, gt=0),
    contract_id: int | None = Query(default=None, gt=0),
    status: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    keyword: str | None = None,
    submitted_by: int | None = Query(default=None, gt=0),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[ReceiptView]:
    user = require_admin_permission(db, "receipts", x_demo_user_id)
    scope = project_scope_ids(db, user, "receipts")
    query = select(Receipt).order_by(Receipt.receipt_date.desc(), Receipt.id.desc())
    if scope is not None:
        query = query.where(Receipt.project_id.in_(scope))
    if project_id:
        query = query.where(Receipt.project_id == project_id)
    if contract_id:
        query = query.where(Receipt.contract_id == contract_id)
    if status:
        query = query.where(Receipt.status == status)
    if period_start:
        query = query.where(Receipt.receipt_date >= period_start)
    if period_end:
        query = query.where(Receipt.receipt_date <= period_end)
    if submitted_by:
        query = query.where(Receipt.submitted_by == submitted_by)
    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(
            Receipt.receipt_no.contains(value)
            | Receipt.payer_name.contains(value)
            | Receipt.comment.contains(value)
            | Receipt.contract_id.in_(select(Contract.id).where(Contract.name.contains(value) | Contract.contract_no.contains(value)))
        )
    return [receipt_view(db, item) for item in db.scalars(query).all()]


@app.post("/api/v1/receipts", response_model=ReceiptView, status_code=201)
def create_receipt(payload: ReceiptCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ReceiptView:
    user = require_admin_permission(db, "receipts", x_demo_user_id)
    require_access(db, "receipts", "CREATE", x_demo_user_id)
    contract = resolve_contract(db, payload.contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    if contract.contract_type != "INCOME":
        raise HTTPException(400, "CONTRACT_TYPE_MISMATCH")
    stage = resolve_contract_stage(db, payload.stage_id, contract.id)
    if payload.amount > stage_remaining(db, stage, "INCOME"):
        raise HTTPException(400, "STAGE_REMAINING_INSUFFICIENT")
    receipt = Receipt(
        receipt_no=next_document_no(db, Receipt, "RC"),
        project_id=contract.project_id,
        contract_id=contract.id,
        stage_id=stage.id if stage else None,
        amount=payload.amount,
        receipt_date=payload.receipt_date,
        payer_name=payload.payer_name,
        payer_bank_name=payload.payer_bank_name,
        payer_bank_account=payload.payer_bank_account,
        status="PENDING",
        submitted_by=user.id,
        submitted_at=now_local(),
        comment=payload.comment,
    )
    db.add(receipt)
    db.flush()
    audit(db, "receipt", receipt.id, "SUBMIT", user.id, None, "PENDING")
    db.commit()
    db.refresh(receipt)
    project = db.get(Project, receipt.project_id)
    send_cash_approval_notifications(
        db,
        "receipt",
        receipt.id,
        "合同收款单",
        receipt.receipt_no,
        project.name if project else "",
        float(receipt.amount or 0),
        user.name,
    )
    db.commit()
    db.refresh(receipt)
    return receipt_view(db, receipt)


@app.get("/api/v1/receipts/{receipt_id}", response_model=ReceiptView)
def get_receipt(receipt_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ReceiptView:
    user = require_admin_permission(db, "receipts", x_demo_user_id)
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    ensure_project_in_scope(db, user, receipt.project_id)
    return receipt_view(db, receipt)


@app.patch("/api/v1/receipts/{receipt_id}", response_model=ReceiptView)
def update_receipt(receipt_id: int, payload: ReceiptUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ReceiptView:
    user = require_admin_permission(db, "receipts", x_demo_user_id)
    require_access(db, "receipts", "EDIT", x_demo_user_id)
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    ensure_project_in_scope(db, user, receipt.project_id)
    if receipt.status not in ("DRAFT", "REJECTED"):
        raise HTTPException(409, "RECEIPT_READ_ONLY")
    contract = resolve_contract(db, payload.contract_id)
    stage = resolve_contract_stage(db, payload.stage_id, contract.id)
    if payload.amount > stage_remaining(db, stage, "INCOME"):
        raise HTTPException(400, "STAGE_REMAINING_INSUFFICIENT")
    receipt.contract_id = contract.id
    receipt.project_id = contract.project_id
    receipt.stage_id = stage.id if stage else None
    receipt.amount = payload.amount
    receipt.receipt_date = payload.receipt_date
    receipt.payer_name = payload.payer_name
    receipt.payer_bank_name = payload.payer_bank_name
    receipt.payer_bank_account = payload.payer_bank_account
    receipt.comment = payload.comment
    audit(db, "receipt", receipt.id, "UPDATE", user.id, receipt.status, receipt.status)
    db.commit()
    db.refresh(receipt)
    return receipt_view(db, receipt)


@app.delete("/api/v1/receipts/{receipt_id}")
def delete_receipt(receipt_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    user = require_admin_permission(db, "receipts", x_demo_user_id)
    require_access(db, "receipts", "DELETE", x_demo_user_id)
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    ensure_project_in_scope(db, user, receipt.project_id)
    if receipt.status not in ("DRAFT", "REJECTED"):
        raise HTTPException(409, "RECEIPT_READ_ONLY")
    db.delete(receipt)
    audit(db, "receipt", receipt.id, "DELETE", user.id, receipt.status, None)
    db.commit()
    return {"deleted": True, "receipt_id": receipt.id}


@app.post("/api/v1/receipts/{receipt_id}/submit", response_model=ReceiptView)
def submit_receipt(receipt_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ReceiptView:
    user = require_admin_permission(db, "receipts", x_demo_user_id)
    require_access(db, "receipts", "CREATE", x_demo_user_id)
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    ensure_project_in_scope(db, user, receipt.project_id)
    if receipt.status not in ("DRAFT", "REJECTED"):
        raise HTTPException(409, "RECEIPT_NOT_RESUBMITTABLE")
    receipt.status = "PENDING"
    receipt.submitted_by = user.id
    receipt.submitted_at = now_local()
    receipt.comment = None
    audit(db, "receipt", receipt.id, "SUBMIT", user.id, "REJECTED", "PENDING")
    db.commit()
    db.refresh(receipt)
    project = db.get(Project, receipt.project_id)
    send_cash_approval_notifications(
        db,
        "receipt",
        receipt.id,
        "合同收款单",
        receipt.receipt_no,
        project.name if project else "",
        float(receipt.amount or 0),
        user.name,
    )
    db.commit()
    db.refresh(receipt)
    return receipt_view(db, receipt)


@app.post("/api/v1/receipts/{receipt_id}/approve", response_model=ReceiptView)
def approve_receipt(receipt_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ReceiptView:
    user = require_admin_permission(db, "cash_approval", x_demo_user_id)
    require_access(db, "cash_approval", "APPROVE", x_demo_user_id)
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    if receipt.status != "PENDING":
        raise HTTPException(409, "RECEIPT_NOT_PENDING")
    receipt.status = "APPROVED"
    receipt.approved_by = user.id
    receipt.approved_at = now_local()
    add_ledger_entry(
        db,
        receipt.project_id,
        "RECEIPT",
        "RECEIPT",
        receipt.id,
        float(receipt.amount),
        occurred_on=receipt.receipt_date,
    )
    stage = db.get(ContractStage, receipt.stage_id) if receipt.stage_id else None
    refresh_stage_status(db, stage, "INCOME")
    audit(db, "receipt", receipt.id, "APPROVE", user.id, "PENDING", "APPROVED")
    db.commit()
    db.refresh(receipt)
    project = db.get(Project, receipt.project_id)
    if receipt.submitted_by:
        send_settlement_notification(
            db,
            "receipt",
            receipt.id,
            "合同收款单",
            receipt.receipt_no,
            project.name if project else "",
            float(receipt.amount),
            receipt.submitted_by,
            user.name,
        )
    return receipt_view(db, receipt)


@app.post("/api/v1/receipts/{receipt_id}/reject", response_model=ReceiptView)
def reject_receipt(receipt_id: int, payload: CashRejectAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ReceiptView:
    user = require_admin_permission(db, "cash_approval", x_demo_user_id)
    require_access(db, "cash_approval", "APPROVE", x_demo_user_id)
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    if receipt.status != "PENDING":
        raise HTTPException(409, "RECEIPT_NOT_PENDING")
    receipt.status = "REJECTED"
    receipt.comment = payload.reason
    audit(db, "receipt", receipt.id, "REJECT", user.id, "PENDING", "REJECTED", payload.reason)
    db.commit()
    db.refresh(receipt)
    return receipt_view(db, receipt)


@app.post("/api/v1/receipts/{receipt_id}/reverse", response_model=ReceiptView)
def reverse_receipt(receipt_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ReceiptView:
    user = require_admin_permission(db, "cash_approval", x_demo_user_id)
    require_access(db, "cash_approval", "APPROVE", x_demo_user_id)
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    if receipt.status != "APPROVED":
        raise HTTPException(409, "RECEIPT_NOT_APPROVED")
    receipt.status = "REVERSED"
    original_entry = db.scalar(
        select(ProjectLedgerEntry.id).where(
            ProjectLedgerEntry.source_type == "RECEIPT",
            ProjectLedgerEntry.source_id == receipt.id,
            ProjectLedgerEntry.entry_type == "RECEIPT",
        )
    )
    add_ledger_entry(
        db,
        receipt.project_id,
        "REVERSAL",
        "RECEIPT",
        receipt.id,
        float(receipt.amount),
        occurred_on=today_local(),
        reversal_of_id=original_entry,
    )
    stage = db.get(ContractStage, receipt.stage_id) if receipt.stage_id else None
    refresh_stage_status(db, stage, "INCOME")
    audit(db, "receipt", receipt.id, "REVERSE", user.id, "APPROVED", "REVERSED")
    db.commit()
    db.refresh(receipt)
    return receipt_view(db, receipt)


@app.get("/api/v1/payments", response_model=list[PaymentView])
def list_payments(
    project_id: int | None = Query(default=None, gt=0),
    contract_id: int | None = Query(default=None, gt=0),
    status: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    keyword: str | None = None,
    submitted_by: int | None = Query(default=None, gt=0),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[PaymentView]:
    user = require_admin_permission(db, "payments", x_demo_user_id)
    scope = project_scope_ids(db, user, "payments")
    query = select(Payment).order_by(Payment.payment_date.desc(), Payment.id.desc())
    if scope is not None:
        query = query.where(Payment.project_id.in_(scope))
    if project_id:
        query = query.where(Payment.project_id == project_id)
    if contract_id:
        query = query.where(Payment.contract_id == contract_id)
    if status:
        query = query.where(Payment.status == status)
    if period_start:
        query = query.where(Payment.payment_date >= period_start)
    if period_end:
        query = query.where(Payment.payment_date <= period_end)
    if submitted_by:
        query = query.where(Payment.submitted_by == submitted_by)
    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(
            Payment.payment_no.contains(value)
            | Payment.payee_name.contains(value)
            | Payment.comment.contains(value)
            | Payment.contract_id.in_(select(Contract.id).where(Contract.name.contains(value) | Contract.contract_no.contains(value)))
        )
    return [payment_view(db, item, user.id) for item in db.scalars(query).all()]


@app.post("/api/v1/payments", response_model=PaymentView, status_code=201)
def create_payment(payload: PaymentCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    user = require_admin_permission(db, "payments", x_demo_user_id)
    require_access(db, "payments", "CREATE", x_demo_user_id)
    contract = resolve_contract(db, payload.contract_id)
    ensure_project_in_scope(db, user, contract.project_id)
    if contract.contract_type != "EXPENSE":
        raise HTTPException(400, "CONTRACT_TYPE_MISMATCH")
    stage = resolve_contract_stage(db, payload.stage_id, contract.id)
    if payload.amount > stage_remaining(db, stage, "EXPENSE"):
        raise HTTPException(400, "STAGE_REMAINING_INSUFFICIENT")
    payment = Payment(
        payment_no=next_document_no(db, Payment, "PAY"),
        project_id=contract.project_id,
        contract_id=contract.id,
        stage_id=stage.id if stage else None,
        amount=payload.amount,
        payment_date=payload.payment_date,
        payee_name=payload.payee_name,
        payee_bank_name=payload.payee_bank_name,
        payee_bank_account=payload.payee_bank_account,
        status="DRAFT",
        submitted_by=user.id,
        submitted_at=None,
        comment=payload.comment,
    )
    apply_contract_budget_snapshot(db, payment, contract)
    db.add(payment)
    db.flush()
    audit(db, "payment", payment.id, "CREATE", user.id, None, "DRAFT")
    db.commit()
    db.refresh(payment)
    return payment_view(db, payment, user.id)


@app.get("/api/v1/payments/{payment_id}", response_model=PaymentView)
def get_payment(payment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    user = payment_access(db, payment, x_demo_user_id)
    return payment_view(db, payment, user.id)


@app.patch("/api/v1/payments/{payment_id}", response_model=PaymentView)
def update_payment(payment_id: int, payload: PaymentUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    user = require_admin_permission(db, "payments", x_demo_user_id)
    require_access(db, "payments", "EDIT", x_demo_user_id)
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    ensure_project_in_scope(db, user, payment.project_id)
    if payment.status not in ("DRAFT", "REJECTED"):
        raise HTTPException(409, "PAYMENT_READ_ONLY")
    contract = resolve_contract(db, payload.contract_id)
    if contract.contract_type != "EXPENSE":
        raise HTTPException(400, "CONTRACT_TYPE_MISMATCH")
    ensure_project_in_scope(db, user, contract.project_id)
    stage = resolve_contract_stage(db, payload.stage_id, contract.id)
    if payload.amount > stage_remaining(db, stage, "EXPENSE"):
        raise HTTPException(400, "STAGE_REMAINING_INSUFFICIENT")
    payment.contract_id = contract.id
    payment.project_id = contract.project_id
    payment.stage_id = stage.id if stage else None
    payment.amount = payload.amount
    payment.payment_date = payload.payment_date
    payment.payee_name = payload.payee_name
    payment.payee_bank_name = payload.payee_bank_name
    payment.payee_bank_account = payload.payee_bank_account
    payment.comment = payload.comment
    apply_contract_budget_snapshot(db, payment, contract)
    audit(db, "payment", payment.id, "UPDATE", user.id, payment.status, payment.status)
    db.commit()
    db.refresh(payment)
    return payment_view(db, payment, user.id)


@app.delete("/api/v1/payments/{payment_id}")
def delete_payment(payment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    user = require_admin_permission(db, "payments", x_demo_user_id)
    require_access(db, "payments", "DELETE", x_demo_user_id)
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    ensure_project_in_scope(db, user, payment.project_id)
    if payment.status not in ("DRAFT", "REJECTED"):
        raise HTTPException(409, "PAYMENT_READ_ONLY")
    db.delete(payment)
    audit(db, "payment", payment.id, "DELETE", user.id, payment.status, None)
    db.commit()
    return {"deleted": True, "payment_id": payment.id}


@app.post("/api/v1/payments/{payment_id}/submit", response_model=PaymentView)
def submit_payment(payment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    user = require_admin_permission(db, "payments", x_demo_user_id)
    require_access(db, "payments", "CREATE", x_demo_user_id)
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    ensure_project_in_scope(db, user, payment.project_id)
    if payment.status not in ("DRAFT", "REJECTED"):
        raise HTTPException(409, "PAYMENT_NOT_RESUBMITTABLE")
    contract = resolve_contract(db, payment.contract_id)
    if contract.contract_type != "EXPENSE" or contract.project_id != payment.project_id:
        raise HTTPException(409, "PAYMENT_CONTRACT_INVALID")
    stage = resolve_contract_stage(db, payment.stage_id, contract.id)
    if float(payment.amount) > payment_submission_remaining(db, stage, payment.id):
        raise HTTPException(409, "STAGE_REMAINING_INSUFFICIENT")
    old_status = payment.status
    payment.submitted_by = user.id
    version, path = resolve_payment_workflow_path(db, payment)
    payment.version += 1
    instance = WorkflowInstance(
        document_type="PAYMENT",
        document_id=payment.id,
        workflow_version_id=version.id,
        applicant_user_id=user.id,
        status="RUNNING",
        current_sequence=int(path[0]["sequence"]),
        snapshot_json=json.dumps({"payment_version": payment.version, "nodes": path}, ensure_ascii=False),
        submitted_at=now_local(),
    )
    db.add(instance)
    db.flush()
    payment.current_workflow_instance_id = instance.id
    payment.status = "PENDING_APPROVAL"
    payment.submitted_at = now_local()
    payment.comment = None
    tasks = assign_workflow_sequence(db, instance, int(path[0]["sequence"]))
    db.add(WorkflowActionLog(workflow_instance_id=instance.id, action="SUBMIT", actor_user_id=user.id, actor_name=user.name, from_status=old_status, to_status="PENDING_APPROVAL"))
    audit(db, "payment", payment.id, "SUBMIT", user.id, old_status, "PENDING_APPROVAL")
    db.commit()
    notify_payment_tasks(db, payment, tasks)
    db.commit()
    db.refresh(payment)
    return payment_view(db, payment, user.id)


@app.post("/api/v1/payments/{payment_id}/approve", response_model=PaymentView)
def approve_payment(payment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    if payment.current_workflow_instance_id:
        user = current_user(db, x_demo_user_id)
        task, instance, node = active_payment_workflow_task(db, payment, user)
        if node.is_payment:
            task.status = "PAID"
            task.processed_by = user.id
            task.processed_at = now_local()
            db.query(WorkflowTask).filter(
                WorkflowTask.workflow_instance_id == instance.id,
                WorkflowTask.node_sequence == task.node_sequence,
                WorkflowTask.id != task.id,
                WorkflowTask.status == "PENDING",
            ).update({"status": "CLOSED"}, synchronize_session=False)
            instance.status = "COMPLETED"
            instance.completed_at = now_local()
            payment.status = "APPROVED"
            payment.approved_by = user.id
            payment.approved_at = now_local()
            budget_item = db.get(ProjectBudgetItem, payment.budget_item_id) if payment.budget_item_id else None
            add_ledger_entry(db, payment.project_id, "PAYMENT", "PAYMENT", payment.id, float(payment.amount), occurred_on=payment.payment_date, budget_item=budget_item)
            stage = db.get(ContractStage, payment.stage_id) if payment.stage_id else None
            refresh_stage_status(db, stage, "EXPENSE")
            db.add(WorkflowActionLog(workflow_instance_id=instance.id, workflow_task_id=task.id, action="CONFIRM_PAYMENT", actor_user_id=user.id, actor_name=user.name, from_status="PENDING_APPROVAL", to_status="APPROVED"))
            audit(db, "payment", payment.id, "CONFIRM_PAYMENT", user.id, "PENDING_APPROVAL", "APPROVED")
            db.commit()
            notify_payment_result(db, payment, "审批通过并已确认支付", user.name)
            db.commit()
            db.refresh(payment)
            return payment_view(db, payment, user.id)
        task.status = "APPROVED"
        task.processed_by = user.id
        task.processed_at = now_local()
        if task.approval_mode == "ANY":
            db.query(WorkflowTask).filter(
                WorkflowTask.workflow_instance_id == instance.id,
                WorkflowTask.node_sequence == task.node_sequence,
                WorkflowTask.id != task.id,
                WorkflowTask.status == "PENDING",
            ).update({"status": "CLOSED"}, synchronize_session=False)
            node_done = True
        else:
            db.flush()
            node_done = not bool(db.scalar(select(WorkflowTask.id).where(
                WorkflowTask.workflow_instance_id == instance.id,
                WorkflowTask.node_sequence == task.node_sequence,
                WorkflowTask.status == "PENDING",
            ).limit(1)))
        db.add(WorkflowActionLog(workflow_instance_id=instance.id, workflow_task_id=task.id, action="APPROVE", actor_user_id=user.id, actor_name=user.name, from_status="PENDING", to_status="APPROVED"))
        next_tasks = advance_payment_workflow(db, instance, user.id) if node_done else []
        audit(db, "payment", payment.id, "APPROVE_NODE", user.id, "PENDING_APPROVAL", "PENDING_APPROVAL", task.node_name)
        db.commit()
        notify_payment_tasks(db, payment, next_tasks)
        db.commit()
        db.refresh(payment)
        return payment_view(db, payment, user.id)
    user = require_admin_permission(db, "cash_approval", x_demo_user_id)
    require_access(db, "cash_approval", "APPROVE", x_demo_user_id)
    if payment.status != "PENDING":
        raise HTTPException(409, "PAYMENT_NOT_PENDING")
    payment.status = "APPROVED"
    payment.approved_by = user.id
    payment.approved_at = now_local()
    budget_item = db.get(ProjectBudgetItem, payment.budget_item_id) if payment.budget_item_id else None
    add_ledger_entry(
        db,
        payment.project_id,
        "PAYMENT",
        "PAYMENT",
        payment.id,
        float(payment.amount),
        occurred_on=payment.payment_date,
        budget_item=budget_item,
    )
    stage = db.get(ContractStage, payment.stage_id) if payment.stage_id else None
    refresh_stage_status(db, stage, "EXPENSE")
    audit(db, "payment", payment.id, "APPROVE", user.id, "PENDING", "APPROVED")
    db.commit()
    db.refresh(payment)
    project = db.get(Project, payment.project_id)
    if payment.submitted_by:
        send_settlement_notification(
            db,
            "payment",
            payment.id,
            "合同付款单",
            payment.payment_no,
            project.name if project else "",
            float(payment.amount),
            payment.submitted_by,
            user.name,
        )
    return payment_view(db, payment, user.id)


@app.post("/api/v1/payments/{payment_id}/reject", response_model=PaymentView)
def reject_payment(payment_id: int, payload: CashRejectAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    if payment.current_workflow_instance_id:
        user = current_user(db, x_demo_user_id)
        task, instance, _node = active_payment_workflow_task(db, payment, user)
        task.status = "REJECTED"
        task.processed_by = user.id
        task.processed_at = now_local()
        task.comment = payload.reason
        db.query(WorkflowTask).filter(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.status == "PENDING").update({"status": "CLOSED"}, synchronize_session=False)
        instance.status = "REJECTED"
        instance.completed_at = now_local()
        payment.status = "REJECTED"
        payment.comment = payload.reason
        db.add(WorkflowActionLog(workflow_instance_id=instance.id, workflow_task_id=task.id, action="REJECT", actor_user_id=user.id, actor_name=user.name, from_status="PENDING_APPROVAL", to_status="REJECTED", comment=payload.reason))
        audit(db, "payment", payment.id, "REJECT", user.id, "PENDING_APPROVAL", "REJECTED", payload.reason)
        db.commit()
        notify_payment_result(db, payment, "已驳回", user.name)
        db.commit()
        db.refresh(payment)
        return payment_view(db, payment, user.id)
    user = require_admin_permission(db, "cash_approval", x_demo_user_id)
    require_access(db, "cash_approval", "APPROVE", x_demo_user_id)
    if payment.status != "PENDING":
        raise HTTPException(409, "PAYMENT_NOT_PENDING")
    payment.status = "REJECTED"
    payment.comment = payload.reason
    audit(db, "payment", payment.id, "REJECT", user.id, "PENDING", "REJECTED", payload.reason)
    db.commit()
    db.refresh(payment)
    return payment_view(db, payment, user.id)


@app.post("/api/v1/payments/{payment_id}/reverse", response_model=PaymentView)
def reverse_payment(payment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    user = require_admin_permission(db, "cash_approval", x_demo_user_id)
    require_access(db, "cash_approval", "APPROVE", x_demo_user_id)
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    if payment.status != "APPROVED":
        raise HTTPException(409, "PAYMENT_NOT_APPROVED")
    payment.status = "REVERSED"
    original_entry = db.scalar(
        select(ProjectLedgerEntry.id).where(
            ProjectLedgerEntry.source_type == "PAYMENT",
            ProjectLedgerEntry.source_id == payment.id,
            ProjectLedgerEntry.entry_type == "PAYMENT",
        )
    )
    add_ledger_entry(
        db,
        payment.project_id,
        "REVERSAL",
        "PAYMENT",
        payment.id,
        float(payment.amount),
        occurred_on=today_local(),
        reversal_of_id=original_entry,
    )
    stage = db.get(ContractStage, payment.stage_id) if payment.stage_id else None
    refresh_stage_status(db, stage, "EXPENSE")
    audit(db, "payment", payment.id, "REVERSE", user.id, "APPROVED", "REVERSED")
    db.commit()
    db.refresh(payment)
    return payment_view(db, payment, user.id)


@app.get("/api/v1/worklogs", response_model=WorklogList)
def list_worklogs(status: str | None = None, period_start: date | None = None, period_end: date | None = None, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> WorklogList:
    user = current_user(db, x_demo_user_id)
    query = select(Worklog).where(Worklog.user_id == user.id).order_by(Worklog.start_date.desc(), Worklog.id.desc())
    if status:
        query = query.where(Worklog.status == status)
    if period_start:
        query = query.where(Worklog.start_date >= period_start)
    if period_end:
        query = query.where(Worklog.end_date <= period_end)
    items = list(db.scalars(query).all())
    return WorklogList(items=[worklog_view(item) for item in items], summary={"quantity": sum(float(item.quantity) for item in items), "count": len(items)})


def admin_worklog_dataset(
    db: Session,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    department_id: int | None = None,
    department_name: str | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> tuple[list[Worklog], dict[int, ApprovalTask], dict[int, str], dict[int, str], list[str]]:
    """返回工时台账筛选后的全部记录及快照，列表分页和导出共用同一口径。"""
    departments = db.scalars(select(Department)).all()
    department_index = DepartmentIndex(departments)
    projects = db.scalars(select(Project)).all()
    project_department_ids = {project.id: project.department_id for project in projects}
    project_department_labels = {
        project.id: department_index.path(project.department_id) if project.department_id else (project.department_name or "未分配部门")
        for project in projects
    }
    option_department_ids = {project.department_id for project in projects if project.department_id}
    department_options = department_index.options(department_index.with_ancestors(option_department_ids), active_only=False)
    selected_department_id = department_index.resolve(department_id, department_name)
    selected_department_ids = department_index.descendants(selected_department_id) if selected_department_id else set()
    user_departments = {
        user.id: (department_index.path(user.department_id) if user.department_id else "未分配部门")
        for user in db.scalars(select(User)).all()
    }
    query = select(Worklog).order_by(Worklog.start_date.desc(), Worklog.id.desc())
    if period_start:
        query = query.where(Worklog.start_date >= period_start)
    if period_end:
        query = query.where(Worklog.end_date <= period_end)
    if user_id:
        query = query.where(Worklog.user_id == user_id)
    if project_id:
        query = query.where(Worklog.project_id == project_id)
    if status:
        query = query.where(Worklog.status == status)
    items = list(db.scalars(query).all())
    keyword_value = keyword.strip().casefold() if keyword and keyword.strip() else ""
    if selected_department_ids:
        items = [item for item in items if project_department_ids.get(item.project_id) in selected_department_ids]
    if keyword_value:
        items = [item for item in items if keyword_value in " ".join((item.user_name_snapshot, item.project_name_snapshot, item.description, item.stage)).casefold()]

    latest_tasks: dict[int, ApprovalTask] = {}
    worklog_ids = [item.id for item in items]
    if worklog_ids:
        tasks = db.scalars(select(ApprovalTask).where(ApprovalTask.worklog_id.in_(worklog_ids)).order_by(ApprovalTask.version.desc(), ApprovalTask.id.desc())).all()
        for task in tasks:
            latest_tasks.setdefault(task.worklog_id, task)
    return items, latest_tasks, user_departments, project_department_labels, department_options


@app.get("/api/v1/admin/worklogs", response_model=AdminWorklogList)
def list_admin_worklogs(
    period_start: date | None = None,
    period_end: date | None = None,
    department_id: int | None = Query(default=None, gt=0),
    department_name: str | None = None,
    user_id: int | None = None,
    project_id: int | None = Query(default=None, gt=0),
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AdminWorklogList:
    """管理员分页查询全部工时，按日期、一级部门、填报人、状态和关键词筛选。"""
    require_admin_permission(db, "worklogs", x_demo_user_id)
    if page < 1:
        raise HTTPException(400, "INVALID_PAGE")
    if page_size < 1 or page_size > 200:
        raise HTTPException(400, "INVALID_PAGE_SIZE")
    if period_start and period_end and period_start > period_end:
        raise HTTPException(400, "INVALID_DATE_RANGE")
    items, latest_tasks, user_departments, project_department_labels, department_options = admin_worklog_dataset(
        db,
        period_start=period_start,
        period_end=period_end,
        department_id=department_id,
        department_name=department_name,
        user_id=user_id,
        project_id=project_id,
        status=status,
        keyword=keyword,
    )
    total = len(items)
    page_count = max(1, (total + page_size - 1) // page_size)
    page = min(page, page_count)
    page_items = items[(page - 1) * page_size:page * page_size]
    result_items = [
        admin_worklog_view(
            item,
            latest_tasks[item.id].serial_no if item.id in latest_tasks else None,
            user_departments.get(item.user_id, "未分配部门"),
            project_department_labels.get(item.project_id, "未分配部门"),
        )
        for item in page_items
    ]
    summary = {
        "quantity": round(sum(float(item.quantity) for item in items), 2),
        "approved_quantity": round(sum(float(item.quantity) for item in items if item.status in {"APPROVED", "LOCKED"}), 2),
        "count": len(items),
        "approved_count": sum(item.status in {"APPROVED", "LOCKED"} for item in items),
        "pending_count": sum(item.status == "PENDING_APPROVAL" for item in items),
        "draft_count": sum(item.status == "DRAFT" for item in items),
        "rejected_count": sum(item.status == "REJECTED" for item in items),
    }
    return AdminWorklogList(items=result_items, total=total, page=page, page_size=page_size, page_count=page_count, summary=summary, department_options=department_options)


@app.get("/api/v1/admin/worklogs/export")
def export_admin_worklogs(
    period_start: date | None = None,
    period_end: date | None = None,
    department_id: int | None = Query(default=None, gt=0),
    department_name: str | None = None,
    user_id: int | None = None,
    project_id: int | None = Query(default=None, gt=0),
    status: str | None = None,
    keyword: str | None = None,
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出工时台账明细 CSV；筛选条件与后台工时台账列表完全一致。"""
    require_access(db, "worklogs", "EXPORT", x_demo_user_id)
    if period_start and period_end and period_start > period_end:
        raise HTTPException(400, "INVALID_DATE_RANGE")
    items, latest_tasks, user_departments, project_department_labels, _ = admin_worklog_dataset(
        db,
        period_start=period_start,
        period_end=period_end,
        department_id=department_id,
        department_name=department_name,
        user_id=user_id,
        project_id=project_id,
        status=status,
        keyword=keyword,
    )
    status_names = {"DRAFT": "草稿", "PENDING_APPROVAL": "审批中", "APPROVED": "已通过", "REJECTED": "已驳回", "LOCKED": "已锁定"}
    work_type_names = {"PROJECT": "项目工时", "MANAGEMENT": "管理工时", "OTHER": "其它工时"}
    work_status_names = {"LOCAL": "本地", "BUSINESS_TRIP": "出差", "REMOTE": "异地办公", "LEAVE": "休假"}
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["工时单号", "填报人", "填报人部门", "项目部门", "项目", "项目阶段", "工时类型", "工作状态", "开始日期", "结束日期", "工时天数", "审批人", "审批状态", "工作描述", "提交时间", "处理时间", "审批意见"])
    for item in items:
        task = latest_tasks.get(item.id)
        processed_at = task.processed_at if task and task.processed_at else item.approved_at or ""
        writer.writerow([
            task.serial_no if task else "",
            item.user_name_snapshot,
            user_departments.get(item.user_id, "未分配部门"),
            project_department_labels.get(item.project_id, "未分配部门"),
            item.project_name_snapshot,
            item.stage,
            work_type_names.get(item.work_type, item.work_type),
            work_status_names.get(item.work_status, item.work_status),
            item.start_date,
            item.end_date,
            f"{float(item.quantity):g}",
            item.approver_name_snapshot or "",
            status_names.get(item.status, item.status),
            item.description,
            item.submitted_at or "",
            processed_at,
            item.approval_comment or item.rejection_reason or (task.comment if task else "") or "",
        ])
    start_label = period_start.strftime("%Y%m%d") if period_start else "start"
    end_label = period_end.strftime("%Y%m%d") if period_end else "end"
    filename = f"xinye-worklog-ledger-{start_label}-{end_label}.csv"
    return StreamingResponse(iter([output.getvalue().encode("utf-8-sig")]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/v1/admin/personnel-costs", response_model=PersonnelCostList)
def list_personnel_costs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    department_id: int | None = Query(default=None, gt=0),
    department_name: str | None = Query(default=None),
    user_id: int | None = Query(default=None, gt=0),
    configured_only: bool = Query(default=False),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> PersonnelCostList:
    """管理员分页读取组织用户的单天成本配置。"""
    require_admin_permission(db, "personnel_costs", x_demo_user_id)
    department_index = DepartmentIndex(db.scalars(select(Department)).all())
    selected_department_id = department_index.resolve(department_id, department_name)
    selected_department_ids = department_index.descendants(selected_department_id) if selected_department_id else set()
    query = select(User).outerjoin(Department, User.department_id == Department.id).where(User.employment_status == "ACTIVE")
    if configured_only:
        query = query.where(User.daily_cost.is_not(None))
    if selected_department_ids:
        query = query.where(User.department_id.in_(selected_department_ids))
    if user_id:
        query = query.where(User.id == user_id)
    users = db.scalars(query.order_by(User.name, User.id)).all()
    total = len(users)
    page_count = max(1, (total + page_size - 1) // page_size)
    page = min(page, page_count)
    page_items = users[(page - 1) * page_size:page * page_size]
    department_options = department_index.options(active_only=True)
    configured_costs = [float(user.daily_cost) for user in users if user.daily_cost is not None]
    configured_user_ids = db.scalars(select(User.id).where(User.employment_status == "ACTIVE", User.daily_cost.is_not(None))).all()
    return PersonnelCostList(
        items=[personnel_cost_view(db, user) for user in page_items],
        total=total,
        page=page,
        page_size=page_size,
        page_count=page_count,
        department_options=department_options,
        configured_user_ids=[int(user_id) for user_id in configured_user_ids],
        summary={"configured_count": len(configured_costs), "unset_count": total - len(configured_costs), "total_daily_cost": round(sum(configured_costs), 2), "average_daily_cost": round(sum(configured_costs) / len(configured_costs), 2) if configured_costs else 0},
    )


@app.patch("/api/v1/admin/personnel-costs/{user_id}", response_model=PersonnelCostView)
def update_personnel_cost(user_id: int, payload: PersonnelCostUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PersonnelCostView:
    """管理员维护组织用户单天成本；组织同步不会覆盖该字段。"""
    require_admin_permission(db, "personnel_costs", x_demo_user_id)
    require_access(db, "personnel_costs", "EDIT", x_demo_user_id)
    user = db.get(User, user_id)
    if not user or user.employment_status != "ACTIVE":
        raise HTTPException(404, "USER_NOT_FOUND")
    user.daily_cost = payload.daily_cost
    refresh_missing_worklog_cost(db, user_id=user.id)
    audit(db, "user", user.id, "UPDATE_DAILY_COST", current_user(db, x_demo_user_id).id, None, None, str(payload.daily_cost) if payload.daily_cost is not None else "")
    db.commit()
    db.refresh(user)
    return personnel_cost_view(db, user)


@app.patch("/api/v1/admin/worklogs/{worklog_id}", response_model=AdminWorklogView)
def update_admin_worklog(worklog_id: int, payload: WorklogUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> AdminWorklogView:
    """管理员修改工时内容，保留现有审批状态和审批任务。"""
    admin = require_admin_permission(db, "worklogs", x_demo_user_id)
    require_access(db, "worklogs", "EDIT", x_demo_user_id)
    item = db.get(Worklog, worklog_id)
    if not item:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    project = db.get(Project, payload.project_id)
    if not project or project.status == "DELETED" or not project.allow_worklog:
        raise HTTPException(400, "PROJECT_NOT_FILLABLE")
    validate_worklog_dates(db, item.user_id, payload.start_date, payload.end_date, item.id)
    validate_worklog_quantity(payload.start_date, payload.end_date, payload.quantity)
    validate_worklog_options(db, payload.stage, payload.work_type, payload.work_status)
    old_value = f"{item.project_name_snapshot}|{item.stage}|{item.start_date}|{item.end_date}|{item.quantity}|{item.description}"
    item.project_id = project.id
    item.project_name_snapshot = project.name
    item.stage = payload.stage
    item.work_type = payload.work_type
    item.work_status = payload.work_status
    item.start_date = payload.start_date
    item.end_date = payload.end_date
    item.quantity = payload.quantity
    item.unit = "DAY"
    item.description = payload.description
    new_value = f"{item.project_name_snapshot}|{item.stage}|{item.start_date}|{item.end_date}|{item.quantity}|{item.description}"
    audit(db, "worklog", item.id, "ADMIN_UPDATE", admin.id, item.status, item.status, f"{old_value} -> {new_value}")
    db.commit()
    db.refresh(item)
    project_departments = {project.id: project.department_name or "未分配部门"}
    department = db.get(Department, project.department_id) if project.department_id else None
    if department and department.parent_name:
        project_departments[project.id] = department.parent_name
    user = db.get(User, item.user_id)
    user_department = db.get(Department, user.department_id).name if user and user.department_id and db.get(Department, user.department_id) else "未分配部门"
    task = db.scalar(select(ApprovalTask).where(ApprovalTask.worklog_id == item.id).order_by(ApprovalTask.version.desc(), ApprovalTask.id.desc()))
    return admin_worklog_view(item, task.serial_no if task else None, user_department, project_departments[project.id])


@app.delete("/api/v1/admin/worklogs/{worklog_id}")
def delete_admin_worklog(worklog_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """管理员删除工时及关联审批通知，保留删除审计事件。"""
    admin = require_admin_permission(db, "worklogs", x_demo_user_id)
    require_access(db, "worklogs", "DELETE", x_demo_user_id)
    item = db.get(Worklog, worklog_id)
    if not item:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    old_status = item.status
    task_ids = [task.id for task in db.scalars(select(ApprovalTask).where(ApprovalTask.worklog_id == item.id)).all()]
    if task_ids:
        for notification in db.scalars(select(Notification).where(Notification.approval_task_id.in_(task_ids))).all():
            db.delete(notification)
        for task in db.scalars(select(ApprovalTask).where(ApprovalTask.id.in_(task_ids))).all():
            db.delete(task)
        db.flush()
    audit(db, "worklog", item.id, "ADMIN_DELETE", admin.id, old_status, None, item.project_name_snapshot)
    db.delete(item)
    db.commit()
    return {"deleted": True, "worklog_id": worklog_id}


@app.get("/api/v1/worklogs/{worklog_id}", response_model=WorklogView)
def get_worklog(worklog_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> WorklogView:
    user = current_user(db, x_demo_user_id)
    item = db.get(Worklog, worklog_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    return worklog_view(item)


@app.get("/api/v1/worklogs/{worklog_id}/approval", response_model=ApprovalTaskView)
def get_worklog_approval(worklog_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ApprovalTaskView:
    """读取员工自己提交的最新审批版本，供工时详情页跳转。"""
    user = current_user(db, x_demo_user_id)
    item = db.get(Worklog, worklog_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    task = db.scalar(select(ApprovalTask).where(ApprovalTask.worklog_id == item.id).order_by(ApprovalTask.version.desc()))
    if not task:
        if item.status not in {"APPROVED", "LOCKED"}:
            raise HTTPException(404, "APPROVAL_NOT_FOUND")
        # 兼容旧导入或演示历史数据：没有本地审批任务时仍返回只读详情快照。
        return ApprovalTaskView(
            id=0,
            worklog_id=item.id,
            version=max(item.approval_version, 1),
            serial_no=f"WL-HISTORY-{item.id:04d}",
            submitter_user_id=item.user_id,
            approver_user_id=item.approver_user_id or item.user_id,
            status="APPROVED" if item.status == "APPROVED" else "LOCKED",
            comment=item.approval_comment,
            submitted_at=item.submitted_at or item.created_at,
            processed_at=item.approved_at,
            processed_by=item.approver_user_id,
            worklog=worklog_view(item),
            notification=None,
        )
    return task_view(db, task)


@app.post("/api/v1/worklogs", response_model=WorklogView, status_code=201)
def create_worklog(payload: WorklogCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> WorklogView:
    user = current_user(db, x_demo_user_id)
    validate_worklog_dates(db, user.id, payload.start_date, payload.end_date)
    validate_worklog_quantity(payload.start_date, payload.end_date, payload.quantity)
    validate_worklog_options(db, payload.stage, payload.work_type, payload.work_status)
    project = db.get(Project, payload.project_id)
    if not project or not project.allow_worklog or project.status != "ACTIVE":
        raise HTTPException(400, "PROJECT_NOT_FILLABLE")
    item = Worklog(user_id=user.id, user_name_snapshot=user.name, project_id=project.id, project_name_snapshot=project.name, stage=payload.stage, work_type=payload.work_type, work_status=payload.work_status, start_date=payload.start_date, end_date=payload.end_date, quantity=payload.quantity, unit=payload.unit, description=payload.description, status="DRAFT")
    db.add(item)
    db.commit()
    db.refresh(item)
    if payload.submit:
        submit_item(db, item, user)
        return worklog_view(db.get(Worklog, item.id))
    return worklog_view(item)


@app.patch("/api/v1/worklogs/{worklog_id}", response_model=WorklogView)
def update_worklog(worklog_id: int, payload: WorklogUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> WorklogView:
    user = current_user(db, x_demo_user_id)
    item = db.get(Worklog, worklog_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    if item.status not in ["DRAFT", "REJECTED"]:
        raise HTTPException(409, "WORKLOG_READ_ONLY")
    validate_worklog_dates(db, user.id, payload.start_date, payload.end_date, item.id)
    validate_worklog_quantity(payload.start_date, payload.end_date, payload.quantity)
    validate_worklog_options(db, payload.stage, payload.work_type, payload.work_status)
    project = db.get(Project, payload.project_id)
    if not project or not project.allow_worklog or project.status != "ACTIVE":
        raise HTTPException(400, "PROJECT_NOT_FILLABLE")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.project_id = project.id
    item.project_name_snapshot = project.name
    db.commit()
    db.refresh(item)
    return worklog_view(item)


@app.delete("/api/v1/worklogs/{worklog_id}")
def delete_worklog(worklog_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, bool]:
    user = current_user(db, x_demo_user_id)
    item = db.get(Worklog, worklog_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    if item.status not in ["DRAFT", "REJECTED"]:
        raise HTTPException(409, "WORKLOG_READ_ONLY")
    db.delete(item)
    db.commit()
    return {"deleted": True}


@app.post("/api/v1/worklogs/{worklog_id}/submit", response_model=ApprovalTaskView)
def submit_worklog(worklog_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ApprovalTaskView:
    user = current_user(db, x_demo_user_id)
    item = db.get(Worklog, worklog_id)
    if not item:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    return submit_item(db, item, user)


@app.get("/api/v1/approvals/pending", response_model=list[ApprovalTaskView])
def pending_approvals(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[ApprovalTaskView]:
    user = current_user(db, x_demo_user_id)
    require_access(db, "approvals", "VIEW", x_demo_user_id)
    tasks = db.scalars(select(ApprovalTask).where(ApprovalTask.approver_user_id == user.id, ApprovalTask.status == "PENDING").order_by(ApprovalTask.submitted_at.desc())).all()
    return [task_view(db, task) for task in tasks]


@app.get("/api/v1/approvals/processed", response_model=list[ApprovalTaskView])
def processed_approvals(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[ApprovalTaskView]:
    """返回当前审批人已经处理的工时审批，供审批历史 TAB 使用。"""
    user = current_user(db, x_demo_user_id)
    require_access(db, "approvals", "VIEW", x_demo_user_id)
    tasks = db.scalars(
        select(ApprovalTask)
        .where(ApprovalTask.approver_user_id == user.id, ApprovalTask.status.in_(["APPROVED", "REJECTED"]))
        .order_by(ApprovalTask.processed_at.desc(), ApprovalTask.id.desc())
    ).all()
    return [task_view(db, task) for task in tasks]


@app.get("/api/v1/approvals/{task_id}", response_model=ApprovalTaskView)
def get_approval(task_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ApprovalTaskView:
    user = current_user(db, x_demo_user_id)
    task = db.get(ApprovalTask, task_id)
    if not task or user.id not in [task.approver_user_id, task.submitter_user_id]:
        raise HTTPException(404, "APPROVAL_NOT_FOUND")
    return task_view(db, task)


def ensure_approver(task: ApprovalTask, user: User) -> None:
    """阻止非当前审批人处理任务。"""
    if task.approver_user_id != user.id:
        raise HTTPException(403, "NOT_APPROVER")
    if task.status != "PENDING":
        raise HTTPException(409, "APPROVAL_ALREADY_PROCESSED")


@app.post("/api/v1/approvals/{task_id}/approve", response_model=ApprovalTaskView)
def approve_task(task_id: int, payload: ApprovalAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ApprovalTaskView:
    user = current_user(db, x_demo_user_id)
    require_access(db, "approvals", "APPROVE", x_demo_user_id)
    task = db.get(ApprovalTask, task_id)
    if not task:
        raise HTTPException(404, "APPROVAL_NOT_FOUND")
    ensure_approver(task, user)
    if payload.version != task.version:
        raise HTTPException(409, "VERSION_CONFLICT")
    item = db.get(Worklog, task.worklog_id)
    old = task.status
    task.status = "APPROVED"
    task.comment = payload.comment
    task.processed_at = now_local()
    task.processed_by = user.id
    item.status = "APPROVED"
    item.approved_at = task.processed_at
    item.approval_comment = payload.comment
    submitter = db.get(User, item.user_id)
    daily_cost = float(submitter.daily_cost) if submitter and submitter.daily_cost is not None else 0
    item.daily_cost_snapshot = daily_cost
    item.cost_amount_snapshot = round(float(item.quantity) * daily_cost, 2)
    labor_budget_item = project_labor_budget_item(db, item.project_id)
    add_ledger_entry(
        db,
        item.project_id,
        "PERSONNEL_COST",
        "WORKLOG",
        item.id,
        item.cost_amount_snapshot,
        occurred_on=item.start_date,
        budget_item=labor_budget_item,
    )
    audit(db, "approval_task", task.id, "APPROVE", user.id, old, "APPROVED", payload.comment)
    db.commit()
    db.refresh(task)
    return task_view(db, task)


@app.post("/api/v1/approvals/{task_id}/reject", response_model=ApprovalTaskView)
def reject_task(task_id: int, payload: RejectionAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ApprovalTaskView:
    user = current_user(db, x_demo_user_id)
    require_access(db, "approvals", "APPROVE", x_demo_user_id)
    task = db.get(ApprovalTask, task_id)
    if not task:
        raise HTTPException(404, "APPROVAL_NOT_FOUND")
    ensure_approver(task, user)
    if payload.version != task.version:
        raise HTTPException(409, "VERSION_CONFLICT")
    item = db.get(Worklog, task.worklog_id)
    old = task.status
    task.status = "REJECTED"
    task.comment = payload.reason
    task.processed_at = now_local()
    task.processed_by = user.id
    item.status = "REJECTED"
    item.rejection_reason = payload.reason
    item.approval_comment = None
    audit(db, "approval_task", task.id, "REJECT", user.id, old, "REJECTED", payload.reason)
    db.commit()
    db.refresh(task)
    return task_view(db, task)


@app.post("/api/v1/approvals/{task_id}/remind", response_model=NotificationView)
def remind_task(task_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> NotificationView:
    user = current_user(db, x_demo_user_id)
    task = db.get(ApprovalTask, task_id)
    if not task:
        raise HTTPException(404, "APPROVAL_NOT_FOUND")
    ensure_approver(task, user)
    item = db.get(Worklog, task.worklog_id)
    approver = db.get(User, task.approver_user_id)
    submitter = db.get(User, task.submitter_user_id)
    channel = notification_policy_channel(db, "WORKLOG_APPROVAL")
    notification = Notification(approval_task_id=task.id, recipient_user_id=approver.id, channel=channel or feishu.notification_mode, idempotency_key=f"approval:{task.id}:remind:{now_local().timestamp()}", retry_count=1)
    db.add(notification)
    db.flush()
    if not notification_policy_enabled(db, "WORKLOG_APPROVAL"):
        notification.status = "SKIPPED"
        db.commit()
        db.refresh(notification)
        return NotificationView.model_validate(notification)
    result = feishu.notify_approval_submitted(task.serial_no, approver.name, submitter.name, item.project_name_snapshot, item.description, str(item.start_date), float(item.quantity), item.unit, worklog_approval_detail_url(task.id), recipient_open_id=approver.open_id, channel=channel)
    notification.status = result.status
    notification.message_id = result.message_id
    notification.error_message = result.error_message
    notification.sent_at = now_local() if result.status == "SENT" else None
    db.commit()
    db.refresh(notification)
    return NotificationView.model_validate(notification)


@app.get("/api/v1/reports/workload", response_model=ReportView)
def workload_report(
    period_start: date | None = None,
    period_end: date | None = None,
    department_id: int | None = Query(default=None, gt=0),
    department_name: str | None = None,
    db: Session = Depends(get_db),
) -> ReportView:
    """按日期和部门树汇总看板数据；选择部门会包含其全部下级部门。"""
    start = period_start or today_local().replace(day=1)
    end = period_end or today_local()
    if start > end:
        raise HTTPException(400, "INVALID_DATE_RANGE")

    department_index = DepartmentIndex(db.scalars(select(Department)).all())
    projects = db.scalars(select(Project)).all()
    projects_by_id = {item.id: item for item in projects}

    project_department = {project.id: department_index.root_name(project.department_id) if project.department_id else "未分配部门" for project in projects}
    project_department_ids = {project.id: project.department_id for project in projects}
    project_ids_with_departments = {project.department_id for project in projects if project.status != "DELETED" and project.department_id}
    department_options = department_index.options(department_index.with_ancestors(project_ids_with_departments), active_only=False)
    selected_department_id = department_index.resolve(department_id, department_name)
    selected_department_ids = department_index.descendants(selected_department_id) if selected_department_id else set()

    all_rows = db.scalars(select(Worklog).where(Worklog.start_date >= start, Worklog.end_date <= end)).all()
    scoped_rows = [item for item in all_rows if item.unit == "DAY" and (not selected_department_ids or project_department_ids.get(item.project_id) in selected_department_ids)]
    approved_rows = [item for item in scoped_rows if item.status in {"APPROVED", "LOCKED"}]
    users_by_id = {user.id: user for user in db.scalars(select(User)).all()}
    scoped_projects = [project for project in projects if project.status != "DELETED" and (not selected_department_ids or project.department_id in selected_department_ids)]
    project_actual_days: dict[int, float] = defaultdict(float)
    project_actual_cost: dict[int, float] = defaultdict(float)
    department_actual_cost: dict[str, float] = defaultdict(float)
    missing_cost_user_ids: set[int] = set()
    pending_count = sum(1 for item in scoped_rows if item.status == "PENDING_APPROVAL")
    status_counts: dict[str, int] = {}
    overdue_pending_count = 0
    for item in scoped_rows:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
        if item.status == "PENDING_APPROVAL" and item.submitted_at and now_local() - item.submitted_at >= timedelta(days=1):
            overdue_pending_count += 1
    by_project: dict[str, float] = {}
    by_project_stage: dict[tuple[str, str], float] = {}
    by_project_stage_unit: dict[tuple[str, str, str], float] = {}
    by_stage: dict[str, float] = {}
    by_stage_unit: dict[tuple[str, str], float] = {}
    by_user: dict[str, float] = {}
    by_user_unit: dict[tuple[str, str], float] = {}
    by_status: dict[str, float] = {}
    by_status_unit: dict[tuple[str, str], float] = {}
    by_work_type: dict[str, float] = {}
    by_work_type_unit: dict[tuple[str, str], float] = {}
    by_department: dict[str, float] = {}
    by_unit: dict[str, float] = {}
    by_project_unit: dict[tuple[str, str], float] = {}
    by_department_unit: dict[tuple[str, str], float] = {}
    by_day_unit: dict[tuple[str, str], float] = {}
    for item in approved_rows:
        quantity = float(item.quantity)
        unit = "DAY"
        department = project_department.get(item.project_id, "未分配部门")
        project_actual_days[item.project_id] += quantity
        person = users_by_id.get(item.user_id)
        if person is None or person.daily_cost is None:
            missing_cost_user_ids.add(item.user_id)
        else:
            cost = quantity * float(person.daily_cost)
            project_actual_cost[item.project_id] += cost
            department_actual_cost[department] += cost
        by_project[item.project_name_snapshot] = by_project.get(item.project_name_snapshot, 0) + quantity
        project_stage_key = (item.project_name_snapshot, item.stage)
        by_project_stage[project_stage_key] = by_project_stage.get(project_stage_key, 0) + quantity
        project_stage_unit_key = (item.project_name_snapshot, item.stage, unit)
        by_project_stage_unit[project_stage_unit_key] = by_project_stage_unit.get(project_stage_unit_key, 0) + quantity
        by_stage[item.stage] = by_stage.get(item.stage, 0) + quantity
        by_stage_unit[(item.stage, unit)] = by_stage_unit.get((item.stage, unit), 0) + quantity
        by_user[item.user_name_snapshot] = by_user.get(item.user_name_snapshot, 0) + quantity
        by_user_unit[(item.user_name_snapshot, unit)] = by_user_unit.get((item.user_name_snapshot, unit), 0) + quantity
        by_status[item.status] = by_status.get(item.status, 0) + quantity
        by_status_unit[(item.status, unit)] = by_status_unit.get((item.status, unit), 0) + quantity
        by_work_type[item.work_type] = by_work_type.get(item.work_type, 0) + quantity
        by_work_type_unit[(item.work_type, unit)] = by_work_type_unit.get((item.work_type, unit), 0) + quantity
        by_department[department] = by_department.get(department, 0) + quantity
        by_unit[unit] = by_unit.get(unit, 0) + quantity
        by_project_unit[(item.project_name_snapshot, unit)] = by_project_unit.get((item.project_name_snapshot, unit), 0) + quantity
        by_department_unit[(department, unit)] = by_department_unit.get((department, unit), 0) + quantity
        by_day_unit[(str(item.start_date), unit)] = by_day_unit.get((str(item.start_date), unit), 0) + quantity

    def breakdown(values: dict[str, float]) -> list[dict[str, str | float]]:
        return [{"name": name, "quantity": round(quantity, 2)} for name, quantity in sorted(values.items(), key=lambda pair: pair[1], reverse=True)]

    def unit_breakdown(values: dict[tuple[str, str], float]) -> list[dict[str, str | float]]:
        return [{"name": name, "unit": unit, "quantity": round(quantity, 2)} for (name, unit), quantity in sorted(values.items(), key=lambda pair: pair[1], reverse=True)]

    def project_stage_unit_breakdown(values: dict[tuple[str, str, str], float]) -> list[dict[str, str | float]]:
        return [{"name": project, "stage": stage, "unit": unit, "quantity": round(quantity, 2)} for (project, stage, unit), quantity in sorted(values.items(), key=lambda pair: pair[1], reverse=True)]

    project_ids = {item.project_id for item in approved_rows}
    user_ids = {item.user_id for item in approved_rows}
    budget_days = sum(float(project.budget_days or 0) for project in scoped_projects)
    budget_cost = sum(float(project.budget_cost or 0) for project in scoped_projects)
    actual_days = round(sum(project_actual_days.values()), 2)
    project_budget_actual = [
        {"name": project.name, "unit": "DAY", "budget_days": round(float(project.budget_days or 0), 2), "actual_days": round(project_actual_days.get(project.id, 0), 2), "budget_cost": round(float(project.budget_cost or 0), 2), "actual_cost": round(project_actual_cost.get(project.id, 0), 2), "remaining_cost": round(float(project.budget_cost or 0) - project_actual_cost.get(project.id, 0), 2), "cost_usage_rate": round(project_actual_cost.get(project.id, 0) / float(project.budget_cost) * 100, 1) if float(project.budget_cost or 0) > 0 else None}
        for project in sorted(scoped_projects, key=lambda item: (project_actual_days.get(item.id, 0), float(item.budget_days or 0)), reverse=True)
    ]
    project_cost_rows = [{"name": project.name, "unit": "COST", "quantity": round(project_actual_cost.get(project.id, 0), 2)} for project in sorted(scoped_projects, key=lambda item: project_actual_cost.get(item.id, 0), reverse=True) if project_actual_cost.get(project.id, 0) > 0]
    department_cost_rows = [{"name": name, "unit": "COST", "quantity": round(quantity, 2)} for name, quantity in sorted(department_actual_cost.items(), key=lambda pair: pair[1], reverse=True)]
    over_budget_project_count = sum(1 for row in project_budget_actual if row["budget_days"] > 0 and row["actual_days"] > row["budget_days"])
    over_budget_cost_project_count = sum(1 for row in project_budget_actual if row["budget_cost"] > 0 and row["actual_cost"] > row["budget_cost"])
    return ReportView(
        scope={"period_start": str(start), "period_end": str(end), "department_name": department_index.path(selected_department_id) if selected_department_id else "全部部门", "department_options": department_options, "status": ["APPROVED", "LOCKED"]},
        metrics={"total_quantity": round(sum(by_project.values()), 2), "total_days": round(by_unit.get("DAY", 0), 2), "budget_days": round(budget_days, 2), "actual_cost": round(sum(project_actual_cost.values()), 2), "budget_cost": round(budget_cost, 2), "budget_usage_rate": round(actual_days / budget_days * 100, 1) if budget_days else 0, "cost_usage_rate": round(sum(project_actual_cost.values()) / budget_cost * 100, 1) if budget_cost else 0, "missing_cost_user_count": len(missing_cost_user_ids), "over_budget_project_count": over_budget_project_count, "over_budget_cost_project_count": over_budget_cost_project_count, "user_count": len(user_ids), "project_count": len(project_ids), "execution_project_count": sum(1 for project_id in project_ids if projects_by_id.get(project_id) and projects_by_id[project_id].status == "ACTIVE"), "pending_count": pending_count, "approved_count": len(approved_rows), "submitted_count": len(scoped_rows), "rejected_count": status_counts.get("REJECTED", 0), "approval_rate": round((len(approved_rows) / (len(approved_rows) + status_counts.get("REJECTED", 0)) * 100), 1) if len(approved_rows) + status_counts.get("REJECTED", 0) else 0, "overdue_pending_count": overdue_pending_count},
        breakdowns={"by_project": breakdown(by_project), "by_project_unit": unit_breakdown(by_project_unit), "by_project_budget_actual": project_budget_actual, "by_project_cost": project_cost_rows, "by_department_cost": department_cost_rows, "by_project_stage": [{"name": project, "stage": stage, "quantity": round(quantity, 2)} for (project, stage), quantity in sorted(by_project_stage.items(), key=lambda pair: pair[1], reverse=True)], "by_project_stage_unit": project_stage_unit_breakdown(by_project_stage_unit), "by_stage": breakdown(by_stage), "by_stage_unit": unit_breakdown(by_stage_unit), "by_user": breakdown(by_user), "by_user_unit": unit_breakdown(by_user_unit), "by_status": breakdown(by_status), "by_status_unit": unit_breakdown(by_status_unit), "approval_status": [{"name": name, "quantity": quantity} for name, quantity in sorted(status_counts.items(), key=lambda pair: pair[1], reverse=True)], "by_work_type": breakdown(by_work_type), "by_work_type_unit": unit_breakdown(by_work_type_unit), "by_department": breakdown(by_department), "by_department_unit": unit_breakdown(by_department_unit), "by_day_unit": unit_breakdown(by_day_unit), "by_unit": breakdown(by_unit)},
        generated_at=now_local(),
    )


@app.get("/api/v1/reports/workload/export")
def export_workload(
    period_start: date | None = None,
    period_end: date | None = None,
    department_id: int | None = Query(default=None, gt=0),
    department_name: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """按看板日期和部门树条件导出天数工时明细 CSV。"""
    user = require_access(db, "reports", "EXPORT")
    start = period_start or today_local().replace(day=1)
    end = period_end or today_local()
    if start > end:
        raise HTTPException(400, "INVALID_DATE_RANGE")

    department_index = DepartmentIndex(db.scalars(select(Department)).all())
    projects = db.scalars(select(Project)).all()
    projects_by_id = {item.id: item for item in projects}
    project_department = {project.id: department_index.root_name(project.department_id) if project.department_id else "未分配部门" for project in projects}
    project_department_ids = {project.id: project.department_id for project in projects}
    selected_department_id = department_index.resolve(department_id, department_name)
    selected_department_ids = department_index.descendants(selected_department_id) if selected_department_id else set()
    visible_project_ids = project_scope_ids(db, user, "reports")

    items = db.scalars(select(Worklog).where(Worklog.start_date >= start, Worklog.end_date <= end, Worklog.unit == "DAY").order_by(Worklog.start_date, Worklog.id)).all()
    items = [item for item in items if (visible_project_ids is None or item.project_id in visible_project_ids) and (not selected_department_ids or project_department_ids.get(item.project_id) in selected_department_ids)]
    worklog_ids = [item.id for item in items]
    latest_tasks: dict[int, ApprovalTask] = {}
    if worklog_ids:
        tasks = db.scalars(select(ApprovalTask).where(ApprovalTask.worklog_id.in_(worklog_ids)).order_by(ApprovalTask.version.desc(), ApprovalTask.id.desc())).all()
        for task in tasks:
            latest_tasks.setdefault(task.worklog_id, task)

    status_names = {"DRAFT": "草稿", "PENDING_APPROVAL": "审批中", "APPROVED": "已通过", "REJECTED": "已驳回", "LOCKED": "已锁定"}
    work_type_names = {"PROJECT": "项目工时", "MANAGEMENT": "管理工时", "OTHER": "其它工时"}
    work_status_names = {"LOCAL": "本地", "BUSINESS_TRIP": "出差", "REMOTE": "异地办公", "LEAVE": "休假"}
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["工时单号", "提交人", "一级部门", "项目", "项目阶段", "工时类型", "工作状态", "开始日期", "结束日期", "工时天数", "审批人", "审批状态", "工作描述", "提交时间", "处理时间", "审批意见"])
    for item in items:
        task = latest_tasks.get(item.id)
        writer.writerow([
            task.serial_no if task else "",
            item.user_name_snapshot,
            project_department.get(item.project_id, "未分配部门"),
            item.project_name_snapshot,
            item.stage,
            work_type_names.get(item.work_type, item.work_type),
            work_status_names.get(item.work_status, item.work_status),
            item.start_date,
            item.end_date,
            f"{float(item.quantity):g}",
            item.approver_name_snapshot or "",
            status_names.get(item.status, item.status),
            item.description,
            task.submitted_at if task else item.submitted_at or "",
            task.processed_at if task else "",
            item.approval_comment or item.rejection_reason or (task.comment if task else "") or "",
        ])
    filename = f"xinye-worklog-details-{start:%Y%m%d}-{end:%Y%m%d}.csv"
    return StreamingResponse(iter([output.getvalue().encode("utf-8-sig")]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/v1/integrations/health")
def integrations_health() -> dict[str, object]:
    return feishu.health()


def integration_notification_view(db: Session, item: SystemNotification) -> IntegrationNotificationView:
    """将内部通知记录转换为管理员可读的业务摘要。"""
    recipient = db.get(User, item.recipient_user_id) if item.recipient_user_id else None
    source_label = f"{item.source_type} #{item.source_id}"
    if item.source_type == "PROJECT":
        source = db.get(Project, item.source_id)
        source_label = source.name if source else source_label
    elif item.source_type == "receipt":
        source = db.get(Receipt, item.source_id)
        source_label = source.receipt_no if source else source_label
    elif item.source_type == "payment":
        source = db.get(Payment, item.source_id)
        source_label = source.payment_no if source else source_label
    elif item.source_type == "CONTRACT_STAGE":
        source = db.get(ContractStage, item.source_id)
        source_label = source.name if source else source_label
    return IntegrationNotificationView(
        id=item.id,
        notification_type=item.notification_type,
        source_type=item.source_type,
        source_id=item.source_id,
        source_label=source_label,
        recipient_user_id=item.recipient_user_id,
        recipient_name=recipient.name if recipient else "未指定",
        channel=item.channel,
        status=item.status,
        error_message=item.error_message,
        retry_count=int(item.retry_count or 0),
        message_id=item.message_id,
        sent_at=item.sent_at,
        created_at=item.created_at,
        record_kind="system",
    )


def integration_worklog_notification_view(db: Session, item: Notification) -> IntegrationNotificationView:
    """将工时审批通知转换为统一通知中心行。"""
    task = db.get(ApprovalTask, item.approval_task_id)
    worklog = db.get(Worklog, task.worklog_id) if task else None
    recipient = db.get(User, item.recipient_user_id) if item.recipient_user_id else None
    return IntegrationNotificationView(
        id=item.id,
        notification_type="WORKLOG_APPROVAL",
        source_type="WORKLOG",
        source_id=worklog.id if worklog else 0,
        source_label=(f"{worklog.project_name_snapshot} · {task.serial_no}" if worklog and task else f"工时通知 #{item.id}"),
        recipient_user_id=item.recipient_user_id,
        recipient_name=recipient.name if recipient else "未指定",
        channel=item.channel,
        status=item.status,
        error_message=item.error_message,
        retry_count=int(item.retry_count or 0),
        message_id=item.message_id,
        sent_at=item.sent_at,
        created_at=item.created_at,
        record_kind="worklog",
    )


@app.get("/api/v1/integrations/overview")
def integrations_overview(
    notification_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """读取集成概况、组织同步历史和飞书应用通知日志。"""
    require_admin_permission(db, "integrations", x_demo_user_id)
    require_access(db, "integrations", "VIEW", x_demo_user_id)
    query = select(SystemNotification).order_by(SystemNotification.created_at.desc(), SystemNotification.id.desc())
    if notification_type:
        query = query.where(SystemNotification.notification_type == notification_type)
    if status:
        query = query.where(SystemNotification.status == status)
    system_items = db.scalars(query.limit(limit)).all()
    worklog_query = select(Notification).order_by(Notification.created_at.desc(), Notification.id.desc())
    if notification_type == "WORKLOG_APPROVAL":
        worklog_items = db.scalars(worklog_query.limit(limit)).all()
    elif notification_type:
        worklog_items = []
    else:
        worklog_items = db.scalars(worklog_query.limit(limit)).all()
    notification_rows = [integration_notification_view(db, item) for item in system_items] + [integration_worklog_notification_view(db, item) for item in worklog_items]
    if status:
        notification_rows = [item for item in notification_rows if item.status == status]
    notification_rows.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    notification_rows = notification_rows[:limit]
    sync_items = db.scalars(select(OrgSyncLog).order_by(OrgSyncLog.created_at.desc(), OrgSyncLog.id.desc()).limit(20)).all()
    sent_total = int(db.scalar(select(func.count(SystemNotification.id)).where(SystemNotification.status == "SENT")) or 0) + int(db.scalar(select(func.count(Notification.id)).where(Notification.status == "SENT")) or 0)
    today_start = datetime.combine(today_local(), datetime.min.time())
    today_sent = int(db.scalar(select(func.count(SystemNotification.id)).where(SystemNotification.status == "SENT", SystemNotification.sent_at >= today_start)) or 0) + int(db.scalar(select(func.count(Notification.id)).where(Notification.status == "SENT", Notification.sent_at >= today_start)) or 0)
    failed_total = int(db.scalar(select(func.count(SystemNotification.id)).where(SystemNotification.status == "FAILED")) or 0) + int(db.scalar(select(func.count(Notification.id)).where(Notification.status == "FAILED")) or 0)
    policies = db.scalars(
        select(NotificationPolicy)
        .where(~NotificationPolicy.notification_type.startswith("DAYS_BUDGET"))
        .order_by(NotificationPolicy.id)
    ).all()
    return {
        "health": feishu.health(),
        "summary": {
            "member_count": int(db.scalar(select(func.count(User.id)).where(User.employment_status == "ACTIVE")) or 0),
            "department_count": int(db.scalar(select(func.count(Department.id)).where(Department.is_active.is_(True))) or 0),
            "sent_count": sent_total,
            "today_sent_count": today_sent,
            "retry_count": failed_total,
        },
        "notifications": [item.model_dump() for item in notification_rows],
        "notification_total": int(db.scalar(select(func.count(SystemNotification.id))) or 0) + int(db.scalar(select(func.count(Notification.id))) or 0),
        "sync_logs": [OrgSyncLogView.model_validate(item).model_dump() for item in sync_items],
        "policies": [NotificationPolicyView.model_validate(item).model_dump() for item in policies],
    }


@app.get("/api/v1/integrations/sync-logs", response_model=OrgSyncLogList)
def list_integration_sync_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> OrgSyncLogList:
    """分页读取组织架构同步记录，保留失败和历史同步统计。"""
    require_admin_permission(db, "integrations", x_demo_user_id)
    total = int(db.scalar(select(func.count(OrgSyncLog.id))) or 0)
    page_count = (total + page_size - 1) // page_size if total else 0
    items = db.scalars(
        select(OrgSyncLog)
        .order_by(OrgSyncLog.created_at.desc(), OrgSyncLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return OrgSyncLogList(
        items=[OrgSyncLogView.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        page_count=page_count,
    )


@app.get("/api/v1/integrations/policies", response_model=NotificationPolicyList)
def list_notification_policies(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> NotificationPolicyList:
    """读取管理员可维护的业务通知策略。"""
    require_admin_permission(db, "integrations", x_demo_user_id)
    rows = db.scalars(
        select(NotificationPolicy)
        .where(~NotificationPolicy.notification_type.startswith("DAYS_BUDGET"))
        .order_by(NotificationPolicy.id)
    ).all()
    return NotificationPolicyList(items=[NotificationPolicyView.model_validate(item) for item in rows])


@app.put("/api/v1/integrations/policies", response_model=NotificationPolicyList)
def update_notification_policies(payload: NotificationPolicyBatchUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> NotificationPolicyList:
    """一次性更新全部通知策略；校验完整后才提交，避免策略处于半保存状态。"""
    admin = require_admin_permission(db, "integrations", x_demo_user_id)
    require_access(db, "integrations", "CONFIGURE", x_demo_user_id)
    policies = db.scalars(
        select(NotificationPolicy)
        .where(~NotificationPolicy.notification_type.startswith("DAYS_BUDGET"))
        .order_by(NotificationPolicy.id)
    ).all()
    policy_map = {policy.notification_type: policy for policy in policies}
    submitted_types = [item.notification_type for item in payload.items]
    if len(submitted_types) != len(set(submitted_types)) or set(submitted_types) != set(policy_map):
        raise HTTPException(400, "NOTIFICATION_POLICY_SET_INVALID")
    for item in payload.items:
        policy = policy_map[item.notification_type]
        policy.enabled = item.enabled
        policy.send_channel = item.send_channel
        policy.remind_days_before = item.remind_days_before
        audit(db, "notification_policy", policy.id, "UPDATE_BATCH", admin.id, None, "ENABLED" if policy.enabled else "DISABLED")
    db.commit()
    rows = db.scalars(
        select(NotificationPolicy)
        .where(~NotificationPolicy.notification_type.startswith("DAYS_BUDGET"))
        .order_by(NotificationPolicy.id)
    ).all()
    return NotificationPolicyList(items=[NotificationPolicyView.model_validate(item) for item in rows])


@app.patch("/api/v1/integrations/policies/{notification_type}", response_model=NotificationPolicyView)
def update_notification_policy(notification_type: str, payload: NotificationPolicyUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> NotificationPolicyView:
    """更新单个业务通知策略；只影响后续扫描和发送。"""
    admin = require_admin_permission(db, "integrations", x_demo_user_id)
    require_access(db, "integrations", "CONFIGURE", x_demo_user_id)
    policy = db.scalar(select(NotificationPolicy).where(NotificationPolicy.notification_type == notification_type))
    if not policy:
        raise HTTPException(404, "NOTIFICATION_POLICY_NOT_FOUND")
    policy.enabled = payload.enabled
    policy.send_channel = payload.send_channel
    policy.remind_days_before = payload.remind_days_before
    audit(db, "notification_policy", policy.id, "UPDATE", admin.id, None, "ENABLED" if policy.enabled else "DISABLED")
    db.commit()
    db.refresh(policy)
    return NotificationPolicyView.model_validate(policy)


def integration_notification_rows(
    db: Session,
    notification_type: str | None = None,
    status: str | None = None,
) -> list[IntegrationNotificationView]:
    """合并系统通知和工时审批通知，作为统一通知中心的数据源。"""
    system_items = db.scalars(select(SystemNotification)).all()
    worklog_items = db.scalars(select(Notification)).all()
    rows = [integration_notification_view(db, item) for item in system_items]
    rows.extend(integration_worklog_notification_view(db, item) for item in worklog_items)
    if notification_type:
        rows = [item for item in rows if item.notification_type == notification_type]
    if status:
        rows = [item for item in rows if item.status == status]
    rows.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    return rows


@app.get("/api/v1/integrations/notifications", response_model=IntegrationNotificationList)
def list_integration_notifications(
    notification_type: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> IntegrationNotificationList:
    """分页读取统一通知中心，支持类型和发送状态筛选。"""
    require_admin_permission(db, "integrations", x_demo_user_id)
    rows = integration_notification_rows(db, notification_type, status)
    total = len(rows)
    page_count = (total + page_size - 1) // page_size if total else 0
    start = (page - 1) * page_size
    return IntegrationNotificationList(
        items=rows[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
        page_count=page_count,
    )


@app.get("/api/v1/integrations/notifications/{notification_id}", response_model=IntegrationNotificationView)
def get_integration_notification(
    notification_id: int,
    record_kind: str = Query(default="system", pattern="^(system|worklog)$"),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> IntegrationNotificationView:
    """读取通知详情，详情和列表使用同一条记录转换逻辑。"""
    require_admin_permission(db, "integrations", x_demo_user_id)
    if record_kind == "worklog":
        item = db.get(Notification, notification_id)
        if not item:
            raise HTTPException(404, "NOTIFICATION_NOT_FOUND")
        return integration_worklog_notification_view(db, item)
    item = db.get(SystemNotification, notification_id)
    if not item:
        raise HTTPException(404, "NOTIFICATION_NOT_FOUND")
    return integration_notification_view(db, item)


@app.post("/api/v1/integrations/notifications/{notification_id}/retry", response_model=IntegrationNotificationView)
def retry_integration_notification(
    notification_id: int,
    record_kind: str = Query(default="system", pattern="^(system|worklog)$"),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> IntegrationNotificationView:
    """重试一条失败的收付款结果或项目预警通知。"""
    admin = require_admin_permission(db, "integrations", x_demo_user_id)
    require_access(db, "integrations", "CONFIGURE", x_demo_user_id)
    if record_kind == "worklog":
        notification = db.get(Notification, notification_id)
        if not notification:
            raise HTTPException(404, "NOTIFICATION_NOT_FOUND")
        if notification.status == "SENT":
            raise HTTPException(409, "NOTIFICATION_ALREADY_SENT")
        task = db.get(ApprovalTask, notification.approval_task_id)
        item = db.get(Worklog, task.worklog_id) if task else None
        approver = db.get(User, task.approver_user_id) if task else None
        submitter = db.get(User, task.submitter_user_id) if task else None
        if not task or not item or not approver or not submitter:
            raise HTTPException(404, "NOTIFICATION_SOURCE_NOT_FOUND")
        channel = notification_policy_channel(db, "WORKLOG_APPROVAL")
        if channel and not notification_policy_enabled(db, "WORKLOG_APPROVAL"):
            raise HTTPException(409, "NOTIFICATION_POLICY_DISABLED")
        result = feishu.notify_approval_submitted(task.serial_no, approver.name, submitter.name, item.project_name_snapshot, item.description, str(item.start_date), float(item.quantity), item.unit, worklog_approval_detail_url(task.id), recipient_open_id=approver.open_id, channel=channel)
        notification.status = result.status
        notification.channel = channel or feishu.notification_mode
        notification.message_id = result.message_id
        notification.error_message = result.error_message
        notification.sent_at = now_local() if result.status == "SENT" else None
        notification.retry_count = int(notification.retry_count or 0) + 1
        db.commit()
        db.refresh(notification)
        return integration_worklog_notification_view(db, notification)
    notification = db.get(SystemNotification, notification_id)
    if not notification:
        raise HTTPException(404, "NOTIFICATION_NOT_FOUND")
    if notification.status == "SENT":
        raise HTTPException(409, "NOTIFICATION_ALREADY_SENT")
    if notification.notification_type in {"PENDING_RECEIPT", "PENDING_PAYMENT"}:
        expected_source_type = "receipt" if notification.notification_type == "PENDING_RECEIPT" else "payment"
        if notification.source_type != expected_source_type:
            raise HTTPException(400, "NOTIFICATION_SOURCE_UNSUPPORTED")
        item = db.get(Receipt if expected_source_type == "receipt" else Payment, notification.source_id)
        if not item or not notification.recipient_user_id:
            raise HTTPException(409, "NOTIFICATION_RECIPIENT_NOT_FOUND")
        project = db.get(Project, item.project_id)
        submitter = db.get(User, item.submitted_by) if item.submitted_by else None
        if expected_source_type == "payment" and item.current_workflow_instance_id:
            tasks = list(db.scalars(select(WorkflowTask).where(
                WorkflowTask.workflow_instance_id == item.current_workflow_instance_id,
                WorkflowTask.assignee_user_id == notification.recipient_user_id,
                WorkflowTask.status == "PENDING",
            )).all())
            if not tasks:
                raise HTTPException(409, "NOTIFICATION_TASK_NOT_ACTIVE")
            notify_payment_tasks(db, item, tasks, recipient_user_id=notification.recipient_user_id)
            db.commit()
            db.refresh(notification)
            return integration_notification_view(db, notification)
        send_cash_approval_notifications(
            db,
            expected_source_type,
            item.id,
            "合同收款单" if expected_source_type == "receipt" else "合同付款单",
            item.receipt_no if expected_source_type == "receipt" else item.payment_no,
            project.name if project else "",
            float(item.amount or 0),
            submitter.name if submitter else "申请人",
            recipient_user_id=notification.recipient_user_id,
        )
        db.commit()
        db.refresh(notification)
        return integration_notification_view(db, notification)
    if notification.notification_type in {"EXPENSE_APPROVAL", "EXPENSE_PAYMENT"}:
        expense = db.get(ProjectExpense, notification.source_id)
        if not expense or notification.source_type != "project_expense" or not notification.recipient_user_id or not expense.current_workflow_instance_id:
            raise HTTPException(409, "NOTIFICATION_RECIPIENT_NOT_FOUND")
        if not notification_policy_enabled(db, notification.notification_type):
            raise HTTPException(409, "NOTIFICATION_POLICY_DISABLED")
        task = db.scalar(select(WorkflowTask).where(
            WorkflowTask.workflow_instance_id == expense.current_workflow_instance_id,
            WorkflowTask.assignee_user_id == notification.recipient_user_id,
            WorkflowTask.status == "PENDING",
        ).order_by(WorkflowTask.node_sequence, WorkflowTask.id).limit(1))
        if not task:
            raise HTTPException(409, "NOTIFICATION_TASK_NOT_ACTIVE")
        node = db.get(WorkflowNode, task.workflow_node_id)
        expected_type = "EXPENSE_PAYMENT" if node and node.is_payment else "EXPENSE_APPROVAL"
        if expected_type != notification.notification_type:
            raise HTTPException(409, "NOTIFICATION_TASK_TYPE_CHANGED")
        notify_expense_tasks(db, expense, [task], recipient_user_id=notification.recipient_user_id)
        audit(db, "system_notification", notification.id, "RETRY", admin.id, "FAILED", notification.status)
        db.commit()
        db.refresh(notification)
        return integration_notification_view(db, notification)
    if notification.notification_type == "EXPENSE_RESULT":
        expense = db.get(ProjectExpense, notification.source_id)
        if not expense or notification.source_type != "project_expense" or not expense.applicant_user_id:
            raise HTTPException(409, "NOTIFICATION_RECIPIENT_NOT_FOUND")
        if not notification_policy_enabled(db, "EXPENSE_RESULT"):
            raise HTTPException(409, "NOTIFICATION_POLICY_DISABLED")
        action = db.scalar(select(WorkflowActionLog).where(
            WorkflowActionLog.workflow_instance_id == expense.current_workflow_instance_id,
            WorkflowActionLog.action.in_(("APPROVE", "REJECT", "CONFIRM_PAYMENT")),
        ).order_by(WorkflowActionLog.created_at.desc(), WorkflowActionLog.id.desc()).limit(1)) if expense.current_workflow_instance_id else None
        status_label = {
            "APPROVED": "审批通过",
            "APPROVED_PENDING_PAYMENT": "审批通过，待出纳支付",
            "PAID": "已支付",
            "REJECTED": "已驳回",
        }.get(expense.status, expense.status)
        notify_expense_result(db, expense, status_label, action.actor_name if action else "审批人")
        audit(db, "system_notification", notification.id, "RETRY", admin.id, "FAILED", notification.status)
        db.commit()
        db.refresh(notification)
        return integration_notification_view(db, notification)
    if notification.notification_type == "PAYMENT_RESULT":
        item = db.get(Payment, notification.source_id)
        if not item or not item.submitted_by:
            raise HTTPException(409, "NOTIFICATION_RECIPIENT_NOT_FOUND")
        actor_name = None
        if item.current_workflow_instance_id:
            last_result = db.scalar(
                select(WorkflowActionLog)
                .where(
                    WorkflowActionLog.workflow_instance_id == item.current_workflow_instance_id,
                    WorkflowActionLog.action.in_(("REJECT", "CONFIRM_PAYMENT")),
                )
                .order_by(WorkflowActionLog.created_at.desc(), WorkflowActionLog.id.desc())
                .limit(1)
            )
            actor_name = last_result.actor_name if last_result else None
        if not actor_name and item.approved_by:
            actor = db.get(User, item.approved_by)
            actor_name = actor.name if actor else None
        notify_payment_result(db, item, "审批通过并已确认支付" if item.status == "APPROVED" else "已驳回", actor_name or "审批人")
        audit(db, "system_notification", notification.id, "RETRY", admin.id, "FAILED", notification.status)
        db.commit()
    elif notification.notification_type == "SETTLEMENT_APPROVED":
        if notification.source_type == "receipt":
            item = db.get(Receipt, notification.source_id)
            label, serial_no, project_id, amount, recipient_id = "合同收款单", item.receipt_no if item else "", item.project_id if item else 0, float(item.amount or 0) if item else 0, item.submitted_by if item else None
        elif notification.source_type == "payment":
            item = db.get(Payment, notification.source_id)
            label, serial_no, project_id, amount, recipient_id = "合同付款单", item.payment_no if item else "", item.project_id if item else 0, float(item.amount or 0) if item else 0, item.submitted_by if item else None
        else:
            raise HTTPException(400, "NOTIFICATION_SOURCE_UNSUPPORTED")
        if not item or not recipient_id:
            raise HTTPException(409, "NOTIFICATION_RECIPIENT_NOT_FOUND")
        project = db.get(Project, project_id)
        if not notification_policy_enabled(db, "SETTLEMENT_APPROVED"):
            raise HTTPException(409, "NOTIFICATION_POLICY_DISABLED")
        approver = db.get(User, item.approved_by) if item.approved_by else None
        send_settlement_notification(db, notification.source_type, notification.source_id, label, serial_no, project.name if project else "", amount, recipient_id, approver.name if approver else None)
    elif notification.source_type == "CONTRACT_STAGE":
        stage = db.get(ContractStage, notification.source_id)
        contract = db.get(Contract, stage.contract_id) if stage else None
        project = db.get(Project, contract.project_id) if contract else None
        owner = db.get(User, project.owner_user_id) if project and project.owner_user_id else None
        if not stage or not contract or not project or not owner:
            raise HTTPException(404, "NOTIFICATION_SOURCE_NOT_FOUND")
        reminder_type = notification.notification_type.removeprefix("STAGE_")
        if reminder_type not in {"UPCOMING", "DUE", "OVERDUE"}:
            raise HTTPException(400, "NOTIFICATION_SOURCE_UNSUPPORTED")
        remaining = stage_remaining(db, stage, contract.contract_type)
        channel = notification_policy_channel(db, notification.notification_type)
        if channel and not notification_policy_enabled(db, notification.notification_type):
            raise HTTPException(409, "NOTIFICATION_POLICY_DISABLED")
        result = feishu.notify_reminder(
            owner.name,
            project.name,
            contract.name,
            stage.name,
            str(stage.planned_date or ""),
            float(stage.amount or 0),
            remaining,
            reminder_type,
            os.getenv("SYSTEM_PUBLIC_URL", "http://192.168.112.188:8088"),
            owner.open_id,
            channel=channel,
        )
        notification.status = result.status
        notification.channel = channel or feishu.notification_mode
        notification.message_id = result.message_id
        notification.error_message = result.error_message
        notification.sent_at = now_local() if result.status == "SENT" else None
        notification.retry_count = int(notification.retry_count or 0) + 1
        audit(db, "system_notification", notification.id, "RETRY", admin.id, "FAILED", result.status)
        db.commit()
    elif notification.source_type == "PROJECT":
        project = db.get(Project, notification.source_id)
        if not project:
            raise HTTPException(404, "PROJECT_NOT_FOUND")
        project_row = project_view(db, project)
        if notification.notification_type.startswith("COST_BUDGET"):
            title = "项目总预算已超支" if notification.notification_type.endswith("OVER") else "项目总预算接近上限"
            detail = f"总预算使用率：{project_row.cost_usage_rate or 0:.1f}%\n实际成本：¥{project_row.actual_cost:,.2f}\n总预算：¥{project_row.budget_cost:,.2f}"
        else:
            raise HTTPException(400, "NOTIFICATION_SOURCE_UNSUPPORTED")
        send_project_warning_notification(db, project, notification.notification_type, title, detail, today_local())
        audit(db, "system_notification", notification.id, "RETRY", admin.id, "FAILED", notification.status)
        db.commit()
    else:
        raise HTTPException(400, "NOTIFICATION_SOURCE_UNSUPPORTED")
    db.refresh(notification)
    return integration_notification_view(db, notification)


def expense_document_type(expense: ProjectExpense) -> str:
    """把费用类型映射为流程模板中的单据类型。"""
    return {
        "TRAVEL": "PROJECT_EXPENSE_TRAVEL",
        "INVOICE": "PROJECT_EXPENSE_INVOICE",
        "OTHER": "PROJECT_EXPENSE_OTHER",
    }[expense.expense_type]


def direct_manager_for(db: Session, applicant: User, project: Project) -> User | None:
    """优先解析飞书直属上级，组织快照不足时回退项目配置的上级领导。"""
    manager_name = (applicant.manager_name or "").strip()
    if manager_name:
        managers = list(db.scalars(select(User).where(User.name == manager_name, User.employment_status == "ACTIVE")).all())
        if len(managers) == 1 and managers[0].id != applicant.id:
            return managers[0]
    leader = db.get(User, project.leader_user_id) if project.leader_user_id else None
    return leader if leader and leader.employment_status == "ACTIVE" and leader.id != applicant.id else None


def workflow_definition_for_document(db: Session, document_type: str) -> tuple[WorkflowDefinition, WorkflowVersion]:
    """返回适用于单据类型的已发布流程版本。"""
    for definition in db.scalars(select(WorkflowDefinition).where(WorkflowDefinition.status == "ACTIVE")).all():
        try:
            document_types = json.loads(definition.document_types or "[]")
        except json.JSONDecodeError:
            document_types = []
        if document_type not in document_types or not definition.current_version_id:
            continue
        version = db.get(WorkflowVersion, definition.current_version_id)
        if version and version.status == "PUBLISHED":
            return definition, version
    raise HTTPException(409, "WORKFLOW_NOT_PUBLISHED")


def resolve_document_workflow_path(
    db: Session,
    document_type: str,
    project: Project | None,
    applicant: User | None,
    *,
    requires_payment: bool = True,
) -> tuple[WorkflowVersion, list[dict[str, object]]]:
    """解析通用项目单据的审批路径，并固化提交时的人员快照。"""
    if not project or not applicant:
        raise HTTPException(409, "WORKFLOW_CONTEXT_MISSING")
    _definition, version = workflow_definition_for_document(db, document_type)
    nodes = list(db.scalars(select(WorkflowNode).where(WorkflowNode.workflow_version_id == version.id).order_by(WorkflowNode.sequence)).all())
    path: list[dict[str, object]] = []
    for node in nodes:
        if node.is_payment and not requires_payment:
            continue
        assignees: list[User] = []
        if node.resolver_type == "PROJECT_APPROVER":
            approver = db.get(User, project.approver_user_id) if project.approver_user_id else None
            if not approver or approver.employment_status != "ACTIVE":
                raise HTTPException(409, "PROJECT_APPROVER_MISSING")
            if approver.id == applicant.id:
                approver = direct_manager_for(db, applicant, project)
                if not approver:
                    raise HTTPException(409, "DIRECT_MANAGER_MISSING")
            assignees = [approver]
        elif node.resolver_type == "DIRECT_MANAGER":
            manager = direct_manager_for(db, applicant, project)
            if not manager:
                raise HTTPException(409, "DIRECT_MANAGER_MISSING")
            assignees = [manager]
        elif node.resolver_type == "APPROVAL_POSITION":
            position = db.get(ApprovalPosition, node.position_id) if node.position_id else None
            if not position or position.status != "ACTIVE":
                raise HTTPException(409, "APPROVAL_POSITION_EMPTY")
            assignees = list(db.scalars(
                select(User)
                .join(ApprovalPositionMember, ApprovalPositionMember.user_id == User.id)
                .where(ApprovalPositionMember.position_id == position.id, User.employment_status == "ACTIVE")
                .order_by(User.name, User.id)
            ).all())
            if not assignees:
                raise HTTPException(409, f"APPROVAL_POSITION_EMPTY:{position.name}")
        if not assignees:
            raise HTTPException(409, f"WORKFLOW_ASSIGNEE_MISSING:{node.name}")
        path.append({
            "node_id": node.id,
            "sequence": node.sequence,
            "node_code": node.code,
            "node_name": node.name,
            "approval_mode": node.approval_mode,
            "is_payment": bool(node.is_payment),
            "notification_enabled": bool(node.notification_enabled),
            "assignees": [{"id": user.id, "name": user.name} for user in assignees],
        })
    if not path:
        raise HTTPException(409, "WORKFLOW_HAS_NO_NODES")
    return version, path


def resolve_expense_workflow_path(db: Session, expense: ProjectExpense) -> tuple[WorkflowVersion, list[dict[str, object]]]:
    """解析并校验费用审批路径；结果可直接固化到流程实例快照。"""
    return resolve_document_workflow_path(
        db,
        expense_document_type(expense),
        db.get(Project, expense.project_id),
        db.get(User, expense.applicant_user_id),
        requires_payment=expense.requires_payment,
    )


def resolve_payment_workflow_path(db: Session, payment: Payment) -> tuple[WorkflowVersion, list[dict[str, object]]]:
    """解析合同付款七级审批路径。"""
    return resolve_document_workflow_path(
        db,
        "PAYMENT",
        db.get(Project, payment.project_id),
        db.get(User, payment.submitted_by) if payment.submitted_by else None,
    )


def expense_workflow_path_views(db: Session, expense: ProjectExpense) -> list[WorkflowPathNodeView]:
    """读取运行实例快照；草稿则实时预览当前流程配置。"""
    instance = db.get(WorkflowInstance, expense.current_workflow_instance_id) if expense.current_workflow_instance_id else None
    if instance:
        try:
            path = json.loads(instance.snapshot_json or "{}").get("nodes", [])
        except json.JSONDecodeError:
            path = []
    else:
        try:
            _version, path = resolve_expense_workflow_path(db, expense)
        except HTTPException:
            return []
    tasks = list(db.scalars(select(WorkflowTask).where(WorkflowTask.workflow_instance_id == instance.id)).all()) if instance else []
    by_sequence: dict[int, list[WorkflowTask]] = defaultdict(list)
    for task in tasks:
        by_sequence[task.node_sequence].append(task)
    result: list[WorkflowPathNodeView] = []
    for node in path:
        node_tasks = by_sequence.get(int(node["sequence"]), [])
        if any(item.status in {"APPROVED", "AUTO_APPROVED", "PAID"} for item in node_tasks):
            status = "DONE"
        elif any(item.status == "REJECTED" for item in node_tasks):
            status = "REJECTED"
        elif any(item.status == "PENDING" for item in node_tasks):
            status = "CURRENT"
        else:
            status = "WAITING"
        result.append(WorkflowPathNodeView(
            sequence=int(node["sequence"]),
            node_code=str(node["node_code"]),
            node_name=str(node["node_name"]),
            approval_mode=str(node["approval_mode"]),
            is_payment=bool(node.get("is_payment")),
            assignees=list(node.get("assignees") or []),
            status=status,
        ))
    return result


def payment_workflow_path_views(db: Session, payment: Payment) -> list[WorkflowPathNodeView]:
    """返回合同付款单提交快照对应的节点状态；草稿使用当前发布流程预览。"""
    instance = db.get(WorkflowInstance, payment.current_workflow_instance_id) if payment.current_workflow_instance_id else None
    if instance:
        try:
            path = json.loads(instance.snapshot_json or "{}").get("nodes", [])
        except json.JSONDecodeError:
            path = []
    else:
        try:
            _version, path = resolve_payment_workflow_path(db, payment)
        except HTTPException:
            return []
    tasks = list(db.scalars(select(WorkflowTask).where(WorkflowTask.workflow_instance_id == instance.id)).all()) if instance else []
    by_sequence: dict[int, list[WorkflowTask]] = defaultdict(list)
    for task in tasks:
        by_sequence[task.node_sequence].append(task)
    result: list[WorkflowPathNodeView] = []
    for node in path:
        node_tasks = by_sequence.get(int(node["sequence"]), [])
        if any(item.status in {"APPROVED", "AUTO_APPROVED", "PAID"} for item in node_tasks):
            status = "DONE"
        elif any(item.status == "REJECTED" for item in node_tasks):
            status = "REJECTED"
        elif any(item.status == "PENDING" for item in node_tasks):
            status = "CURRENT"
        else:
            status = "WAITING"
        result.append(WorkflowPathNodeView(
            sequence=int(node["sequence"]),
            node_code=str(node["node_code"]),
            node_name=str(node["node_name"]),
            approval_mode=str(node["approval_mode"]),
            is_payment=bool(node.get("is_payment")),
            assignees=list(node.get("assignees") or []),
            status=status,
        ))
    return result


def expense_budget_metrics(db: Session, project_id: int, budget_item_id: int | None = None) -> tuple[float, float, float, float | None]:
    """返回费用单归集预算项的预算、已用、剩余和使用率；缺少预算项时退回非人工预算合计。"""
    if budget_item_id:
        item = db.get(ProjectBudgetItem, budget_item_id)
        budget = round(float(item.budget_amount or 0), 2) if item and item.project_id == project_id else 0.0
        used = round(float(project_budget_item_actuals(db, project_id).get(budget_item_id, 0)), 2)
    else:
        budget = round(float(db.scalar(
            select(func.coalesce(func.sum(ProjectBudgetItem.budget_amount), 0)).where(
                ProjectBudgetItem.project_id == project_id,
                ProjectBudgetItem.is_active.is_(True),
                ProjectBudgetItem.code != "LABOR_COST",
            )
        ) or 0), 2)
        cost = float(db.scalar(select(func.coalesce(func.sum(ProjectLedgerEntry.amount), 0)).where(ProjectLedgerEntry.project_id == project_id, ProjectLedgerEntry.entry_type == "PROJECT_EXPENSE_COST")) or 0)
        reversal = float(db.scalar(select(func.coalesce(func.sum(ProjectLedgerEntry.amount), 0)).where(ProjectLedgerEntry.project_id == project_id, ProjectLedgerEntry.entry_type == "REVERSAL", ProjectLedgerEntry.source_type == "PROJECT_EXPENSE")) or 0)
        used = round(max(cost - reversal, 0), 2)
    return budget, used, round(budget - used, 2), round(used / budget * 100, 1) if budget > 0 else None


def expense_access(db: Session, expense: ProjectExpense, demo_user_id: int | None, *, action: str = "VIEW") -> User:
    """校验费用菜单、数据范围或审批任务授权。"""
    user = current_user(db, demo_user_id)
    assigned = bool(db.scalar(
        select(WorkflowTask.id)
        .join(WorkflowInstance, WorkflowTask.workflow_instance_id == WorkflowInstance.id)
        .where(WorkflowInstance.document_type.like("PROJECT_EXPENSE_%"), WorkflowInstance.document_id == expense.id, WorkflowTask.assignee_user_id == user.id)
    ))
    if action == "VIEW" and (expense.applicant_user_id == user.id or assigned):
        return user
    require_access(db, "project_expenses", action, demo_user_id)
    scope = project_scope_ids(db, user, "project_expenses")
    if scope is not None and expense.project_id not in scope and expense.applicant_user_id != user.id and not assigned:
        raise HTTPException(403, "PROJECT_OUT_OF_SCOPE")
    return user


def payment_workflow_assigned(db: Session, payment: Payment, user_id: int) -> bool:
    """判断用户是否属于合同付款单任一流程任务，用于详情和附件只读授权。"""
    if not payment.current_workflow_instance_id:
        return False
    return bool(db.scalar(
        select(WorkflowTask.id).where(
            WorkflowTask.workflow_instance_id == payment.current_workflow_instance_id,
            WorkflowTask.assignee_user_id == user_id,
        ).limit(1)
    ))


def payment_access(db: Session, payment: Payment, demo_user_id: int | None, *, action: str = "VIEW") -> User:
    """校验付款菜单范围，申请人和流程任务人可读取必要详情。"""
    user = current_user(db, demo_user_id)
    assigned = payment_workflow_assigned(db, payment, user.id)
    if action == "VIEW" and (payment.submitted_by == user.id or assigned):
        return user
    require_access(db, "payments", action, demo_user_id)
    ensure_project_in_scope(db, user, payment.project_id)
    return user


def active_payment_workflow_task(db: Session, payment: Payment, user: User) -> tuple[WorkflowTask, WorkflowInstance, WorkflowNode]:
    """返回当前用户在付款流程中的有效待办，阻止越权和重复处理。"""
    instance = db.get(WorkflowInstance, payment.current_workflow_instance_id) if payment.current_workflow_instance_id else None
    if not instance or instance.document_type != "PAYMENT" or instance.document_id != payment.id or instance.status != "RUNNING":
        raise HTTPException(409, "PAYMENT_WORKFLOW_NOT_RUNNING")
    task = db.scalar(select(WorkflowTask).where(
        WorkflowTask.workflow_instance_id == instance.id,
        WorkflowTask.assignee_user_id == user.id,
        WorkflowTask.status == "PENDING",
    ).order_by(WorkflowTask.node_sequence).limit(1))
    if not task:
        raise HTTPException(403, "PAYMENT_TASK_NOT_ASSIGNED")
    node = db.get(WorkflowNode, task.workflow_node_id)
    if not node:
        raise HTTPException(409, "WORKFLOW_NODE_NOT_FOUND")
    return task, instance, node


def payment_approval_timeline(db: Session, payment: Payment) -> list[ApprovalTimelineEvent]:
    """将动态付款流程日志转换为付款详情时间线，旧单据沿用审计时间线。"""
    if not payment.current_workflow_instance_id:
        return approval_timeline(db, "payment", payment.id)
    labels = {
        "SUBMIT": "提交审批",
        "APPROVE": "节点通过",
        "AUTO_APPROVE": "系统自动通过",
        "REJECT": "审批驳回",
        "CONFIRM_PAYMENT": "出纳确认支付",
    }
    logs = db.scalars(select(WorkflowActionLog).where(
        WorkflowActionLog.workflow_instance_id == payment.current_workflow_instance_id,
    ).order_by(WorkflowActionLog.created_at, WorkflowActionLog.id)).all()
    task_ids = {item.workflow_task_id for item in logs if item.workflow_task_id}
    task_names = {
        item.id: item.node_name
        for item in db.scalars(select(WorkflowTask).where(WorkflowTask.id.in_(task_ids))).all()
    } if task_ids else {}
    return [ApprovalTimelineEvent(
        event=" · ".join(filter(None, (labels.get(item.action, item.action), task_names.get(item.workflow_task_id)))),
        actor_name=item.actor_name,
        status=item.to_status,
        comment=item.comment,
        occurred_at=item.created_at,
    ) for item in logs]


def project_expense_view(db: Session, expense: ProjectExpense, viewer_id: int | None = None) -> ProjectExpenseView:
    """组装费用、附件、审批轨道和预算上下文。"""
    project = db.get(Project, expense.project_id)
    attachments = list(db.scalars(select(ProjectExpenseAttachment).where(ProjectExpenseAttachment.expense_id == expense.id).order_by(ProjectExpenseAttachment.id)).all())
    instance = db.get(WorkflowInstance, expense.current_workflow_instance_id) if expense.current_workflow_instance_id else None
    logs = list(db.scalars(select(WorkflowActionLog).where(WorkflowActionLog.workflow_instance_id == instance.id).order_by(WorkflowActionLog.created_at, WorkflowActionLog.id)).all()) if instance else []
    pending_task = db.scalar(select(WorkflowTask).where(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.status == "PENDING", WorkflowTask.assignee_user_id == viewer_id).limit(1)) if instance and viewer_id else None
    current_task = db.scalar(select(WorkflowTask).where(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.status == "PENDING").order_by(WorkflowTask.node_sequence).limit(1)) if instance else None
    budget, used, remaining, rate = expense_budget_metrics(db, expense.project_id, expense.budget_item_id)
    try:
        detail = json.loads(expense.detail_json or "{}")
    except json.JSONDecodeError:
        detail = {}
    action_labels = {
        "SUBMIT": "提交审批",
        "APPROVE": "节点通过",
        "AUTO_APPROVE": "系统自动通过",
        "REJECT": "审批驳回",
        "CONFIRM_PAYMENT": "出纳确认支付",
        "WITHDRAW": "撤回申请",
    }
    return ProjectExpenseView(
        id=expense.id,
        expense_no=expense.expense_no,
        expense_type=expense.expense_type,
        project_id=expense.project_id,
        project_name=project.name if project else "已删除项目",
        project_code=project.code if project else "-",
        applicant_user_id=expense.applicant_user_id,
        applicant_name=expense.applicant_name,
        applicant_department_name=expense.applicant_department_name,
        occurred_on=expense.occurred_on,
        amount=float(expense.amount),
        cost_amount=float(expense.cost_amount),
        budget_item_id=expense.budget_item_id,
        budget_item_name=expense.budget_item_name_snapshot,
        cost_major=expense.cost_major_snapshot,
        cost_minor=expense.cost_minor_snapshot,
        requires_payment=expense.requires_payment,
        payee_name=expense.payee_name,
        payee_bank_name=expense.payee_bank_name,
        payee_bank_account=expense.payee_bank_account,
        payment_due_date=expense.payment_due_date,
        purpose=expense.purpose,
        notes=expense.notes,
        detail=detail,
        invoice_code=expense.invoice_code,
        invoice_no=expense.invoice_no,
        supplier_id=expense.supplier_id,
        status=expense.status,
        current_node_name=current_task.node_name if current_task else None,
        current_task_id=pending_task.id if pending_task else None,
        version=expense.version,
        submitted_at=expense.submitted_at,
        approved_at=expense.approved_at,
        paid_at=expense.paid_at,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
        attachment_count=len(attachments),
        attachments=[expense_attachment_view(db, item) for item in attachments],
        approval_path=expense_workflow_path_views(db, expense),
        approval_logs=[WorkflowActionLogView(id=item.id, action=action_labels.get(item.action, item.action), actor_name=item.actor_name, from_status=item.from_status, to_status=item.to_status, comment=item.comment, created_at=item.created_at) for item in logs],
        expense_budget=budget,
        expense_budget_used=used,
        expense_budget_remaining=remaining,
        expense_budget_usage_rate=rate,
        can_edit=bool(viewer_id == expense.applicant_user_id and expense.status in {"DRAFT", "REJECTED", "WITHDRAWN"}),
        can_approve=bool(pending_task),
    )


def assign_workflow_sequence(db: Session, instance: WorkflowInstance, sequence: int, previous_approver_id: int | None = None) -> list[WorkflowTask]:
    """创建当前节点任务；相邻重复审批人自动通过，支付节点永不跳过。"""
    snapshot = json.loads(instance.snapshot_json or "{}")
    nodes = list(snapshot.get("nodes") or [])
    node = next((item for item in nodes if int(item["sequence"]) == sequence), None)
    if not node:
        return []
    instance.current_sequence = sequence
    tasks: list[WorkflowTask] = []
    assignees = list(node.get("assignees") or [])
    auto = bool(previous_approver_id and not node.get("is_payment") and len(assignees) == 1 and int(assignees[0]["id"]) == previous_approver_id)
    for assignee in assignees:
        task = WorkflowTask(
            workflow_instance_id=instance.id,
            workflow_node_id=int(node["node_id"]),
            node_sequence=sequence,
            node_name=str(node["node_name"]),
            approval_mode=str(node["approval_mode"]),
            assignee_user_id=int(assignee["id"]),
            assignee_name=str(assignee["name"]),
            status="AUTO_APPROVED" if auto else "PENDING",
            is_automatic=auto,
            processed_by=previous_approver_id if auto else None,
            processed_at=now_local() if auto else None,
            comment="与上一节点审批人相同，系统自动通过" if auto else None,
        )
        db.add(task)
        tasks.append(task)
    db.flush()
    if auto:
        db.add(WorkflowActionLog(workflow_instance_id=instance.id, workflow_task_id=tasks[0].id, action="AUTO_APPROVE", actor_user_id=previous_approver_id, actor_name=tasks[0].assignee_name, from_status="WAITING", to_status="APPROVED", comment=tasks[0].comment))
        return advance_document_workflow(db, instance, previous_approver_id)
    return tasks


def notify_expense_tasks(db: Session, expense: ProjectExpense, tasks: list[WorkflowTask], recipient_user_id: int | None = None) -> None:
    """给费用审批或支付节点候选人发送飞书卡片，并幂等更新通知记录。"""
    if not tasks:
        return
    project = db.get(Project, expense.project_id)
    base = os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088").rstrip("/")
    for task in tasks:
        if recipient_user_id is not None and task.assignee_user_id != recipient_user_id:
            continue
        node = db.get(WorkflowNode, task.workflow_node_id)
        notification_type = "EXPENSE_PAYMENT" if node and node.is_payment else "EXPENSE_APPROVAL"
        if not notification_policy_enabled(db, notification_type):
            continue
        recipient = db.get(User, task.assignee_user_id)
        if not recipient:
            continue
        key_prefix = "expense-payment" if notification_type == "EXPENSE_PAYMENT" else "expense-approval"
        key = f"{key_prefix}:{expense.id}:{expense.version}:{task.id}"
        notification = db.scalar(select(SystemNotification).where(SystemNotification.idempotency_key == key))
        if notification and notification.status == "SENT":
            continue
        channel = notification_policy_channel(db, notification_type)
        result = feishu.notify_cash_approval_submitted(
            recipient.name,
            expense.applicant_name,
            f"项目费用{'支付确认' if notification_type == 'EXPENSE_PAYMENT' else '审批'}（{task.node_name}）",
            expense.expense_no,
            project.name if project else "",
            float(expense.amount),
            f"{base}/?page=expenseDetail&id={expense.id}&task={task.id}",
            recipient.open_id,
            channel=channel,
        )
        if not notification:
            notification = SystemNotification(notification_type=notification_type, source_type="project_expense", source_id=expense.id, recipient_user_id=recipient.id, channel=channel or feishu.notification_mode, idempotency_key=key)
            db.add(notification)
        else:
            notification.retry_count = int(notification.retry_count or 0) + 1
        notification.status = result.status
        notification.channel = channel or feishu.notification_mode
        notification.message_id = result.message_id
        notification.error_message = result.error_message
        notification.sent_at = now_local() if result.status == "SENT" else None


def notify_expense_result(db: Session, expense: ProjectExpense, status_label: str, actor_name: str) -> None:
    """向费用申请人发送审批或支付结果。"""
    if not notification_policy_enabled(db, "EXPENSE_RESULT"):
        return
    recipient = db.get(User, expense.applicant_user_id)
    project = db.get(Project, expense.project_id)
    if not recipient:
        return
    key = f"expense-result:{expense.id}:{expense.version}:{expense.status}"
    notification = db.scalar(select(SystemNotification).where(SystemNotification.idempotency_key == key))
    if notification and notification.status == "SENT":
        return
    base = os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088").rstrip("/")
    channel = notification_policy_channel(db, "EXPENSE_RESULT")
    result = feishu.notify_settlement_result(recipient.name, "项目费用单", expense.expense_no, project.name if project else "", float(expense.amount), status_label, f"{base}/?page=expenseDetail&id={expense.id}", recipient.open_id, channel=channel, approver_name=actor_name)
    if not notification:
        notification = SystemNotification(notification_type="EXPENSE_RESULT", source_type="project_expense", source_id=expense.id, recipient_user_id=recipient.id, channel=channel or feishu.notification_mode, idempotency_key=key)
        db.add(notification)
    else:
        notification.retry_count = int(notification.retry_count or 0) + 1
    notification.status = result.status
    notification.channel = channel or feishu.notification_mode
    notification.message_id = result.message_id
    notification.error_message = result.error_message
    notification.sent_at = now_local() if result.status == "SENT" else None


def notify_payment_tasks(db: Session, payment: Payment, tasks: list[WorkflowTask], recipient_user_id: int | None = None) -> None:
    """向合同付款当前节点候选人发送直达付款详情的飞书卡片。"""
    if not tasks or not notification_policy_enabled(db, "PENDING_PAYMENT"):
        return
    project = db.get(Project, payment.project_id)
    submitter = db.get(User, payment.submitted_by) if payment.submitted_by else None
    base = os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088").rstrip("/")
    channel = notification_policy_channel(db, "PENDING_PAYMENT")
    for task in tasks:
        if recipient_user_id is not None and task.assignee_user_id != recipient_user_id:
            continue
        recipient = db.get(User, task.assignee_user_id)
        if not recipient:
            continue
        key = f"payment-workflow:{payment.id}:{payment.version}:{task.id}"
        notification = db.scalar(select(SystemNotification).where(SystemNotification.idempotency_key == key))
        if notification and notification.status == "SENT":
            continue
        result = feishu.notify_cash_approval_submitted(
            recipient.name,
            submitter.name if submitter else "申请人",
            f"合同付款单（{task.node_name}）",
            payment.payment_no,
            project.name if project else "",
            float(payment.amount),
            f"{base}/?page=paymentDetail&id={payment.id}&task={task.id}",
            recipient.open_id,
            channel=channel,
        )
        if not notification:
            notification = SystemNotification(
                notification_type="PENDING_PAYMENT",
                source_type="payment",
                source_id=payment.id,
                recipient_user_id=recipient.id,
                channel=channel or feishu.notification_mode,
                idempotency_key=key,
            )
            db.add(notification)
        else:
            notification.retry_count = int(notification.retry_count or 0) + 1
        notification.status = result.status
        notification.message_id = result.message_id
        notification.error_message = result.error_message
        notification.sent_at = now_local() if result.status == "SENT" else None


def notify_payment_result(db: Session, payment: Payment, status_label: str, actor_name: str) -> None:
    """向合同付款申请人发送节点终态通知。"""
    if not payment.submitted_by or not notification_policy_enabled(db, "PAYMENT_RESULT"):
        return
    recipient = db.get(User, payment.submitted_by)
    project = db.get(Project, payment.project_id)
    if not recipient:
        return
    key = f"payment-result:{payment.id}:{payment.version}:{payment.status}"
    notification = db.scalar(select(SystemNotification).where(SystemNotification.idempotency_key == key))
    if notification and notification.status == "SENT":
        return
    base = os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088").rstrip("/")
    channel = notification_policy_channel(db, "PAYMENT_RESULT")
    result = feishu.notify_settlement_result(
        recipient.name,
        "合同付款单",
        payment.payment_no,
        project.name if project else "",
        float(payment.amount),
        status_label,
        f"{base}/?page=paymentDetail&id={payment.id}",
        recipient.open_id,
        channel=channel,
        approver_name=actor_name,
    )
    if not notification:
        notification = SystemNotification(
            notification_type="PAYMENT_RESULT",
            source_type="payment",
            source_id=payment.id,
            recipient_user_id=recipient.id,
            channel=channel or feishu.notification_mode,
            idempotency_key=key,
        )
        db.add(notification)
    else:
        notification.retry_count = int(notification.retry_count or 0) + 1
    notification.status = result.status
    notification.message_id = result.message_id
    notification.error_message = result.error_message
    notification.sent_at = now_local() if result.status == "SENT" else None


def advance_payment_workflow(db: Session, instance: WorkflowInstance, approver_id: int | None) -> list[WorkflowTask]:
    """推进合同付款到下一节点；最后的出纳节点由确认动作单独记账。"""
    snapshot = json.loads(instance.snapshot_json or "{}")
    nodes = list(snapshot.get("nodes") or [])
    next_node = next((item for item in nodes if int(item["sequence"]) > instance.current_sequence), None)
    if next_node:
        return assign_workflow_sequence(db, instance, int(next_node["sequence"]), approver_id)
    return []


def advance_document_workflow(db: Session, instance: WorkflowInstance, approver_id: int | None) -> list[WorkflowTask]:
    """按实例单据类型分派流程推进逻辑。"""
    if instance.document_type == "PAYMENT":
        return advance_payment_workflow(db, instance, approver_id)
    return advance_expense_workflow(db, instance, approver_id)


def confirm_expense_cost(db: Session, expense: ProjectExpense) -> None:
    """在业务审批完成时幂等确认费用成本。"""
    budget_item = db.get(ProjectBudgetItem, expense.budget_item_id) if expense.budget_item_id else None
    add_ledger_entry(db, expense.project_id, "PROJECT_EXPENSE_COST", "PROJECT_EXPENSE", expense.id, float(expense.cost_amount), occurred_on=expense.occurred_on, budget_item=budget_item)
    expense.approved_at = expense.approved_at or now_local()


def advance_expense_workflow(db: Session, instance: WorkflowInstance, approver_id: int | None) -> list[WorkflowTask]:
    """推进到下一节点，或完成费用审批并确认成本。"""
    expense = db.get(ProjectExpense, instance.document_id)
    snapshot = json.loads(instance.snapshot_json or "{}")
    nodes = list(snapshot.get("nodes") or [])
    current = next((item for item in nodes if int(item["sequence"]) == instance.current_sequence), None)
    next_node = next((item for item in nodes if int(item["sequence"]) > instance.current_sequence), None)
    current_is_payment = bool(current and current.get("is_payment"))
    if current_is_payment:
        return []
    if next_node and not next_node.get("is_payment"):
        return assign_workflow_sequence(db, instance, int(next_node["sequence"]), approver_id)
    confirm_expense_cost(db, expense)
    if next_node and expense.requires_payment:
        expense.status = "APPROVED_PENDING_PAYMENT"
        return assign_workflow_sequence(db, instance, int(next_node["sequence"]), approver_id)
    expense.status = "APPROVED"
    instance.status = "COMPLETED"
    instance.completed_at = now_local()
    return []


def apply_expense_fields(db: Session, expense: ProjectExpense, payload: ProjectExpenseCreate | ProjectExpenseUpdate) -> None:
    """写入可编辑费用字段并序列化类型扩展明细。"""
    if payload.expense_type == "LABOR_COST":
        budget_item = project_labor_budget_item(db, payload.project_id)
        if not budget_item:
            raise HTTPException(400, "LABOR_BUDGET_ITEM_REQUIRED")
    elif payload.budget_item_id is None:
        preferred_code = {
            "TRAVEL": "TRAVEL_COST",
            "INVOICE": "OTHER_COST",
            "OTHER": "OTHER_COST",
            "PROJECT_COST": "OTHER_COST",
        }.get(payload.expense_type, "OTHER_COST")
        budget_item = default_project_budget_item(db, payload.project_id, "PROJECT_EXPENSE", preferred_code)
        if not budget_item:
            raise HTTPException(400, "BUDGET_ITEM_REQUIRED")
    else:
        budget_item = resolve_project_budget_item(db, payload.project_id, payload.budget_item_id, required=True, source_kind="PROJECT_EXPENSE")
    expense.expense_type = payload.expense_type
    expense.project_id = payload.project_id
    expense.occurred_on = payload.occurred_on
    expense.amount = payload.amount
    expense.cost_amount = payload.cost_amount
    apply_budget_snapshot(expense, budget_item)
    expense.requires_payment = payload.requires_payment
    expense.payee_name = payload.payee_name.strip() if payload.payee_name else None
    expense.payee_bank_name = payload.payee_bank_name.strip() if payload.payee_bank_name else None
    expense.payee_bank_account = payload.payee_bank_account.strip() if payload.payee_bank_account else None
    expense.payment_due_date = payload.payment_due_date
    expense.purpose = payload.purpose.strip()
    expense.notes = payload.notes.strip() if payload.notes else None
    expense.detail_json = json.dumps(payload.detail, ensure_ascii=False)
    expense.invoice_code = payload.invoice_code.strip() if payload.invoice_code else None
    expense.invoice_no = payload.invoice_no.strip() if payload.invoice_no else None
    expense.supplier_id = payload.supplier_id


def validate_expense_invoice(db: Session, expense: ProjectExpense) -> None:
    """阻止同一供应商或收款方重复使用发票。"""
    if expense.expense_type != "INVOICE" or not expense.invoice_no:
        return
    query = select(ProjectExpense.id).where(ProjectExpense.expense_type == "INVOICE", ProjectExpense.invoice_no == expense.invoice_no, ProjectExpense.status != "REVERSED", ProjectExpense.id != expense.id)
    if expense.invoice_code:
        query = query.where(ProjectExpense.invoice_code == expense.invoice_code)
    if expense.supplier_id:
        query = query.where(ProjectExpense.supplier_id == expense.supplier_id)
    else:
        query = query.where(ProjectExpense.payee_name == expense.payee_name)
    if db.scalar(query):
        raise HTTPException(409, "DUPLICATE_INVOICE")


@app.get("/api/v1/project-expenses", response_model=ProjectExpenseList)
def list_project_expenses(
    project_id: int | None = Query(default=None, gt=0),
    expense_type: str | None = None,
    status: str | None = None,
    applicant_user_id: int | None = Query(default=None, gt=0),
    period_start: date | None = None,
    period_end: date | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ProjectExpenseList:
    """分页查询项目费用，范围包含本人申请、负责项目和角色授权数据。"""
    user = require_access(db, "project_expenses", "VIEW", x_demo_user_id)
    scope = project_scope_ids(db, user, "project_expenses")
    query = select(ProjectExpense)
    if scope is not None:
        query = query.where(or_(ProjectExpense.project_id.in_(scope), ProjectExpense.applicant_user_id == user.id))
    if project_id:
        query = query.where(ProjectExpense.project_id == project_id)
    if expense_type:
        query = query.where(ProjectExpense.expense_type == expense_type)
    if status:
        query = query.where(ProjectExpense.status == status)
    if applicant_user_id:
        query = query.where(ProjectExpense.applicant_user_id == applicant_user_id)
    if period_start:
        query = query.where(ProjectExpense.occurred_on >= period_start)
    if period_end:
        query = query.where(ProjectExpense.occurred_on <= period_end)
    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(or_(ProjectExpense.expense_no.contains(value), ProjectExpense.purpose.contains(value), ProjectExpense.applicant_name.contains(value)))
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = list(db.scalars(query.order_by(ProjectExpense.updated_at.desc(), ProjectExpense.id.desc()).offset((page - 1) * page_size).limit(page_size)).all())
    amount_total = float(db.scalar(select(func.coalesce(func.sum(query.subquery().c.amount), 0))) or 0)
    return ProjectExpenseList(items=[project_expense_view(db, item, user.id) for item in rows], total=total, page=page, page_size=page_size, page_count=max(1, math.ceil(total / page_size)), summary={"amount": round(amount_total, 2)})


@app.post("/api/v1/project-expenses", response_model=ProjectExpenseView, status_code=201)
def create_project_expense(payload: ProjectExpenseCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectExpenseView:
    """保存费用草稿；附件可在随后提交前立即上传。"""
    user = require_access(db, "project_expenses", "CREATE", x_demo_user_id)
    project = ensure_project_in_scope(db, user, payload.project_id)
    department = db.get(Department, user.department_id) if user.department_id else None
    expense = ProjectExpense(expense_no=next_document_no(db, ProjectExpense, "FY"), expense_type=payload.expense_type, project_id=project.id, applicant_user_id=user.id, applicant_name=user.name, applicant_department_name=DepartmentIndex(db.scalars(select(Department)).all()).path(department.id if department else None), occurred_on=payload.occurred_on, amount=payload.amount, cost_amount=payload.cost_amount, purpose=payload.purpose, status="DRAFT")
    apply_expense_fields(db, expense, payload)
    db.add(expense)
    db.flush()
    validate_expense_invoice(db, expense)
    audit(db, "project_expense", expense.id, "CREATE", user.id, None, "DRAFT")
    db.commit()
    db.refresh(expense)
    return project_expense_view(db, expense, user.id)


@app.get("/api/v1/project-expenses/{expense_id}", response_model=ProjectExpenseView)
def get_project_expense(expense_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectExpenseView:
    expense = db.get(ProjectExpense, expense_id)
    if not expense:
        raise HTTPException(404, "PROJECT_EXPENSE_NOT_FOUND")
    user = expense_access(db, expense, x_demo_user_id)
    return project_expense_view(db, expense, user.id)


@app.patch("/api/v1/project-expenses/{expense_id}", response_model=ProjectExpenseView)
def update_project_expense(expense_id: int, payload: ProjectExpenseUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectExpenseView:
    expense = db.get(ProjectExpense, expense_id)
    if not expense:
        raise HTTPException(404, "PROJECT_EXPENSE_NOT_FOUND")
    user = expense_access(db, expense, x_demo_user_id, action="EDIT")
    if expense.applicant_user_id != user.id and user.id not in system_admin_user_ids(db):
        raise HTTPException(403, "EXPENSE_APPLICANT_ONLY")
    if expense.status not in {"DRAFT", "REJECTED", "WITHDRAWN"}:
        raise HTTPException(409, "EXPENSE_READ_ONLY")
    if payload.version != expense.version:
        raise HTTPException(409, "EXPENSE_VERSION_CONFLICT")
    ensure_project_in_scope(db, user, payload.project_id)
    apply_expense_fields(db, expense, payload)
    expense.version += 1
    validate_expense_invoice(db, expense)
    audit(db, "project_expense", expense.id, "UPDATE", user.id, expense.status, expense.status)
    db.commit()
    db.refresh(expense)
    return project_expense_view(db, expense, user.id)


@app.delete("/api/v1/project-expenses/{expense_id}")
def delete_project_expense(expense_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    expense = db.get(ProjectExpense, expense_id)
    if not expense:
        raise HTTPException(404, "PROJECT_EXPENSE_NOT_FOUND")
    user = expense_access(db, expense, x_demo_user_id, action="DELETE")
    if expense.status not in {"DRAFT", "REJECTED", "WITHDRAWN"}:
        raise HTTPException(409, "EXPENSE_READ_ONLY")
    attachments = list(db.scalars(select(ProjectExpenseAttachment).where(ProjectExpenseAttachment.expense_id == expense.id)).all())
    for attachment in attachments:
        path = expense_attachment_path(attachment)
        if path.exists():
            path.unlink()
        db.delete(attachment)
    db.delete(expense)
    audit(db, "project_expense", expense_id, "DELETE", user.id, expense.status, None)
    db.commit()
    return {"deleted": True, "expense_id": expense_id}


@app.post("/api/v1/project-expenses/{expense_id}/preflight", response_model=list[WorkflowPathNodeView])
def preflight_project_expense(expense_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[WorkflowPathNodeView]:
    expense = db.get(ProjectExpense, expense_id)
    if not expense:
        raise HTTPException(404, "PROJECT_EXPENSE_NOT_FOUND")
    user = expense_access(db, expense, x_demo_user_id, action="EDIT")
    if expense.applicant_user_id != user.id and user.id not in system_admin_user_ids(db):
        raise HTTPException(403, "EXPENSE_APPLICANT_ONLY")
    validate_expense_invoice(db, expense)
    _version, path = resolve_expense_workflow_path(db, expense)
    return [WorkflowPathNodeView(sequence=int(item["sequence"]), node_code=str(item["node_code"]), node_name=str(item["node_name"]), approval_mode=str(item["approval_mode"]), is_payment=bool(item["is_payment"]), assignees=list(item["assignees"]), status="WAITING") for item in path]


@app.post("/api/v1/project-expenses/{expense_id}/submit", response_model=ProjectExpenseView)
def submit_project_expense(expense_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectExpenseView:
    expense = db.get(ProjectExpense, expense_id)
    if not expense:
        raise HTTPException(404, "PROJECT_EXPENSE_NOT_FOUND")
    user = expense_access(db, expense, x_demo_user_id, action="EDIT")
    if expense.applicant_user_id != user.id or expense.status not in {"DRAFT", "REJECTED", "WITHDRAWN"}:
        raise HTTPException(409, "EXPENSE_NOT_SUBMITTABLE")
    if not db.scalar(select(ProjectExpenseAttachment.id).where(ProjectExpenseAttachment.expense_id == expense.id).limit(1)):
        raise HTTPException(400, "EXPENSE_ATTACHMENT_REQUIRED")
    validate_expense_invoice(db, expense)
    version, path = resolve_expense_workflow_path(db, expense)
    expense.version += 1
    instance = WorkflowInstance(document_type=expense_document_type(expense), document_id=expense.id, workflow_version_id=version.id, applicant_user_id=user.id, status="RUNNING", current_sequence=int(path[0]["sequence"]), snapshot_json=json.dumps({"expense_version": expense.version, "nodes": path}, ensure_ascii=False), submitted_at=now_local())
    db.add(instance)
    db.flush()
    expense.current_workflow_instance_id = instance.id
    expense.status = "PENDING_APPROVAL"
    expense.submitted_at = now_local()
    tasks = assign_workflow_sequence(db, instance, int(path[0]["sequence"]))
    db.add(WorkflowActionLog(workflow_instance_id=instance.id, action="SUBMIT", actor_user_id=user.id, actor_name=user.name, from_status="DRAFT", to_status="PENDING_APPROVAL"))
    audit(db, "project_expense", expense.id, "SUBMIT", user.id, "DRAFT", "PENDING_APPROVAL")
    db.commit()
    notify_expense_tasks(db, expense, tasks)
    db.commit()
    db.refresh(expense)
    return project_expense_view(db, expense, user.id)


@app.post("/api/v1/project-expenses/{expense_id}/withdraw", response_model=ProjectExpenseView)
def withdraw_project_expense(expense_id: int, payload: WorkflowTaskRejectAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectExpenseView:
    expense = db.get(ProjectExpense, expense_id)
    if not expense:
        raise HTTPException(404, "PROJECT_EXPENSE_NOT_FOUND")
    user = expense_access(db, expense, x_demo_user_id)
    if expense.applicant_user_id != user.id or expense.status != "PENDING_APPROVAL":
        raise HTTPException(409, "EXPENSE_NOT_WITHDRAWABLE")
    instance = db.get(WorkflowInstance, expense.current_workflow_instance_id)
    if db.scalar(select(WorkflowTask.id).join(WorkflowNode, WorkflowTask.workflow_node_id == WorkflowNode.id).where(WorkflowTask.workflow_instance_id == instance.id, WorkflowNode.is_payment.is_(True), WorkflowTask.status == "PENDING")):
        raise HTTPException(409, "EXPENSE_PAYMENT_STAGE_ACTIVE")
    db.query(WorkflowTask).filter(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.status == "PENDING").update({"status": "CLOSED"}, synchronize_session=False)
    instance.status = "WITHDRAWN"
    instance.completed_at = now_local()
    expense.status = "WITHDRAWN"
    db.add(WorkflowActionLog(workflow_instance_id=instance.id, action="WITHDRAW", actor_user_id=user.id, actor_name=user.name, from_status="PENDING_APPROVAL", to_status="WITHDRAWN", comment=payload.reason))
    audit(db, "project_expense", expense.id, "WITHDRAW", user.id, "PENDING_APPROVAL", "WITHDRAWN", payload.reason)
    db.commit()
    return project_expense_view(db, expense, user.id)


@app.post("/api/v1/project-expenses/{expense_id}/reverse", response_model=ProjectExpenseView)
def reverse_project_expense(expense_id: int, payload: WorkflowTaskRejectAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectExpenseView:
    expense = db.get(ProjectExpense, expense_id)
    if not expense:
        raise HTTPException(404, "PROJECT_EXPENSE_NOT_FOUND")
    user = expense_access(db, expense, x_demo_user_id, action="REVERSE")
    if expense.status not in {"APPROVED", "APPROVED_PENDING_PAYMENT", "PAID"}:
        raise HTTPException(409, "EXPENSE_NOT_REVERSIBLE")
    original = db.scalar(select(ProjectLedgerEntry.id).where(ProjectLedgerEntry.entry_type == "PROJECT_EXPENSE_COST", ProjectLedgerEntry.source_type == "PROJECT_EXPENSE", ProjectLedgerEntry.source_id == expense.id))
    add_ledger_entry(db, expense.project_id, "REVERSAL", "PROJECT_EXPENSE", expense.id, float(expense.cost_amount), occurred_on=today_local(), reversal_of_id=original)
    expense.status = "REVERSED"
    audit(db, "project_expense", expense.id, "REVERSE", user.id, None, "REVERSED", payload.reason)
    db.commit()
    return project_expense_view(db, expense, user.id)


def workflow_task_view(db: Session, task: WorkflowTask) -> WorkflowTaskView:
    instance = db.get(WorkflowInstance, task.workflow_instance_id)
    expense = db.get(ProjectExpense, instance.document_id) if instance and instance.document_type.startswith("PROJECT_EXPENSE_") else None
    project = db.get(Project, expense.project_id) if expense else None
    return WorkflowTaskView(id=task.id, workflow_instance_id=task.workflow_instance_id, document_type=instance.document_type if instance else "", document_id=instance.document_id if instance else 0, document_no=expense.expense_no if expense else "", project_name=project.name if project else "", applicant_name=expense.applicant_name if expense else "", amount=float(expense.amount) if expense else 0, node_sequence=task.node_sequence, node_name=task.node_name, approval_mode=task.approval_mode, assignee_user_id=task.assignee_user_id, assignee_name=task.assignee_name, status=task.status, comment=task.comment, processed_at=task.processed_at, created_at=task.created_at)


@app.get("/api/v1/approval/tasks", response_model=WorkflowTaskList)
def list_workflow_tasks(status: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=200), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> WorkflowTaskList:
    user = current_user(db, x_demo_user_id)
    query = select(WorkflowTask).where(WorkflowTask.assignee_user_id == user.id)
    if status:
        query = query.where(WorkflowTask.status == status)
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = list(db.scalars(query.order_by(WorkflowTask.created_at.desc(), WorkflowTask.id.desc()).offset((page - 1) * page_size).limit(page_size)).all())
    return WorkflowTaskList(items=[workflow_task_view(db, item) for item in rows], total=total)


def active_expense_task(db: Session, task_id: int, user: User) -> tuple[WorkflowTask, WorkflowInstance, ProjectExpense, WorkflowNode]:
    task = db.get(WorkflowTask, task_id)
    if not task or task.assignee_user_id != user.id:
        raise HTTPException(404, "WORKFLOW_TASK_NOT_FOUND")
    if task.status != "PENDING":
        raise HTTPException(409, "TASK_ALREADY_HANDLED")
    instance = db.get(WorkflowInstance, task.workflow_instance_id)
    expense = db.get(ProjectExpense, instance.document_id) if instance else None
    node = db.get(WorkflowNode, task.workflow_node_id)
    if not instance or instance.status != "RUNNING" or not expense or not node:
        raise HTTPException(409, "WORKFLOW_INSTANCE_NOT_RUNNING")
    return task, instance, expense, node


@app.post("/api/v1/approval/tasks/{task_id}/approve", response_model=ProjectExpenseView)
def approve_workflow_task(task_id: int, payload: WorkflowTaskAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectExpenseView:
    user = current_user(db, x_demo_user_id)
    task, instance, expense, node = active_expense_task(db, task_id, user)
    if node.is_payment:
        raise HTTPException(409, "PAYMENT_CONFIRMATION_REQUIRED")
    task.status = "APPROVED"
    task.processed_by = user.id
    task.processed_at = now_local()
    task.comment = payload.comment
    if task.approval_mode == "ANY":
        db.query(WorkflowTask).filter(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.node_sequence == task.node_sequence, WorkflowTask.id != task.id, WorkflowTask.status == "PENDING").update({"status": "CLOSED"}, synchronize_session=False)
        node_done = True
    else:
        db.flush()
        node_done = not bool(db.scalar(select(WorkflowTask.id).where(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.node_sequence == task.node_sequence, WorkflowTask.status == "PENDING").limit(1)))
    db.add(WorkflowActionLog(workflow_instance_id=instance.id, workflow_task_id=task.id, action="APPROVE", actor_user_id=user.id, actor_name=user.name, from_status="PENDING", to_status="APPROVED", comment=payload.comment))
    next_tasks = advance_expense_workflow(db, instance, user.id) if node_done else []
    audit(db, "project_expense", expense.id, "APPROVE", user.id, "PENDING_APPROVAL", expense.status, payload.comment)
    db.commit()
    notify_expense_tasks(db, expense, next_tasks)
    if expense.status in {"APPROVED", "APPROVED_PENDING_PAYMENT"}:
        notify_expense_result(db, expense, "审批通过，待出纳支付" if expense.status == "APPROVED_PENDING_PAYMENT" else "审批通过", user.name)
    db.commit()
    return project_expense_view(db, expense, user.id)


@app.post("/api/v1/approval/tasks/{task_id}/reject", response_model=ProjectExpenseView)
def reject_workflow_task(task_id: int, payload: WorkflowTaskRejectAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectExpenseView:
    user = current_user(db, x_demo_user_id)
    task, instance, expense, _node = active_expense_task(db, task_id, user)
    task.status = "REJECTED"
    task.processed_by = user.id
    task.processed_at = now_local()
    task.comment = payload.reason
    db.query(WorkflowTask).filter(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.status == "PENDING").update({"status": "CLOSED"}, synchronize_session=False)
    instance.status = "REJECTED"
    instance.completed_at = now_local()
    expense.status = "REJECTED"
    db.add(WorkflowActionLog(workflow_instance_id=instance.id, workflow_task_id=task.id, action="REJECT", actor_user_id=user.id, actor_name=user.name, from_status="PENDING_APPROVAL", to_status="REJECTED", comment=payload.reason))
    audit(db, "project_expense", expense.id, "REJECT", user.id, "PENDING_APPROVAL", "REJECTED", payload.reason)
    db.commit()
    notify_expense_result(db, expense, "已驳回", user.name)
    db.commit()
    return project_expense_view(db, expense, user.id)


@app.post("/api/v1/approval/tasks/{task_id}/confirm-payment", response_model=ProjectExpenseView)
def confirm_expense_payment(task_id: int, payload: ProjectExpensePaymentAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectExpenseView:
    user = current_user(db, x_demo_user_id)
    task, instance, expense, node = active_expense_task(db, task_id, user)
    if not node.is_payment or expense.status != "APPROVED_PENDING_PAYMENT":
        raise HTTPException(409, "EXPENSE_NOT_PENDING_PAYMENT")
    if round(float(payload.amount), 2) != round(float(expense.amount), 2):
        raise HTTPException(400, "PAYMENT_AMOUNT_MUST_EQUAL_EXPENSE")
    payment = ProjectExpensePayment(expense_id=expense.id, amount=payload.amount, payment_date=payload.payment_date, company_account=payload.company_account, voucher_note=payload.voucher_note, cashier_user_id=user.id, status="CONFIRMED")
    db.add(payment)
    db.flush()
    add_ledger_entry(db, expense.project_id, "EXPENSE_PAYMENT", "PROJECT_EXPENSE_PAYMENT", payment.id, float(payment.amount), occurred_on=payment.payment_date)
    task.status = "PAID"
    task.processed_by = user.id
    task.processed_at = now_local()
    task.comment = payload.comment
    db.query(WorkflowTask).filter(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.node_sequence == task.node_sequence, WorkflowTask.id != task.id, WorkflowTask.status == "PENDING").update({"status": "CLOSED"}, synchronize_session=False)
    instance.status = "COMPLETED"
    instance.completed_at = now_local()
    expense.status = "PAID"
    expense.paid_at = now_local()
    db.add(WorkflowActionLog(workflow_instance_id=instance.id, workflow_task_id=task.id, action="CONFIRM_PAYMENT", actor_user_id=user.id, actor_name=user.name, from_status="APPROVED_PENDING_PAYMENT", to_status="PAID", comment=payload.comment))
    audit(db, "project_expense", expense.id, "CONFIRM_PAYMENT", user.id, "APPROVED_PENDING_PAYMENT", "PAID", payload.comment)
    db.commit()
    notify_expense_result(db, expense, "已支付", user.name)
    db.commit()
    return project_expense_view(db, expense, user.id)


@app.get("/api/v1/project-expenses/{expense_id}/attachments", response_model=list[ProjectExpenseAttachmentView])
def list_expense_attachments(expense_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[ProjectExpenseAttachmentView]:
    expense = db.get(ProjectExpense, expense_id)
    if not expense:
        raise HTTPException(404, "PROJECT_EXPENSE_NOT_FOUND")
    expense_access(db, expense, x_demo_user_id)
    rows = list(db.scalars(select(ProjectExpenseAttachment).where(ProjectExpenseAttachment.expense_id == expense.id).order_by(ProjectExpenseAttachment.id)).all())
    return [expense_attachment_view(db, item) for item in rows]


@app.post("/api/v1/project-expenses/{expense_id}/attachments", response_model=ProjectExpenseAttachmentView, status_code=201)
async def upload_expense_attachment(expense_id: int, file: UploadFile = File(...), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectExpenseAttachmentView:
    expense = db.get(ProjectExpense, expense_id)
    if not expense:
        raise HTTPException(404, "PROJECT_EXPENSE_NOT_FOUND")
    user = expense_access(db, expense, x_demo_user_id, action="EDIT")
    if expense.status not in {"DRAFT", "REJECTED", "WITHDRAWN"}:
        raise HTTPException(409, "EXPENSE_READ_ONLY")
    original_name = Path(file.filename or "").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in CONTRACT_ATTACHMENT_EXTENSIONS:
        raise HTTPException(400, "ATTACHMENT_TYPE_NOT_ALLOWED")
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "ATTACHMENT_TOO_LARGE")
    storage_name = f"{secrets.token_hex(20)}{suffix}"
    destination = expense_attachment_root() / storage_name
    destination.write_bytes(content)
    attachment = ProjectExpenseAttachment(expense_id=expense.id, file_name=original_name[:300], storage_name=storage_name, mime_type=(file.content_type or CONTRACT_ATTACHMENT_EXTENSIONS[suffix])[:160], file_size=len(content), uploaded_by=user.id)
    db.add(attachment)
    db.flush()
    audit(db, "project_expense_attachment", attachment.id, "CREATE", user.id, None, None, f"上传附件：{attachment.file_name}")
    db.commit()
    db.refresh(attachment)
    return expense_attachment_view(db, attachment)


@app.get("/api/v1/project-expense-attachments/{attachment_id}/preview", response_model=None)
def preview_expense_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> HTMLResponse | FileResponse:
    attachment = db.get(ProjectExpenseAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "EXPENSE_ATTACHMENT_NOT_FOUND")
    expense = db.get(ProjectExpense, attachment.expense_id)
    expense_access(db, expense, x_demo_user_id)
    path = expense_attachment_path(attachment)
    if not path.exists():
        raise HTTPException(404, "EXPENSE_ATTACHMENT_FILE_NOT_FOUND")
    kind = attachment_preview_kind(attachment.file_name)
    if kind in {"word", "excel", "powerpoint"}:
        try:
            preview_path, preview_dir = _convert_office_to_pdf(path)
            return FileResponse(preview_path, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(attachment.file_name)}.pdf"}, background=BackgroundTask(shutil.rmtree, preview_dir, ignore_errors=True))
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError):
            if Path(attachment.file_name).suffix.lower() in {".docx", ".xlsx", ".pptx"}:
                return HTMLResponse(render_contract_office_preview(attachment, path))
            raise HTTPException(422, "ATTACHMENT_PREVIEW_FAILED")
    return FileResponse(path, media_type=attachment.mime_type, headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(attachment.file_name)}"})


@app.get("/api/v1/project-expense-attachments/{attachment_id}/download")
def download_expense_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> FileResponse:
    attachment = db.get(ProjectExpenseAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "EXPENSE_ATTACHMENT_NOT_FOUND")
    expense_access(db, db.get(ProjectExpense, attachment.expense_id), x_demo_user_id)
    path = expense_attachment_path(attachment)
    if not path.exists():
        raise HTTPException(404, "EXPENSE_ATTACHMENT_FILE_NOT_FOUND")
    return FileResponse(path, media_type=attachment.mime_type, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.file_name)}"})


@app.delete("/api/v1/project-expense-attachments/{attachment_id}")
def delete_expense_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    attachment = db.get(ProjectExpenseAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "EXPENSE_ATTACHMENT_NOT_FOUND")
    expense = db.get(ProjectExpense, attachment.expense_id)
    user = expense_access(db, expense, x_demo_user_id, action="EDIT")
    if expense.status not in {"DRAFT", "REJECTED", "WITHDRAWN"}:
        raise HTTPException(409, "EXPENSE_READ_ONLY")
    path = expense_attachment_path(attachment)
    db.delete(attachment)
    audit(db, "project_expense_attachment", attachment.id, "DELETE", user.id, None, None, f"删除附件：{attachment.file_name}")
    db.commit()
    if path.exists():
        path.unlink()
    return {"deleted": True, "attachment_id": attachment_id}


def approval_position_view(db: Session, position: ApprovalPosition) -> ApprovalPositionView:
    members = list(db.scalars(select(User).join(ApprovalPositionMember, ApprovalPositionMember.user_id == User.id).where(ApprovalPositionMember.position_id == position.id).order_by(User.name)).all())
    return ApprovalPositionView(id=position.id, code=position.code, name=position.name, description=position.description, status=position.status, member_ids=[item.id for item in members], member_names=[item.name for item in members], updated_at=position.updated_at)


@app.get("/api/v1/admin/approval-positions", response_model=list[ApprovalPositionView])
def list_approval_positions(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[ApprovalPositionView]:
    require_access(db, "approval_positions", "VIEW", x_demo_user_id)
    return [approval_position_view(db, item) for item in db.scalars(select(ApprovalPosition).order_by(ApprovalPosition.id)).all()]


@app.put("/api/v1/admin/approval-positions/{position_id}", response_model=ApprovalPositionView)
def update_approval_position(position_id: int, payload: ApprovalPositionUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ApprovalPositionView:
    admin = require_access(db, "approval_positions", "CONFIGURE", x_demo_user_id)
    position = db.get(ApprovalPosition, position_id)
    if not position:
        raise HTTPException(404, "APPROVAL_POSITION_NOT_FOUND")
    members = [active_org_user(db, user_id) for user_id in dict.fromkeys(payload.member_ids)]
    if payload.status == "ACTIVE" and not members:
        raise HTTPException(400, "APPROVAL_POSITION_MEMBERS_REQUIRED")
    position.name = payload.name.strip()
    position.description = payload.description.strip() if payload.description else None
    position.status = payload.status
    position.updated_by = admin.id
    db.query(ApprovalPositionMember).filter(ApprovalPositionMember.position_id == position.id).delete(synchronize_session=False)
    for member in members:
        db.add(ApprovalPositionMember(position_id=position.id, user_id=member.id))
    audit(db, "approval_position", position.id, "UPDATE", admin.id, None, position.status, ", ".join(item.name for item in members))
    db.commit()
    db.refresh(position)
    return approval_position_view(db, position)


def workflow_definition_view(db: Session, definition: WorkflowDefinition) -> WorkflowDefinitionView:
    version = db.get(WorkflowVersion, definition.current_version_id) if definition.current_version_id else None
    nodes = list(db.scalars(select(WorkflowNode).where(WorkflowNode.workflow_version_id == version.id).order_by(WorkflowNode.sequence)).all()) if version else []
    position_by_id = {item.id: item for item in db.scalars(select(ApprovalPosition)).all()}
    views = [WorkflowPathNodeView(sequence=node.sequence, node_code=node.code, node_name=node.name, approval_mode=node.approval_mode, is_payment=node.is_payment, assignees=[{"id": node.position_id or 0, "name": position_by_id[node.position_id].name}] if node.position_id in position_by_id else [], status="PUBLISHED") for node in nodes]
    try:
        types = json.loads(definition.document_types or "[]")
    except json.JSONDecodeError:
        types = []
    return WorkflowDefinitionView(id=definition.id, code=definition.code, name=definition.name, document_types=types, status=definition.status, current_version_id=definition.current_version_id, current_version=version.version if version else None, node_count=len(nodes), nodes=views)


@app.get("/api/v1/admin/workflows", response_model=list[WorkflowDefinitionView])
def list_workflows(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[WorkflowDefinitionView]:
    require_access(db, "approval_workflows", "VIEW", x_demo_user_id)
    return [workflow_definition_view(db, item) for item in db.scalars(select(WorkflowDefinition).order_by(WorkflowDefinition.id)).all()]


@app.get("/api/v1/timesheets/{timesheet_id}", response_model=TimesheetView)
def get_legacy_timesheet(timesheet_id: int, db: Session = Depends(get_db)) -> TimesheetView:
    """保留旧周期单只读查询，v2.0 不再创建新的周期审批单。"""
    sheet = db.get(Timesheet, timesheet_id)
    if not sheet:
        raise HTTPException(404, "TIMESHEET_NOT_FOUND")
    items = db.scalars(select(Worklog).where(Worklog.timesheet_id == sheet.id).order_by(Worklog.start_date)).all()
    return TimesheetView(id=sheet.id, serial_no=sheet.serial_no, period_start=sheet.period_start, period_end=sheet.period_end, total_quantity=float(sheet.total_quantity), unit=sheet.unit, status=sheet.status, approval_instance_code=sheet.approval_instance_code, approver_name=sheet.approver_name, worklogs=[worklog_view(item) for item in items])
