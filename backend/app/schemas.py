"""HTTP 输入输出模型。"""

import json
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.time_utils import today_local


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    department_name: str
    roles: list[str]
    management_permissions: list[str] = []
    permission_menus: list["EffectivePermissionMenu"] = []
    data_scopes: dict[str, str] = {}
    is_system_admin: bool = False


class MenuView(BaseModel):
    id: int
    code: str
    parent_id: int | None = None
    label: str
    route: str | None = None
    sort_order: int = 0
    is_active: bool = True
    actions: list[str] = []


class RoleView(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    is_builtin: bool
    is_active: bool
    user_count: int = 0
    menu_count: int = 0


class RoleList(BaseModel):
    items: list[RoleView] = []
    total: int = 0


class RoleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z][A-Za-z0-9_\-]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


class RoleUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


class RolePermissionInput(BaseModel):
    menu_code: str = Field(min_length=1, max_length=80)
    actions: list[str] = []


class RolePermissionsUpdate(BaseModel):
    permissions: list[RolePermissionInput] = []
    scopes: list["DataScopeInput"] = []


class DataScopeInput(BaseModel):
    resource: str = Field(min_length=1, max_length=80)
    scope_type: Literal["SELF", "OWNED_PROJECTS", "DEPARTMENT_AND_CHILDREN", "ALL"]
    department_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_department(self):
        if self.scope_type != "DEPARTMENT_AND_CHILDREN":
            self.department_id = None
        return self


class RolePermissionsView(BaseModel):
    role_id: int
    permissions: list[RolePermissionInput] = []
    scopes: list[DataScopeInput] = []


class UserRoleView(BaseModel):
    id: int
    user_id: int
    user_name: str
    department_name: str
    department_path: str
    employment_status: str
    role_ids: list[int] = []
    role_names: list[str] = []
    data_scopes: dict[str, str] = {}
    is_system_admin: bool = False


class UserRoleList(BaseModel):
    items: list[UserRoleView] = []
    total: int = 0


class UserRoleUpdate(BaseModel):
    role_ids: list[int] = []
    scopes: list[DataScopeInput] = []


class EffectivePermissionMenu(BaseModel):
    menu_code: str
    label: str
    route: str | None = None
    actions: list[str] = []
    scope_type: str | None = None
    scope_department_id: int | None = None
    source_roles: list[str] = []


class EffectivePermissionView(BaseModel):
    user_id: int
    user_name: str
    roles: list[RoleView] = []
    menus: list[EffectivePermissionMenu] = []
    data_scopes: dict[str, str] = {}


class AuthCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)


class CustomerView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    short_name: str | None
    unified_credit_code: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    address: str | None = None
    office_address: str | None = None
    license_expiry_date: date | None = None
    bank_name: str | None = None
    bank_branch: str | None = None
    bank_account: str | None = None
    invoice_title: str | None = None
    taxpayer_id: str | None = None
    invoice_address: str | None = None
    invoice_phone: str | None = None
    notes: str | None = None
    status: str


class CustomerCreate(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    short_name: str | None = Field(default=None, max_length=120)
    unified_credit_code: str | None = Field(default=None, max_length=32)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_phone: str | None = Field(default=None, max_length=60)
    contact_email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    office_address: str | None = Field(default=None, max_length=500)
    license_expiry_date: date | None = None
    bank_name: str | None = Field(default=None, max_length=200)
    bank_branch: str | None = Field(default=None, max_length=200)
    bank_account: str | None = Field(default=None, max_length=100)
    invoice_title: str | None = Field(default=None, max_length=300)
    taxpayer_id: str | None = Field(default=None, max_length=32)
    invoice_address: str | None = Field(default=None, max_length=500)
    invoice_phone: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=2000)
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"

    @field_validator("code", mode="before")
    @classmethod
    def blank_code_as_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class CustomerUpdate(CustomerCreate):
    pass


class SupplierView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    short_name: str | None = None
    unified_credit_code: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    address: str | None = None
    office_address: str | None = None
    license_expiry_date: date | None = None
    bank_name: str | None = None
    bank_branch: str | None = None
    bank_account: str | None = None
    invoice_title: str | None = None
    taxpayer_id: str | None = None
    invoice_address: str | None = None
    invoice_phone: str | None = None
    notes: str | None = None
    status: str


class SupplierCreate(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    short_name: str | None = Field(default=None, max_length=120)
    unified_credit_code: str | None = Field(default=None, max_length=32)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_phone: str | None = Field(default=None, max_length=60)
    contact_email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    office_address: str | None = Field(default=None, max_length=500)
    license_expiry_date: date | None = None
    bank_name: str | None = Field(default=None, max_length=200)
    bank_branch: str | None = Field(default=None, max_length=200)
    bank_account: str | None = Field(default=None, max_length=100)
    invoice_title: str | None = Field(default=None, max_length=300)
    taxpayer_id: str | None = Field(default=None, max_length=32)
    invoice_address: str | None = Field(default=None, max_length=500)
    invoice_phone: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=2000)
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"

    @field_validator("code", mode="before")
    @classmethod
    def blank_code_as_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class SupplierUpdate(SupplierCreate):
    pass


