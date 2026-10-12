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

from .db.models import AdminPermission, ApprovalPosition, ApprovalPositionMember, AuditLog, ApprovalTask, BudgetItemTemplate, CashDocumentAttachment, ConfigOption, Contract, ContractAttachment, ContractStage, Customer, Department, Menu, Notification, NotificationPolicy, OrgSyncLog, Payment, PaymentPlan, PermissionAudit, Project, ProjectBudgetItem, ProjectCostAttachment, ProjectCostEntry, ProjectExpense, ProjectExpenseAttachment, ProjectExpensePayment, ProjectLedgerEntry, Receipt, ReceiptPlan, ReminderEvent, Role, RoleDataScope, RolePermission, Supplier, SystemNotification, Timesheet, User, UserRole, UserRoleScope, WorkCalendarDay, WorkflowActionLog, WorkflowDefinition, WorkflowInstance, WorkflowNode, WorkflowTask, WorkflowVersion, Worklog
from .db.session import Base, SessionLocal, engine, get_db
from .time_utils import now_local, today_local
from .schemas import (
    ApprovalAction,
    ApprovalPositionUpdate,
    ApprovalPositionView,
    AdminWorklogList,
    AdminWorklogView,
    BatchApprovalRequest,
    BatchApprovalResult,
    BatchApprovalResultItem,
    BatchRejectionRequest,
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
    ClassificationCatalog,
    ClassificationNode,
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
    WorklogFillReminderRunResult,
    ProjectBoardAgingBucket,
    ProjectBoardAgingItem,
    ProjectBoardInsights,
    OrgDepartmentView,
    OrgSyncView,
    PaymentCreate,
    PaymentPlanCreate,
    PaymentPlanList,
    PaymentPlanSummary,
    PaymentPlanUpdate,
    PaymentPlanView,
    PaymentUpdate,
    PaymentView,
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
    ProjectCostAttachmentView,
    ProjectCostEntryCreate,
    ProjectCostEntryPage,
    ProjectCostEntryUpdate,
    ProjectCostEntryView,
    ProjectCostRejectAction,
    ProjectCostReviewAction,
    ProjectCostReversalAction,
    CostReviewItem,
    CostReviewPage,
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
    ReceiptLedgerList,
    ReceiptLedgerSummary,
    ReceiptPlanUpsert,
    ReceiptPlanView,
    ReceiptUpdate,
    ReceiptView,
    BusinessAnalysisTrendItem,
    BusinessAnalysisView,
    RejectionAction,
    SupplierCreate,
    SupplierUpdate,
    SupplierView,
    TimesheetView,
    UserRoleList,
    UserRoleUpdate,
    UserRoleView,
    UserView,
    WorkflowPathNodeView,
    WorkflowTaskAction,
    WorkflowTaskList,
    WorkflowTaskRejectAction,
    WorkflowTaskView,
    WorkflowActionLogView,
    WorkbenchOverview,
    WorkbenchProjectRow,
    WorkbenchReminder,
    WorklogCalendar,
    WorklogCalendarDay,
    WorklogCalendarSummary,
    WorklogCreate,
    WorklogList,
    WorklogMonthlyLedgerDetailList,
    WorklogMonthlyLedgerItem,
    WorklogMonthlyLedgerList,
    WorklogMonthlyLedgerPrintRow,
    WorklogMonthlyLedgerPrintView,
    WorklogUpdate,
    WorkCalendarList,
    WorkCalendarDayView,
    WorkCalendarDayUpsert,
    WorklogView,
)
from .services.feishu import FeishuAdapter


API_VERSION = "3.0.97"
TIMEZONE_DATA_MIGRATION_VERSION = 1
RBAC_RESET_MARKER = "RBAC_ROLE_RESET_V3_0_24"
FIRST_FEISHU_ADMIN_MARKER = "FIRST_FEISHU_ADMIN_USER_ID"
RBAC_ACTIONS = ("VIEW", "CREATE", "UPDATE", "EDIT", "DELETE", "APPROVE", "EXPORT", "IMPORT", "UPLOAD", "DOWNLOAD", "SYNC", "RETRY", "CONFIGURE", "PUBLISH", "DISABLE", "REVERSE")
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
    ("project_budget", "projects", "项目预算项", "projectBudgetItems", 31, ["VIEW", "CREATE", "EDIT", "DELETE", "IMPORT", "EXPORT"]),
    ("contracts", None, "项目合同", "projectContracts", 32, ["VIEW", "CREATE", "EDIT", "DELETE"]),
    ("receipts", None, "合同收款", "projectReceipts", 33, ["VIEW", "CREATE", "EDIT", "DELETE", "APPROVE", "EXPORT"]),
    ("payments", None, "合同付款", "projectPayments", 34, ["VIEW", "CREATE", "EDIT", "DELETE", "APPROVE", "EXPORT"]),
    ("receipt_ledger", None, "回款台账", "receiptLedger", 35, ["VIEW", "CREATE", "EDIT", "DELETE", "EXPORT"]),
    ("payment_plan", None, "付款计划", "paymentPlans", 36, ["VIEW", "CREATE", "EDIT", "DELETE", "EXPORT"]),
    ("business_analysis", None, "经营分析", "businessAnalysis", 37, ["VIEW", "EXPORT"]),
    ("project_expenses", None, "项目费用", "projectExpenses", 38, ["VIEW", "CREATE", "EDIT", "DELETE", "APPROVE", "REVERSE", "EXPORT"]),
    ("labor_costs", None, "人工成本结转", "laborCosts", 39, ["VIEW", "CREATE", "EDIT", "DELETE", "APPROVE", "REVERSE", "EXPORT"]),
    ("cost_review", None, "费用复核", "costReview", 40, ["VIEW", "APPROVE"]),
    ("project_board", None, "项目看板", "projectBoard", 41, ["VIEW", "EXPORT"]),
    ("counterparties", None, "客户与供应商", "customers", 42, ["VIEW", "CREATE", "EDIT", "DELETE"]),
    ("cash_approval", None, "收付款复核", "projectReceipts", 43, ["VIEW", "APPROVE"]),
    ("budget_templates", None, "预算项模板", "budgetTemplates", 45, ["VIEW", "CREATE", "EDIT", "DELETE"]),
    ("integrations", None, "集成与通知", "integrations", 50, ["VIEW", "CONFIGURE", "SYNC", "EXPORT"]),
    ("admins", None, "权限管理", "adminPermissions", 51, ["VIEW", "CONFIGURE"]),
    ("approval_positions", None, "复核岗位", "approvalPositions", 52, ["VIEW", "CONFIGURE"]),
    ("configuration", None, "基础配置", "configuration", 54, ["VIEW", "CREATE", "EDIT", "DELETE"]),
]
# v3.0.59 起不再作为新单据入口的内置菜单：保留菜单行与授权，仅从导航下线。
# 注意：这些 code 必须同时存在于 RBAC_MENU_SEED，否则历史授权行会因找不到菜单而解析失败。
# project_budget（项目预算项）：预算项接口的鉴权实际走 projects，该菜单只在权限管理里多出一个
# 勾选项，容易让人以为预算项需要单独授权，v3.0.66 起下线。
RETIRED_MENU_SEED = ["budget_templates", "project_budget"]
# v3.0.68 起彻底删除的功能入口：菜单行与其全部授权一次性清理，不再出现在任何位置。
# personnel_costs（人员成本）：日成本折算在 v3.0.61 已由人工成本结转单取代，功能整体删除。
# approval_workflows（审批流程）：v3.0.69 起删除。费用/付款的单据流转已由审批岗位与一级费用
# 复核接管，页面只剩一个只读列表，没有可维护内容，继续挂着只会误导配置。
PURGED_MENU_SEED = ["personnel_costs", "approval_workflows"]
RBAC_ROLE_SEED = {
    "system_admin": ("系统管理员", "拥有全部菜单、操作和数据范围", {code: list(actions) for code, _, _, _, _, actions in RBAC_MENU_SEED}, "ALL"),
    "project_manager": ("项目经营管理员", "维护项目经营主数据、预算、成本和收付款", {code: list(actions) for code, _, _, _, _, actions in RBAC_MENU_SEED if code in {"projects", "project_budget", "contracts", "receipts", "payments", "receipt_ledger", "payment_plan", "business_analysis", "project_expenses", "labor_costs", "cost_review", "project_board", "counterparties"}}, "ALL"),
    "project_owner": ("项目负责人", "管理负责项目的经营数据", {code: ["VIEW", "CREATE", "EDIT"] for code in ["projects", "contracts", "receipts", "payments", "receipt_ledger", "payment_plan", "project_expenses", "labor_costs"]} | {"project_budget": ["VIEW"], "business_analysis": ["VIEW"], "project_board": ["VIEW"], "cost_review": ["VIEW"]}, "OWNED_PROJECTS"),
    "cashier": ("出纳", "处理合同收付款单据和收付款复核", {"receipts": ["VIEW", "CREATE", "EDIT", "APPROVE"], "payments": ["VIEW", "CREATE", "EDIT", "APPROVE"], "cash_approval": ["VIEW", "APPROVE"], "cost_review": ["VIEW"]}, "OWNED_PROJECTS"),
    "worklog_manager": ("工时管理员", "维护工时台账和工时看板", {"worklogs": ["VIEW", "EDIT", "DELETE", "EXPORT"], "reports": ["VIEW", "EXPORT"]}, "DEPARTMENT_AND_CHILDREN"),
    "worklog_approver": ("工时审批人", "处理分配给自己的工时审批", {"approvals": ["VIEW", "APPROVE"]}, "SELF"),
    "cost_reviewer": ("费用复核员", "一级复核合同付款、项目费用和人工成本结转", {"cost_review": ["VIEW", "APPROVE"], "payments": ["VIEW"], "project_expenses": ["VIEW"], "labor_costs": ["VIEW"]}, "ALL"),
    "finance": ("财务", "按月录入人工成本结转并维护项目成本", {"labor_costs": ["VIEW", "CREATE", "EDIT", "DELETE", "REVERSE", "EXPORT"], "project_expenses": ["VIEW", "CREATE", "EDIT", "DELETE", "REVERSE", "EXPORT"], "project_budget": ["VIEW", "EXPORT"], "cost_review": ["VIEW"], "projects": ["VIEW"], "project_board": ["VIEW"]}, "ALL"),
    "business_viewer": ("经营查看者", "只读查看项目经营数据", {code: ["VIEW"] for code in ["projects", "project_budget", "contracts", "receipts", "payments", "project_expenses", "labor_costs", "project_board", "counterparties"]}, "DEPARTMENT_AND_CHILDREN"),
    "integration_manager": ("集成管理员", "维护飞书集成和通知策略", {"integrations": ["VIEW", "CONFIGURE", "SYNC", "EXPORT"]}, "ALL"),
}
CONFIG_CATEGORY_LABELS = {
    "project_stage": "项目阶段",
    "work_type": "工时类型",
    "work_status": "工作状态",
    "project_status": "项目状态",
    "project_category": "项目大类",
    "project_sub_category": "项目小类",
}
# 层级分类：上级分类 -> 下级分类。成本分类已并入统一 8 项预算项，不再单独成树。
CLASSIFICATION_TREE_CATEGORIES = {
    "project_category": "project_sub_category",
}
DEFAULT_CONFIG_OPTIONS = {
    "project_stage": [("需求", "需求"), ("设计", "设计"), ("开发", "开发"), ("联调", "联调"), ("测试", "测试"), ("交付", "交付"), ("管理", "管理"), ("现场", "现场"), ("其它", "其它")],
    "work_type": [
        ("RND_PROJECT_WORK", "研发项目工时"),
        ("TECH_SERVICE_WORK", "技术服务工时"),
        ("DEMO_PROMOTION_WORK", "观摩推广工时"),
        ("MARKETING_WORK", "市场营销工时"),
        ("MANAGEMENT_WORK", "管理工时"),
        ("OTHER_WORK", "其他工时"),
    ],
    "work_status": [("LOCAL", "本地"), ("BUSINESS_TRIP", "出差"), ("REMOTE", "异地办公"), ("LEAVE", "休假")],
    "project_status": [("PRE_APPROVAL", "预立项"), ("ACTIVE", "进行中"), ("ACCEPTANCE", "验收中"), ("PAUSED", "已暂停"), ("COMPLETED", "已完成"), ("PRE_APPROVAL_FAILED", "预立项失败")],
}
PROJECT_WORK_TYPES = {"RND_PROJECT_WORK", "TECH_SERVICE_WORK", "PROJECT"}
NON_PROJECT_WORK_TYPES = {"DEMO_PROMOTION_WORK", "MARKETING_WORK", "MANAGEMENT_WORK", "OTHER_WORK", "MANAGEMENT", "OTHER"}
LEGACY_WORK_TYPE_VALUES = {"PROJECT", "MANAGEMENT", "OTHER"}
WORK_TYPE_PROJECT_CATEGORY = {
    "RND_PROJECT_WORK": "RND_PROJECT",
    "TECH_SERVICE_WORK": "BUSINESS_PROJECT",
}
PRE_APPROVAL_CONVERTIBLE_WORK_TYPES = {"RND_PROJECT_WORK", "TECH_SERVICE_WORK", "PROJECT"}
# 项目分类树默认内容，依据《项目预算与成本复核重构设计》v3.0.59 第 3 节。
# 数组结构：上级编码、上级名称、[(下级编码, 下级名称), ...]。
DEFAULT_CLASSIFICATION_TREES = {
    "project_category": [
        (
            "BUSINESS_PROJECT",
            "经营项目",
            [
                ("ENTRUSTED_RND", "委托研发"),
                ("EQUIPMENT_SALES", "设备销售"),
                ("TECHNICAL_SERVICE", "技术服务"),
                ("ROBOT_CONSTRUCTION", "机器人施工"),
                ("EQUIPMENT_RENTAL", "设备租赁"),
            ],
        ),
        (
            "RND_PROJECT",
            "研发项目",
            [
                ("SELF_DEVELOPED_RND", "自主研发"),
                ("EXTERNAL_DECLARATION", "外部申报"),
            ],
        ),
    ],
}
# 旧项目类型到项目大类的归并关系；第二个元素为可推导出的项目小类。
LEGACY_PROJECT_CATEGORY_ALIASES = {
    "TOPIC_PROJECT": ("RND_PROJECT", None),
    "SELF_DEVELOPED_RND": ("RND_PROJECT", "SELF_DEVELOPED_RND"),
    "EXTERNAL_DECLARATION": ("RND_PROJECT", "EXTERNAL_DECLARATION"),
    "IMPLEMENTATION_PROJECT": ("BUSINESS_PROJECT", None),
    "DEMONSTRATION_PROJECT": ("BUSINESS_PROJECT", None),
    "研发项目": ("RND_PROJECT", None),
    "课题项目": ("RND_PROJECT", None),
    "实施项目": ("BUSINESS_PROJECT", None),
    "观摩项目": ("BUSINESS_PROJECT", None),
    "经营项目": ("BUSINESS_PROJECT", None),
    "自主研发": ("RND_PROJECT", "SELF_DEVELOPED_RND"),
    "外部申报": ("RND_PROJECT", "EXTERNAL_DECLARATION"),
}
PROJECT_CATEGORY_LABELS = {"BUSINESS_PROJECT": "经营项目", "RND_PROJECT": "研发项目"}
# 预算项即成本归集口径：经营与研发共用同一套 8 项，不再区分成本大类/小类。
# 数组结构：预算项编码、预算项名称、来源类型。
DEFAULT_BUDGET_ITEM_TEMPLATES = {
    "BUSINESS_PROJECT": [
        ("LABOR_COST", "人工费用", "LABOR"),
        ("MATERIAL_EQUIPMENT", "材料、设备采购", "MIXED"),
        ("UTILITIES", "水、电、燃气费用", "MIXED"),
        ("OUTSOURCING", "委托、分包、外包费用", "MIXED"),
        ("TRAVEL_COST", "差旅费用", "MIXED"),
        ("PACKAGING_TRANSPORT", "包装、运输费用", "MIXED"),
        ("LEASE_DEPRECIATION", "租赁费、折旧费", "MIXED"),
        ("OTHER_COST", "其他费用", "MIXED"),
    ],
    "RND_PROJECT": [
        ("LABOR_COST", "人工费用", "LABOR"),
        ("MATERIAL_EQUIPMENT", "材料、设备采购", "MIXED"),
        ("UTILITIES", "水、电、燃气费用", "MIXED"),
        ("OUTSOURCING", "委托、分包、外包费用", "MIXED"),
        ("TRAVEL_COST", "差旅费用", "MIXED"),
        ("PACKAGING_TRANSPORT", "包装、运输费用", "MIXED"),
        ("LEASE_DEPRECIATION", "租赁费、折旧费", "MIXED"),
        ("OTHER_COST", "其他费用", "MIXED"),
    ],
}
PROJECT_BUDGET_ITEM_COUNT = len(next(iter(DEFAULT_BUDGET_ITEM_TEMPLATES.values())))
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
    ("PENDING_RECEIPT", "待复核合同收款单", True, 0),
    ("PENDING_PAYMENT_REVIEW", "合同付款待复核", True, 0),
    ("PENDING_EXPENSE_REVIEW", "项目费用待复核", True, 0),
    ("PENDING_LABOR_REVIEW", "人工成本待复核", True, 0),
    ("COST_REVIEW_RESULT", "费用复核结果", True, 0),
    # v3.0.64：定时填报提醒默认停用，管理员配置提醒时间和通知范围后启用。
    ("WORKLOG_FILL_REMINDER", "工时填报提醒", False, 0),
    # v3.0.81：T-1 补漏提醒默认停用，范围默认继承定时填报提醒，避免默认全量误发。
    ("WORKLOG_FILL_REMINDER_T1", "工时补填提醒（T-1）", False, 0),
]
# 工时填报提醒：默认每个工作日 09:00 提醒一次，未配置时回落到该默认值。
WORKLOG_FILL_REMINDER_TYPE = "WORKLOG_FILL_REMINDER"
WORKLOG_FILL_REMINDER_DEFAULT_TIME = "09:00"
# 扫描器按分钟推进，命中窗口覆盖扫描间隔，保证配置时刻一定会被扫到且只发一次。
WORKLOG_FILL_REMINDER_MATCH_WINDOW_MINUTES = 10
# 默认工作日规则：未被国家法定工作日历覆盖的日期按周一至周五处理。
WORKDAY_WEEKDAYS = (0, 1, 2, 3, 4)
CHINA_2026_WORK_CALENDAR_SOURCE = "国务院办公厅2026年部分节假日安排"
CHINA_2026_HOLIDAYS = {
    "2026-01-01": "元旦",
    "2026-01-02": "元旦",
    "2026-01-03": "元旦",
    "2026-02-15": "春节",
    "2026-02-16": "春节",
    "2026-02-17": "春节",
    "2026-02-18": "春节",
    "2026-02-19": "春节",
    "2026-02-20": "春节",
    "2026-02-21": "春节",
    "2026-02-22": "春节",
    "2026-02-23": "春节",
    "2026-04-04": "清明节",
    "2026-04-05": "清明节",
    "2026-04-06": "清明节",
    "2026-05-01": "劳动节",
    "2026-05-02": "劳动节",
    "2026-05-03": "劳动节",
    "2026-05-04": "劳动节",
    "2026-05-05": "劳动节",
    "2026-06-19": "端午节",
    "2026-06-20": "端午节",
    "2026-06-21": "端午节",
    "2026-09-25": "中秋节",
    "2026-09-26": "中秋节",
    "2026-09-27": "中秋节",
    "2026-10-01": "国庆节",
    "2026-10-02": "国庆节",
    "2026-10-03": "国庆节",
    "2026-10-04": "国庆节",
    "2026-10-05": "国庆节",
    "2026-10-06": "国庆节",
    "2026-10-07": "国庆节",
}
CHINA_2026_ADJUSTED_WORKDAYS = {
    "2026-01-04": "元旦调休上班",
    "2026-02-14": "春节调休上班",
    "2026-02-28": "春节调休上班",
    "2026-05-09": "劳动节调休上班",
    "2026-09-20": "中秋节调休上班",
    "2026-10-10": "国庆节调休上班",
}
# v3.0.81：T-1 补漏提醒——每个工作日按设定时刻提醒补填上一个工作日漏填的工时。
WORKLOG_FILL_REMINDER_T1_TYPE = "WORKLOG_FILL_REMINDER_T1"
WORKLOG_FILL_REMINDER_T1_DEFAULT_TIME = "09:30"
# v3.0.59 多级审批与出纳确认口径作废，对应通知策略随之下线（保留记录不再触发）。
RETIRED_NOTIFICATION_TYPES = [
    "PENDING_PAYMENT",
    "PAYMENT_RESULT",
    "EXPENSE_APPROVAL",
    "EXPENSE_RESULT",
    "EXPENSE_PAYMENT",
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


def seed_work_calendar(db: Session) -> None:
    """内置国家法定工作日历覆盖项；只补缺失项，不覆盖管理员后续维护。"""
    rows: list[tuple[str, str, str]] = []
    rows.extend((day, "HOLIDAY", name) for day, name in CHINA_2026_HOLIDAYS.items())
    rows.extend((day, "WORKDAY", name) for day, name in CHINA_2026_ADJUSTED_WORKDAYS.items())
    for day_text, day_type, name in rows:
        calendar_date = date.fromisoformat(day_text)
        existing = db.scalar(select(WorkCalendarDay).where(WorkCalendarDay.calendar_date == calendar_date))
        if existing:
            continue
        db.add(
            WorkCalendarDay(
                calendar_date=calendar_date,
                day_type=day_type,
                name=name,
                source=CHINA_2026_WORK_CALENDAR_SOURCE,
                is_builtin=True,
            )
        )


def seed_classification_trees(db: Session) -> None:
    """初始化项目分类树与成本分类树，幂等执行且不覆盖管理员的名称调整。"""
    for parent_category, tree in DEFAULT_CLASSIFICATION_TREES.items():
        child_category = CLASSIFICATION_TREE_CATEGORIES[parent_category]
        for parent_order, (parent_value, parent_label, children) in enumerate(tree, start=1):
            parent = db.scalar(select(ConfigOption).where(ConfigOption.category == parent_category, ConfigOption.value == parent_value))
            if not parent:
                parent = ConfigOption(
                    category=parent_category,
                    value=parent_value,
                    label=parent_label,
                    level=1,
                    is_leaf=not children,
                    sort_order=parent_order * 10,
                    is_active=True,
                    is_builtin=True,
                )
                db.add(parent)
                db.flush()
            else:
                parent.level = 1
                parent.is_leaf = not children
                if parent.is_builtin:
                    parent.label = parent_label
            parent.path = f"/{parent.id}/"
            for child_order, (child_value, child_label) in enumerate(children, start=1):
                child = db.scalar(select(ConfigOption).where(ConfigOption.category == child_category, ConfigOption.value == child_value))
                if not child:
                    child = ConfigOption(
                        category=child_category,
                        value=child_value,
                        label=child_label,
                        parent_id=parent.id,
                        level=2,
                        is_leaf=True,
                        sort_order=child_order * 10,
                        is_active=True,
                        is_builtin=True,
                    )
                    db.add(child)
                    db.flush()
                else:
                    if child.is_builtin:
                        child.label = child_label
                    child.parent_id = child.parent_id or parent.id
                    child.level = 2
                    child.is_leaf = True
                child.path = f"/{parent.id}/{child.id}/"
            db.flush()


def normalize_project_categories(db: Session) -> None:
    """把历史项目类型归并为项目大类，并尽量补齐项目小类。"""
    for project in db.scalars(select(Project)).all():
        major, derived_sub = resolve_project_category(project.project_type)
        if project.project_type != major:
            project.project_type = major
        if not project.project_sub_category and derived_sub:
            project.project_sub_category = derived_sub


def resolve_project_category(value: str | None) -> tuple[str, str | None]:
    """把项目大类输入归一到内置两类；返回可推导出的项目小类编码。"""
    normalized = (value or "").strip()
    if normalized in ("BUSINESS_PROJECT", "RND_PROJECT"):
        return normalized, None
    if normalized in LEGACY_PROJECT_CATEGORY_ALIASES:
        return LEGACY_PROJECT_CATEGORY_ALIASES[normalized]
    return "BUSINESS_PROJECT", None


def project_sub_category_label(db: Session, value: str | None) -> str | None:
    """返回项目小类的展示名称，供列表与详情展示。"""
    if not value:
        return None
    option = db.scalar(select(ConfigOption).where(ConfigOption.category == "project_sub_category", ConfigOption.value == value))
    return option.label if option else value


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
        for order, (code, name, source_kind) in enumerate(rows, start=1):
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
                        source_kind=source_kind,
                        sort_order=order * 10,
                        is_active=True,
                        is_builtin=True,
                    )
                )
            elif template.is_builtin:
                template.name = name
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
    """把预算项快照写入合同、付款、费用或流水；成本分类已并入预算项。"""
    setattr(target, "budget_item_id", item.id if item else None)
    setattr(target, "budget_item_name_snapshot", item.name if item else None)


def apply_contract_budget_snapshot(db: Session, target: object, contract: Contract) -> ProjectBudgetItem | None:
    """付款单继承支出合同预算项快照，合同项仍存在时返回预算项实体供流水使用。"""
    item = db.get(ProjectBudgetItem, contract.budget_item_id) if contract.budget_item_id else None
    setattr(target, "budget_item_id", contract.budget_item_id)
    setattr(target, "budget_item_name_snapshot", contract.budget_item_name_snapshot)
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
            policy = NotificationPolicy(notification_type=notification_type, label=label, enabled=enabled, send_channel="app", remind_days_before=remind_days_before)
            if notification_type == WORKLOG_FILL_REMINDER_TYPE:
                policy.schedule_time = WORKLOG_FILL_REMINDER_DEFAULT_TIME
            if notification_type == WORKLOG_FILL_REMINDER_T1_TYPE:
                policy.schedule_time = WORKLOG_FILL_REMINDER_T1_DEFAULT_TIME
                # 补漏提醒与定时填报提醒面向同一批人，首次出现时直接继承范围配置。
                source = db.scalar(select(NotificationPolicy).where(NotificationPolicy.notification_type == WORKLOG_FILL_REMINDER_TYPE))
                if source:
                    policy.target_scope = source.target_scope
                    policy.target_ids = source.target_ids
                    policy.only_unfilled = source.only_unfilled
                    policy.send_channel = source.send_channel
            db.add(policy)
        elif policy.label != label:
            policy.label = label
    # 会话关闭了自动刷新，先落盘再补默认值，避免刚插入的策略查不到。
    db.flush()
    # 定时填报提醒首次出现时补默认时刻；管理员改过以后不再覆盖。
    fill_policy = db.scalar(select(NotificationPolicy).where(NotificationPolicy.notification_type == WORKLOG_FILL_REMINDER_TYPE))
    if fill_policy and not (fill_policy.schedule_time or "").strip():
        fill_policy.schedule_time = WORKLOG_FILL_REMINDER_DEFAULT_TIME
    t1_policy = db.scalar(select(NotificationPolicy).where(NotificationPolicy.notification_type == WORKLOG_FILL_REMINDER_T1_TYPE))
    if t1_policy and not (t1_policy.schedule_time or "").strip():
        t1_policy.schedule_time = WORKLOG_FILL_REMINDER_T1_DEFAULT_TIME
    # v3.0.59：多级审批相关的旧策略不再触发，改为停用而非删除，便于追溯历史通知。
    for policy in db.scalars(select(NotificationPolicy).where(NotificationPolicy.notification_type.in_(RETIRED_NOTIFICATION_TYPES))).all():
        policy.enabled = False


def disable_retired_menus(db: Session) -> None:
    """下线不再作为新入口的内置菜单，保留菜单行以兼容历史授权记录。"""
    for menu in db.scalars(select(Menu).where(Menu.code.in_(RETIRED_MENU_SEED), Menu.is_active.is_(True))).all():
        menu.is_active = False


def drop_retired_menu_grants(db: Session) -> None:
    """删除已下线菜单的历史授权。

    菜单停用后界面不再展示，用户无法自行取消勾选；若保留这些授权行，
    前端保存时会把它们原样回传，被后端判为非法菜单并拒绝整单提交，
    导致该角色的权限永远改不动。这里随启动统一清理。
    """
    retired_menu_ids = [item.id for item in db.scalars(select(Menu).where(Menu.code.in_(RETIRED_MENU_SEED))).all()]
    if retired_menu_ids:
        db.query(RolePermission).filter(RolePermission.menu_id.in_(retired_menu_ids)).delete(synchronize_session=False)
    db.query(RoleDataScope).filter(RoleDataScope.resource.in_(RETIRED_MENU_SEED)).delete(synchronize_session=False)
    db.query(UserRoleScope).filter(UserRoleScope.resource.in_(RETIRED_MENU_SEED)).delete(synchronize_session=False)


