"""MVP 数据模型，字段与 docs/v1.0/03-system-design.md 对齐。"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .session import Base
from ..time_utils import now_local


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feishu_department_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    parent_feishu_department_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feishu_user_id: Mapped[str] = mapped_column(String(64), unique=True)
    open_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employment_status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AdminPermission(Base):
    """管理模块权限配置；环境变量管理员始终拥有全部权限。"""

    __tablename__ = "admin_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    can_manage_projects: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_worklogs: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_integrations: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_admins: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_configuration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_contracts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_receipts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_payments: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_view_project_board: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_counterparties: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_approve_cash: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    project_data_scope: Mapped[str] = mapped_column(String(20), default="OWNED", nullable=False)
    scope_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class Role(Base):
    """RBAC 角色；内置角色只能停用或复制，不能物理删除。"""

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("code", name="uq_role_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class Menu(Base):
    """系统菜单资源树；菜单本身同时作为权限资源。"""

    __tablename__ = "menus"
    __table_args__ = (UniqueConstraint("code", name="uq_menu_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("menus.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    route: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    actions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class RolePermission(Base):
    """角色在菜单资源上的操作集合，actions 存 JSON 数组以便后续扩展。"""

    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "menu_id", name="uq_role_permission_menu"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    menu_id: Mapped[int] = mapped_column(ForeignKey("menus.id"), nullable=False)
    actions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class UserRole(Base):
    """用户与角色的多对多授权关系。"""

    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class RoleDataScope(Base):
    """角色对业务资源的默认数据范围。"""

    __tablename__ = "role_data_scopes"
    __table_args__ = (UniqueConstraint("role_id", "resource", name="uq_role_scope_resource"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    resource: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), default="SELF", nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)


class UserRoleScope(Base):
    """人员对指定角色的数据范围覆盖配置。"""

    __tablename__ = "user_role_scopes"
    __table_args__ = (UniqueConstraint("user_id", "role_id", "resource", name="uq_user_role_scope_resource"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    resource: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), default="SELF", nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)


class PermissionAudit(Base):
    """角色和人员授权变更审计，保存变更前后完整 JSON。"""

    __tablename__ = "permission_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class Customer(Base):
    """项目客户主数据；完整开票和账户信息在后续往来单位模块扩展。"""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unified_credit_code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    office_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    taxpayer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    invoice_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    invoice_phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class Supplier(Base):
    """供应商主数据，字段与客户保持一致以支持合同双向挂接。"""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unified_credit_code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    office_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    taxpayer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    invoice_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    invoice_phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(300))
    project_type: Mapped[str] = mapped_column(String(80), default="RND_PROJECT", nullable=False)
    project_sub_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    owner_name: Mapped[str] = mapped_column(String(100))
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    owner_open_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approver_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approver_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approver_open_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    leader_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    leader_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    leader_open_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    department_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_days: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    budget_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    expense_budget: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    allow_worklog: Mapped[bool] = mapped_column(Boolean, default=True)
    source_record_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class BudgetItemTemplate(Base):
    """后台维护的项目预算项模板，按项目大类自动带入项目。"""

    __tablename__ = "budget_item_templates"
    __table_args__ = (UniqueConstraint("project_category", "code", name="uq_budget_item_template_category_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_category: Mapped[str] = mapped_column(String(40), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), default="MIXED", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class ProjectBudgetItem(Base):
    """项目预算项实例，保存模板快照和本项目预算金额。"""

    __tablename__ = "project_budget_items"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_project_budget_item_project_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("budget_item_templates.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), default="MIXED", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    budget_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class Worklog(Base):
    __tablename__ = "worklogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user_name_snapshot: Mapped[str] = mapped_column(String(100))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    project_name_snapshot: Mapped[str] = mapped_column(String(300))
    stage: Mapped[str] = mapped_column(String(40))
    work_type: Mapped[str] = mapped_column(String(40))
    work_status: Mapped[str] = mapped_column(String(40))
    fill_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(String(10), default="DAY")
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    timesheet_id: Mapped[int | None] = mapped_column(ForeignKey("timesheets.id"), nullable=True)
    approver_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approver_name_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_version: Mapped[int] = mapped_column(Integer, default=0)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class Timesheet(Base):
    __tablename__ = "timesheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    serial_no: Mapped[str] = mapped_column(String(32), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    total_quantity: Mapped[float] = mapped_column(Numeric(12, 2))
    unit: Mapped[str] = mapped_column(String(10), default="DAY")
    status: Mapped[str] = mapped_column(String(20), default="APPROVING")
    approval_instance_code: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    approver_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class ApprovalTask(Base):
    """一条工时的本地审批版本。"""

    __tablename__ = "approval_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worklog_id: Mapped[int] = mapped_column(ForeignKey("worklogs.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    serial_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    submitter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approver_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class Notification(Base):
    """飞书提醒发送记录，通知失败不影响审批任务状态。"""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_task_id: Mapped[int] = mapped_column(ForeignKey("approval_tasks.id"), nullable=False)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), default="mock")
    idempotency_key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    message_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class AuditLog(Base):
    """追加写入的业务审计记录。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    old_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class ConfigOption(Base):
    """管理员可维护的业务下拉选项；value 用于存储，label 用于展示。

    `project_category`、`project_sub_category` 两类分类项使用层级字段构成父子树：
    `level=1` 为上级，`level=2` 为下级，
    下级通过 `parent_id` 指向上级，`path` 保存祖先路径便于排序与判重。
    """

    __tablename__ = "config_options"
    __table_args__ = (UniqueConstraint("category", "value", name="uq_config_option_category_value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("config_options.id"), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_leaf: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class Contract(Base):
    """项目收入或支出合同；金额与阶段计划驱动收款和付款。"""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(20), default="INCOME", nullable=False)
    counterparty_type: Mapped[str] = mapped_column(String(20), default="CUSTOMER", nullable=False)
    counterparty_id: Mapped[int] = mapped_column(Integer, nullable=False)
    counterparty_name: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    amount_without_tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(8, 6), default=0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    budget_item_id: Mapped[int | None] = mapped_column(ForeignKey("project_budget_items.id"), nullable=True)
    budget_item_name_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class ContractAttachment(Base):
    """合同附件元数据；文件本体存储在数据卷内的随机文件名下。"""

    __tablename__ = "contract_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class CashDocumentAttachment(Base):
    """合同收付款单附件元数据；文件本体存储在数据卷内的随机文件名下。"""

    __tablename__ = "cash_document_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class ContractStage(Base):
    """合同收款/付款阶段，实际合同收款与合同付款单可关联到阶段。"""

    __tablename__ = "contract_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    amount_without_tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(8, 6), default=0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remind_days_before: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    reminder_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class Receipt(Base):
    """合同收款单；经出纳审批通过后计入项目已收。"""

    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), nullable=False)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("contract_stages.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    amount_without_tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(8, 6), default=0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    payer_name: Mapped[str] = mapped_column(String(300), nullable=False)
    payer_bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payer_bank_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class Payment(Base):
    """合同付款单；新单据走动态审批，出纳末节点确认后计入项目已付。"""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), nullable=False)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("contract_stages.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    amount_without_tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(8, 6), default=0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payee_name: Mapped[str] = mapped_column(String(300), nullable=False)
    payee_bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payee_bank_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    budget_item_id: Mapped[int | None] = mapped_column(ForeignKey("project_budget_items.id"), nullable=True)
    budget_item_name_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_workflow_instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class ProjectLedgerEntry(Base):
    """项目经营流水：收付款确认和工时人员成本只追加不更新。"""

    __tablename__ = "project_ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    budget_item_id: Mapped[int | None] = mapped_column(ForeignKey("project_budget_items.id"), nullable=True)
    budget_item_name_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reversal_of_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class ReminderEvent(Base):
    """合同阶段到期提醒事件，按业务日期幂等去重。"""

    __tablename__ = "reminder_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("contract_stages.id"), nullable=False)
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class SystemNotification(Base):
    """非工时类业务通知：合同收付款审批结果、到期提醒等。"""

    __tablename__ = "system_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), default="mock", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class NotificationPolicy(Base):
    """业务通知策略；未关闭的策略才会触发对应的飞书提醒。"""

    __tablename__ = "notification_policies"
    __table_args__ = (UniqueConstraint("notification_type", name="uq_notification_policy_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    send_channel: Mapped[str] = mapped_column(String(30), default="app", nullable=False)
    remind_days_before: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    # v3.0.64 定时填报提醒：只有带定时语义的策略（WORKLOG_FILL_REMINDER）使用这几个字段。
    schedule_time: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_scope: Mapped[str] = mapped_column(String(20), default="ALL", nullable=False)
    target_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    only_unfilled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class OrgSyncLog(Base):
    """飞书组织架构主动同步记录。"""

    __tablename__ = "org_sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    user_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    department_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    added_user_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_user_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    added_department_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_department_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class ApprovalPosition(Base):
    """动态审批岗位；岗位与菜单角色相互独立。"""

    __tablename__ = "approval_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class ApprovalPositionMember(Base):
    """审批岗位成员；同一用户在同一岗位中只能出现一次。"""

    __tablename__ = "approval_position_members"
    __table_args__ = (UniqueConstraint("position_id", "user_id", name="uq_approval_position_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("approval_positions.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class WorkflowDefinition(Base):
    """轻量审批流程定义；发布版本后运行实例只引用不可变版本。"""

    __tablename__ = "workflow_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    document_types: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class WorkflowVersion(Base):
    """流程不可变版本；草稿发布后不能原地修改。"""

    __tablename__ = "workflow_versions"
    __table_args__ = (UniqueConstraint("workflow_definition_id", "version", name="uq_workflow_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_definition_id: Mapped[int] = mapped_column(ForeignKey("workflow_definitions.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    published_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class WorkflowNode(Base):
    """流程版本节点，保存审批人解析方式、审批模式和顺序。"""

    __tablename__ = "workflow_nodes"
    __table_args__ = (UniqueConstraint("workflow_version_id", "sequence", name="uq_workflow_node_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_version_id: Mapped[int] = mapped_column(ForeignKey("workflow_versions.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    resolver_type: Mapped[str] = mapped_column(String(40), nullable=False)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("approval_positions.id"), nullable=True)
    approval_mode: Mapped[str] = mapped_column(String(10), default="SINGLE", nullable=False)
    is_payment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProjectExpense(Base):
    """项目费用单；业务审批确认成本，出纳确认资金支付。"""

    __tablename__ = "project_expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expense_type: Mapped[str] = mapped_column(String(30), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    applicant_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    applicant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    applicant_department_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    amount_without_tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(8, 6), default=0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    cost_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    budget_item_id: Mapped[int | None] = mapped_column(ForeignKey("project_budget_items.id"), nullable=True)
    budget_item_name_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    requires_payment: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payee_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    payee_bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payee_bank_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    invoice_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", nullable=False)
    current_workflow_instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class ProjectExpenseAttachment(Base):
    """费用附件元数据，文件本体保存在 Docker 数据卷。"""

    __tablename__ = "project_expense_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("project_expenses.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class ProjectExpensePayment(Base):
    """费用实际支付；首期一张费用单只允许一次全额支付。"""

    __tablename__ = "project_expense_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("project_expenses.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    company_account: Mapped[str] = mapped_column(String(300), nullable=False)
    voucher_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cashier_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="CONFIRMED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class ProjectCostEntry(Base):
    """项目成本单：项目费用与人工成本结转共用一张表。

    `entry_kind` 区分两类单据：
    - `PROJECT_EXPENSE`：通用项目成本录入，按单据选择的预算项归集。
    - `PERSONNEL_COST`：财务按项目 + 核算月份录入的人工成本，固定归入人工费用预算项。

    两类单据都走一级费用复核（草稿 → 待复核 → 复核通过 / 驳回 → 冲销），
    复核通过后写项目流水并计入项目成本。
    """

    __tablename__ = "project_cost_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cost_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    entry_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    applicant_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    applicant_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    applicant_department_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    budget_item_id: Mapped[int | None] = mapped_column(ForeignKey("project_budget_items.id"), nullable=True)
    budget_item_name_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    amount_without_tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(8, 6), default=0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    accounting_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # 填报日期：服务端按 Asia/Shanghai 当日写入，不可由用户修改，用于区分「业务日期」与「录入日期」。
    fill_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class ProjectCostAttachment(Base):
    """项目成本单附件元数据；文件本体存储在数据卷内的随机文件名下。"""

    __tablename__ = "project_cost_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("project_cost_entries.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class WorkflowInstance(Base):
    """单据提交时生成的审批实例，固化流程版本和人员快照。"""

    __tablename__ = "workflow_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    workflow_version_id: Mapped[int] = mapped_column(ForeignKey("workflow_versions.id"), nullable=False)
    applicant_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="RUNNING", nullable=False)
    current_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WorkflowTask(Base):
    """审批节点候选人任务；ANY 节点处理后关闭同节点其余任务。"""

    __tablename__ = "workflow_tasks"
    __table_args__ = (UniqueConstraint("workflow_instance_id", "workflow_node_id", "assignee_user_id", name="uq_workflow_task_assignee"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_instance_id: Mapped[int] = mapped_column(ForeignKey("workflow_instances.id"), nullable=False)
    workflow_node_id: Mapped[int] = mapped_column(ForeignKey("workflow_nodes.id"), nullable=False)
    node_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    node_name: Mapped[str] = mapped_column(String(120), nullable=False)
    approval_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    assignee_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assignee_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_automatic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class WorkflowActionLog(Base):
    """审批实例操作日志，用于详情时间线和审计追溯。"""

    __tablename__ = "workflow_action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_instance_id: Mapped[int] = mapped_column(ForeignKey("workflow_instances.id"), nullable=False)
    workflow_task_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_tasks.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(100), default="系统", nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