class ContractCreate(BaseModel):
    contract_no: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    project_id: int = Field(gt=0)
    contract_type: Literal["INCOME", "EXPENSE"] = "INCOME"
    counterparty_type: Literal["CUSTOMER", "SUPPLIER"] = "CUSTOMER"
    counterparty_id: int = Field(gt=0)
    amount: float = Field(default=0, ge=0)
    amount_without_tax: float | None = Field(default=None, ge=0)
    tax_rate: float = Field(default=0, ge=0, le=1)
    tax_amount: float | None = Field(default=None, ge=0)
    budget_item_id: int | None = Field(default=None, gt=0)
    sign_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: Literal["ACTIVE", "COMPLETED", "TERMINATED", "DRAFT"] = "ACTIVE"
    description: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("CONTRACT_DATE_ORDER_INVALID")
        return self


class ContractUpdate(ContractCreate):
    pass


class ContractView(BaseModel):
    id: int
    contract_no: str
    name: str
    project_id: int
    project_name: str
    contract_type: str
    counterparty_type: str
    counterparty_id: int
    counterparty_name: str
    amount: float = 0
    amount_without_tax: float = 0
    tax_rate: float = 0
    tax_amount: float = 0
    budget_item_id: int | None = None
    budget_item_name: str | None = None
    sign_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str
    description: str | None = None
    stage_count: int = 0
    settled_amount: float = 0
    remaining_amount: float = 0
    settlement_rate: float | None = None
    settled_document_count: int = 0
    next_stage_date: date | None = None


class ContractAttachmentView(BaseModel):
    id: int
    contract_id: int
    file_name: str
    mime_type: str
    file_size: int = 0
    uploaded_by: int
    uploaded_by_name: str = "系统"
    created_at: datetime
    can_preview: bool = False
    preview_kind: str = "download"


class CashDocumentAttachmentView(BaseModel):
    document_type: Literal["RECEIPT", "PAYMENT"]
    document_id: int
    id: int
    file_name: str
    mime_type: str
    file_size: int = 0
    uploaded_by: int
    uploaded_by_name: str = "系统"
    created_at: datetime
    can_preview: bool = False
    preview_kind: str = "download"


class ContractStageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: float = Field(default=0, ge=0)
    amount_without_tax: float | None = Field(default=None, ge=0)
    tax_rate: float = Field(default=0, ge=0, le=1)
    tax_amount: float | None = Field(default=None, ge=0)
    planned_date: date | None = None
    remind_days_before: int = Field(default=7, ge=0, le=365)
    reminder_paused: bool = False
    sort_order: int = Field(default=0, ge=0, le=100000)
    status: Literal["PENDING", "PARTIAL", "DONE", "CANCELLED"] = "PENDING"


class ContractStageUpdate(ContractStageCreate):
    pass


class ContractStageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    contract_id: int
    name: str
    amount: float = 0
    amount_without_tax: float = 0
    tax_rate: float = 0
    tax_amount: float = 0
    planned_date: date | None = None
    remind_days_before: int = 7
    reminder_paused: bool = False
    sort_order: int = 0
    status: str
    settled_amount: float = 0
    remaining_amount: float = 0
    settlement_rate: float | None = None
    settled_document_count: int = 0


class ReceiptCreate(BaseModel):
    contract_id: int = Field(gt=0)
    stage_id: int = Field(gt=0)
    amount: float = Field(gt=0)
    amount_without_tax: float | None = Field(default=None, ge=0)
    tax_rate: float = Field(default=0, ge=0, le=1)
    tax_amount: float | None = Field(default=None, ge=0)
    receipt_date: date
    payer_name: str = Field(min_length=1, max_length=300)
    payer_bank_name: str | None = Field(default=None, max_length=200)
    payer_bank_account: str | None = Field(default=None, max_length=100)
    comment: str | None = Field(default=None, max_length=2000)


class ReceiptUpdate(ReceiptCreate):
    pass


class ApprovalTimelineEvent(BaseModel):
    """合同收付款单的可读审批事件，用于详情页时间线。"""

    event: str
    actor_name: str = "系统"
    status: str | None = None
    comment: str | None = None
    occurred_at: datetime


class ReceiptView(BaseModel):
    id: int
    receipt_no: str
    project_id: int
    project_name: str
    contract_id: int
    contract_name: str
    contract_no: str | None = None
    counterparty_name: str | None = None
    stage_id: int | None = None
    stage_name: str | None = None
    amount: float = 0
    amount_without_tax: float = 0
    tax_rate: float = 0
    tax_amount: float = 0
    receipt_date: date
    payer_name: str
    payer_bank_name: str | None = None
    payer_bank_account: str | None = None
    status: str
    submitted_by: int | None = None
    submitted_at: datetime | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    comment: str | None = None
    submitted_by_name: str | None = None
    approved_by_name: str | None = None
    stage_planned_amount: float | None = None
    stage_settled_amount: float | None = None
    stage_remaining_amount: float | None = None
    stage_settlement_rate: float | None = None
    approval_timeline: list[ApprovalTimelineEvent] = []
    can_withdraw: bool = False