def purge_deleted_menus(db: Session) -> None:
    """删除已彻底下线功能的菜单行及其全部授权。

    覆盖 PURGED_MENU_SEED 里的全部 code（人员成本、审批流程）：
    菜单行留着只会让权限管理多出一个无意义的勾选项。
    """
    menu_ids = [item.id for item in db.scalars(select(Menu).where(Menu.code.in_(PURGED_MENU_SEED))).all()]
    if menu_ids:
        db.query(RolePermission).filter(RolePermission.menu_id.in_(menu_ids)).delete(synchronize_session=False)
    db.query(RoleDataScope).filter(RoleDataScope.resource.in_(PURGED_MENU_SEED)).delete(synchronize_session=False)
    db.query(UserRoleScope).filter(UserRoleScope.resource.in_(PURGED_MENU_SEED)).delete(synchronize_session=False)
    if menu_ids:
        db.query(Menu).filter(Menu.id.in_(menu_ids)).delete(synchronize_session=False)


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
            # 已下线菜单不再写入默认授权：写了也会被 drop_retired_menu_grants 清掉，
            # 中途还可能被前端回传判为非法菜单。
            if menu_code in RETIRED_MENU_SEED:
                continue
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
    """初始化复核岗位和两套已确认流程；已有发布版本绝不覆盖。

    v3.0.59 起新单据只走一级费用复核，岗位改为“复核岗位”，
    历史多级流程定义保留只读，不再作为新单据配置入口。
    """
    position_specs = [
        ("COST_REVIEWER", "费用复核", "一级复核合同付款、项目费用和人工成本结转"),
        ("RECEIPT_REVIEWER", "收款复核", "一级复核合同收款"),
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


def grant_cost_review_permissions(db: Session) -> None:
    """一级费用复核上线后，把复核权限补给原本能审批合同付款或项目费用的角色。

    同时补发「人工成本结转」权限（沿用项目费用的动作集合），并创建「费用复核」
    岗位、纳入现有会计岗位成员。全过程幂等，管理员后续在界面上的调整不会被覆盖。
    """
    review_menu = db.scalar(select(Menu).where(Menu.code == COST_REVIEW_RESOURCE))
    if not review_menu:
        return
    labor_menu = db.scalar(select(Menu).where(Menu.code == "labor_costs"))
    expense_menu = db.scalar(select(Menu).where(Menu.code == "project_expenses"))
    payment_menu = db.scalar(select(Menu).where(Menu.code == "payments"))
    labor_actions = json.loads(labor_menu.actions or "[]") if labor_menu else []

    def actions_of(role_id: int, menu: Menu | None) -> list[str]:
        if not menu:
            return []
        row = db.scalar(select(RolePermission).where(RolePermission.role_id == role_id, RolePermission.menu_id == menu.id))
        if not row:
            return []
        try:
            return list(json.loads(row.actions or "[]"))
        except ValueError:
            return []

    def permission_row(role_id: int, menu: Menu) -> RolePermission | None:
        return db.scalar(select(RolePermission).where(RolePermission.role_id == role_id, RolePermission.menu_id == menu.id))

    for role in db.scalars(select(Role)).all():
        approvable = "APPROVE" in actions_of(role.id, payment_menu) or "APPROVE" in actions_of(role.id, expense_menu)
        if not approvable:
            continue
        if not permission_row(role.id, review_menu):
            db.add(RolePermission(role_id=role.id, menu_id=review_menu.id, actions=json.dumps(["VIEW", "APPROVE"])))
        if labor_menu and expense_menu and not permission_row(role.id, labor_menu):
            wanted = [action for action in actions_of(role.id, expense_menu) if action in labor_actions] or ["VIEW"]
            db.add(RolePermission(role_id=role.id, menu_id=labor_menu.id, actions=json.dumps(wanted)))
    db.flush()

    position = db.scalar(select(ApprovalPosition).where(ApprovalPosition.code == "COST_REVIEWER"))
    if not position:
        position = ApprovalPosition(code="COST_REVIEWER", name="费用复核", description="一级复核合同付款、项目费用与人工成本结转", status="ACTIVE")
        db.add(position)
        db.flush()
    accountant = db.scalar(select(ApprovalPosition).where(ApprovalPosition.code == "ACCOUNTANT"))
    source_ids = set()
    if accountant:
        source_ids = {item.user_id for item in db.scalars(select(ApprovalPositionMember).where(ApprovalPositionMember.position_id == accountant.id)).all()}
    existing_ids = {item.user_id for item in db.scalars(select(ApprovalPositionMember).where(ApprovalPositionMember.position_id == position.id)).all()}
    for user_id in sorted(source_ids - existing_ids):
        db.add(ApprovalPositionMember(position_id=position.id, user_id=user_id))
    db.flush()


QUERY_INDEX_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_users_department_status", "users", ("department_id", "employment_status")),
    ("ix_projects_status_updated", "projects", ("status", "updated_at", "id")),
    ("ix_projects_owner_status", "projects", ("owner_user_id", "status")),
    ("ix_projects_department_status", "projects", ("department_id", "status")),
    ("ix_projects_type_status", "projects", ("project_type", "status")),
    ("ix_config_options_category_active_sort", "config_options", ("category", "is_active", "sort_order", "id")),
    ("ix_config_options_parent_sort", "config_options", ("parent_id", "sort_order", "id")),
    ("ix_budget_templates_category_active_sort", "budget_item_templates", ("project_category", "is_active", "sort_order", "id")),
    ("ix_project_budget_items_project_sort", "project_budget_items", ("project_id", "is_active", "sort_order", "id")),
    ("ix_worklogs_user_date", "worklogs", ("user_id", "start_date", "id")),
    ("ix_worklogs_user_fill_date", "worklogs", ("user_id", "fill_date", "id")),
    ("ix_worklogs_project_status_date", "worklogs", ("project_id", "status", "start_date", "id")),
    ("ix_worklogs_status_date", "worklogs", ("status", "start_date", "id")),
    ("ix_worklogs_approver_status_submitted", "worklogs", ("approver_user_id", "status", "submitted_at")),
    ("ix_approval_tasks_approver_status", "approval_tasks", ("approver_user_id", "status", "submitted_at", "id")),
    ("ix_approval_tasks_worklog_version", "approval_tasks", ("worklog_id", "version", "id")),
    ("ix_notifications_status_created", "notifications", ("status", "created_at", "id")),
    ("ix_notifications_recipient_status", "notifications", ("recipient_user_id", "status", "created_at")),
    ("ix_audit_logs_object_created", "audit_logs", ("object_type", "object_id", "created_at", "id")),
    ("ix_contracts_project_type_status", "contracts", ("project_id", "contract_type", "status", "id")),
    ("ix_contracts_counterparty", "contracts", ("counterparty_type", "counterparty_id", "status")),
    ("ix_contracts_budget_item", "contracts", ("budget_item_id", "status")),
    ("ix_contract_stages_contract_sort", "contract_stages", ("contract_id", "status", "planned_date", "sort_order", "id")),
    ("ix_contract_stages_due", "contract_stages", ("planned_date", "status", "reminder_paused")),
    ("ix_receipts_project_status_date", "receipts", ("project_id", "status", "receipt_date", "id")),
    ("ix_receipts_contract_status", "receipts", ("contract_id", "status", "id")),
    ("ix_receipts_stage_status", "receipts", ("stage_id", "status", "id")),
    ("ix_payments_project_status_date", "payments", ("project_id", "status", "payment_date", "id")),
    ("ix_payments_contract_status", "payments", ("contract_id", "status", "id")),
    ("ix_payments_stage_status", "payments", ("stage_id", "status", "id")),
    ("ix_payments_budget_item_status", "payments", ("budget_item_id", "status")),
    ("ix_receipt_plans_month_project", "receipt_plans", ("period_month", "project_id", "contract_id")),
    ("ix_payment_plans_month_project", "payment_plans", ("period_month", "project_id", "status", "id")),
    ("ix_payment_plans_handler_month", "payment_plans", ("handler_user_id", "period_month", "status")),
    ("ix_payment_plans_source", "payment_plans", ("source_type", "contract_id", "contract_stage_id")),
    ("ix_project_ledger_project_type", "project_ledger_entries", ("project_id", "entry_type", "created_at", "id")),
    ("ix_project_ledger_source", "project_ledger_entries", ("source_type", "source_id", "entry_type")),
    ("ix_project_ledger_budget_item", "project_ledger_entries", ("budget_item_id", "entry_type")),
    ("ix_system_notifications_status_created", "system_notifications", ("status", "created_at", "id")),
    ("ix_system_notifications_recipient_status", "system_notifications", ("recipient_user_id", "status", "created_at")),
    ("ix_system_notifications_source", "system_notifications", ("source_type", "source_id", "notification_type")),
    ("ix_workflow_instances_document", "workflow_instances", ("document_type", "document_id", "status")),
    ("ix_workflow_instances_applicant_status", "workflow_instances", ("applicant_user_id", "status", "submitted_at")),
    ("ix_workflow_tasks_assignee_status", "workflow_tasks", ("assignee_user_id", "status", "created_at", "id")),
    ("ix_workflow_tasks_instance_status", "workflow_tasks", ("workflow_instance_id", "status", "node_sequence", "id")),
    ("ix_workflow_actions_instance_created", "workflow_action_logs", ("workflow_instance_id", "created_at", "id")),
    ("ix_project_expenses_project_status", "project_expenses", ("project_id", "status", "updated_at", "id")),
    ("ix_project_expenses_applicant_status", "project_expenses", ("applicant_user_id", "status", "occurred_on", "id")),
    ("ix_project_expenses_type_status", "project_expenses", ("expense_type", "status", "occurred_on", "id")),
    ("ix_project_expenses_budget_item_status", "project_expenses", ("budget_item_id", "status")),
    ("ix_project_expense_attachments_expense", "project_expense_attachments", ("expense_id", "id")),
    ("ix_project_expense_payments_expense_status", "project_expense_payments", ("expense_id", "status", "payment_date")),
    ("ix_project_cost_entries_project_kind_status", "project_cost_entries", ("project_id", "entry_kind", "status", "id")),
    ("ix_project_cost_entries_applicant_status", "project_cost_entries", ("applicant_user_id", "status", "created_at", "id")),
    ("ix_project_cost_entries_month_kind", "project_cost_entries", ("accounting_month", "entry_kind", "status")),
    ("ix_project_cost_entries_budget_item_status", "project_cost_entries", ("budget_item_id", "status")),
)