class PaymentCreate(BaseModel):
    contract_id: int = Field(gt=0)
    stage_id: int = Field(gt=0)
    amount: float = Field(gt=0)
    amount_without_tax: float | None = Field(default=None, ge=0)
    tax_rate: float = Field(default=0, ge=0, le=1)
    tax_amount: float | None = Field(default=None, ge=0)
    payment_date: date
    # 收款方留空时由支出合同的供应商主数据带出，允许在单据上覆盖。
    payee_name: str | None = Field(default=None, max_length=300)
    payee_bank_name: str | None = Field(default=None, max_length=200)
    payee_bank_account: str | None = Field(default=None, max_length=100)
    comment: str | None = Field(default=None, max_length=2000)


class PaymentUpdate(PaymentCreate):
    pass


class CashRejectAction(BaseModel):
    reason: str = Field(min_length=2, max_length=2000)


class PaymentView(BaseModel):
    id: int
    payment_no: str
    project_id: int
    project_name: str
    contract_id: int
    contract_name: str
    contract_no: str | None = None
    counterparty_name: str | None = None
    stage_id: int | None = None
    stage_name: str | None = None
    amount: float = 0
    amount_without_tax: float = 0
    tax_rate: float = 0
    tax_amount: float = 0
    payment_date: date
    payee_name: str
    payee_bank_name: str | None = None
    payee_bank_account: str | None = None
    budget_item_id: int | None = None
    budget_item_name: str | None = None
    status: str
    submitted_by: int | None = None
    submitted_at: datetime | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    comment: str | None = None
    submitted_by_name: str | None = None
    approved_by_name: str | None = None
    stage_planned_amount: float | None = None
    stage_settled_amount: float | None = None
    stage_remaining_amount: float | None = None
    stage_settlement_rate: float | None = None
    approval_timeline: list[ApprovalTimelineEvent] = []
    current_workflow_instance_id: int | None = None
    current_node_name: str | None = None
    current_task_id: int | None = None
    version: int = 1
    approval_path: list["WorkflowPathNodeView"] = []
    can_approve: bool = False
    can_withdraw: bool = False


class ProjectView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    project_type: str
    project_sub_category: str | None = None
    project_category_label: str | None = None
    project_sub_category_label: str | None = None
    owner_name: str
    owner_user_id: int | None
    approver_name: str | None
    approver_user_id: int | None
    leader_name: str | None
    leader_user_id: int | None
    department_id: int | None
    department_name: str | None
    department_path: str = "未分配部门"
    customer_id: int | None = None
    customer_name: str | None = None
    start_date: date | None = None
    planned_end_date: date | None = None
    description: str | None = None
    budget_days: float = 0
    budget_cost: float = 0
    expense_budget: float = 0
    actual_days: float = 0
    completion_rate: float | None = None
    remaining_days: float = 0
    actual_cost: float = 0
    personnel_cost: float = 0
    actual_contract_cost: float = 0
    actual_expense_cost: float = 0
    remaining_cost: float = 0
    personnel_cost_usage_rate: float | None = None
    cost_usage_rate: float | None = None
    cost_execution_status: str = "NO_BUDGET"
    expense_budget_remaining: float = 0
    expense_budget_usage_rate: float | None = None
    execution_status: str = "NOT_STARTED"
    status: str
    allow_worklog: bool


class BudgetItemTemplateView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_category: str
    code: str
    name: str
    source_kind: str = "MIXED"
    sort_order: int = 0
    is_active: bool = True
    is_builtin: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BudgetItemTemplateCreate(BaseModel):
    project_category: Literal["BUSINESS_PROJECT", "RND_PROJECT"]
    code: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    source_kind: Literal["LABOR", "CONTRACT_PAYMENT", "PROJECT_EXPENSE", "MIXED"] = "MIXED"
    sort_order: int = Field(default=0, ge=0, le=100000)
    is_active: bool = True


class BudgetItemTemplateUpdate(BudgetItemTemplateCreate):
    pass


class ProjectBudgetItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    template_id: int | None = None
    code: str
    name: str
    source_kind: str = "MIXED"
    sort_order: int = 0
    budget_amount: float = 0
    actual_amount: float = 0
    remaining_amount: float = 0
    usage_rate: float | None = None
    is_active: bool = True
    remark: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectBudgetItemUpdate(BaseModel):
    budget_amount: float = Field(default=0, ge=0)
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=1000)


class ProjectList(BaseModel):
    items: list[ProjectView]
    total: int
    page: int
    page_size: int
    page_count: int


class ProjectFinanceView(BaseModel):
    project_id: int
    contract_income: float = 0
    contract_expense: float = 0
    received: float = 0
    paid: float = 0
    receivable: float = 0
    payable: float = 0
    gross_profit: float = 0


class ProjectAnalysisStageView(BaseModel):
    id: int
    name: str
    planned_date: date | None = None
    planned_amount: float = 0
    settled_amount: float = 0
    remaining_amount: float = 0
    settlement_rate: float | None = None
    status: str = "PLANNED"
    warning_level: str | None = None
    warning_type: str | None = None
    days_to_due: int | None = None
    settled_document_count: int = 0


class ProjectAnalysisContractView(BaseModel):
    id: int
    contract_no: str
    name: str
    contract_type: str
    counterparty_name: str
    amount: float = 0
    settled_amount: float = 0
    remaining_amount: float = 0
    settlement_rate: float | None = None
    stages: list[ProjectAnalysisStageView] = []


class ProjectAnalysisCostTrendView(BaseModel):
    month: str
    personnel_cost: float = 0
    contract_cost: float = 0
    expense_cost: float = 0
    total_cost: float = 0


class ProjectAnalysisCostView(BaseModel):
    personnel_cost: float = 0
    contract_cost: float = 0
    expense_cost: float = 0
    total_cost: float = 0
    budget_cost: float = 0
    expense_budget: float = 0
    expense_budget_remaining: float = 0
    expense_budget_usage_rate: float | None = None
    remaining_cost: float = 0
    personnel_cost_budget_base: float | None = None
    personnel_cost_usage_rate: float | None = None
    cost_usage_rate: float | None = None
    budget_items: list[ProjectBudgetItemView] = []
    monthly_trend: list[ProjectAnalysisCostTrendView] = []


class ProjectAnalysisSettlementView(BaseModel):
    income_contracts: list[ProjectAnalysisContractView] = []
    expense_contracts: list[ProjectAnalysisContractView] = []
    pending_approval_receipt_amount: float = 0
    pending_approval_payment_amount: float = 0


class ProjectAnalysisCloseoutView(BaseModel):
    planned_end_date: date | None = None
    days_to_close: int | None = None
    before_close_receivable: float = 0
    before_close_payable: float = 0
    after_close_receivable: float = 0
    after_close_payable: float = 0
    unscheduled_receivable: float = 0
    unscheduled_payable: float = 0
    status: str = "NO_DATE"


class ProjectAnalysisWarningView(BaseModel):
    level: str
    warning_type: str
    title: str
    detail: str
    amount: float = 0
    planned_date: date | None = None
    source_type: str | None = None
    source_id: int | None = None
    project_id: int | None = None


class ProjectAnalysisView(BaseModel):
    project: ProjectView
    as_of: date
    kpis: ProjectFinanceView
    cost: ProjectAnalysisCostView
    settlement: ProjectAnalysisSettlementView
    closeout: ProjectAnalysisCloseoutView
    warnings: list[ProjectAnalysisWarningView] = []


class ProjectBoardRow(BaseModel):
    id: int
    code: str
    name: str
    project_type: str
    project_sub_category: str | None = None
    project_category_label: str | None = None
    project_sub_category_label: str | None = None
    status: str
    owner_name: str
    department_path: str = "未分配部门"
    customer_name: str | None = None
    budget_days: float = 0
    actual_days: float = 0
    completion_rate: float | None = None
    budget_cost: float = 0
    actual_cost: float = 0
    actual_contract_cost: float = 0
    actual_expense_cost: float = 0
    personnel_cost: float = 0
    remaining_cost: float = 0
    cost_usage_rate: float | None = None
    personnel_cost_usage_rate: float | None = None
    expense_budget: float = 0
    expense_budget_remaining: float = 0
    expense_budget_usage_rate: float | None = None
    execution_status: str = "NOT_STARTED"
    cost_execution_status: str = "NO_BUDGET"
    contract_income: float = 0
    contract_expense: float = 0
    received: float = 0
    paid: float = 0
    receivable: float = 0
    payable: float = 0
    gross_profit: float = 0
    warning: str | None = None


class ProjectBoardOption(BaseModel):
    """项目看板筛选器的项目选项，按看板数据范围返回。"""

    id: int
    code: str
    name: str
    owner_user_id: int | None = None


class ProjectBoardInsights(BaseModel):
    """项目看板图表和账龄分析数据。"""

    as_of: date
    trend: list[dict[str, str | float]] = []
    receivable_aging: list["ProjectBoardAgingBucket"] = []
    payable_aging: list["ProjectBoardAgingBucket"] = []
    warning_items: list[ProjectAnalysisWarningView] = []


class ProjectBoardAgingItem(BaseModel):
    """账龄柱下钻到的项目合同阶段。"""

    project_id: int
    project_name: str
    contract_id: int
    contract_name: str
    stage_id: int
    stage_name: str
    amount: float = 0