def ensure_query_indexes(connection) -> None:
    """Create read-path indexes for existing SQLite databases without changing business data."""
    inspector = inspect(engine)
    existing_columns_by_table: dict[str, set[str]] = {}
    for _, table, _ in QUERY_INDEX_SPECS:
        if table not in existing_columns_by_table:
            if not inspector.has_table(table):
                existing_columns_by_table[table] = set()
            else:
                existing_columns_by_table[table] = {column["name"] for column in inspector.get_columns(table)}
    for index_name, table, columns in QUERY_INDEX_SPECS:
        existing_columns = existing_columns_by_table.get(table, set())
        if not existing_columns or not set(columns).issubset(existing_columns):
            continue
        column_sql = ", ".join(f'"{column}"' for column in columns)
        connection.execute(text(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table}" ({column_sql})'))


def ensure_worklogs_project_nullable(connection) -> None:
    """旧 SQLite 库中 worklogs.project_id 曾是 NOT NULL；非项目工时需要允许为空。"""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if not inspector.has_table("worklogs"):
        return
    columns = inspector.get_columns("worklogs")
    project_column = next((column for column in columns if column["name"] == "project_id"), None)
    if not project_column or project_column.get("nullable", True):
        return

    target_columns: list[tuple[str, str, str]] = [
        ("id", "INTEGER PRIMARY KEY", "id"),
        ("user_id", "INTEGER NOT NULL", "user_id"),
        ("user_name_snapshot", "VARCHAR(100) NOT NULL", "user_name_snapshot"),
        ("project_id", "INTEGER", "project_id"),
        ("project_name_snapshot", "VARCHAR(300) NOT NULL", "COALESCE(project_name_snapshot, '非项目工时')"),
        ("stage", "VARCHAR(40) NOT NULL", "stage"),
        ("work_type", "VARCHAR(40) NOT NULL", "work_type"),
        ("work_status", "VARCHAR(40) NOT NULL", "work_status"),
        ("fill_date", "DATE", "fill_date"),
        ("start_date", "DATE NOT NULL", "start_date"),
        ("end_date", "DATE NOT NULL", "end_date"),
        ("quantity", "NUMERIC(10, 2) NOT NULL", "quantity"),
        ("unit", "VARCHAR(10) NOT NULL DEFAULT 'DAY'", "COALESCE(unit, 'DAY')"),
        ("description", "TEXT NOT NULL", "description"),
        ("status", "VARCHAR(20) NOT NULL DEFAULT 'DRAFT'", "COALESCE(status, 'DRAFT')"),
        ("timesheet_id", "INTEGER", "timesheet_id"),
        ("approver_user_id", "INTEGER", "approver_user_id"),
        ("approver_name_snapshot", "VARCHAR(100)", "approver_name_snapshot"),
        ("submitted_at", "DATETIME", "submitted_at"),
        ("approved_at", "DATETIME", "approved_at"),
        ("rejection_reason", "TEXT", "rejection_reason"),
        ("approval_comment", "TEXT", "approval_comment"),
        ("approval_version", "INTEGER NOT NULL DEFAULT 0", "COALESCE(approval_version, 0)"),
        ("approval_flow_type", "VARCHAR(40)", "approval_flow_type"),
        ("converted_from_project_id", "INTEGER", "converted_from_project_id"),
        ("converted_from_project_name", "VARCHAR(300)", "converted_from_project_name"),
        ("converted_at", "DATETIME", "converted_at"),
        ("converted_by", "INTEGER", "converted_by"),
        ("conversion_reason", "TEXT", "conversion_reason"),
        ("last_notified_at", "DATETIME", "last_notified_at"),
        ("created_at", "DATETIME NOT NULL", "COALESCE(created_at, datetime('now', '+8 hours'))"),
        ("updated_at", "DATETIME NOT NULL", "COALESCE(updated_at, datetime('now', '+8 hours'))"),
    ]
    existing = {column["name"] for column in columns}
    column_definitions = ", ".join(f'"{name}" {definition}' for name, definition, _ in target_columns)
    target_names = ", ".join(f'"{name}"' for name, _, _ in target_columns)
    source_values = ", ".join(expression if name in existing else "NULL" for name, _, expression in target_columns)

    connection.execute(text("PRAGMA foreign_keys=OFF"))
    connection.execute(text("DROP TABLE IF EXISTS worklogs_nullable_migration"))
    connection.execute(text(f"CREATE TABLE worklogs_nullable_migration ({column_definitions})"))
    connection.execute(text(f"INSERT INTO worklogs_nullable_migration ({target_names}) SELECT {source_values} FROM worklogs"))
    connection.execute(text("DROP TABLE worklogs"))
    connection.execute(text("ALTER TABLE worklogs_nullable_migration RENAME TO worklogs"))
    connection.execute(text("PRAGMA foreign_keys=ON"))


def upgrade_schema() -> None:
    """为现有 SQLite 数据库增量补齐字段，所有操作均可重复执行。"""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    # 成本分类已并入统一 8 项预算项，这些历史列随本次迁移整体下线。
    retired_cost_classification_columns = {
        "budget_item_templates": ["cost_major", "cost_minor", "cost_minor_options"],
        "project_budget_items": ["cost_major", "cost_minor", "cost_minor_options"],
        "contracts": ["cost_major_snapshot", "cost_minor_snapshot"],
        "payments": ["cost_major_snapshot", "cost_minor_snapshot"],
        "project_expenses": ["cost_major_snapshot", "cost_minor_snapshot"],
        "project_ledger_entries": ["cost_major_snapshot", "cost_minor_snapshot"],
        "project_cost_entries": ["cost_major_snapshot", "cost_minor_snapshot"],
    }
    # 人工成本已完全由「人工成本结转单」承担，日成本口径连同旧「人员成本」模块一并删除。
    retired_personnel_cost_columns = {
        "users": ["daily_cost"],
        "worklogs": ["daily_cost_snapshot", "cost_amount_snapshot"],
        "admin_permissions": ["can_manage_personnel_costs"],
    }
    additions = {
        # daily_cost 等列已下线，见 retired_personnel_cost_columns。
        "users": [
            ("open_id", "VARCHAR(128)"),
            ("email", "VARCHAR(200)"),
            ("snapshot_at", "DATETIME"),
            ("supervisor_user_id", "INTEGER"),
            ("supervisor_name", "VARCHAR(100)"),
            ("supervisor_feishu_user_id", "VARCHAR(64)"),
        ],
        "departments": [
            ("parent_feishu_department_id", "VARCHAR(64)"),
            ("manager_user_id", "INTEGER"),
            ("manager_name", "VARCHAR(100)"),
        ],
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
            ("project_sub_category", "VARCHAR(80)"),
        ],
        "config_options": [
            ("parent_id", "INTEGER"),
            ("level", "INTEGER NOT NULL DEFAULT 1"),
            ("path", "VARCHAR(255)"),
            ("is_leaf", "BOOLEAN NOT NULL DEFAULT 1"),
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
            ("amount_without_tax", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
            ("tax_rate", "NUMERIC(8, 6) NOT NULL DEFAULT 0"),
            ("tax_amount", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
        ],
        "contracts": [
            ("budget_item_id", "INTEGER"),
            ("budget_item_name_snapshot", "VARCHAR(120)"),
            ("cost_major_snapshot", "VARCHAR(120)"),
            ("cost_minor_snapshot", "VARCHAR(120)"),
            ("amount_without_tax", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
            ("tax_rate", "NUMERIC(8, 6) NOT NULL DEFAULT 0"),
            ("tax_amount", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
        ],
        "receipts": [
            ("amount_without_tax", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
            ("tax_rate", "NUMERIC(8, 6) NOT NULL DEFAULT 0"),
            ("tax_amount", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
        ],
        "payments": [
            ("current_workflow_instance_id", "INTEGER"),
            ("version", "INTEGER NOT NULL DEFAULT 1"),
            ("budget_item_id", "INTEGER"),
            ("budget_item_name_snapshot", "VARCHAR(120)"),
            ("cost_major_snapshot", "VARCHAR(120)"),
            ("cost_minor_snapshot", "VARCHAR(120)"),
            ("amount_without_tax", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
            ("tax_rate", "NUMERIC(8, 6) NOT NULL DEFAULT 0"),
            ("tax_amount", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
        ],
        "project_expenses": [
            ("budget_item_id", "INTEGER"),
            ("budget_item_name_snapshot", "VARCHAR(120)"),
            ("cost_major_snapshot", "VARCHAR(120)"),
            ("cost_minor_snapshot", "VARCHAR(120)"),
            ("amount_without_tax", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
            ("tax_rate", "NUMERIC(8, 6) NOT NULL DEFAULT 0"),
            ("tax_amount", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
        ],
        "project_cost_entries": [
            ("amount_without_tax", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
            ("tax_rate", "NUMERIC(8, 6) NOT NULL DEFAULT 0"),
            ("tax_amount", "NUMERIC(14, 2) NOT NULL DEFAULT 0"),
            # v3.0.83：填报日期，新增结转单由服务端写当天，历史单据升级时按创建日回填。
            ("fill_date", "DATE"),
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
            ("fill_date", "DATE"),
            ("approver_user_id", "INTEGER"),
            ("approver_name_snapshot", "VARCHAR(100)"),
            ("submitted_at", "DATETIME"),
            ("approved_at", "DATETIME"),
            ("rejection_reason", "TEXT"),
            ("approval_comment", "TEXT"),
            ("approval_version", "INTEGER NOT NULL DEFAULT 0"),
            ("approval_flow_type", "VARCHAR(40)"),
            ("converted_from_project_id", "INTEGER"),
            ("converted_from_project_name", "VARCHAR(300)"),
            ("converted_at", "DATETIME"),
            ("converted_by", "INTEGER"),
            ("conversion_reason", "TEXT"),
            # daily_cost_snapshot / cost_amount_snapshot 已下线，见 retired_personnel_cost_columns。
            ("last_notified_at", "DATETIME"),
        ],
        "approval_tasks": [
            ("step_order", "INTEGER NOT NULL DEFAULT 1"),
            ("step_name", "VARCHAR(100)"),
            ("total_steps", "INTEGER NOT NULL DEFAULT 1"),
            ("flow_type", "VARCHAR(40)"),
            ("resolved_reason", "VARCHAR(200)"),
        ],
        "system_notifications": [
            ("retry_count", "INTEGER NOT NULL DEFAULT 0"),
        ],
        "notification_policies": [
            ("schedule_time", "VARCHAR(200)"),
            ("target_scope", "VARCHAR(20) NOT NULL DEFAULT 'ALL'"),
            ("target_ids", "TEXT"),
            ("only_unfilled", "BOOLEAN NOT NULL DEFAULT 1"),
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
        ensure_worklogs_project_nullable(connection)
        for table in ("contracts", "contract_stages", "receipts", "payments", "project_expenses", "project_cost_entries"):
            if not inspect(engine).has_table(table):
                continue
            existing = {column["name"] for column in inspect(engine).get_columns(table)}
            if {"amount", "amount_without_tax", "tax_rate", "tax_amount"}.issubset(existing):
                connection.execute(text(f"""
                    UPDATE {table}
                    SET amount_without_tax = amount,
                        tax_rate = 0,
                        tax_amount = 0
                    WHERE COALESCE(amount, 0) > 0
                      AND COALESCE(amount_without_tax, 0) = 0
                      AND COALESCE(tax_rate, 0) = 0
                      AND COALESCE(tax_amount, 0) = 0
                """))
        # v3.0.83：填报日期上线后，按单据统计口径把历史单据的填报日期回填为创建日，
        # 保证按填报日期查询与导出时历史数据不为空。
        if inspect(engine).has_table("project_cost_entries"):
            _fill_date_column = {column["name"] for column in inspect(engine).get_columns("project_cost_entries")}
            if "fill_date" in _fill_date_column and "created_at" in _fill_date_column:
                date_expression = "DATE(created_at)" if is_sqlite else "created_at::date"
                connection.execute(
                    text(
                        f"UPDATE project_cost_entries SET fill_date = {date_expression} "
                        "WHERE fill_date IS NULL AND created_at IS NOT NULL"
                    )
                )
        for table, columns in retired_cost_classification_columns.items():
            if not inspect(engine).has_table(table):
                continue
            existing = {column["name"] for column in inspect(engine).get_columns(table)}
            for name in columns:
                if name in existing:
                    connection.execute(text(f'ALTER TABLE "{table}" DROP COLUMN "{name}"'))
        for table, columns in retired_personnel_cost_columns.items():
            if not inspect(engine).has_table(table):
                continue
            existing = {column["name"] for column in inspect(engine).get_columns(table)}
            for name in columns:
                if name in existing:
                    connection.execute(text(f'ALTER TABLE "{table}" DROP COLUMN "{name}"'))
        # 成本分类树配置数据整体下线，只保留项目分类树。
        connection.execute(text("DELETE FROM config_options WHERE category IN ('cost_category', 'cost_sub_category')"))
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
        connection.execute(text("UPDATE worklogs SET fill_date = start_date WHERE fill_date IS NULL"))
        # v3.0.61 起人工成本改由财务在本系统内按项目 + 核算月份录入（project_cost_entries），
        # 工时只统计人天、不再按单天成本折算，因此这里不再回填工时成本快照，也不再补写
        # source_type='WORKLOG' 的 PERSONNEL_COST 流水。历史已生成的流水保留原样以便追溯。
        # 统一旧版本中文类型，避免历史项目无法匹配新的动态配置编码。
        connection.execute(text("UPDATE projects SET project_type = 'RND_PROJECT' WHERE project_type IN ('研发项目', '客户项目', '内部项目') OR project_type IS NULL OR project_type = ''"))
        connection.execute(text("UPDATE projects SET budget_cost = 0 WHERE budget_cost IS NULL"))
        connection.execute(text("UPDATE projects SET expense_budget = 0 WHERE expense_budget IS NULL"))
        connection.execute(text("UPDATE payments SET version = 1 WHERE version IS NULL OR version < 1"))
        # v3.0.61 合同付款由七级审批改为一级费用复核：历史在途单据挂到新状态并解绑旧流程实例，
        # 否则新复核入口的 can_approve 会因为仍挂着工作流实例而拒绝复核人处理。
        connection.execute(text("UPDATE workflow_tasks SET status = 'CLOSED' WHERE status = 'PENDING' AND workflow_instance_id IN (SELECT id FROM workflow_instances WHERE document_type = 'PAYMENT')"))
        connection.execute(text("UPDATE workflow_instances SET status = 'CLOSED', completed_at = datetime('now', '+8 hours') WHERE document_type = 'PAYMENT' AND status = 'RUNNING'"))
        connection.execute(text("UPDATE payments SET status = 'PENDING_REVIEW', current_workflow_instance_id = NULL WHERE status IN ('PENDING', 'PENDING_APPROVAL')"))
        # 旧项目类型已不再属于当前业务范围，配置记录也直接删除而非仅停用。
        connection.execute(text("DELETE FROM config_options WHERE category = 'project_type' AND (value IN ('研发项目', '客户项目', '内部项目', 'CUSTOMER_PROJECT', 'INTERNAL_PROJECT') OR label IN ('研发项目', '客户项目', '内部项目'))"))
        # v3.0.59 起项目分类改用 project_category / project_sub_category 两级树，扁平的 project_type 分类整体下线。
        connection.execute(text("DELETE FROM config_options WHERE category = 'project_type'"))
        ensure_query_indexes(connection)


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
        seed_work_calendar(db)
        seed_classification_trees(db)
        seed_budget_item_templates(db)
        seed_notification_policies(db)
        seed_rbac(db)
        seed_approval_workflows(db)
        disable_retired_menus(db)
        drop_retired_menu_grants(db)
        purge_deleted_menus(db)
        grant_cost_review_permissions(db)
        normalize_project_categories(db)
        ensure_all_project_budget_items(db)
        backfill_ledger_budget_snapshots(db)
        db.flush()
        if not demo_seed_enabled():
            repair_legacy_approval_tasks(db)
            reset_rbac_configuration(db)
            normalize_project_categories(db)
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
                item = Worklog(user_id=user.id, user_name_snapshot=user.name, project_id=project.id, project_name_snapshot=project.name, stage=stage, work_type="PROJECT", work_status="LOCAL", fill_date=today, start_date=today - timedelta(days=2), end_date=today - timedelta(days=2), quantity=quantity, unit="DAY", description=description, status=status, approved_at=now_local() if status == "APPROVED" else None)
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
    # 岗位制复核：费用复核岗位成员即使没有单独授权菜单，也应看到并处理费用复核。
    if user_id in {member.id for member in position_members(db, COST_REVIEW_POSITION_CODE)}:
        target = details.setdefault(
            COST_REVIEW_RESOURCE,
            {"actions": [], "scope_type": "ALL", "scope_department_id": None, "source_roles": []},
        )
        target["actions"] = sorted(
            set(target["actions"]) | {"VIEW", "APPROVE"},
            key=lambda action: RBAC_ACTIONS.index(action) if action in RBAC_ACTIONS else len(RBAC_ACTIONS),
        )
        if "费用复核岗位" not in target["source_roles"]:
            target["source_roles"].append("费用复核岗位")
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
        project_category_label=PROJECT_CATEGORY_LABELS.get(project.project_type, project.project_type),
        project_sub_category_label=project_sub_category_label(db, project.project_sub_category),
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


def worklog_scope_sets(db: Session, user: User, resource: str = "worklogs") -> tuple[set[int] | None, set[int] | None]:
    """返回工时数据范围：项目 ID 集合、非项目填报人 ID 集合；None 表示该维度不限制。"""
    if user.id in system_admin_user_ids(db):
        return None, None
    details = effective_permission_details(db, user.id)
    scope = details.get(resource) or details.get("projects")
    scope_type = str(scope.get("scope_type")) if scope else "OWNED_PROJECTS"
    if scope_type == "ALL":
        return None, None
    if scope_type == "SELF":
        return set(), {user.id}
    if scope_type == "OWNED_PROJECTS":
        return project_scope_ids(db, user, resource), {user.id}
    department_id = scope.get("scope_department_id") if scope else None
    if department_id:
        index = DepartmentIndex(db.scalars(select(Department)).all())
        department_ids = index.descendants(int(department_id))
        project_ids = {
            project.id
            for project in db.scalars(select(Project).where(Project.department_id.in_(department_ids), Project.status != "DELETED")).all()
        }
        user_ids = {
            scoped_user.id
            for scoped_user in db.scalars(select(User).where(User.department_id.in_(department_ids), User.employment_status == "ACTIVE")).all()
        }
        return project_ids, user_ids
    return set(), {user.id}


def worklog_in_scope(worklog: Worklog, project_ids: set[int] | None, user_ids: set[int] | None) -> bool:
    """判断一条工时是否落在已计算好的数据范围内。"""
    if project_ids is None and user_ids is None:
        return True
    if worklog.project_id:
        return (project_ids is None or worklog.project_id in project_ids) or (user_ids is not None and worklog.user_id in user_ids)
    return user_ids is None or worklog.user_id in user_ids


def ensure_worklog_in_scope(db: Session, user: User, worklog: Worklog, resource: str = "worklogs") -> None:
    """对单条工时执行数据范围校验，防止越权编辑/删除/下钻。"""
    project_ids, user_ids = worklog_scope_sets(db, user, resource)
    if not worklog_in_scope(worklog, project_ids, user_ids):
        raise HTTPException(403, "WORKLOG_OUT_OF_SCOPE")


def tax_amount_fields(amount: float | int | None, tax_rate: float | int | None = 0, amount_without_tax: float | int | None = None) -> dict[str, float]:
    """根据含税金额、税率和可选未税金额，统一计算未税金额与税额。

    现有 amount 字段在 v3.0.78 后统一解释为含税金额；旧请求不传未税金额时，
    后端按含税金额和税率自动补齐，保证旧接口兼容。
    """
    gross = round(float(amount or 0), 2)
    rate = max(float(tax_rate or 0), 0)
    if amount_without_tax is None:
        net = round(gross / (1 + rate), 2) if rate > 0 else gross
    else:
        net = round(float(amount_without_tax or 0), 2)
    tax = round(max(gross - net, 0), 2)
    return {"amount_without_tax": net, "tax_rate": round(rate, 6), "tax_amount": tax}


def apply_tax_amount_fields(target: object, amount: float | int | None, tax_rate: float | int | None = 0, amount_without_tax: float | int | None = None) -> None:
    """把统一税额计算结果写回 ORM 对象。"""
    fields = tax_amount_fields(amount, tax_rate, amount_without_tax)
    setattr(target, "amount_without_tax", fields["amount_without_tax"])
    setattr(target, "tax_rate", fields["tax_rate"])
    setattr(target, "tax_amount", fields["tax_amount"])


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
        amount_without_tax=float(contract.amount_without_tax or 0),
        tax_rate=float(contract.tax_rate or 0),
        tax_amount=float(contract.tax_amount or 0),
        budget_item_id=contract.budget_item_id,
        budget_item_name=contract.budget_item_name_snapshot,
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
    "contracts": ("合同编号", "合同名称", "项目名称", "合同类型", "往来单位名称", "合同含税金额"),
    "labor_costs": ("项目名称", "结转月份", "金额"),
}
# 导入资源 -> 权限项；人工成本结转沿用 labor_costs 菜单权限。
IMPORT_RESOURCE_PERMISSIONS: dict[str, str] = {
    "customers": "counterparties",
    "suppliers": "counterparties",
    "contracts": "contracts",
    "labor_costs": "labor_costs",
}
IMPORT_MONTH_PATTERN = re.compile(r"^(\d{4})\s*[-/.年]\s*(\d{1,2})\s*月?$")


def parse_import_month(value: str) -> str | None:
    """容错解析导入模板里的结转月份，返回 YYYY-MM。

    兼容 `2026-09` / `2026/9` / `2026年9月` / `202609`，以及 Excel 日期单元格被读成
    `2026-09-01` 或 `2026-09-01 00:00:00` 的情况。
    """
    raw = (value or "").strip()
    if not raw:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        raw = raw[:7]
    match = IMPORT_MONTH_PATTERN.match(raw)
    if not match:
        match = re.match(r"^(\d{4})(\d{2})$", raw)
        if not match:
            return None
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return f"{year:04d}-{month:02d}"


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
    physical_position_count = len(positions)
    if resource == "contracts" and "合同含税金额" not in positions and "合同金额" in positions:
        positions["合同含税金额"] = positions["合同金额"]
    for field in required_fields:
        if field not in positions:
            errors.append({"row": rows[0][0], "field": field, "message": "缺少此列"})
    if physical_position_count != len([header for header in headers if header]):
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
            amount = float(values["合同含税金额"])
            if not math.isfinite(amount) or amount < 0:
                raise ValueError
        except ValueError:
            if values["合同含税金额"]:
                errors.append({"row": row, "field": "合同含税金额", "message": "必须是大于等于 0 的数字"})
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


def _validate_labor_cost_import(db: Session, user: User, records: list[dict[str, object]], errors: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """校验人工成本结转导入：项目必须在数据范围内且名称唯一，月份与金额需可解析。"""
    project_ids = project_scope_ids(db, user, "labor_costs")
    projects: dict[str, list[Project]] = defaultdict(list)
    for item in db.scalars(select(Project).where(Project.status != "DELETED")).all():
        if project_ids is None or item.id in project_ids:
            projects[item.name].append(item)
    existing_keys = {
        (int(project_id), month)
        for project_id, month in db.execute(
            select(ProjectCostEntry.project_id, ProjectCostEntry.accounting_month).where(
                ProjectCostEntry.entry_kind == "PERSONNEL_COST",
                ProjectCostEntry.status != "REVERSED",
            )
        ).all()
    }
    seen_keys: set[tuple[int, str]] = set()
    payloads: list[dict[str, object]] = []
    for record in records:
        row = int(record["row"])
        values = {field: str(record.get(field, "")).strip() for field in IMPORT_REQUIRED_FIELDS["labor_costs"]}
        row_has_error = False
        for field in IMPORT_REQUIRED_FIELDS["labor_costs"]:
            if not values[field]:
                errors.append({"row": row, "field": field, "message": "不能为空"})
                row_has_error = True
        matching_projects = projects.get(values["项目名称"], [])
        if values["项目名称"] and not matching_projects:
            errors.append({"row": row, "field": "项目名称", "message": "未找到匹配的项目名称或项目不在当前数据范围，请修正后重新导入"})
            row_has_error = True
        elif len(matching_projects) > 1:
            errors.append({"row": row, "field": "项目名称", "message": "匹配到多个同名项目，请先保证项目名称唯一后重新导入"})
            row_has_error = True
        month = parse_import_month(values["结转月份"])
        if values["结转月份"] and not month:
            errors.append({"row": row, "field": "结转月份", "message": "请填写 2026-09 这样的年月"})
            row_has_error = True
        amount_text = str(record.get("金额", "")).strip().replace(",", "").replace("¥", "").replace("￥", "")
        try:
            amount = float(amount_text)
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError
        except ValueError:
            if amount_text:
                errors.append({"row": row, "field": "金额", "message": "必须是大于 0 的数字"})
            row_has_error = True
            amount = 0
        key = (matching_projects[0].id, month or "") if matching_projects and month else None
        if key and not row_has_error:
            if key in existing_keys or key in seen_keys:
                errors.append({"row": row, "field": "项目名称", "message": f"该项目已存在 {key[1]} 的人工成本结转单，如需追加请先调整台账"})
                row_has_error = True
        if not row_has_error and key:
            seen_keys.add(key)
            payloads.append({
                "row": row,
                "project_id": key[0],
                "accounting_month": key[1],
                "amount": round(amount, 2),
                "description": str(record.get("备注", "")).strip() or "批量导入",
            })
    return payloads, errors


def create_labor_cost_entries_from_import(db: Session, user: User, payloads: list[dict[str, object]], submit: bool = False) -> list[ProjectCostEntry]:
    """把导入校验通过的明细写成人工成本结转单；税额恒为 0，填报日期取当天。"""
    department_index = DepartmentIndex(db.scalars(select(Department)).all())
    created: list[ProjectCostEntry] = []
    for payload in payloads:
        project_id = int(payload["project_id"])
        ensure_cost_entry_scope(db, user, project_id, "PERSONNEL_COST")
        budget_item = resolve_cost_entry_budget_item(db, "PERSONNEL_COST", project_id, None)
        entry = ProjectCostEntry(
            cost_no=next_document_no(db, ProjectCostEntry, PROJECT_COST_KIND_PREFIXES["PERSONNEL_COST"]),
            entry_kind="PERSONNEL_COST",
            project_id=project_id,
            applicant_user_id=user.id,
            applicant_name=user.name,
            applicant_department_name=department_index.path(user.department_id),
            amount=float(payload["amount"]),
            occurred_on=None,
            accounting_month=str(payload["accounting_month"]),
            fill_date=today_local(),
            description=str(payload.get("description") or "批量导入")[:2000] or None,
            status="DRAFT",
            version=1,
        )
        apply_tax_amount_fields(entry, entry.amount, 0, entry.amount)
        apply_cost_entry_snapshot(entry, budget_item)
        db.add(entry)
        db.flush()
        audit(db, "project_cost_entry", entry.id, "CREATE", user.id, None, "DRAFT", f"人工成本结转导入 · {project_id}")
        if submit:
            mark_cost_entry_submitted(db, entry, user)
        db.flush()
        created.append(entry)
    return created


async def _prepare_import(resource: str, file: UploadFile, db: Session, user: User) -> tuple[dict[str, object], list[dict[str, object]]]:
    """读取并校验导入文件，返回预览和可直接写入的字段。"""
    filename, rows = await _read_import_file(file)
    records, errors = _import_records(resource, rows)
    if resource in {"customers", "suppliers"}:
        payloads, errors = _validate_counterparty_import(db, resource, records, errors)
    elif resource == "labor_costs":
        payloads, errors = _validate_labor_cost_import(db, user, records, errors)
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
        amount_without_tax=float(stage.amount_without_tax or 0),
        tax_rate=float(stage.tax_rate or 0),
        tax_amount=float(stage.tax_amount or 0),
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


def receipt_view(db: Session, receipt: Receipt, viewer_id: int | None = None) -> ReceiptView:
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
        amount_without_tax=float(receipt.amount_without_tax or 0),
        tax_rate=float(receipt.tax_rate or 0),
        tax_amount=float(receipt.tax_amount or 0),
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
        can_withdraw=bool(viewer_id and receipt.status == "PENDING" and receipt.submitted_by == viewer_id),
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
        amount_without_tax=float(payment.amount_without_tax or 0),
        tax_rate=float(payment.tax_rate or 0),
        tax_amount=float(payment.tax_amount or 0),
        payment_date=payment.payment_date,
        payee_name=payment.payee_name,
        payee_bank_name=payment.payee_bank_name,
        payee_bank_account=payment.payee_bank_account,
        budget_item_id=payment.budget_item_id,
        budget_item_name=payment.budget_item_name_snapshot,
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
            and (
                (payment.status == "PENDING" and "cash_approval" in user_admin_permissions(db, viewer_id))
                or (
                    payment.status == "PENDING_REVIEW"
                    and (
                        "APPROVE" in effective_permission_details(db, viewer_id).get(COST_REVIEW_RESOURCE, {}).get("actions", [])
                        or any(member.id == viewer_id for member in position_members(db, COST_REVIEW_POSITION_CODE))
                    )
                )
            )
        ),
        can_withdraw=bool(viewer_id and payment.status == "PENDING_REVIEW" and payment.submitted_by == viewer_id),
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


def next_project_code(db: Session, project_type: str) -> str:
    """新增项目未填写编码时，按项目大类生成唯一项目编号。"""
    prefix = "RND" if project_budget_category(project_type) == "RND_PROJECT" else "BIZ"
    date_part = f"{now_local():%Y%m%d}"
    pattern = f"{prefix}-{date_part}-%"
    existing_codes = set(db.scalars(select(Project.code).where(Project.code.like(pattern))).all())
    sequence = 1
    while True:
        code = f"{prefix}-{date_part}-{sequence:04d}"
        if code not in existing_codes and not db.scalar(select(Project.id).where(Project.code == code)):
            return code
        sequence += 1


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
            Payment.status.in_(("PENDING", "PENDING_APPROVAL", "PENDING_REVIEW", "APPROVED")),
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


def reversal_target_types(rows: list[ProjectLedgerEntry]) -> dict[int, str]:
    """把冲销流水归回被冲销的原始类型，便于人工成本与项目费用分别按净额口径统计。

    优先读取 `reversal_of_id` 指向的原始流水类型；历史数据没有关联时按 `source_type` 回退。
    """
    kind_by_id = {row.id: row.entry_type for row in rows}
    targets: dict[int, str] = {}
    for row in rows:
        if row.entry_type != "REVERSAL":
            continue
        target = kind_by_id.get(row.reversal_of_id) if row.reversal_of_id else None
        if not target:
            if row.source_type == "PAYMENT":
                target = "PAYMENT"
            elif row.source_type == "PROJECT_EXPENSE":
                target = "PROJECT_EXPENSE_COST"
            else:
                target = "PERSONNEL_COST"
        targets[row.id] = target
    return targets


def project_analysis_view(db: Session, project: Project, as_of: date) -> ProjectAnalysisView:
    """组装单项目经营分析，统一返回成本、合同阶段、结项风险和可下钻来源。"""
    finance = project_finance_summary(db, project, as_of=as_of)
    project_detail = project_view(db, project)
    approved_days = float(db.scalar(select(func.coalesce(func.sum(Worklog.quantity), 0)).where(Worklog.project_id == project.id, Worklog.status.in_(("APPROVED", "LOCKED")))) or 0)
    ledger_rows = db.scalars(select(ProjectLedgerEntry).where(ProjectLedgerEntry.project_id == project.id)).all()
    reversal_targets = reversal_target_types(ledger_rows)
    personnel_cost = 0.0
    expense_cost = 0.0
    for ledger_row in ledger_rows:
        amount = float(ledger_row.amount or 0)
        if ledger_row.entry_type == "PERSONNEL_COST":
            personnel_cost += amount
        elif ledger_row.entry_type == "PROJECT_EXPENSE_COST":
            expense_cost += amount
        elif ledger_row.entry_type == "REVERSAL" and reversal_targets.get(ledger_row.id) == "PERSONNEL_COST":
            personnel_cost -= amount
        elif ledger_row.entry_type == "REVERSAL" and reversal_targets.get(ledger_row.id) == "PROJECT_EXPENSE_COST":
            expense_cost -= amount
    personnel_cost = round(max(personnel_cost, 0), 2)
    contract_cost = round(float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.project_id == project.id, Payment.status == "APPROVED")) or 0), 2)
    expense_cost = round(max(expense_cost, 0), 2)
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
            elif reversal_targets.get(entry.id) == "PROJECT_EXPENSE_COST":
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
    pending_payment_amount = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.project_id == project.id, Payment.status.in_(("PENDING", "PENDING_APPROVAL", "PENDING_REVIEW")))) or 0)
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


def resolve_project_classification(db: Session, project_type: str | None, sub_category: str | None) -> tuple[str, str | None]:
    """校验并归一并项目大类与小类；小类必须属于所选大类。"""
    major, derived_sub = resolve_project_category(project_type)
    raw_sub = (sub_category or "").strip() or None
    if raw_sub is None:
        return major, derived_sub
    major_option = db.scalar(select(ConfigOption).where(ConfigOption.category == "project_category", ConfigOption.value == major))
    minor_option = db.scalar(select(ConfigOption).where(ConfigOption.category == "project_sub_category", ConfigOption.value == raw_sub, ConfigOption.is_active.is_(True)))
    if not minor_option or not major_option or minor_option.parent_id != major_option.id:
        raise HTTPException(400, "INVALID_PROJECT_SUB_CATEGORY")
    return major, raw_sub


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
    """已退役：v3.0.61 起工时不再折算人员成本，人工成本由财务录入。

    保留函数签名只为兼容历史调用点，既不回填工时成本快照，也不创建任何经营流水。
    """
    return 0


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


def cash_approval_detail_url(source_type: str, source_id: int) -> str:
    """生成收付款审批卡片的系统内直达地址，避免飞书按钮只打开首页。"""
    base = os.getenv("SYSTEM_PUBLIC_URL", "http://192.168.112.188:8088").rstrip("/")
    page_map = {
        "receipt": "receiptDetail",
        "payment": "paymentDetail",
    }
    page = page_map.get(source_type)
    return f"{base}/?page={page}&id={source_id}" if page else base


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
    resend_sent: bool = False,
) -> int:
    """向出纳审批人发送待审批提醒；正式重新提交时允许覆盖已发送记录再次推送。"""
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
        if notification and notification.status == "SENT" and not resend_sent:
            continue
        result = feishu.notify_cash_approval_submitted(
            recipient.name,
            submitter_name,
            document_type_label,
            serial_no,
            project_name,
            amount,
            cash_approval_detail_url(source_type, source_id),
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
                select(Payment).where(Payment.project_id == project.id, Payment.status.in_(("PENDING", "PENDING_APPROVAL", "PENDING_REVIEW")))
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


def parse_reminder_times(raw: str | None) -> list[str]:
    """解析提醒时刻配置；支持“09:00,17:30”这类多时刻写法，非法片段直接丢弃。"""
    slots: list[str] = []
    for piece in (raw or "").replace("；", ",").replace("，", ",").replace("：", ":").replace(" ", "").split(","):
        if not piece:
            continue
        try:
            hour_text, minute_text = piece.split(":")
            hour, minute = int(hour_text), int(minute_text)
        except ValueError:
            continue
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            slot = f"{hour:02d}:{minute:02d}"
            if slot not in slots:
                slots.append(slot)
    return slots


def is_statutory_workday(db: Session, day: date) -> bool:
    """判断指定日期是否国家法定工作日；日历覆盖优先，未配置时回退到周一至周五。"""
    override = db.scalar(select(WorkCalendarDay).where(WorkCalendarDay.calendar_date == day))
    if override:
        return override.day_type == "WORKDAY"
    return day.weekday() in WORKDAY_WEEKDAYS


def worklog_workday_count(db: Session, start_date: date, end_date: date) -> int:
    """计算包含首尾日期的国家法定工作日数量；调休上班日计入，法定假日排除。"""
    if end_date < start_date:
        return 0
    return sum(
        is_statutory_workday(db, start_date + timedelta(days=offset))
        for offset in range((end_date - start_date).days + 1)
    )


@app.get("/api/v1/work-calendar", response_model=WorkCalendarList)
def list_work_calendar(
    start: date | None = None,
    end: date | None = None,
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> WorkCalendarList:
    """返回工作日历覆盖项；未返回的日期由前端按周一至周五兜底。"""
    current_user(db, x_demo_user_id)
    start_date = start or date(today_local().year, 1, 1)
    end_date = end or date(today_local().year, 12, 31)
    if start_date > end_date:
        raise HTTPException(400, "INVALID_DATE_RANGE")
    if (end_date - start_date).days > 1100:
        raise HTTPException(400, "DATE_RANGE_TOO_LARGE")
    rows = db.scalars(
        select(WorkCalendarDay)
        .where(WorkCalendarDay.calendar_date >= start_date, WorkCalendarDay.calendar_date <= end_date)
        .order_by(WorkCalendarDay.calendar_date)
    ).all()
    return WorkCalendarList(items=[WorkCalendarDayView.model_validate(item) for item in rows])


@app.get("/api/v1/admin/work-calendar", response_model=WorkCalendarList)
def list_admin_work_calendar(
    year: int | None = Query(default=None, ge=2000, le=2100),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> WorkCalendarList:
    """基础配置中的工作日历覆盖项列表；未列出的日期按周一至周五默认规则处理。"""
    require_access(db, "configuration", "VIEW", x_demo_user_id)
    target_year = year or today_local().year
    start_date = date(target_year, 1, 1)
    end_date = date(target_year, 12, 31)
    rows = db.scalars(
        select(WorkCalendarDay)
        .where(WorkCalendarDay.calendar_date >= start_date, WorkCalendarDay.calendar_date <= end_date)
        .order_by(WorkCalendarDay.calendar_date)
    ).all()
    return WorkCalendarList(items=[WorkCalendarDayView.model_validate(item) for item in rows])


@app.put("/api/v1/admin/work-calendar/{calendar_date}", response_model=WorkCalendarDayView)
def upsert_admin_work_calendar_day(
    calendar_date: date,
    payload: WorkCalendarDayUpsert,
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> WorkCalendarDayView:
    """新增或更新某一天的国家工作日历覆盖项。"""
    require_access(db, "configuration", "EDIT", x_demo_user_id)
    item = db.scalar(select(WorkCalendarDay).where(WorkCalendarDay.calendar_date == calendar_date))
    if not item:
        item = WorkCalendarDay(calendar_date=calendar_date, day_type=payload.day_type, name=payload.name.strip(), source=(payload.source or "").strip() or None, is_builtin=False)
        db.add(item)
    else:
        item.day_type = payload.day_type
        item.name = payload.name.strip()
        item.source = (payload.source or "").strip() or None
        item.is_builtin = False if not item.is_builtin else item.is_builtin
    db.commit()
    db.refresh(item)
    return WorkCalendarDayView.model_validate(item)


@app.delete("/api/v1/admin/work-calendar/{calendar_date}")
def delete_admin_work_calendar_day(
    calendar_date: date,
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """删除某一天的覆盖项；删除后该日期回退到默认周一至周五规则。"""
    require_access(db, "configuration", "DELETE", x_demo_user_id)
    item = db.scalar(select(WorkCalendarDay).where(WorkCalendarDay.calendar_date == calendar_date))
    if not item:
        raise HTTPException(404, "WORK_CALENDAR_DAY_NOT_FOUND")
    if item.is_builtin:
        raise HTTPException(400, "BUILTIN_WORK_CALENDAR_DELETE_FORBIDDEN")
    db.delete(item)
    db.commit()
    return {"deleted": True, "calendar_date": calendar_date.isoformat()}


def worklog_fill_reminder_due(db: Session, policy: NotificationPolicy, now: datetime) -> str | None:
    """判断当前时刻是否命中填报提醒；非国家工作日不提醒。"""
    if not is_statutory_workday(db, now.date()):
        return None
    slots = parse_reminder_times(policy.schedule_time) or parse_reminder_times(WORKLOG_FILL_REMINDER_DEFAULT_TIME)
    now_minutes = now.hour * 60 + now.minute
    for slot in slots:
        hour, minute = (int(part) for part in slot.split(":"))
        if 0 <= now_minutes - (hour * 60 + minute) < WORKLOG_FILL_REMINDER_MATCH_WINDOW_MINUTES:
            return slot
    return None


def _policy_id_list(value: str | None) -> list[int]:
    """读取策略里以 JSON 数组保存的 id 列表；数据损坏时按空集合处理。"""
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    result: list[int] = []
    for item in parsed:
        text = str(item).strip()
        if text.isdigit():
            result.append(int(text))
    return result


def expand_department_ids(db: Session, department_ids: list[int]) -> list[int]:
    """把选中的部门展开成包含所有下级部门的 id 集合。

    组织架构是飞书同步过来的多层树，只按 department_id 精确匹配会漏掉挂在
    子部门下的人（例如选了产品研发部，应用创新中心的人收不到提醒）。
    """
    if not department_ids:
        return []
    index = DepartmentIndex(list(db.scalars(select(Department)).all()))
    result: list[int] = []
    seen: set[int] = set()
    for department_id in department_ids:
        for item in index.descendants(department_id):
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result


def worklog_reminder_recipients(db: Session, policy: NotificationPolicy) -> list[User]:
    """按策略范围解析提醒对象；离职或停用人员不会收到提醒。

    指定部门时包含其全部下级部门，避免子部门成员收不到提醒。
    """
    scope = policy.target_scope or "ALL"
    if scope == "ALL":
        return list(db.scalars(select(User).where(User.employment_status == "ACTIVE").order_by(User.id)).all())
    raw_ids = _policy_id_list(policy.target_ids)
    if not raw_ids:
        return []
    ids = expand_department_ids(db, raw_ids) if scope == "DEPARTMENT" else raw_ids
    if not ids:
        return []
    query = select(User).where(User.employment_status == "ACTIVE")
    query = query.where(User.department_id.in_(ids) if scope == "DEPARTMENT" else User.id.in_(ids))
    return list(db.scalars(query.order_by(User.id)).all())


def previous_workday(db: Session, day: date) -> date:
    """返回指定日期之前最近的一个国家法定工作日。"""
    cursor = day - timedelta(days=1)
    while not is_statutory_workday(db, cursor):
        cursor -= timedelta(days=1)
    return cursor


def has_worklog_on(db: Session, user_id: int, day: date) -> bool:
    """判断某人在指定日期已有工时记录（含草稿）；区间填报按覆盖该日计算。"""
    return bool(
        db.scalar(
            select(Worklog.id)
            .where(Worklog.user_id == user_id, Worklog.start_date <= day, Worklog.end_date >= day)
            .limit(1)
        )
    )


def run_worklog_fill_reminder_scan_once(force: bool = False) -> dict[str, int]:
    """按策略在每个工作日的指定时刻提醒填报工时；同一时刻每人只发一次。"""
    db = SessionLocal()
    try:
        policy = notification_policy(db, WORKLOG_FILL_REMINDER_TYPE)
        if not policy or not policy.enabled:
            return {"scanned": 0, "sent": 0, "failed": 0, "skipped": 0}
        now = now_local()
        slot = f"manual{now:%H%M}" if force else worklog_fill_reminder_due(db, policy, now)
        if slot is None:
            return {"scanned": 0, "sent": 0, "failed": 0, "skipped": 0}
        today = today_local()
        recipients = worklog_reminder_recipients(db, policy)
        base = os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088").rstrip("/")
        channel = notification_policy_channel(db, WORKLOG_FILL_REMINDER_TYPE)
        weekday_label = "一二三四五六日"[today.weekday()]
        sent = 0
        failed = 0
        skipped = 0
        for user in recipients:
            key = f"worklog-fill-reminder:{user.id}:{today.isoformat()}:{slot}"
            if db.scalar(select(SystemNotification.id).where(SystemNotification.idempotency_key == key)):
                skipped += 1
                continue
            if policy.only_unfilled and has_worklog_on(db, user.id, today):
                skipped += 1
                continue
            result = feishu.notify_worklog_fill_reminder(
                user.name,
                f"{today.isoformat()}（周{weekday_label}）",
                f"{base}/?page=worklogs",
                user.open_id,
                channel=channel,
            )
            db.add(
                SystemNotification(
                    notification_type=WORKLOG_FILL_REMINDER_TYPE,
                    source_type="WORKLOG_REMINDER",
                    source_id=user.id,
                    recipient_user_id=user.id,
                    channel=channel or feishu.notification_mode,
                    idempotency_key=key,
                    status=result.status,
                    message_id=result.message_id,
                    error_message=result.error_message,
                    sent_at=now_local() if result.status == "SENT" else None,
                )
            )
            if result.status == "SENT":
                sent += 1
            else:
                failed += 1
        db.commit()
        return {"scanned": len(recipients), "sent": sent, "failed": failed, "skipped": skipped}
    finally:
        db.close()


def run_worklog_fill_reminder_t1_scan_once(force: bool = False) -> dict[str, int]:
    """T-1 补漏提醒：每个工作日按设定时刻提醒补填上一个工作日漏填的工时。

    与当天填报提醒的区别是只检查上一个工作日，用于兜住当天忘填的人；
    同一天同一时刻每个人只发一次，已补填的人会在下次扫描时自动跳过。
    """
    db = SessionLocal()
    try:
        policy = notification_policy(db, WORKLOG_FILL_REMINDER_T1_TYPE)
        if not policy or not policy.enabled:
            return {"scanned": 0, "sent": 0, "failed": 0, "skipped": 0}
        now = now_local()
        slot = f"manual{now:%H%M}" if force else worklog_fill_reminder_due(db, policy, now)
        if slot is None:
            return {"scanned": 0, "sent": 0, "failed": 0, "skipped": 0}
        target_day = previous_workday(db, today_local())
        recipients = worklog_reminder_recipients(db, policy)
        base = os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088").rstrip("/")
        channel = notification_policy_channel(db, WORKLOG_FILL_REMINDER_T1_TYPE)
        weekday_label = "一二三四五六日"[target_day.weekday()]
        sent = 0
        failed = 0
        skipped = 0
        for user in recipients:
            key = f"worklog-fill-reminder-t1:{user.id}:{target_day.isoformat()}:{slot}"
            if db.scalar(select(SystemNotification.id).where(SystemNotification.idempotency_key == key)):
                skipped += 1
                continue
            if policy.only_unfilled and has_worklog_on(db, user.id, target_day):
                skipped += 1
                continue
            result = feishu.notify_worklog_fill_reminder_t1(
                user.name,
                f"{target_day.isoformat()}（周{weekday_label}）",
                f"{base}/?page=worklogs",
                user.open_id,
                channel=channel,
            )
            db.add(
                SystemNotification(
                    notification_type=WORKLOG_FILL_REMINDER_T1_TYPE,
                    source_type="WORKLOG_REMINDER",
                    source_id=user.id,
                    recipient_user_id=user.id,
                    channel=channel or feishu.notification_mode,
                    idempotency_key=key,
                    status=result.status,
                    message_id=result.message_id,
                    error_message=result.error_message,
                    sent_at=now_local() if result.status == "SENT" else None,
                )
            )
            if result.status == "SENT":
                sent += 1
            else:
                failed += 1
        db.commit()
        return {"scanned": len(recipients), "sent": sent, "failed": failed, "skipped": skipped}
    finally:
        db.close()


def reminder_scan_loop() -> None:
    """后台守护任务：合同类提醒按配置间隔扫描（默认 10 分钟），填报提醒按分钟精度检查。"""
    interval = max(30, int(os.getenv("REMINDER_SCAN_INTERVAL_SECONDS", "600")))
    tick = min(interval, 60)
    last_stage_scan = 0.0
    while True:
        try:
            run_worklog_fill_reminder_scan_once()
        except Exception:
            pass
        try:
            run_worklog_fill_reminder_t1_scan_once()
        except Exception:
            pass
        try:
            if time.time() - last_stage_scan >= interval:
                run_stage_reminder_scan_once()
                last_stage_scan = time.time()
        except Exception:
            pass
        time.sleep(tick)


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


def is_project_work_type(work_type: str) -> bool:
    """判断工时类型是否必须关联项目；兼容旧 PROJECT 值。"""
    return work_type in PROJECT_WORK_TYPES


def project_category_for_work_type(work_type: str) -> str | None:
    """项目类工时限定可选择的项目大类；旧 PROJECT 不额外限定。"""
    return WORK_TYPE_PROJECT_CATEGORY.get(work_type)


def active_user_or_none(db: Session, user_id: int | None) -> User | None:
    """读取启用用户，避免审批任务派给离职/停用人员。"""
    if not user_id:
        return None
    user = db.get(User, user_id)
    return user if user and user.employment_status == "ACTIVE" else None


def supervisor_for_user(db: Session, user: User) -> User | None:
    """优先使用同步/手工维护的直属上级，其次按历史 manager_name 精确匹配。"""
    supervisor = active_user_or_none(db, user.supervisor_user_id)
    if supervisor and supervisor.id != user.id:
        return supervisor
    if user.supervisor_feishu_user_id:
        supervisor = db.scalar(
            select(User).where(
                or_(User.feishu_user_id == user.supervisor_feishu_user_id, User.open_id == user.supervisor_feishu_user_id),
                User.employment_status == "ACTIVE",
            )
        )
        if supervisor and supervisor.id != user.id:
            user.supervisor_user_id = supervisor.id
            user.supervisor_name = supervisor.name
            return supervisor
    name = (user.supervisor_name or user.manager_name or "").strip()
    if name:
        matches = db.scalars(select(User).where(User.name == name, User.employment_status == "ACTIVE")).all()
        if len(matches) == 1 and matches[0].id != user.id:
            user.supervisor_user_id = matches[0].id
            user.supervisor_name = matches[0].name
            return matches[0]
    return None


def department_manager_for_user(db: Session, user: User, *, prefer_market: bool = False) -> User:
    """解析非项目工时审批人：市场类优先市场部门负责人，其它按填报人部门负责人。"""
    department: Department | None = None
    if prefer_market:
        setting = db.scalar(select(ConfigOption).where(ConfigOption.category == "approval_setting", ConfigOption.value == "MARKET_DEPARTMENT_ID"))
        if setting and setting.label.strip().isdigit():
            department = db.get(Department, int(setting.label.strip()))
        configured = os.getenv("MARKET_DEPARTMENT_ID", "").strip()
        if not department and configured.isdigit():
            department = db.get(Department, int(configured))
        if not department:
            department = db.scalar(select(Department).where(Department.name.like("%市场%"), Department.is_active.is_(True)).order_by(Department.id))
    if not department and user.department_id:
        department = db.get(Department, user.department_id)
    manager = None
    while department and not manager:
        manager = active_user_or_none(db, department.manager_user_id)
        if not manager and department.manager_name:
            matches = db.scalars(select(User).where(User.name == department.manager_name, User.employment_status == "ACTIVE")).all()
            manager = matches[0] if len(matches) == 1 else None
        if manager:
            break
        department = db.scalar(select(Department).where(Department.feishu_department_id == department.parent_feishu_department_id)) if department.parent_feishu_department_id else None
    if not manager:
        raise HTTPException(400, "DEPARTMENT_MANAGER_MISSING")
    if manager.id == user.id:
        manager = supervisor_for_user(db, user)
        if not manager:
            raise HTTPException(400, "DEPARTMENT_MANAGER_SELF_NO_SUPERVISOR")
    return manager


def reroute_project_self_approver(
    db: Session,
    project: Project,
    submitter: User,
    *,
    self_role: str,
    preferred_project_approver: User | None = None,
) -> tuple[User, str]:
    """项目工时审批节点命中提交人本人时，按项目审批人/直属上级兜底转派。"""
    if preferred_project_approver and preferred_project_approver.id != submitter.id:
        return preferred_project_approver, f"{self_role}为本人，转项目审批人"
    rerouted = supervisor_for_user(db, submitter) or active_user_or_none(db, project.leader_user_id)
    if not rerouted or rerouted.id == submitter.id:
        raise HTTPException(400, "APPROVER_SELF_NO_LEADER")
    return rerouted, f"{self_role}为本人，转直属上级"


def worklog_project_for_payload(db: Session, work_type: str, project_id: int | None) -> Project | None:
    """按工时类型校验项目是否必填、可填报和项目大类是否匹配。"""
    if not is_project_work_type(work_type):
        return None
    if not project_id:
        raise HTTPException(400, "PROJECT_REQUIRED")
    project = db.get(Project, project_id)
    if not project or project.status == "DELETED" or not project.allow_worklog or project.status not in {"ACTIVE", "PRE_APPROVAL"}:
        raise HTTPException(400, "PROJECT_NOT_FILLABLE")
    expected_category = project_category_for_work_type(work_type)
    if expected_category and project.project_type != expected_category:
        raise HTTPException(400, "PROJECT_TYPE_NOT_MATCH_WORK_TYPE")
    return project


def worklog_approval_chain(db: Session, item: Worklog, submitter: User) -> list[tuple[User, str, str]]:
    """生成工时审批链；返回审批人、节点名称、解析原因。"""
    chain: list[tuple[User, str, str]] = []
    if is_project_work_type(item.work_type):
        project = db.get(Project, item.project_id) if item.project_id else None
        if not project:
            raise HTTPException(400, "PROJECT_REQUIRED")
        owner = active_user_or_none(db, project.owner_user_id)
        if not owner:
            raise HTTPException(400, "PROJECT_OWNER_MISSING")
        project_approver = approver_for_project(db, project)
        owner_reason = "项目负责人"
        if owner.id == submitter.id:
            owner, owner_reason = reroute_project_self_approver(
                db,
                project,
                submitter,
                self_role="项目负责人",
                preferred_project_approver=project_approver,
            )
        if project_approver.id == submitter.id:
            project_approver, reason = reroute_project_self_approver(
                db,
                project,
                submitter,
                self_role="项目审批人",
            )
        else:
            reason = "项目审批人"
        chain = [(owner, "项目负责人审批", owner_reason), (project_approver, "项目审批人审批", reason)]
    else:
        prefer_market = item.work_type in {"DEMO_PROMOTION_WORK", "MARKETING_WORK"}
        manager = department_manager_for_user(db, submitter, prefer_market=prefer_market)
        node_name = "市场部门负责人审批" if prefer_market else "部门负责人审批"
        chain = [(manager, node_name, node_name)]

    deduped: list[tuple[User, str, str]] = []
    seen: set[int] = set()
    for approver, step_name, reason in chain:
        if approver.id in seen:
            continue
        seen.add(approver.id)
        deduped.append((approver, step_name, reason))
    if not deduped:
        raise HTTPException(400, "APPROVER_MISSING")
    return deduped


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


def validate_worklog_quantity(db: Session, start_date: date, end_date: date, quantity: int) -> None:
    """校验工时天数为日期区间内的国家法定工作日数量，禁止手工填写不一致的天数。"""
    expected_days = worklog_workday_count(db, start_date, end_date)
    if expected_days == 0:
        raise HTTPException(400, "WORKLOG_NO_WORKDAY")
    if quantity != expected_days:
        raise HTTPException(400, "WORKLOG_QUANTITY_MISMATCH")


def validate_worklog_options(db: Session, stage: str, work_type: str, work_status: str) -> None:
    validate_config_option(db, "project_stage", stage)
    if work_type not in LEGACY_WORK_TYPE_VALUES:
        validate_config_option(db, "work_type", work_type)
    validate_config_option(db, "work_status", work_status)


def task_view(db: Session, task: ApprovalTask) -> ApprovalTaskView:
    """组装审批任务、工时快照和最近通知。"""
    item = db.get(Worklog, task.worklog_id)
    notification = db.scalar(select(Notification).where(Notification.approval_task_id == task.id).order_by(Notification.id.desc()))
    return ApprovalTaskView(id=task.id, worklog_id=task.worklog_id, version=task.version, serial_no=task.serial_no, submitter_user_id=task.submitter_user_id, approver_user_id=task.approver_user_id, step_order=task.step_order, step_name=task.step_name, total_steps=task.total_steps, flow_type=task.flow_type, resolved_reason=task.resolved_reason, status=task.status, comment=task.comment, submitted_at=task.submitted_at, processed_at=task.processed_at, processed_by=task.processed_by, worklog=worklog_view(item), notification=NotificationView.model_validate(notification) if notification else None)


def submit_item(db: Session, item: Worklog, user: User) -> ApprovalTaskView:
    """提交单条工时，生成独立审批版本并发送飞书提醒。"""
    if item.user_id != user.id:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    if item.status not in ["DRAFT", "REJECTED"]:
        raise HTTPException(409, "WORKLOG_READ_ONLY")
    validate_worklog_dates(db, item.user_id, item.start_date, item.end_date, item.id)
    validate_worklog_quantity(db, item.start_date, item.end_date, item.quantity)
    validate_worklog_options(db, item.stage, item.work_type, item.work_status)
    project = worklog_project_for_payload(db, item.work_type, item.project_id)
    chain = worklog_approval_chain(db, item, user)
    approver, step_name, resolved_reason = chain[0]
    old_status = item.status
    item.status = "PENDING_APPROVAL"
    item.approver_user_id = approver.id
    item.approver_name_snapshot = approver.name
    item.approval_version = max(item.approval_version, 0) + 1
    item.approval_flow_type = "PROJECT_TWO_STEP" if project else "DEPARTMENT_SINGLE"
    item.submitted_at = now_local()
    item.rejection_reason = None
    item.approval_comment = None
    db.flush()
    task = ApprovalTask(worklog_id=item.id, version=item.approval_version, serial_no=f"WL-{item.submitted_at:%Y%m%d}-{item.id:04d}-V{item.approval_version}-S1", submitter_user_id=item.user_id, approver_user_id=approver.id, step_order=1, step_name=step_name, total_steps=len(chain), flow_type=item.approval_flow_type, resolved_reason=resolved_reason, status="PENDING", submitted_at=item.submitted_at)
    db.add(task)
    db.flush()
    audit(db, "approval_task", task.id, "SUBMIT", user.id, old_status, "PENDING_APPROVAL")
    notify_task(db, task, item, approver, user)
    db.commit()
    db.refresh(task)
    return task_view(db, task)


def create_next_worklog_task(db: Session, item: Worklog, current_task: ApprovalTask, actor: User, comment: str | None) -> ApprovalTask | None:
    """当前节点通过后创建下一审批节点；没有下一节点时返回 None 表示流程结束。"""
    submitter = db.get(User, item.user_id)
    if not submitter:
        raise HTTPException(400, "SUBMITTER_MISSING")
    chain = worklog_approval_chain(db, item, submitter)
    next_index = current_task.step_order
    if next_index >= len(chain):
        return None
    approver, step_name, resolved_reason = chain[next_index]
    submitted_at = now_local()
    serial_date = item.submitted_at or submitted_at
    item.approver_user_id = approver.id
    item.approver_name_snapshot = approver.name
    next_task = ApprovalTask(
        worklog_id=item.id,
        version=current_task.version,
        serial_no=f"WL-{serial_date:%Y%m%d}-{item.id:04d}-V{current_task.version}-S{next_index + 1}",
        submitter_user_id=item.user_id,
        approver_user_id=approver.id,
        step_order=next_index + 1,
        step_name=step_name,
        total_steps=len(chain),
        flow_type=item.approval_flow_type,
        resolved_reason=resolved_reason,
        status="PENDING",
        submitted_at=submitted_at,
        comment=comment,
    )
    db.add(next_task)
    db.flush()
    notify_task(db, next_task, item, approver, submitter)
    audit(db, "approval_task", next_task.id, "SUBMIT_NEXT", actor.id, "APPROVED", "PENDING_APPROVAL", step_name)
    return next_task


def withdraw_worklog_item(db: Session, item: Worklog, user: User) -> WorklogView:
    """提交人撤回未审批工时：关闭当前待办任务，并把工时恢复为草稿。"""
    if item.user_id != user.id:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    if item.status != "PENDING_APPROVAL":
        raise HTTPException(409, "WORKLOG_NOT_WITHDRAWABLE")
    task = db.scalar(
        select(ApprovalTask)
        .where(ApprovalTask.worklog_id == item.id, ApprovalTask.status == "PENDING")
        .order_by(ApprovalTask.version.desc(), ApprovalTask.id.desc())
    )
    if not task:
        raise HTTPException(409, "WORKLOG_NOT_WITHDRAWABLE")
    processed_at = now_local()
    task.status = "WITHDRAWN"
    task.comment = "提交人撤回"
    task.processed_at = processed_at
    task.processed_by = user.id
    old_status = item.status
    item.status = "DRAFT"
    item.approver_user_id = None
    item.approver_name_snapshot = None
    item.submitted_at = None
    item.approved_at = None
    item.rejection_reason = None
    item.approval_comment = None
    item.last_notified_at = None
    audit(db, "approval_task", task.id, "WITHDRAW", user.id, old_status, "DRAFT", "提交人撤回，工时恢复草稿")
    db.commit()
    db.refresh(item)
    return worklog_view(item)


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
        user.supervisor_feishu_user_id = record.leader_user_id or user.supervisor_feishu_user_id
        user.supervisor_name = record.leader_name or user.supervisor_name
        user.snapshot_at = now_local()
    db.flush()
    users_by_feishu_id = {item.feishu_user_id: item for item in db.scalars(select(User)).all()}
    users_by_open_id = {item.open_id: item for item in db.scalars(select(User).where(User.open_id.is_not(None))).all()}
    users_by_name: dict[str, list[User]] = defaultdict(list)
    for item in db.scalars(select(User)).all():
        users_by_name[item.name].append(item)
    for record in directory_users:
        user = users_by_feishu_id.get(record.feishu_user_id) or (users_by_open_id.get(record.open_id) if record.open_id else None)
        if not user:
            continue
        supervisor = None
        if record.leader_user_id:
            supervisor = users_by_feishu_id.get(record.leader_user_id) or users_by_open_id.get(record.leader_user_id)
        if not supervisor and record.leader_name:
            matches = [item for item in users_by_name.get(record.leader_name, []) if item.employment_status == "ACTIVE"]
            supervisor = matches[0] if len(matches) == 1 else None
        if supervisor and supervisor.id != user.id:
            user.supervisor_user_id = supervisor.id
            user.supervisor_name = supervisor.name
    synced_at = now_local()
    db.add(OrgSyncLog(status="SUCCESS", mode=feishu.mode, user_count=len(directory_users), department_count=len(directory_departments), added_user_count=added_user_count, updated_user_count=updated_user_count, added_department_count=added_department_count, updated_department_count=updated_department_count, duration_ms=round((time.perf_counter() - started_at) * 1000)))
    db.commit()
    return OrgSyncView(status="SUCCESS", mode=feishu.mode, user_count=len(directory_users), department_count=len(directory_departments), synced_at=synced_at)


@app.get("/api/v1/admin/org-approval-config")
def get_org_approval_config(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """后台维护部门负责人和人员直属上级，供非项目工时审批兜底。"""
    require_access(db, "configuration", "VIEW", x_demo_user_id)
    index = DepartmentIndex(db.scalars(select(Department)).all())
    active_users = db.scalars(select(User).where(User.employment_status == "ACTIVE").order_by(User.name, User.id)).all()
    users_by_id = {item.id: item for item in active_users}
    departments = [
        {
            "id": item.id,
            "name": item.name,
            "path": index.path(item.id),
            "manager_user_id": item.manager_user_id,
            "manager_name": users_by_id.get(item.manager_user_id).name if item.manager_user_id in users_by_id else item.manager_name,
            "is_active": item.is_active,
        }
        for item in sorted(index.departments, key=lambda row: (index.path(row.id), row.id))
        if item.is_active
    ]
    market_setting = db.scalar(select(ConfigOption).where(ConfigOption.category == "approval_setting", ConfigOption.value == "MARKET_DEPARTMENT_ID"))
    market_department_id = int(market_setting.label) if market_setting and market_setting.label.strip().isdigit() else None
    users = [
        {
            "id": item.id,
            "name": item.name,
            "department_id": item.department_id,
            "department_path": index.path(item.department_id) if item.department_id else "未分配部门",
            "supervisor_user_id": item.supervisor_user_id,
            "supervisor_name": users_by_id.get(item.supervisor_user_id).name if item.supervisor_user_id in users_by_id else item.supervisor_name,
        }
        for item in active_users
    ]
    return {"departments": departments, "users": users, "market_department_id": market_department_id}


@app.patch("/api/v1/admin/org-approval-config/market-department")
def update_market_department(payload: dict[str, int | None], x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """设置观摩推广/市场营销工时的审批部门。"""
    actor = require_access(db, "configuration", "EDIT", x_demo_user_id)
    department_id = payload.get("department_id")
    department = db.get(Department, int(department_id)) if department_id else None
    if department_id and not department:
        raise HTTPException(404, "DEPARTMENT_NOT_FOUND")
    setting = db.scalar(select(ConfigOption).where(ConfigOption.category == "approval_setting", ConfigOption.value == "MARKET_DEPARTMENT_ID"))
    if not setting:
        setting = ConfigOption(category="approval_setting", value="MARKET_DEPARTMENT_ID", label=str(department.id if department else ""), sort_order=1, is_active=True, is_builtin=True)
        db.add(setting)
        db.flush()
    old_value = setting.label
    setting.label = str(department.id if department else "")
    audit(db, "config_option", setting.id or 0, "SET_MARKET_DEPARTMENT", actor.id, old_value, setting.label, department.name if department else "未设置")
    db.commit()
    return {"market_department_id": department.id if department else None, "market_department_name": department.name if department else None}


@app.patch("/api/v1/admin/departments/{department_id}/manager")
def update_department_manager(department_id: int, payload: dict[str, int | None], x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """设置部门负责人；负责人本人填报时会继续转直属上级审批。"""
    actor = require_access(db, "configuration", "EDIT", x_demo_user_id)
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(404, "DEPARTMENT_NOT_FOUND")
    manager_user_id = payload.get("manager_user_id")
    manager = active_user_or_none(db, int(manager_user_id)) if manager_user_id else None
    old_name = department.manager_name
    department.manager_user_id = manager.id if manager else None
    department.manager_name = manager.name if manager else None
    audit(db, "department", department.id, "SET_MANAGER", actor.id, old_name, department.manager_name, department.name)
    db.commit()
    return {"id": department.id, "manager_user_id": department.manager_user_id, "manager_name": department.manager_name}


@app.patch("/api/v1/admin/users/{user_id}/supervisor")
def update_user_supervisor(user_id: int, payload: dict[str, int | None], x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """设置人员直属上级，作为本人就是审批人时的转交人。"""
    actor = require_access(db, "configuration", "EDIT", x_demo_user_id)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "USER_NOT_FOUND")
    supervisor_user_id = payload.get("supervisor_user_id")
    supervisor = active_user_or_none(db, int(supervisor_user_id)) if supervisor_user_id else None
    if supervisor and supervisor.id == user.id:
        raise HTTPException(400, "SUPERVISOR_CANNOT_BE_SELF")
    old_name = user.supervisor_name
    user.supervisor_user_id = supervisor.id if supervisor else None
    user.supervisor_name = supervisor.name if supervisor else None
    user.supervisor_feishu_user_id = supervisor.feishu_user_id if supervisor else None
    audit(db, "user", user.id, "SET_SUPERVISOR", actor.id, old_name, user.supervisor_name, user.name)
    db.commit()
    return {"id": user.id, "supervisor_user_id": user.supervisor_user_id, "supervisor_name": user.supervisor_name}


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
    # 只回传启用的菜单；已下线的菜单界面上不可见，回传只会在保存时被判为非法。
    active_codes = {item.code for item in menus.values() if item.is_active}
    permission_rows = db.scalars(select(RolePermission).where(RolePermission.role_id == role.id).order_by(RolePermission.id)).all()
    permissions = [
        RolePermissionInput(menu_code=menus[item.menu_id].code, actions=_json_list(item.actions))
        for item in permission_rows
        if item.menu_id in menus and menus[item.menu_id].code in active_codes and _json_list(item.actions)
    ]
    scopes = [
        DataScopeInput(resource=item.resource, scope_type=item.scope_type, department_id=item.department_id)
        for item in db.scalars(select(RoleDataScope).where(RoleDataScope.role_id == role.id).order_by(RoleDataScope.id)).all()
        if item.resource in active_codes
    ]
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
            # 已下线菜单的残留授权直接丢弃，避免历史数据让整份权限无法保存。
            continue
        actions = sorted(set(item.actions), key=lambda value: RBAC_ACTIONS.index(value) if value in RBAC_ACTIONS else len(RBAC_ACTIONS))
        if any(action not in _json_list(menu.actions) for action in actions):
            raise HTTPException(400, "INVALID_MENU_ACTION")
        if actions:
            db.add(RolePermission(role_id=role.id, menu_id=menu.id, actions=json.dumps(actions)))
    db.query(RoleDataScope).filter(RoleDataScope.role_id == role.id).delete(synchronize_session=False)
    for scope in payload.scopes:
        if scope.resource not in menus:
            continue
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
        if scope.resource in RETIRED_MENU_SEED:
            continue
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


def classification_tree(db: Session, parent_category: str, active_only: bool) -> list[ClassificationNode]:
    """组装两棵层级分类树；上级为项目/成本大类，下级为对应小类。"""
    child_category = CLASSIFICATION_TREE_CATEGORIES[parent_category]
    parents_query = select(ConfigOption).where(ConfigOption.category == parent_category)
    children_query = select(ConfigOption).where(ConfigOption.category == child_category)
    if active_only:
        parents_query = parents_query.where(ConfigOption.is_active.is_(True))
        children_query = children_query.where(ConfigOption.is_active.is_(True))
    parents = db.scalars(parents_query.order_by(ConfigOption.sort_order, ConfigOption.id)).all()
    children = db.scalars(children_query.order_by(ConfigOption.sort_order, ConfigOption.id)).all()
    grouped: dict[int, list[ConfigOption]] = defaultdict(list)
    for child in children:
        if child.parent_id:
            grouped[child.parent_id].append(child)
    return [
        ClassificationNode(
            id=parent.id,
            value=parent.value,
            label=parent.label,
            parent_id=parent.parent_id,
            level=parent.level,
            path=parent.path,
            is_leaf=parent.is_leaf,
            is_active=parent.is_active,
            is_builtin=parent.is_builtin,
            sort_order=parent.sort_order,
            children=[
                ClassificationNode(
                    id=child.id,
                    value=child.value,
                    label=child.label,
                    parent_id=child.parent_id,
                    level=child.level,
                    path=child.path,
                    is_leaf=child.is_leaf,
                    is_active=child.is_active,
                    is_builtin=child.is_builtin,
                    sort_order=child.sort_order,
                )
                for child in grouped.get(parent.id, [])
            ],
        )
        for parent in parents
    ]


def classification_catalog(db: Session, active_only: bool) -> ClassificationCatalog:
    return ClassificationCatalog(
        project_category=classification_tree(db, "project_category", active_only),
    )


@app.get("/api/v1/config/classifications", response_model=ClassificationCatalog)
def list_classifications(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ClassificationCatalog:
    """读取启用中的项目分类树，供业务表单联动使用。"""
    current_user(db, x_demo_user_id)
    return classification_catalog(db, active_only=True)


@app.get("/api/v1/admin/config/classifications", response_model=ClassificationCatalog)
def list_admin_classifications(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ClassificationCatalog:
    """后台基础配置读取完整分类树，包含停用节点。"""
    require_admin_permission(db, "configuration", x_demo_user_id)
    return classification_catalog(db, active_only=False)


@app.get("/api/v1/admin/config/options", response_model=ConfigOptionCatalog)
def list_admin_config_options(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ConfigOptionCatalog:
    require_admin_permission(db, "configuration", x_demo_user_id)
    return config_catalog(db, active_only=False)


def config_option_usage_count(db: Session, option: ConfigOption) -> int:
    if option.category in ("project_category", "project_sub_category"):
        column = Project.project_type if option.category == "project_category" else Project.project_sub_category
        return int(db.scalar(select(func.count(Project.id)).where(column == option.value)) or 0)
    if option.category == "project_stage":
        return int(db.scalar(select(func.count(Worklog.id)).where(Worklog.stage == option.value)) or 0)
    if option.category == "work_type":
        return int(db.scalar(select(func.count(Worklog.id)).where(Worklog.work_type == option.value)) or 0)
    if option.category == "work_status":
        return int(db.scalar(select(func.count(Worklog.id)).where(Worklog.work_status == option.value)) or 0)
    if option.category == "project_status":
        return int(db.scalar(select(func.count(Project.id)).where(Project.status == option.value)) or 0)
    return 0


def resolve_classification_parent(db: Session, category: str, parent_id: int | None) -> tuple[int | None, int]:
    """校验分类项的层级归属，返回（上级 ID，层级）。"""
    parent_category = next((parent for parent, child in CLASSIFICATION_TREE_CATEGORIES.items() if child == category), None)
    if parent_category is None:
        if parent_id:
            raise HTTPException(400, "INVALID_CONFIG_PARENT")
        return None, 1
    if not parent_id:
        return None, 1
    parent = db.get(ConfigOption, parent_id)
    if not parent or parent.category != parent_category:
        raise HTTPException(400, "INVALID_CONFIG_PARENT")
    return parent.id, 2


def apply_classification_paths(db: Session, option: ConfigOption) -> None:
    """写入分类项的 path，并在其成为上级时更新 is_leaf。"""
    if option.parent_id:
        option.level = 2
        option.is_leaf = True
        option.path = f"/{option.parent_id}/{option.id}/"
        parent = db.get(ConfigOption, option.parent_id)
        if parent:
            parent.is_leaf = False
    else:
        option.level = 1
        option.is_leaf = True
        option.path = f"/{option.id}/"


@app.post("/api/v1/admin/config/options", response_model=ConfigOptionView, status_code=201)
def create_config_option(payload: ConfigOptionCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ConfigOptionView:
    admin = require_admin_permission(db, "configuration", x_demo_user_id)
    require_access(db, "configuration", "CREATE", x_demo_user_id)
    if payload.category not in CONFIG_CATEGORY_LABELS:
        raise HTTPException(400, "INVALID_CONFIG_CATEGORY")
    duplicate = db.scalar(select(ConfigOption).where(ConfigOption.category == payload.category, ConfigOption.value == payload.value))
    if duplicate:
        raise HTTPException(409, "CONFIG_OPTION_EXISTS")
    parent_id, level = resolve_classification_parent(db, payload.category, payload.parent_id)
    option = ConfigOption(category=payload.category, value=payload.value, label=payload.label, parent_id=parent_id, level=level, is_leaf=True, sort_order=payload.sort_order, is_active=payload.is_active, is_builtin=False)
    db.add(option)
    db.flush()
    apply_classification_paths(db, option)
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
    if "parent_id" in payload.model_fields_set:
        parent_id, _ = resolve_classification_parent(db, option.category, payload.parent_id)
        option.parent_id = parent_id
    old_label = option.label
    option.label = payload.label
    option.sort_order = payload.sort_order
    option.is_active = payload.is_active
    apply_classification_paths(db, option)
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
    child = db.scalar(select(ConfigOption.id).where(ConfigOption.parent_id == option.id))
    if child:
        raise HTTPException(409, "CONFIG_OPTION_HAS_CHILDREN")
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
    user = require_access(db, IMPORT_RESOURCE_PERMISSIONS[resource], "VIEW", x_demo_user_id)
    preview, _ = await _prepare_import(resource, file, db, user)
    return preview


async def _execute_import_endpoint(resource: str, file: UploadFile, x_demo_user_id: int | None, db: Session, submit: bool = False) -> dict[str, object]:
    """在完整校验通过后一次性导入，任一数据库异常都会整体回滚。"""
    user = require_access(db, IMPORT_RESOURCE_PERMISSIONS[resource], "CREATE", x_demo_user_id)
    preview, payloads = await _prepare_import(resource, file, db, user)
    errors = preview["errors"]
    if errors:
        raise HTTPException(422, detail=errors)
    try:
        if resource == "labor_costs":
            entries = create_labor_cost_entries_from_import(db, user, payloads, submit)
            db.commit()
            # 通知需要单据已落库，因此放在统一提交之后。
            for entry in entries:
                if entry.status != "PENDING_REVIEW":
                    continue
                project = db.get(Project, entry.project_id)
                notify_cost_review_submitted(
                    db,
                    source_type=f"project_cost_{entry.entry_kind.lower()}",
                    source_id=entry.id,
                    version=entry.version,
                    notification_type=PROJECT_COST_KIND_NOTIFICATIONS[entry.entry_kind],
                    document_label=PROJECT_COST_KIND_LABELS[entry.entry_kind],
                    serial_no=entry.cost_no,
                    project_name=project.name if project else "",
                    amount=float(entry.amount),
                    submitter_name=user.name,
                    page=PROJECT_COST_KIND_PAGES[entry.entry_kind],
                )
            db.commit()
            return {"resource": resource, "filename": preview["filename"], "imported": len(entries), "submitted": len(entries) if submit else 0, "skipped": 0}
        model = Customer if resource == "customers" else Supplier if resource == "suppliers" else Contract
        for payload in payloads:
            if resource == "contracts":
                item = Contract(**payload)
                apply_tax_amount_fields(item, payload.get("amount", 0), 0, payload.get("amount", 0))
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


@app.post("/api/v1/imports/labor_costs/preview")
async def preview_labor_cost_import(file: UploadFile = File(...), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """校验人工成本结转导入文件：项目名称、结转月份、金额。"""
    return await _preview_import_endpoint("labor_costs", file, x_demo_user_id, db)


@app.post("/api/v1/imports/labor_costs")
async def execute_labor_cost_import(
    file: UploadFile = File(...),
    submit: bool = Query(default=False, description="导入后是否直接提交费用复核"),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """批量写入人工成本结转单，全部校验通过才落库，任一异常整体回滚。"""
    return await _execute_import_endpoint("labor_costs", file, x_demo_user_id, db, submit)


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
    project_sub_category: str | None = None,
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
    if project_sub_category:
        query = query.where(Project.project_sub_category == project_sub_category)
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
    validate_config_option(db, "project_status", payload.status)
    major, sub_category = resolve_project_classification(db, payload.project_type, payload.project_sub_category)
    code = (payload.code or "").strip() or next_project_code(db, major)
    if db.scalar(select(Project).where(Project.code == code)):
        raise HTTPException(409, "PROJECT_CODE_EXISTS")
    department = active_org_department(db, payload.department_id)
    project = Project(code=code, name=payload.name, project_type=major, project_sub_category=sub_category, owner_name="", department_id=department.id, department_name=department.name, budget_days=payload.budget_days, budget_cost=payload.budget_cost, expense_budget=0, status=payload.status, allow_worklog=payload.allow_worklog)
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
    """预算项已固定为统一 8 项，不再允许新增；保留接口以便前端给出明确提示。"""
    require_access(db, "configuration", "CREATE", x_demo_user_id)
    raise HTTPException(409, "BUDGET_TEMPLATE_FIXED")


@app.patch("/api/v1/admin/budget-item-templates/{template_id}", response_model=BudgetItemTemplateView)
def update_budget_item_template(template_id: int, payload: BudgetItemTemplateUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> BudgetItemTemplateView:
    """预算项固定为统一 8 项，只允许切换启用状态；名称、排序由内置模板维护。"""
    user = require_access(db, "configuration", "EDIT", x_demo_user_id)
    template = db.get(BudgetItemTemplate, template_id)
    if not template:
        raise HTTPException(404, "BUDGET_TEMPLATE_NOT_FOUND")
    old_status = "ACTIVE" if template.is_active else "INACTIVE"
    template.is_active = payload.is_active
    audit(db, "budget_item_template", template.id, "UPDATE", user.id, old_status, "ACTIVE" if template.is_active else "INACTIVE", template.name)
    db.commit()
    db.refresh(template)
    return BudgetItemTemplateView.model_validate(template)


@app.delete("/api/v1/admin/budget-item-templates/{template_id}")
def delete_budget_item_template(template_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """预算项已固定为统一 8 项，不再允许删除；停用请改用启用状态开关。"""
    require_access(db, "configuration", "DELETE", x_demo_user_id)
    raise HTTPException(409, "BUDGET_TEMPLATE_FIXED")


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
    validate_config_option(db, "project_status", payload.status)
    major, sub_category = resolve_project_classification(db, payload.project_type, payload.project_sub_category)
    old_status = project.status
    old_category = project.project_type
    project.code = payload.code
    project.name = payload.name
    project.project_type = major
    project.project_sub_category = sub_category
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
    if old_category != major:
        # 项目大类切换后按新大类的模板补齐预算项，已有预算金额保持不变。
        ensure_project_budget_items(db, project)
    audit(db, "project", project.id, "UPDATE", user.id, old_status, project.status)
    db.commit()
    db.refresh(project)
    return project_view(db, project)


@app.get("/api/v1/projects/{project_id}/worklogs/convert-to-management/preview")
def preview_pre_approval_worklog_conversion(project_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """预览预立项项目可转换为管理工时的记录数量和人天。"""
    user = require_access(db, "projects", "VIEW", x_demo_user_id)
    project = ensure_project_in_scope(db, user, project_id)
    rows = db.scalars(select(Worklog).where(Worklog.project_id == project.id, Worklog.work_type.in_(PRE_APPROVAL_CONVERTIBLE_WORK_TYPES))).all()
    status_counts: dict[str, int] = defaultdict(int)
    total_days = 0.0
    for row in rows:
        status_counts[row.status] += 1
        total_days += float(row.quantity)
    return {
        "project_id": project.id,
        "project_name": project.name,
        "convertible_count": len(rows),
        "total_days": round(total_days, 2),
        "status_counts": dict(status_counts),
    }


@app.post("/api/v1/projects/{project_id}/worklogs/convert-to-management")
def convert_pre_approval_worklogs_to_management(project_id: int, payload: dict[str, str] | None = None, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """将预立项项目工时批量转为管理工时；可在任意项目状态执行，转换过程写入审计。"""
    user = require_access(db, "projects", "EDIT", x_demo_user_id)
    require_access(db, "worklogs", "EDIT", x_demo_user_id)
    project = ensure_project_in_scope(db, user, project_id)
    reason = ((payload or {}).get("reason") or "预立项未成功，转为管理工时").strip()
    rows = db.scalars(select(Worklog).where(Worklog.project_id == project.id, Worklog.work_type.in_(PRE_APPROVAL_CONVERTIBLE_WORK_TYPES))).all()
    converted = 0
    closed_tasks = 0
    now = now_local()
    for item in rows:
        old_status = item.status
        pending_tasks = db.scalars(select(ApprovalTask).where(ApprovalTask.worklog_id == item.id, ApprovalTask.status == "PENDING")).all()
        for task in pending_tasks:
            task.status = "WITHDRAWN"
            task.comment = "预立项工时转管理工时"
            task.processed_at = now
            task.processed_by = user.id
            closed_tasks += 1
        item.converted_from_project_id = item.project_id
        item.converted_from_project_name = item.project_name_snapshot
        item.converted_at = now
        item.converted_by = user.id
        item.conversion_reason = reason
        item.project_id = None
        item.project_name_snapshot = "管理工时"
        item.work_type = "MANAGEMENT_WORK"
        item.stage = "管理"
        item.approval_flow_type = "DEPARTMENT_SINGLE" if item.status == "PENDING_APPROVAL" else item.approval_flow_type
        if item.status in {"PENDING_APPROVAL", "REJECTED"}:
            item.status = "DRAFT"
            item.approver_user_id = None
            item.approver_name_snapshot = None
            item.submitted_at = None
            item.rejection_reason = None
            item.approval_comment = None
            item.last_notified_at = None
        audit(db, "worklog", item.id, "CONVERT_TO_MANAGEMENT", user.id, old_status, item.status, f"{project.name} -> 管理工时；{reason}")
        converted += 1
    old_project_status = project.status
    if project.status == "PRE_APPROVAL":
        project.status = "PRE_APPROVAL_FAILED"
        project.allow_worklog = False
        audit(db, "project", project.id, "PRE_APPROVAL_FAILED", user.id, old_project_status, project.status, reason)
    db.commit()
    return {"project_id": project.id, "converted_count": converted, "closed_pending_tasks": closed_tasks, "project_status": project.status}


@app.post("/api/v1/projects/{project_id}/pre-approval/fail", response_model=ProjectView)
def mark_project_pre_approval_failed(project_id: int, payload: dict[str, str] | None = None, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectView:
    """只标记预立项失败，不自动转换工时；转换由单独按钮显式执行。"""
    user = require_access(db, "projects", "EDIT", x_demo_user_id)
    project = ensure_project_in_scope(db, user, project_id)
    old_status = project.status
    project.status = "PRE_APPROVAL_FAILED"
    project.allow_worklog = False
    reason = ((payload or {}).get("reason") or "预立项未成功").strip()
    audit(db, "project", project.id, "PRE_APPROVAL_FAILED", user.id, old_status, project.status, reason)
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
    apply_tax_amount_fields(contract, payload.amount, payload.tax_rate, payload.amount_without_tax)
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
    apply_tax_amount_fields(contract, payload.amount, payload.tax_rate, payload.amount_without_tax)
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
    active_cash = active_cash or db.scalar(select(Payment.id).where(Payment.contract_id == contract.id, Payment.status.in_(("DRAFT", "PENDING", "PENDING_APPROVAL", "PENDING_REVIEW", "APPROVED"))).limit(1))
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
    data = payload.model_dump()
    data.update(tax_amount_fields(payload.amount, payload.tax_rate, payload.amount_without_tax))
    stage = ContractStage(contract_id=contract.id, **data)
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
    data = payload.model_dump()
    data.update(tax_amount_fields(payload.amount, payload.tax_rate, payload.amount_without_tax))
    for key, value in data.items():
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
    return [receipt_view(db, item, user.id) for item in db.scalars(query).all()]


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
    apply_tax_amount_fields(receipt, payload.amount, payload.tax_rate, payload.amount_without_tax)
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
        resend_sent=True,
    )
    db.commit()
    db.refresh(receipt)
    return receipt_view(db, receipt, user.id)


@app.get("/api/v1/receipts/{receipt_id}", response_model=ReceiptView)
def get_receipt(receipt_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ReceiptView:
    user = require_admin_permission(db, "receipts", x_demo_user_id)
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    ensure_project_in_scope(db, user, receipt.project_id)
    return receipt_view(db, receipt, user.id)


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
    apply_tax_amount_fields(receipt, payload.amount, payload.tax_rate, payload.amount_without_tax)
    receipt.receipt_date = payload.receipt_date
    receipt.payer_name = payload.payer_name
    receipt.payer_bank_name = payload.payer_bank_name
    receipt.payer_bank_account = payload.payer_bank_account
    receipt.comment = payload.comment
    audit(db, "receipt", receipt.id, "UPDATE", user.id, receipt.status, receipt.status)
    db.commit()
    db.refresh(receipt)
    return receipt_view(db, receipt, user.id)


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
    old_status = receipt.status
    receipt.status = "PENDING"
    receipt.submitted_by = user.id
    receipt.submitted_at = now_local()
    audit(db, "receipt", receipt.id, "SUBMIT", user.id, old_status, "PENDING")
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
        resend_sent=True,
    )
    db.commit()
    db.refresh(receipt)
    return receipt_view(db, receipt, user.id)


@app.post("/api/v1/receipts/{receipt_id}/withdraw", response_model=ReceiptView)
def withdraw_receipt(receipt_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ReceiptView:
    """提交人撤回待出纳复核的合同收款单，恢复为草稿后可重新编辑提交。"""
    user = require_admin_permission(db, "receipts", x_demo_user_id)
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    ensure_project_in_scope(db, user, receipt.project_id)
    if receipt.submitted_by != user.id:
        raise HTTPException(403, "RECEIPT_WITHDRAW_FORBIDDEN")
    if receipt.status != "PENDING":
        raise HTTPException(409, "RECEIPT_NOT_PENDING")
    receipt.status = "DRAFT"
    receipt.submitted_at = None
    receipt.approved_by = None
    receipt.approved_at = None
    audit(db, "receipt", receipt.id, "WITHDRAW", user.id, "PENDING", "DRAFT")
    db.commit()
    db.refresh(receipt)
    return receipt_view(db, receipt, user.id)


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
    return receipt_view(db, receipt, user.id)


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
    return receipt_view(db, receipt, user.id)


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
    return receipt_view(db, receipt, user.id)


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


def resolve_payment_payee(db: Session, contract: Contract, payee_name: str | None, payee_bank_name: str | None, payee_bank_account: str | None) -> tuple[str, str | None, str | None]:
    """收款方留空时按支出合同的供应商主数据带出，避免重复录入并保持快照一致。"""
    supplier = db.get(Supplier, contract.counterparty_id) if contract.counterparty_type == "SUPPLIER" else None
    name = (payee_name or "").strip() or (supplier.name if supplier else contract.counterparty_name)
    bank_name = (payee_bank_name or "").strip() or ((supplier.bank_branch or supplier.bank_name) if supplier else None)
    bank_account = (payee_bank_account or "").strip() or (supplier.bank_account if supplier else None)
    return name, bank_name, bank_account


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
    payee_name, payee_bank_name, payee_bank_account = resolve_payment_payee(db, contract, payload.payee_name, payload.payee_bank_name, payload.payee_bank_account)
    payment = Payment(
        payment_no=next_document_no(db, Payment, "PAY"),
        project_id=contract.project_id,
        contract_id=contract.id,
        stage_id=stage.id if stage else None,
        amount=payload.amount,
        payment_date=payload.payment_date,
        payee_name=payee_name,
        payee_bank_name=payee_bank_name,
        payee_bank_account=payee_bank_account,
        status="DRAFT",
        submitted_by=user.id,
        submitted_at=None,
        comment=payload.comment,
    )
    apply_tax_amount_fields(payment, payload.amount, payload.tax_rate, payload.amount_without_tax)
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
    apply_tax_amount_fields(payment, payload.amount, payload.tax_rate, payload.amount_without_tax)
    payment.payment_date = payload.payment_date
    payee_name, payee_bank_name, payee_bank_account = resolve_payment_payee(db, contract, payload.payee_name, payload.payee_bank_name, payload.payee_bank_account)
    payment.payee_name = payee_name
    payment.payee_bank_name = payee_bank_name
    payment.payee_bank_account = payee_bank_account
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


COST_REVIEW_POSITION_CODE = "COST_REVIEWER"
COST_REVIEW_RESOURCE = "cost_review"


def position_members(db: Session, code: str) -> list[User]:
    """返回复核岗位内的在职成员，作为一级复核候选人。"""
    position = db.scalar(select(ApprovalPosition).where(ApprovalPosition.code == code))
    if not position:
        return []
    return list(
        db.scalars(
            select(User)
            .join(ApprovalPositionMember, ApprovalPositionMember.user_id == User.id)
            .where(ApprovalPositionMember.position_id == position.id, User.employment_status == "ACTIVE")
            .order_by(User.name)
        ).all()
    )


def cost_reviewer_users(db: Session) -> list[User]:
    """一级费用复核候选人：优先取费用复核岗位成员，岗位为空时回退到持有费用复核权限的人员。"""
    members = position_members(db, COST_REVIEW_POSITION_CODE)
    if members:
        return members
    return [
        user
        for user in db.scalars(select(User).where(User.employment_status == "ACTIVE")).all()
        if "APPROVE" in effective_permission_details(db, user.id).get(COST_REVIEW_RESOURCE, {}).get("actions", [])
    ]


def cost_can_review(db: Session, user: User | None) -> bool:
    """判断用户是否可执行一级费用复核：属于费用复核岗位，或直接持有费用复核权限。"""
    if not user:
        return False
    if "APPROVE" in effective_permission_details(db, user.id).get(COST_REVIEW_RESOURCE, {}).get("actions", []):
        return True
    return any(member.id == user.id for member in position_members(db, COST_REVIEW_POSITION_CODE))


def require_cost_reviewer(db: Session, demo_user_id: int | None = None) -> User:
    """校验当前用户可执行一级费用复核；不满足时返回统一错误。"""
    user = current_user(db, demo_user_id)
    if not cost_can_review(db, user):
        raise HTTPException(403, "COST_REVIEW_FORBIDDEN")
    return user


def notify_cost_review_submitted(
    db: Session,
    *,
    source_type: str,
    source_id: int,
    version: int,
    notification_type: str,
    document_label: str,
    serial_no: str,
    project_name: str,
    amount: float,
    submitter_name: str,
    page: str,
) -> int:
    """通知费用复核岗位全部有效成员；任一人处理后其余待办自然关闭，无需关闭任务。"""
    if not notification_policy_enabled(db, notification_type):
        return 0
    base = os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088").rstrip("/")
    channel = notification_policy_channel(db, notification_type)
    sent = 0
    for recipient in cost_reviewer_users(db):
        key = f"cost-review:{source_type}:{source_id}:{version}:{recipient.id}"
        notification = db.scalar(select(SystemNotification).where(SystemNotification.idempotency_key == key))
        if notification and notification.status == "SENT":
            continue
        result = feishu.notify_cash_approval_submitted(
            recipient.name,
            submitter_name,
            document_label,
            serial_no,
            project_name,
            amount,
            f"{base}/?page={page}&id={source_id}",
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
                idempotency_key=key,
            )
            db.add(notification)
        else:
            notification.retry_count = int(notification.retry_count or 0) + 1
        notification.status = result.status
        notification.channel = channel or feishu.notification_mode
        notification.message_id = result.message_id
        notification.error_message = result.error_message
        notification.sent_at = now_local() if result.status == "SENT" else None
        sent += 1
    return sent


def notify_cost_review_result(
    db: Session,
    *,
    source_type: str,
    source_id: int,
    version: int,
    recipient_user_id: int | None,
    document_label: str,
    serial_no: str,
    project_name: str,
    amount: float,
    status_label: str,
    page: str,
    actor_name: str,
) -> None:
    """向申请人发送一级复核结果，失败不影响单据状态。"""
    if not notification_policy_enabled(db, "COST_REVIEW_RESULT"):
        return
    recipient = db.get(User, recipient_user_id) if recipient_user_id else None
    if not recipient:
        return
    base = os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088").rstrip("/")
    key = f"cost-review-result:{source_type}:{source_id}:{version}:{status_label}"
    notification = db.scalar(select(SystemNotification).where(SystemNotification.idempotency_key == key))
    if notification and notification.status == "SENT":
        return
    channel = notification_policy_channel(db, "COST_REVIEW_RESULT")
    result = feishu.notify_settlement_result(
        recipient.name,
        document_label,
        serial_no,
        project_name,
        amount,
        status_label,
        f"{base}/?page={page}&id={source_id}",
        recipient.open_id,
        channel=channel,
        approver_name=actor_name,
    )
    if not notification:
        notification = SystemNotification(
            notification_type="COST_REVIEW_RESULT",
            source_type=source_type,
            source_id=source_id,
            recipient_user_id=recipient.id,
            channel=channel or feishu.notification_mode,
            idempotency_key=key,
        )
        db.add(notification)
    else:
        notification.retry_count = int(notification.retry_count or 0) + 1
    notification.status = result.status
    notification.channel = channel or feishu.notification_mode
    notification.message_id = result.message_id
    notification.error_message = result.error_message
    notification.sent_at = now_local() if result.status == "SENT" else None


@app.post("/api/v1/payments/{payment_id}/submit", response_model=PaymentView)
def submit_payment(payment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    """提交一级费用复核；不再生成多级审批实例，费用复核岗位任一人通过即完成。"""
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
    payment.submitted_at = now_local()
    payment.version += 1
    payment.status = "PENDING_REVIEW"
    payment.comment = None
    payment.approved_by = None
    payment.approved_at = None
    payment.current_workflow_instance_id = None
    project = db.get(Project, payment.project_id)
    audit(db, "payment", payment.id, "SUBMIT", user.id, old_status, "PENDING_REVIEW")
    db.commit()
    notify_cost_review_submitted(
        db,
        source_type="payment",
        source_id=payment.id,
        version=payment.version,
        notification_type="PENDING_PAYMENT_REVIEW",
        document_label="合同付款单",
        serial_no=payment.payment_no,
        project_name=project.name if project else "",
        amount=float(payment.amount),
        submitter_name=user.name,
        page="paymentDetail",
    )
    db.commit()
    db.refresh(payment)
    return payment_view(db, payment, user.id)


@app.post("/api/v1/payments/{payment_id}/withdraw", response_model=PaymentView)
def withdraw_payment(payment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    """提交人撤回待费用复核的合同付款单，恢复为草稿后可重新编辑提交。"""
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    user = payment_access(db, payment, x_demo_user_id)
    if payment.submitted_by != user.id:
        raise HTTPException(403, "PAYMENT_WITHDRAW_FORBIDDEN")
    if payment.status != "PENDING_REVIEW":
        raise HTTPException(409, "PAYMENT_NOT_PENDING_REVIEW")
    instance = db.get(WorkflowInstance, payment.current_workflow_instance_id) if payment.current_workflow_instance_id else None
    if instance:
        instance.status = "WITHDRAWN"
        instance.completed_at = now_local()
        for task in db.scalars(select(WorkflowTask).where(WorkflowTask.workflow_instance_id == instance.id, WorkflowTask.status == "PENDING")).all():
            task.status = "WITHDRAWN"
            task.processed_by = user.id
            task.processed_at = now_local()
        db.add(WorkflowActionLog(workflow_instance_id=instance.id, action="WITHDRAW", actor_user_id=user.id, actor_name=user.name, from_status="PENDING_REVIEW", to_status="DRAFT"))
    payment.status = "DRAFT"
    payment.submitted_at = None
    payment.approved_by = None
    payment.approved_at = None
    payment.current_workflow_instance_id = None
    audit(db, "payment", payment.id, "WITHDRAW", user.id, "PENDING_REVIEW", "DRAFT")
    db.commit()
    db.refresh(payment)
    return payment_view(db, payment, user.id)


@app.post("/api/v1/payments/{payment_id}/approve", response_model=PaymentView)
def approve_payment(payment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    """一级费用复核通过：通过即视为已付并计入合同成本，同时记录实际复核人。"""
    user = require_cost_reviewer(db, x_demo_user_id)
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    if payment.status != "PENDING_REVIEW":
        raise HTTPException(409, "PAYMENT_NOT_PENDING_REVIEW")
    payment.status = "APPROVED"
    payment.approved_by = user.id
    payment.approved_at = now_local()
    budget_item = db.get(ProjectBudgetItem, payment.budget_item_id) if payment.budget_item_id else None
    add_ledger_entry(db, payment.project_id, "PAYMENT", "PAYMENT", payment.id, float(payment.amount), occurred_on=payment.payment_date, budget_item=budget_item)
    stage = db.get(ContractStage, payment.stage_id) if payment.stage_id else None
    refresh_stage_status(db, stage, "EXPENSE")
    audit(db, "payment", payment.id, "APPROVE", user.id, "PENDING_REVIEW", "APPROVED")
    db.commit()
    db.refresh(payment)
    project = db.get(Project, payment.project_id)
    notify_cost_review_result(
        db,
        source_type="payment",
        source_id=payment.id,
        version=payment.version,
        recipient_user_id=payment.submitted_by,
        document_label="合同付款单",
        serial_no=payment.payment_no,
        project_name=project.name if project else "",
        amount=float(payment.amount),
        status_label="复核通过",
        page="paymentDetail",
        actor_name=user.name,
    )
    db.commit()
    return payment_view(db, payment, user.id)


@app.post("/api/v1/payments/{payment_id}/reject", response_model=PaymentView)
def reject_payment(payment_id: int, payload: CashRejectAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    """一级费用复核驳回：驳回后不计入合同成本和已付。"""
    user = require_cost_reviewer(db, x_demo_user_id)
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    if payment.status != "PENDING_REVIEW":
        raise HTTPException(409, "PAYMENT_NOT_PENDING_REVIEW")
    payment.status = "REJECTED"
    payment.comment = payload.reason
    payment.approved_by = user.id
    payment.approved_at = now_local()
    audit(db, "payment", payment.id, "REJECT", user.id, "PENDING_REVIEW", "REJECTED", payload.reason)
    db.commit()
    db.refresh(payment)
    project = db.get(Project, payment.project_id)
    notify_cost_review_result(
        db,
        source_type="payment",
        source_id=payment.id,
        version=payment.version,
        recipient_user_id=payment.submitted_by,
        document_label="合同付款单",
        serial_no=payment.payment_no,
        project_name=project.name if project else "",
        amount=float(payment.amount),
        status_label="复核驳回",
        page="paymentDetail",
        actor_name=user.name,
    )
    db.commit()
    return payment_view(db, payment, user.id)


@app.post("/api/v1/payments/{payment_id}/reverse", response_model=PaymentView)
def reverse_payment(payment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentView:
    user = require_cost_reviewer(db, x_demo_user_id)
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


def month_bounds(period_month: str) -> tuple[date, date]:
    """把 YYYY-MM 转为该月首尾日期，供台账与经营分析统一口径使用。"""
    if not re.match(r"^\d{4}-\d{2}$", period_month):
        raise HTTPException(400, "PERIOD_MONTH_INVALID")
    year, month = [int(part) for part in period_month.split("-")]
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return start, end


def shift_month(period_month: str, offset: int) -> str:
    """返回指定月份偏移后的 YYYY-MM 字符串。"""
    year, month = [int(part) for part in period_month.split("-")]
    zero_based = year * 12 + month - 1 + offset
    return f"{zero_based // 12:04d}-{zero_based % 12 + 1:02d}"


def receipt_ledger_rows(
    db: Session,
    user: User,
    *,
    period_month: str,
    project_id: int | None = None,
    owner_user_id: int | None = None,
    customer_id: int | None = None,
    keyword: str | None = None,
    status: str | None = None,
    limit_risk: int | None = None,
) -> list[ReceiptPlanView]:
    """生成回款台账行：收入合同是事实来源，计划表只补充月度计划字段。"""
    start, end = month_bounds(period_month)
    previous_month = shift_month(period_month, -1)
    prev_start, prev_end = month_bounds(previous_month)
    scope = project_scope_ids(db, user, "receipt_ledger")
    query = select(Contract).where(Contract.contract_type == "INCOME", Contract.status != "TERMINATED").order_by(Contract.id.desc())
    if scope is not None:
        query = query.where(Contract.project_id.in_(scope))
    if project_id:
        query = query.where(Contract.project_id == project_id)
    if customer_id:
        query = query.where(Contract.counterparty_type == "CUSTOMER", Contract.counterparty_id == customer_id)
    if owner_user_id:
        query = query.where(Contract.project_id.in_(select(Project.id).where(Project.owner_user_id == owner_user_id)))
    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(
            Contract.name.contains(value)
            | Contract.contract_no.contains(value)
            | Contract.counterparty_name.contains(value)
            | Contract.project_id.in_(select(Project.id).where(Project.name.contains(value) | Project.code.contains(value)))
        )
    contracts = db.scalars(query).all()
    contract_ids = [item.id for item in contracts]
    plans = {item.contract_id: item for item in db.scalars(select(ReceiptPlan).where(ReceiptPlan.period_month == period_month, ReceiptPlan.contract_id.in_(contract_ids))).all()} if contract_ids else {}
    prev_plans = {item.contract_id: item for item in db.scalars(select(ReceiptPlan).where(ReceiptPlan.period_month == previous_month, ReceiptPlan.contract_id.in_(contract_ids))).all()} if contract_ids else {}
    rows: list[ReceiptPlanView] = []
    for contract in contracts:
        project = db.get(Project, contract.project_id)
        customer = db.get(Customer, contract.counterparty_id) if contract.counterparty_type == "CUSTOMER" else None
        stage_total = float(db.scalar(select(func.coalesce(func.sum(ContractStage.amount), 0)).where(ContractStage.contract_id == contract.id, ContractStage.status != "CANCELLED")) or 0)
        receivable_amount = stage_total if stage_total > 0 else float(contract.amount or 0)
        received_amount = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.contract_id == contract.id, Receipt.status == "APPROVED")) or 0)
        current_actual = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.contract_id == contract.id, Receipt.status == "APPROVED", Receipt.receipt_date >= start, Receipt.receipt_date <= end)) or 0)
        previous_actual = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.contract_id == contract.id, Receipt.status == "APPROVED", Receipt.receipt_date >= prev_start, Receipt.receipt_date <= prev_end)) or 0)
        overdue_stage_total = float(db.scalar(select(func.coalesce(func.sum(ContractStage.amount), 0)).where(ContractStage.contract_id == contract.id, ContractStage.status != "CANCELLED", ContractStage.planned_date.is_not(None), ContractStage.planned_date <= today_local())) or 0)
        overdue_received = float(db.scalar(select(func.coalesce(func.sum(Receipt.amount), 0)).join(ContractStage, Receipt.stage_id == ContractStage.id).where(Receipt.contract_id == contract.id, Receipt.status == "APPROVED", ContractStage.planned_date.is_not(None), ContractStage.planned_date <= today_local())) or 0)
        plan = plans.get(contract.id)
        prev_plan = prev_plans.get(contract.id)
        current_plan = float(plan.plan_amount or 0) if plan else 0
        unreceived_amount = max(receivable_amount - received_amount, 0)
        warning_tags: list[str] = []
        if max(overdue_stage_total - overdue_received, 0) > 0:
            warning_tags.append("逾期未收")
        if current_plan > 0 and current_actual < current_plan and today_local() >= end - timedelta(days=5):
            warning_tags.append("本月计划未完成")
        if plan and plan.expected_finish_date and plan.expected_finish_date <= today_local() + timedelta(days=30) and unreceived_amount > 0:
            warning_tags.append("临近完成未收")
        if not plan and today_local().day >= 5:
            warning_tags.append("本月计划未维护")
        updater = db.get(User, plan.updated_by) if plan and plan.updated_by else None
        row = ReceiptPlanView(
            id=plan.id if plan else None,
            period_month=period_month,
            project_id=contract.project_id,
            project_name=project.name if project else "",
            project_code=project.code if project else None,
            owner_name=project.owner_name if project else None,
            department_name=project.department_name if project else None,
            contract_id=contract.id,
            contract_name=contract.name,
            contract_no=contract.contract_no,
            customer_name=customer.name if customer else contract.counterparty_name,
            contract_amount=float(contract.amount or 0),
            receivable_amount=round(receivable_amount, 2),
            received_amount=round(received_amount, 2),
            unreceived_amount=round(unreceived_amount, 2),
            previous_plan_amount=round(float(prev_plan.plan_amount or 0), 2) if prev_plan else 0,
            previous_actual_amount=round(previous_actual, 2),
            current_plan_amount=round(current_plan, 2),
            current_actual_amount=round(current_actual, 2),
            completion_rate=round(current_actual / current_plan * 100, 1) if current_plan > 0 else None,
            progress_note=plan.progress_note if plan else None,
            expected_finish_date=plan.expected_finish_date if plan else None,
            remark=plan.remark if plan else None,
            updated_by_name=updater.name if updater else None,
            updated_at=plan.updated_at if plan else None,
            warning_tags=warning_tags,
        )
        if status == "UNRECEIVED" and row.unreceived_amount <= 0:
            continue
        if status == "COMPLETED" and row.unreceived_amount > 0:
            continue
        if status == "OVERDUE" and "逾期未收" not in warning_tags:
            continue
        rows.append(row)
    if limit_risk:
        rows = sorted(rows, key=lambda item: (0 if item.warning_tags else 1, -item.unreceived_amount))[:limit_risk]
    return rows


def receipt_ledger_summary(rows: list[ReceiptPlanView]) -> ReceiptLedgerSummary:
    current_plan = round(sum(item.current_plan_amount for item in rows), 2)
    current_actual = round(sum(item.current_actual_amount for item in rows), 2)
    return ReceiptLedgerSummary(
        contract_amount=round(sum(item.contract_amount for item in rows), 2),
        receivable_amount=round(sum(item.receivable_amount for item in rows), 2),
        received_amount=round(sum(item.received_amount for item in rows), 2),
        unreceived_amount=round(sum(item.unreceived_amount for item in rows), 2),
        current_plan_amount=current_plan,
        current_actual_amount=current_actual,
        completion_rate=round(current_actual / current_plan * 100, 1) if current_plan > 0 else None,
        overdue_unreceived_amount=round(sum(item.unreceived_amount for item in rows if "逾期未收" in item.warning_tags), 2),
    )


def payment_plan_view(db: Session, plan: PaymentPlan) -> PaymentPlanView:
    """返回付款计划展示对象，并对来源、收款方、状态做中文化。"""
    project = db.get(Project, plan.project_id) if plan.project_id else None
    contract = db.get(Contract, plan.contract_id) if plan.contract_id else None
    stage = db.get(ContractStage, plan.contract_stage_id) if plan.contract_stage_id else None
    department = db.get(Department, plan.department_id) if plan.department_id else None
    handler = db.get(User, plan.handler_user_id) if plan.handler_user_id else None
    creator = db.get(User, plan.created_by) if plan.created_by else None
    source_labels = {"CONTRACT_STAGE": "支出合同阶段", "PROJECT_EXPENSE": "项目费用", "MANUAL": "手工计划"}
    payee_labels = {"SUPPLIER": "供应商", "COMPANY": "公司", "EMPLOYEE": "员工", "EXTERNAL_PERSON": "外部个人", "OTHER": "其他"}
    status_labels = {"DRAFT": "草稿", "SUBMITTED": "已列入计划", "CONVERTED": "已转付款", "CANCELLED": "已取消"}
    return PaymentPlanView(
        id=plan.id,
        plan_no=plan.plan_no,
        period_month=plan.period_month,
        department_id=plan.department_id,
        department_name=department.name if department else None,
        handler_user_id=plan.handler_user_id,
        handler_name=handler.name if handler else None,
        payment_category=plan.payment_category,
        source_type=plan.source_type,
        source_label=source_labels.get(plan.source_type, plan.source_type),
        project_id=plan.project_id,
        project_name=project.name if project else None,
        contract_id=plan.contract_id,
        contract_name=contract.name if contract else None,
        contract_stage_id=plan.contract_stage_id,
        contract_stage_name=stage.name if stage else None,
        payee_type=plan.payee_type,
        payee_type_label=payee_labels.get(plan.payee_type, plan.payee_type),
        payee_ref_id=plan.payee_ref_id,
        payee_name_snapshot=plan.payee_name_snapshot,
        payee_bank_snapshot=plan.payee_bank_snapshot,
        payee_account_last4=plan.payee_account_last4,
        planned_amount=float(plan.planned_amount or 0),
        payment_method=plan.payment_method,
        planned_pay_date=plan.planned_pay_date,
        purpose=plan.purpose,
        has_finance_material=plan.has_finance_material,
        is_urgent=plan.is_urgent,
        status=plan.status,
        status_label=status_labels.get(plan.status, plan.status),
        linked_document_type=plan.linked_document_type,
        linked_document_id=plan.linked_document_id,
        remark=plan.remark,
        created_by_name=creator.name if creator else None,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def payment_plan_summary(items: list[PaymentPlanView]) -> PaymentPlanSummary:
    active = [item for item in items if item.status != "CANCELLED"]
    return PaymentPlanSummary(
        planned_amount=round(sum(item.planned_amount for item in active), 2),
        current_month_amount=round(sum(item.planned_amount for item in active), 2),
        urgent_amount=round(sum(item.planned_amount for item in active if item.is_urgent), 2),
        contract_stage_amount=round(sum(item.planned_amount for item in active if item.source_type == "CONTRACT_STAGE"), 2),
        project_expense_amount=round(sum(item.planned_amount for item in active if item.source_type == "PROJECT_EXPENSE"), 2),
        personal_payee_amount=round(sum(item.planned_amount for item in active if item.payee_type in {"EMPLOYEE", "EXTERNAL_PERSON"}), 2),
        converted_amount=round(sum(item.planned_amount for item in items if item.status == "CONVERTED"), 2),
    )


def apply_payment_plan_payload(db: Session, plan: PaymentPlan, payload: PaymentPlanCreate | PaymentPlanUpdate) -> None:
    """写入付款计划并按来源执行必填/一致性校验；不创建审批或通知。"""
    project_id = payload.project_id
    contract_id = payload.contract_id
    stage_id = payload.contract_stage_id
    if payload.source_type == "CONTRACT_STAGE":
        contract = resolve_contract(db, payload.contract_id or 0)
        if contract.contract_type != "EXPENSE":
            raise HTTPException(400, "PAYMENT_PLAN_CONTRACT_TYPE_MISMATCH")
        stage = resolve_contract_stage(db, payload.contract_stage_id, contract.id)
        project_id = contract.project_id
        contract_id = contract.id
        stage_id = stage.id if stage else None
    elif payload.source_type == "PROJECT_EXPENSE":
        contract_id = None
        stage_id = None
    else:
        if contract_id:
            contract = resolve_contract(db, contract_id)
            project_id = project_id or contract.project_id
            stage = resolve_contract_stage(db, stage_id, contract.id) if stage_id else None
            stage_id = stage.id if stage else None
    if project_id:
        project = db.get(Project, project_id)
        if not project or project.status == "DELETED":
            raise HTTPException(404, "PROJECT_NOT_FOUND")
    account = (payload.payee_account or "").strip()
    plan.period_month = payload.period_month
    plan.department_id = payload.department_id
    plan.handler_user_id = payload.handler_user_id
    plan.payment_category = payload.payment_category
    plan.source_type = payload.source_type
    plan.project_id = project_id
    plan.contract_id = contract_id
    plan.contract_stage_id = stage_id
    plan.payee_type = payload.payee_type
    plan.payee_ref_id = payload.payee_ref_id
    plan.payee_name_snapshot = payload.payee_name_snapshot
    plan.payee_bank_snapshot = payload.payee_bank_snapshot
    plan.payee_account = account or None
    plan.payee_account_last4 = account[-4:] if account else None
    plan.planned_amount = payload.planned_amount
    plan.payment_method = payload.payment_method or "银行转账"
    plan.planned_pay_date = payload.planned_pay_date
    plan.purpose = payload.purpose
    plan.has_finance_material = payload.has_finance_material
    plan.is_urgent = payload.is_urgent
    plan.status = payload.status
    plan.remark = payload.remark


@app.get("/api/v1/receipt-ledger", response_model=ReceiptLedgerList)
def list_receipt_ledger(
    period_month: str = Query(default_factory=lambda: today_local().strftime("%Y-%m")),
    project_id: int | None = Query(default=None, gt=0),
    owner_user_id: int | None = Query(default=None, gt=0),
    customer_id: int | None = Query(default=None, gt=0),
    keyword: str | None = None,
    status: str | None = None,
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ReceiptLedgerList:
    user = require_admin_permission(db, "receipt_ledger", x_demo_user_id)
    rows = receipt_ledger_rows(db, user, period_month=period_month, project_id=project_id, owner_user_id=owner_user_id, customer_id=customer_id, keyword=keyword, status=status)
    return ReceiptLedgerList(items=rows, summary=receipt_ledger_summary(rows))


@app.post("/api/v1/receipt-ledger/plans", response_model=ReceiptPlanView)
def upsert_receipt_plan(payload: ReceiptPlanUpsert, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ReceiptPlanView:
    user = require_admin_permission(db, "receipt_ledger", x_demo_user_id)
    contract = resolve_contract(db, payload.contract_id)
    if contract.contract_type != "INCOME":
        raise HTTPException(400, "RECEIPT_PLAN_CONTRACT_TYPE_MISMATCH")
    scope = project_scope_ids(db, user, "receipt_ledger")
    if scope is not None and contract.project_id not in scope:
        raise HTTPException(403, "PROJECT_OUT_OF_SCOPE")
    plan = db.scalar(select(ReceiptPlan).where(ReceiptPlan.period_month == payload.period_month, ReceiptPlan.contract_id == contract.id))
    require_access(db, "receipt_ledger", "EDIT" if plan else "CREATE", x_demo_user_id)
    is_new = plan is None
    if not plan:
        plan = ReceiptPlan(period_month=payload.period_month, project_id=contract.project_id, contract_id=contract.id)
        db.add(plan)
    plan.project_id = contract.project_id
    plan.plan_amount = payload.plan_amount
    plan.progress_note = payload.progress_note
    plan.expected_finish_date = payload.expected_finish_date
    plan.remark = payload.remark
    plan.updated_by = user.id
    db.flush()
    audit(db, "receipt_plan", plan.id, "CREATE" if is_new else "UPDATE", user.id, None, "SAVED")
    db.commit()
    rows = receipt_ledger_rows(db, user, period_month=payload.period_month, project_id=contract.project_id)
    return next(item for item in rows if item.contract_id == contract.id)


@app.delete("/api/v1/receipt-ledger/plans/{plan_id}")
def delete_receipt_plan(plan_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    user = require_admin_permission(db, "receipt_ledger", x_demo_user_id)
    require_access(db, "receipt_ledger", "DELETE", x_demo_user_id)
    plan = db.get(ReceiptPlan, plan_id)
    if not plan:
        raise HTTPException(404, "RECEIPT_PLAN_NOT_FOUND")
    scope = project_scope_ids(db, user, "receipt_ledger")
    if scope is not None and plan.project_id not in scope:
        raise HTTPException(403, "PROJECT_OUT_OF_SCOPE")
    db.delete(plan)
    audit(db, "receipt_plan", plan.id, "DELETE", user.id, "SAVED", None)
    db.commit()
    return {"deleted": True, "plan_id": plan_id}

def payment_plan_items(
    db: Session,
    user: User,
    *,
    period_month: str,
    resource: str,
    project_id: int | None = None,
    source_type: str | None = None,
    payee_type: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> list[PaymentPlanView]:
    """按指定资源的数据范围查询付款计划；供 HTTP 接口和经营分析内部复用。"""
    scope = project_scope_ids(db, user, resource)
    query = select(PaymentPlan).where(PaymentPlan.period_month == period_month).order_by(PaymentPlan.planned_pay_date.is_(None), PaymentPlan.planned_pay_date, PaymentPlan.id.desc())
    if scope is not None:
        query = query.where(or_(PaymentPlan.project_id.in_(scope), PaymentPlan.handler_user_id == user.id, PaymentPlan.created_by == user.id))
    if project_id:
        query = query.where(PaymentPlan.project_id == project_id)
    if source_type:
        query = query.where(PaymentPlan.source_type == source_type)
    if payee_type:
        query = query.where(PaymentPlan.payee_type == payee_type)
    if status:
        query = query.where(PaymentPlan.status == status)
    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(PaymentPlan.plan_no.contains(value) | PaymentPlan.payee_name_snapshot.contains(value) | PaymentPlan.purpose.contains(value) | PaymentPlan.payment_category.contains(value))
    return [payment_plan_view(db, item) for item in db.scalars(query).all()]


@app.get("/api/v1/payment-plans", response_model=PaymentPlanList)
def list_payment_plans(
    period_month: str = Query(default_factory=lambda: today_local().strftime("%Y-%m")),
    project_id: int | None = Query(default=None, gt=0),
    source_type: str | None = None,
    payee_type: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> PaymentPlanList:
    user = require_admin_permission(db, "payment_plan", x_demo_user_id)
    items = payment_plan_items(
        db,
        user,
        period_month=period_month,
        resource="payment_plan",
        project_id=project_id,
        source_type=source_type,
        payee_type=payee_type,
        status=status,
        keyword=keyword,
    )
    return PaymentPlanList(items=items, summary=payment_plan_summary(items))


@app.post("/api/v1/payment-plans", response_model=PaymentPlanView, status_code=201)
def create_payment_plan(payload: PaymentPlanCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentPlanView:
    user = require_admin_permission(db, "payment_plan", x_demo_user_id)
    require_access(db, "payment_plan", "CREATE", x_demo_user_id)
    plan = PaymentPlan(plan_no=next_document_no(db, PaymentPlan, "PLAN"), period_month=payload.period_month, payment_category=payload.payment_category, source_type=payload.source_type, payee_type=payload.payee_type, payee_name_snapshot=payload.payee_name_snapshot, planned_amount=payload.planned_amount, purpose=payload.purpose, created_by=user.id)
    apply_payment_plan_payload(db, plan, payload)
    scope = project_scope_ids(db, user, "payment_plan")
    if scope is not None and plan.project_id and plan.project_id not in scope:
        raise HTTPException(403, "PROJECT_OUT_OF_SCOPE")
    db.add(plan)
    db.flush()
    audit(db, "payment_plan", plan.id, "CREATE", user.id, None, plan.status)
    db.commit()
    db.refresh(plan)
    return payment_plan_view(db, plan)


@app.patch("/api/v1/payment-plans/{plan_id}", response_model=PaymentPlanView)
def update_payment_plan(plan_id: int, payload: PaymentPlanUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> PaymentPlanView:
    user = require_admin_permission(db, "payment_plan", x_demo_user_id)
    require_access(db, "payment_plan", "EDIT", x_demo_user_id)
    plan = db.get(PaymentPlan, plan_id)
    if not plan:
        raise HTTPException(404, "PAYMENT_PLAN_NOT_FOUND")
    if plan.status == "CONVERTED":
        raise HTTPException(409, "PAYMENT_PLAN_CONVERTED_READ_ONLY")
    scope = project_scope_ids(db, user, "payment_plan")
    if scope is not None and plan.project_id and plan.project_id not in scope and plan.created_by != user.id and plan.handler_user_id != user.id:
        raise HTTPException(403, "PROJECT_OUT_OF_SCOPE")
    old_status = plan.status
    apply_payment_plan_payload(db, plan, payload)
    if scope is not None and plan.project_id and plan.project_id not in scope and plan.created_by != user.id and plan.handler_user_id != user.id:
        raise HTTPException(403, "PROJECT_OUT_OF_SCOPE")
    audit(db, "payment_plan", plan.id, "UPDATE", user.id, old_status, plan.status)
    db.commit()
    db.refresh(plan)
    return payment_plan_view(db, plan)


@app.delete("/api/v1/payment-plans/{plan_id}")
def delete_payment_plan(plan_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    user = require_admin_permission(db, "payment_plan", x_demo_user_id)
    require_access(db, "payment_plan", "DELETE", x_demo_user_id)
    plan = db.get(PaymentPlan, plan_id)
    if not plan:
        raise HTTPException(404, "PAYMENT_PLAN_NOT_FOUND")
    scope = project_scope_ids(db, user, "payment_plan")
    if scope is not None and plan.project_id and plan.project_id not in scope and plan.created_by != user.id:
        raise HTTPException(403, "PROJECT_OUT_OF_SCOPE")
    plan.status = "CANCELLED"
    audit(db, "payment_plan", plan.id, "DELETE", user.id, None, "CANCELLED")
    db.commit()
    return {"deleted": True, "plan_id": plan_id}


@app.get("/api/v1/business-analysis", response_model=BusinessAnalysisView)
def get_business_analysis(
    period_month: str = Query(default_factory=lambda: today_local().strftime("%Y-%m")),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> BusinessAnalysisView:
    user = require_admin_permission(db, "business_analysis", x_demo_user_id)
    receipt_rows = receipt_ledger_rows(db, user, period_month=period_month)
    payment_items = payment_plan_items(db, user, period_month=period_month, resource="business_analysis")
    trend: list[BusinessAnalysisTrendItem] = []
    for offset in range(-5, 1):
        month = shift_month(period_month, offset)
        month_receipts = receipt_ledger_rows(db, user, period_month=month)
        month_payments = payment_plan_items(db, user, period_month=month, resource="business_analysis")
        receipt_summary = receipt_ledger_summary(month_receipts)
        payment_summary = payment_plan_summary(month_payments)
        trend.append(BusinessAnalysisTrendItem(period_month=month, receipt_plan_amount=receipt_summary.current_plan_amount, actual_receipt_amount=receipt_summary.current_actual_amount, payment_plan_amount=payment_summary.planned_amount, net_cash_flow=round(receipt_summary.current_actual_amount - payment_summary.planned_amount, 2)))
    receipt_summary = receipt_ledger_summary(receipt_rows)
    payment_summary = payment_plan_summary(payment_items)
    return BusinessAnalysisView(period_month=period_month, receipt_summary=receipt_summary, payment_summary=payment_summary, net_cash_flow=round(receipt_summary.current_actual_amount - payment_summary.planned_amount, 2), trend=trend, risk_projects=receipt_ledger_rows(db, user, period_month=period_month, limit_risk=8), urgent_payments=[item for item in payment_items if item.is_urgent][:8])


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


WORKLOG_CALENDAR_STATUS_LABELS = {
    "FILLED": "已填报",
    "APPROVED": "已通过",
    "PENDING_APPROVAL": "审批中",
    "DRAFT": "草稿",
    "REJECTED": "已驳回",
    "MISSING": "已过未填",
    "TODAY_MISSING": "今日未填",
    "HOLIDAY": "非工作日",
    "FUTURE": "待填报",
}
WORKLOG_CALENDAR_STATUS_PRIORITY = {
    "REJECTED": 5,
    "DRAFT": 4,
    "PENDING_APPROVAL": 3,
    "APPROVED": 2,
    "LOCKED": 2,
}


def calendar_month_range(month: str) -> tuple[date, date]:
    """把 YYYY-MM 转为本月首尾日期，供工时日历接口使用。"""
    if not re.fullmatch(r"\d{4}-\d{2}", month or ""):
        raise HTTPException(400, "MONTH_FORMAT_INVALID")
    year, month_number = (int(part) for part in month.split("-"))
    if not 1 <= month_number <= 12:
        raise HTTPException(400, "MONTH_FORMAT_INVALID")
    start = date(year, month_number, 1)
    end = date(year + (1 if month_number == 12 else 0), 1 if month_number == 12 else month_number + 1, 1) - timedelta(days=1)
    return start, end


@app.get("/api/v1/worklogs/calendar", response_model=WorklogCalendar)
def worklog_calendar(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> WorklogCalendar:
    """返回当前用户月度工时日历，标记已填、漏填、今日待填和非工作日。"""
    user = current_user(db, x_demo_user_id)
    start, end = calendar_month_range(month)
    today = today_local()
    overrides = {
        item.calendar_date: item
        for item in db.scalars(select(WorkCalendarDay).where(WorkCalendarDay.calendar_date >= start, WorkCalendarDay.calendar_date <= end)).all()
    }
    worklog_rows = list(db.scalars(
        select(Worklog)
        .where(Worklog.user_id == user.id, Worklog.start_date <= end, Worklog.end_date >= start)
        .order_by(Worklog.start_date.asc(), Worklog.id.asc())
    ).all())
    by_day: dict[date, Worklog] = {}
    for item in worklog_rows:
        cursor = max(item.start_date, start)
        last = min(item.end_date, end)
        while cursor <= last:
            if is_statutory_workday(db, cursor):
                existing = by_day.get(cursor)
                if not existing or WORKLOG_CALENDAR_STATUS_PRIORITY.get(item.status, 1) > WORKLOG_CALENDAR_STATUS_PRIORITY.get(existing.status, 1):
                    by_day[cursor] = item
            cursor += timedelta(days=1)

    days: list[WorklogCalendarDay] = []
    summary = WorklogCalendarSummary()
    cursor = start
    while cursor <= end:
        item = by_day.get(cursor)
        is_workday = is_statutory_workday(db, cursor)
        override = overrides.get(cursor)
        status = "HOLIDAY"
        if item:
            status = item.status if item.status in WORKLOG_CALENDAR_STATUS_LABELS else "FILLED"
            if status == "LOCKED":
                status = "APPROVED"
        elif is_workday and cursor < today:
            status = "MISSING"
        elif is_workday and cursor == today:
            status = "TODAY_MISSING"
        elif is_workday:
            status = "FUTURE"

        if is_workday:
            summary.required_workdays += 1
        if item:
            summary.filled_days += 1
            if item.status == "PENDING_APPROVAL":
                summary.pending_count += 1
            elif item.status == "REJECTED":
                summary.rejected_count += 1
            elif item.status == "DRAFT":
                summary.draft_count += 1
        elif status == "MISSING":
            summary.missing_days += 1
        elif status == "TODAY_MISSING":
            summary.today_missing += 1

        days.append(WorklogCalendarDay(
            date=cursor,
            day=cursor.day,
            is_workday=is_workday,
            is_today=cursor == today,
            is_past=cursor < today,
            has_worklog=item is not None,
            status=status,
            status_label=WORKLOG_CALENDAR_STATUS_LABELS.get(status, status),
            worklog_id=item.id if item else None,
            quantity=float(item.quantity or 0) if item else 0,
            holiday_name=override.name if override else None,
        ))
        cursor += timedelta(days=1)
    return WorklogCalendar(month=month, summary=summary, days=days)


def admin_worklog_dataset(
    db: Session,
    *,
    viewer: User | None = None,
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
    users = db.scalars(select(User)).all()
    user_departments = {user.id: (department_index.path(user.department_id) if user.department_id else "未分配部门") for user in users}
    user_department_ids = {user.id: user.department_id for user in users}
    query = select(Worklog).order_by(Worklog.fill_date.desc(), Worklog.start_date.desc(), Worklog.id.desc())
    if period_start:
        query = query.where(Worklog.fill_date >= period_start)
    if period_end:
        query = query.where(Worklog.fill_date <= period_end)
    if user_id:
        query = query.where(Worklog.user_id == user_id)
    if project_id:
        query = query.where(Worklog.project_id == project_id)
    if status:
        query = query.where(Worklog.status == status)
    items = list(db.scalars(query).all())
    if viewer:
        scoped_project_ids, scoped_user_ids = worklog_scope_sets(db, viewer, "worklogs")
        items = [item for item in items if worklog_in_scope(item, scoped_project_ids, scoped_user_ids)]
    keyword_value = keyword.strip().casefold() if keyword and keyword.strip() else ""
    if selected_department_ids:
        items = [
            item
            for item in items
            if (
                project_department_ids.get(item.project_id) in selected_department_ids
                if item.project_id
                else user_department_ids.get(item.user_id) in selected_department_ids
            )
        ]
    if keyword_value:
        items = [item for item in items if keyword_value in " ".join((item.user_name_snapshot, item.project_name_snapshot, item.description, item.stage)).casefold()]

    latest_tasks: dict[int, ApprovalTask] = {}
    worklog_ids = [item.id for item in items]
    if worklog_ids:
        tasks = db.scalars(select(ApprovalTask).where(ApprovalTask.worklog_id.in_(worklog_ids)).order_by(ApprovalTask.version.desc(), ApprovalTask.id.desc())).all()
        for task in tasks:
            latest_tasks.setdefault(task.worklog_id, task)
    return items, latest_tasks, user_departments, project_department_labels, department_options


def parse_month_range(month: str | None) -> tuple[str, date, date]:
    """把 YYYY-MM 月份转换为本地自然月起止日期；未传时默认当前月。"""
    if month and month.strip():
        try:
            year_text, month_text = month.strip().split("-", 1)
            start = date(int(year_text), int(month_text), 1)
        except Exception as exc:
            raise HTTPException(400, "INVALID_MONTH") from exc
    else:
        today = today_local()
        start = date(today.year, today.month, 1)
    if start.month == 12:
        end = date(start.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(start.year, start.month + 1, 1) - timedelta(days=1)
    return start.strftime("%Y-%m"), start, end


def option_label_map(db: Session, category: str) -> dict[str, str]:
    """返回基础配置的 value -> label 映射，包含停用项以便历史数据仍可展示中文。"""
    return {item.value: item.label for item in config_option_rows(db, category, active_only=False)}


def monthly_ledger_dataset(
    db: Session,
    *,
    viewer: User | None = None,
    month: str | None = None,
    project_keyword: str | None = None,
    project_type: str | None = None,
    project_status: str | None = None,
    department_id: int | None = None,
    department_name: str | None = None,
    owner_user_id: int | None = None,
) -> tuple[str, date, date, list[WorklogMonthlyLedgerItem], list[str]]:
    """按项目聚合某个月的项目类工时，供月度台账列表和导出共用。"""
    month_label, period_start, period_end = parse_month_range(month)
    departments = db.scalars(select(Department)).all()
    department_index = DepartmentIndex(departments)
    selected_department_id = department_index.resolve(department_id, department_name)
    selected_department_ids = department_index.descendants(selected_department_id) if selected_department_id else set()
    project_type_labels = option_label_map(db, "project_category") | PROJECT_CATEGORY_LABELS
    project_status_labels = option_label_map(db, "project_status")
    project_query = select(Project).where(Project.status != "DELETED")
    if project_type:
        project_query = project_query.where(Project.project_type == project_type)
    if project_status:
        project_query = project_query.where(Project.status == project_status)
    if owner_user_id:
        project_query = project_query.where(Project.owner_user_id == owner_user_id)
    if project_keyword and project_keyword.strip():
        keyword = f"%{project_keyword.strip()}%"
        project_query = project_query.where(or_(Project.name.like(keyword), Project.code.like(keyword)))
    projects = list(db.scalars(project_query.order_by(Project.code, Project.id)).all())
    scoped_project_ids: set[int] | None = None
    scoped_user_ids: set[int] | None = None
    if viewer:
        scoped_project_ids, scoped_user_ids = worklog_scope_sets(db, viewer, "worklogs")
    if selected_department_ids:
        projects = [project for project in projects if project.department_id in selected_department_ids]
    option_department_ids = {project.department_id for project in projects if project.department_id}
    department_options = department_index.options(department_index.with_ancestors(option_department_ids), active_only=False)
    project_ids = [project.id for project in projects]
    if not project_ids:
        return month_label, period_start, period_end, [], department_options
    rows = list(
        db.scalars(
            select(Worklog).where(
                Worklog.project_id.in_(project_ids),
                Worklog.fill_date >= period_start,
                Worklog.fill_date <= period_end,
            )
        ).all()
    )
    rows_by_project: dict[int, list[Worklog]] = defaultdict(list)
    for row in rows:
        if viewer and not worklog_in_scope(row, scoped_project_ids, scoped_user_ids):
            continue
        rows_by_project[row.project_id].append(row)
    items: list[WorklogMonthlyLedgerItem] = []
    for project in projects:
        project_rows = rows_by_project.get(project.id, [])
        if not project_rows:
            continue
        approved_days = round(sum(float(row.quantity) for row in project_rows if row.status in {"APPROVED", "LOCKED"}), 2)
        pending_days = round(sum(float(row.quantity) for row in project_rows if row.status == "PENDING_APPROVAL"), 2)
        rejected_days = round(sum(float(row.quantity) for row in project_rows if row.status == "REJECTED"), 2)
        total_days = round(sum(float(row.quantity) for row in project_rows), 2)
        items.append(
            WorklogMonthlyLedgerItem(
                project_id=project.id,
                project_code=project.code,
                project_name=project.name,
                project_type=project.project_type,
                project_type_name=project_type_labels.get(project.project_type, project.project_type),
                project_status=project.status,
                project_status_name=project_status_labels.get(project.status, project.status),
                department_id=project.department_id,
                department_name=department_index.path(project.department_id) if project.department_id else (project.department_name or "未分配部门"),
                owner_user_id=project.owner_user_id,
                owner_name=project.owner_name or "未配置",
                user_count=len({row.user_id for row in project_rows}),
                approved_days=approved_days,
                pending_days=pending_days,
                rejected_days=rejected_days,
                total_days=total_days,
            )
        )
    items.sort(key=lambda item: (-item.total_days, item.project_code, item.project_id))
    return month_label, period_start, period_end, items, department_options


@app.get("/api/v1/worklogs/monthly-ledger", response_model=WorklogMonthlyLedgerList)
def list_worklog_monthly_ledger(
    month: str | None = None,
    project_keyword: str | None = None,
    project_type: str | None = None,
    project_status: str | None = None,
    department_id: int | None = Query(default=None, gt=0),
    department_name: str | None = None,
    owner_user_id: int | None = Query(default=None, gt=0),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> WorklogMonthlyLedgerList:
    """按项目汇总月度工时，默认当前月。"""
    user = require_admin_permission(db, "worklogs", x_demo_user_id)
    month_label, _, _, items, department_options = monthly_ledger_dataset(
        db,
        viewer=user,
        month=month,
        project_keyword=project_keyword,
        project_type=project_type,
        project_status=project_status,
        department_id=department_id,
        department_name=department_name,
        owner_user_id=owner_user_id,
    )
    return WorklogMonthlyLedgerList(
        month=month_label,
        total_projects=len(items),
        total_days=round(sum(item.total_days for item in items), 2),
        approved_days=round(sum(item.approved_days for item in items), 2),
        pending_days=round(sum(item.pending_days for item in items), 2),
        rejected_days=round(sum(item.rejected_days for item in items), 2),
        items=items,
        department_options=department_options,
    )


@app.get("/api/v1/worklogs/monthly-ledger/{project_id}/print", response_model=WorklogMonthlyLedgerPrintView)
def get_worklog_monthly_ledger_print(
    project_id: int,
    month: str | None = None,
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> WorklogMonthlyLedgerPrintView:
    """生成某项目某月已审批工时的人员汇总打印视图。"""
    user = require_admin_permission(db, "worklogs", x_demo_user_id)
    month_label, period_start, period_end = parse_month_range(month)
    project = db.get(Project, project_id)
    if not project or project.status == "DELETED":
        raise HTTPException(404, "PROJECT_NOT_FOUND")

    scoped_project_ids, scoped_user_ids = worklog_scope_sets(db, user, "worklogs")
    source_rows = list(
        db.scalars(
            select(Worklog).where(
                Worklog.project_id == project_id,
                Worklog.fill_date >= period_start,
                Worklog.fill_date <= period_end,
                Worklog.status.in_(["APPROVED", "LOCKED"]),
            )
        ).all()
    )
    grouped: dict[int, dict[str, object]] = {}
    for row in source_rows:
        if not worklog_in_scope(row, scoped_project_ids, scoped_user_ids):
            continue
        summary = grouped.setdefault(
            row.user_id,
            {"user_id": row.user_id, "user_name": row.user_name_snapshot or "未命名人员", "quantity": 0.0},
        )
        summary["quantity"] = round(float(summary["quantity"]) + float(row.quantity), 2)

    sorted_rows = sorted(grouped.values(), key=lambda item: (str(item["user_name"]), int(item["user_id"])))
    rows = [
        WorklogMonthlyLedgerPrintRow(
            index=index,
            user_id=int(item["user_id"]),
            user_name=str(item["user_name"]),
            quantity=round(float(item["quantity"]), 2),
        )
        for index, item in enumerate(sorted_rows, start=1)
    ]
    return WorklogMonthlyLedgerPrintView(
        month=month_label,
        project_id=project.id,
        project_name=project.name,
        project_owner_name=project.owner_name or "未配置",
        printed_by_name=user.name,
        printed_at=now_local(),
        rows=rows,
        total_quantity=round(sum(item.quantity for item in rows), 2),
    )


@app.get("/api/v1/worklogs/monthly-ledger/{project_id}/details", response_model=WorklogMonthlyLedgerDetailList)
def list_worklog_monthly_ledger_details(
    project_id: int,
    month: str | None = None,
    status: str | None = None,
    user_id: int | None = Query(default=None, gt=0),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> WorklogMonthlyLedgerDetailList:
    """查看某项目某月的工时明细，供月度台账下钻使用。"""
    user = require_admin_permission(db, "worklogs", x_demo_user_id)
    month_label, period_start, period_end = parse_month_range(month)
    project = db.get(Project, project_id)
    if not project or project.status == "DELETED":
        raise HTTPException(404, "PROJECT_NOT_FOUND")
    items, latest_tasks, user_departments, project_department_labels, _ = admin_worklog_dataset(
        db,
        viewer=user,
        period_start=period_start,
        period_end=period_end,
        project_id=project_id,
        status=status,
        user_id=user_id,
    )
    view_items = [
        admin_worklog_view(
            item,
            latest_tasks[item.id].serial_no if item.id in latest_tasks else None,
            user_departments.get(item.user_id, "未分配部门"),
            project_department_labels.get(item.project_id, "未分配部门"),
        )
        for item in items
    ]
    return WorklogMonthlyLedgerDetailList(
        month=month_label,
        project_id=project.id,
        project_name=project.name,
        items=view_items,
        summary={
            "quantity": round(sum(float(item.quantity) for item in items), 2),
            "approved_quantity": round(sum(float(item.quantity) for item in items if item.status in {"APPROVED", "LOCKED"}), 2),
            "pending_quantity": round(sum(float(item.quantity) for item in items if item.status == "PENDING_APPROVAL"), 2),
            "rejected_quantity": round(sum(float(item.quantity) for item in items if item.status == "REJECTED"), 2),
            "count": len(items),
        },
    )


@app.get("/api/v1/worklogs/monthly-ledger/export")
def export_worklog_monthly_ledger(
    mode: str = Query(default="summary", pattern="^(summary|details)$"),
    month: str | None = None,
    project_id: int | None = Query(default=None, gt=0),
    project_keyword: str | None = None,
    project_type: str | None = None,
    project_status: str | None = None,
    department_id: int | None = Query(default=None, gt=0),
    department_name: str | None = None,
    owner_user_id: int | None = Query(default=None, gt=0),
    status: str | None = None,
    user_id: int | None = Query(default=None, gt=0),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出工时月度台账汇总或某项目明细。"""
    user = require_access(db, "worklogs", "EXPORT", x_demo_user_id)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    if mode == "details":
        if not project_id:
            raise HTTPException(400, "PROJECT_REQUIRED")
        details = list_worklog_monthly_ledger_details(project_id, month, status, user_id, x_demo_user_id, db)
        writer.writerow(["项目", "月份", "工时单号", "填报人", "填报人部门", "项目部门", "项目阶段", "工时类型", "工作状态", "填报日期", "开始日期", "结束日期", "工时天数", "审批人", "审批状态", "工作描述"])
        status_names = {"DRAFT": "草稿", "PENDING_APPROVAL": "审批中", "APPROVED": "已通过", "REJECTED": "已驳回", "LOCKED": "已锁定"}
        work_type_names = option_label_map(db, "work_type") | {"PROJECT": "项目工时", "MANAGEMENT": "管理工时", "OTHER": "其它工时"}
        work_status_names = option_label_map(db, "work_status") | {"LOCAL": "本地", "BUSINESS_TRIP": "出差", "REMOTE": "异地办公", "LEAVE": "休假"}
        for item in details.items:
            writer.writerow([
                details.project_name,
                details.month,
                item.serial_no or "",
                item.user_name_snapshot,
                item.user_department_name,
                item.project_department_name,
                item.stage,
                work_type_names.get(item.work_type, item.work_type),
                work_status_names.get(item.work_status, item.work_status),
                item.fill_date,
                item.start_date,
                item.end_date,
                f"{float(item.quantity):g}",
                item.approver_name_snapshot or "",
                status_names.get(item.status, item.status),
                item.description,
            ])
        filename = f"xinye-worklog-monthly-ledger-details-{details.month}-{project_id}.csv"
    else:
        ledger = list_worklog_monthly_ledger(month, project_keyword, project_type, project_status, department_id, department_name, owner_user_id, x_demo_user_id, db)
        writer.writerow(["月份", "项目编号", "项目名称", "项目类型", "项目状态", "所属部门", "项目负责人", "本月填报人数", "本月审批通过人天", "本月审批中人天", "本月驳回人天", "本月合计填报人天"])
        for item in ledger.items:
            writer.writerow([
                ledger.month,
                item.project_code,
                item.project_name,
                item.project_type_name,
                item.project_status_name,
                item.department_name,
                item.owner_name,
                item.user_count,
                f"{item.approved_days:g}",
                f"{item.pending_days:g}",
                f"{item.rejected_days:g}",
                f"{item.total_days:g}",
            ])
        filename = f"xinye-worklog-monthly-ledger-summary-{ledger.month}.csv"
    return StreamingResponse(iter([output.getvalue().encode("utf-8-sig")]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


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
    user = require_admin_permission(db, "worklogs", x_demo_user_id)
    if page < 1:
        raise HTTPException(400, "INVALID_PAGE")
    if page_size < 1 or page_size > 200:
        raise HTTPException(400, "INVALID_PAGE_SIZE")
    if period_start and period_end and period_start > period_end:
        raise HTTPException(400, "INVALID_DATE_RANGE")
    items, latest_tasks, user_departments, project_department_labels, department_options = admin_worklog_dataset(
        db,
        viewer=user,
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
    user = require_access(db, "worklogs", "EXPORT", x_demo_user_id)
    if period_start and period_end and period_start > period_end:
        raise HTTPException(400, "INVALID_DATE_RANGE")
    items, latest_tasks, user_departments, project_department_labels, _ = admin_worklog_dataset(
        db,
        viewer=user,
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
    work_type_names = option_label_map(db, "work_type") | {"PROJECT": "项目工时", "MANAGEMENT": "管理工时", "OTHER": "其它工时"}
    work_status_names = option_label_map(db, "work_status") | {"LOCAL": "本地", "BUSINESS_TRIP": "出差", "REMOTE": "异地办公", "LEAVE": "休假"}
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["工时单号", "填报人", "填报人部门", "项目部门", "项目", "项目阶段", "工时类型", "工作状态", "填报日期", "开始日期", "结束日期", "工时天数", "审批人", "审批状态", "工作描述", "提交时间", "处理时间", "审批意见"])
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
            item.fill_date,
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


@app.patch("/api/v1/admin/worklogs/{worklog_id}", response_model=AdminWorklogView)
def update_admin_worklog(worklog_id: int, payload: WorklogUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> AdminWorklogView:
    """管理员修改工时内容，保留现有审批状态和审批任务。"""
    admin = require_admin_permission(db, "worklogs", x_demo_user_id)
    require_access(db, "worklogs", "EDIT", x_demo_user_id)
    item = db.get(Worklog, worklog_id)
    if not item:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    ensure_worklog_in_scope(db, admin, item, "worklogs")
    project = worklog_project_for_payload(db, payload.work_type, payload.project_id)
    validate_worklog_dates(db, item.user_id, payload.start_date, payload.end_date, item.id)
    validate_worklog_quantity(db, payload.start_date, payload.end_date, payload.quantity)
    validate_worklog_options(db, payload.stage, payload.work_type, payload.work_status)
    old_value = f"{item.project_name_snapshot}|{item.stage}|{item.fill_date}|{item.start_date}|{item.end_date}|{item.quantity}|{item.description}"
    item.project_id = project.id if project else None
    item.project_name_snapshot = project.name if project else "非项目工时"
    item.stage = payload.stage
    item.work_type = payload.work_type
    item.work_status = payload.work_status
    item.fill_date = payload.fill_date or payload.start_date
    item.start_date = payload.start_date
    item.end_date = payload.end_date
    item.quantity = payload.quantity
    item.unit = "DAY"
    item.description = payload.description
    new_value = f"{item.project_name_snapshot}|{item.stage}|{item.fill_date}|{item.start_date}|{item.end_date}|{item.quantity}|{item.description}"
    audit(db, "worklog", item.id, "ADMIN_UPDATE", admin.id, item.status, item.status, f"{old_value} -> {new_value}")
    db.commit()
    db.refresh(item)
    project_departments = {project.id: project.department_name or "未分配部门"} if project else {0: "非项目工时"}
    department = db.get(Department, project.department_id) if project and project.department_id else None
    if project and department and department.parent_name:
        project_departments[project.id] = department.parent_name
    user = db.get(User, item.user_id)
    user_department = db.get(Department, user.department_id).name if user and user.department_id and db.get(Department, user.department_id) else "未分配部门"
    task = db.scalar(select(ApprovalTask).where(ApprovalTask.worklog_id == item.id).order_by(ApprovalTask.version.desc(), ApprovalTask.id.desc()))
    return admin_worklog_view(item, task.serial_no if task else None, user_department, project_departments.get(project.id if project else 0, "非项目工时"))


@app.delete("/api/v1/admin/worklogs/{worklog_id}")
def delete_admin_worklog(worklog_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """管理员删除工时及关联审批通知，保留删除审计事件。"""
    admin = require_admin_permission(db, "worklogs", x_demo_user_id)
    require_access(db, "worklogs", "DELETE", x_demo_user_id)
    item = db.get(Worklog, worklog_id)
    if not item:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    ensure_worklog_in_scope(db, admin, item, "worklogs")
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
    task = db.scalar(select(ApprovalTask).where(ApprovalTask.worklog_id == item.id).order_by(ApprovalTask.version.desc(), ApprovalTask.id.desc()))
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
    validate_worklog_quantity(db, payload.start_date, payload.end_date, payload.quantity)
    validate_worklog_options(db, payload.stage, payload.work_type, payload.work_status)
    project = worklog_project_for_payload(db, payload.work_type, payload.project_id)
    item = Worklog(user_id=user.id, user_name_snapshot=user.name, project_id=project.id if project else None, project_name_snapshot=project.name if project else "非项目工时", stage=payload.stage, work_type=payload.work_type, work_status=payload.work_status, fill_date=payload.fill_date or payload.start_date, start_date=payload.start_date, end_date=payload.end_date, quantity=payload.quantity, unit=payload.unit, description=payload.description, status="DRAFT")
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
    validate_worklog_quantity(db, payload.start_date, payload.end_date, payload.quantity)
    validate_worklog_options(db, payload.stage, payload.work_type, payload.work_status)
    project = worklog_project_for_payload(db, payload.work_type, payload.project_id)
    for key, value in payload.model_dump(exclude={"fill_date", "project_id"}).items():
        setattr(item, key, value)
    item.fill_date = payload.fill_date or payload.start_date
    item.project_id = project.id if project else None
    item.project_name_snapshot = project.name if project else "非项目工时"
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


@app.post("/api/v1/worklogs/{worklog_id}/withdraw", response_model=WorklogView)
def withdraw_worklog(worklog_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> WorklogView:
    """提交人撤回审批中工时，恢复为草稿后可重新编辑提交。"""
    user = current_user(db, x_demo_user_id)
    item = db.get(Worklog, worklog_id)
    if not item:
        raise HTTPException(404, "WORKLOG_NOT_FOUND")
    return withdraw_worklog_item(db, item, user)


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


@app.post("/api/v1/approvals/batch-approve", response_model=BatchApprovalResult)
def batch_approve_tasks(payload: BatchApprovalRequest, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> BatchApprovalResult:
    """批量通过工时审批；逐条复用单条审批逻辑，保留二级流转、通知和审计。"""
    current_user(db, x_demo_user_id)
    require_access(db, "approvals", "APPROVE", x_demo_user_id)
    results: list[BatchApprovalResultItem] = []
    for task_id in dict.fromkeys(payload.task_ids):
        try:
            task = db.get(ApprovalTask, task_id)
            if not task:
                raise HTTPException(404, "APPROVAL_NOT_FOUND")
            view = approve_task(task_id, ApprovalAction(version=task.version, comment=payload.comment), x_demo_user_id, db)
            results.append(BatchApprovalResultItem(task_id=task_id, success=True, worklog_id=view.worklog_id, status=view.worklog.status))
        except HTTPException as exc:
            db.rollback()
            results.append(BatchApprovalResultItem(task_id=task_id, success=False, message=str(exc.detail)))
        except Exception as exc:
            db.rollback()
            logger.exception("batch approve task failed: %s", task_id)
            results.append(BatchApprovalResultItem(task_id=task_id, success=False, message=str(exc)))
    success_count = sum(1 for item in results if item.success)
    return BatchApprovalResult(success_count=success_count, failed_count=len(results) - success_count, results=results)


@app.post("/api/v1/approvals/batch-reject", response_model=BatchApprovalResult)
def batch_reject_tasks(payload: BatchRejectionRequest, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> BatchApprovalResult:
    """批量驳回工时审批；每条审批记录写入同一个驳回原因。"""
    current_user(db, x_demo_user_id)
    require_access(db, "approvals", "APPROVE", x_demo_user_id)
    results: list[BatchApprovalResultItem] = []
    for task_id in dict.fromkeys(payload.task_ids):
        try:
            task = db.get(ApprovalTask, task_id)
            if not task:
                raise HTTPException(404, "APPROVAL_NOT_FOUND")
            view = reject_task(task_id, RejectionAction(version=task.version, reason=payload.reason), x_demo_user_id, db)
            results.append(BatchApprovalResultItem(task_id=task_id, success=True, worklog_id=view.worklog_id, status=view.worklog.status))
        except HTTPException as exc:
            db.rollback()
            results.append(BatchApprovalResultItem(task_id=task_id, success=False, message=str(exc.detail)))
        except Exception as exc:
            db.rollback()
            logger.exception("batch reject task failed: %s", task_id)
            results.append(BatchApprovalResultItem(task_id=task_id, success=False, message=str(exc)))
    success_count = sum(1 for item in results if item.success)
    return BatchApprovalResult(success_count=success_count, failed_count=len(results) - success_count, results=results)


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
    next_task = create_next_worklog_task(db, item, task, user, payload.comment)
    if next_task:
        item.status = "PENDING_APPROVAL"
        item.approval_comment = payload.comment
    else:
        item.status = "APPROVED"
        item.approved_at = task.processed_at
        item.approver_user_id = user.id
        item.approver_name_snapshot = user.name
        item.approval_comment = payload.comment
    # v3.0.61 起工时审批只推进审批状态，不再折算人员成本、不再写 PERSONNEL_COST 流水；
    # 人工成本统一由财务按项目 + 核算月份录入并走一级费用复核。
    db.commit()
    db.refresh(next_task or task)
    return task_view(db, next_task or task)


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
    user_id: int | None = None,
    project_id: int | None = None,
    work_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> ReportView:
    """按日期、部门树、人员、项目、工时类型和审批状态汇总工时看板数据。"""
    start = period_start or today_local().replace(day=1)
    end = period_end or today_local()
    if start > end:
        raise HTTPException(400, "INVALID_DATE_RANGE")

    department_index = DepartmentIndex(db.scalars(select(Department)).all())
    projects = db.scalars(select(Project)).all()
    projects_by_id = {item.id: item for item in projects}
    users = db.scalars(select(User)).all()
    user_department_ids = {item.id: item.department_id for item in users}

    project_department = {project.id: department_index.root_name(project.department_id) if project.department_id else "未分配部门" for project in projects}
    project_department_ids = {project.id: project.department_id for project in projects}
    user_department = {user.id: department_index.root_name(user.department_id) if user.department_id else "未分配部门" for user in users}
    work_type_names = option_label_map(db, "work_type") | {"PROJECT": "项目工时", "MANAGEMENT": "管理工时", "OTHER": "其他工时"}
    department_ids_with_data = {project.department_id for project in projects if project.status != "DELETED" and project.department_id} | {user.department_id for user in users if user.department_id}
    department_options = department_index.options(department_index.with_ancestors(department_ids_with_data), active_only=False)
    selected_department_id = department_index.resolve(department_id, department_name)
    selected_department_ids = department_index.descendants(selected_department_id) if selected_department_id else set()

    all_rows = db.scalars(select(Worklog).where(Worklog.start_date <= end, Worklog.end_date >= start)).all()
    def worklog_department_id(item: Worklog) -> int | None:
        return project_department_ids.get(item.project_id) if item.project_id else user_department_ids.get(item.user_id)

    def worklog_department_name(item: Worklog) -> str:
        return project_department.get(item.project_id) if item.project_id else user_department.get(item.user_id, "未分配部门")

    scoped_rows_before_status = [
        item for item in all_rows
        if item.unit == "DAY"
        and (not selected_department_ids or worklog_department_id(item) in selected_department_ids)
        and (not user_id or item.user_id == user_id)
        and (not project_id or item.project_id == project_id)
        and (not work_type or item.work_type == work_type)
    ]
    scoped_rows = [item for item in scoped_rows_before_status if not status or item.status == status]
    approved_rows = [item for item in scoped_rows if item.status in {"APPROVED", "LOCKED"}]
    scoped_projects = [project for project in projects if project.status != "DELETED" and (not selected_department_ids or project.department_id in selected_department_ids) and (not project_id or project.id == project_id)]
    scoped_project_ids = {project.id for project in scoped_projects}
    eligible_users = [
        item for item in users
        if item.employment_status == "ACTIVE"
        and (not selected_department_ids or item.department_id in selected_department_ids)
        and (not user_id or item.id == user_id)
    ]
    if (project_id or work_type) and not user_id:
        scoped_user_ids_before_status = {item.user_id for item in scoped_rows_before_status}
        eligible_users = [item for item in eligible_users if item.id in scoped_user_ids_before_status]
    eligible_user_ids = {item.id for item in eligible_users}
    completion_end = min(end, today_local())
    required_workdays: list[date] = []
    if start <= completion_end:
        cursor = start
        while cursor <= completion_end:
            if is_statutory_workday(db, cursor):
                required_workdays.append(cursor)
            cursor += timedelta(days=1)
    required_user_days = len(required_workdays) * len(eligible_user_ids)
    completion_statuses = {status} if status else {"PENDING_APPROVAL", "APPROVED", "LOCKED"}
    filled_user_day_keys: set[tuple[int, date]] = set()
    required_workday_set = set(required_workdays)
    for item in scoped_rows:
        if item.user_id not in eligible_user_ids or item.status not in completion_statuses:
            continue
        cursor = max(item.start_date, start)
        last = min(item.end_date, completion_end)
        while cursor <= last:
            if cursor in required_workday_set and is_statutory_workday(db, cursor):
                filled_user_day_keys.add((item.user_id, cursor))
            cursor += timedelta(days=1)
    filled_user_days = len(filled_user_day_keys)
    missing_user_days = max(required_user_days - filled_user_days, 0)
    fill_completion_rate = round(filled_user_days / required_user_days * 100, 1) if required_user_days else 0
    project_actual_days: dict[int, float] = defaultdict(float)
    department_actual_cost: dict[str, float] = defaultdict(float)
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
    by_project_kind: dict[str, float] = {}
    by_unit: dict[str, float] = {}
    by_project_unit: dict[tuple[str, str], float] = {}
    by_department_unit: dict[tuple[str, str], float] = {}
    by_day_unit: dict[tuple[str, str], float] = {}
    for item in approved_rows:
        quantity = float(item.quantity)
        unit = "DAY"
        department = worklog_department_name(item)
        is_project_work = item.work_type in PROJECT_WORK_TYPES and item.project_id is not None
        by_project_kind["项目类工时" if is_project_work else "非项目类工时"] = by_project_kind.get("项目类工时" if is_project_work else "非项目类工时", 0) + quantity
        if is_project_work:
            project_actual_days[item.project_id] += quantity
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
        work_type_label = work_type_names.get(item.work_type, item.work_type)
        by_work_type[work_type_label] = by_work_type.get(work_type_label, 0) + quantity
        by_work_type_unit[(work_type_label, unit)] = by_work_type_unit.get((work_type_label, unit), 0) + quantity
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

    # 人工成本一律以「人工成本结转单」为准，不再按日成本折算工时；
    # 取数与项目明细保持一致，只统计期间内发生结转金额。
    labor_cost_rows = db.scalars(
        select(ProjectLedgerEntry).where(
            ProjectLedgerEntry.entry_type == "PERSONNEL_COST",
            ProjectLedgerEntry.occurred_on.is_not(None),
            ProjectLedgerEntry.occurred_on >= start,
            ProjectLedgerEntry.occurred_on <= end,
        )
    ).all()
    project_actual_cost: dict[int, float] = defaultdict(float)
    for row in labor_cost_rows:
        if row.project_id in scoped_project_ids:
            project_actual_cost[row.project_id] += float(row.amount or 0)
    for project_id, cost in project_actual_cost.items():
        department_actual_cost[project_department.get(project_id, "未分配部门")] += cost

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
    approval_node_counts: dict[str, int] = {}
    pending_worklog_ids = [item.id for item in scoped_rows if item.status == "PENDING_APPROVAL"]
    if pending_worklog_ids:
        tasks = db.scalars(
            select(ApprovalTask)
            .where(ApprovalTask.worklog_id.in_(pending_worklog_ids), ApprovalTask.status == "PENDING")
            .order_by(ApprovalTask.version.desc(), ApprovalTask.step_order.desc(), ApprovalTask.id.desc())
        ).all()
        latest_pending_tasks: dict[int, ApprovalTask] = {}
        for task in tasks:
            latest_pending_tasks.setdefault(task.worklog_id, task)
        for task in latest_pending_tasks.values():
            node_name = task.step_name or "待审批"
            approval_node_counts[node_name] = approval_node_counts.get(node_name, 0) + 1
    return ReportView(
        scope={"period_start": str(start), "period_end": str(end), "department_name": department_index.path(selected_department_id) if selected_department_id else "全部部门", "department_options": department_options, "status": ["APPROVED", "LOCKED"]},
        metrics={"total_quantity": round(sum(by_project.values()), 2), "total_days": round(by_unit.get("DAY", 0), 2), "budget_days": round(budget_days, 2), "actual_cost": round(sum(project_actual_cost.values()), 2), "budget_cost": round(budget_cost, 2), "budget_usage_rate": round(actual_days / budget_days * 100, 1) if budget_days else 0, "cost_usage_rate": round(sum(project_actual_cost.values()) / budget_cost * 100, 1) if budget_cost else 0, "over_budget_project_count": over_budget_project_count, "over_budget_cost_project_count": over_budget_cost_project_count, "user_count": len(user_ids), "project_count": len(project_ids), "execution_project_count": sum(1 for project_id in project_ids if projects_by_id.get(project_id) and projects_by_id[project_id].status == "ACTIVE"), "pending_count": pending_count, "approved_count": len(approved_rows), "submitted_count": len(scoped_rows), "rejected_count": status_counts.get("REJECTED", 0), "approval_rate": round((len(approved_rows) / (len(approved_rows) + status_counts.get("REJECTED", 0)) * 100), 1) if len(approved_rows) + status_counts.get("REJECTED", 0) else 0, "overdue_pending_count": overdue_pending_count, "fill_completion_rate": fill_completion_rate, "required_user_days": required_user_days, "filled_user_days": filled_user_days, "missing_user_days": missing_user_days, "active_user_count": len(eligible_user_ids)},
        breakdowns={"by_project": breakdown(by_project), "by_project_unit": unit_breakdown(by_project_unit), "by_project_budget_actual": project_budget_actual, "by_project_cost": project_cost_rows, "by_department_cost": department_cost_rows, "by_project_stage": [{"name": project, "stage": stage, "quantity": round(quantity, 2)} for (project, stage), quantity in sorted(by_project_stage.items(), key=lambda pair: pair[1], reverse=True)], "by_project_stage_unit": project_stage_unit_breakdown(by_project_stage_unit), "by_stage": breakdown(by_stage), "by_stage_unit": unit_breakdown(by_stage_unit), "by_user": breakdown(by_user), "by_user_unit": unit_breakdown(by_user_unit), "by_status": breakdown(by_status), "by_status_unit": unit_breakdown(by_status_unit), "approval_status": [{"name": name, "quantity": quantity} for name, quantity in sorted(status_counts.items(), key=lambda pair: pair[1], reverse=True)], "by_approval_node": [{"name": name, "quantity": quantity} for name, quantity in sorted(approval_node_counts.items(), key=lambda pair: pair[1], reverse=True)], "by_work_type": breakdown(by_work_type), "by_work_type_unit": unit_breakdown(by_work_type_unit), "by_project_kind": breakdown(by_project_kind), "by_project_kind_unit": unit_breakdown({(name, "DAY"): quantity for name, quantity in by_project_kind.items()}), "by_department": breakdown(by_department), "by_department_unit": unit_breakdown(by_department_unit), "by_day_unit": unit_breakdown(by_day_unit), "by_unit": breakdown(by_unit)},
        generated_at=now_local(),
    )


@app.get("/api/v1/reports/workload/export")
def export_workload(
    period_start: date | None = None,
    period_end: date | None = None,
    department_id: int | None = Query(default=None, gt=0),
    department_name: str | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
    work_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """按看板筛选条件导出天数工时明细 CSV。"""
    user = require_access(db, "reports", "EXPORT")
    start = period_start or today_local().replace(day=1)
    end = period_end or today_local()
    if start > end:
        raise HTTPException(400, "INVALID_DATE_RANGE")

    department_index = DepartmentIndex(db.scalars(select(Department)).all())
    projects = db.scalars(select(Project)).all()
    projects_by_id = {item.id: item for item in projects}
    users = db.scalars(select(User)).all()
    user_department_ids = {item.id: item.department_id for item in users}
    user_department = {user.id: department_index.root_name(user.department_id) if user.department_id else "未分配部门" for user in users}
    project_department = {project.id: department_index.root_name(project.department_id) if project.department_id else "未分配部门" for project in projects}
    project_department_ids = {project.id: project.department_id for project in projects}
    selected_department_id = department_index.resolve(department_id, department_name)
    selected_department_ids = department_index.descendants(selected_department_id) if selected_department_id else set()
    visible_project_ids = project_scope_ids(db, user, "reports")

    def worklog_department_id(item: Worklog) -> int | None:
        return project_department_ids.get(item.project_id) if item.project_id else user_department_ids.get(item.user_id)

    def worklog_department_name(item: Worklog) -> str:
        return project_department.get(item.project_id) if item.project_id else user_department.get(item.user_id, "未分配部门")

    items = db.scalars(select(Worklog).where(Worklog.start_date <= end, Worklog.end_date >= start, Worklog.unit == "DAY").order_by(Worklog.start_date, Worklog.id)).all()
    items = [
        item for item in items
        if (visible_project_ids is None or item.project_id is None or item.project_id in visible_project_ids)
        and (not selected_department_ids or worklog_department_id(item) in selected_department_ids)
        and (not user_id or item.user_id == user_id)
        and (not project_id or item.project_id == project_id)
        and (not work_type or item.work_type == work_type)
        and (not status or item.status == status)
    ]
    worklog_ids = [item.id for item in items]
    latest_tasks: dict[int, ApprovalTask] = {}
    if worklog_ids:
        tasks = db.scalars(select(ApprovalTask).where(ApprovalTask.worklog_id.in_(worklog_ids)).order_by(ApprovalTask.version.desc(), ApprovalTask.id.desc())).all()
        for task in tasks:
            latest_tasks.setdefault(task.worklog_id, task)

    status_names = {"DRAFT": "草稿", "PENDING_APPROVAL": "审批中", "APPROVED": "已通过", "REJECTED": "已驳回", "LOCKED": "已锁定"}
    work_type_names = option_label_map(db, "work_type") | {"PROJECT": "项目工时", "MANAGEMENT": "管理工时", "OTHER": "其它工时"}
    work_status_names = option_label_map(db, "work_status") | {"LOCAL": "本地", "BUSINESS_TRIP": "出差", "REMOTE": "异地办公", "LEAVE": "休假"}
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["工时单号", "提交人", "一级部门", "项目", "项目阶段", "工时类型", "工作状态", "开始日期", "结束日期", "工时天数", "审批人", "审批状态", "工作描述", "提交时间", "处理时间", "审批意见"])
    for item in items:
        task = latest_tasks.get(item.id)
        writer.writerow([
            task.serial_no if task else "",
            item.user_name_snapshot,
            worklog_department_name(item),
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
    elif item.source_type in {"project_cost_project_expense", "project_cost_personnel_cost"}:
        source = db.get(ProjectCostEntry, item.source_id)
        if source:
            kind_label = PROJECT_COST_KIND_LABELS.get(source.entry_kind, "项目成本单")
            source_label = f"{kind_label} {source.cost_no}"
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


def validated_schedule_time(raw: str | None) -> str | None:
    """校验提醒时刻；空值表示沿用默认时刻，非法值直接拒绝保存。"""
    if raw is None:
        return None
    text = (raw or "").strip()
    if not text:
        return ""
    if not parse_reminder_times(text):
        raise HTTPException(400, "NOTIFICATION_POLICY_REMIND_TIME_INVALID")
    return text


def validated_target_ids(raw: str | None) -> str | None:
    """校验提醒对象 id 列表，必须是整数数组文本。"""
    if raw is None:
        return None
    text = (raw or "").strip()
    if not text:
        return "[]"
    try:
        parsed = json.loads(text)
    except ValueError:
        raise HTTPException(400, "NOTIFICATION_POLICY_TARGET_IDS_INVALID")
    if not isinstance(parsed, list) or any(not isinstance(item, int) for item in parsed):
        raise HTTPException(400, "NOTIFICATION_POLICY_TARGET_IDS_INVALID")
    return json.dumps(parsed)


def apply_policy_schedule_fields(policy: NotificationPolicy, payload: NotificationPolicyUpdate) -> None:
    """把定时填报提醒相关字段写入策略；未提交的字段保持原值。"""
    if payload.schedule_time is not None:
        policy.schedule_time = validated_schedule_time(payload.schedule_time)
    if payload.target_scope:
        policy.target_scope = payload.target_scope
    if payload.target_ids is not None:
        policy.target_ids = validated_target_ids(payload.target_ids)
    if payload.only_unfilled is not None:
        policy.only_unfilled = payload.only_unfilled


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
        apply_policy_schedule_fields(policy, item)
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
    apply_policy_schedule_fields(policy, payload)
    audit(db, "notification_policy", policy.id, "UPDATE", admin.id, None, "ENABLED" if policy.enabled else "DISABLED")
    db.commit()
    db.refresh(policy)
    return NotificationPolicyView.model_validate(policy)


@app.post("/api/v1/integrations/worklog-fill-reminder/run", response_model=WorklogFillReminderRunResult)
def run_worklog_fill_reminder(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> WorklogFillReminderRunResult:
    """按当前策略立即发送一次填报提醒，用于配置完成后验证通知对象和渠道。"""
    require_admin_permission(db, "integrations", x_demo_user_id)
    require_access(db, "integrations", "CONFIGURE", x_demo_user_id)
    policy = notification_policy(db, WORKLOG_FILL_REMINDER_TYPE)
    if not policy or not policy.enabled:
        raise HTTPException(409, "WORKLOG_FILL_REMINDER_DISABLED")
    return WorklogFillReminderRunResult(**run_worklog_fill_reminder_scan_once(force=True))


@app.post("/api/v1/integrations/worklog-fill-reminder-t1/run", response_model=WorklogFillReminderRunResult)
def run_worklog_fill_reminder_t1(x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> WorklogFillReminderRunResult:
    """按当前策略立即发送一次 T-1 补漏提醒，用于验证补填提醒的对象和渠道。"""
    require_admin_permission(db, "integrations", x_demo_user_id)
    require_access(db, "integrations", "CONFIGURE", x_demo_user_id)
    policy = notification_policy(db, WORKLOG_FILL_REMINDER_T1_TYPE)
    if not policy or not policy.enabled:
        raise HTTPException(409, "WORKLOG_FILL_REMINDER_T1_DISABLED")
    return WorklogFillReminderRunResult(**run_worklog_fill_reminder_t1_scan_once(force=True))


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


COST_REVIEW_RESULT_LABELS = {"APPROVED": "复核通过", "REJECTED": "复核驳回", "REVERSED": "已冲销", "DRAFT": "草稿", "PENDING_REVIEW": "待复核"}


def cost_review_notification_payload(db: Session, notification: SystemNotification) -> dict[str, object] | None:
    """解析费用复核类通知对应的来源单据，供发送与失败重试共用同一份口径。"""
    if notification.source_type == "payment":
        payment = db.get(Payment, notification.source_id)
        if not payment:
            return None
        project = db.get(Project, payment.project_id)
        applicant = db.get(User, payment.submitted_by) if payment.submitted_by else None
        reviewer = db.get(User, payment.approved_by) if payment.approved_by else None
        return {
            "document_label": "合同付款单",
            "serial_no": payment.payment_no,
            "project_name": project.name if project else "",
            "amount": float(payment.amount or 0),
            "submitter_name": applicant.name if applicant else "系统",
            "status_label": COST_REVIEW_RESULT_LABELS.get(payment.status, "待复核"),
            "actor_name": reviewer.name if reviewer else "系统",
            "page": "paymentDetail",
        }
    entry = db.get(ProjectCostEntry, notification.source_id)
    if not entry:
        return None
    project = db.get(Project, entry.project_id)
    applicant = db.get(User, entry.applicant_user_id) if entry.applicant_user_id else None
    reviewer = db.get(User, entry.reviewed_by) if entry.reviewed_by else None
    return {
        "document_label": PROJECT_COST_KIND_LABELS.get(entry.entry_kind, "项目成本单"),
        "serial_no": entry.cost_no,
        "project_name": project.name if project else "",
        "amount": float(entry.amount or 0),
        "submitter_name": applicant.name if applicant else "系统",
        "status_label": COST_REVIEW_RESULT_LABELS.get(entry.status, "待复核"),
        "actor_name": reviewer.name if reviewer else "系统",
        "page": PROJECT_COST_KIND_PAGES.get(entry.entry_kind, "projectExpenses"),
    }


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
    if notification.notification_type in {"PENDING_PAYMENT_REVIEW", "PENDING_EXPENSE_REVIEW", "PENDING_LABOR_REVIEW", "COST_REVIEW_RESULT"}:
        payload = cost_review_notification_payload(db, notification)
        recipient = db.get(User, notification.recipient_user_id) if notification.recipient_user_id else None
        if not payload or not recipient:
            raise HTTPException(404, "NOTIFICATION_SOURCE_NOT_FOUND")
        channel = notification_policy_channel(db, notification.notification_type)
        if channel and not notification_policy_enabled(db, notification.notification_type):
            raise HTTPException(409, "NOTIFICATION_POLICY_DISABLED")
        base = os.getenv("SYSTEM_PUBLIC_URL", "http://localhost:8088").rstrip("/")
        deep_link = f"{base}/?page={payload['page']}&id={notification.source_id}"
        if notification.notification_type == "COST_REVIEW_RESULT":
            result = feishu.notify_settlement_result(
                recipient.name,
                str(payload["document_label"]),
                str(payload["serial_no"]),
                str(payload["project_name"]),
                float(payload["amount"]),
                str(payload["status_label"]),
                deep_link,
                recipient.open_id,
                channel=channel,
                approver_name=str(payload["actor_name"]),
            )
        else:
            result = feishu.notify_cash_approval_submitted(
                recipient.name,
                str(payload["submitter_name"]),
                str(payload["document_label"]),
                str(payload["serial_no"]),
                str(payload["project_name"]),
                float(payload["amount"]),
                deep_link,
                recipient.open_id,
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
        db.refresh(notification)
        return integration_notification_view(db, notification)
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
    supervisor = supervisor_for_user(db, applicant)
    if supervisor:
        return supervisor
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


COST_REVIEW_PATH_STATUS = {"PENDING_REVIEW": "CURRENT", "APPROVED": "DONE", "REVERSED": "DONE", "REJECTED": "REJECTED"}


def payment_workflow_path_views(db: Session, payment: Payment) -> list[WorkflowPathNodeView]:
    """返回合同付款单的复核路径。

    v3.0.61 起合同付款只走一级费用复核，未挂在历史流程实例上的单据固定展示单节点路径；
    历史多级流程实例仍按实例快照展开，保证旧单据的审批轨迹可追溯。
    """
    instance = db.get(WorkflowInstance, payment.current_workflow_instance_id) if payment.current_workflow_instance_id else None
    if not instance:
        return [
            WorkflowPathNodeView(
                sequence=1,
                node_code="COST_REVIEW",
                node_name="费用复核",
                approval_mode="ANY",
                assignees=[{"id": user.id, "name": user.name} for user in cost_reviewer_users(db)],
                status=COST_REVIEW_PATH_STATUS.get(payment.status, "WAITING"),
            )
        ]
    try:
        path = json.loads(instance.snapshot_json or "{}").get("nodes", [])
    except json.JSONDecodeError:
        path = []
    tasks = list(db.scalars(select(WorkflowTask).where(WorkflowTask.workflow_instance_id == instance.id)).all())
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
        amount_without_tax=float(expense.amount_without_tax or 0),
        tax_rate=float(expense.tax_rate or 0),
        tax_amount=float(expense.tax_amount or 0),
        cost_amount=float(expense.cost_amount),
        budget_item_id=expense.budget_item_id,
        budget_item_name=expense.budget_item_name_snapshot,
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
    apply_tax_amount_fields(expense, payload.amount, payload.tax_rate, payload.amount_without_tax)
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


PROJECT_COST_KIND_LABELS = {"PROJECT_EXPENSE": "项目费用单", "PERSONNEL_COST": "人工成本结转单"}
PROJECT_COST_KIND_RESOURCES = {"PROJECT_EXPENSE": "project_expenses", "PERSONNEL_COST": "labor_costs"}
PROJECT_COST_KIND_PREFIXES = {"PROJECT_EXPENSE": "CE", "PERSONNEL_COST": "LC"}
PROJECT_COST_LEDGER_TYPES = {"PROJECT_EXPENSE": "PROJECT_EXPENSE_COST", "PERSONNEL_COST": "PERSONNEL_COST"}
PROJECT_COST_KIND_PAGES = {"PROJECT_EXPENSE": "expenseDetail", "PERSONNEL_COST": "expenseDetail"}
PROJECT_COST_KIND_NOTIFICATIONS = {"PROJECT_EXPENSE": "PENDING_EXPENSE_REVIEW", "PERSONNEL_COST": "PENDING_LABOR_REVIEW"}
EDITABLE_COST_ENTRY_STATUSES = {"DRAFT", "REJECTED"}


def cost_attachment_root() -> Path:
    """返回项目成本单附件持久化目录，并确保目录存在。"""
    root = Path(os.getenv("PROJECT_COST_ATTACHMENT_DIR", "/app/data/project-cost-attachments"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def cost_attachment_path(attachment: ProjectCostAttachment) -> Path:
    """解析项目成本单附件路径并阻止随机存储名越界。"""
    root = cost_attachment_root().resolve()
    path = (root / attachment.storage_name).resolve()
    if path.parent != root:
        raise HTTPException(500, "PROJECT_COST_ATTACHMENT_STORAGE_INVALID")
    return path


def cost_attachment_view(db: Session, attachment: ProjectCostAttachment) -> ProjectCostAttachmentView:
    """将项目成本单附件实体转换为安全的前端响应。"""
    uploader = db.get(User, attachment.uploaded_by)
    kind = attachment_preview_kind(attachment.file_name)
    return ProjectCostAttachmentView(
        id=attachment.id,
        entry_id=attachment.entry_id,
        file_name=attachment.file_name,
        mime_type=attachment.mime_type,
        file_size=attachment.file_size,
        uploaded_by=attachment.uploaded_by,
        uploaded_by_name=uploader.name if uploader else "系统",
        created_at=attachment.created_at,
        can_preview=kind != "download",
        preview_kind=kind,
    )


def cost_entry_attachment_views(db: Session, entry_id: int) -> list[ProjectCostAttachmentView]:
    rows = db.scalars(select(ProjectCostAttachment).where(ProjectCostAttachment.entry_id == entry_id).order_by(ProjectCostAttachment.id)).all()
    return [cost_attachment_view(db, item) for item in rows]


def project_cost_kind(entry_kind: str | None) -> str:
    value = (entry_kind or "PROJECT_EXPENSE").strip().upper()
    if value not in PROJECT_COST_KIND_LABELS:
        raise HTTPException(400, "COST_ENTRY_KIND_INVALID")
    return value


def cost_entry_resource(entry_kind: str | None) -> str:
    return PROJECT_COST_KIND_RESOURCES[project_cost_kind(entry_kind)]


LABOR_BUDGET_PREDICATES = (
    lambda item: item.code == "LABOR_COST",
    lambda item: item.source_kind == "LABOR",
    lambda item: "人工" in (item.name or ""),
)


def labor_budget_item(db: Session, project_id: int) -> ProjectBudgetItem | None:
    """返回项目的人工费用预算项；人工成本结转固定归入该项，不依赖界面选择。

    按「预算项编码 -> 来源类型 -> 名称含人工」逐级匹配，每级优先取启用项，
    避免模板被改名或排序调整后把人工成本归到别的预算项上。
    """
    items = db.scalars(select(ProjectBudgetItem).where(ProjectBudgetItem.project_id == project_id).order_by(ProjectBudgetItem.sort_order, ProjectBudgetItem.id)).all()
    # 先按优先级找启用项；该级全被停用就往下走一级，而不是硬塞一个已停用的项。
    for predicate in LABOR_BUDGET_PREDICATES:
        active = next((item for item in items if predicate(item) and item.is_active), None)
        if active:
            return active
    for predicate in LABOR_BUDGET_PREDICATES:
        inactive = next((item for item in items if predicate(item)), None)
        if inactive:
            return inactive
    return next((item for item in items if item.is_active), items[0] if items else None)


def apply_cost_entry_snapshot(entry: ProjectCostEntry, item: ProjectBudgetItem) -> None:
    """写入预算项快照；成本分类已并入预算项，不再单独记录大小类。"""
    entry.budget_item_id = item.id
    entry.budget_item_name_snapshot = item.name


def resolve_cost_entry_budget_item(db: Session, entry_kind: str, project_id: int, budget_item_id: int | None) -> ProjectBudgetItem:
    """人工成本固定归入人工费用预算项；项目费用必须显式选择项目内启用中的预算项。"""
    if entry_kind == "PERSONNEL_COST":
        item = labor_budget_item(db, project_id)
        if not item:
            raise HTTPException(400, "LABOR_BUDGET_ITEM_MISSING")
        return item
    if not budget_item_id:
        raise HTTPException(400, "BUDGET_ITEM_REQUIRED")
    item = db.get(ProjectBudgetItem, budget_item_id)
    if not item or item.project_id != project_id:
        raise HTTPException(400, "BUDGET_ITEM_INVALID")
    if not item.is_active:
        raise HTTPException(400, "BUDGET_ITEM_INACTIVE")
    return item


def ensure_cost_entry_scope(db: Session, user: User, project_id: int, entry_kind: str | None = None) -> Project:
    """同时按单据类型的数据范围与项目范围校验可见性。"""
    scope = project_scope_ids(db, user, cost_entry_resource(entry_kind))
    if scope is not None and project_id not in scope:
        raise HTTPException(403, "PROJECT_OUT_OF_SCOPE")
    return ensure_project_in_scope(db, user, project_id)


def cost_entry_access(db: Session, entry: ProjectCostEntry, demo_user_id: int | None, *, action: str = "VIEW") -> User:
    """校验成本单菜单、数据范围或复核岗位授权；申请人本人始终可读。"""
    user = current_user(db, demo_user_id)
    if action == "VIEW" and entry.applicant_user_id == user.id:
        return user
    resource = cost_entry_resource(entry.entry_kind)
    require_access(db, resource, action, demo_user_id)
    scope = project_scope_ids(db, user, resource)
    if scope is not None and entry.project_id not in scope and entry.applicant_user_id != user.id:
        raise HTTPException(403, "PROJECT_OUT_OF_SCOPE")
    return user


def same_month_labor_entries(db: Session, entry: ProjectCostEntry) -> int:
    """同一项目同一核算月份的其他人工成本笔数，用于录入提示而不阻止录入。"""
    if entry.entry_kind != "PERSONNEL_COST" or not entry.accounting_month:
        return 0
    return int(
        db.scalar(
            select(func.count(ProjectCostEntry.id)).where(
                ProjectCostEntry.entry_kind == "PERSONNEL_COST",
                ProjectCostEntry.project_id == entry.project_id,
                ProjectCostEntry.accounting_month == entry.accounting_month,
                ProjectCostEntry.status != "REVERSED",
                ProjectCostEntry.id != entry.id,
            )
        )
        or 0
    )


def cost_entry_view(db: Session, entry: ProjectCostEntry, viewer: User | None = None) -> ProjectCostEntryView:
    project = db.get(Project, entry.project_id)
    submitter = db.get(User, entry.submitted_by) if entry.submitted_by else None
    reviewer = db.get(User, entry.reviewed_by) if entry.reviewed_by else None
    can_edit = bool(
        viewer
        and entry.status in EDITABLE_COST_ENTRY_STATUSES
        and (
            entry.applicant_user_id == viewer.id
            or "EDIT" in effective_permission_details(db, viewer.id).get(cost_entry_resource(entry.entry_kind), {}).get("actions", [])
        )
    )
    return ProjectCostEntryView(
        id=entry.id,
        cost_no=entry.cost_no,
        entry_kind=entry.entry_kind,
        project_id=entry.project_id,
        project_name=project.name if project else "",
        project_code=project.code if project else "",
        applicant_user_id=entry.applicant_user_id,
        applicant_name=entry.applicant_name or "",
        applicant_department_name=entry.applicant_department_name,
        budget_item_id=entry.budget_item_id,
        budget_item_name=entry.budget_item_name_snapshot,
        amount=float(entry.amount or 0),
        amount_without_tax=float(entry.amount_without_tax or 0),
        tax_rate=float(entry.tax_rate or 0),
        tax_amount=float(entry.tax_amount or 0),
        occurred_on=entry.occurred_on,
        accounting_month=entry.accounting_month,
        fill_date=entry.fill_date,
        description=entry.description,
        status=entry.status,
        version=entry.version,
        submitted_by=entry.submitted_by,
        submitted_by_name=submitter.name if submitter else None,
        submitted_at=entry.submitted_at,
        reviewed_by=entry.reviewed_by,
        reviewed_by_name=reviewer.name if reviewer else None,
        reviewed_at=entry.reviewed_at,
        review_comment=entry.review_comment,
        created_at=entry.created_at,
        attachments=cost_entry_attachment_views(db, entry.id),
        can_edit=can_edit,
        can_review=bool(viewer) and entry.status == "PENDING_REVIEW" and cost_can_review(db, viewer),
        can_reverse=bool(viewer) and entry.status == "APPROVED" and (
            cost_can_review(db, viewer)
            or "REVERSE" in effective_permission_details(db, viewer.id).get(cost_entry_resource(entry.entry_kind), {}).get("actions", [])
        ),
        can_withdraw=bool(viewer and entry.status == "PENDING_REVIEW" and entry.applicant_user_id == viewer.id),
        same_month_count=same_month_labor_entries(db, entry),
    )


def cost_entry_query(
    db: Session,
    user: User,
    *,
    entry_kind: str | None = None,
    project_id: int | None = None,
    status: str | None = None,
    department_id: int | None = None,
    applicant_user_id: int | None = None,
    accounting_month: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    keyword: str | None = None,
    data_scope: str = "ALL",
) -> list[ProjectCostEntry]:
    """按筛选条件读取成本单；数据范围沿用角色配置。"""
    query = select(ProjectCostEntry)
    if entry_kind:
        query = query.where(ProjectCostEntry.entry_kind == project_cost_kind(entry_kind))
    if data_scope == "OWNED":
        query = query.where(ProjectCostEntry.applicant_user_id == user.id)
    else:
        resource = cost_entry_resource(entry_kind) if entry_kind else "project_expenses"
        scope = project_scope_ids(db, user, resource)
        if scope is not None:
            query = query.where(ProjectCostEntry.project_id.in_(scope or {-1}))
    if project_id:
        query = query.where(ProjectCostEntry.project_id == project_id)
    if status:
        query = query.where(ProjectCostEntry.status == status)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.where(or_(ProjectCostEntry.cost_no.like(like), ProjectCostEntry.description.like(like)))
    if applicant_user_id:
        query = query.where(ProjectCostEntry.applicant_user_id == applicant_user_id)
    if accounting_month:
        query = query.where(ProjectCostEntry.accounting_month == accounting_month)
    if period_start:
        query = query.where(func.coalesce(ProjectCostEntry.occurred_on, ProjectCostEntry.created_at) >= period_start)
    if period_end:
        query = query.where(func.coalesce(ProjectCostEntry.occurred_on, ProjectCostEntry.created_at) <= period_end)
    if department_id:
        index = DepartmentIndex(db.scalars(select(Department)).all())
        department_ids = index.descendants(department_id)
        if not department_ids:
            raise HTTPException(400, "INVALID_DEPARTMENT")
        query = query.where(ProjectCostEntry.project_id.in_(select(Project.id).where(Project.department_id.in_(department_ids))))
    return list(db.scalars(query.order_by(ProjectCostEntry.id.desc())).all())


@app.get("/api/v1/project-cost-entries", response_model=ProjectCostEntryPage)
def list_project_cost_entries(
    entry_kind: str = Query(default="PROJECT_EXPENSE"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    project_id: int | None = Query(default=None, gt=0),
    status: str | None = None,
    department_id: int | None = Query(default=None, gt=0),
    applicant_user_id: int | None = Query(default=None, gt=0),
    accounting_month: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    keyword: str | None = None,
    data_scope: str = Query(default="ALL", pattern="^(OWNED|ALL)$"),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ProjectCostEntryPage:
    """项目费用与人工成本结转共用列表接口，按 entry_kind 区分。"""
    user = current_user(db, x_demo_user_id)
    require_access(db, cost_entry_resource(entry_kind), "VIEW", x_demo_user_id)
    rows = cost_entry_query(
        db,
        user,
        entry_kind=entry_kind,
        project_id=project_id,
        status=status,
        department_id=department_id,
        applicant_user_id=applicant_user_id,
        accounting_month=accounting_month,
        period_start=period_start,
        period_end=period_end,
        keyword=keyword,
        data_scope=data_scope,
    )
    total = len(rows)
    page_count = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    items = [cost_entry_view(db, item, user) for item in rows[start : start + page_size]]
    summary = {
        "total_amount": round(sum(float(item.amount or 0) for item in rows if item.status == "APPROVED"), 2),
        "pending_amount": round(sum(float(item.amount or 0) for item in rows if item.status == "PENDING_REVIEW"), 2),
        "approved_count": float(sum(1 for item in rows if item.status == "APPROVED")),
        "pending_count": float(sum(1 for item in rows if item.status == "PENDING_REVIEW")),
    }
    return ProjectCostEntryPage(items=items, total=total, page=page, page_size=page_size, page_count=page_count, summary=summary)


@app.post("/api/v1/project-cost-entries", response_model=ProjectCostEntryView, status_code=201)
def create_project_cost_entry(payload: ProjectCostEntryCreate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectCostEntryView:
    """新增项目费用或人工成本结转草稿；复核通过前不参与项目成本口径。"""
    entry_kind = project_cost_kind(payload.entry_kind)
    resource = PROJECT_COST_KIND_RESOURCES[entry_kind]
    user = require_admin_permission(db, resource, x_demo_user_id)
    require_access(db, resource, "CREATE", x_demo_user_id)
    project = ensure_cost_entry_scope(db, user, payload.project_id, entry_kind)
    item = resolve_cost_entry_budget_item(db, entry_kind, payload.project_id, payload.budget_item_id)
    entry = ProjectCostEntry(
        cost_no=next_document_no(db, ProjectCostEntry, PROJECT_COST_KIND_PREFIXES[entry_kind]),
        entry_kind=entry_kind,
        project_id=payload.project_id,
        applicant_user_id=user.id,
        applicant_name=user.name,
        applicant_department_name=DepartmentIndex(db.scalars(select(Department)).all()).path(user.department_id),
        amount=payload.amount,
        occurred_on=payload.occurred_on,
        accounting_month=payload.accounting_month,
        # 填报日期固定为当天且不开放修改，编辑单据时保持创建日不变。
        fill_date=today_local(),
        description=(payload.description or "").strip() or None,
        status="DRAFT",
        version=1,
    )
    if entry_kind == "PERSONNEL_COST":
        # 人工成本结转是内部成本结转，不产生进项税：金额即入账金额，税额恒为 0。
        apply_tax_amount_fields(entry, payload.amount, 0, payload.amount)
    else:
        apply_tax_amount_fields(entry, payload.amount, payload.tax_rate, payload.amount_without_tax)
    apply_cost_entry_snapshot(entry, item)
    db.add(entry)
    db.flush()
    audit(db, "project_cost_entry", entry.id, "CREATE", user.id, None, "DRAFT", f"{PROJECT_COST_KIND_LABELS[entry_kind]} · {project.name}")
    db.commit()
    db.refresh(entry)
    return cost_entry_view(db, entry, user)


@app.get("/api/v1/project-cost-entries/{entry_id}", response_model=ProjectCostEntryView)
def get_project_cost_entry(entry_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectCostEntryView:
    entry = db.get(ProjectCostEntry, entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    user = cost_entry_access(db, entry, x_demo_user_id)
    return cost_entry_view(db, entry, user)


@app.patch("/api/v1/project-cost-entries/{entry_id}", response_model=ProjectCostEntryView)
def update_project_cost_entry(entry_id: int, payload: ProjectCostEntryUpdate, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectCostEntryView:
    """修改草稿或被驳回的成本单；复核中和已通过的单据只读。"""
    entry = db.get(ProjectCostEntry, entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    user = cost_entry_access(db, entry, x_demo_user_id, action="EDIT")
    if entry.status not in EDITABLE_COST_ENTRY_STATUSES:
        raise HTTPException(409, "PROJECT_COST_ENTRY_READ_ONLY")
    if payload.version != entry.version:
        raise HTTPException(409, "PROJECT_COST_ENTRY_VERSION_CONFLICT")
    if payload.entry_kind and project_cost_kind(payload.entry_kind) != entry.entry_kind:
        raise HTTPException(400, "COST_ENTRY_KIND_IMMUTABLE")
    ensure_cost_entry_scope(db, user, payload.project_id, entry.entry_kind)
    item = resolve_cost_entry_budget_item(db, entry.entry_kind, payload.project_id, payload.budget_item_id)
    entry.project_id = payload.project_id
    entry.amount = payload.amount
    if entry.entry_kind == "PERSONNEL_COST":
        apply_tax_amount_fields(entry, payload.amount, 0, payload.amount)
    else:
        apply_tax_amount_fields(entry, payload.amount, payload.tax_rate, payload.amount_without_tax)
    entry.occurred_on = payload.occurred_on
    entry.accounting_month = payload.accounting_month
    entry.description = (payload.description or "").strip() or None
    apply_cost_entry_snapshot(entry, item)
    entry.version += 1
    audit(db, "project_cost_entry", entry.id, "UPDATE", user.id, entry.status, entry.status)
    db.commit()
    db.refresh(entry)
    return cost_entry_view(db, entry, user)


@app.delete("/api/v1/project-cost-entries/{entry_id}")
def delete_project_cost_entry(entry_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    """只允许删除草稿或被驳回的成本单；已产生流水的单据必须走冲销。"""
    entry = db.get(ProjectCostEntry, entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    user = cost_entry_access(db, entry, x_demo_user_id, action="DELETE")
    if entry.status not in EDITABLE_COST_ENTRY_STATUSES:
        raise HTTPException(409, "PROJECT_COST_ENTRY_READ_ONLY")
    attachments = list(db.scalars(select(ProjectCostAttachment).where(ProjectCostAttachment.entry_id == entry.id)).all())
    paths = [cost_attachment_path(item) for item in attachments]
    for item in attachments:
        db.delete(item)
    audit(db, "project_cost_entry", entry.id, "DELETE", user.id, entry.status, None, entry.cost_no)
    db.delete(entry)
    db.commit()
    for path in paths:
        if path.exists():
            path.unlink()
    return {"deleted": True, "entry_id": entry_id}


def mark_cost_entry_submitted(db: Session, entry: ProjectCostEntry, user: User) -> None:
    """把草稿或被驳回的成本单推进到待复核；不提交事务，也不负责通知。"""

    if entry.status not in EDITABLE_COST_ENTRY_STATUSES:
        raise HTTPException(409, "PROJECT_COST_ENTRY_NOT_RESUBMITTABLE")
    if float(entry.amount or 0) <= 0:
        raise HTTPException(400, "PROJECT_COST_ENTRY_AMOUNT_REQUIRED")
    old_status = entry.status
    entry.submitted_by = user.id
    entry.submitted_at = now_local()
    entry.reviewed_by = None
    entry.reviewed_at = None
    entry.review_comment = None
    entry.version += 1
    entry.status = "PENDING_REVIEW"
    audit(db, "project_cost_entry", entry.id, "SUBMIT", user.id, old_status, "PENDING_REVIEW")


@app.post("/api/v1/project-cost-entries/{entry_id}/submit", response_model=ProjectCostEntryView)
def submit_project_cost_entry(entry_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectCostEntryView:
    """提交一级费用复核，并通知费用复核岗位全部有效成员。"""
    entry = db.get(ProjectCostEntry, entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    resource = cost_entry_resource(entry.entry_kind)
    user = cost_entry_access(db, entry, x_demo_user_id, action="EDIT")
    mark_cost_entry_submitted(db, entry, user)
    project = db.get(Project, entry.project_id)
    db.commit()
    kind = entry.entry_kind
    notify_cost_review_submitted(
        db,
        source_type=f"project_cost_{kind.lower()}",
        source_id=entry.id,
        version=entry.version,
        notification_type=PROJECT_COST_KIND_NOTIFICATIONS[kind],
        document_label=PROJECT_COST_KIND_LABELS[kind],
        serial_no=entry.cost_no,
        project_name=project.name if project else "",
        amount=float(entry.amount),
        submitter_name=user.name,
        page=PROJECT_COST_KIND_PAGES[kind],
    )
    db.commit()
    db.refresh(entry)
    require_access(db, resource, "VIEW", x_demo_user_id)
    return cost_entry_view(db, entry, user)


@app.post("/api/v1/project-cost-entries/{entry_id}/withdraw", response_model=ProjectCostEntryView)
def withdraw_project_cost_entry(entry_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectCostEntryView:
    """申请人撤回待费用复核的项目费用或人工成本结转单，恢复为草稿。"""
    entry = db.get(ProjectCostEntry, entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    user = cost_entry_access(db, entry, x_demo_user_id)
    if entry.applicant_user_id != user.id:
        raise HTTPException(403, "PROJECT_COST_ENTRY_WITHDRAW_FORBIDDEN")
    if entry.status != "PENDING_REVIEW":
        raise HTTPException(409, "PROJECT_COST_ENTRY_NOT_PENDING_REVIEW")
    entry.status = "DRAFT"
    entry.submitted_at = None
    entry.reviewed_by = None
    entry.reviewed_at = None
    entry.review_comment = None
    audit(db, "project_cost_entry", entry.id, "WITHDRAW", user.id, "PENDING_REVIEW", "DRAFT")
    db.commit()
    db.refresh(entry)
    return cost_entry_view(db, entry, user)


@app.post("/api/v1/project-cost-entries/{entry_id}/approve", response_model=ProjectCostEntryView)
def approve_project_cost_entry(entry_id: int, payload: ProjectCostReviewAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectCostEntryView:
    """一级费用复核通过：写项目流水并计入项目成本，记录实际复核人。"""
    user = require_cost_reviewer(db, x_demo_user_id)
    entry = db.get(ProjectCostEntry, entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    if entry.status == "APPROVED":
        return cost_entry_view(db, entry, user)
    if entry.status != "PENDING_REVIEW":
        raise HTTPException(409, "PROJECT_COST_ENTRY_NOT_PENDING_REVIEW")
    entry.status = "APPROVED"
    entry.reviewed_by = user.id
    entry.reviewed_at = now_local()
    entry.review_comment = payload.comment
    budget_item = db.get(ProjectBudgetItem, entry.budget_item_id) if entry.budget_item_id else None
    add_ledger_entry(
        db,
        entry.project_id,
        PROJECT_COST_LEDGER_TYPES[entry.entry_kind],
        "PROJECT_COST_ENTRY",
        entry.id,
        float(entry.amount),
        occurred_on=entry.occurred_on or today_local(),
        budget_item=budget_item,
    )
    audit(db, "project_cost_entry", entry.id, "APPROVE", user.id, "PENDING_REVIEW", "APPROVED")
    db.commit()
    db.refresh(entry)
    project = db.get(Project, entry.project_id)
    notify_cost_review_result(
        db,
        source_type=f"project_cost_{entry.entry_kind.lower()}",
        source_id=entry.id,
        version=entry.version,
        recipient_user_id=entry.applicant_user_id,
        document_label=PROJECT_COST_KIND_LABELS[entry.entry_kind],
        serial_no=entry.cost_no,
        project_name=project.name if project else "",
        amount=float(entry.amount),
        status_label="复核通过",
        page=PROJECT_COST_KIND_PAGES[entry.entry_kind],
        actor_name=user.name,
    )
    db.commit()
    return cost_entry_view(db, entry, user)


@app.post("/api/v1/project-cost-entries/{entry_id}/reject", response_model=ProjectCostEntryView)
def reject_project_cost_entry(entry_id: int, payload: ProjectCostRejectAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectCostEntryView:
    """一级费用复核驳回：驳回不计入项目成本，申请人可修改后重新提交。"""
    user = require_cost_reviewer(db, x_demo_user_id)
    entry = db.get(ProjectCostEntry, entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    if entry.status != "PENDING_REVIEW":
        raise HTTPException(409, "PROJECT_COST_ENTRY_NOT_PENDING_REVIEW")
    entry.status = "REJECTED"
    entry.reviewed_by = user.id
    entry.reviewed_at = now_local()
    entry.review_comment = payload.reason
    audit(db, "project_cost_entry", entry.id, "REJECT", user.id, "PENDING_REVIEW", "REJECTED", payload.reason)
    db.commit()
    db.refresh(entry)
    project = db.get(Project, entry.project_id)
    notify_cost_review_result(
        db,
        source_type=f"project_cost_{entry.entry_kind.lower()}",
        source_id=entry.id,
        version=entry.version,
        recipient_user_id=entry.applicant_user_id,
        document_label=PROJECT_COST_KIND_LABELS[entry.entry_kind],
        serial_no=entry.cost_no,
        project_name=project.name if project else "",
        amount=float(entry.amount),
        status_label="复核驳回",
        page=PROJECT_COST_KIND_PAGES[entry.entry_kind],
        actor_name=user.name,
    )
    db.commit()
    return cost_entry_view(db, entry, user)


@app.post("/api/v1/project-cost-entries/{entry_id}/reverse", response_model=ProjectCostEntryView)
def reverse_project_cost_entry(entry_id: int, payload: ProjectCostReversalAction, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectCostEntryView:
    """冲销已通过的成本单：追加反向流水，原流水保留便于追溯。"""
    user = require_cost_reviewer(db, x_demo_user_id)
    entry = db.get(ProjectCostEntry, entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    if entry.status != "APPROVED":
        raise HTTPException(409, "PROJECT_COST_ENTRY_NOT_APPROVED")
    entry.status = "REVERSED"
    entry.review_comment = payload.reason or entry.review_comment
    original_entry = db.scalar(
        select(ProjectLedgerEntry.id).where(
            ProjectLedgerEntry.source_type == "PROJECT_COST_ENTRY",
            ProjectLedgerEntry.source_id == entry.id,
            ProjectLedgerEntry.entry_type == PROJECT_COST_LEDGER_TYPES[entry.entry_kind],
        )
    )
    add_ledger_entry(
        db,
        entry.project_id,
        "REVERSAL",
        "PROJECT_COST_ENTRY",
        entry.id,
        float(entry.amount),
        occurred_on=today_local(),
        reversal_of_id=original_entry,
        budget_item=db.get(ProjectBudgetItem, entry.budget_item_id) if entry.budget_item_id else None,
    )
    audit(db, "project_cost_entry", entry.id, "REVERSE", user.id, "APPROVED", "REVERSED", payload.reason)
    db.commit()
    db.refresh(entry)
    return cost_entry_view(db, entry, user)


@app.get("/api/v1/project-cost-entries/{entry_id}/attachments", response_model=list[ProjectCostAttachmentView])
def list_project_cost_attachments(entry_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> list[ProjectCostAttachmentView]:
    entry = db.get(ProjectCostEntry, entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    cost_entry_access(db, entry, x_demo_user_id)
    return cost_entry_attachment_views(db, entry.id)


@app.post("/api/v1/project-cost-entries/{entry_id}/attachments", response_model=ProjectCostAttachmentView, status_code=201)
async def upload_project_cost_attachment(entry_id: int, file: UploadFile = File(...), x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> ProjectCostAttachmentView:
    entry = db.get(ProjectCostEntry, entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    user = cost_entry_access(db, entry, x_demo_user_id, action="EDIT")
    if entry.status not in EDITABLE_COST_ENTRY_STATUSES:
        raise HTTPException(409, "PROJECT_COST_ENTRY_READ_ONLY")
    original_name = Path(file.filename or "").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in CONTRACT_ATTACHMENT_EXTENSIONS:
        raise HTTPException(400, "ATTACHMENT_TYPE_NOT_ALLOWED")
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "ATTACHMENT_TOO_LARGE")
    storage_name = f"{secrets.token_hex(20)}{suffix}"
    destination = cost_attachment_root() / storage_name
    destination.write_bytes(content)
    attachment = ProjectCostAttachment(
        entry_id=entry.id,
        file_name=original_name[:300],
        storage_name=storage_name,
        mime_type=(file.content_type or CONTRACT_ATTACHMENT_EXTENSIONS[suffix])[:160],
        file_size=len(content),
        uploaded_by=user.id,
    )
    db.add(attachment)
    db.flush()
    audit(db, "project_cost_attachment", attachment.id, "CREATE", user.id, None, None, f"上传附件：{attachment.file_name}")
    db.commit()
    db.refresh(attachment)
    return cost_attachment_view(db, attachment)


@app.delete("/api/v1/project-cost-attachments/{attachment_id}")
def delete_project_cost_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    attachment = db.get(ProjectCostAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "PROJECT_COST_ATTACHMENT_NOT_FOUND")
    entry = db.get(ProjectCostEntry, attachment.entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    user = cost_entry_access(db, entry, x_demo_user_id, action="EDIT")
    if entry.status not in EDITABLE_COST_ENTRY_STATUSES:
        raise HTTPException(409, "PROJECT_COST_ENTRY_READ_ONLY")
    path = cost_attachment_path(attachment)
    db.delete(attachment)
    audit(db, "project_cost_attachment", attachment.id, "DELETE", user.id, None, None, f"删除附件：{attachment.file_name}")
    db.commit()
    if path.exists():
        path.unlink()
    return {"deleted": True, "attachment_id": attachment_id}


@app.get("/api/v1/project-cost-attachments/{attachment_id}/preview", response_model=None)
def preview_project_cost_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> HTMLResponse | FileResponse:
    attachment = db.get(ProjectCostAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "PROJECT_COST_ATTACHMENT_NOT_FOUND")
    entry = db.get(ProjectCostEntry, attachment.entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    cost_entry_access(db, entry, x_demo_user_id)
    path = cost_attachment_path(attachment)
    if not path.exists():
        raise HTTPException(404, "PROJECT_COST_ATTACHMENT_FILE_NOT_FOUND")
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


@app.get("/api/v1/project-cost-attachments/{attachment_id}/download")
def download_project_cost_attachment(attachment_id: int, x_demo_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> FileResponse:
    attachment = db.get(ProjectCostAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "PROJECT_COST_ATTACHMENT_NOT_FOUND")
    entry = db.get(ProjectCostEntry, attachment.entry_id)
    if not entry:
        raise HTTPException(404, "PROJECT_COST_ENTRY_NOT_FOUND")
    cost_entry_access(db, entry, x_demo_user_id)
    path = cost_attachment_path(attachment)
    if not path.exists():
        raise HTTPException(404, "PROJECT_COST_ATTACHMENT_FILE_NOT_FOUND")
    return FileResponse(path, media_type=attachment.mime_type, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.file_name)}"})


def cost_review_items(db: Session, entries: list[ProjectCostEntry]) -> list[CostReviewItem]:
    items: list[CostReviewItem] = []
    for entry in entries:
        project = db.get(Project, entry.project_id)
        reviewer = db.get(User, entry.reviewed_by) if entry.reviewed_by else None
        items.append(
            CostReviewItem(
                kind=entry.entry_kind,
                entry_id=entry.id,
                document_no=entry.cost_no,
                document_label=PROJECT_COST_KIND_LABELS.get(entry.entry_kind, entry.entry_kind),
                project_id=entry.project_id,
                project_name=project.name if project else "",
                project_code=project.code if project else "",
                budget_item_name=entry.budget_item_name_snapshot,
                amount=float(entry.amount or 0),
                occurred_on=entry.occurred_on,
                accounting_month=entry.accounting_month,
                applicant_name=entry.applicant_name or "",
                status=entry.status,
                submitted_at=entry.submitted_at,
                reviewed_by_name=reviewer.name if reviewer else None,
                reviewed_at=entry.reviewed_at,
                review_comment=entry.review_comment,
                description=entry.description,
            )
        )
    return items


@app.get("/api/v1/cost-review", response_model=CostReviewPage)
def list_cost_review(
    tab: str = Query(default="pending", pattern="^(pending|processed|all)$"),
    kind: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    project_id: int | None = Query(default=None, gt=0),
    department_id: int | None = Query(default=None, gt=0),
    x_demo_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CostReviewPage:
    """费用复核统一待办：合同付款、项目费用、人工成本结转三类单据合并展示。"""
    require_access(db, COST_REVIEW_RESOURCE, "VIEW", x_demo_user_id)
    wanted = (kind or "").strip().upper()
    if wanted and wanted not in {"PROJECT_EXPENSE", "PERSONNEL_COST", "PAYMENT"}:
        raise HTTPException(400, "COST_ENTRY_KIND_INVALID")
    entry_kinds = (
        [wanted] if wanted in {"PROJECT_EXPENSE", "PERSONNEL_COST"}
        else ([] if wanted == "PAYMENT" else ["PROJECT_EXPENSE", "PERSONNEL_COST"])
    )
    # 费用复核是岗位制全局职责：待办按复核权限收敛，不再叠加项目数据范围，
    # 否则只是被纳入复核岗位、没有业务角色的人会看不到任何待办。
    cost_entries: list[ProjectCostEntry] = []
    for entry_kind in entry_kinds:
        query = select(ProjectCostEntry).where(ProjectCostEntry.entry_kind == entry_kind)
        cost_entries.extend(db.scalars(query.order_by(ProjectCostEntry.id.desc())).all())

    payments: list[Payment] = []
    if not wanted or wanted == "PAYMENT":
        payments = list(db.scalars(select(Payment).order_by(Payment.id.desc())).all())

    if project_id:
        cost_entries = [item for item in cost_entries if item.project_id == project_id]
        payments = [item for item in payments if item.project_id == project_id]
    if department_id:
        index = DepartmentIndex(db.scalars(select(Department)).all())
        department_ids = index.descendants(department_id)
        if not department_ids:
            raise HTTPException(400, "INVALID_DEPARTMENT")
        allowed = {item.id for item in db.scalars(select(Project).where(Project.department_id.in_(department_ids))).all()}
        cost_entries = [item for item in cost_entries if item.project_id in allowed]
        payments = [item for item in payments if item.project_id in allowed]

    rows = cost_review_items(db, cost_entries)
    # 合同付款复用付款单表，按同一形状并入统一待办。
    for payment in payments:
        project = db.get(Project, payment.project_id)
        reviewer = db.get(User, payment.approved_by) if payment.approved_by else None
        rows.append(
            CostReviewItem(
                kind="PAYMENT",
                entry_id=payment.id,
                document_no=payment.payment_no,
                document_label="合同付款单",
                project_id=payment.project_id,
                project_name=project.name if project else "",
                project_code=project.code if project else "",
                budget_item_name=payment.budget_item_name_snapshot,
                amount=float(payment.amount or 0),
                occurred_on=payment.payment_date,
                applicant_name=(
                    db.get(User, payment.submitted_by).name
                    if payment.submitted_by and db.get(User, payment.submitted_by)
                    else ""
                ),
                status=payment.status,
                submitted_at=payment.submitted_at,
                reviewed_by_name=reviewer.name if reviewer else None,
                reviewed_at=payment.approved_at,
                review_comment=payment.comment,
                description=None,
            )
        )

    rows.sort(key=lambda item: (item.submitted_at or datetime.min, item.entry_id), reverse=True)
    pending = [item for item in rows if item.status == "PENDING_REVIEW"]
    processed = [item for item in rows if item.status in {"APPROVED", "REJECTED", "REVERSED"}]
    if tab == "pending":
        rows = pending
    elif tab == "processed":
        rows = processed
    total = len(rows)
    page_count = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    return CostReviewPage(
        tab=tab,
        items=rows[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
        page_count=page_count,
        pending_count=len(pending),
        processed_count=len(processed),
    )


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


@app.get("/api/v1/timesheets/{timesheet_id}", response_model=TimesheetView)
def get_legacy_timesheet(timesheet_id: int, db: Session = Depends(get_db)) -> TimesheetView:
    """保留旧周期单只读查询，v2.0 不再创建新的周期审批单。"""
    sheet = db.get(Timesheet, timesheet_id)
    if not sheet:
        raise HTTPException(404, "TIMESHEET_NOT_FOUND")
    items = db.scalars(select(Worklog).where(Worklog.timesheet_id == sheet.id).order_by(Worklog.start_date)).all()
    return TimesheetView(id=sheet.id, serial_no=sheet.serial_no, period_start=sheet.period_start, period_end=sheet.period_end, total_quantity=float(sheet.total_quantity), unit=sheet.unit, status=sheet.status, approval_instance_code=sheet.approval_instance_code, approver_name=sheet.approver_name, worklogs=[worklog_view(item) for item in items])