class ProjectBoardAgingBucket(BaseModel):
    """项目看板的账龄分组及其可下钻明细。"""

    name: str
    amount: float = 0
    items: list[ProjectBoardAgingItem] = []


class WorkbenchProjectRow(BaseModel):
    id: int
    code: str
    name: str
    project_type: str
    project_sub_category: str | None = None
    project_category_label: str | None = None
    project_sub_category_label: str | None = None
    status: str
    owner_name: str
    department_path: str = "未分配部门"
    budget_days: float = 0
    actual_days: float = 0
    completion_rate: float | None = None
    budget_cost: float = 0
    personnel_cost: float = 0
    cost_usage_rate: float | None = None
    execution_status: str = "NOT_STARTED"
    contract_income: float = 0
    contract_expense: float = 0
    received: float = 0
    paid: float = 0
    receivable: float = 0
    payable: float = 0
    gross_profit: float = 0
    warning: str | None = None


class WorkbenchReminder(BaseModel):
    kind: str
    project_id: int
    project_name: str
    contract_name: str
    stage_name: str
    amount: float = 0
    remaining: float = 0
    planned_date: date | None = None


class WorkbenchOverview(BaseModel):
    owned_projects: list[WorkbenchProjectRow] = []
    metrics: dict[str, float | int] = {}
    reminders: list[WorkbenchReminder] = []


class AuditEntryView(BaseModel):
    id: int
    object_type: str
    object_id: int
    action: str
    actor_name: str = "系统"
    old_status: str | None = None
    new_status: str | None = None
    comment: str | None = None
    object_label: str | None = None
    description: str | None = None
    created_at: datetime


class ProjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    project_type: str = Field(min_length=1, max_length=80)
    project_sub_category: str | None = Field(default=None, max_length=80)
    owner_user_id: int
    department_id: int = Field(gt=0)
    approver_user_id: int
    leader_user_id: int
    customer_id: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    planned_end_date: date | None = None
    description: str | None = Field(default=None, max_length=4000)
    budget_days: float = Field(default=0, ge=0)
    budget_cost: float = Field(default=0, ge=0)
    expense_budget: float = Field(default=0, ge=0)
    status: Literal["ACTIVE", "PAUSED", "ACCEPTANCE", "COMPLETED"] = "ACTIVE"
    allow_worklog: bool = True

    @model_validator(mode="after")
    def validate_date_order(self):
        if self.start_date and self.planned_end_date and self.start_date > self.planned_end_date:
            raise ValueError("PROJECT_DATE_ORDER_INVALID")
        return self


class ProjectUpdate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    project_type: str = Field(min_length=1, max_length=80)
    project_sub_category: str | None = Field(default=None, max_length=80)
    owner_user_id: int
    department_id: int = Field(gt=0)
    approver_user_id: int
    leader_user_id: int
    customer_id: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    planned_end_date: date | None = None
    description: str | None = Field(default=None, max_length=4000)
    budget_days: float = Field(default=0, ge=0)
    budget_cost: float = Field(default=0, ge=0)
    expense_budget: float = Field(default=0, ge=0)
    status: Literal["ACTIVE", "PAUSED", "ACCEPTANCE", "COMPLETED"]
    allow_worklog: bool

    @model_validator(mode="after")
    def validate_date_order(self):
        if self.start_date and self.planned_end_date and self.start_date > self.planned_end_date:
            raise ValueError("PROJECT_DATE_ORDER_INVALID")
        return self


class ProjectExpenseAttachmentView(BaseModel):
    id: int
    expense_id: int
    file_name: str
    mime_type: str
    file_size: int
    uploaded_by: int
    uploaded_by_name: str = "系统"
    created_at: datetime
    can_preview: bool = False
    preview_kind: str = "download"


class WorkflowPathNodeView(BaseModel):
    sequence: int
    node_code: str
    node_name: str
    approval_mode: str
    is_payment: bool = False
    assignees: list[dict[str, int | str]] = []
    status: str = "WAITING"


class WorkflowActionLogView(BaseModel):
    id: int
    action: str
    actor_name: str
    from_status: str | None = None
    to_status: str | None = None
    comment: str | None = None
    created_at: datetime


class ProjectExpenseBase(BaseModel):
    expense_type: Literal["TRAVEL", "INVOICE", "OTHER", "PROJECT_COST", "LABOR_COST"]
    project_id: int = Field(gt=0)
    occurred_on: date
    amount: float = Field(gt=0, le=1000000000)
    amount_without_tax: float | None = Field(default=None, ge=0, le=1000000000)
    tax_rate: float = Field(default=0, ge=0, le=1)
    tax_amount: float | None = Field(default=None, ge=0, le=1000000000)
    cost_amount: float = Field(gt=0, le=1000000000)
    budget_item_id: int | None = Field(default=None, gt=0)
    requires_payment: bool = True
    payee_name: str | None = Field(default=None, max_length=300)
    payee_bank_name: str | None = Field(default=None, max_length=200)
    payee_bank_account: str | None = Field(default=None, max_length=100)
    payment_due_date: date | None = None
    purpose: str = Field(min_length=2, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    detail: dict[str, str | float | int | bool | None] = {}
    invoice_code: str | None = Field(default=None, max_length=80)
    invoice_no: str | None = Field(default=None, max_length=120)
    supplier_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_payment_and_invoice(self):
        if self.occurred_on > today_local():
            raise ValueError("EXPENSE_DATE_IN_FUTURE")
        return self


class ProjectExpenseCreate(ProjectExpenseBase):
    pass


class ProjectExpenseUpdate(ProjectExpenseBase):
    version: int = Field(ge=1)


class ProjectExpensePaymentAction(BaseModel):
    payment_date: date
    amount: float = Field(gt=0, le=1000000000)
    company_account: str = Field(min_length=2, max_length=300)
    voucher_note: str | None = Field(default=None, max_length=2000)
    comment: str | None = Field(default=None, max_length=2000)


class WorkflowTaskAction(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class WorkflowTaskRejectAction(BaseModel):
    reason: str = Field(min_length=2, max_length=2000)


class ProjectExpenseView(BaseModel):
    id: int
    expense_no: str
    expense_type: str
    project_id: int
    project_name: str
    project_code: str
    applicant_user_id: int
    applicant_name: str
    applicant_department_name: str | None = None
    occurred_on: date
    amount: float
    amount_without_tax: float = 0
    tax_rate: float = 0
    tax_amount: float = 0
    cost_amount: float
    budget_item_id: int | None = None
    budget_item_name: str | None = None
    requires_payment: bool
    payee_name: str | None = None
    payee_bank_name: str | None = None
    payee_bank_account: str | None = None
    payment_due_date: date | None = None
    purpose: str
    notes: str | None = None
    detail: dict[str, str | float | int | bool | None] = {}
    invoice_code: str | None = None
    invoice_no: str | None = None
    supplier_id: int | None = None
    status: str
    current_node_name: str | None = None
    current_task_id: int | None = None
    version: int
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    attachment_count: int = 0
    attachments: list[ProjectExpenseAttachmentView] = []
    approval_path: list[WorkflowPathNodeView] = []
    approval_logs: list[WorkflowActionLogView] = []
    expense_budget: float = 0
    expense_budget_used: float = 0
    expense_budget_remaining: float = 0
    expense_budget_usage_rate: float | None = None
    can_edit: bool = False
    can_approve: bool = False


class ProjectExpenseList(BaseModel):
    items: list[ProjectExpenseView] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    page_count: int = 0
    summary: dict[str, float | int] = {}


class ApprovalPositionView(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    status: str
    member_ids: list[int] = []
    member_names: list[str] = []
    updated_at: datetime


class ApprovalPositionUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"
    member_ids: list[int] = []


class WorkflowTaskView(BaseModel):
    id: int
    workflow_instance_id: int
    document_type: str
    document_id: int
    document_no: str
    project_name: str
    applicant_name: str
    amount: float
    node_sequence: int
    node_name: str
    approval_mode: str
    assignee_user_id: int
    assignee_name: str
    status: str
    comment: str | None = None
    processed_at: datetime | None = None
    created_at: datetime


class WorkflowTaskList(BaseModel):
    items: list[WorkflowTaskView] = []
    total: int = 0


class WorklogCreate(BaseModel):
    project_id: int
    stage: str = Field(min_length=1, max_length=40)
    work_type: str = "PROJECT"
    work_status: str = "LOCAL"
    fill_date: date | None = None
    start_date: date
    end_date: date
    quantity: int = Field(gt=0, le=31)
    unit: Literal["DAY"] = "DAY"
    description: str = Field(min_length=2, max_length=2000)
    submit: bool = True


class WorklogUpdate(BaseModel):
    project_id: int
    stage: str = Field(min_length=1, max_length=40)
    work_type: str = "PROJECT"
    work_status: str = "LOCAL"
    fill_date: date | None = None
    start_date: date
    end_date: date
    quantity: int = Field(gt=0, le=31)
    unit: Literal["DAY"] = "DAY"
    description: str = Field(min_length=2, max_length=2000)


class WorklogView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    project_name_snapshot: str
    stage: str
    work_type: str
    work_status: str
    fill_date: date
    start_date: date
    end_date: date
    quantity: float
    unit: str
    description: str
    status: str
    timesheet_id: int | None
    approver_user_id: int | None
    approver_name_snapshot: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    rejection_reason: str | None
    approval_comment: str | None
    approval_version: int
    last_notified_at: datetime | None
    updated_at: datetime


class WorklogList(BaseModel):
    items: list[WorklogView]
    summary: dict[str, float | int]


class AdminWorklogView(WorklogView):
    """管理员全量工时行，补充填报人部门、一级部门和审批单号。"""

    serial_no: str | None = None
    user_name_snapshot: str
    user_department_name: str
    project_department_name: str


class AdminWorklogList(BaseModel):
    """管理员工时列表及筛选汇总。"""

    items: list[AdminWorklogView]
    total: int
    page: int
    page_size: int
    page_count: int
    summary: dict[str, float | int]
    department_options: list[str]

class ConfigOptionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    value: str
    label: str
    parent_id: int | None = None
    level: int = 1
    path: str | None = None
    is_leaf: bool = True
    sort_order: int
    is_active: bool
    is_builtin: bool


class ConfigOptionCreate(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None
    sort_order: int = Field(default=0, ge=0, le=100000)
    is_active: bool = True


class ConfigOptionUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None
    sort_order: int = Field(default=0, ge=0, le=100000)
    is_active: bool = True


class ClassificationNode(BaseModel):
    """层级分类节点，用于项目分类树与成本分类树。"""

    id: int
    value: str
    label: str
    parent_id: int | None = None
    level: int = 1
    path: str | None = None
    is_leaf: bool = True
    is_active: bool = True
    is_builtin: bool = False
    sort_order: int = 0
    children: list["ClassificationNode"] = []


class ClassificationCatalog(BaseModel):
    """按上级分类返回分类树；成本分类已并入统一 8 项预算项，不再单独成树。"""

    project_category: list[ClassificationNode] = []


class ConfigOptionCatalog(BaseModel):
    options: dict[str, list[ConfigOptionView]]


class TimesheetPreviewRequest(BaseModel):
    period_start: date
    period_end: date
    worklog_ids: list[int] = []


class TimesheetCreateRequest(TimesheetPreviewRequest):
    idempotency_key: str = Field(min_length=8, max_length=100)


class ApprovalAction(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)
    version: int = Field(ge=1)


class RejectionAction(BaseModel):
    reason: str = Field(min_length=2, max_length=2000)
    version: int = Field(ge=1)


class ProjectApproverUpdate(BaseModel):
    approver_user_id: int
    leader_user_id: int


class OrgUserView(BaseModel):
    id: int
    feishu_user_id: str
    name: str
    department_name: str
    department_id: int | None = None
    department_path: str = "未分配部门"
    employment_status: str


class OrgDepartmentView(BaseModel):
    id: int
    feishu_department_id: str
    name: str
    parent_name: str | None
    parent_id: int | None = None
    path: str = ""
    is_active: bool


class OrgSyncView(BaseModel):
    status: str
    mode: str
    user_count: int
    department_count: int
    synced_at: datetime | None = None
    error: str | None = None


class OrgSyncLogView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    mode: str
    user_count: int
    department_count: int
    added_user_count: int = 0
    updated_user_count: int = 0
    added_department_count: int = 0
    updated_department_count: int = 0
    duration_ms: int = 0
    error_message: str | None = None
    created_at: datetime

    @field_validator("added_user_count", "updated_user_count", "added_department_count", "updated_department_count", "duration_ms", mode="before")
    @classmethod
    def default_legacy_sync_stat(cls, value):
        """旧版本同步记录没有统计字段时统一按零返回。"""
        return 0 if value is None else value


class OrgSyncLogList(BaseModel):
    items: list[OrgSyncLogView] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    page_count: int = 0


class IntegrationNotificationView(BaseModel):
    id: int
    notification_type: str
    source_type: str
    source_id: int
    source_label: str
    recipient_user_id: int | None = None
    recipient_name: str = "未指定"
    channel: str
    status: str
    error_message: str | None = None
    retry_count: int = 0
    message_id: str | None = None
    sent_at: datetime | None = None
    created_at: datetime
    record_kind: Literal["system", "worklog"] = "system"


class NotificationPolicyView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notification_type: str
    label: str
    enabled: bool
    send_channel: str
    remind_days_before: int = 0
    schedule_time: str | None = None
    target_scope: str = "ALL"
    target_ids: str | None = None
    only_unfilled: bool = True
    updated_at: datetime


class NotificationPolicyUpdate(BaseModel):
    enabled: bool
    send_channel: Literal["app", "webhook", "mock"] = "app"
    remind_days_before: int = Field(default=0, ge=0, le=365)
    # v3.0.64 定时填报提醒配置；其它策略忽略这三个字段。
    schedule_time: str | None = Field(default=None, max_length=200)
    target_scope: Literal["ALL", "DEPARTMENT", "USER"] | None = None
    target_ids: str | None = None
    only_unfilled: bool | None = None


class WorklogFillReminderRunResult(BaseModel):
    scanned: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0


class NotificationPolicyBatchItem(NotificationPolicyUpdate):
    notification_type: str


class NotificationPolicyBatchUpdate(BaseModel):
    items: list[NotificationPolicyBatchItem]


class NotificationPolicyList(BaseModel):
    items: list[NotificationPolicyView] = []


class IntegrationNotificationList(BaseModel):
    items: list[IntegrationNotificationView] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    page_count: int = 0


class NotificationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    channel: str
    status: str
    error_message: str | None
    retry_count: int
    sent_at: datetime | None


class ApprovalTaskView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    worklog_id: int
    version: int
    serial_no: str
    submitter_user_id: int
    approver_user_id: int
    status: str
    comment: str | None
    submitted_at: datetime
    processed_at: datetime | None
    processed_by: int | None
    worklog: WorklogView
    notification: NotificationView | None = None


class TimesheetView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    serial_no: str
    period_start: date
    period_end: date
    total_quantity: float
    unit: str
    status: str
    approval_instance_code: str | None
    approver_name: str | None
    worklogs: list[WorklogView]


class ReportScope(BaseModel):
    period_start: str
    period_end: str
    department_name: str
    department_options: list[str]
    status: list[str]


class ReportView(BaseModel):
    scope: ReportScope
    metrics: dict[str, float | int]
    # A project without a configured cost budget has no percentage to report.
    # Keep that state as null instead of failing the entire report response.
    breakdowns: dict[str, list[dict[str, str | float | int | None]]]
    generated_at: datetime


PROJECT_COST_KINDS = ("PROJECT_EXPENSE", "PERSONNEL_COST")


class ProjectCostEntryCreate(BaseModel):
    """项目成本单新增入参；项目费用只保留项目、预算项、金额、发生时间、附件和说明。"""

    entry_kind: Literal["PROJECT_EXPENSE", "PERSONNEL_COST"] = "PROJECT_EXPENSE"
    project_id: int = Field(gt=0)
    budget_item_id: int | None = Field(default=None, gt=0)
    amount: float = Field(gt=0, le=1000000000)
    amount_without_tax: float | None = Field(default=None, ge=0, le=1000000000)
    tax_rate: float = Field(default=0, ge=0, le=1)
    tax_amount: float | None = Field(default=None, ge=0, le=1000000000)
    occurred_on: date | None = None
    accounting_month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _validate_kind_fields(self) -> "ProjectCostEntryCreate":
        if self.entry_kind == "PERSONNEL_COST":
            if not self.accounting_month:
                raise ValueError("PERSONNEL_COST_ACCOUNTING_MONTH_REQUIRED")
        elif not self.occurred_on:
            raise ValueError("PROJECT_EXPENSE_OCCURRED_ON_REQUIRED")
        return self


class ProjectCostEntryUpdate(ProjectCostEntryCreate):
    version: int = Field(ge=1)


class ProjectCostReviewAction(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class ProjectCostRejectAction(BaseModel):
    reason: str = Field(min_length=2, max_length=2000)


class ProjectCostReversalAction(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class ProjectCostAttachmentView(BaseModel):
    id: int
    entry_id: int
    file_name: str
    mime_type: str
    file_size: int
    uploaded_by: int
    uploaded_by_name: str = "系统"
    created_at: datetime
    can_preview: bool = False
    preview_kind: str = "download"


class ProjectCostEntryView(BaseModel):
    id: int
    cost_no: str
    entry_kind: str
    project_id: int
    project_name: str
    project_code: str
    applicant_user_id: int | None = None
    applicant_name: str = ""
    applicant_department_name: str | None = None
    budget_item_id: int | None = None
    budget_item_name: str | None = None
    amount: float
    amount_without_tax: float = 0
    tax_rate: float = 0
    tax_amount: float = 0
    occurred_on: date | None = None
    accounting_month: str | None = None
    # 填报日期由服务端在新增时写入当天（Asia/Shanghai），不可修改。
    fill_date: date | None = None
    description: str | None = None
    status: str
    version: int = 1
    submitted_by: int | None = None
    submitted_by_name: str | None = None
    submitted_at: datetime | None = None
    reviewed_by: int | None = None
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    created_at: datetime | None = None
    attachments: list[ProjectCostAttachmentView] = []
    can_edit: bool = False
    can_review: bool = False
    can_reverse: bool = False
    can_withdraw: bool = False
    same_month_count: int = 0


class ProjectCostEntryPage(BaseModel):
    items: list[ProjectCostEntryView]
    total: int
    page: int
    page_size: int
    page_count: int
    summary: dict[str, float] = {}


class CostReviewItem(BaseModel):
    kind: str
    entry_id: int
    document_no: str
    document_label: str
    project_id: int
    project_name: str
    project_code: str
    budget_item_name: str | None = None
    amount: float
    occurred_on: date | None = None
    accounting_month: str | None = None
    applicant_name: str = ""
    status: str
    submitted_at: datetime | None = None
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    description: str | None = None


class CostReviewPage(BaseModel):
    tab: str
    items: list[CostReviewItem]
    total: int
    page: int
    page_size: int
    page_count: int
    pending_count: int = 0
    processed_count: int = 0
