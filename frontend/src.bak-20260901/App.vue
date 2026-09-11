<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components";
import { init, use, type ECharts, type EChartsOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
]);

type Page =
  | "workbench"
  | "worklogs"
  | "editor"
  | "detail"
  | "approvals"
  | "approvalDetail"
  | "receiptDetail"
  | "paymentDetail"
  | "reports"
  | "projects"
  | "projectDetail"
  | "projectContracts"
  | "contractDetail"
  | "projectReceipts"
  | "projectPayments"
  | "projectBoard"
  | "suppliers"
  | "customers"
  | "integrations"
  | "adminWorklogs"
  | "personnelCosts"
  | "adminPermissions"
  | "configuration";
type ManagementPermission =
  | "projects"
  | "contracts"
  | "receipts"
  | "payments"
  | "project_board"
  | "counterparties"
  | "cash_approval"
  | "worklogs"
  | "personnel_costs"
  | "integrations"
  | "admins"
  | "configuration";
type AdminPermissionField =
  | "can_manage_projects"
  | "can_manage_contracts"
  | "can_manage_receipts"
  | "can_manage_payments"
  | "can_view_project_board"
  | "can_manage_counterparties"
  | "can_approve_cash"
  | "can_manage_worklogs"
  | "can_manage_personnel_costs"
  | "can_manage_integrations"
  | "can_manage_admins"
  | "can_manage_configuration";
type DemoUser = {
  id: number;
  name: string;
  department_name: string;
  department_id?: number | null;
  department_path?: string;
  roles?: string[];
  management_permissions?: ManagementPermission[];
};
type OrgDepartment = {
  id: number;
  feishu_department_id: string;
  name: string;
  parent_name: string | null;
  parent_id?: number | null;
  path?: string;
  is_active: boolean;
};
type OrgDepartmentNode = {
  department: OrgDepartment;
  depth: number;
  hasChildren: boolean;
};
type Customer = {
  id: number;
  code: string;
  name: string;
  short_name: string | null;
  unified_credit_code?: string | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  address?: string | null;
  office_address?: string | null;
  license_expiry_date?: string | null;
  bank_name?: string | null;
  bank_branch?: string | null;
  bank_account?: string | null;
  invoice_title?: string | null;
  taxpayer_id?: string | null;
  invoice_address?: string | null;
  invoice_phone?: string | null;
  notes?: string | null;
  status: string;
};
type Supplier = Customer;
type ProjectContract = {
  id: number;
  contract_no: string;
  name: string;
  project_id: number;
  project_name: string;
  contract_type: "INCOME" | "EXPENSE";
  counterparty_type: "CUSTOMER" | "SUPPLIER";
  counterparty_id: number;
  counterparty_name: string;
  amount: number;
  sign_date: string | null;
  start_date: string | null;
  end_date: string | null;
  status: string;
  description: string | null;
  stage_count: number;
  settled_amount: number;
  settlement_rate?: number | null;
  settled_document_count?: number;
};
type ContractAttachment = {
  id: number;
  contract_id: number;
  file_name: string;
  mime_type: string;
  file_size: number;
  uploaded_by: number;
  uploaded_by_name: string;
  created_at: string;
  can_preview: boolean;
  preview_kind: "word" | "excel" | "powerpoint" | "pdf" | "image" | "download";
};
type ProjectContractStage = {
  id: number;
  contract_id: number;
  name: string;
  amount: number;
  planned_date: string | null;
  remind_days_before?: number;
  reminder_paused?: boolean;
  sort_order: number;
  status: string;
  settled_amount?: number;
  remaining_amount?: number;
  settlement_rate?: number | null;
  settled_document_count?: number;
};
type Receipt = {
  id: number;
  receipt_no: string;
  project_id: number;
  project_name: string;
  contract_id: number;
  contract_name: string;
  stage_id: number | null;
  stage_name: string | null;
  amount: number;
  receipt_date: string;
  payer_name: string;
  payer_bank_name: string | null;
  payer_bank_account: string | null;
  status: string;
  submitted_at: string | null;
  approved_at: string | null;
  comment: string | null;
};
type Payment = {
  id: number;
  payment_no: string;
  project_id: number;
  project_name: string;
  contract_id: number;
  contract_name: string;
  stage_id: number | null;
  stage_name: string | null;
  amount: number;
  payment_date: string;
  payee_name: string;
  payee_bank_name: string | null;
  payee_bank_account: string | null;
  status: string;
  submitted_at: string | null;
  approved_at: string | null;
  comment: string | null;
};
type ProjectBoardRow = {
  id: number;
  code: string;
  name: string;
  project_type: string;
  status: string;
  owner_name: string;
  department_path: string;
  customer_name: string | null;
  contract_income: number;
  contract_expense: number;
  received: number;
  paid: number;
  receivable: number;
  payable: number;
  gross_profit: number;
  warning: string | null;
};
type ProjectFinance = {
  project_id: number;
  contract_income: number;
  contract_expense: number;
  received: number;
  paid: number;
  receivable: number;
  payable: number;
  gross_profit: number;
};
type ProjectAnalysisStage = {
  id: number;
  name: string;
  planned_date: string | null;
  planned_amount: number;
  settled_amount: number;
  remaining_amount: number;
  settlement_rate: number | null;
  status: string;
  warning_level: string | null;
  warning_type: string | null;
  days_to_due: number | null;
  settled_document_count: number;
};
type ProjectAnalysisContract = {
  id: number;
  contract_no: string;
  name: string;
  contract_type: "INCOME" | "EXPENSE";
  counterparty_name: string;
  amount: number;
  settled_amount: number;
  remaining_amount: number;
  settlement_rate: number | null;
  stages: ProjectAnalysisStage[];
};
type ProjectAnalysis = {
  project: Project;
  as_of: string;
  kpis: ProjectFinance;
  cost: {
    personnel_cost: number;
    contract_cost: number;
    total_cost: number;
    budget_cost: number;
    remaining_cost: number;
    personnel_cost_budget_base: number | null;
    personnel_cost_usage_rate: number | null;
    cost_usage_rate: number | null;
    monthly_trend: Array<{
      month: string;
      personnel_cost: number;
      contract_cost: number;
      total_cost: number;
    }>;
  };
  settlement: {
    income_contracts: ProjectAnalysisContract[];
    expense_contracts: ProjectAnalysisContract[];
    pending_approval_receipt_amount: number;
    pending_approval_payment_amount: number;
  };
  closeout: {
    planned_end_date: string | null;
    days_to_close: number | null;
    before_close_receivable: number;
    before_close_payable: number;
    after_close_receivable: number;
    after_close_payable: number;
    unscheduled_receivable: number;
    unscheduled_payable: number;
    status: string;
  };
  warnings: Array<{
    level: string;
    warning_type: string;
    title: string;
    detail: string;
    amount: number;
    planned_date: string | null;
    source_type: string | null;
    source_id: number | null;
  }>;
};
type WorkbenchProjectRow = {
  id: number;
  code: string;
  name: string;
  project_type: string;
  status: string;
  owner_name: string;
  department_path: string;
  budget_days: number;
  actual_days: number;
  completion_rate: number | null;
  budget_cost: number;
  personnel_cost: number;
  cost_usage_rate: number | null;
  execution_status: string;
  contract_income: number;
  contract_expense: number;
  received: number;
  paid: number;
  receivable: number;
  payable: number;
  gross_profit: number;
  warning: string | null;
};
type WorkbenchReminder = {
  kind: string;
  project_id: number;
  project_name: string;
  contract_name: string;
  stage_name: string;
  amount: number;
  remaining: number;
  planned_date: string | null;
};
type WorkbenchOverview = {
  owned_projects: WorkbenchProjectRow[];
  metrics: Record<string, number>;
  reminders: WorkbenchReminder[];
};
type AuditEntry = {
  id: number;
  object_type: string;
  object_id: number;
  action: string;
  actor_name: string;
  old_status: string | null;
  new_status: string | null;
  comment: string | null;
  created_at: string;
};
type Project = {
  id: number;
  code: string;
  name: string;
  project_type: string;
  owner_name: string;
  owner_user_id: number | null;
  approver_name: string | null;
  approver_user_id: number | null;
  leader_name: string | null;
  leader_user_id: number | null;
  department_id: number | null;
  department_name: string | null;
  department_path: string;
  customer_id: number | null;
  customer_name: string | null;
  start_date: string | null;
  planned_end_date: string | null;
  description: string | null;
  budget_days: number;
  budget_cost: number;
  actual_days: number;
  completion_rate: number | null;
  remaining_days: number;
  actual_cost: number;
  personnel_cost: number;
  actual_contract_cost: number;
  remaining_cost: number;
  personnel_cost_usage_rate: number | null;
  cost_usage_rate: number | null;
  cost_execution_status: string;
  execution_status: string;
  status: string;
  allow_worklog: boolean;
};
type ProjectList = {
  items: Project[];
  total: number;
  page: number;
  page_size: number;
  page_count: number;
};
type Worklog = {
  id: number;
  project_id: number;
  user_name_snapshot?: string;
  project_name_snapshot: string;
  stage: string;
  work_type: string;
  work_status: string;
  start_date: string;
  end_date: string;
  quantity: number;
  unit: string;
  description: string;
  status: string;
  timesheet_id: number | null;
  approver_user_id: number | null;
  approver_name_snapshot: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  approval_comment: string | null;
  approval_version: number;
  last_notified_at: string | null;
  updated_at: string;
};
type AdminWorklog = Worklog & {
  serial_no: string | null;
  user_name_snapshot: string;
  user_department_name: string;
  project_department_name: string;
};
type AdminWorklogList = {
  items: AdminWorklog[];
  total: number;
  page: number;
  page_size: number;
  page_count: number;
  summary: Record<string, number>;
  department_options: string[];
};
type PersonnelCost = {
  id: number;
  name: string;
  department_name: string;
  daily_cost: number | null;
};
type PersonnelCostList = {
  items: PersonnelCost[];
  total: number;
  page: number;
  page_size: number;
  page_count: number;
  department_options: string[];
  configured_user_ids: number[];
  summary: {
    configured_count: number;
    unset_count: number;
    total_daily_cost: number;
    average_daily_cost: number;
  };
};
type AdminPermission = {
  id: number | null;
  user_id: number;
  user_name: string;
  department_name: string;
  can_manage_projects: boolean;
  can_manage_contracts: boolean;
  can_manage_receipts: boolean;
  can_manage_payments: boolean;
  can_view_project_board: boolean;
  can_manage_counterparties: boolean;
  can_approve_cash: boolean;
  can_manage_worklogs: boolean;
  can_manage_personnel_costs: boolean;
  can_manage_integrations: boolean;
  can_manage_admins: boolean;
  can_manage_configuration: boolean;
  project_data_scope: "OWNED" | "DEPARTMENT" | "ALL";
  scope_department_id: number | null;
  is_active: boolean;
  is_system_admin: boolean;
};
type ConfigOption = {
  id: number;
  category: string;
  value: string;
  label: string;
  sort_order: number;
  is_active: boolean;
  is_builtin: boolean;
};
type ConfigCatalog = { options: Record<string, ConfigOption[]> };
type AdminPermissionList = { items: AdminPermission[]; total: number };
type Notification = {
  id: number;
  channel: string;
  status: string;
  error_message: string | null;
  retry_count: number;
  sent_at: string | null;
};
type ApprovalTask = {
  id: number;
  worklog_id: number;
  version: number;
  serial_no: string;
  submitter_user_id: number;
  approver_user_id: number;
  status: string;
  comment: string | null;
  submitted_at: string;
  processed_at: string | null;
  processed_by: number | null;
  worklog: Worklog;
  notification: Notification | null;
};
type ReportRow = {
  name: string;
  quantity: number;
  unit?: string;
  stage?: string;
  budget_days?: number;
  actual_days?: number;
  budget_cost?: number;
  actual_cost?: number;
  remaining_cost?: number;
  cost_usage_rate?: number | null;
};
type Report = {
  scope: {
    period_start: string;
    period_end: string;
    department_name: string;
    department_options: string[];
    status: string[];
  };
  metrics: Record<string, number>;
  breakdowns: Record<string, ReportRow[]>;
  generated_at: string;
};
type AuthConfig = {
  mode: "mock" | "app";
  auth_app_id: string | null;
  feishu_login_enabled: boolean;
  auth_required: boolean;
  authenticated: boolean;
};
type IntegrationHealth = {
  mode: string;
  oauth: string;
  directory: string;
  approval: string;
  notification: string;
};
type IntegrationNotification = {
  id: number;
  notification_type: string;
  source_type: string;
  source_id: number;
  source_label: string;
  recipient_user_id?: number | null;
  recipient_name: string;
  channel: string;
  status: string;
  error_message?: string | null;
  retry_count: number;
  message_id?: string | null;
  sent_at?: string | null;
  created_at: string;
};
type OrgSyncLog = {
  id: number;
  status: string;
  mode: string;
  user_count: number;
  department_count: number;
  error_message?: string | null;
  created_at: string;
};
type IntegrationOverview = {
  health: IntegrationHealth;
  summary: {
    member_count: number;
    department_count: number;
    sent_count: number;
    retry_count: number;
  };
  notifications: IntegrationNotification[];
  notification_total: number;
  sync_logs: OrgSyncLog[];
};

const initialPage = (() => {
  const requested = new URLSearchParams(window.location.search).get("page");
  const supported: Page[] = [
    "workbench",
    "worklogs",
    "approvals",
    "reports",
    "projects",
    "projectDetail",
    "projectContracts",
    "contractDetail",
    "projectReceipts",
    "projectPayments",
    "projectBoard",
    "suppliers",
    "customers",
    "personnelCosts",
    "integrations",
    "adminPermissions",
    "configuration",
    "adminWorklogs",
  ];
  return supported.includes(requested as Page)
    ? (requested as Page)
    : ("workbench" as Page);
})();
const page = ref<Page>(initialPage);
const mobileManagementOpen = ref(false);
const loading = ref(false);
const authLoading = ref(true);
const authRequired = ref(false);
const authMode = ref<"mock" | "app">("mock");
const feishuLoginEnabled = ref(false);
const authAppId = ref("");
const errorMessage = ref("");
const successMessage = ref("");
const projects = ref<Project[]>([]);
const managedProjects = ref<Project[]>([]);
const customers = ref<Customer[]>([]);
const suppliers = ref<Supplier[]>([]);
const projectContracts = ref<ProjectContract[]>([]);
const incomeContractOptions = ref<ProjectContract[]>([]);
const expenseContractOptions = ref<ProjectContract[]>([]);
const incomeContractsLoading = ref(false);
const expenseContractsLoading = ref(false);
const projectContractStages = ref<ProjectContractStage[]>([]);
const receipts = ref<Receipt[]>([]);
const payments = ref<Payment[]>([]);
const selectedReceipt = ref<Receipt | null>(null);
const selectedPayment = ref<Payment | null>(null);
const projectBoardRows = ref<ProjectBoardRow[]>([]);
const projectFinance = ref<ProjectFinance | null>(null);
const projectAnalysis = ref<ProjectAnalysis | null>(null);
const projectAnalysisLoading = ref(false);
const projectAnalysisError = ref("");
const analysisSettlementTab = ref<"income" | "expense">("income");
const expandedAnalysisStages = ref<Set<number>>(new Set());
const workbenchOverview = ref<WorkbenchOverview | null>(null);
const workbenchLoading = ref(false);
const projectDetailTab = ref("overview");
const projectAuditLogs = ref<AuditEntry[]>([]);
const selectedManagedProject = ref<Project | null>(null);
const projectListLoading = ref(false);
const projectListTotal = ref(0);
const configOptions = ref<Record<string, ConfigOption[]>>({});
const adminConfigOptions = ref<Record<string, ConfigOption[]>>({});
const configurationCategory = ref("project_type");
const configurationLoading = ref(false);
const configurationFormOpen = ref(false);
const configurationEditingId = ref<number | null>(null);
const configurationForm = reactive({
  category: "project_type",
  value: "",
  label: "",
  sort_order: 1,
  is_active: true,
});
const demoUsers = ref<DemoUser[]>([]);
const departments = ref<OrgDepartment[]>([]);
const worklogs = ref<Worklog[]>([]);
const adminWorklogs = ref<AdminWorklog[]>([]);
const adminWorklogTotal = ref(0);
const adminPage = ref(1);
const adminPageSize = ref(20);
const adminPageSizeMode = ref("20");
const adminPageCount = ref(1);
const adminSummary = ref<Record<string, number>>({
  quantity: 0,
  approved_quantity: 0,
  count: 0,
  approved_count: 0,
  pending_count: 0,
  draft_count: 0,
  rejected_count: 0,
});
const adminDepartmentOptions = ref<string[]>([]);
const adminLoading = ref(false);
const adminDepartment = ref("");
const adminUserId = ref(0);
const adminProjectId = ref(0);
const adminStatus = ref("");
const adminPeriodStart = ref("");
const adminPeriodEnd = ref("");
const adminWorklogFormOpen = ref(false);
const personnelCosts = ref<PersonnelCost[]>([]);
const personnelCostTotal = ref(0);
const personnelCostPage = ref(1);
const personnelCostPageSize = ref(20);
const personnelCostPageSizeMode = ref("20");
const personnelCostPageCount = ref(1);
const personnelCostDepartmentOptions = ref<string[]>([]);
const personnelCostDepartment = ref("");
const personnelCostUserId = ref(0);
const personnelCostLoading = ref(false);
const personnelCostSavingId = ref<number | null>(null);
const personnelCostConfiguredCount = ref(0);
const personnelCostUnsetCount = ref(0);
const personnelCostAverage = ref(0);
const personnelCostTotalDailyCost = ref(0);
const personnelCostConfiguredUserIds = ref<number[]>([]);
const personnelCostFormOpen = ref(false);
const personnelCostForm = reactive({
  user_id: 0,
  daily_cost: null as number | null,
});
const adminPermissions = ref<AdminPermission[]>([]);
const adminPermissionKeyword = ref("");
const adminPermissionLoading = ref(false);
const adminPermissionSavingId = ref<number | null>(null);
const adminPermissionFormOpen = ref(false);
const adminPermissionForm = reactive({
  user_id: 0,
  can_manage_projects: false,
  can_manage_contracts: false,
  can_manage_receipts: false,
  can_manage_payments: false,
  can_view_project_board: false,
  can_manage_counterparties: false,
  can_approve_cash: false,
  can_manage_worklogs: false,
  can_manage_personnel_costs: false,
  can_manage_integrations: false,
  can_manage_admins: false,
  can_manage_configuration: false,
  project_data_scope: "OWNED" as "OWNED" | "DEPARTMENT" | "ALL",
  scope_department_id: null as number | null,
  is_active: true,
});
const adminEditingId = ref<number | null>(null);
const adminForm = reactive({
  project_id: 0,
  project_type: "RND_PROJECT",
  stage: "开发",
  work_type: "PROJECT",
  work_status: "LOCAL",
  start_date: "",
  end_date: "",
  quantity: 1,
  unit: "DAY",
  description: "",
});
const permissionLabels: Array<{
  key: ManagementPermission;
  field: AdminPermissionField;
  label: string;
}> = [
  { key: "projects", field: "can_manage_projects", label: "项目管理" },
  { key: "contracts", field: "can_manage_contracts", label: "项目合同" },
  { key: "receipts", field: "can_manage_receipts", label: "项目收款" },
  { key: "payments", field: "can_manage_payments", label: "项目付款" },
  { key: "project_board", field: "can_view_project_board", label: "项目看板" },
  {
    key: "counterparties",
    field: "can_manage_counterparties",
    label: "客户与供应商",
  },
  { key: "cash_approval", field: "can_approve_cash", label: "出纳审批" },
  { key: "worklogs", field: "can_manage_worklogs", label: "工时管理" },
  {
    key: "personnel_costs",
    field: "can_manage_personnel_costs",
    label: "人员成本",
  },
  {
    key: "integrations",
    field: "can_manage_integrations",
    label: "集成与通知",
  },
  { key: "admins", field: "can_manage_admins", label: "管理员管理" },
  {
    key: "configuration",
    field: "can_manage_configuration",
    label: "基础配置",
  },
];
const pendingApprovals = ref<ApprovalTask[]>([]);
const processedApprovals = ref<ApprovalTask[]>([]);
const approvalTab = ref<"pending" | "processed">("pending");
const report = ref<Report | null>(null);
const integrationHealth = ref<IntegrationHealth>({
  mode: "mock",
  oauth: "mock-ok",
  directory: "mock-ok",
  approval: "local-only",
  notification: "mock",
});
const integrationOverview = ref<IntegrationOverview | null>(null);
const integrationOverviewLoading = ref(false);
const integrationNotificationType = ref("");
const integrationNotificationStatus = ref("");
const selectedTask = ref<ApprovalTask | null>(null);
const selectedStatus = ref("");
const projectQuery = ref("");
const projectPickerOpen = ref(false);
const reportDepartment = ref("");
const reportPeriodStart = ref(new Date().toISOString().slice(0, 8) + "01");
const reportPeriodEnd = ref(new Date().toISOString().slice(0, 10));
const exportReadyUrl = ref("");
let statusRefreshTimer: ReturnType<typeof setInterval> | null = null;
let statusRefreshBusy = false;
const editingId = ref<number | null>(null);
const rejectionReason = ref("");
const activeUserId = ref(1);
const editingProjectId = ref<number | null>(null);
const projectFormOpen = ref(false);
const projectFilterType = ref("");
const projectFilterStatus = ref("");
const projectFilterDepartment = ref(0);
const projectFilterOwner = ref(0);
const projectFilterCustomer = ref(0);
const projectFilterKeyword = ref("");
const projectDataScope = ref<"OWNED" | "ALL">("OWNED");
const projectDepartmentPickerOpen = ref(false);
const projectDepartmentExpanded = ref<Set<number>>(new Set());
const projectPage = ref(1);
const projectPageSize = ref(20);
const projectPageSizeMode = ref("20");
const contractsLoading = ref(false);
const receiptsLoading = ref(false);
const paymentsLoading = ref(false);
const boardLoading = ref(false);
const counterpartiesLoading = ref(false);
const contractTab = ref<"INCOME" | "EXPENSE">("INCOME");
const contractFilterProject = ref(0);
const contractFilterType = ref("");
const contractFilterCounterparty = ref(0);
const contractFormOpen = ref(false);
const editingContractId = ref<number | null>(null);
const selectedContract = ref<ProjectContract | null>(null);
const contractDetailStages = ref<ProjectContractStage[]>([]);
const contractAttachments = ref<ContractAttachment[]>([]);
const contractAttachmentsLoading = ref(false);
const contractAttachmentUploading = ref(false);
const attachmentPreviewOpen = ref(false);
const attachmentPreviewLoading = ref(false);
const attachmentPreviewUrl = ref("");
const attachmentPreviewError = ref("");
const attachmentPreviewItem = ref<ContractAttachment | null>(null);
const contractDetailLoading = ref(false);
const contractDetailError = ref("");
const contractForm = reactive({
  contract_no: "",
  name: "",
  project_id: 0,
  contract_type: "INCOME" as "INCOME" | "EXPENSE",
  counterparty_type: "CUSTOMER" as "CUSTOMER" | "SUPPLIER",
  counterparty_id: 0,
  amount: 0,
  sign_date: "",
  start_date: "",
  end_date: "",
  status: "ACTIVE",
  description: "",
});
const stageFormOpen = ref(false);
const stageListOpen = ref(false);
const stageContractId = ref(0);
const contractStagesLoading = ref(false);
const editingStageId = ref<number | null>(null);
const stageForm = reactive({
  name: "",
  amount: 0,
  planned_date: "",
  remind_days_before: 7,
  reminder_paused: false,
  sort_order: 0,
  status: "PENDING",
});
const receiptFilterProject = ref(0);
const receiptFilterStatus = ref("");
const receiptTab = ref<"pending" | "all">("pending");
const receiptFormOpen = ref(false);
const editingReceiptId = ref<number | null>(null);
const receiptForm = reactive({
  contract_id: 0,
  stage_id: null as number | null,
  amount: 0,
  receipt_date: new Date().toISOString().slice(0, 10),
  payer_name: "",
  payer_bank_name: "",
  payer_bank_account: "",
  comment: "",
});
const paymentFilterProject = ref(0);
const paymentFilterStatus = ref("");
const paymentTab = ref<"pending" | "all">("pending");
const paymentFormOpen = ref(false);
const editingPaymentId = ref<number | null>(null);
const paymentForm = reactive({
  contract_id: 0,
  stage_id: null as number | null,
  amount: 0,
  payment_date: new Date().toISOString().slice(0, 10),
  payee_name: "",
  payee_bank_name: "",
  payee_bank_account: "",
  comment: "",
});
const customerFormOpen = ref(false);
const editingCustomerId = ref<number | null>(null);
const customerForm = reactive({
  code: "",
  name: "",
  short_name: "",
  unified_credit_code: "",
  contact_name: "",
  contact_phone: "",
  contact_email: "",
  address: "",
  office_address: "",
  license_expiry_date: "",
  bank_name: "",
  bank_branch: "",
  bank_account: "",
  invoice_title: "",
  taxpayer_id: "",
  invoice_address: "",
  invoice_phone: "",
  notes: "",
  status: "ACTIVE",
});
const supplierFormOpen = ref(false);
const editingSupplierId = ref<number | null>(null);
const supplierForm = reactive({
  code: "",
  name: "",
  short_name: "",
  unified_credit_code: "",
  contact_name: "",
  contact_phone: "",
  contact_email: "",
  address: "",
  office_address: "",
  license_expiry_date: "",
  bank_name: "",
  bank_branch: "",
  bank_account: "",
  invoice_title: "",
  taxpayer_id: "",
  invoice_address: "",
  invoice_phone: "",
  notes: "",
  status: "ACTIVE",
});
const counterpartyKeyword = ref("");
const counterpartyStatus = ref("");
const boardFilterProject = ref(0);
const boardFilterType = ref("");
const boardFilterStatus = ref("");
const boardFilterDepartment = ref(0);
const boardFilterOwner = ref(0);
const boardFilterCustomer = ref(0);
const boardDataScope = ref<"OWNED" | "ALL">("OWNED");
const boardChartEl = ref<HTMLElement | null>(null);
const boardProfitChartEl = ref<HTMLElement | null>(null);
const syncSummary = ref("");
const projectChartEl = ref<HTMLElement | null>(null);
const trendChartEl = ref<HTMLElement | null>(null);
const userChartEl = ref<HTMLElement | null>(null);
const departmentChartEl = ref<HTMLElement | null>(null);
const stageChartEl = ref<HTMLElement | null>(null);
const statusChartEl = ref<HTMLElement | null>(null);
const projectStageChartEl = ref<HTMLElement | null>(null);
const workTypeChartEl = ref<HTMLElement | null>(null);
const budgetActualChartEl = ref<HTMLElement | null>(null);
const costBudgetActualChartEl = ref<HTMLElement | null>(null);
const projectCostChartEl = ref<HTMLElement | null>(null);
const departmentCostChartEl = ref<HTMLElement | null>(null);
const chartInstances: ECharts[] = [];
const statusSyncedAt = ref("");
const user = ref<DemoUser>({
  id: 1,
  name: "杨阳",
  department_name: "研发中心",
});
const form = reactive({
  project_id: 0,
  stage: "开发",
  work_type: "PROJECT",
  work_status: "LOCAL",
  start_date: new Date().toISOString().slice(0, 10),
  end_date: new Date().toISOString().slice(0, 10),
  quantity: 1,
  unit: "DAY",
  description: "",
});
const projectForm = reactive({
  code: "",
  name: "",
  project_type: "RND_PROJECT",
  owner_user_id: 0,
  department_id: 0,
  approver_user_id: 0,
  leader_user_id: 0,
  customer_id: null as number | null,
  start_date: "",
  planned_end_date: "",
  description: "",
  budget_days: 0,
  budget_cost: 0,
  status: "ACTIVE",
  allow_worklog: true,
});

const api = async <T,>(url: string, options?: RequestInit): Promise<T> => {
  const headers = new Headers(options?.headers);
  headers.set("Content-Type", "application/json");
  if (authMode.value === "mock")
    headers.set("X-Demo-User-Id", String(activeUserId.value));
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (response.status === 401 && body.detail === "AUTH_REQUIRED")
      authRequired.value = true;
    const detail = body.detail;
    const readableDetail = Array.isArray(detail)
      ? detail
          .map((item) => item?.msg || item?.message || JSON.stringify(item))
          .join("；")
      : detail;
    const message =
      typeof readableDetail === "string"
        ? readableDetail
        : JSON.stringify(readableDetail ?? `请求失败（${response.status}）`);
    throw new Error(message);
  }
  return response.status === 204 ? (undefined as T) : response.json();
};

const reportUrl = () => {
  const params = new URLSearchParams({
    period_start: reportPeriodStart.value,
    period_end: reportPeriodEnd.value,
  });
  if (reportDepartment.value)
    params.set("department_name", reportDepartment.value);
  return `/api/v1/reports/workload?${params.toString()}`;
};

const reportExportUrl = () => {
  const params = new URLSearchParams({
    period_start: reportPeriodStart.value,
    period_end: reportPeriodEnd.value,
  });
  if (reportDepartment.value)
    params.set("department_name", reportDepartment.value);
  return `/api/v1/reports/workload/export?${params.toString()}`;
};

const loadReport = async () => {
  if (reportPeriodStart.value > reportPeriodEnd.value) {
    errorMessage.value = "报表开始日期不能晚于结束日期";
    return;
  }
  try {
    report.value = await api<Report>(reportUrl());
    errorMessage.value = "";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "报表加载失败";
  }
};

const exportReport = async () => {
  if (reportPeriodStart.value > reportPeriodEnd.value) {
    errorMessage.value = "报表开始日期不能晚于结束日期";
    return;
  }
  try {
    exportReadyUrl.value = "";
    const headers = new Headers();
    if (authMode.value === "mock")
      headers.set("X-Demo-User-Id", String(activeUserId.value));
    const response = await fetch(reportExportUrl(), {
      headers,
      credentials: "same-origin",
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `导出失败（${response.status}）`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const filename =
      disposition.match(/filename="?([^";]+)"?/)?.[1] ||
      `xinye-worklog-details-${reportPeriodStart.value}-${reportPeriodEnd.value}.csv`;
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = decodeURIComponent(filename);
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    exportReadyUrl.value = reportExportUrl();
    successMessage.value =
      "明细文件已生成，若飞书未弹出下载，请查看飞书浏览器的下载列表";
  } catch (error) {
    exportReadyUrl.value = "";
    errorMessage.value =
      error instanceof Error ? error.message : "明细导出失败";
  }
};

const disposeCharts = () => {
  while (chartInstances.length) chartInstances.pop()?.dispose();
};

const renderCharts = async () => {
  await nextTick();
  disposeCharts();
  if (page.value !== "reports" || !report.value) return;
  const chartText = "#344054";
  const chartMuted = "#667085";
  const grid = { left: 12, right: 18, top: 24, bottom: 30, containLabel: true };
  const unit = "DAY";
  const unitName = "天";
  const rowsForUnit = (key: string) =>
    (report.value?.breakdowns[key] || []).filter((row) => row.unit === unit);
  const makeChart = (element: HTMLElement | null, option: EChartsOption) => {
    if (!element) return;
    element.innerHTML = "";
    const chart = init(element);
    chart.setOption(option);
    chartInstances.push(chart);
  };
  const projectRows = rowsForUnit("by_project_unit").slice(0, 10);
  const projectNames = projectRows.map((row) => row.name).reverse();
  const budgetRows = (report.value?.breakdowns.by_project_budget_actual || [])
    .slice(0, 10)
    .reverse();
  makeChart(budgetActualChartEl.value, {
    color: ["#98a2b3", "#0f766e"],
    tooltip: { trigger: "axis" },
    legend: {
      data: ["预算人天", "已发生人天"],
      bottom: 0,
      textStyle: { color: chartMuted },
    },
    grid: { left: 12, right: 18, top: 24, bottom: 48, containLabel: true },
    xAxis: {
      type: "value",
      name: "天",
      nameTextStyle: { color: chartMuted },
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    yAxis: {
      type: "category",
      data: budgetRows.map((row) => row.name),
      axisLabel: { color: chartText, width: 150, overflow: "truncate" },
    },
    series: [
      {
        name: "预算人天",
        type: "bar",
        data: budgetRows.map((row) => row.budget_days || 0),
        barMaxWidth: 14,
      },
      {
        name: "已发生人天",
        type: "bar",
        data: budgetRows.map((row) => row.actual_days || 0),
        barMaxWidth: 14,
      },
    ],
  });
  const costBudgetRows = (
    report.value?.breakdowns.by_project_budget_actual || []
  )
    .filter((row) => (row.budget_cost || 0) > 0 || (row.actual_cost || 0) > 0)
    .slice(0, 10)
    .reverse();
  makeChart(costBudgetActualChartEl.value, {
    color: ["#98a2b3", "#d97706"],
    tooltip: {
      trigger: "axis",
      valueFormatter: (value: number) =>
        `¥${Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`,
    },
    legend: {
      data: ["成本预算", "实际人工成本"],
      bottom: 0,
      textStyle: { color: chartMuted },
    },
    grid: { left: 12, right: 24, top: 24, bottom: 48, containLabel: true },
    xAxis: {
      type: "value",
      name: "元",
      nameTextStyle: { color: chartMuted },
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    yAxis: {
      type: "category",
      data: costBudgetRows.map((row) => row.name),
      axisLabel: { color: chartText, width: 150, overflow: "truncate" },
    },
    series: [
      {
        name: "成本预算",
        type: "bar",
        data: costBudgetRows.map((row) => row.budget_cost || 0),
        barMaxWidth: 14,
      },
      {
        name: "实际人工成本",
        type: "bar",
        data: costBudgetRows.map((row) => row.actual_cost || 0),
        barMaxWidth: 14,
      },
    ],
  });
  const projectCostRows = (report.value?.breakdowns.by_project_cost || [])
    .slice(0, 10)
    .reverse();
  makeChart(projectCostChartEl.value, {
    color: ["#d97706"],
    tooltip: {
      trigger: "axis",
      valueFormatter: (value: number) =>
        `¥${Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`,
    },
    grid,
    xAxis: {
      type: "value",
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    yAxis: {
      type: "category",
      data: projectCostRows.map((row) => row.name),
      axisLabel: { color: chartText, width: 150, overflow: "truncate" },
    },
    series: [
      {
        name: "实际人工成本",
        type: "bar",
        data: projectCostRows.map((row) => row.quantity),
        barMaxWidth: 18,
        label: {
          show: true,
          position: "right",
          color: chartText,
          formatter: (params: { value?: number }) =>
            `¥${Number(params.value || 0).toLocaleString("zh-CN")}`,
        },
      },
    ],
  });
  const departmentCostRows = (report.value?.breakdowns.by_department_cost || [])
    .slice(0, 10)
    .reverse();
  makeChart(departmentCostChartEl.value, {
    color: ["#3266b8"],
    tooltip: {
      trigger: "axis",
      valueFormatter: (value: number) =>
        `¥${Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`,
    },
    grid,
    xAxis: {
      type: "value",
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    yAxis: {
      type: "category",
      data: departmentCostRows.map((row) => row.name),
      axisLabel: { color: chartText },
    },
    series: [
      {
        name: "实际人工成本",
        type: "bar",
        data: departmentCostRows.map((row) => row.quantity),
        barMaxWidth: 20,
        label: {
          show: true,
          position: "right",
          color: chartText,
          formatter: (params: { value?: number }) =>
            `¥${Number(params.value || 0).toLocaleString("zh-CN")}`,
        },
      },
    ],
  });
  const departmentRows = rowsForUnit("by_department_unit").slice(0, 10);
  makeChart(departmentChartEl.value, {
    color: ["#0f766e"],
    tooltip: { trigger: "axis" },
    grid,
    xAxis: {
      type: "value",
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    yAxis: {
      type: "category",
      data: departmentRows.map((row) => row.name).reverse(),
      axisLabel: { color: chartText },
    },
    series: [
      {
        name: unitName,
        type: "bar",
        data: departmentRows.map((row) => row.quantity).reverse(),
        barMaxWidth: 24,
        label: { show: true, position: "right", color: chartText },
      },
    ],
  });
  const trendRows = rowsForUnit("by_day_unit").sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  makeChart(trendChartEl.value, {
    color: ["#3266b8"],
    tooltip: { trigger: "axis" },
    grid: { left: 12, right: 16, top: 24, bottom: 36, containLabel: true },
    xAxis: {
      type: "category",
      data: trendRows.map((row) => row.name.slice(5)),
      axisLabel: { color: chartMuted, rotate: trendRows.length > 8 ? 30 : 0 },
    },
    yAxis: {
      type: "value",
      name: unitName,
      nameTextStyle: { color: chartMuted },
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    series: [
      {
        name: unitName,
        type: "line",
        data: trendRows.map((row) => row.quantity),
        smooth: true,
        symbolSize: 7,
        lineStyle: { width: 3 },
        itemStyle: { color: "#3266b8" },
        areaStyle: { color: "#e8f0fb" },
        label: { show: false },
      },
    ],
  });
  makeChart(projectChartEl.value, {
    color: ["#0f766e"],
    tooltip: { trigger: "axis" },
    legend: { data: [unitName], bottom: 0, textStyle: { color: chartMuted } },
    grid,
    xAxis: {
      type: "value",
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    yAxis: {
      type: "category",
      data: projectNames,
      axisLabel: { color: chartText, width: 150, overflow: "truncate" },
    },
    series: [
      {
        name: unitName,
        type: "bar",
        data: projectRows.map((row) => row.quantity).reverse(),
        barMaxWidth: 18,
        label: { show: true, position: "right", color: chartText },
      },
    ],
  });
  const userRows = rowsForUnit("by_user_unit").slice(0, 8);
  makeChart(userChartEl.value, {
    color: [
      "#2563eb",
      "#0f766e",
      "#d97706",
      "#7c3aed",
      "#15803d",
      "#dc2626",
      "#0891b2",
      "#64748b",
    ],
    tooltip: { trigger: "item", formatter: "{b}: {c}" },
    legend: { show: false },
    grid,
    xAxis: {
      type: "value",
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    yAxis: {
      type: "category",
      data: userRows.map((row) => row.name).reverse(),
      axisLabel: { color: chartText },
    },
    series: [
      {
        name: unitName,
        type: "bar",
        data: userRows.map((row) => row.quantity).reverse(),
        barMaxWidth: 18,
        label: { show: true, position: "right", color: chartText },
      },
    ],
  });
  const stageRows = rowsForUnit("by_stage_unit").slice(0, 10).reverse();
  makeChart(stageChartEl.value, {
    color: ["#0891b2"],
    tooltip: { trigger: "axis" },
    legend: { show: false },
    grid,
    xAxis: {
      type: "category",
      data: stageRows.map((row) => row.name),
      axisLabel: { color: chartText, rotate: stageRows.length > 5 ? 24 : 0 },
    },
    yAxis: {
      type: "value",
      name: unitName,
      nameTextStyle: { color: chartMuted },
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    series: [
      {
        name: unitName,
        type: "bar",
        data: stageRows.map((row) => row.quantity),
        barMaxWidth: 28,
        itemStyle: { borderRadius: [6, 6, 0, 0] },
        label: { show: true, position: "top", color: chartText },
      },
    ],
  });
  const statusRows = report.value?.breakdowns.approval_status || [];
  makeChart(statusChartEl.value, {
    color: ["#12b76a", "#f79009", "#f04438", "#98a2b3"],
    tooltip: { trigger: "item", formatter: "{b}: {c}（{d}%）" },
    legend: { bottom: 0, textStyle: { color: chartMuted } },
    series: [
      {
        type: "pie",
        radius: ["42%", "70%"],
        center: ["50%", "45%"],
        label: { color: chartText, formatter: "{b}: {d}%" },
        data: statusRows.map((row) => ({
          name: statusLabel(row.name),
          value: row.quantity,
        })),
      },
    ],
  });
  const projectStageRows = rowsForUnit("by_project_stage_unit");
  const stackedProjects = projectRows
    .slice()
    .reverse()
    .map((row) => row.name);
  const stageNames = [
    ...new Set(
      projectStageRows
        .map((row) => row.stage)
        .filter((stage): stage is string => Boolean(stage)),
    ),
  ];
  const stageValue = (projectName: string, stage: string) =>
    projectStageRows.find(
      (row) => row.name === projectName && row.stage === stage,
    )?.quantity || 0;
  makeChart(projectStageChartEl.value, {
    color: [
      "#12b76a",
      "#2e90fa",
      "#7f56d9",
      "#f79009",
      "#f04438",
      "#06aed4",
      "#98a2b3",
    ],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) =>
        Array.isArray(params)
          ? `${(params[0] as { axisValue?: string }).axisValue}<br>${(
              params as Array<{ seriesName?: string; value?: number }>
            )
              .filter((item) => Number(item.value) > 0)
              .map((item) => `${item.seriesName}: ${item.value} ${unitName}`)
              .join("<br>")}`
          : "",
    },
    legend: { type: "scroll", top: 0, textStyle: { color: chartMuted } },
    grid: { left: 12, right: 18, top: 44, bottom: 62, containLabel: true },
    xAxis: {
      type: "category",
      data: stackedProjects,
      axisLabel: {
        color: chartText,
        rotate: 28,
        width: 90,
        overflow: "truncate",
      },
    },
    yAxis: {
      type: "value",
      max: 100,
      axisLabel: { color: chartMuted, formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    series: stageNames.map((stage) => ({
      name: stage,
      type: "bar",
      stack: "share",
      barMaxWidth: 28,
      data: stackedProjects.map((projectName) => {
        const total =
          projectRows.find((row) => row.name === projectName)?.quantity || 0;
        return total
          ? Number(((stageValue(projectName, stage) / total) * 100).toFixed(1))
          : 0;
      }),
      label: {
        show: true,
        position: "inside",
        formatter: (params: { value?: number }) =>
          Number(params.value) >= 8 ? `${params.value}%` : "",
      },
    })),
  });
  const workTypeRows = rowsForUnit("by_work_type_unit");
  makeChart(workTypeChartEl.value, {
    color: ["#7f56d9"],
    tooltip: { trigger: "axis" },
    legend: { show: false },
    grid,
    xAxis: {
      type: "value",
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: "#e4e7ec" } },
    },
    yAxis: {
      type: "category",
      data: workTypeRows.map((row) => reportTypeLabel(row.name)).reverse(),
      axisLabel: { color: chartText },
    },
    series: [
      {
        name: unitName,
        type: "bar",
        data: workTypeRows.map((row) => row.quantity).reverse(),
        barMaxWidth: 22,
        itemStyle: { borderRadius: [0, 6, 6, 0] },
        label: { show: true, position: "right", color: chartText },
      },
    ],
  });
};

const resizeCharts = () => chartInstances.forEach((chart) => chart.resize());

watch(
  [report, page],
  () => {
    if (page.value === "reports") renderCharts();
  },
  { deep: true },
);
watch(projectBoardRows, () => {
  if (page.value === "projectBoard") void renderBoardCharts();
});
watch(
  [
    projectFormOpen,
    adminWorklogFormOpen,
    adminPermissionFormOpen,
    personnelCostFormOpen,
    configurationFormOpen,
  ],
  ([
    projectOpen,
    worklogOpen,
    permissionOpen,
    personnelCostOpen,
    configurationOpen,
  ]) => {
    document.body.style.overflow =
      projectOpen ||
      worklogOpen ||
      permissionOpen ||
      personnelCostOpen ||
      configurationOpen
        ? "hidden"
        : "";
  },
);
watch(
  () => form.project_type,
  () => {
    if (
      form.project_id &&
      !fillableProjects.value.some(
        (project) => project.id === Number(form.project_id),
      )
    )
      form.project_id = 0;
  },
);
onBeforeUnmount(() => {
  document.body.style.overflow = "";
  disposeCharts();
  if (attachmentPreviewUrl.value) URL.revokeObjectURL(attachmentPreviewUrl.value);
  window.removeEventListener("resize", resizeCharts);
  document.removeEventListener("click", closeProjectPicker);
  window.removeEventListener("focus", refreshWorklogStatus);
  if (statusRefreshTimer) window.clearInterval(statusRefreshTimer);
});

const refresh = async () => {
  if (authRequired.value) return;
  loading.value = true;
  errorMessage.value = "";
  try {
    const me = await api<DemoUser>("/api/v1/me");
    user.value = me;
    if (authMode.value === "app") activeUserId.value = me.id;
    const [
      users,
      departmentList,
      projectList,
      customerList,
      supplierList,
      worklogList,
      approvals,
      processed,
      workbench,
      optionCatalog,
    ] = await Promise.all([
      api<DemoUser[]>("/api/v1/org/users?active_only=true"),
      api<OrgDepartment[]>("/api/v1/org/departments?active_only=true"),
      api<Project[]>("/api/v1/projects"),
      api<Customer[]>("/api/v1/customers?active_only=true"),
      api<Supplier[]>("/api/v1/suppliers?active_only=true"),
      api<{ items: Worklog[] }>("/api/v1/worklogs"),
      api<ApprovalTask[]>("/api/v1/approvals/pending"),
      api<ApprovalTask[]>("/api/v1/approvals/processed"),
      api<WorkbenchOverview>("/api/v1/workbench/overview"),
      api<ConfigCatalog>("/api/v1/config/options"),
    ]);
    demoUsers.value = users;
    departments.value = departmentList;
    projects.value = projectList;
    customers.value = customerList;
    suppliers.value = supplierList;
    worklogs.value = worklogList.items;
    pendingApprovals.value = approvals;
    processedApprovals.value = processed;
    workbenchOverview.value = workbench;
    configOptions.value = optionCatalog.options;
    const [reportResult, healthResult] = await Promise.allSettled([
      api<Report>(reportUrl()),
      api<IntegrationHealth>("/api/v1/integrations/health"),
    ]);
    if (reportResult.status === "fulfilled") {
      report.value = reportResult.value;
    } else {
      errorMessage.value =
        reportResult.reason instanceof Error
          ? `工时看板加载失败：${reportResult.reason.message}`
          : "工时看板加载失败";
    }
    if (healthResult.status === "fulfilled")
      integrationHealth.value = healthResult.value;
    if (canManage("integrations")) await refreshIntegrationOverview();
    if (
      !fillableProjects.value.some((item) => item.id === form.project_id) &&
      fillableProjects.value[0]
    )
      form.project_id = fillableProjects.value[0].id;
    const managementRefreshes: Promise<unknown>[] = [];
    if (canManage("worklogs")) managementRefreshes.push(refreshAdminWorklogs());
    if (canManage("personnel_costs"))
      managementRefreshes.push(refreshPersonnelCosts());
    if (canManage("admins"))
      managementRefreshes.push(refreshAdminPermissions());
    if (canManage("configuration"))
      managementRefreshes.push(refreshAdminConfiguration());
    await Promise.all(managementRefreshes);
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "数据加载失败";
  } finally {
    loading.value = false;
  }
};

const refreshWorklogStatus = async () => {
  if (
    authRequired.value ||
    statusRefreshBusy ||
    !["workbench", "worklogs", "detail"].includes(page.value)
  )
    return;
  statusRefreshBusy = true;
  try {
    const [worklogList, approvals, processed] = await Promise.all([
      api<{ items: Worklog[] }>("/api/v1/worklogs"),
      api<ApprovalTask[]>("/api/v1/approvals/pending"),
      api<ApprovalTask[]>("/api/v1/approvals/processed"),
    ]);
    worklogs.value = worklogList.items;
    pendingApprovals.value = approvals;
    processedApprovals.value = processed;
    if (page.value === "detail" && selectedTask.value) {
      selectedTask.value = await api<ApprovalTask>(
        `/api/v1/worklogs/${selectedTask.value.worklog_id}/approval`,
      );
    }
    statusSyncedAt.value = new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    // 后台轮询失败不打断当前页面；下一次轮询或手动刷新继续尝试。
  } finally {
    statusRefreshBusy = false;
  }
};

const startStatusPolling = () => {
  if (statusRefreshTimer) return;
  statusRefreshTimer = window.setInterval(() => {
    void refreshWorklogStatus();
  }, 30000);
  window.addEventListener("focus", refreshWorklogStatus);
};

const switchUser = async () => {
  page.value = "workbench";
  selectedTask.value = null;
  approvalTab.value = "pending";
  await refresh();
};
const requestFeishuAuthCode = () =>
  new Promise<string>((resolve, reject) => {
    type FeishuBrowser = typeof window & {
      tt?: {
        requestAccess?: (options: {
          scopeList: string[];
          appID: string;
          success: (result: { code?: string }) => void;
          fail: (error: unknown) => void;
        }) => void;
        requestAuthCode?: (options: {
          appId: string;
          success: (result: { code?: string }) => void;
          fail: (error: unknown) => void;
        }) => void;
      };
      h5sdk?: { ready?: (callback: () => void) => void };
    };
    const browser = window as FeishuBrowser;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const finishResolve = (code: string) => {
      if (timeout) clearTimeout(timeout);
      resolve(code);
    };
    const finishReject = (message: string) => {
      if (timeout) clearTimeout(timeout);
      reject(new Error(message));
    };
    const describeFailure = (error: unknown) => {
      if (typeof error === "string") return error;
      if (error && typeof error === "object") {
        const detail = error as {
          errMsg?: unknown;
          errorMessage?: unknown;
          errorCode?: unknown;
          errno?: unknown;
          errCode?: unknown;
          code?: unknown;
        };
        const message = [detail.errMsg, detail.errorMessage].find(
          (value) => typeof value === "string" && value.trim(),
        );
        const code = [
          detail.errno,
          detail.errorCode,
          detail.errCode,
          detail.code,
        ].find(
          (value) => typeof value === "string" || typeof value === "number",
        );
        if (message || code)
          return [message, code ? `错误码 ${code}` : ""]
            .filter(Boolean)
            .join("，");
        try {
          return JSON.stringify(error);
        } catch {
          return "";
        }
      }
      return "";
    };
    if (!authAppId.value) {
      reject(new Error("飞书应用未配置，请联系系统管理员"));
      return;
    }
    const finishFailure = (error: unknown) => {
      const detail = describeFailure(error);
      finishReject(
        detail
          ? `飞书授权失败：${detail}`
          : "飞书授权失败，请检查应用是否已启用并重新打开页面",
      );
    };
    const requestLegacyCode = (modernFailure = "") => {
      if (!browser.tt?.requestAuthCode) {
        finishReject(
          "飞书授权组件未加载，请在飞书客户端内打开系统；如果已在飞书内打开，请刷新页面重试",
        );
        return;
      }
      try {
        browser.tt.requestAuthCode({
          appId: authAppId.value,
          success: (result) =>
            result.code
              ? finishResolve(result.code)
              : finishReject("飞书未返回授权码，请刷新后重试"),
          fail: (error) => {
            const detail = describeFailure(error);
            if (modernFailure) {
              finishReject(
                `新版飞书授权失败：${modernFailure}；兼容授权失败：${detail || "请检查应用配置并重新打开页面"}`,
              );
            } else {
              finishFailure(error);
            }
          },
        });
      } catch {
        finishReject("无法打开飞书授权，请刷新页面后重试");
      }
    };
    const requestCode = () => {
      if (!browser.tt?.requestAccess) {
        requestLegacyCode();
        return;
      }
      try {
        browser.tt.requestAccess({
          scopeList: [],
          appID: authAppId.value,
          success: (result) =>
            result.code
              ? finishResolve(result.code)
              : finishReject("飞书未返回授权码，请刷新后重试"),
          fail: (error) => {
            const detail = describeFailure(error);
            const errno =
              error && typeof error === "object"
                ? (error as { errno?: unknown }).errno
                : undefined;
            const errorText = `${errno ?? ""} ${detail}`;
            if (
              errno === 103 ||
              errno === "103" ||
              /(?:^|\D)103(?:\D|$)/.test(errorText)
            )
              requestLegacyCode();
            else if (
              errno === 2700002 ||
              errno === "2700002" ||
              /(?:^|\D)2700002(?:\D|$)/.test(errorText)
            )
              requestLegacyCode(detail);
            else finishFailure(error);
          },
        });
      } catch {
        finishReject("无法打开飞书授权，请刷新页面后重试");
      }
    };
    if (browser.h5sdk?.ready) {
      timeout = setTimeout(
        () =>
          finishReject(
            "飞书授权组件初始化超时，请关闭当前页面后从飞书重新打开",
          ),
        8000,
      );
      try {
        browser.h5sdk.ready(requestCode);
      } catch {
        finishReject("飞书授权组件初始化失败，请关闭当前页面后重新打开");
      }
    } else requestCode();
  });
const loginWithFeishu = async () => {
  loading.value = true;
  errorMessage.value = "";
  try {
    const code = await requestFeishuAuthCode();
    await api<{ ok: boolean }>("/api/v1/auth/feishu/exchange", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
    authRequired.value = false;
    await refresh();
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "飞书登录失败";
  } finally {
    loading.value = false;
  }
};
const logout = async () => {
  try {
    await api<{ ok: boolean }>("/api/v1/auth/logout", { method: "POST" });
  } finally {
    authRequired.value = true;
    page.value = "workbench";
    selectedTask.value = null;
  }
};
const go = (target: Page) => {
  const permissionByPage: Partial<Record<Page, ManagementPermission>> = {
    projects: "projects",
    projectDetail: "projects",
    projectContracts: "contracts",
    contractDetail: "contracts",
    projectReceipts: "receipts",
    projectPayments: "payments",
    projectBoard: "project_board",
    suppliers: "counterparties",
    customers: "counterparties",
    adminWorklogs: "worklogs",
    personnelCosts: "personnel_costs",
    integrations: "integrations",
    adminPermissions: "admins",
    configuration: "configuration",
  };
  const requiredPermission = permissionByPage[target];
  if (requiredPermission && !canManage(requiredPermission)) {
    const label =
      permissionLabels.find((item) => item.key === requiredPermission)?.label ||
      "该管理功能";
    errorMessage.value = `你没有${label}权限`;
    return;
  }
  mobileManagementOpen.value = false;
  page.value = target;
  window.scrollTo(0, 0);
  errorMessage.value = "";
  successMessage.value = "";
  if (["workbench", "worklogs"].includes(target)) void refreshWorklogStatus();
  if (target === "adminWorklogs") void refreshAdminWorklogs();
  if (target === "personnelCosts") void refreshPersonnelCosts();
  if (target === "adminPermissions") void refreshAdminPermissions();
  if (target === "projects") void refreshProjectPage();
  if (target === "customers") void refreshCustomers();
  if (target === "suppliers") void refreshSuppliers();
  if (target === "projectContracts") void refreshContracts();
  if (target === "projectReceipts") {
    receiptTab.value = canManage("cash_approval") ? "pending" : "all";
    void refreshReceipts();
  }
  if (target === "projectPayments") {
    paymentTab.value = canManage("cash_approval") ? "pending" : "all";
    void refreshPayments();
  }
  if (target === "projectBoard") void refreshProjectBoard();
  if (target === "projectDetail") void refreshProjectFinance();
};
const refreshCustomers = async () => {
  if (!canManage("counterparties")) return;
  counterpartiesLoading.value = true;
  try {
    customers.value = await api<Customer[]>("/api/v1/customers?active_only=false");
  } finally {
    counterpartiesLoading.value = false;
  }
};
const refreshSuppliers = async () => {
  if (!canManage("counterparties")) return;
  counterpartiesLoading.value = true;
  try {
    suppliers.value = await api<Supplier[]>("/api/v1/suppliers?active_only=false");
  } finally {
    counterpartiesLoading.value = false;
  }
};
const contractUrl = () => {
  const params = new URLSearchParams();
  if (contractFilterProject.value) params.set("project_id", String(contractFilterProject.value));
  if (contractFilterType.value || contractTab.value)
    params.set("contract_type", contractFilterType.value || contractTab.value);
  if (contractFilterCounterparty.value) params.set("counterparty_id", String(contractFilterCounterparty.value));
  return `/api/v1/contracts?${params.toString()}`;
};
const refreshContracts = async () => {
  if (!canManage("contracts")) return;
  contractsLoading.value = true;
  try {
    projectContracts.value = await api<ProjectContract[]>(contractUrl());
  } finally {
    contractsLoading.value = false;
  }
};
const refreshCashContractOptions = async (contractType: "INCOME" | "EXPENSE") => {
  const loading = contractType === "INCOME" ? incomeContractsLoading : expenseContractsLoading;
  loading.value = true;
  try {
    const options = await api<ProjectContract[]>(
      `/api/v1/contracts?contract_type=${contractType}`,
    );
    if (contractType === "INCOME") incomeContractOptions.value = options;
    else expenseContractOptions.value = options;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "可用合同加载失败";
  } finally {
    loading.value = false;
  }
};
const resetContractForm = () => {
  editingContractId.value = null;
  contractFormOpen.value = false;
  contractAttachments.value = [];
  Object.assign(contractForm, {
    contract_no: "",
    name: "",
    project_id: 0,
    contract_type: "INCOME",
    counterparty_type: "CUSTOMER",
    counterparty_id: 0,
    amount: 0,
    sign_date: "",
    start_date: "",
    end_date: "",
    status: "ACTIVE",
    description: "",
  });
};
const openContractForm = () => {
  resetContractForm();
  contractFormOpen.value = true;
};
const editContract = (item: ProjectContract) => {
  editingContractId.value = item.id;
  contractFormOpen.value = true;
  contractAttachments.value = [];
  Object.assign(contractForm, {
    contract_no: item.contract_no,
    name: item.name,
    project_id: item.project_id,
    contract_type: item.contract_type,
    counterparty_type: item.counterparty_type,
    counterparty_id: item.counterparty_id,
    amount: item.amount,
    sign_date: item.sign_date || "",
    start_date: item.start_date || "",
    end_date: item.end_date || "",
    status: item.status,
    description: item.description || "",
  });
  void loadContractAttachments(item.id);
};
const saveContract = async () => {
  if (!contractForm.project_id || !contractForm.counterparty_id) {
    errorMessage.value = "请选择项目和往来单位";
    return;
  }
  try {
    const editingId = editingContractId.value;
    const wasEditing = Boolean(editingId);
    const url = editingId
      ? `/api/v1/contracts/${editingId}`
      : "/api/v1/contracts";
    const payload = {
      ...contractForm,
      sign_date: contractForm.sign_date || null,
      start_date: contractForm.start_date || null,
      end_date: contractForm.end_date || null,
    };
    const savedContract = await api<ProjectContract>(url, {
      method: editingId ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    editingContractId.value = savedContract.id;
    contractFormOpen.value = true;
    Object.assign(contractForm, {
      contract_no: savedContract.contract_no,
      name: savedContract.name,
      project_id: savedContract.project_id,
      contract_type: savedContract.contract_type,
      counterparty_type: savedContract.counterparty_type,
      counterparty_id: savedContract.counterparty_id,
      amount: savedContract.amount,
      sign_date: savedContract.sign_date || "",
      start_date: savedContract.start_date || "",
      end_date: savedContract.end_date || "",
      status: savedContract.status,
      description: savedContract.description || "",
    });
    await Promise.all([refreshContracts(), loadContractAttachments(savedContract.id)]);
    if (selectedContract.value?.id === savedContract.id) {
      selectedContract.value = await api<ProjectContract>(`/api/v1/contracts/${savedContract.id}`);
      if (page.value !== "contractDetail") contractFormOpen.value = false;
    }
    successMessage.value = wasEditing ? "合同已更新" : "合同已创建";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "合同保存失败";
  }
};
const loadContractAttachments = async (contractId: number) => {
  contractAttachmentsLoading.value = true;
  try {
    contractAttachments.value = await api<ContractAttachment[]>(
      `/api/v1/contracts/${contractId}/attachments`,
    );
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "合同附件加载失败";
  } finally {
    contractAttachmentsLoading.value = false;
  }
};
const attachmentSizeText = (size: number) => {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};
const attachmentKindLabel = (kind: ContractAttachment["preview_kind"]) =>
  ({ word: "Word", excel: "Excel", powerpoint: "PPT", pdf: "PDF", image: "图片", download: "文件" })[kind];
const attachmentAuthHeaders = () => {
  const headers = new Headers();
  if (authMode.value === "mock") headers.set("X-Demo-User-Id", String(activeUserId.value));
  return headers;
};
const uploadContractAttachment = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || !editingContractId.value) return;
  contractAttachmentUploading.value = true;
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`/api/v1/contracts/${editingContractId.value}/attachments`, {
      method: "POST",
      headers: attachmentAuthHeaders(),
      credentials: "same-origin",
      body: formData,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      if (response.status === 413) throw new Error("附件不能超过 50MB");
      if (response.status === 401) throw new Error("登录已失效，请重新打开飞书页面");
      throw new Error(typeof body.detail === "string" ? body.detail : `上传失败（${response.status}）`);
    }
    await loadContractAttachments(editingContractId.value);
    successMessage.value = "合同附件已上传";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "合同附件上传失败";
  } finally {
    contractAttachmentUploading.value = false;
  }
};
const closeAttachmentPreview = () => {
  if (attachmentPreviewUrl.value) URL.revokeObjectURL(attachmentPreviewUrl.value);
  attachmentPreviewOpen.value = false;
  attachmentPreviewLoading.value = false;
  attachmentPreviewUrl.value = "";
  attachmentPreviewError.value = "";
  attachmentPreviewItem.value = null;
};
const previewContractAttachment = async (attachment: ContractAttachment) => {
  if (!attachment.can_preview) return;
  closeAttachmentPreview();
  attachmentPreviewItem.value = attachment;
  attachmentPreviewOpen.value = true;
  attachmentPreviewLoading.value = true;
  try {
    const response = await fetch(`/api/v1/contract-attachments/${attachment.id}/preview`, {
      headers: attachmentAuthHeaders(),
      credentials: "same-origin",
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : `预览失败（${response.status}）`);
    }
    attachmentPreviewUrl.value = URL.createObjectURL(await response.blob());
  } catch (error) {
    attachmentPreviewError.value = error instanceof Error ? error.message : "合同附件预览失败";
  } finally {
    attachmentPreviewLoading.value = false;
  }
};
const downloadContractAttachment = async (attachment: ContractAttachment) => {
  try {
    const response = await fetch(`/api/v1/contract-attachments/${attachment.id}/download`, {
      headers: attachmentAuthHeaders(),
      credentials: "same-origin",
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : `下载失败（${response.status}）`);
    }
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = attachment.file_name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "合同附件下载失败";
  }
};
const deleteContractAttachment = async (attachment: ContractAttachment) => {
  if (!window.confirm(`确定删除附件“${attachment.file_name}”吗？`)) return;
  try {
    await api(`/api/v1/contract-attachments/${attachment.id}`, { method: "DELETE" });
    const reloadContractId = editingContractId.value || selectedContract.value?.id;
    if (reloadContractId) await loadContractAttachments(reloadContractId);
    successMessage.value = "合同附件已删除";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "合同附件删除失败";
  }
};
const deleteContract = async (item: ProjectContract) => {
  if (!window.confirm(`确定终止合同“${item.name}”吗？`)) return;
  try {
    await api(`/api/v1/contracts/${item.id}`, { method: "DELETE" });
    await refreshContracts();
    successMessage.value = "合同已终止";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "合同删除失败";
  }
};
const activateContract = async (item: ProjectContract) => {
  if (!window.confirm(`确定激活合同“${item.name}”吗？阶段金额合计必须等于合同金额。`)) return;
  try {
    await api<ProjectContract>(`/api/v1/contracts/${item.id}/activate`, {
      method: "POST",
    });
    await refreshContracts();
    successMessage.value = "合同已激活";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "合同激活失败";
  }
};
const contractStagesOf = (contractId: number) => projectContractStages.value.filter((item) => item.contract_id === contractId);
const loadContractStages = async (contractId: number) => {
  stageContractId.value = contractId;
  projectContractStages.value = [];
  contractStagesLoading.value = true;
  try {
    projectContractStages.value = await api<ProjectContractStage[]>(
      `/api/v1/contracts/${contractId}/stages`,
    );
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "合同阶段加载失败";
  } finally {
    contractStagesLoading.value = false;
  }
};
const loadContractDetailStages = async (contractId: number) => {
  contractDetailStages.value = await api<ProjectContractStage[]>(
    `/api/v1/contracts/${contractId}/stages`,
  );
};
const openContractDetail = async (item: ProjectContract) => {
  if (!canManage("contracts")) {
    errorMessage.value = "你没有合同管理权限";
    return;
  }
  selectedContract.value = item;
  contractDetailStages.value = [];
  contractAttachments.value = [];
  contractDetailError.value = "";
  contractDetailLoading.value = true;
  page.value = "contractDetail";
  window.scrollTo(0, 0);
  try {
    const [contract, stages] = await Promise.all([
      api<ProjectContract>(`/api/v1/contracts/${item.id}`),
      api<ProjectContractStage[]>(`/api/v1/contracts/${item.id}/stages`),
      loadContractAttachments(item.id),
    ]);
    selectedContract.value = contract;
    contractDetailStages.value = stages;
  } catch (error) {
    contractDetailError.value =
      error instanceof Error ? error.message : "合同详情加载失败";
  } finally {
    contractDetailLoading.value = false;
  }
};
const closeContractDetail = () => {
  selectedContract.value = null;
  contractDetailStages.value = [];
  contractAttachments.value = [];
  contractDetailError.value = "";
  go("projectContracts");
};
const openContractStages = (item: ProjectContract) => {
  stageContractId.value = item.id;
  stageListOpen.value = true;
  stageFormOpen.value = false;
  void loadContractStages(item.id);
};
const openStageForm = (contractId: number, stage: ProjectContractStage | null = null) => {
  stageContractId.value = contractId;
  editingStageId.value = stage?.id ?? null;
  stageFormOpen.value = true;
  Object.assign(stageForm, {
    name: stage?.name || "",
    amount: stage?.amount || 0,
    planned_date: stage?.planned_date || "",
    remind_days_before: stage?.remind_days_before ?? 7,
    reminder_paused: stage?.reminder_paused ?? false,
    sort_order: stage?.sort_order || 0,
    status: stage?.status || "PENDING",
  });
  if (!stage) void loadContractStages(contractId);
};
const saveStage = async () => {
  const contractId = stageContractId.value;
  if (!stageForm.name) {
    errorMessage.value = "请填写阶段名称";
    return;
  }
  try {
    const url = editingStageId.value
      ? `/api/v1/contract-stages/${editingStageId.value}`
      : `/api/v1/contracts/${contractId}/stages`;
    const payload = {
      ...stageForm,
      planned_date: stageForm.planned_date || null,
    };
    await api<ProjectContractStage>(url, {
      method: editingStageId.value ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    const wasEditing = Boolean(editingStageId.value);
    stageFormOpen.value = false;
    const reloads: Promise<unknown>[] = [refreshContracts()];
    if (stageListOpen.value) reloads.push(loadContractStages(contractId));
    if (selectedContract.value?.id === contractId) {
      reloads.push(loadContractDetailStages(contractId));
      const updatedContract = api<ProjectContract>(`/api/v1/contracts/${contractId}`);
      reloads.push(updatedContract.then((contract) => { selectedContract.value = contract; }));
    }
    await Promise.all(reloads);
    successMessage.value = wasEditing ? "阶段已更新" : "阶段已创建";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "阶段保存失败";
  }
};
const deleteStage = async (stage: ProjectContractStage) => {
  if (!window.confirm(`确定删除阶段“${stage.name}”吗？`)) return;
  try {
    await api(`/api/v1/contract-stages/${stage.id}`, { method: "DELETE" });
    const reloads: Promise<unknown>[] = [refreshContracts()];
    if (stageListOpen.value) reloads.push(loadContractStages(stage.contract_id));
    if (selectedContract.value?.id === stage.contract_id) {
      reloads.push(loadContractDetailStages(stage.contract_id));
    }
    await Promise.all(reloads);
    successMessage.value = "阶段已删除";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "阶段删除失败";
  }
};
const receiptUrl = () => {
  const params = new URLSearchParams();
  if (receiptFilterProject.value) params.set("project_id", String(receiptFilterProject.value));
  if (receiptFilterStatus.value) params.set("status", receiptFilterStatus.value);
  return `/api/v1/receipts?${params.toString()}`;
};
const refreshReceipts = async () => {
  if (!canManage("receipts")) return;
  receiptsLoading.value = true;
  try {
    receipts.value = await api<Receipt[]>(receiptUrl());
  } finally {
    receiptsLoading.value = false;
  }
};
const openReceiptApproval = async (item: Receipt) => {
  try {
    selectedReceipt.value = await api<Receipt>(`/api/v1/receipts/${item.id}`);
    go("receiptDetail");
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "收款单详情加载失败";
  }
};
const resetReceiptForm = () => {
  editingReceiptId.value = null;
  receiptFormOpen.value = false;
  Object.assign(receiptForm, {
    contract_id: 0,
    stage_id: null,
    amount: 0,
    receipt_date: new Date().toISOString().slice(0, 10),
    payer_name: "",
    payer_bank_name: "",
    payer_bank_account: "",
    comment: "",
  });
};
const openReceiptForm = async (item: Receipt | null = null) => {
  editingReceiptId.value = item?.id ?? null;
  receiptFormOpen.value = true;
  Object.assign(receiptForm, {
    contract_id: item?.contract_id || 0,
    stage_id: item?.stage_id || null,
    amount: item?.amount || 0,
    receipt_date: item?.receipt_date || new Date().toISOString().slice(0, 10),
    payer_name: item?.payer_name || "",
    payer_bank_name: item?.payer_bank_name || "",
    payer_bank_account: item?.payer_bank_account || "",
    comment: item?.comment || "",
  });
  await refreshCashContractOptions("INCOME");
  if (receiptForm.contract_id) await loadContractStages(receiptForm.contract_id);
};
const saveReceipt = async () => {
  if (
    !receiptForm.contract_id ||
    !receiptForm.stage_id ||
    !receiptForm.payer_name ||
    !receiptForm.payer_bank_name ||
    !receiptForm.payer_bank_account ||
    !receiptForm.amount
  ) {
    errorMessage.value = "请填写收入合同、收款阶段、付款方姓名、付款银行、付款账号和金额";
    return;
  }
  if (Number(receiptForm.amount) > receiptStageRemaining.value) {
    errorMessage.value = `本次金额不能超过阶段剩余应收 ${moneyText(receiptStageRemaining.value)}`;
    return;
  }
  try {
    const wasEditing = Boolean(editingReceiptId.value);
    const url = editingReceiptId.value
      ? `/api/v1/receipts/${editingReceiptId.value}`
      : "/api/v1/receipts";
    await api<Receipt>(url, {
      method: editingReceiptId.value ? "PATCH" : "POST",
      body: JSON.stringify(receiptForm),
    });
    resetReceiptForm();
    await refreshReceipts();
    successMessage.value = wasEditing ? "收款单已更新" : "收款单已提交，等待出纳审批";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "收款单保存失败";
  }
};
const approveReceipt = async (item: Receipt) => {
  try {
    const updated = await api<Receipt>(`/api/v1/receipts/${item.id}/approve`, { method: "POST" });
    if (selectedReceipt.value?.id === updated.id) selectedReceipt.value = updated;
    await refreshReceipts();
    successMessage.value = "收款单已确认入账";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "收款审批失败";
  }
};
const rejectReceipt = async (item: Receipt) => {
  const reason = window.prompt("请输入驳回原因", "");
  if (!reason) return;
  try {
    const updated = await api<Receipt>(`/api/v1/receipts/${item.id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
    if (selectedReceipt.value?.id === updated.id) selectedReceipt.value = updated;
    await refreshReceipts();
    successMessage.value = "收款单已驳回";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "收款驳回失败";
  }
};
const reverseReceipt = async (item: Receipt) => {
  if (!window.confirm(`确定冲销收款单 ${item.receipt_no} 吗？`)) return;
  try {
    await api<Receipt>(`/api/v1/receipts/${item.id}/reverse`, { method: "POST" });
    await refreshReceipts();
    successMessage.value = "收款单已冲销";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "收款冲销失败";
  }
};
const deleteReceipt = async (item: Receipt) => {
  if (!window.confirm(`确定删除收款单 ${item.receipt_no} 吗？`)) return;
  try {
    await api(`/api/v1/receipts/${item.id}`, { method: "DELETE" });
    await refreshReceipts();
    successMessage.value = "收款单已删除";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "收款单删除失败";
  }
};
const paymentUrl = () => {
  const params = new URLSearchParams();
  if (paymentFilterProject.value) params.set("project_id", String(paymentFilterProject.value));
  if (paymentFilterStatus.value) params.set("status", paymentFilterStatus.value);
  return `/api/v1/payments?${params.toString()}`;
};
const refreshPayments = async () => {
  if (!canManage("payments")) return;
  paymentsLoading.value = true;
  try {
    payments.value = await api<Payment[]>(paymentUrl());
  } finally {
    paymentsLoading.value = false;
  }
};
const openPaymentApproval = async (item: Payment) => {
  try {
    selectedPayment.value = await api<Payment>(`/api/v1/payments/${item.id}`);
    go("paymentDetail");
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "付款单详情加载失败";
  }
};
const resetPaymentForm = () => {
  editingPaymentId.value = null;
  paymentFormOpen.value = false;
  Object.assign(paymentForm, {
    contract_id: 0,
    stage_id: null,
    amount: 0,
    payment_date: new Date().toISOString().slice(0, 10),
    payee_name: "",
    payee_bank_name: "",
    payee_bank_account: "",
    comment: "",
  });
};
const openPaymentForm = async (item: Payment | null = null) => {
  editingPaymentId.value = item?.id ?? null;
  paymentFormOpen.value = true;
  Object.assign(paymentForm, {
    contract_id: item?.contract_id || 0,
    stage_id: item?.stage_id || null,
    amount: item?.amount || 0,
    payment_date: item?.payment_date || new Date().toISOString().slice(0, 10),
    payee_name: item?.payee_name || "",
    payee_bank_name: item?.payee_bank_name || "",
    payee_bank_account: item?.payee_bank_account || "",
    comment: item?.comment || "",
  });
  await refreshCashContractOptions("EXPENSE");
  if (paymentForm.contract_id) await loadContractStages(paymentForm.contract_id);
};
const savePayment = async () => {
  if (
    !paymentForm.contract_id ||
    !paymentForm.stage_id ||
    !paymentForm.payee_name ||
    !paymentForm.payee_bank_name ||
    !paymentForm.payee_bank_account ||
    !paymentForm.amount
  ) {
    errorMessage.value = "请填写支出合同、付款阶段、收款方姓名、收款银行、收款账号和金额";
    return;
  }
  if (Number(paymentForm.amount) > paymentStageRemaining.value) {
    errorMessage.value = `本次金额不能超过阶段剩余应付 ${moneyText(paymentStageRemaining.value)}`;
    return;
  }
  try {
    const wasEditing = Boolean(editingPaymentId.value);
    const url = editingPaymentId.value
      ? `/api/v1/payments/${editingPaymentId.value}`
      : "/api/v1/payments";
    await api<Payment>(url, {
      method: editingPaymentId.value ? "PATCH" : "POST",
      body: JSON.stringify(paymentForm),
    });
    resetPaymentForm();
    await refreshPayments();
    successMessage.value = wasEditing ? "付款单已更新" : "付款单已提交，等待出纳审批";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "付款单保存失败";
  }
};
const approvePayment = async (item: Payment) => {
  try {
    const updated = await api<Payment>(`/api/v1/payments/${item.id}/approve`, { method: "POST" });
    if (selectedPayment.value?.id === updated.id) selectedPayment.value = updated;
    await refreshPayments();
    successMessage.value = "付款单已确认支付";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "付款审批失败";
  }
};
const rejectPayment = async (item: Payment) => {
  const reason = window.prompt("请输入驳回原因", "");
  if (!reason) return;
  try {
    const updated = await api<Payment>(`/api/v1/payments/${item.id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
    if (selectedPayment.value?.id === updated.id) selectedPayment.value = updated;
    await refreshPayments();
    successMessage.value = "付款单已驳回";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "付款驳回失败";
  }
};
const reversePayment = async (item: Payment) => {
  if (!window.confirm(`确定冲销付款单 ${item.payment_no} 吗？`)) return;
  try {
    await api<Payment>(`/api/v1/payments/${item.id}/reverse`, { method: "POST" });
    await refreshPayments();
    successMessage.value = "付款单已冲销";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "付款冲销失败";
  }
};
const deletePayment = async (item: Payment) => {
  if (!window.confirm(`确定删除付款单 ${item.payment_no} 吗？`)) return;
  try {
    await api(`/api/v1/payments/${item.id}`, { method: "DELETE" });
    await refreshPayments();
    successMessage.value = "付款单已删除";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "付款单删除失败";
  }
};
const resetCounterpartyForm = (target: "customers" | "suppliers") => {
  const form = target === "customers" ? customerForm : supplierForm;
  Object.assign(form, {
    code: "",
    name: "",
    short_name: "",
    unified_credit_code: "",
    contact_name: "",
    contact_phone: "",
    contact_email: "",
    address: "",
    office_address: "",
    license_expiry_date: "",
    bank_name: "",
    bank_branch: "",
    bank_account: "",
    invoice_title: "",
    taxpayer_id: "",
    invoice_address: "",
    invoice_phone: "",
    notes: "",
    status: "ACTIVE",
  });
  if (target === "customers") {
    editingCustomerId.value = null;
    customerFormOpen.value = true;
  } else {
    editingSupplierId.value = null;
    supplierFormOpen.value = true;
  }
};
const editCounterparty = (target: "customers" | "suppliers", item: Customer | Supplier) => {
  const form = target === "customers" ? customerForm : supplierForm;
  Object.assign(form, {
    code: item.code,
    name: item.name,
    short_name: item.short_name || "",
    unified_credit_code: item.unified_credit_code || "",
    contact_name: item.contact_name || "",
    contact_phone: item.contact_phone || "",
    contact_email: item.contact_email || "",
    address: item.address || "",
    office_address: item.office_address || "",
    license_expiry_date: item.license_expiry_date || "",
    bank_name: item.bank_name || "",
    bank_branch: item.bank_branch || "",
    bank_account: item.bank_account || "",
    invoice_title: item.invoice_title || "",
    taxpayer_id: item.taxpayer_id || "",
    invoice_address: item.invoice_address || "",
    invoice_phone: item.invoice_phone || "",
    notes: item.notes || "",
    status: item.status,
  });
  if (target === "customers") {
    editingCustomerId.value = item.id;
    customerFormOpen.value = true;
  } else {
    editingSupplierId.value = item.id;
    supplierFormOpen.value = true;
  }
};
const saveCounterparty = async (target: "customers" | "suppliers") => {
  const isCustomer = target === "customers";
  const form = isCustomer ? customerForm : supplierForm;
  if (!form.code || !form.name) {
    errorMessage.value = "请填写编号和名称";
    return;
  }
  try {
    const editingId = isCustomer ? editingCustomerId.value : editingSupplierId.value;
    const url = editingId
      ? `/api/v1/${target}/${editingId}`
      : `/api/v1/${target}`;
    const payload = {
      ...form,
      license_expiry_date: form.license_expiry_date || null,
    };
    await api<Customer>(url, {
      method: editingId ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    if (isCustomer) {
      customerFormOpen.value = false;
      await refreshCustomers();
    } else {
      supplierFormOpen.value = false;
      await refreshSuppliers();
    }
    successMessage.value = editingId ? "往来单位已更新" : "往来单位已创建";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "往来单位保存失败";
  }
};
const deleteCounterparty = async (target: "customers" | "suppliers", item: Customer | Supplier) => {
  if (!window.confirm(`确定停用“${item.name}”吗？`)) return;
  try {
    await api(`/api/v1/${target}/${item.id}`, { method: "DELETE" });
    if (target === "customers") await refreshCustomers();
    else await refreshSuppliers();
    successMessage.value = "往来单位已停用";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "往来单位删除失败";
  }
};
const boardUrl = () => {
  const params = new URLSearchParams({ data_scope: boardDataScope.value });
  if (boardFilterProject.value) params.set("project_id", String(boardFilterProject.value));
  if (boardFilterType.value) params.set("project_type", boardFilterType.value);
  if (boardFilterStatus.value) params.set("status", boardFilterStatus.value);
  if (boardFilterDepartment.value) params.set("department_id", String(boardFilterDepartment.value));
  if (boardFilterOwner.value) params.set("owner_user_id", String(boardFilterOwner.value));
  if (boardFilterCustomer.value) params.set("customer_id", String(boardFilterCustomer.value));
  return `/api/v1/projects/board?${params.toString()}`;
};
const refreshProjectBoard = async () => {
  if (!canManage("project_board")) return;
  boardLoading.value = true;
  try {
    projectBoardRows.value = await api<ProjectBoardRow[]>(boardUrl());
  } finally {
    boardLoading.value = false;
  }
  void renderBoardCharts();
};
const boardTotals = computed(() => {
  const rows = projectBoardRows.value;
  return rows.reduce(
    (total, row) => ({
      contract_income: total.contract_income + Number(row.contract_income || 0),
      contract_expense: total.contract_expense + Number(row.contract_expense || 0),
      received: total.received + Number(row.received || 0),
      paid: total.paid + Number(row.paid || 0),
      receivable: total.receivable + Number(row.receivable || 0),
      payable: total.payable + Number(row.payable || 0),
      gross_profit: total.gross_profit + Number(row.gross_profit || 0),
    }),
    {
      contract_income: 0,
      contract_expense: 0,
      received: 0,
      paid: 0,
      receivable: 0,
      payable: 0,
      gross_profit: 0,
    },
  );
});
const boardMarginRate = computed(() =>
  boardTotals.value.received > 0
    ? `${((boardTotals.value.gross_profit / boardTotals.value.received) * 100).toFixed(1)}%`
    : "—",
);
const boardExportUrl = () => {
  const params = new URLSearchParams({ data_scope: boardDataScope.value });
  if (boardFilterProject.value) params.set("project_id", String(boardFilterProject.value));
  if (boardFilterType.value) params.set("project_type", boardFilterType.value);
  if (boardFilterStatus.value) params.set("status", boardFilterStatus.value);
  if (boardFilterDepartment.value) params.set("department_id", String(boardFilterDepartment.value));
  if (boardFilterOwner.value) params.set("owner_user_id", String(boardFilterOwner.value));
  if (boardFilterCustomer.value) params.set("customer_id", String(boardFilterCustomer.value));
  return `/api/v1/reports/projects/export?${params.toString()}`;
};
const exportProjectBoard = async () => {
  try {
    const headers = new Headers();
    if (authMode.value === "mock")
      headers.set("X-Demo-User-Id", String(activeUserId.value));
    const response = await fetch(boardExportUrl(), {
      headers,
      credentials: "same-origin",
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `导出失败（${response.status}）`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = /filename="?([^";]+)"?/.exec(disposition);
    const filename = match?.[1] || `xinye-project-board-${new Date().toISOString().slice(0, 10)}.csv`;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    successMessage.value = "项目看板明细已导出";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "项目看板导出失败";
  }
};
const renderBoardCharts = async () => {
  await nextTick();
  disposeCharts();
  if (page.value !== "projectBoard") return;
  const chartText = "#344054";
  const chartMuted = "#667085";
  const grid = { left: 12, right: 18, top: 24, bottom: 30, containLabel: true };
  const makeChart = (element: HTMLElement | null, option: EChartsOption) => {
    if (!element) return;
    element.innerHTML = "";
    const chart = init(element);
    chart.setOption(option);
    chartInstances.push(chart);
  };
  const rows = projectBoardRows.value.slice(0, 10).reverse();
  makeChart(boardChartEl.value, {
    color: ["#0f766e", "#d97706"],
    tooltip: { trigger: "axis", valueFormatter: (value: number) => moneyText(value) },
    legend: { data: ["已收", "已付"], bottom: 0, textStyle: { color: chartMuted } },
    grid,
    xAxis: { type: "value", axisLabel: { color: chartMuted }, splitLine: { lineStyle: { color: "#e4e7ec" } } },
    yAxis: { type: "category", data: rows.map((row) => row.name), axisLabel: { color: chartText, width: 140, overflow: "truncate" } },
    series: [
      { name: "已收", type: "bar", data: rows.map((row) => row.received), barMaxWidth: 14 },
      { name: "已付", type: "bar", data: rows.map((row) => row.paid), barMaxWidth: 14 },
    ],
  });
  const profitRows = projectBoardRows.value
    .slice()
    .sort((a, b) => b.gross_profit - a.gross_profit)
    .slice(0, 8)
    .reverse();
  makeChart(boardProfitChartEl.value, {
    color: ["#15803d", "#b91c1c"],
    tooltip: { trigger: "axis", valueFormatter: (value: number) => moneyText(value) },
    grid,
    xAxis: { type: "value", axisLabel: { color: chartMuted }, splitLine: { lineStyle: { color: "#e4e7ec" } } },
    yAxis: { type: "category", data: profitRows.map((row) => row.name), axisLabel: { color: chartText, width: 140, overflow: "truncate" } },
    series: [
      {
        name: "毛利",
        type: "bar",
        data: profitRows.map((row) => row.gross_profit),
        barMaxWidth: 20,
        itemStyle: {
          color: (params: { value?: number }) => Number(params.value) >= 0 ? "#15803d" : "#b91c1c",
        },
        label: { show: true, position: "right", color: chartText, formatter: (params: { value?: number }) => moneyText(params.value) },
      },
    ],
  });
};
const refreshProjectFinance = async () => {
  if (!selectedManagedProject.value) return;
  const projectId = selectedManagedProject.value.id;
  projectAnalysisLoading.value = true;
  projectAnalysisError.value = "";
  try {
    projectFinance.value = await api<ProjectFinance>(
      `/api/v1/projects/${projectId}/finance`,
    );
  } catch (error) {
    projectFinance.value = null;
  }
  try {
    projectAnalysis.value = await api<ProjectAnalysis>(
      `/api/v1/projects/${projectId}/analysis`,
    );
  } catch (error) {
    projectAnalysis.value = null;
    projectAnalysisError.value =
      error instanceof Error ? error.message : "项目经营分析加载失败";
  } finally {
    projectAnalysisLoading.value = false;
  }
  if (canManage("contracts") || canManage("receipts") || canManage("payments")) {
    try {
      projectContracts.value = await api<ProjectContract[]>(
        `/api/v1/contracts?project_id=${projectId}`,
      );
    } catch {
      projectContracts.value = [];
    }
  } else {
    projectContracts.value = [];
  }
};
const adminWorklogUrl = () => {
  const params = new URLSearchParams();
  params.set("page", String(adminPage.value));
  params.set("page_size", String(adminPageSize.value));
  if (adminPeriodStart.value)
    params.set("period_start", adminPeriodStart.value);
  if (adminPeriodEnd.value) params.set("period_end", adminPeriodEnd.value);
  if (adminDepartment.value)
    params.set("department_name", adminDepartment.value);
  if (adminUserId.value) params.set("user_id", String(adminUserId.value));
  if (adminProjectId.value) params.set("project_id", String(adminProjectId.value));
  if (adminStatus.value) params.set("status", adminStatus.value);
  return `/api/v1/admin/worklogs?${params.toString()}`;
};
const refreshAdminWorklogs = async () => {
  if (!canManage("worklogs")) return;
  adminLoading.value = true;
  try {
    const result = await api<AdminWorklogList>(adminWorklogUrl());
    adminWorklogs.value = result.items;
    adminWorklogTotal.value = result.total;
    adminPage.value = result.page;
    adminPageSize.value = result.page_size;
    adminPageCount.value = result.page_count;
    adminSummary.value = result.summary;
    adminDepartmentOptions.value = result.department_options;
  } finally {
    adminLoading.value = false;
  }
};
const queryAdminWorklogs = async () => {
  if (
    adminPeriodStart.value &&
    adminPeriodEnd.value &&
    adminPeriodStart.value > adminPeriodEnd.value
  ) {
    errorMessage.value = "工时开始日期不能晚于结束日期";
    return;
  }
  try {
    adminPage.value = 1;
    await refreshAdminWorklogs();
    errorMessage.value = "";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "工时管理查询失败";
  }
};
const changeAdminPage = async (nextPage: number) => {
  if (
    nextPage < 1 ||
    nextPage > adminPageCount.value ||
    nextPage === adminPage.value
  )
    return;
  adminPage.value = nextPage;
  await refreshAdminWorklogs();
};
const changeAdminPageSizeMode = async () => {
  if (adminPageSizeMode.value !== "custom")
    adminPageSize.value = Number(adminPageSizeMode.value);
  adminPageSize.value = Math.min(
    200,
    Math.max(1, Number(adminPageSize.value) || 20),
  );
  adminPage.value = 1;
  await queryAdminWorklogs();
};
const changeAdminCustomPageSize = async () => {
  adminPageSize.value = Math.min(
    200,
    Math.max(1, Number(adminPageSize.value) || 20),
  );
  adminPage.value = 1;
  await queryAdminWorklogs();
};
const personnelCostUrl = () => {
  const params = new URLSearchParams();
  params.set("page", String(personnelCostPage.value));
  params.set("page_size", String(personnelCostPageSize.value));
  if (personnelCostDepartment.value)
    params.set("department_name", personnelCostDepartment.value);
  if (personnelCostUserId.value)
    params.set("user_id", String(personnelCostUserId.value));
  params.set("configured_only", "true");
  return `/api/v1/admin/personnel-costs?${params.toString()}`;
};
const refreshPersonnelCosts = async () => {
  if (!canManage("personnel_costs")) return;
  personnelCostLoading.value = true;
  try {
    const result = await api<PersonnelCostList>(personnelCostUrl());
    personnelCosts.value = result.items;
    personnelCostTotal.value = result.total;
    personnelCostPage.value = result.page;
    personnelCostPageSize.value = result.page_size;
    personnelCostPageCount.value = result.page_count;
    personnelCostDepartmentOptions.value = result.department_options;
    personnelCostConfiguredUserIds.value = result.configured_user_ids;
    personnelCostConfiguredCount.value = result.summary.configured_count;
    personnelCostUnsetCount.value = result.summary.unset_count;
    personnelCostAverage.value = result.summary.average_daily_cost;
    personnelCostTotalDailyCost.value = result.summary.total_daily_cost;
  } finally {
    personnelCostLoading.value = false;
  }
};
const personnelCostUserOptions = computed(() => {
  if (!personnelCostDepartment.value) return demoUsers.value;
  const selectedPath = personnelCostDepartment.value;
  return demoUsers.value.filter((person) => {
    const path = person.department_path || person.department_name;
    return path === selectedPath || path.startsWith(`${selectedPath} / `);
  });
});
const personnelCostAvailableUsers = computed(() =>
  demoUsers.value.filter(
    (person) => !personnelCostConfiguredUserIds.value.includes(person.id),
  ),
);
watch(personnelCostDepartment, () => {
  if (
    personnelCostUserId.value &&
    !personnelCostUserOptions.value.some(
      (person) => person.id === personnelCostUserId.value,
    )
  )
    personnelCostUserId.value = 0;
});
const queryPersonnelCosts = async () => {
  personnelCostPage.value = 1;
  try {
    await refreshPersonnelCosts();
    errorMessage.value = "";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "人员成本查询失败";
  }
};
const changePersonnelCostPage = async (nextPage: number) => {
  if (
    nextPage < 1 ||
    nextPage > personnelCostPageCount.value ||
    nextPage === personnelCostPage.value
  )
    return;
  personnelCostPage.value = nextPage;
  try {
    await refreshPersonnelCosts();
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "人员成本查询失败";
  }
};
const changePersonnelCostPageSizeMode = async () => {
  if (personnelCostPageSizeMode.value !== "custom")
    personnelCostPageSize.value = Number(personnelCostPageSizeMode.value);
  personnelCostPageSize.value = Math.min(
    200,
    Math.max(1, Number(personnelCostPageSize.value) || 20),
  );
  personnelCostPage.value = 1;
  await queryPersonnelCosts();
};
const changePersonnelCostCustomPageSize = async () => {
  personnelCostPageSize.value = Math.min(
    200,
    Math.max(1, Number(personnelCostPageSize.value) || 20),
  );
  personnelCostPage.value = 1;
  await queryPersonnelCosts();
};
const savePersonnelCost = async (person: PersonnelCost) => {
  personnelCostSavingId.value = person.id;
  try {
    const result = await api<PersonnelCost>(
      `/api/v1/admin/personnel-costs/${person.id}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          daily_cost:
            person.daily_cost === null ||
            person.daily_cost === undefined ||
            Number.isNaN(Number(person.daily_cost))
              ? null
              : Number(person.daily_cost),
        }),
      },
    );
    Object.assign(person, result);
    successMessage.value = `${person.name} 的单天成本已保存`;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "人员成本保存失败";
  } finally {
    personnelCostSavingId.value = null;
  }
};
const resetPersonnelCostForm = () => {
  personnelCostFormOpen.value = false;
  personnelCostForm.user_id = personnelCostAvailableUsers.value[0]?.id || 0;
  personnelCostForm.daily_cost = null;
};
const openPersonnelCostForm = () => {
  if (!personnelCostAvailableUsers.value.length) {
    errorMessage.value = "所有组织人员都已加入成本管理";
    return;
  }
  personnelCostForm.user_id = personnelCostAvailableUsers.value[0].id;
  personnelCostForm.daily_cost = null;
  personnelCostFormOpen.value = true;
};
const saveNewPersonnelCost = async () => {
  const person = personnelCostAvailableUsers.value.find(
    (item) => item.id === personnelCostForm.user_id,
  );
  const dailyCost = Number(personnelCostForm.daily_cost);
  if (!person) {
    errorMessage.value = "请选择要加入成本管理的组织人员";
    return;
  }
  if (!Number.isFinite(dailyCost) || dailyCost < 0) {
    errorMessage.value = "请输入有效的单天成本";
    return;
  }
  personnelCostSavingId.value = person.id;
  try {
    await api<PersonnelCost>(`/api/v1/admin/personnel-costs/${person.id}`, {
      method: "PATCH",
      body: JSON.stringify({ daily_cost: dailyCost }),
    });
    resetPersonnelCostForm();
    await refreshPersonnelCosts();
    successMessage.value = `${person.name} 已加入成本管理`;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "人员成本保存失败";
  } finally {
    personnelCostSavingId.value = null;
  }
};
const adminPermissionUrl = () => {
  const params = new URLSearchParams();
  if (adminPermissionKeyword.value.trim())
    params.set("keyword", adminPermissionKeyword.value.trim());
  const query = params.toString();
  return `/api/v1/admin/permissions${query ? `?${query}` : ""}`;
};
const refreshAdminPermissions = async () => {
  if (!canManage("admins")) return;
  adminPermissionLoading.value = true;
  try {
    const result = await api<AdminPermissionList>(adminPermissionUrl());
    adminPermissions.value = result.items;
  } finally {
    adminPermissionLoading.value = false;
  }
};
const refreshAdminConfiguration = async () => {
  if (!canManage("configuration")) return;
  configurationLoading.value = true;
  try {
    const result = await api<ConfigCatalog>("/api/v1/admin/config/options");
    adminConfigOptions.value = result.options;
  } finally {
    configurationLoading.value = false;
  }
};
const configCategoryLabel = (category: string) =>
  ({
    project_type: "项目类型",
    project_stage: "项目阶段",
    work_type: "工时类型",
    work_status: "工作状态",
    project_status: "项目状态",
  })[category] || category;
const activeConfigOptions = (category: string) =>
  configOptions.value[category] || [];
const visibleConfigOptions = computed(
  () => adminConfigOptions.value[configurationCategory.value] || [],
);
const configOptionErrorMessage = (error: unknown) =>
  (
    ({
      CONFIG_OPTION_EXISTS: "该分类下的选项值已经存在",
      CONFIG_OPTION_IN_USE: "该选项已被业务数据使用，不能停用或删除",
      BUILTIN_CONFIG_OPTION_DISABLE_ONLY: "系统默认选项不能删除，只能停用",
      INVALID_CONFIG_CATEGORY: "配置分类无效",
    }) as Record<string, string>
  )[error instanceof Error ? error.message : ""] || "配置项保存失败";
const resetConfigurationForm = () => {
  configurationFormOpen.value = false;
  configurationEditingId.value = null;
  Object.assign(configurationForm, {
    category: configurationCategory.value,
    value: "",
    label: "",
    sort_order:
      (adminConfigOptions.value[configurationCategory.value]?.length || 0) + 1,
    is_active: true,
  });
};
const openConfigurationForm = () => {
  resetConfigurationForm();
  configurationForm.category = configurationCategory.value;
  configurationFormOpen.value = true;
};
const editConfigurationOption = (option: ConfigOption) => {
  configurationEditingId.value = option.id;
  Object.assign(configurationForm, {
    category: option.category,
    value: option.value,
    label: option.label,
    sort_order: option.sort_order,
    is_active: option.is_active,
  });
  configurationFormOpen.value = true;
};
const saveConfigurationOption = async () => {
  const label = configurationForm.label.trim();
  const value = configurationForm.value.trim();
  if (!label || (!configurationEditingId.value && !value)) {
    errorMessage.value = "请填写选项值和显示名称";
    return;
  }
  try {
    const wasEditing = Boolean(configurationEditingId.value);
    if (configurationEditingId.value)
      await api<ConfigOption>(
        `/api/v1/admin/config/options/${configurationEditingId.value}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            label,
            sort_order: Number(configurationForm.sort_order) || 0,
            is_active: configurationForm.is_active,
          }),
        },
      );
    else
      await api<ConfigOption>("/api/v1/admin/config/options", {
        method: "POST",
        body: JSON.stringify({
          category: configurationForm.category,
          value,
          label,
          sort_order: Number(configurationForm.sort_order) || 0,
          is_active: configurationForm.is_active,
        }),
      });
    resetConfigurationForm();
    await Promise.all([refreshAdminConfiguration(), refresh()]);
    successMessage.value = wasEditing ? "配置项已更新" : "配置项已创建";
  } catch (error) {
    errorMessage.value = configOptionErrorMessage(error);
  }
};
const deleteConfigurationOption = async (option: ConfigOption) => {
  if (option.is_builtin || !window.confirm(`确定删除“${option.label}”吗？`))
    return;
  try {
    await api(`/api/v1/admin/config/options/${option.id}`, {
      method: "DELETE",
    });
    await refreshAdminConfiguration();
    await refresh();
    successMessage.value = "配置项已删除";
  } catch (error) {
    errorMessage.value = configOptionErrorMessage(error);
  }
};
const adminPermissionAvailableUsers = computed(() =>
  demoUsers.value.filter(
    (person) =>
      !adminPermissions.value.some((item) => item.user_id === person.id),
  ),
);
const resetAdminPermissionForm = () => {
  adminPermissionFormOpen.value = false;
  Object.assign(adminPermissionForm, {
    user_id: adminPermissionAvailableUsers.value[0]?.id || 0,
    can_manage_projects: false,
    can_manage_contracts: false,
    can_manage_receipts: false,
    can_manage_payments: false,
    can_view_project_board: false,
    can_manage_counterparties: false,
    can_approve_cash: false,
    can_manage_worklogs: false,
    can_manage_personnel_costs: false,
    can_manage_integrations: false,
    can_manage_admins: false,
    can_manage_configuration: false,
    project_data_scope: "OWNED",
    scope_department_id: null,
    is_active: true,
  });
};
const openAdminPermissionForm = () => {
  resetAdminPermissionForm();
  adminPermissionFormOpen.value = true;
};
const saveNewAdminPermission = async () => {
  if (!adminPermissionForm.user_id) {
    errorMessage.value = "请选择要加入的组织人员";
    return;
  }
  if (
    !permissionLabels.some(
      (permission) => adminPermissionForm[permission.field],
    )
  ) {
    errorMessage.value = "至少选择一个可见管理菜单";
    return;
  }
  if (
    adminPermissionForm.project_data_scope === "DEPARTMENT" &&
    !adminPermissionForm.scope_department_id
  ) {
    errorMessage.value = "请选择项目数据权限对应的部门";
    return;
  }
  try {
    await api<AdminPermission>(
      `/api/v1/admin/permissions/${adminPermissionForm.user_id}`,
      { method: "PATCH", body: JSON.stringify(adminPermissionForm) },
    );
    const selected = demoUsers.value.find(
      (person) => person.id === adminPermissionForm.user_id,
    );
    resetAdminPermissionForm();
    await refreshAdminPermissions();
    successMessage.value = `${selected?.name || "管理员"} 已加入管理权限`;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "管理员权限保存失败";
  }
};
const queryAdminPermissions = async () => {
  try {
    await refreshAdminPermissions();
    errorMessage.value = "";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "管理员列表查询失败";
  }
};
const saveAdminPermission = async (item: AdminPermission) => {
  if (item.is_system_admin) return;
  if (item.project_data_scope === "DEPARTMENT" && !item.scope_department_id) {
    errorMessage.value = "请选择项目数据权限对应的部门";
    return;
  }
  adminPermissionSavingId.value = item.user_id;
  try {
    const payload = {
      can_manage_projects: item.can_manage_projects,
      can_manage_contracts: item.can_manage_contracts,
      can_manage_receipts: item.can_manage_receipts,
      can_manage_payments: item.can_manage_payments,
      can_view_project_board: item.can_view_project_board,
      can_manage_counterparties: item.can_manage_counterparties,
      can_approve_cash: item.can_approve_cash,
      can_manage_worklogs: item.can_manage_worklogs,
      can_manage_personnel_costs: item.can_manage_personnel_costs,
      can_manage_integrations: item.can_manage_integrations,
      can_manage_admins: item.can_manage_admins,
      can_manage_configuration: item.can_manage_configuration,
      project_data_scope: item.project_data_scope,
      scope_department_id:
        item.project_data_scope === "DEPARTMENT"
          ? item.scope_department_id
          : null,
      is_active: item.is_active,
    };
    const result = await api<AdminPermission>(
      `/api/v1/admin/permissions/${item.user_id}`,
      { method: "PATCH", body: JSON.stringify(payload) },
    );
    Object.assign(item, result);
    await refreshAdminPermissions();
    successMessage.value = `${item.user_name} 的管理权限已保存`;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "管理员权限保存失败";
  } finally {
    adminPermissionSavingId.value = null;
  }
};
const clearAdminPermission = async (item: AdminPermission) => {
  if (
    item.is_system_admin ||
    !window.confirm(`确定清除 ${item.user_name} 的全部管理权限吗？`)
  )
    return;
  adminPermissionSavingId.value = item.user_id;
  try {
    await api(`/api/v1/admin/permissions/${item.user_id}`, {
      method: "DELETE",
    });
    item.can_manage_projects = false;
    item.can_manage_worklogs = false;
    item.can_manage_personnel_costs = false;
    item.can_manage_integrations = false;
    item.can_manage_admins = false;
    item.is_active = false;
    await refreshAdminPermissions();
    successMessage.value = `${item.user_name} 的管理权限已清除`;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "管理员权限清除失败";
  } finally {
    adminPermissionSavingId.value = null;
  }
};
const validateWorklogDateRange = (startDate: string, endDate: string) => {
  if (!startDate || !endDate) return "请选择开始日期和结束日期";
  if (startDate > endDate) return "工时开始日期不能晚于结束日期";
  if (startDate.slice(0, 7) !== endDate.slice(0, 7))
    return "工时开始日期和结束日期不能跨月";
  return "";
};
const worklogErrorMessage = (error: unknown, fallback: string) => {
  const raw = error instanceof Error ? error.message : "";
  return (
    (
      {
        DATE_RANGE_INVALID: "工时开始日期不能晚于结束日期",
        DATE_RANGE_CROSSES_MONTH: "工时开始日期和结束日期不能跨月",
        WORKLOG_DATE_OVERLAP:
          "该人员已有日期重叠的工时，请调整开始日期或结束日期",
      } as Record<string, string>
    )[raw] ||
    raw ||
    fallback
  );
};
const resetAdminWorklogForm = () => {
  adminEditingId.value = null;
  adminWorklogFormOpen.value = false;
  Object.assign(adminForm, {
    project_id: 0,
    project_type:
      activeConfigOptions("project_type")[0]?.value || "RND_PROJECT",
    stage: activeConfigOptions("project_stage")[0]?.value || "开发",
    work_type: activeConfigOptions("work_type")[0]?.value || "PROJECT",
    work_status: activeConfigOptions("work_status")[0]?.value || "LOCAL",
    start_date: "",
    end_date: "",
    quantity: 1,
    unit: "DAY",
    description: "",
  });
};
const openAdminWorklogEditor = (item: AdminWorklog) => {
  adminEditingId.value = item.id;
  Object.assign(adminForm, {
    project_id: item.project_id,
    project_type:
      projects.value.find((project) => project.id === item.project_id)
        ?.project_type ||
      activeConfigOptions("project_type")[0]?.value ||
      "RND_PROJECT",
    stage: item.stage,
    work_type: item.work_type,
    work_status: item.work_status,
    start_date: item.start_date,
    end_date: item.end_date,
    quantity: Number(item.quantity),
    unit: "DAY",
    description: item.description,
  });
  adminWorklogFormOpen.value = true;
};
const saveAdminWorklog = async () => {
  if (!adminEditingId.value) return;
  const dateError = validateWorklogDateRange(
    adminForm.start_date,
    adminForm.end_date,
  );
  if (dateError) {
    errorMessage.value = dateError;
    return;
  }
  try {
    await api<AdminWorklog>(`/api/v1/admin/worklogs/${adminEditingId.value}`, {
      method: "PATCH",
      body: JSON.stringify(adminForm),
    });
    resetAdminWorklogForm();
    await refreshAdminWorklogs();
    successMessage.value = "工时已更新，审批状态保持不变";
  } catch (error) {
    errorMessage.value = worklogErrorMessage(error, "工时修改失败");
  }
};
const deleteAdminWorklog = async (item: AdminWorklog) => {
  if (
    !window.confirm(
      `确定删除 ${item.user_name_snapshot} 的这条工时吗？删除后不可恢复。`,
    )
  )
    return;
  try {
    await api(`/api/v1/admin/worklogs/${item.id}`, { method: "DELETE" });
    await refreshAdminWorklogs();
    successMessage.value = "工时已删除，关联审批任务已同步清理";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "工时删除失败";
  }
};
const filteredWorklogs = computed(() =>
  selectedStatus.value
    ? worklogs.value.filter((item) => item.status === selectedStatus.value)
    : worklogs.value,
);
const approvalItems = computed(() =>
  approvalTab.value === "pending"
    ? pendingApprovals.value
    : processedApprovals.value,
);
const fillableProjects = computed(() =>
  projects.value.filter(
    (item) =>
      item.status === "ACTIVE" &&
      item.allow_worklog &&
      (!form.project_type || item.project_type === form.project_type),
  ),
);
const filteredProjects = computed(() => {
  const query = projectQuery.value.trim().toLowerCase();
  if (!query) return fillableProjects.value;
  return fillableProjects.value.filter(
    (item) =>
      item.id === Number(form.project_id) ||
      item.name.toLowerCase().includes(query) ||
      item.code.toLowerCase().includes(query),
  );
});
const adminFilteredProjects = computed(() =>
  projects.value.filter(
    (project) =>
      project.status !== "DELETED" &&
      (!adminForm.project_type ||
        project.project_type === adminForm.project_type),
  ),
);
const projectDepartmentOptions = computed(() =>
  departments.value
    .filter((item) => item.is_active)
    .sort((left, right) =>
      (left.path || left.name).localeCompare(right.path || right.name, "zh-CN"),
    ),
);
const projectOwnerOptions = computed(() =>
  demoUsers.value
    .filter((person) =>
      projects.value.some((project) => project.owner_user_id === person.id),
    )
    .sort((left, right) => left.name.localeCompare(right.name, "zh-CN")),
);
const projectDepartmentTree = computed<OrgDepartmentNode[]>(() => {
  const options = projectDepartmentOptions.value;
  const ids = new Set(options.map((item) => item.id));
  const children = new Map<number | null, OrgDepartment[]>();
  options.forEach((item) => {
    const parentId =
      item.parent_id && ids.has(item.parent_id) ? item.parent_id : null;
    const items = children.get(parentId) || [];
    items.push(item);
    children.set(parentId, items);
  });
  const rows: OrgDepartmentNode[] = [];
  const walk = (parentId: number | null, depth: number) => {
    const items = (children.get(parentId) || [])
      .slice()
      .sort((left, right) => left.name.localeCompare(right.name, "zh-CN"));
    items.forEach((item) => {
      const hasChildren = (children.get(item.id) || []).length > 0;
      rows.push({ department: item, depth, hasChildren });
      if (hasChildren && projectDepartmentExpanded.value.has(item.id))
        walk(item.id, depth + 1);
    });
  };
  walk(null, 0);
  return rows;
});
const selectedProjectDepartmentLabel = computed(() => {
  if (!projectFilterDepartment.value) return "全部部门";
  const department = projectDepartmentOptions.value.find(
    (item) => item.id === projectFilterDepartment.value,
  );
  return department?.path || department?.name || "全部部门";
});
const projectDepartmentScope = (departmentId: number | null) => {
  if (!projectFilterDepartment.value) return true;
  if (!departmentId) return false;
  const scope = new Set<number>([projectFilterDepartment.value]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const department of departments.value) {
      if (
        department.parent_id &&
        scope.has(department.parent_id) &&
        !scope.has(department.id)
      ) {
        scope.add(department.id);
        changed = true;
      }
    }
  }
  return scope.has(departmentId);
};
const projectManagementFilteredProjects = computed(() => {
  return managedProjects.value;
});
const projectPageCount = computed(() =>
  Math.max(1, Math.ceil(projectListTotal.value / projectPageSize.value)),
);
const projectManagementPagedProjects = computed(() => managedProjects.value);
const projectListUrl = () => {
  const params = new URLSearchParams({
    page: String(projectPage.value),
    page_size: String(projectPageSize.value),
    data_scope: projectDataScope.value,
  });
  if (projectFilterType.value)
    params.set("project_type", projectFilterType.value);
  if (projectFilterStatus.value)
    params.set("status", projectFilterStatus.value);
  if (projectFilterDepartment.value)
    params.set("department_id", String(projectFilterDepartment.value));
  if (projectFilterOwner.value)
    params.set("owner_user_id", String(projectFilterOwner.value));
  if (projectFilterCustomer.value)
    params.set("customer_id", String(projectFilterCustomer.value));
  if (projectFilterKeyword.value.trim())
    params.set("keyword", projectFilterKeyword.value.trim());
  return `/api/v1/projects/page?${params.toString()}`;
};
const refreshProjectPage = async () => {
  projectListLoading.value = true;
  try {
    const result = await api<ProjectList>(projectListUrl());
    managedProjects.value = result.items;
    projectListTotal.value = result.total;
    if (projectPage.value > result.page_count)
      projectPage.value = result.page_count;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "项目列表加载失败";
  } finally {
    projectListLoading.value = false;
  }
};
const queryProjects = () => {
  projectPage.value = 1;
  void refreshProjectPage();
};
watch(
  [
    projectFilterType,
    projectFilterStatus,
    projectFilterDepartment,
    projectFilterOwner,
    projectFilterCustomer,
    projectFilterKeyword,
    projectDataScope,
  ],
  () => {
    projectPage.value = 1;
  },
);
watch(projectPageCount, (pageCount) => {
  if (projectPage.value > pageCount) projectPage.value = pageCount;
});
const changeProjectPage = (nextPage: number) => {
  if (
    nextPage < 1 ||
    nextPage > projectPageCount.value ||
    nextPage === projectPage.value
  )
    return;
  projectPage.value = nextPage;
  void refreshProjectPage();
};
const changeProjectPageSizeMode = () => {
  if (projectPageSizeMode.value !== "custom")
    projectPageSize.value = Number(projectPageSizeMode.value);
  projectPageSize.value = Math.min(
    200,
    Math.max(1, Number(projectPageSize.value) || 20),
  );
  projectPage.value = 1;
  void refreshProjectPage();
};
const changeProjectCustomPageSize = () => {
  projectPageSize.value = Math.min(
    200,
    Math.max(1, Number(projectPageSize.value) || 20),
  );
  projectPage.value = 1;
  void refreshProjectPage();
};
const toggleProjectDepartmentPicker = () => {
  projectDepartmentPickerOpen.value = !projectDepartmentPickerOpen.value;
  if (
    projectDepartmentPickerOpen.value &&
    !projectDepartmentExpanded.value.size
  ) {
    const rootIds = projectDepartmentOptions.value
      .filter(
        (item) =>
          !item.parent_id ||
          !projectDepartmentOptions.value.some(
            (parent) => parent.id === item.parent_id,
          ),
      )
      .map((item) => item.id);
    projectDepartmentExpanded.value = new Set(rootIds);
  }
};
const toggleProjectDepartmentNode = (departmentId: number) => {
  const next = new Set(projectDepartmentExpanded.value);
  if (next.has(departmentId)) next.delete(departmentId);
  else next.add(departmentId);
  projectDepartmentExpanded.value = next;
};
const selectProjectDepartment = (departmentId: number) => {
  projectFilterDepartment.value = departmentId;
  projectDepartmentPickerOpen.value = false;
};
const resetProjectFilters = () => {
  projectFilterType.value = "";
  projectFilterStatus.value = "";
  projectFilterDepartment.value = 0;
  projectFilterOwner.value = 0;
  projectFilterCustomer.value = 0;
  projectFilterKeyword.value = "";
  projectDepartmentPickerOpen.value = false;
  projectPage.value = 1;
  void refreshProjectPage();
};
const draftCount = computed(
  () =>
    worklogs.value.filter((item) => ["DRAFT", "REJECTED"].includes(item.status))
      .length,
);
const approvedSummary = computed(
  () =>
    `${worklogs.value
      .filter(
        (item) =>
          ["APPROVED", "LOCKED"].includes(item.status) && item.unit === "DAY",
      )
      .reduce((total, item) => total + Number(item.quantity), 0)
      .toFixed(1)} 天`,
);
const unitLabel = (_unit: string) => "天";
const formatProjectDays = (value: number | null | undefined) =>
  Number(value || 0).toFixed(1);
const projectRemainingDays = (project: Project) =>
  Number(project.budget_days || 0) - Number(project.actual_days || 0);
const projectExecutionLabel = (status: string) =>
  ({
    NOT_STARTED: "未开始",
    IN_PROGRESS: "正常执行",
    NEAR_BUDGET: "接近预算",
    OVER_BUDGET: "已超预算",
  })[status] || status;
const projectExecutionClass = (status: string) =>
  ({
    NOT_STARTED: "neutral",
    IN_PROGRESS: "teal",
    NEAR_BUDGET: "warning",
    OVER_BUDGET: "danger",
  })[status] || "neutral";
const isSystemAdmin = computed(
  () => user.value.roles?.includes("SYSTEM_ADMIN") === true,
);
const canManage = (permission: ManagementPermission) =>
  isSystemAdmin.value ||
  user.value.management_permissions?.includes(permission) === true;
const canManageAny = computed(
  () =>
    isSystemAdmin.value || (user.value.management_permissions?.length || 0) > 0,
);
const managementHome = computed<Page>(() => {
  if (canManage("projects")) return "projects";
  if (canManage("contracts")) return "projectContracts";
  if (canManage("receipts")) return "projectReceipts";
  if (canManage("payments")) return "projectPayments";
  if (canManage("project_board")) return "projectBoard";
  if (canManage("counterparties")) return "customers";
  if (canManage("worklogs")) return "adminWorklogs";
  if (canManage("personnel_costs")) return "personnelCosts";
  if (canManage("integrations")) return "integrations";
  if (canManage("configuration")) return "configuration";
  return "adminPermissions";
});
const mobileManagementItems = computed(() =>
  [
    { page: "adminWorklogs", permission: "worklogs" as ManagementPermission, label: "工时台账", glyph: "账" },
    { page: "projects", permission: "projects" as ManagementPermission, label: "项目管理", glyph: "▣" },
    { page: "projectContracts", permission: "contracts" as ManagementPermission, label: "项目合同", glyph: "合" },
    { page: "projectReceipts", permission: "receipts" as ManagementPermission, label: "项目收款", glyph: "收" },
    { page: "projectPayments", permission: "payments" as ManagementPermission, label: "项目付款", glyph: "付" },
    { page: "projectBoard", permission: "project_board" as ManagementPermission, label: "项目看板", glyph: "析" },
    { page: "customers", permission: "counterparties" as ManagementPermission, label: "客户管理", glyph: "客" },
    { page: "suppliers", permission: "counterparties" as ManagementPermission, label: "供应商管理", glyph: "供" },
    { page: "personnelCosts", permission: "personnel_costs" as ManagementPermission, label: "人员成本", glyph: "￥" },
    { page: "integrations", permission: "integrations" as ManagementPermission, label: "集成与通知", glyph: "↻" },
    { page: "adminPermissions", permission: "admins" as ManagementPermission, label: "管理员管理", glyph: "♙" },
    { page: "configuration", permission: "configuration" as ManagementPermission, label: "基础配置", glyph: "⚙" },
  ].filter((item) => canManage(item.permission)),
);
const ownedProjectRows = computed(() => workbenchOverview.value?.owned_projects || []);
const workbenchMetric = (key: string) =>
  Number(workbenchOverview.value?.metrics?.[key] || 0);
const workbenchReminderLabel = (kind: string) =>
  ({
    RECEIVABLE: "应收提醒",
    PAYABLE: "应付提醒",
    OVERDUE_RECEIVABLE: "应收逾期",
    OVERDUE_PAYABLE: "应付逾期",
  })[kind] || "提醒";
const auditActionLabel = (action: string) =>
  ({
    CREATE: "创建",
    UPDATE: "编辑",
    DELETE: "删除",
    SUBMIT: "提交",
    APPROVE: "审批通过",
    REJECT: "驳回",
    REVERSE: "冲销",
    UPDATE_APPROVAL_CHAIN: "调整审批链",
    UPDATE_DAILY_COST: "更新单天成本",
  })[action] || action;
const todayLabel = computed(() =>
  new Date().toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }),
);
const pageTitle = computed(
  () =>
    ({
      workbench: "工作台",
      worklogs: "我的工时",
      editor: "我的工时",
      detail: "我的工时",
      approvals: "工时审批",
      approvalDetail: "工时审批",
      receiptDetail: "项目收款",
      paymentDetail: "项目付款",
      reports: "工时看板",
      adminWorklogs: "工时台账",
      projects: "项目管理",
      projectDetail: "项目详情",
      projectContracts: "项目合同",
      projectReceipts: "项目收款",
      projectPayments: "项目付款",
      projectBoard: "项目看板",
      suppliers: "供应商管理",
      customers: "客户管理",
      personnelCosts: "人员成本",
      integrations: "集成与通知",
      adminPermissions: "管理员管理",
      configuration: "基础配置",
    })[page.value],
);
const reportTotalSummary = computed(() => {
  if (!report.value) return "0 天";
  return `${report.value.metrics.total_days || 0} 天`;
});
const reportBudgetSummary = computed(
  () => `${formatProjectDays(report.value?.metrics.budget_days)} 天`,
);
const reportBudgetCostSummary = computed(
  () =>
    `¥${Number(report.value?.metrics.budget_cost || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`,
);
const reportCostUsageSummary = computed(
  () => `${Number(report.value?.metrics.cost_usage_rate || 0).toFixed(1)}%`,
);
const reportCostSummary = computed(
  () =>
    `¥${Number(report.value?.metrics.actual_cost || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`,
);
const reportBudgetUsageSummary = computed(
  () => `${Number(report.value?.metrics.budget_usage_rate || 0).toFixed(1)}%`,
);
const statusLabel = (status: string) =>
  ({
    DRAFT: "草稿",
    PENDING: "审批中",
    PENDING_APPROVAL: "审批中",
    APPROVING: "审批中",
    APPROVED: "已通过",
    REJECTED: "已驳回",
    LOCKED: "已锁定",
  })[status] || status;
const statusClass = (status: string) =>
  ({
    DRAFT: "neutral",
    PENDING_APPROVAL: "warning",
    APPROVING: "warning",
    APPROVED: "success",
    REJECTED: "danger",
    LOCKED: "success",
  })[status] || "neutral";
const userName = (id: number | null) =>
  demoUsers.value.find((item) => item.id === id)?.name || "未知用户";
const selectedProject = computed(
  () =>
    projects.value.find((item) => item.id === Number(form.project_id)) || null,
);
const optionLabel = (category: string, value: string) =>
  activeConfigOptions(category).find((option) => option.value === value)
    ?.label || value;
const workTypeLabel = (value: string) => optionLabel("work_type", value);
const workStatusLabel = (value: string) => optionLabel("work_status", value);
const contractTypeLabel = (value: string) =>
  ({ INCOME: "收入合同", EXPENSE: "支出合同" })[value] || value;
const contractStatusLabel = (value: string) =>
  ({ ACTIVE: "执行中", COMPLETED: "已完成", TERMINATED: "已终止", DRAFT: "草稿" })[value] || value;
const contractStatusClass = (value: string) =>
  ({ ACTIVE: "success", COMPLETED: "info", TERMINATED: "neutral", DRAFT: "warning" })[value] || "neutral";
const cashStatusLabel = (value: string) =>
  ({
    DRAFT: "草稿",
    PENDING: "待出纳审批",
    APPROVED: "已确认",
    REJECTED: "已驳回",
    REVERSED: "已冲销",
  })[value] || value;
const cashStatusClass = (value: string) =>
  ({ PENDING: "warning", APPROVED: "success", REJECTED: "danger", REVERSED: "neutral" })[value] || "neutral";
const moneyText = (value: number | null | undefined) =>
  `¥${Number(value || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`;
const analysisStatusLabel = (status: string) =>
  ({
    DONE: "已完成",
    OVERDUE: "已逾期",
    UPCOMING: "即将到期",
    PARTIAL: "部分完成",
    PLANNED: "未到期",
    CANCELLED: "已取消",
  })[status] || status;
const analysisStatusClass = (status: string) =>
  ({
    DONE: "success",
    OVERDUE: "danger",
    UPCOMING: "warning",
    PARTIAL: "info",
    PLANNED: "neutral",
    CANCELLED: "neutral",
  })[status] || "neutral";
const analysisWarningClass = (level: string) =>
  ({ CRITICAL: "danger", WARNING: "warning", INFO: "info" })[level] || "info";
const analysisWarningLabel = (level: string) =>
  ({ CRITICAL: "严重", WARNING: "预警", INFO: "提示" })[level] || level;
const analysisCloseoutLabel = (status: string) =>
  ({ NORMAL: "资金计划正常", AT_RISK: "需要关注", OVERDUE: "结项已逾期", NO_DATE: "未设置结项日期" })[status] || status;
const analysisContracts = computed(() =>
  analysisSettlementTab.value === "income"
    ? projectAnalysis.value?.settlement.income_contracts || []
    : projectAnalysis.value?.settlement.expense_contracts || [],
);
const analysisTrendMax = computed(() =>
  Math.max(
    1,
    ...(projectAnalysis.value?.cost.monthly_trend || []).map(
      (item) => item.total_cost,
    ),
  ),
);
const analysisTrendHeight = (value: number) =>
  `${Math.max(4, Math.round((value / analysisTrendMax.value) * 100))}%`;
const analysisCostCompositionWidth = (value: number) => {
  const total = Number(projectAnalysis.value?.cost.total_cost || 0);
  return `${total > 0 ? Math.max(2, Math.round((value / total) * 100)) : 0}%`;
};
const isAnalysisStageExpanded = (stageId: number) =>
  expandedAnalysisStages.value.has(stageId);
const toggleAnalysisStage = (stageId: number) => {
  const next = new Set(expandedAnalysisStages.value);
  if (next.has(stageId)) next.delete(stageId);
  else next.add(stageId);
  expandedAnalysisStages.value = next;
};
const resetProjectAnalysisState = () => {
  analysisSettlementTab.value = "income";
  expandedAnalysisStages.value = new Set();
  projectAnalysis.value = null;
  projectAnalysisError.value = "";
};
const focusProjectAnalysisWarning = (
  warning: ProjectAnalysis["warnings"][number],
) => {
  if (warning.source_type === "PROJECT") {
    successMessage.value = "已定位项目风险，请处理项目预算或结项日期";
    return;
  }
  projectDetailTab.value = "finance";
  successMessage.value = "已切换到合同与资金，可查看关联明细";
};
const incomeContracts = computed(() =>
  page.value === "projectReceipts"
    ? incomeContractOptions.value
    : projectContracts.value.filter((item) => item.contract_type === "INCOME"),
);
const expenseContracts = computed(() =>
  page.value === "projectPayments"
    ? expenseContractOptions.value
    : projectContracts.value.filter((item) => item.contract_type === "EXPENSE"),
);
const contractById = (id: number) =>
  projectContracts.value.find((item) => item.id === id) || null;
const stageOptionsFor = (contractId: number) =>
  projectContractStages.value.filter((item) => item.contract_id === contractId);
const visibleReceipts = computed(() =>
  receiptTab.value === "pending"
    ? receipts.value.filter((item) => item.status === "PENDING")
    : receipts.value,
);
const visiblePayments = computed(() =>
  paymentTab.value === "pending"
    ? payments.value.filter((item) => item.status === "PENDING")
    : payments.value,
);
const receiptSelectedStage = computed(() =>
  projectContractStages.value.find((item) => item.id === receiptForm.stage_id) ||
  null,
);
const receiptStageRemaining = computed(() =>
  receiptSelectedStage.value?.remaining_amount ??
  receiptSelectedStage.value?.amount ??
  0,
);
const paymentSelectedStage = computed(() =>
  projectContractStages.value.find((item) => item.id === paymentForm.stage_id) ||
  null,
);
const paymentStageRemaining = computed(() =>
  paymentSelectedStage.value?.remaining_amount ??
  paymentSelectedStage.value?.amount ??
  0,
);
const projectDetailWorklogs = computed(() =>
  worklogs.value.filter(
    (item) => item.project_id === selectedManagedProject.value?.id,
  ),
);
const selectedProjectContracts = computed(() =>
  projectContracts.value.filter(
    (item) => item.project_id === selectedManagedProject.value?.id,
  ),
);
const selectedProjectIncomeContracts = computed(() =>
  selectedProjectContracts.value.filter((item) => item.contract_type === "INCOME"),
);
const selectedProjectExpenseContracts = computed(() =>
  selectedProjectContracts.value.filter((item) => item.contract_type === "EXPENSE"),
);
const visibleCounterparties = computed(() => {
  const items = page.value === "suppliers" ? suppliers.value : customers.value;
  const keyword = counterpartyKeyword.value.trim().toLowerCase();
  return items.filter((item) => {
    const matchesKeyword = !keyword || [item.name, item.short_name, item.code, item.unified_credit_code]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keyword));
    return matchesKeyword && (!counterpartyStatus.value || item.status === counterpartyStatus.value);
  });
});
const activeCounterpartyForm = computed(() =>
  page.value === "suppliers" ? supplierForm : customerForm,
);
const notificationStatusLabel = (value: string | undefined) =>
  ({ SENT: "发送成功", FAILED: "发送失败", PENDING: "发送中" })[value || ""] ||
  "未发送";
const notificationErrorLabel = (value: string | null | undefined) => {
  if (!value) return "飞书通知未生成，请联系系统管理员检查通知配置。";
  if (value.includes("230013"))
    return "当前飞书应用未对该审批人开放，请在飞书应用后台的“可用范围”中加入该用户后重新发送。";
  if (value.includes("230006"))
    return "飞书应用机器人能力未启用，请在飞书应用后台启用机器人后重新发送。";
  if (value.includes("OPEN_ID_MISSING"))
    return "审批人没有可用的飞书身份，请先同步组织架构后重新提交。";
  return value;
};
const reportBarMax = (key: string) =>
  Math.max(
    1,
    ...(report.value?.breakdowns[key] || []).map((item) => item.quantity),
  );
const formatDateTime = (value: string | null | undefined) => {
  if (!value) return "";
  const match = value.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return match ? `${match[1]} ${match[2]}` : value;
};
const reportTypeLabel = (value: string) =>
  ({
    PROJECT: "项目工时",
    MANAGEMENT: "管理工时",
    OTHER: "其它工时",
    LOCAL: "本地",
    BUSINESS_TRIP: "出差",
    REMOTE: "异地办公",
    LEAVE: "休假",
    APPROVED: "已通过",
    LOCKED: "已锁定",
  })[value] || value;
const notificationHealthLabel = (value: string) =>
  ({
    mock: "模拟通知",
    webhook: "群机器人 Webhook",
    "webhook-not-configured": "群机器人未配置",
    app: "飞书应用私聊",
    "app-not-configured": "飞书应用未配置",
  })[value] || value;
const directoryHealthLabel = (value: string) =>
  ({
    "mock-ok": "模拟组织架构",
    "app-configured": "飞书组织架构已配置",
    "app-not-configured": "飞书组织架构未配置",
  })[value] || value;
const integrationNotificationTypeLabel = (value: string) =>
  ({
    SETTLEMENT_APPROVED: "收付款审批结果",
    COST_BUDGET_NEAR: "成本预算预警",
    COST_BUDGET_OVER: "成本预算超支",
    DAYS_BUDGET_NEAR: "人天预算预警",
    DAYS_BUDGET_OVER: "人天预算超支",
    STAGE_UPCOMING: "合同阶段临期",
    STAGE_DUE: "合同阶段到期",
    STAGE_OVERDUE: "合同阶段逾期",
  })[value] || value;
const integrationNotificationStatusLabel = (value: string) =>
  ({ SENT: "发送成功", FAILED: "发送失败", PENDING: "发送中" })[value] || value;
const integrationNotificationStatusClass = (value: string) =>
  ({ SENT: "success", FAILED: "danger", PENDING: "warning" })[value] || "neutral";
const integrationNotificationRows = computed(() =>
  (integrationOverview.value?.notifications || []).filter((item) =>
    (!integrationNotificationType.value || item.notification_type === integrationNotificationType.value) &&
    (!integrationNotificationStatus.value || item.status === integrationNotificationStatus.value),
  ),
);
const integrationNotificationTypes = computed(() =>
  [...new Set((integrationOverview.value?.notifications || []).map((item) => item.notification_type))],
);
const refreshIntegrationOverview = async () => {
  if (!canManage("integrations")) return;
  integrationOverviewLoading.value = true;
  try {
    const result = await api<IntegrationOverview>("/api/v1/integrations/overview");
    integrationOverview.value = result;
    integrationHealth.value = result.health;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "集成数据加载失败";
  } finally {
    integrationOverviewLoading.value = false;
  }
};
const queryIntegrationOverview = () => {
  void refreshIntegrationOverview();
};
const retryIntegrationNotification = async (item: IntegrationNotification) => {
  if (item.status === "SENT") return;
  try {
    await api<IntegrationNotification>(
      `/api/v1/integrations/notifications/${item.id}/retry`,
      { method: "POST" },
    );
    await refreshIntegrationOverview();
    successMessage.value = "通知已重新发送";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "通知重试失败";
  }
};
const isSelfApprover = computed(
  () => selectedProject.value?.approver_user_id === activeUserId.value,
);
const actualApproverName = computed(() => {
  const project = selectedProject.value;
  if (!project) return "未配置";
  if (project.approver_user_id === activeUserId.value)
    return (
      project.leader_name ||
      (project.leader_user_id
        ? userName(project.leader_user_id)
        : "请先配置上级领导")
    );
  return project.approver_name || "未配置";
});

const openEditor = (item?: Worklog) => {
  editingId.value = item?.id || null;
  projectQuery.value = "";
  projectPickerOpen.value = false;
  if (item)
    Object.assign(form, {
      project_id: item.project_id,
      project_type:
        projects.value.find((project) => project.id === item.project_id)
          ?.project_type ||
        activeConfigOptions("project_type")[0]?.value ||
        "RND_PROJECT",
      stage: item.stage,
      work_type: item.work_type,
      work_status: item.work_status,
      start_date: item.start_date,
      end_date: item.end_date,
      quantity: Number(item.quantity),
      unit: "DAY",
      description: item.description,
    });
  else
    Object.assign(form, {
      project_id: 0,
      project_type: activeConfigOptions("project_type")[0]?.value || "",
      stage: activeConfigOptions("project_stage")[0]?.value || "开发",
      work_type: activeConfigOptions("work_type")[0]?.value || "PROJECT",
      work_status: activeConfigOptions("work_status")[0]?.value || "LOCAL",
      start_date: new Date().toISOString().slice(0, 10),
      end_date: new Date().toISOString().slice(0, 10),
      quantity: 1,
      unit: "DAY",
      description: "",
    });
  if (!item) form.project_id = fillableProjects.value[0]?.id || 0;
  go("editor");
};

const toggleProjectPicker = () => {
  projectPickerOpen.value = !projectPickerOpen.value;
  if (!projectPickerOpen.value) projectQuery.value = "";
};
const chooseProject = (project: Project) => {
  form.project_id = project.id;
  projectQuery.value = "";
  projectPickerOpen.value = false;
};

const saveWorklog = async (submit: boolean) => {
  const dateError = validateWorklogDateRange(form.start_date, form.end_date);
  if (dateError) {
    errorMessage.value = dateError;
    return;
  }
  try {
    let item: Worklog;
    if (editingId.value)
      item = await api<Worklog>(`/api/v1/worklogs/${editingId.value}`, {
        method: "PATCH",
        body: JSON.stringify(form),
      });
    else
      item = await api<Worklog>("/api/v1/worklogs", {
        method: "POST",
        body: JSON.stringify({ ...form, submit }),
      });
    if (submit && editingId.value) {
      const task = await api<ApprovalTask>(
        `/api/v1/worklogs/${item.id}/submit`,
        { method: "POST" },
      );
      selectedTask.value = task;
      await refresh();
      go("detail");
      successMessage.value =
        task.notification?.status === "SENT"
          ? "已提交，飞书通知已发送"
          : "已提交，但飞书通知未发送成功";
    } else if (submit) {
      selectedTask.value = await api<ApprovalTask>(
        `/api/v1/worklogs/${item.id}/approval`,
      );
      await refresh();
      go("detail");
      successMessage.value =
        selectedTask.value.notification?.status === "SENT"
          ? "已提交，飞书通知已发送"
          : "已提交，但飞书通知未发送成功";
    } else {
      await refresh();
      go("worklogs");
      successMessage.value = "草稿已保存";
    }
  } catch (error) {
    errorMessage.value = worklogErrorMessage(error, "保存失败");
  }
};

const openTask = async (task: ApprovalTask) => {
  try {
    selectedTask.value = await api<ApprovalTask>(
      `/api/v1/approvals/${task.id}`,
    );
    go("approvalDetail");
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "审批详情加载失败";
  }
};
const openWorklog = async (item: Worklog) => {
  try {
    selectedTask.value = await api<ApprovalTask>(
      `/api/v1/worklogs/${item.id}/approval`,
    );
    go("detail");
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "工时详情加载失败";
  }
};
const openDetail = openWorklog;
const processTask = async (action: "approve" | "reject") => {
  if (!selectedTask.value) return;
  if (action === "reject" && rejectionReason.value.trim().length < 2) {
    errorMessage.value = "驳回原因至少填写 2 个字";
    return;
  }
  try {
    selectedTask.value = await api<ApprovalTask>(
      `/api/v1/approvals/${selectedTask.value.id}/${action}`,
      {
        method: "POST",
        body: JSON.stringify(
          action === "approve"
            ? { version: selectedTask.value.version, comment: "" }
            : {
                version: selectedTask.value.version,
                reason: rejectionReason.value,
              },
        ),
      },
    );
    rejectionReason.value = "";
    successMessage.value =
      action === "approve" ? "审批已通过" : "已驳回，提交人可以修改后重新提交";
    await refresh();
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "审批操作失败";
  }
};
const remindTask = async () => {
  if (!selectedTask.value) return;
  try {
    const notification = await api<Notification>(
      `/api/v1/approvals/${selectedTask.value.id}/remind`,
      { method: "POST" },
    );
    selectedTask.value.notification = notification;
    successMessage.value =
      notification.status === "SENT" ? "提醒已发送" : "提醒发送失败";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "提醒失败";
  }
};
const saveApprover = async (project: Project) => {
  if (!project.approver_user_id || !project.leader_user_id) {
    errorMessage.value = "请同时配置审批人和上级领导";
    return;
  }
  try {
    const updated = await api<Project>(
      `/api/v1/projects/${project.id}/approver`,
      {
        method: "PATCH",
        body: JSON.stringify({
          approver_user_id: project.approver_user_id,
          leader_user_id: project.leader_user_id,
        }),
      },
    );
    Object.assign(project, updated);
    successMessage.value = "项目审批配置已更新";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "审批配置保存失败";
  }
};

const resetProjectForm = () => {
  editingProjectId.value = null;
  projectFormOpen.value = false;
  Object.assign(projectForm, {
    code: "",
    name: "",
    project_type:
      activeConfigOptions("project_type")[0]?.value || "RND_PROJECT",
    owner_user_id: 0,
    department_id: 0,
    approver_user_id: 0,
    leader_user_id: 0,
    customer_id: null,
    start_date: "",
    planned_end_date: "",
    description: "",
    budget_days: 0,
    budget_cost: 0,
    status: activeConfigOptions("project_status")[0]?.value || "ACTIVE",
    allow_worklog: true,
  });
};
const openProjectForm = () => {
  resetProjectForm();
  projectFormOpen.value = true;
};
const editProject = (project: Project) => {
  editingProjectId.value = project.id;
  projectFormOpen.value = true;
  Object.assign(projectForm, {
    code: project.code,
    name: project.name,
    project_type: project.project_type,
    owner_user_id: project.owner_user_id || 0,
    department_id: project.department_id || 0,
    approver_user_id: project.approver_user_id || 0,
    leader_user_id: project.leader_user_id || 0,
    customer_id: project.customer_id,
    start_date: project.start_date || "",
    planned_end_date: project.planned_end_date || "",
    description: project.description || "",
    budget_days: project.budget_days || 0,
    budget_cost: project.budget_cost || 0,
    status: project.status,
    allow_worklog: project.allow_worklog,
  });
  go("projects");
};
const openProjectDetail = async (project: Project) => {
  try {
    selectedManagedProject.value = await api<Project>(
      `/api/v1/projects/${project.id}`,
    );
    projectDetailTab.value = "overview";
    resetProjectAnalysisState();
    projectAuditLogs.value = [];
    go("projectDetail");
    void loadProjectAudit();
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "项目详情加载失败";
  }
};
const loadProjectAudit = async () => {
  if (!selectedManagedProject.value) return;
  try {
    projectAuditLogs.value = await api<AuditEntry[]>(
      `/api/v1/projects/${selectedManagedProject.value.id}/audit`,
    );
  } catch {
    projectAuditLogs.value = [];
  }
};
const saveProject = async () => {
  if (!canManage("projects")) {
    errorMessage.value = "你没有项目管理权限";
    return;
  }
  if (
    !projectForm.owner_user_id ||
    !projectForm.department_id ||
    !projectForm.approver_user_id ||
    !projectForm.leader_user_id
  ) {
    errorMessage.value =
      "项目部门、负责人、审批人和上级领导必须从组织架构中选择";
    return;
  }
  try {
    const wasEditing = Boolean(editingProjectId.value);
    const url = editingProjectId.value
      ? `/api/v1/projects/${editingProjectId.value}`
      : "/api/v1/projects";
    const payload = {
      ...projectForm,
      start_date: projectForm.start_date || null,
      planned_end_date: projectForm.planned_end_date || null,
    };
    await api<Project>(url, {
      method: editingProjectId.value ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    resetProjectForm();
    await refresh();
    await refreshProjectPage();
    successMessage.value = wasEditing ? "项目已更新" : "项目已创建";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "项目保存失败";
  }
};
const deleteProject = async (project: Project) => {
  if (!canManage("projects")) {
    errorMessage.value = "你没有项目管理权限";
    return;
  }
  if (!window.confirm(`确定删除项目“${project.name}”吗？历史工时会保留。`))
    return;
  try {
    await api(`/api/v1/projects/${project.id}`, { method: "DELETE" });
    await refresh();
    successMessage.value = "项目已删除，历史记录已保留";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "项目删除失败";
  }
};
const syncOrgUsers = async () => {
  if (!canManage("integrations")) {
    errorMessage.value = "你没有集成与通知权限";
    return;
  }
  try {
    const result = await api<{
      status: string;
      user_count: number;
      department_count: number;
    }>("/api/v1/org/sync", { method: "POST" });
    syncSummary.value =
      result.status === "MOCK"
        ? "当前为演示组织架构，已刷新人员和部门列表"
        : `最近同步完成：${result.user_count} 名用户、${result.department_count} 个部门`;
    await refresh();
    successMessage.value = syncSummary.value;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "组织架构同步失败";
  }
};

const initialize = async () => {
  authLoading.value = true;
  try {
    const response = await fetch("/api/v1/auth/config");
    const config = (await response.json()) as AuthConfig;
    authMode.value = config.mode;
    authAppId.value = config.auth_app_id || "";
    feishuLoginEnabled.value = config.feishu_login_enabled;
    authRequired.value = config.auth_required;
    const authError = new URLSearchParams(window.location.search).get(
      "auth_error",
    );
    if (authError) {
      errorMessage.value =
        (
          {
            AUTH_STATE_INVALID: "登录链接已失效，请重新登录",
            FEISHU_AUTH_CANCELLED: "已取消飞书授权",
            FEISHU_OAUTH_FAILED: "飞书登录失败，请稍后重试",
            FEISHU_USER_NOT_SYNCED: "当前飞书用户尚未同步到工时系统",
            FEISHU_USER_INACTIVE: "当前飞书用户已停用",
          } as Record<string, string>
        )[authError] || "飞书登录失败";
      window.history.replaceState({}, document.title, window.location.pathname);
      authRequired.value = true;
    }
    if (!authRequired.value) {
      await refresh();
      if (page.value === "projects") await refreshProjectPage();
      if (page.value === "projectContracts") await refreshContracts();
      if (page.value === "projectReceipts") await refreshReceipts();
      if (page.value === "projectPayments") await refreshPayments();
      if (page.value === "projectBoard") {
        await refreshProjectBoard();
        await nextTick();
        await renderBoardCharts();
      }
      if (page.value === "suppliers") await refreshSuppliers();
      if (page.value === "customers") await refreshCustomers();
    }
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "认证状态加载失败";
  } finally {
    authLoading.value = false;
  }
};

const closeProjectPicker = () => {
  projectPickerOpen.value = false;
  projectQuery.value = "";
};
onMounted(() => {
  window.addEventListener("resize", resizeCharts);
  document.addEventListener("click", closeProjectPicker);
  initialize();
  startStatusPolling();
});
</script>

<template>
  <div v-if="authLoading" class="auth-gate">
    <section class="auth-panel">
      <span class="brand-mark">综</span>
      <h1>综合项目管理系统</h1>
      <p>正在检查飞书登录状态…</p>
    </section>
  </div>
  <div v-else-if="authRequired" class="auth-gate">
    <section class="auth-panel">
      <span class="brand-mark">综</span>
      <h1>综合项目管理系统</h1>
      <p>{{ errorMessage || "请使用飞书账号登录后继续" }}</p>
      <button
        v-if="feishuLoginEnabled"
        class="primary auth-button"
        :disabled="loading"
        @click="loginWithFeishu"
      >
        {{ loading ? "正在打开飞书授权…" : "使用飞书登录" }}
      </button>
      <p v-else class="auth-helper">飞书登录尚未完成配置，请联系系统管理员。</p>
    </section>
  </div>
  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">综</span
        ><span class="brand-copy"
          ><strong>综合</strong><small>项目管理系统</small></span
        >
      </div>
      <div class="nav-label">工作台</div>
      <button
        class="nav-item"
        :class="{ active: page === 'workbench' }"
        @click="go('workbench')"
      >
        ⌂ <span>工作台</span>
      </button>
      <div class="nav-label">工时管理</div>
      <button
        class="nav-item"
        :class="{ active: ['worklogs', 'editor', 'detail'].includes(page) }"
        @click="go('worklogs')"
      >
        ▤ <span>我的工时</span>
      </button>
      <button
        class="nav-item"
        :class="{ active: ['approvals', 'approvalDetail'].includes(page) }"
        @click="go('approvals')"
      >
        ✓
        <span
          >工时审批
          <b v-if="pendingApprovals.length">{{
            pendingApprovals.length
          }}</b></span
        >
      </button>
      <button
        class="nav-item"
        :class="{ active: page === 'reports' }"
        @click="go('reports')"
      >
        ◫ <span>工时看板</span>
      </button>
      <button
        v-if="canManage('worklogs')"
        class="nav-item"
        :class="{ active: page === 'adminWorklogs' }"
        @click="go('adminWorklogs')"
      >
        账 <span>工时台账</span>
      </button>
      <template v-if="canManageAny">
        <div class="nav-label">项目管理</div>
        <button
          v-if="canManage('projects')"
          class="nav-item"
          :class="{ active: ['projects', 'projectDetail'].includes(page) }"
          @click="go('projects')"
        >
          ▣ <span>项目管理</span>
        </button>
        <button
          v-if="canManage('contracts')"
          class="nav-item"
          :class="{ active: page === 'projectContracts' }"
          @click="go('projectContracts')"
        >
          合 <span>项目合同</span>
        </button>
        <button
          v-if="canManage('receipts')"
          class="nav-item"
          :class="{ active: page === 'projectReceipts' }"
          @click="go('projectReceipts')"
        >
          收 <span>项目收款</span>
        </button>
        <button
          v-if="canManage('payments')"
          class="nav-item"
          :class="{ active: page === 'projectPayments' }"
          @click="go('projectPayments')"
        >
          付 <span>项目付款</span>
        </button>
        <button
          v-if="canManage('project_board')"
          class="nav-item"
          :class="{ active: page === 'projectBoard' }"
          @click="go('projectBoard')"
        >
          析 <span>项目看板</span>
        </button>
        <button
          v-if="canManage('counterparties')"
          class="nav-item"
          :class="{ active: page === 'suppliers' }"
          @click="go('suppliers')"
        >
          供 <span>供应商管理</span>
        </button>
        <button
          v-if="canManage('counterparties')"
          class="nav-item"
          :class="{ active: page === 'customers' }"
          @click="go('customers')"
        >
          客 <span>客户管理</span>
        </button>
        <div class="nav-label">系统管理</div>
        <button
          v-if="canManage('personnel_costs')"
          class="nav-item"
          :class="{ active: page === 'personnelCosts' }"
          @click="go('personnelCosts')"
        >
          ￥ <span>人员成本</span>
        </button>
        <button
          v-if="canManage('integrations')"
          class="nav-item"
          :class="{ active: page === 'integrations' }"
          @click="go('integrations')"
        >
          ↻ <span>集成与通知</span>
        </button>
        <button
          v-if="canManage('admins')"
          class="nav-item"
          :class="{ active: page === 'adminPermissions' }"
          @click="go('adminPermissions')"
        >
          ♙ <span>管理员管理</span>
        </button>
        <button
          v-if="canManage('configuration')"
          class="nav-item"
          :class="{ active: page === 'configuration' }"
          @click="go('configuration')"
        >
          ⚙ <span>基础配置</span>
        </button>
      </template>
    </aside>
    <main class="main">
      <header class="topbar">
        <div class="crumb">
          <span class="topbar-kicker">SINYE PROJECT MANAGE SYSTEM</span><span>工作空间</span
          ><span>/</span><strong>{{ pageTitle }}</strong>
        </div>
        <div class="user-chip">
          <span>{{ authMode === "app" ? "飞书用户" : "演示身份" }}</span
          ><select
            v-if="authMode === 'mock'"
            class="identity-select"
            v-model.number="activeUserId"
            @change="switchUser"
          >
            <option v-for="item in demoUsers" :key="item.id" :value="item.id">
              {{ item.name }}
            </option></select
          ><strong v-else>{{ user.name }}</strong
          ><i>{{ user.name.slice(0, 1) }}</i
          ><button
            v-if="authMode === 'app'"
            class="text-button"
            @click="logout"
          >
            退出
          </button>
        </div>
      </header>
      <div v-if="loading" class="loading-bar"></div>
      <div class="content">
        <div v-if="errorMessage" class="notice error">
          <strong>操作失败</strong><span>{{ errorMessage }}</span
          ><button class="text-button" @click="errorMessage = ''">关闭</button>
        </div>
        <div v-if="successMessage" class="notice success">
          <strong>已完成</strong><span>{{ successMessage }}</span
          ><a
            v-if="exportReadyUrl"
            class="text-button download-fallback"
            :href="exportReadyUrl"
            download
            >点击下载 CSV</a
          ><button class="text-button" @click="successMessage = ''">
            关闭
          </button>
        </div>

        <section v-if="page === 'workbench'" class="page-view workbench-page">
          <div class="page-head">
            <div>
              <div class="eyebrow">WORKSPACE / {{ user.name }}</div>
              <h1>早上好，{{ user.name }}</h1>
              <p class="muted">{{ todayLabel }} · 每条工作内容独立审批。</p>
            </div>
          </div>

          <template v-if="ownedProjectRows.length">
            <section class="workbench-owner-section">
              <div class="section-head">
                <div>
                  <h2>我的项目</h2>
                  <p class="muted">负责项目的预算、人工成本与收付款提醒</p>
                </div>
                <button
                  class="text-button"
                  @click="projectDataScope = 'OWNED'; go('projects')"
                >
                  进入项目管理 →
                </button>
              </div>
              <div class="workbench-owner-metrics">
                <button type="button" @click="go('projects')">
                  <b>{{ workbenchMetric("project_count") }}</b><span>负责项目</span>
                </button>
                <button type="button" @click="go('approvals')">
                  <b>{{ workbenchMetric("pending_worklog_count") }}</b
                  ><span>待审工时</span>
                </button>
                <button type="button" @click="go('projectContracts')">
                  <b>{{ moneyText(workbenchMetric("receivable_due_7d")) }}</b
                  ><span>7 天内应收</span>
                </button>
                <button type="button" @click="go('projectContracts')">
                  <b>{{ moneyText(workbenchMetric("payable_due_7d")) }}</b
                  ><span>7 天内应付</span>
                </button>
                <button type="button" @click="go('projectBoard')">
                  <b>{{ workbenchMetric("overdue_count") }}</b><span>逾期事项</span>
                </button>
                <button type="button" @click="go('projectBoard')">
                  <b>{{ workbenchMetric("warning_project_count") }}</b
                  ><span>预警项目</span>
                </button>
                <button type="button" @click="go('projectBoard')">
                  <b>{{ workbenchMetric("over_budget_project_count") }}</b
                  ><span>超预算项目</span>
                </button>
              </div>
              <div class="workbench-owner-grid">
                <div class="card workbench-project-card">
                  <div class="section-head">
                    <div>
                      <h2>项目经营概况</h2>
                      <p class="muted">预算、人工成本与收付款</p>
                    </div>
                  </div>
                  <div class="table-wrap">
                    <table class="workbench-project-table">
                      <thead>
                        <tr>
                          <th>项目</th>
                          <th>类型</th>
                          <th>预算执行</th>
                          <th>人员成本</th>
                          <th>已付 / 应付</th>
                          <th>已收 / 应收</th>
                          <th>预警</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="item in ownedProjectRows.slice(0, 8)"
                          :key="item.id"
                          @click="openProjectDetail({ id: item.id } as Project)"
                        >
                          <td>
                            <strong>{{ item.name }}</strong>
                            <small>{{ item.code }}</small>
                          </td>
                          <td>{{ optionLabel("project_type", item.project_type) }}</td>
                          <td>
                            <div class="workbench-progress">
                              <span
                                :class="projectExecutionClass(item.execution_status)"
                              >
                                {{ projectExecutionLabel(item.execution_status) }}
                              </span>
                              <small
                                >{{ item.completion_rate === null ? "未设置预算" : formatProjectDays(item.completion_rate) + "%" }} · {{ formatProjectDays(item.actual_days) }} / {{ formatProjectDays(item.budget_days) }} 天</small
                              >
                            </div>
                          </td>
                          <td>{{ moneyText(item.personnel_cost) }}</td>
                          <td>{{ moneyText(item.paid) }} / {{ moneyText(item.payable) }}</td>
                          <td>{{ moneyText(item.received) }} / {{ moneyText(item.receivable) }}</td>
                          <td>
                            <span v-if="item.warning" class="tag warning">{{ item.warning }}</span>
                            <span v-else>—</span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div class="workbench-quick-actions">
                    <button
                      v-if="canManage('receipts')"
                      class="secondary"
                      @click="go('projectReceipts')"
                    >
                      ＋ 增加收款
                    </button>
                    <button
                      v-if="canManage('payments')"
                      class="secondary"
                      @click="go('projectPayments')"
                    >
                      ＋ 发起付款
                    </button>
                    <button class="primary" @click="go('approvals')">工时审批</button>
                  </div>
                </div>
                <section class="card workbench-reminders">
                  <div class="section-head">
                    <div>
                      <h2>项目提醒</h2>
                      <p class="muted">收付款到期与逾期事项</p>
                    </div>
                  </div>
                  <div
                    v-if="!workbenchOverview?.reminders.length"
                    class="empty"
                  >
                    近期没有收付款到期或逾期事项
                  </div>
                  <button
                    v-for="reminder in workbenchOverview?.reminders.slice(0, 6)"
                    :key="reminder.kind + reminder.stage_name + reminder.planned_date"
                    class="list-link"
                    @click="go('projectContracts')"
                  >
                    <span
                      ><strong>{{ reminder.project_name }} · {{ reminder.stage_name }}</strong
                      ><small
                        >{{ workbenchReminderLabel(reminder.kind) }} ·
                        {{ reminder.planned_date }} · 剩余
                        {{ moneyText(reminder.remaining) }}</small
                      ></span
                    ><span
                      class="tag"
                      :class="
                        reminder.kind.startsWith('OVERDUE') ? 'danger' : 'warning'
                      "
                      >{{ workbenchReminderLabel(reminder.kind) }}</span
                    >
                  </button>
                </section>
              </div>
            </section>
          </template>

          <section class="workbench-employee-section">
            <div class="section-head">
              <div>
                <h2>我的工时</h2>
                <p class="muted">本月填报与审批进度</p>
              </div>
              <button class="primary" @click="openEditor()">＋ 填报工时</button>
            </div>
            <div class="metrics workbench-employee-metrics">
              <article class="card">
                <b class="metric-value-compact">{{ approvedSummary }}</b
                ><span>本月已审批天数</span>
              </article>
              <article class="card">
                <b>{{
                  worklogs.filter((item) => item.status === "PENDING_APPROVAL")
                    .length
                }}</b
                ><span>我的审批中</span>
              </article>
              <article class="card">
                <b>{{ pendingApprovals.length }}</b
                ><span>待我审批</span>
              </article>
              <article class="card">
                <b>{{ draftCount }}</b
                ><span>草稿/待修改</span>
              </article>
            </div>
            <div class="two-columns">
              <section class="card">
                <div class="section-head">
                  <div>
                    <h2>待处理事项</h2>
                    <p class="muted">需要你完成的操作</p>
                  </div>
                </div>
                <button v-if="draftCount" class="list-link" @click="go('worklogs')">
                  <span
                    ><strong>处理待提交工时</strong
                    ><small>{{ draftCount }} 条草稿或驳回记录</small></span
                  ><span>→</span></button
                ><button
                  v-if="pendingApprovals.length"
                  class="list-link"
                  @click="go('approvals')"
                >
                  <span
                    ><strong>处理工时审批</strong
                    ><small>{{ pendingApprovals.length }} 条待我审批任务</small
                    ></span
                  ><span>→</span>
                </button>
                <div v-if="!draftCount && !pendingApprovals.length" class="empty">
                  当前没有待处理事项
                </div>
              </section>
              <section class="card">
                <h2>最近工时</h2>
                <button
                  v-for="item in worklogs.slice(0, 4)"
                  :key="item.id"
                  class="list-link"
                  @click="
                    ['DRAFT', 'REJECTED'].includes(item.status)
                      ? openEditor(item)
                      : openWorklog(item)
                  "
                >
                  <span
                    ><strong>{{ item.project_name_snapshot }}</strong
                    ><small
                      >{{ item.start_date }} · {{ item.description }}</small
                    ></span
                  ><span class="tag" :class="statusClass(item.status)">{{
                    statusLabel(item.status)
                  }}</span>
                </button>
              </section>
            </div>
          </section>
        </section>

        <section
          v-else-if="page === 'worklogs'"
          class="page-view worklogs-page"
        >
          <div class="page-head">
            <div>
              <div class="eyebrow">MY WORKLOGS</div>
              <h1>我的工时</h1>
              <p class="muted">每条工作内容单独提交，随时查看审批进度。</p>
            </div>
            <button class="primary" @click="openEditor()">＋ 新增工时</button>
          </div>
          <section class="card worklog-list-card">
            <div class="worklog-toolbar">
              <div class="filters">
                <label class="filter-label"
                  >状态<select v-model="selectedStatus">
                    <option value="">全部状态</option>
                    <option value="DRAFT">草稿</option>
                    <option value="PENDING_APPROVAL">审批中</option>
                    <option value="REJECTED">已驳回</option>
                    <option value="APPROVED">已通过</option>
                  </select></label
                >
              </div>
              <div class="worklog-count">
                <strong>{{ filteredWorklogs.length }}</strong
                ><span>条工时记录</span
                ><span class="worklog-count-divider"></span
                ><span>已通过 {{ approvedSummary }}</span>
              </div>
              <small class="status-sync-note"
                >状态自动更新{{
                  statusSyncedAt ? ` · ${statusSyncedAt}` : ""
                }}</small
              >
            </div>
            <div class="table-wrap">
              <table class="worklog-table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>项目与工作内容</th>
                    <th>工时</th>
                    <th>审批人</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in filteredWorklogs" :key="item.id">
                    <td class="worklog-date">
                      <span>{{ item.start_date }}</span
                      ><small v-if="item.end_date !== item.start_date"
                        >至 {{ item.end_date }}</small
                      >
                    </td>
                    <td class="worklog-summary">
                      <strong>{{ item.project_name_snapshot }}</strong
                      ><span>{{ item.description }}</span>
                    </td>
                    <td class="worklog-quantity">
                      <strong>{{ item.quantity }}</strong
                      ><small>{{ unitLabel(item.unit) }}</small>
                    </td>
                    <td class="worklog-approver">
                      {{ item.approver_name_snapshot || "提交后确定" }}
                    </td>
                    <td class="worklog-status">
                      <span class="tag" :class="statusClass(item.status)">{{
                        statusLabel(item.status)
                      }}</span
                      ><small
                        v-if="item.rejection_reason"
                        class="form-helper"
                        >{{ item.rejection_reason }}</small
                      >
                    </td>
                    <td class="worklog-actions">
                      <div class="table-actions">
                        <button
                          v-if="['DRAFT', 'REJECTED'].includes(item.status)"
                          class="text-button"
                          @click="openEditor(item)"
                        >
                          {{
                            item.status === "REJECTED" ? "修改并提交" : "编辑"
                          }}</button
                        ><button
                          v-else
                          class="text-button"
                          @click="openDetail(item)"
                        >
                          查看详情
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!filteredWorklogs.length" class="empty">
                当前筛选范围没有工时记录<button
                  class="primary"
                  @click="openEditor()"
                >
                  新增第一条工时
                </button>
              </div>
            </div>
          </section>
        </section>

        <section v-else-if="page === 'editor'" class="page-view narrow">
          <div class="page-head">
            <div>
              <div class="eyebrow">WORKLOG EDITOR</div>
              <h1>{{ editingId ? "修改工时" : "新增工时" }}</h1>
              <p class="muted">
                先选择项目类型，再选择该类型下的项目；每条工时独立审批。
              </p>
            </div>
            <span class="tag teal">工作日天数</span>
          </div>
          <section class="card form-card">
            <div class="form-grid">
              <label
                >项目类型<select v-model="form.project_type">
                  <option value="" disabled>请选择项目类型</option>
                  <option
                    v-for="option in activeConfigOptions('project_type')"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select></label
              ><label class="project-picker-label"
                >项目
                <div class="project-picker" @click.stop>
                  <button
                    type="button"
                    class="project-picker-trigger"
                    :aria-expanded="projectPickerOpen"
                    :disabled="!form.project_type"
                    @click="toggleProjectPicker"
                  >
                    <span v-if="selectedProject"
                      ><strong
                        >{{ selectedProject.code }} ·
                        {{ selectedProject.name }}</strong
                      ><small
                        >{{ selectedProject.project_type }} ·
                        点击展开筛选项目</small
                      ></span
                    ><span v-else class="project-picker-placeholder">{{
                      form.project_type
                        ? "请选择可填报项目"
                        : "请先选择项目类型"
                    }}</span
                    ><span class="project-picker-chevron" aria-hidden="true"
                      >⌄</span
                    >
                  </button>
                  <div v-if="projectPickerOpen" class="project-picker-menu">
                    <input
                      v-model="projectQuery"
                      type="search"
                      placeholder="按项目名称或编码筛选"
                      aria-label="按项目名称或编码筛选"
                      @click.stop
                    />
                    <div class="project-picker-options">
                      <button
                        v-for="project in filteredProjects"
                        :key="project.id"
                        type="button"
                        class="project-picker-option"
                        @click="chooseProject(project)"
                      >
                        <span
                          ><strong>{{ project.code }}</strong
                          ><small>{{ project.name }}</small></span
                        ><b
                          v-if="project.id === Number(form.project_id)"
                          aria-label="当前项目"
                          >✓</b
                        >
                      </button>
                      <p
                        v-if="!filteredProjects.length"
                        class="project-picker-empty"
                      >
                        没有匹配的可填报项目
                      </p>
                    </div>
                  </div>
                </div>
                <small
                  class="form-helper"
                  :class="
                    isSelfApprover && selectedProject?.leader_user_id
                      ? 'muted'
                      : ''
                  "
                  >实际审批人：{{ actualApproverName }}</small
                ></label
              >
              <div v-if="isSelfApprover" class="notice warning full">
                <strong>本人填报</strong
                ><span>本人是项目审批人，本条工时将由上级领导审批。</span>
              </div>
              <label
                >项目阶段<select v-model="form.stage">
                  <option value="" disabled>请选择项目阶段</option>
                  <option
                    v-for="option in activeConfigOptions('project_stage')"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select></label
              ><label
                >工时类型<select v-model="form.work_type">
                  <option value="" disabled>请选择工时类型</option>
                  <option
                    v-for="option in activeConfigOptions('work_type')"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select></label
              ><label
                >工作状态<select v-model="form.work_status">
                  <option value="" disabled>请选择工作状态</option>
                  <option
                    v-for="option in activeConfigOptions('work_status')"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select></label
              ><label
                >开始日期<input v-model="form.start_date" type="date" /></label
              ><label
                >结束日期<input v-model="form.end_date" type="date" /></label
              ><label
                >工时天数<input
                  v-model.number="form.quantity"
                  type="number"
                  min="0.25"
                  step="0.25" /></label
              ><label class="full"
                >工作描述<textarea
                  v-model="form.description"
                  placeholder="描述本次工作的具体产出，至少 2 个字"
                ></textarea>
              </label>
            </div>
            <div class="form-footer">
              <button class="secondary" @click="go('worklogs')">取消</button
              ><button class="secondary" @click="saveWorklog(false)">
                保存草稿</button
              ><button class="primary" @click="saveWorklog(true)">
                保存并提交
              </button>
            </div>
          </section>
        </section>

        <section
          v-else-if="page === 'detail'"
          class="page-view worklog-detail-page"
        >
          <div class="page-head detail-page-head">
            <div>
              <div class="eyebrow">WORKLOG DETAIL</div>
              <h1>工时提交结果</h1>
              <p class="muted">本条工时的完整信息、审批状态和通知结果。</p>
            </div>
            <button class="secondary" @click="go('worklogs')">
              返回我的工时
            </button>
          </div>
          <section v-if="selectedTask" class="detail-layout">
            <article class="card detail-main-card">
              <div class="detail-result-head">
                <div class="detail-serial">
                  <small>工时单号</small
                  ><strong>{{ selectedTask.serial_no }}</strong>
                </div>
                <div class="detail-result-status">
                  <small>当前状态</small
                  ><span
                    class="tag"
                    :class="statusClass(selectedTask.worklog.status)"
                    >{{ statusLabel(selectedTask.worklog.status) }}</span
                  >
                </div>
                <div class="detail-approver">
                  <small>实际审批人</small
                  ><strong>{{
                    selectedTask.worklog.approver_name_snapshot || "未确定"
                  }}</strong>
                </div>
              </div>
              <div class="detail-section">
                <div class="detail-section-head">
                  <div>
                    <small class="detail-kicker">WORK SUMMARY</small>
                    <h2>工作信息</h2>
                  </div>
                  <span class="tag teal"
                    >{{ selectedTask.worklog.quantity }} 天</span
                  >
                </div>
                <div class="detail-grid">
                  <div>
                    <small>项目</small
                    ><strong>{{
                      selectedTask.worklog.project_name_snapshot
                    }}</strong>
                  </div>
                  <div>
                    <small>项目阶段</small
                    ><strong>{{ selectedTask.worklog.stage }}</strong>
                  </div>
                  <div>
                    <small>工时类型</small
                    ><strong>{{
                      workTypeLabel(selectedTask.worklog.work_type)
                    }}</strong>
                  </div>
                  <div>
                    <small>工作状态</small
                    ><strong>{{
                      workStatusLabel(selectedTask.worklog.work_status)
                    }}</strong>
                  </div>
                  <div>
                    <small>日期范围</small
                    ><strong
                      >{{ selectedTask.worklog.start_date }} 至
                      {{ selectedTask.worklog.end_date }}</strong
                    >
                  </div>
                  <div>
                    <small>提交时间</small
                    ><strong class="date-value">{{
                      formatDateTime(selectedTask.worklog.submitted_at) ||
                      "尚未提交"
                    }}</strong>
                  </div>
                  <div>
                    <small>处理时间</small
                    ><strong class="date-value">{{
                      formatDateTime(selectedTask.processed_at) ||
                      "待审批人处理"
                    }}</strong>
                  </div>
                  <div
                    v-if="
                      selectedTask.worklog.approval_comment ||
                      selectedTask.comment
                    "
                  >
                    <small>审批意见</small
                    ><strong>{{
                      selectedTask.worklog.approval_comment ||
                      selectedTask.comment
                    }}</strong>
                  </div>
                </div>
                <div class="detail-description">
                  <small>工作描述</small>
                  <p>{{ selectedTask.worklog.description }}</p>
                </div>
                <div
                  v-if="selectedTask.worklog.rejection_reason"
                  class="detail-description rejection-copy"
                >
                  <small>驳回原因</small>
                  <p>{{ selectedTask.worklog.rejection_reason }}</p>
                </div>
              </div>
              <div
                class="notice detail-notice"
                :class="
                  selectedTask.notification?.status === 'SENT' ? '' : 'warning'
                "
              >
                <strong
                  >飞书通知：{{
                    notificationStatusLabel(selectedTask.notification?.status)
                  }}</strong
                ><span v-if="selectedTask.notification?.status === 'SENT'"
                  >审批人可从飞书消息进入系统处理。</span
                ><span v-else>{{
                  notificationErrorLabel(
                    selectedTask.notification?.error_message,
                  )
                }}</span>
              </div>
            </article>
            <aside class="card detail-timeline-card">
              <div class="detail-section-head">
                <div>
                  <small class="detail-kicker">APPROVAL FLOW</small>
                  <h2>审批时间线</h2>
                </div>
                <span
                  class="tag"
                  :class="statusClass(selectedTask.worklog.status)"
                  >{{
                    selectedTask.status === "PENDING"
                      ? "待处理"
                      : statusLabel(selectedTask.status)
                  }}</span
                >
              </div>
              <div class="timeline">
                <div>
                  <b>提交工时</b
                  ><small
                    >{{ formatDateTime(selectedTask.submitted_at) }} ·
                    {{ userName(selectedTask.submitter_user_id) }}</small
                  >
                </div>
                <div>
                  <b>确定审批人</b
                  ><small>{{
                    selectedTask.worklog.approver_name_snapshot || "未确定"
                  }}</small>
                </div>
                <div>
                  <b>发送飞书通知</b
                  ><small>{{
                    notificationStatusLabel(selectedTask.notification?.status)
                  }}</small
                  ><small
                    v-if="selectedTask.notification?.status === 'FAILED'"
                    >{{
                      notificationErrorLabel(
                        selectedTask.notification.error_message,
                      )
                    }}</small
                  >
                </div>
                <div>
                  <b>{{
                    selectedTask.status === "PENDING"
                      ? "等待处理"
                      : selectedTask.status === "APPROVED"
                        ? "审批通过"
                        : "已驳回"
                  }}</b
                  ><small>{{
                    formatDateTime(selectedTask.processed_at) || "待审批人处理"
                  }}</small
                  ><small v-if="selectedTask.comment"
                    >审批意见：{{ selectedTask.comment }}</small
                  >
                </div>
              </div>
              <button
                class="secondary detail-back-button"
                @click="go('worklogs')"
              >
                返回我的工时
              </button>
            </aside>
          </section>
          <section v-else class="card empty">
            <h2>还没有可查看的工时提交</h2>
            <button class="primary" @click="go('worklogs')">
              返回我的工时
            </button>
          </section>
        </section>

        <section
          v-else-if="page === 'approvals'"
          class="page-view approval-page"
        >
          <div class="page-head">
            <div>
              <div class="eyebrow">APPROVALS / WORKLOGS</div>
              <h1>工时审批</h1>
              <p class="muted">按待处理和历史结果查看你负责的工时审批。</p>
            </div>
            <button class="secondary" @click="refresh">刷新</button>
          </div>
          <section class="card approval-card">
            <div class="approval-tabs" role="tablist" aria-label="工时审批状态">
              <button
                class="approval-tab"
                :class="{ active: approvalTab === 'pending' }"
                role="tab"
                :aria-selected="approvalTab === 'pending'"
                @click="approvalTab = 'pending'"
              >
                <span>待我审批</span
                ><b v-if="pendingApprovals.length">{{
                  pendingApprovals.length
                }}</b></button
              ><button
                class="approval-tab"
                :class="{ active: approvalTab === 'processed' }"
                role="tab"
                :aria-selected="approvalTab === 'processed'"
                @click="approvalTab = 'processed'"
              >
                <span>已审批</span
                ><b v-if="processedApprovals.length">{{
                  processedApprovals.length
                }}</b>
              </button>
            </div>
            <div v-if="approvalItems.length" class="approval-list">
              <button
                v-for="task in approvalItems"
                :key="task.id"
                class="approval-row"
                @click="openTask(task)"
              >
                <span
                  ><strong>{{ task.worklog.project_name_snapshot }}</strong
                  ><small
                    >{{ userName(task.submitter_user_id) }} ·
                    {{ task.worklog.start_date }} ·
                    {{ task.worklog.quantity }} 天</small
                  ><small>{{ task.worklog.description }}</small></span
                ><span
                  ><span
                    class="tag"
                    :class="
                      approvalTab === 'pending'
                        ? 'warning'
                        : statusClass(task.status)
                    "
                    >{{
                      approvalTab === "pending"
                        ? "待处理"
                        : statusLabel(task.status)
                    }}</span
                  ><b>→</b></span
                >
              </button>
            </div>
            <div v-else class="empty">
              <h2>
                {{
                  approvalTab === "pending" ? "暂无待审批" : "暂无已审批记录"
                }}
              </h2>
              <p>
                {{
                  approvalTab === "pending"
                    ? "新的工时提交后会出现在这里。"
                    : "处理过的工时审批会保留在这里。"
                }}
              </p>
            </div>
          </section>
        </section>

        <section v-else-if="page === 'approvalDetail'" class="page-view narrow">
          <div class="page-head">
            <div>
              <div class="eyebrow">
                APPROVAL DETAIL / {{ selectedTask?.serial_no }}
              </div>
              <h1>工时审批详情</h1>
              <p class="muted">
                提交人：{{
                  userName(selectedTask?.submitter_user_id || null)
                }}
                · {{ selectedTask?.submitted_at }}
              </p>
            </div>
            <span
              v-if="selectedTask"
              class="tag"
              :class="
                statusClass(
                  selectedTask.status === 'PENDING'
                    ? 'PENDING_APPROVAL'
                    : selectedTask.status,
                )
              "
              >{{
                selectedTask.status === "PENDING"
                  ? "待审批"
                  : statusLabel(selectedTask.status)
              }}</span
            >
          </div>
          <section v-if="selectedTask" class="two-columns">
            <section class="card">
              <h2>工作内容</h2>
              <div class="detail-grid">
                <div>
                  <small>项目</small
                  ><strong>{{
                    selectedTask.worklog.project_name_snapshot
                  }}</strong>
                </div>
                <div>
                  <small>项目阶段</small
                  ><strong>{{ selectedTask.worklog.stage }}</strong>
                </div>
                <div>
                  <small>工时类型</small
                  ><strong>{{
                    workTypeLabel(selectedTask.worklog.work_type)
                  }}</strong>
                </div>
                <div>
                  <small>工作状态</small
                  ><strong>{{
                    workStatusLabel(selectedTask.worklog.work_status)
                  }}</strong>
                </div>
                <div>
                  <small>日期范围</small
                  ><strong
                    >{{ selectedTask.worklog.start_date }} 至
                    {{ selectedTask.worklog.end_date }}</strong
                  >
                </div>
                <div>
                  <small>工时天数</small
                  ><strong>{{ selectedTask.worklog.quantity }} 天</strong>
                </div>
                <div>
                  <small>审批人</small
                  ><strong>{{
                    selectedTask.worklog.approver_name_snapshot
                  }}</strong>
                </div>
                <div class="full">
                  <small>工作描述</small
                  ><strong>{{ selectedTask.worklog.description }}</strong>
                </div>
              </div>
              <div
                v-if="
                  selectedTask.status === 'PENDING' &&
                  selectedTask.approver_user_id === activeUserId
                "
                class="actions"
              >
                <button
                  class="primary success-button"
                  @click="processTask('approve')"
                >
                  通过</button
                ><button
                  class="secondary danger-button"
                  @click="processTask('reject')"
                >
                  驳回</button
                ><button class="secondary" @click="remindTask">
                  重新发送通知
                </button>
              </div>
              <div
                v-if="
                  selectedTask.status === 'PENDING' &&
                  selectedTask.approver_user_id === activeUserId
                "
                class="reject-box"
              >
                <label
                  >驳回原因（驳回时必填）<textarea
                    v-model="rejectionReason"
                    placeholder="请填写需要修改的内容"
                  ></textarea>
                </label>
              </div>
              <div
                v-if="selectedTask.status === 'REJECTED'"
                class="notice error"
              >
                <strong>驳回意见</strong><span>{{ selectedTask.comment }}</span>
              </div>
            </section>
            <section class="card">
              <h2>审批时间线</h2>
              <div class="timeline">
                <div>
                  <b>提交工时</b
                  ><small
                    >{{ selectedTask.submitted_at }} ·
                    {{ userName(selectedTask.submitter_user_id) }}</small
                  >
                </div>
                <div>
                  <b>发送飞书通知</b
                  ><small>{{
                    notificationStatusLabel(selectedTask.notification?.status)
                  }}</small
                  ><small
                    v-if="selectedTask.notification?.status === 'FAILED'"
                    >{{
                      notificationErrorLabel(
                        selectedTask.notification.error_message,
                      )
                    }}</small
                  >
                </div>
                <div>
                  <b>{{
                    selectedTask.status === "PENDING"
                      ? "等待处理"
                      : selectedTask.status === "APPROVED"
                        ? "审批通过"
                        : "已驳回"
                  }}</b
                  ><small>{{
                    selectedTask.processed_at || "待审批人处理"
                  }}</small
                  ><small v-if="selectedTask.comment"
                    >审批意见：{{ selectedTask.comment }}</small
                  >
                </div>
              </div>
            </section>
          </section>
          <section v-else class="card empty">
            <h2>审批任务不存在</h2>
            <button class="primary" @click="go('approvals')">
              返回待我审批
            </button>
          </section>
        </section>

        <section v-else-if="page === 'reports'" class="page-view report-page">
          <div class="page-head report-page-head">
            <div>
              <div class="eyebrow">REPORTS / WORKLOAD</div>
              <h1>工时看板</h1>
              <p class="muted">
                只看工时口径：投入规模、填报分布与审批效率。
              </p>
            </div>
            <span class="tag teal">{{
              report?.scope.department_name || "全部部门"
            }}</span>
          </div>
          <section class="card report-toolbar">
            <div class="report-toolbar-head">
              <div>
                <span class="report-toolbar-kicker">VIEW / FILTERS</span
                ><strong>筛选看板数据</strong>
              </div>
              <span class="report-toolbar-meta">数据口径：已通过、已锁定</span>
            </div>
            <div class="report-filter">
              <label
                >部门<select v-model="reportDepartment">
                  <option value="">全部部门</option>
                  <option
                    v-for="name in report?.scope.department_options || []"
                    :key="name"
                    :value="name"
                  >
                    {{ name }}
                  </option>
                </select></label
              ><label
                >开始日期<input
                  v-model="reportPeriodStart"
                  type="date" /></label
              ><label
                >结束日期<input v-model="reportPeriodEnd" type="date"
              /></label>
            </div>
            <div class="report-toolbar-actions">
              <div class="report-toolbar-buttons">
                <button class="primary" @click="loadReport">查询</button
                ><button class="secondary" @click="exportReport">
                  导出明细
                </button>
              </div>
              <span class="report-generated-at"
                >更新于
                {{
                  report?.generated_at
                    ? formatDateTime(report.generated_at)
                    : "待查询"
                }}</span
              >
            </div>
          </section>
          <div v-if="report" class="report-overview">
            <article class="report-overview-card report-overview-primary">
              <span>已审批工时</span><strong>{{ reportTotalSummary }}</strong
              ><small>已通过和已锁定的有效工时</small>
              <div class="report-overview-foot">
                <span
                  >{{ report?.metrics.approved_count || 0 }} 条已完成审批</span
                ><span
                  >共 {{ report?.metrics.submitted_count || 0 }} 条提交</span
                >
              </div>
            </article>
            <article class="report-overview-card">
              <span>涉及项目数</span
              ><strong>{{ report?.metrics.project_count || 0 }}</strong
              ><small>当前范围有有效工时的项目</small>
              <div class="report-overview-foot">
                <span>执行中 {{ report?.metrics.execution_project_count || 0 }} 个</span>
              </div>
            </article>
            <article class="report-overview-card">
              <span>待审批记录</span
              ><strong>{{ report?.metrics.pending_count || 0 }}</strong
              ><small
                >其中 {{ report?.metrics.overdue_pending_count || 0 }} 条超过 1
                天</small
              >
              <div class="report-overview-foot">
                <span
                  >审批完成率 {{ report?.metrics.approval_rate || 0 }}%</span
                >
              </div>
            </article>
            <article class="report-overview-card report-overview-people">
              <span>填报人数</span
              ><strong>{{ report?.metrics.user_count || 0 }}</strong
              ><small>当前范围有有效工时</small>
              <div class="report-overview-foot">
                <span>覆盖当前筛选部门</span>
              </div>
            </article>
            <article class="report-overview-card report-overview-rate">
              <span>审批通过率</span
              ><strong>{{ report?.metrics.approval_rate || 0 }}%</strong
              ><small>已通过记录 / 已提交记录</small>
              <div class="report-overview-foot">
                <span>已完成 {{ report?.metrics.approved_count || 0 }} 条</span>
              </div>
            </article>
          </div>
          <div v-if="report" class="report-chart-grid report-echarts-grid">
            <section class="card report-card report-feature-card">
              <div class="section-head">
                <div>
                  <h2>部门投入对比</h2>
                  <p class="muted">按部门汇总已审批工时，判断资源分布</p>
                </div>
                <strong>天</strong>
              </div>
              <div ref="departmentChartEl" class="report-chart"></div>
            </section>
            <section class="card report-card report-feature-card">
              <div class="section-head">
                <div>
                  <h2>工时投入趋势</h2>
                  <p class="muted">按填报开始日查看投入变化</p>
                </div>
                <strong>天</strong>
              </div>
              <div ref="trendChartEl" class="report-chart"></div>
            </section>
            <section class="card report-card">
              <div class="section-head">
                <div>
                  <h2>项目投入排行</h2>
                  <p class="muted">按项目汇总已审批工时</p>
                </div>
                <strong>Top 10</strong>
              </div>
              <div ref="projectChartEl" class="report-chart"></div>
            </section>
            <section class="card report-card">
              <div class="section-head">
                <div>
                  <h2>人员工时排行</h2>
                  <p class="muted">按填报人汇总已审批工时</p>
                </div>
                <strong>Top 8</strong>
              </div>
              <div ref="userChartEl" class="report-chart"></div>
            </section>
            <section class="card report-card">
              <div class="section-head">
                <div>
                  <h2>审批状态分布</h2>
                  <p class="muted">查看当前范围内的处理进度</p>
                </div>
              </div>
              <div ref="statusChartEl" class="report-chart"></div>
            </section>
            <section class="card report-card">
              <div class="section-head">
                <div>
                  <h2>工作阶段分布</h2>
                  <p class="muted">按项目阶段汇总已审批工时</p>
                </div>
                <strong>天</strong>
              </div>
              <div ref="stageChartEl" class="report-chart"></div>
            </section>
            <section class="card report-card report-wide">
              <div class="section-head">
                <div>
                  <h2>项目阶段占比</h2>
                  <p class="muted">按项目查看各阶段投入结构</p>
                </div>
                <strong>%</strong>
              </div>
              <div
                ref="projectStageChartEl"
                class="report-chart report-chart-tall"
              ></div>
            </section>
            <section class="card report-card">
              <div class="section-head">
                <div>
                  <h2>工时类型分布</h2>
                  <p class="muted">项目、管理和其它工时占比</p>
                </div>
                <strong>天</strong>
              </div>
              <div ref="workTypeChartEl" class="report-chart"></div>
            </section>
          </div>
          <section v-else class="card empty">报表正在加载，请稍候</section>
        </section>

        <section
          v-else-if="page === 'projects'"
          class="page-view project-management-page project-v3-page"
        >
          <div class="page-head">
            <div>
              <div class="eyebrow">PROJECT MASTER DATA</div>
              <h1>项目管理</h1>
              <p class="muted">
                维护项目主信息。预算执行、人工成本和经营数据在项目详情中查看。
              </p>
            </div>
            <div class="actions">
              <button class="primary" @click="openProjectForm">
                ＋ 新增项目
              </button>
            </div>
          </div>
          <section class="card project-filter-card project-v3-filter-card">
            <div class="project-filter-heading">
              <strong>筛选项目</strong>
              <div class="scope-switch" aria-label="项目数据范围">
                <button
                  type="button"
                  :class="{ active: projectDataScope === 'OWNED' }"
                  @click="
                    projectDataScope = 'OWNED';
                    queryProjects();
                  "
                >
                  我负责的
                </button>
                <button
                  type="button"
                  :class="{ active: projectDataScope === 'ALL' }"
                  @click="
                    projectDataScope = 'ALL';
                    queryProjects();
                  "
                >
                  全部项目
                </button>
              </div>
            </div>
            <div class="project-filter-grid">
              <label
                >项目类型<select v-model="projectFilterType">
                  <option value="">全部类型</option>
                  <option
                    v-for="option in activeConfigOptions('project_type')"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select></label
              ><label class="project-department-filter"
                >项目部门
                <div
                  class="project-department-picker"
                  :class="{ open: projectDepartmentPickerOpen }"
                >
                  <button
                    type="button"
                    class="project-department-trigger"
                    :aria-expanded="projectDepartmentPickerOpen"
                    @click="toggleProjectDepartmentPicker"
                    @keydown.esc="projectDepartmentPickerOpen = false"
                  >
                    <span :class="{ placeholder: !projectFilterDepartment }">{{
                      selectedProjectDepartmentLabel
                    }}</span
                    ><span class="project-department-chevron">⌄</span>
                  </button>
                  <div
                    v-if="projectDepartmentPickerOpen"
                    class="project-department-menu"
                    role="listbox"
                    @keydown.esc="projectDepartmentPickerOpen = false"
                  >
                    <button
                      type="button"
                      class="project-department-option project-department-all"
                      :class="{ selected: !projectFilterDepartment }"
                      @click="selectProjectDepartment(0)"
                    >
                      <span>全部部门</span
                      ><b v-if="!projectFilterDepartment">✓</b>
                    </button>
                    <div
                      v-for="node in projectDepartmentTree"
                      :key="node.department.id"
                      class="project-department-row"
                      :style="{ '--tree-depth': node.depth }"
                    >
                      <button
                        type="button"
                        class="project-department-expand"
                        :class="{ 'is-leaf': !node.hasChildren }"
                        :aria-label="
                          node.hasChildren ? '展开或收起下级部门' : '无下级部门'
                        "
                        @click.stop="
                          node.hasChildren &&
                          toggleProjectDepartmentNode(node.department.id)
                        "
                      >
                        <span v-if="node.hasChildren">{{
                          projectDepartmentExpanded.has(node.department.id)
                            ? "−"
                            : "+"
                        }}</span></button
                      ><button
                        type="button"
                        class="project-department-option"
                        :class="{
                          selected:
                            projectFilterDepartment === node.department.id,
                        }"
                        @click="selectProjectDepartment(node.department.id)"
                      >
                        <span>{{ node.department.name }}</span
                        ><small v-if="node.depth === 0 && node.hasChildren"
                          >包含下级部门</small
                        ><b
                          v-if="projectFilterDepartment === node.department.id"
                          >✓</b
                        >
                      </button>
                    </div>
                  </div>
                </div></label
              ><label
                >项目状态<select v-model="projectFilterStatus">
                  <option value="">全部状态</option>
                  <option
                    v-for="option in activeConfigOptions('project_status')"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select></label
              ><label
                >项目负责人<select v-model.number="projectFilterOwner">
                  <option :value="0">全部负责人</option>
                  <option
                    v-for="person in projectOwnerOptions"
                    :key="person.id"
                    :value="person.id"
                  >
                    {{ person.name }} · {{ person.department_name }}
                  </option>
                </select></label
              ><label
                >客户<select v-model.number="projectFilterCustomer">
                  <option :value="0">全部客户</option>
                  <option
                    v-for="customer in customers"
                    :key="customer.id"
                    :value="customer.id"
                  >
                    {{ customer.name }}
                  </option>
                </select></label
              ><label class="project-filter-keyword"
                >项目标题<input
                  v-model.trim="projectFilterKeyword"
                  type="search"
                  placeholder="按名称或编号查询"
                  @keyup.enter="queryProjects"
              /></label>
              <div class="project-filter-actions">
                <button class="primary" @click="queryProjects">查询</button>
                <button
                  class="secondary project-filter-reset"
                  @click="resetProjectFilters"
                >
                  重置
                </button>
              </div>
            </div>
          </section>
          <section class="card project-v3-list-card">
            <div class="section-head">
              <div>
                <h2>项目列表</h2>
                <p class="muted">
                  共
                  {{ projectListTotal }} 个项目，点击项目名称查看预算与经营概况
                </p>
              </div>
              <span class="tag teal">主数据</span>
            </div>
            <div v-if="projectListLoading" class="empty">正在加载项目…</div>
            <div v-else class="table-wrap">
              <table class="project-table project-v3-table">
                <thead>
                  <tr>
                    <th>项目</th>
                    <th>状态</th>
                    <th>类型</th>
                    <th>负责人</th>
                    <th>所属部门</th>
                    <th>客户</th>
                    <th>工时填报</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="project in projectManagementPagedProjects"
                    :key="project.id"
                    @click="openProjectDetail(project)"
                  >
                    <td>
                      <button class="project-name-link" type="button">
                        <strong>{{ project.name }}</strong>
                        <small>{{ project.code }}</small>
                      </button>
                    </td>
                    <td>
                      <span
                        class="tag"
                        :class="
                          project.status === 'ACTIVE' ? 'success' : 'warning'
                        "
                        >{{
                          optionLabel("project_status", project.status)
                        }}</span
                      >
                    </td>
                    <td>
                      <span class="tag teal">{{
                        optionLabel("project_type", project.project_type)
                      }}</span>
                    </td>
                    <td>
                      <strong>{{ project.owner_name }}</strong>
                    </td>
                    <td>
                      <span class="project-path">{{
                        project.department_path ||
                        project.department_name ||
                        "未配置"
                      }}</span>
                    </td>
                    <td>{{ project.customer_name || "未关联" }}</td>
                    <td>
                      <span
                        class="tag"
                        :class="project.allow_worklog ? 'teal' : 'neutral'"
                        >{{
                          project.allow_worklog ? "可填报" : "不可填报"
                        }}</span
                      >
                    </td>
                    <td>
                      <div class="table-actions" @click.stop>
                        <button
                          class="text-button"
                          @click="openProjectDetail(project)"
                        >
                          查看
                        </button>
                        <button
                          class="text-button"
                          @click="editProject(project)"
                        >
                          编辑</button
                        ><button
                          class="text-button danger-button"
                          @click="deleteProject(project)"
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div
                v-if="!projectManagementFilteredProjects.length"
                class="empty"
              >
                暂无符合当前条件的项目
              </div>
              <div class="admin-pagination project-pagination">
                <span
                  >第 {{ projectPage }} / {{ projectPageCount }} 页 · 共
                  {{ projectListTotal }} 个项目</span
                >
                <div class="admin-pagination-actions">
                  <label
                    >每页条数<select
                      v-model="projectPageSizeMode"
                      @change="changeProjectPageSizeMode"
                    >
                      <option value="10">10 条</option>
                      <option value="20">20 条</option>
                      <option value="50">50 条</option>
                      <option value="custom">自定义</option></select
                    ><input
                      v-if="projectPageSizeMode === 'custom'"
                      v-model.number="projectPageSize"
                      type="number"
                      min="1"
                      max="200"
                      placeholder="1-200"
                      @change="changeProjectCustomPageSize" /></label
                  ><button
                    class="secondary"
                    :disabled="projectPage <= 1"
                    @click="changeProjectPage(projectPage - 1)"
                  >
                    上一页</button
                  ><button
                    class="secondary"
                    :disabled="projectPage >= projectPageCount"
                    @click="changeProjectPage(projectPage + 1)"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </div>
          </section>
          <div v-if="projectFormOpen" class="modal-backdrop">
            <section
              class="modal-card"
              role="dialog"
              aria-modal="true"
              aria-labelledby="project-modal-title"
            >
              <div class="modal-head">
                <div>
                  <div class="eyebrow">PROJECT FORM</div>
                  <h2 id="project-modal-title">
                    {{ editingProjectId ? "编辑项目" : "新增项目" }}
                  </h2>
                  <p class="muted">
                    负责人、项目部门、审批人和上级领导必须选择组织架构中的启用项。
                  </p>
                </div>
                <button
                  class="modal-close"
                  aria-label="关闭弹窗"
                  @click="resetProjectForm"
                >
                  ×
                </button>
              </div>
              <div class="form-grid project-v3-form-grid">
                <label
                  >项目编码<input
                    v-model.trim="projectForm.code"
                    placeholder="如 PRJ-2026-010" /></label
                ><label
                  >项目名称<input
                    v-model.trim="projectForm.name"
                    placeholder="请输入项目名称" /></label
                ><label
                  >项目状态<select v-model="projectForm.status">
                    <option value="" disabled>请选择项目状态</option>
                    <option
                      v-for="option in activeConfigOptions('project_status')"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select></label
                ><label
                  >项目类型<select v-model="projectForm.project_type">
                    <option value="" disabled>请选择项目类型</option>
                    <option
                      v-for="option in activeConfigOptions('project_type')"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select></label
                ><label
                  >项目负责人<select v-model.number="projectForm.owner_user_id">
                    <option :value="0" disabled>请选择组织用户</option>
                    <option
                      v-for="person in demoUsers"
                      :key="person.id"
                      :value="person.id"
                    >
                      {{ person.name }} · {{ person.department_name }}
                    </option>
                  </select></label
                ><label
                  >项目部门<select v-model.number="projectForm.department_id">
                    <option :value="0" disabled>请选择组织部门</option>
                    <option
                      v-for="department in projectDepartmentOptions"
                      :key="department.id"
                      :value="department.id"
                    >
                      {{ department.path || department.name }}
                    </option></select
                  ><small class="form-helper" v-if="!departments.length"
                    >暂无启用部门，请先同步组织架构</small
                  ></label
                ><label
                  >客户<select v-model="projectForm.customer_id">
                    <option :value="null">暂不关联客户</option>
                    <option
                      v-for="customer in customers"
                      :key="customer.id"
                      :value="customer.id"
                    >
                      {{ customer.name }}
                    </option>
                  </select></label
                ><label
                  >工时填报<select v-model="projectForm.allow_worklog">
                    <option :value="true">允许填报</option>
                    <option :value="false">关闭填报</option>
                  </select></label
                ><label
                  >项目审批人<select
                    v-model.number="projectForm.approver_user_id"
                  >
                    <option :value="0" disabled>请选择组织用户</option>
                    <option
                      v-for="person in demoUsers"
                      :key="person.id"
                      :value="person.id"
                    >
                      {{ person.name }} · {{ person.department_name }}
                    </option>
                  </select></label
                ><label
                  >上级领导<select v-model.number="projectForm.leader_user_id">
                    <option :value="0" disabled>请选择组织用户</option>
                    <option
                      v-for="person in demoUsers"
                      :key="person.id"
                      :value="person.id"
                    >
                      {{ person.name }} · {{ person.department_name }}
                    </option>
                  </select></label
                ><label
                  >开始日期<input
                    v-model="projectForm.start_date"
                    type="date" /></label
                ><label
                  >计划结束日期<input
                    v-model="projectForm.planned_end_date"
                    type="date" /></label
                ><label
                  >预算人天数<input
                    v-model.number="projectForm.budget_days"
                    type="number"
                    min="0"
                    step="0.5"
                    placeholder="请输入预算人天数" /></label
                ><label
                  >项目成本预算<input
                    v-model.number="projectForm.budget_cost"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="请输入成本预算金额" /></label
                ><label class="project-description-field"
                  >项目说明<textarea
                    v-model.trim="projectForm.description"
                    rows="4"
                    placeholder="填写项目目标、范围或交付说明"
                  ></textarea>
                </label>
              </div>
              <div class="form-footer">
                <button class="secondary" @click="resetProjectForm">取消</button
                ><button
                  class="primary"
                  :disabled="!departments.length"
                  @click="saveProject"
                >
                  保存项目
                </button>
              </div>
            </section>
          </div>
        </section>

        <section
          v-else-if="page === 'projectDetail'"
          class="page-view project-detail-v3-page"
        >
          <template v-if="selectedManagedProject">
            <div class="project-detail-hero">
              <div>
                <button
                  class="text-button project-back"
                  @click="go('projects')"
                >
                  ← 返回项目列表
                </button>
                <div class="project-detail-title-row">
                  <h1>{{ selectedManagedProject.name }}</h1>
                  <span
                    class="tag"
                    :class="
                      selectedManagedProject.status === 'ACTIVE'
                        ? 'success'
                        : 'warning'
                    "
                  >
                    {{
                      optionLabel(
                        "project_status",
                        selectedManagedProject.status,
                      )
                    }}
                  </span>
                </div>
                <p>
                  {{ selectedManagedProject.code }} ·
                  {{
                    optionLabel(
                      "project_type",
                      selectedManagedProject.project_type,
                    )
                  }}
                  ·
                  {{
                    selectedManagedProject.department_path ||
                    selectedManagedProject.department_name ||
                    "未配置部门"
                  }}
                </p>
              </div>
              <div class="actions">
                <button
                  class="secondary"
                  @click="editProject(selectedManagedProject)"
                >
                  编辑项目信息
                </button>
              </div>
            </div>

            <nav class="project-detail-tabs" aria-label="项目详情模块">
              <button
                type="button"
                :class="{ active: projectDetailTab === 'overview' }"
                @click="projectDetailTab = 'overview'"
              >
                概况
              </button>
              <button
                type="button"
                :class="{ active: projectDetailTab === 'info' }"
                @click="projectDetailTab = 'info'"
              >
                基本信息
              </button>
              <button
                type="button"
                :class="{ active: projectDetailTab === 'team' }"
                @click="projectDetailTab = 'team'"
              >
                人员与工时
              </button>
              <button
                type="button"
                :class="{ active: projectDetailTab === 'budget' }"
                @click="projectDetailTab = 'budget'"
              >
                预算
              </button>
              <button
                type="button"
                :class="{ active: projectDetailTab === 'finance' }"
                @click="projectDetailTab = 'finance'"
              >
                合同与资金
              </button>
              <button
                type="button"
                :class="{ active: projectDetailTab === 'audit' }"
                @click="projectDetailTab = 'audit'; loadProjectAudit()"
              >
                操作记录
              </button>
            </nav>

            <template v-if="projectDetailTab === 'overview'">
              <div v-if="projectAnalysisLoading && !projectAnalysis" class="card project-analysis-state">
                <div class="loading-spinner"></div>
                <strong>正在加载项目经营分析</strong>
                <span class="muted">正在汇总工时、合同阶段和收付款数据</span>
              </div>
              <div v-else-if="projectAnalysis" class="project-analysis-page">
                <section class="project-analysis-kpis">
                  <div><span>收入合同</span><strong>{{ moneyText(projectAnalysis.kpis.contract_income) }}</strong><small>已收 {{ moneyText(projectAnalysis.kpis.received) }}</small></div>
                  <div><span>支出合同</span><strong>{{ moneyText(projectAnalysis.kpis.contract_expense) }}</strong><small>已付 {{ moneyText(projectAnalysis.kpis.paid) }}</small></div>
                  <div><span>总成本</span><strong>{{ moneyText(projectAnalysis.cost.total_cost) }}</strong><small>人员 {{ moneyText(projectAnalysis.cost.personnel_cost) }} · 合同 {{ moneyText(projectAnalysis.cost.contract_cost) }}</small></div>
                  <div><span>毛利 / 毛利率</span><strong :class="projectAnalysis.kpis.gross_profit >= 0 ? 'positive-number' : 'negative-number'">{{ moneyText(projectAnalysis.kpis.gross_profit) }}</strong><small>{{ projectAnalysis.kpis.received > 0 ? formatProjectDays(projectAnalysis.kpis.gross_profit / projectAnalysis.kpis.received * 100) + '%' : '暂无收入基准' }} · 现金口径</small></div>
                  <div><span>未完成预警</span><strong class="negative-number">{{ projectAnalysis.warnings.length }}</strong><small>严重 {{ projectAnalysis.warnings.filter((item) => item.level === 'CRITICAL').length }} · 预警 {{ projectAnalysis.warnings.filter((item) => item.level === 'WARNING').length }}</small></div>
                </section>

                <div class="project-analysis-grid">
                  <section class="card project-analysis-card">
                    <div class="section-head"><div><h2>成本组成与预算执行</h2><p class="muted">已审批工时和已确认付款才计入实际成本</p></div><span class="muted">更新于 {{ projectAnalysis.as_of }}</span></div>
                    <div class="project-analysis-body">
                      <div class="analysis-cost-summary"><div><span>成本预算</span><strong>{{ moneyText(projectAnalysis.cost.budget_cost) }}</strong></div><div><span>{{ projectAnalysis.cost.remaining_cost >= 0 ? '预算剩余' : '预算超支' }}</span><strong :class="projectAnalysis.cost.remaining_cost >= 0 ? 'positive-number' : 'negative-number'">{{ moneyText(Math.abs(projectAnalysis.cost.remaining_cost)) }}</strong></div><div><span>总成本使用率</span><strong :class="(projectAnalysis.cost.cost_usage_rate || 0) >= 80 ? 'warning-number' : ''">{{ projectAnalysis.cost.cost_usage_rate === null ? '未设置预算' : formatProjectDays(projectAnalysis.cost.cost_usage_rate) + '%' }}</strong></div></div>
                      <div class="analysis-composition"><div class="analysis-subhead"><span>成本构成</span><span class="analysis-legend"><i class="personnel"></i>人员成本 <i class="contract"></i>合同成本</span></div><div class="analysis-composition-track"><i class="personnel" :style="{ width: analysisCostCompositionWidth(projectAnalysis.cost.personnel_cost) }"></i><i class="contract" :style="{ width: analysisCostCompositionWidth(projectAnalysis.cost.contract_cost) }"></i></div><div class="analysis-composition-values"><span><strong>{{ moneyText(projectAnalysis.cost.personnel_cost) }}</strong><small>人员成本 · {{ projectAnalysis.cost.total_cost ? formatProjectDays(projectAnalysis.cost.personnel_cost / projectAnalysis.cost.total_cost * 100) : '0.0' }}%</small></span><span><strong>{{ moneyText(projectAnalysis.cost.contract_cost) }}</strong><small>合同成本 · {{ projectAnalysis.cost.total_cost ? formatProjectDays(projectAnalysis.cost.contract_cost / projectAnalysis.cost.total_cost * 100) : '0.0' }}%</small></span></div></div>
                      <div class="analysis-budget-metrics"><div><div class="analysis-metric-line"><span>人天执行率</span><strong>{{ selectedManagedProject.completion_rate === null ? '未设置预算' : formatProjectDays(selectedManagedProject.completion_rate) + '%' }}</strong></div><div class="analysis-progress"><i :style="{ width: `${Math.min(100, Math.max(0, selectedManagedProject.completion_rate || 0))}%` }"></i></div><small>{{ formatProjectDays(selectedManagedProject.actual_days) }} / {{ formatProjectDays(selectedManagedProject.budget_days) }} 天 · 剩余 {{ formatProjectDays(selectedManagedProject.remaining_days) }} 天</small></div><div><div class="analysis-metric-line"><span>人员成本使用率</span><strong>{{ projectAnalysis.cost.personnel_cost_usage_rate === null ? '暂无成本基准' : formatProjectDays(projectAnalysis.cost.personnel_cost_usage_rate) + '%' }}</strong></div><div class="analysis-progress info"><i :style="{ width: `${Math.min(100, Math.max(0, projectAnalysis.cost.personnel_cost_usage_rate || 0))}%` }"></i></div><small>人员成本基线 {{ moneyText(projectAnalysis.cost.personnel_cost_budget_base) }} · 加权单价</small></div></div>
                      <div class="analysis-trend"><div class="analysis-subhead"><span>近 6 个月成本趋势</span><span class="analysis-legend"><i class="personnel"></i>人员 <i class="contract"></i>合同</span></div><div class="analysis-trend-chart"><div v-for="item in projectAnalysis.cost.monthly_trend" :key="item.month" class="analysis-trend-month"><div class="analysis-trend-stack"><i class="personnel" :style="{ height: analysisTrendHeight(item.personnel_cost) }"></i><i class="contract" :style="{ height: analysisTrendHeight(item.contract_cost) }"></i></div><small>{{ item.month.slice(5) }}月</small></div></div></div>
                    </div>
                  </section>

                  <section class="card project-analysis-card project-closeout-card">
                    <div class="section-head"><div><h2>结项资金风险</h2><p class="muted">按计划结项日期拆分结项前后风险</p></div><span class="tag" :class="analysisStatusClass(projectAnalysis.closeout.status)">{{ analysisCloseoutLabel(projectAnalysis.closeout.status) }}</span></div>
                    <div class="project-analysis-body"><div class="analysis-closeout-banner"><div class="analysis-closeout-days"><strong>{{ projectAnalysis.closeout.days_to_close === null ? '--' : Math.abs(projectAnalysis.closeout.days_to_close) }}</strong><span>{{ projectAnalysis.closeout.days_to_close !== null && projectAnalysis.closeout.days_to_close < 0 ? '天已过' : '天' }}</span></div><div><strong>{{ projectAnalysis.closeout.days_to_close === null ? '尚未设置计划结项日期' : projectAnalysis.closeout.days_to_close < 0 ? '项目已超过计划结项日期' : projectAnalysis.closeout.days_to_close <= 7 ? '项目即将结项' : '项目进入结项准备窗口' }}</strong><p>{{ projectAnalysis.closeout.planned_end_date || '请补充项目计划结项日期' }}</p></div></div><div class="analysis-closeout-metrics"><div class="income"><span>结项前待收</span><strong>{{ moneyText(projectAnalysis.closeout.before_close_receivable) }}</strong><small>收入阶段未收</small></div><div class="expense"><span>结项前待付</span><strong>{{ moneyText(projectAnalysis.closeout.before_close_payable) }}</strong><small>支出阶段未付</small></div><div><span>结项后待收</span><strong>{{ moneyText(projectAnalysis.closeout.after_close_receivable) }}</strong><small>后续收入阶段</small></div><div><span>结项后待付</span><strong>{{ moneyText(projectAnalysis.closeout.after_close_payable) }}</strong><small>后续支出阶段</small></div></div><div class="analysis-closeout-note"><span class="status-marker" :class="projectAnalysis.closeout.status === 'NORMAL' ? 'success' : 'danger'"></span><div><strong>{{ projectAnalysis.closeout.status === 'NORMAL' ? '结项资金计划正常' : '结项资金未闭合' }}</strong><p>未排期待收 {{ moneyText(projectAnalysis.closeout.unscheduled_receivable) }} · 未排期待付 {{ moneyText(projectAnalysis.closeout.unscheduled_payable) }}</p></div></div></div>
                  </section>
                </div>

                <section class="card project-analysis-card project-settlement-card"><div class="section-head"><div><h2>合同阶段收付款分析</h2><p class="muted">阶段结算率和收付款单笔数直接展示，未审批单据不计入已收已付</p></div><div class="analysis-settlement-summary"><span>待审批收款 <strong>{{ moneyText(projectAnalysis.settlement.pending_approval_receipt_amount) }}</strong></span><span>待审批付款 <strong>{{ moneyText(projectAnalysis.settlement.pending_approval_payment_amount) }}</strong></span></div></div><div class="analysis-settlement-tabs"><button :class="{ active: analysisSettlementTab === 'income' }" @click="analysisSettlementTab = 'income'">收入合同 <span>{{ projectAnalysis.settlement.income_contracts.length }}</span></button><button :class="{ active: analysisSettlementTab === 'expense' }" @click="analysisSettlementTab = 'expense'">支出合同 <span>{{ projectAnalysis.settlement.expense_contracts.length }}</span></button></div><div v-if="!analysisContracts.length" class="project-analysis-empty">当前项目暂无{{ analysisSettlementTab === 'income' ? '收入' : '支出' }}合同</div><div v-for="contract in analysisContracts" :key="contract.id" class="analysis-contract-block"><div class="analysis-contract-summary"><div><strong>{{ contract.name }}</strong><small>{{ contract.contract_no }} · {{ contract.counterparty_name }}</small></div><div><strong>{{ moneyText(contract.amount) }}</strong><small>已{{ analysisSettlementTab === 'income' ? '收' : '付' }} {{ moneyText(contract.settled_amount) }} · {{ contract.settlement_rate === null ? '暂无进度' : formatProjectDays(contract.settlement_rate) + '%' }}</small></div></div><div class="analysis-stage-head"><span>合同阶段</span><span>计划金额</span><span>已{{ analysisSettlementTab === 'income' ? '收' : '付' }}</span><span>未{{ analysisSettlementTab === 'income' ? '收' : '付' }}</span><span>结算率</span><span>{{ analysisSettlementTab === 'income' ? '收款' : '付款' }}单</span><span>状态</span></div><div v-for="stage in contract.stages" :key="stage.id" class="analysis-stage-block"><div class="analysis-stage-row"><div class="analysis-stage-name"><strong>{{ stage.name }}</strong><small>{{ stage.planned_date || '未排期' }} · {{ stage.days_to_due === null ? '暂无计划日期' : stage.days_to_due < 0 ? '逾期 ' + Math.abs(stage.days_to_due) + ' 天' : '距到期 ' + stage.days_to_due + ' 天' }}</small></div><strong class="analysis-stage-amount analysis-stage-planned">{{ moneyText(stage.planned_amount) }}</strong><span class="analysis-stage-amount analysis-stage-settled">{{ moneyText(stage.settled_amount) }}</span><strong class="analysis-stage-amount analysis-stage-remaining" :class="stage.warning_level === 'CRITICAL' ? 'negative-number' : stage.warning_level === 'WARNING' ? 'warning-number' : ''">{{ moneyText(stage.remaining_amount) }}</strong><span class="analysis-stage-amount analysis-stage-rate">{{ stage.settlement_rate === null ? '暂无' : formatProjectDays(stage.settlement_rate) + '%' }}</span><span class="analysis-stage-amount analysis-stage-docs">{{ stage.settled_document_count }} 笔</span><span class="analysis-stage-status"><span class="tag" :class="analysisStatusClass(stage.status)">{{ analysisStatusLabel(stage.status) }}</span></span></div></div></div></section>

                <section class="card project-analysis-card project-warning-card"><div class="section-head"><div><h2>风险与待处理事项</h2><p class="muted">按严重程度排序，点击处理按钮定位来源</p></div><span class="muted">共 {{ projectAnalysis.warnings.length }} 项</span></div><div v-if="!projectAnalysis.warnings.length" class="project-analysis-empty">当前项目暂无风险事项</div><div v-else class="analysis-warning-list"><div v-for="(warning, index) in projectAnalysis.warnings" :key="`${warning.warning_type}-${warning.source_id || index}`" class="analysis-warning-row"><span class="analysis-warning-icon" :class="analysisWarningClass(warning.level)">{{ warning.level === 'CRITICAL' ? '!' : warning.level === 'WARNING' ? '△' : 'i' }}</span><div><strong>{{ warning.title }}</strong><p>{{ warning.detail }}</p></div><button class="secondary compact-button" @click="focusProjectAnalysisWarning(warning)">{{ analysisWarningLabel(warning.level) === '严重' ? '处理' : '查看' }}</button></div></div></section>
              </div>
              <div v-else class="card project-analysis-state error-state"><strong>项目经营分析加载失败</strong><span class="muted">{{ projectAnalysisError || '暂时无法获取分析数据' }}</span><button class="secondary" @click="refreshProjectFinance">重新加载</button></div>
            </template>

            <section v-else-if="projectDetailTab === 'info'" class="card project-info-card project-tab-panel">
              <div class="section-head">
                <div>
                  <h2>基本信息</h2>
                  <p class="muted">项目主数据与工时填报开关</p>
                </div>
                <button class="secondary" @click="editProject(selectedManagedProject)">编辑信息</button>
              </div>
              <dl class="project-info-list">
                <div><dt>项目编码</dt><dd>{{ selectedManagedProject.code }}</dd></div>
                <div><dt>项目名称</dt><dd>{{ selectedManagedProject.name }}</dd></div>
                <div><dt>项目类型</dt><dd>{{ optionLabel("project_type", selectedManagedProject.project_type) }}</dd></div>
                <div><dt>项目状态</dt><dd>{{ optionLabel("project_status", selectedManagedProject.status) }}</dd></div>
                <div><dt>所属部门</dt><dd>{{ selectedManagedProject.department_path }}</dd></div>
                <div><dt>客户</dt><dd>{{ selectedManagedProject.customer_name || "未关联" }}</dd></div>
                <div><dt>开始日期</dt><dd>{{ selectedManagedProject.start_date || "未设置" }}</dd></div>
                <div><dt>计划结束</dt><dd>{{ selectedManagedProject.planned_end_date || "未设置" }}</dd></div>
                <div><dt>工时填报</dt><dd>{{ selectedManagedProject.allow_worklog ? "允许" : "关闭" }}</dd></div>
                <div class="wide"><dt>项目说明</dt><dd>{{ selectedManagedProject.description || "暂无项目说明" }}</dd></div>
              </dl>
            </section>

            <section v-else-if="projectDetailTab === 'team'" class="card project-tab-panel">
              <div class="section-head">
                <div>
                  <h2>人员与工时</h2>
                  <p class="muted">审批链来自项目配置，工时明细按已审批口径汇总</p>
                </div>
                <button class="secondary" @click="editProject(selectedManagedProject)">编辑人员配置</button>
              </div>
              <dl class="project-info-list project-team-list">
                <div><dt>项目负责人</dt><dd>{{ selectedManagedProject.owner_name }}</dd></div>
                <div><dt>项目审批人</dt><dd>{{ selectedManagedProject.approver_name || "未配置" }}</dd></div>
                <div><dt>上级领导</dt><dd>{{ selectedManagedProject.leader_name || "未配置" }}</dd></div>
                <div><dt>已发生人天</dt><dd>{{ formatProjectDays(selectedManagedProject.actual_days) }} 天</dd></div>
              </dl>
              <div class="project-tab-subhead">
                <strong>项目工时明细</strong>
                <span>{{ projectDetailWorklogs.length }} 条记录</span>
              </div>
              <div v-if="!projectDetailWorklogs.length" class="empty">该项目暂无工时记录。</div>
              <div v-else class="table-wrap">
                <table class="v3-ops-table">
                  <thead>
                    <tr>
                      <th>填报人</th>
                      <th>日期</th>
                      <th>阶段</th>
                      <th>天数</th>
                      <th>状态</th>
                      <th>工作内容</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in projectDetailWorklogs.slice(0, 50)" :key="item.id">
                      <td>{{ item.user_name_snapshot || "—" }}</td>
                      <td>{{ item.start_date }}</td>
                      <td>{{ item.stage }}</td>
                      <td>{{ item.quantity }} 天</td>
                      <td><span class="tag" :class="statusClass(item.status)">{{ statusLabel(item.status) }}</span></td>
                      <td>{{ item.description }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section v-else-if="projectDetailTab === 'budget'" class="card project-tab-panel">
              <div class="section-head">
                <div>
                  <h2>预算</h2>
                  <p class="muted">人天预算和成本预算由项目管理维护</p>
                </div>
                <button class="secondary" @click="editProject(selectedManagedProject)">编辑预算</button>
              </div>
              <div class="project-kpi-row project-budget-kpis">
                <section><span>预算人天</span><strong>{{ formatProjectDays(selectedManagedProject.budget_days) }}</strong><small>天</small></section>
                <section><span>已发生人天</span><strong>{{ formatProjectDays(selectedManagedProject.actual_days) }}</strong><small>天，仅已审批</small></section>
                <section><span>成本预算</span><strong>{{ moneyText(selectedManagedProject.budget_cost) }}</strong><small>项目总预算</small></section>
                <section><span>已发生人员成本</span><strong>{{ moneyText(selectedManagedProject.personnel_cost) }}</strong><small>按审批时单价快照</small></section>
                <section><span>已发生合同成本</span><strong>{{ moneyText(selectedManagedProject.actual_contract_cost) }}</strong><small>已审批付款，扣除冲销</small></section>
                <section :class="{ 'budget-remaining': true, negative: selectedManagedProject.remaining_cost < 0 }"><span>预算剩余</span><strong>{{ moneyText(selectedManagedProject.remaining_cost) }}</strong><small>预算减去实际总成本</small></section>
              </div>
              <div class="project-progress-block">
                <div><span>人天执行率</span><strong>{{ selectedManagedProject.completion_rate === null ? "未设置预算" : formatProjectDays(selectedManagedProject.completion_rate) + "%" }}</strong></div>
                <div class="project-progress-track"><i :style="{ width: `${Math.min(100, Math.max(0, selectedManagedProject.completion_rate || 0))}%` }"></i></div>
              </div>
              <div class="project-progress-block cost">
                <div><span>成本执行率</span><strong>{{ selectedManagedProject.cost_usage_rate === null ? "未设置预算" : formatProjectDays(selectedManagedProject.cost_usage_rate) + "%" }}</strong></div>
                <div class="project-progress-track"><i :style="{ width: `${Math.min(100, Math.max(0, selectedManagedProject.cost_usage_rate || 0))}%` }"></i></div>
              </div>
            </section>

            <section v-else-if="projectDetailTab === 'finance'" class="card project-tab-panel">
              <div class="section-head">
                <div>
                  <h2>合同与资金</h2>
                  <p class="muted">收入合同、支出合同及对应收付款汇总</p>
                </div>
                <div class="actions">
                  <button v-if="canManage('contracts')" class="secondary" @click="go('projectContracts')">合同管理</button>
                  <button v-if="canManage('receipts')" class="secondary" @click="go('projectReceipts')">收款</button>
                  <button v-if="canManage('payments')" class="secondary" @click="go('projectPayments')">付款</button>
                </div>
              </div>
              <div class="project-money-grid">
                <div><span>合同收入</span><strong>{{ moneyText(projectFinance?.contract_income) }}</strong></div>
                <div><span>合同成本</span><strong>{{ moneyText(projectFinance?.contract_expense) }}</strong></div>
                <div><span>已收 / 应收</span><strong>{{ moneyText(projectFinance?.received) }} / {{ moneyText(projectFinance?.receivable) }}</strong></div>
                <div><span>已付 / 应付</span><strong>{{ moneyText(projectFinance?.paid) }} / {{ moneyText(projectFinance?.payable) }}</strong></div>
                <div><span>毛利</span><strong>{{ moneyText(projectFinance?.gross_profit) }}</strong></div>
              </div>
              <div v-if="!selectedProjectContracts.length" class="empty">该项目暂无合同。</div>
              <template v-else>
                <section class="project-contract-group">
                  <div class="project-tab-subhead"><strong>收入合同</strong><span>{{ selectedProjectIncomeContracts.length }} 份</span></div>
                  <div v-if="!selectedProjectIncomeContracts.length" class="empty">该项目暂无收入合同。</div>
                  <div v-else class="table-wrap">
                    <table class="v3-ops-table project-contract-table">
                      <thead><tr><th>合同</th><th>客户</th><th>金额</th><th>已确认</th><th>状态</th></tr></thead>
                      <tbody>
                        <tr v-for="item in selectedProjectIncomeContracts" :key="item.id">
                          <td><button class="text-button contract-name-link" @click="openContractDetail(item)"><strong>{{ item.name }}</strong></button><small>{{ item.contract_no }}</small></td>
                          <td>{{ item.counterparty_name }}</td>
                          <td>{{ moneyText(item.amount) }}</td>
                          <td>{{ moneyText(item.settled_amount) }}</td>
                          <td>{{ contractStatusLabel(item.status) }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </section>
                <section class="project-contract-group">
                  <div class="project-tab-subhead"><strong>支出合同</strong><span>{{ selectedProjectExpenseContracts.length }} 份</span></div>
                  <div v-if="!selectedProjectExpenseContracts.length" class="empty">该项目暂无支出合同。</div>
                  <div v-else class="table-wrap">
                    <table class="v3-ops-table project-contract-table">
                      <thead><tr><th>合同</th><th>供应商</th><th>金额</th><th>已确认</th><th>状态</th></tr></thead>
                      <tbody>
                        <tr v-for="item in selectedProjectExpenseContracts" :key="item.id">
                          <td><button class="text-button contract-name-link" @click="openContractDetail(item)"><strong>{{ item.name }}</strong></button><small>{{ item.contract_no }}</small></td>
                          <td>{{ item.counterparty_name }}</td>
                          <td>{{ moneyText(item.amount) }}</td>
                          <td>{{ moneyText(item.settled_amount) }}</td>
                          <td>{{ contractStatusLabel(item.status) }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </section>
              </template>
            </section>

            <section v-else-if="projectDetailTab === 'audit'" class="card project-tab-panel">
              <div class="section-head">
                <div>
                  <h2>操作记录</h2>
                  <p class="muted">项目、合同、收付款和预算变更审计</p>
                </div>
                <button class="secondary" @click="loadProjectAudit">刷新</button>
              </div>
              <div v-if="!projectAuditLogs.length" class="empty">暂无操作记录。</div>
              <div v-else class="audit-list">
                <div v-for="entry in projectAuditLogs" :key="entry.id" class="audit-row">
                  <div>
                    <strong>{{ auditActionLabel(entry.action) }}</strong>
                    <small>{{ entry.object_type }} #{{ entry.object_id }} · {{ entry.actor_name }}</small>
                  </div>
                  <div>
                    <span v-if="entry.old_status || entry.new_status" class="audit-status">{{ entry.old_status || "—" }} → {{ entry.new_status || "—" }}</span>
                    <small>{{ formatDateTime(entry.created_at) }}</small>
                  </div>
                  <p v-if="entry.comment">{{ entry.comment }}</p>
                </div>
              </div>
            </section>
          </template>
          <section v-else class="card empty">
            <h2>未选择项目</h2>
            <button class="primary" @click="go('projects')">
              返回项目列表
            </button>
          </section>
        </section>

        <section
          v-else-if="page === 'projectContracts'"
          class="page-view v3-ops-page"
        >
          <div class="page-head">
            <div>
              <div class="eyebrow">PROJECT / CONTRACTS</div>
              <h1>项目合同</h1>
              <p class="muted">收入合同和支出合同分开维护，合同阶段用于收付款计划。</p>
            </div>
            <div class="actions">
              <button class="primary" @click="openContractForm">＋ 新增合同</button>
            </div>
          </div>
          <div class="v3-tabs" role="tablist" aria-label="合同类型">
            <button
              type="button"
              :class="{ active: contractTab === 'INCOME' }"
              @click="contractTab = 'INCOME'; contractFilterType = ''; refreshContracts()"
            >
              收入合同
            </button>
            <button
              type="button"
              :class="{ active: contractTab === 'EXPENSE' }"
              @click="contractTab = 'EXPENSE'; contractFilterType = ''; refreshContracts()"
            >
              支出合同
            </button>
          </div>
          <section class="card v3-filter-card">
            <div class="v3-filters">
              <label>
                项目
                <select v-model.number="contractFilterProject">
                  <option :value="0">全部项目</option>
                  <option v-for="item in managedProjects" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </option>
                </select>
              </label>
              <label>
                合同类型
                <select v-model="contractFilterType">
                  <option value="">全部类型</option>
                  <option value="INCOME">收入合同</option>
                  <option value="EXPENSE">支出合同</option>
                </select>
              </label>
              <label>
                往来单位
                <select v-model.number="contractFilterCounterparty">
                  <option :value="0">全部单位</option>
                  <option v-for="item in customers" :key="'c' + item.id" :value="item.id">
                    {{ item.name }}
                  </option>
                  <option v-for="item in suppliers" :key="'s' + item.id" :value="item.id">
                    {{ item.name }}
                  </option>
                </select>
              </label>
              <div class="v3-filter-actions">
                <button class="primary" @click="refreshContracts">查询</button>
              </div>
            </div>
          </section>
          <section class="card">
            <div class="section-head">
              <div>
                <h2>合同列表</h2>
                <p class="muted">共 {{ projectContracts.length }} 份合同</p>
              </div>
            </div>
            <div v-if="contractsLoading" class="empty">正在加载合同…</div>
            <div v-else-if="!projectContracts.length" class="empty">暂无合同，请先新增。</div>
            <div v-else class="table-wrap">
              <table class="v3-ops-table">
                <thead>
                  <tr>
                    <th>合同</th>
                    <th>类型</th>
                    <th>项目</th>
                    <th>往来单位</th>
                    <th>合同金额</th>
                    <th>已确认</th>
                    <th>阶段</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in projectContracts" :key="item.id">
                    <td>
                      <button class="text-button contract-name-link" @click="openContractDetail(item)"><strong>{{ item.name }}</strong></button>
                      <small>{{ item.contract_no }}</small>
                    </td>
                    <td>{{ contractTypeLabel(item.contract_type) }}</td>
                    <td>{{ item.project_name }}</td>
                    <td>{{ item.counterparty_name }}</td>
                    <td>{{ moneyText(item.amount) }}</td>
                    <td>{{ moneyText(item.settled_amount) }}</td>
                    <td>{{ item.stage_count }} 个阶段</td>
                    <td>{{ contractStatusLabel(item.status) }}</td>
                    <td>
                      <div class="table-actions">
                        <button class="text-button" @click="openContractStages(item)">查看阶段</button>
                        <button class="text-button" @click="editContract(item)">编辑</button>
                        <button v-if="item.status === 'DRAFT'" class="text-button" @click="activateContract(item)">激活</button>
                        <button class="text-button danger-text" @click="deleteContract(item)">删除</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <div v-if="contractFormOpen" class="modal-backdrop">
            <section class="modal-card v3-modal" role="dialog" aria-modal="true">
              <div class="modal-head">
                <div>
                  <div class="eyebrow">CONTRACT FORM</div>
                  <h2>{{ editingContractId ? "编辑合同" : "新增合同" }}</h2>
                </div>
                <button class="modal-close" aria-label="关闭弹窗" @click="resetContractForm">×</button>
              </div>
              <div class="form-grid">
                <label>合同编号<input v-model.trim="contractForm.contract_no" placeholder="如 HT-2026-001" /></label>
                <label>合同名称<input v-model.trim="contractForm.name" placeholder="请输入合同名称" /></label>
                <label>
                  所属项目
                  <select v-model.number="contractForm.project_id">
                    <option :value="0" disabled>请选择项目</option>
                    <option v-for="item in managedProjects" :key="item.id" :value="item.id">
                      {{ item.name }}
                    </option>
                  </select>
                </label>
                <label>
                  合同类型
                  <select v-model="contractForm.contract_type">
                    <option value="INCOME">收入合同</option>
                    <option value="EXPENSE">支出合同</option>
                  </select>
                </label>
                <label>
                  往来单位类型
                  <select v-model="contractForm.counterparty_type" @change="contractForm.counterparty_id = 0">
                    <option value="CUSTOMER">客户</option>
                    <option value="SUPPLIER">供应商</option>
                  </select>
                </label>
                <label>
                  往来单位
                  <select v-model.number="contractForm.counterparty_id">
                    <option :value="0" disabled>请选择往来单位</option>
                    <option v-for="item in contractForm.counterparty_type === 'CUSTOMER' ? customers : suppliers" :key="item.id" :value="item.id">
                      {{ item.name }}
                    </option>
                  </select>
                </label>
                <label>合同金额<input v-model.number="contractForm.amount" type="number" min="0" step="0.01" /></label>
                <label>签订日期<input v-model="contractForm.sign_date" type="date" /></label>
                <label>开始日期<input v-model="contractForm.start_date" type="date" /></label>
                <label>结束日期<input v-model="contractForm.end_date" type="date" /></label>
                <label>
                  状态
                  <select v-model="contractForm.status">
                    <option value="ACTIVE">执行中</option>
                    <option value="COMPLETED">已完成</option>
                    <option value="DRAFT">草稿</option>
                  </select>
                </label>
                <label class="span-2">合同说明<textarea v-model.trim="contractForm.description" rows="3" placeholder="付款或交付约定"></textarea></label>
              </div>
              <section class="contract-attachment-editor">
                <div class="section-head"><div><h3>合同附件</h3><p class="muted">先保存合同后上传，单个文件最大 50MB</p></div><label v-if="editingContractId" class="secondary file-upload-button"><input type="file" accept=".doc,.docx,.xls,.xlsx,.ppt,.pptx,.pdf,.png,.jpg,.jpeg,.webp" :disabled="contractAttachmentUploading" @change="uploadContractAttachment" />{{ contractAttachmentUploading ? '上传中…' : '＋ 上传附件' }}</label></div>
                <div v-if="!editingContractId" class="attachment-save-hint">保存合同后可继续上传附件</div>
                <div v-else-if="contractAttachmentsLoading" class="attachment-save-hint">正在加载附件…</div>
                <div v-else-if="!contractAttachments.length" class="attachment-save-hint">暂无附件，可点击右侧按钮上传</div>
                <div v-else class="contract-attachment-list compact-attachment-list">
                  <div v-for="attachment in contractAttachments" :key="attachment.id" class="contract-attachment-row">
                    <div class="attachment-file-icon" :class="`attachment-${attachment.preview_kind}`">{{ attachmentKindLabel(attachment.preview_kind) }}</div>
                    <div class="attachment-file-main"><strong>{{ attachment.file_name }}</strong><small>{{ attachmentSizeText(attachment.file_size) }} · {{ formatDateTime(attachment.created_at) }}</small></div>
                    <div class="table-actions"><button v-if="attachment.can_preview" class="text-button" @click="previewContractAttachment(attachment)">预览</button><button class="text-button" @click="downloadContractAttachment(attachment)">下载</button><button class="text-button danger-text" @click="deleteContractAttachment(attachment)">删除</button></div>
                  </div>
                </div>
              </section>
              <div class="form-footer">
                <button class="secondary" @click="resetContractForm">取消</button>
                <button class="primary" @click="saveContract">保存合同</button>
              </div>
            </section>
          </div>
          <div v-if="stageListOpen" class="modal-backdrop">
            <section class="modal-card v3-modal" role="dialog" aria-modal="true">
              <div class="modal-head">
                <div>
                  <div class="eyebrow">CONTRACT STAGES</div>
                  <h2>阶段列表</h2>
                </div>
                <button class="modal-close" aria-label="关闭弹窗" @click="stageListOpen = false">×</button>
              </div>
              <div class="stage-inline-list">
                <div v-if="contractStagesLoading" class="empty">正在加载阶段…</div>
                <div v-else-if="!projectContractStages.length" class="empty">暂无阶段，请点击下方“新增阶段”。</div>
                <div v-for="stage in projectContractStages" :key="stage.id" class="stage-inline-row">
                  <div>
                    <strong>{{ stage.name }}</strong>
                    <small>{{ stage.planned_date || "未设置计划日期" }} · {{ contractTypeLabel(contractById(stage.contract_id)?.contract_type || "") }}</small>
                  </div>
                  <div>
                    <b>{{ moneyText(stage.amount) }}</b>
                    <span class="tag" :class="stage.status === 'DONE' ? 'success' : stage.status === 'PARTIAL' ? 'warning' : 'neutral'">
                      {{ stage.status === "DONE" ? "已完成" : stage.status === "PARTIAL" ? "部分完成" : "待执行" }}
                    </span>
                  </div>
                  <div class="table-actions">
                    <button class="text-button" @click="openStageForm(stage.contract_id, stage)">编辑</button>
                    <button class="text-button danger-text" @click="deleteStage(stage)">删除</button>
                  </div>
                </div>
                <button class="secondary stage-add" @click="openStageForm(stageContractId)">
                  ＋ 新增阶段
                </button>
              </div>
            </section>
          </div>
          <div v-if="stageFormOpen" class="modal-backdrop">
            <section class="modal-card v3-modal stage-form-modal" role="dialog" aria-modal="true">
              <div class="modal-head">
                <div>
                  <div class="eyebrow">CONTRACT STAGE FORM</div>
                  <h2>{{ editingStageId ? "编辑合同阶段" : "新增合同阶段" }}</h2>
                </div>
                <button class="modal-close" aria-label="关闭弹窗" @click="stageFormOpen = false">×</button>
              </div>
              <div class="form-grid">
                <label>阶段名称<input v-model.trim="stageForm.name" placeholder="如 设备到货款" /></label>
                <label>阶段金额<input v-model.number="stageForm.amount" type="number" min="0" step="0.01" /></label>
                <label>计划日期<input v-model="stageForm.planned_date" type="date" /></label>
                <label>提前提醒<input v-model.number="stageForm.remind_days_before" type="number" min="0" max="365" /></label>
                <label>排序<input v-model.number="stageForm.sort_order" type="number" min="0" /></label>
                <label class="checkbox-field"><input v-model="stageForm.reminder_paused" type="checkbox" /> 暂停提醒</label>
              </div>
              <div class="form-footer">
                <button class="secondary" @click="stageFormOpen = false">取消</button>
                <button class="primary" @click="saveStage">保存阶段</button>
              </div>
            </section>
          </div>
        </section>

        <section v-else-if="page === 'contractDetail'" class="page-view v3-ops-page contract-detail-page">
          <template v-if="selectedContract">
            <div class="page-head contract-detail-head">
              <div>
                <button class="text-button contract-back" @click="closeContractDetail">← 返回合同列表</button>
                <div class="eyebrow">PROJECT / CONTRACT DETAIL</div>
                <h1>{{ selectedContract.name }}</h1>
                <p class="muted">{{ selectedContract.contract_no }} · {{ contractTypeLabel(selectedContract.contract_type) }} · {{ selectedContract.project_name }}</p>
              </div>
              <div class="actions">
                <button v-if="canManage('contracts')" class="secondary" @click="editContract(selectedContract)">编辑合同</button>
                <button v-if="canManage('contracts')" class="primary" @click="openStageForm(selectedContract.id)">＋ 新增阶段</button>
              </div>
            </div>
            <div v-if="contractDetailLoading" class="card contract-detail-state"><div class="loading-spinner"></div><strong>正在加载合同详情</strong></div>
            <div v-else-if="contractDetailError" class="card contract-detail-state error-state"><strong>合同详情加载失败</strong><span class="muted">{{ contractDetailError }}</span><button class="secondary" @click="openContractDetail(selectedContract)">重新加载</button></div>
            <template v-else>
              <section class="card contract-detail-summary">
                <div class="contract-detail-summary-primary"><span>合同金额</span><strong>{{ moneyText(selectedContract.amount) }}</strong><small>{{ selectedContract.contract_type === 'INCOME' ? '收入合同' : '支出合同' }}</small></div>
                <div><span>结算率</span><strong>{{ selectedContract.settlement_rate === null || selectedContract.settlement_rate === undefined ? '暂无' : formatProjectDays(selectedContract.settlement_rate) + '%' }}</strong><small>{{ selectedContract.settled_document_count || 0 }} 笔已确认{{ selectedContract.contract_type === 'INCOME' ? '收款' : '付款' }}</small></div>
                <div><span>{{ selectedContract.contract_type === 'INCOME' ? '已收' : '已付' }}</span><strong>{{ moneyText(selectedContract.settled_amount) }}</strong><small>已审批确认</small></div>
                <div><span>{{ selectedContract.contract_type === 'INCOME' ? '待收' : '待付' }}</span><strong :class="selectedContract.amount - selectedContract.settled_amount > 0 ? 'warning-number' : 'positive-number'">{{ moneyText(Math.max(selectedContract.amount - selectedContract.settled_amount, 0)) }}</strong><small>尚未确认</small></div>
                <div><span>阶段数</span><strong>{{ contractDetailStages.length }}</strong><small>已配置计划</small></div>
                <div><span>单据数</span><strong>{{ selectedContract.settled_document_count || 0 }}</strong><small>已确认{{ selectedContract.contract_type === 'INCOME' ? '收款' : '付款' }}</small></div>
              </section>
              <section class="card contract-detail-info">
                <div class="section-head"><div><h2>合同信息</h2><p class="muted">合同主数据和履约对象</p></div><span class="tag" :class="contractStatusClass(selectedContract.status)">{{ contractStatusLabel(selectedContract.status) }}</span></div>
                <div class="contract-info-grid">
                  <div><span>合同名称</span><strong>{{ selectedContract.name }}</strong></div>
                  <div><span>合同编号</span><strong>{{ selectedContract.contract_no }}</strong></div>
                  <div><span>所属项目</span><strong>{{ selectedContract.project_name }}</strong></div>
                  <div><span>{{ selectedContract.counterparty_type === 'CUSTOMER' ? '客户' : '供应商' }}</span><strong>{{ selectedContract.counterparty_name }}</strong></div>
                  <div><span>签订日期</span><strong>{{ selectedContract.sign_date || '未设置' }}</strong></div>
                  <div><span>履约期间</span><strong>{{ selectedContract.start_date || '未设置' }} 至 {{ selectedContract.end_date || '未设置' }}</strong></div>
                </div>
              </section>
              <section class="card contract-detail-stages">
                <div class="section-head"><div><h2>阶段详情</h2><p class="muted">收付款计划、结算进度和关联单据一览</p></div><span class="muted">共 {{ contractDetailStages.length }} 个阶段</span></div>
                <div v-if="!contractDetailStages.length" class="empty contract-detail-empty"><strong>暂无合同阶段</strong><span class="muted">点击右上角“新增阶段”建立收付款计划</span></div>
                <div v-else class="contract-detail-stage-list">
                  <div class="contract-detail-stage-head"><span>阶段</span><span>计划日期</span><span>计划金额</span><span>已{{ selectedContract.contract_type === 'INCOME' ? '收' : '付' }}</span><span>未{{ selectedContract.contract_type === 'INCOME' ? '收' : '付' }}</span><span>结算率</span><span>{{ selectedContract.contract_type === 'INCOME' ? '收款' : '付款' }}单</span><span>状态</span><span>操作</span></div>
                  <div v-for="stage in contractDetailStages" :key="stage.id" class="contract-detail-stage-row">
                    <div><strong>{{ stage.name }}</strong><small>第 {{ stage.sort_order + 1 }} 阶段 · 提前 {{ stage.remind_days_before || 0 }} 天提醒</small></div>
                    <span class="stage-cell-date">{{ stage.planned_date || '未排期' }}</span>
                    <strong class="stage-cell-planned">{{ moneyText(stage.amount) }}</strong>
                    <span class="stage-cell-settled">{{ moneyText(stage.settled_amount) }}</span>
                    <strong class="stage-cell-remaining" :class="(stage.remaining_amount || 0) > 0 ? 'warning-number' : 'positive-number'">{{ moneyText(stage.remaining_amount) }}</strong>
                    <span class="stage-cell-rate">{{ stage.settlement_rate === null || stage.settlement_rate === undefined ? '暂无' : formatProjectDays(stage.settlement_rate) + '%' }}</span>
                    <span class="stage-cell-docs">{{ stage.settled_document_count || 0 }} 笔</span>
                    <span class="stage-cell-status"><span class="tag" :class="stage.status === 'DONE' ? 'success' : stage.status === 'PARTIAL' ? 'warning' : stage.status === 'CANCELLED' ? 'danger' : 'neutral'">{{ stage.status === 'DONE' ? '已完成' : stage.status === 'PARTIAL' ? '部分完成' : stage.status === 'CANCELLED' ? '已取消' : '待执行' }}</span></span>
                    <div class="table-actions"><button class="text-button" @click="openStageForm(selectedContract.id, stage)">编辑</button><button class="text-button danger-text" @click="deleteStage(stage)">删除</button></div>
                  </div>
                </div>
              </section>
              <section v-if="selectedContract.description" class="card contract-detail-description"><div class="section-head"><h2>合同说明</h2></div><p>{{ selectedContract.description }}</p></section>
              <section class="card contract-attachments-card">
                <div class="section-head">
                  <div><h2>合同附件</h2><p class="muted">支持 Word、Excel、PPT、PDF 和图片</p></div>
                  <span class="muted">{{ contractAttachments.length }} 个文件</span>
                </div>
                <div v-if="contractAttachmentsLoading" class="empty attachment-empty">正在加载附件…</div>
                <div v-else-if="!contractAttachments.length" class="empty attachment-empty">暂无合同附件</div>
                <div v-else class="contract-attachment-list">
                  <div v-for="attachment in contractAttachments" :key="attachment.id" class="contract-attachment-row">
                    <div class="attachment-file-icon" :class="`attachment-${attachment.preview_kind}`">{{ attachmentKindLabel(attachment.preview_kind) }}</div>
                    <div class="attachment-file-main"><strong>{{ attachment.file_name }}</strong><small>{{ attachmentSizeText(attachment.file_size) }} · {{ attachment.uploaded_by_name }} · {{ formatDateTime(attachment.created_at) }}</small></div>
                    <span class="tag neutral">{{ attachment.can_preview ? '可预览' : '仅下载' }}</span>
                    <div class="table-actions"><button v-if="attachment.can_preview" class="text-button" @click="previewContractAttachment(attachment)">预览</button><button class="text-button" @click="downloadContractAttachment(attachment)">下载</button><button v-if="canManage('contracts')" class="text-button danger-text" @click="deleteContractAttachment(attachment)">删除</button></div>
                  </div>
                </div>
              </section>
            </template>
          </template>
          <section v-else class="card empty"><h2>未选择合同</h2><button class="primary" @click="go('projectContracts')">返回合同列表</button></section>
          <div v-if="contractFormOpen" class="modal-backdrop">
            <section class="modal-card v3-modal" role="dialog" aria-modal="true">
              <div class="modal-head"><div><div class="eyebrow">CONTRACT FORM</div><h2>{{ editingContractId ? '编辑合同' : '新增合同' }}</h2></div><button class="modal-close" aria-label="关闭弹窗" @click="resetContractForm">×</button></div>
              <div class="form-grid">
                <label>合同编号<input v-model.trim="contractForm.contract_no" placeholder="如 HT-2026-001" /></label>
                <label>合同名称<input v-model.trim="contractForm.name" placeholder="请输入合同名称" /></label>
                <label>所属项目<select v-model.number="contractForm.project_id"><option :value="0" disabled>请选择项目</option><option v-for="item in managedProjects" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
                <label>合同类型<select v-model="contractForm.contract_type"><option value="INCOME">收入合同</option><option value="EXPENSE">支出合同</option></select></label>
                <label>往来单位类型<select v-model="contractForm.counterparty_type" @change="contractForm.counterparty_id = 0"><option value="CUSTOMER">客户</option><option value="SUPPLIER">供应商</option></select></label>
                <label>往来单位<select v-model.number="contractForm.counterparty_id"><option :value="0" disabled>请选择往来单位</option><option v-for="item in contractForm.counterparty_type === 'CUSTOMER' ? customers : suppliers" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
                <label>合同金额<input v-model.number="contractForm.amount" type="number" min="0" step="0.01" /></label>
                <label>签订日期<input v-model="contractForm.sign_date" type="date" /></label>
                <label>开始日期<input v-model="contractForm.start_date" type="date" /></label>
                <label>结束日期<input v-model="contractForm.end_date" type="date" /></label>
                <label>状态<select v-model="contractForm.status"><option value="ACTIVE">执行中</option><option value="COMPLETED">已完成</option><option value="DRAFT">草稿</option></select></label>
                <label class="span-2">合同说明<textarea v-model.trim="contractForm.description" rows="3" placeholder="付款或交付约定"></textarea></label>
              </div>
              <section class="contract-attachment-editor">
                <div class="section-head"><div><h3>合同附件</h3><p class="muted">先保存合同后上传，单个文件最大 50MB</p></div><label v-if="editingContractId" class="secondary file-upload-button"><input type="file" accept=".doc,.docx,.xls,.xlsx,.ppt,.pptx,.pdf,.png,.jpg,.jpeg,.webp" :disabled="contractAttachmentUploading" @change="uploadContractAttachment" />{{ contractAttachmentUploading ? '上传中…' : '＋ 上传附件' }}</label></div>
                <div v-if="!editingContractId" class="attachment-save-hint">保存合同后可继续上传附件</div>
                <div v-else-if="contractAttachmentsLoading" class="attachment-save-hint">正在加载附件…</div>
                <div v-else-if="!contractAttachments.length" class="attachment-save-hint">暂无附件，可点击右侧按钮上传</div>
                <div v-else class="contract-attachment-list compact-attachment-list">
                  <div v-for="attachment in contractAttachments" :key="attachment.id" class="contract-attachment-row">
                    <div class="attachment-file-icon" :class="`attachment-${attachment.preview_kind}`">{{ attachmentKindLabel(attachment.preview_kind) }}</div>
                    <div class="attachment-file-main"><strong>{{ attachment.file_name }}</strong><small>{{ attachmentSizeText(attachment.file_size) }} · {{ formatDateTime(attachment.created_at) }}</small></div>
                    <div class="table-actions"><button v-if="attachment.can_preview" class="text-button" @click="previewContractAttachment(attachment)">预览</button><button class="text-button" @click="downloadContractAttachment(attachment)">下载</button><button class="text-button danger-text" @click="deleteContractAttachment(attachment)">删除</button></div>
                  </div>
                </div>
              </section>
              <div class="form-footer"><button class="secondary" @click="resetContractForm">取消</button><button class="primary" @click="saveContract">保存合同</button></div>
            </section>
          </div>
          <div v-if="stageFormOpen" class="modal-backdrop">
            <section class="modal-card v3-modal stage-form-modal" role="dialog" aria-modal="true">
              <div class="modal-head"><div><div class="eyebrow">CONTRACT STAGE FORM</div><h2>{{ editingStageId ? '编辑合同阶段' : '新增合同阶段' }}</h2></div><button class="modal-close" aria-label="关闭弹窗" @click="stageFormOpen = false">×</button></div>
              <div class="form-grid"><label>阶段名称<input v-model.trim="stageForm.name" placeholder="如 设备到货款" /></label><label>阶段金额<input v-model.number="stageForm.amount" type="number" min="0" step="0.01" /></label><label>计划日期<input v-model="stageForm.planned_date" type="date" /></label><label>提前提醒<input v-model.number="stageForm.remind_days_before" type="number" min="0" max="365" /></label><label>排序<input v-model.number="stageForm.sort_order" type="number" min="0" /></label><label class="checkbox-field"><input v-model="stageForm.reminder_paused" type="checkbox" /> 暂停提醒</label></div>
              <div class="form-footer"><button class="secondary" @click="stageFormOpen = false">取消</button><button class="primary" @click="saveStage">保存阶段</button></div>
            </section>
          </div>
        </section>

        <section v-else-if="page === 'projectReceipts'" class="page-view v3-ops-page">
          <div class="page-head">
            <div>
              <div class="eyebrow">PROJECT / RECEIPTS</div>
              <h1>项目收款</h1>
              <p class="muted">收款单提交后由具备出纳审批权限的人员确认入账。</p>
            </div>
            <div class="actions">
              <button class="primary" @click="openReceiptForm()">＋ 新增收款单</button>
            </div>
          </div>
          <div class="v3-tabs" role="tablist" aria-label="收款单范围">
            <button type="button" :class="{ active: receiptTab === 'pending' }" @click="receiptTab = 'pending'">待我审批</button>
            <button type="button" :class="{ active: receiptTab === 'all' }" @click="receiptTab = 'all'">全部单据</button>
          </div>
          <section class="card v3-filter-card">
            <div class="v3-filters">
              <label>
                项目
                <select v-model.number="receiptFilterProject">
                  <option :value="0">全部项目</option>
                  <option v-for="item in managedProjects" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </option>
                </select>
              </label>
              <label>
                状态
                <select v-model="receiptFilterStatus">
                  <option value="">全部状态</option>
                  <option value="PENDING">待出纳审批</option>
                  <option value="APPROVED">已确认</option>
                  <option value="REJECTED">已驳回</option>
                  <option value="REVERSED">已冲销</option>
                </select>
              </label>
              <div class="v3-filter-actions">
                <button class="primary" @click="refreshReceipts">查询</button>
              </div>
            </div>
          </section>
          <section class="card">
            <div class="section-head">
              <div>
                <h2>收款单列表</h2>
                <p class="muted">共 {{ visibleReceipts.length }} 张收款单</p>
              </div>
            </div>
            <div v-if="receiptsLoading" class="empty">正在加载收款单…</div>
            <div v-else-if="!visibleReceipts.length" class="empty">当前范围暂无收款单。</div>
            <div v-else class="table-wrap">
              <table class="v3-ops-table">
                <thead>
                  <tr>
                    <th>收款单号</th>
                    <th>项目 / 合同</th>
                    <th>阶段</th>
                    <th>金额</th>
                    <th>收款日期</th>
                    <th>付款方</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in visibleReceipts" :key="item.id">
                    <td><button class="text-button" @click="openReceiptApproval(item)"><strong>{{ item.receipt_no }}</strong></button></td>
                    <td><strong>{{ item.project_name }}</strong><small>{{ item.contract_name }}</small></td>
                    <td>{{ item.stage_name || "未关联阶段" }}</td>
                    <td>{{ moneyText(item.amount) }}</td>
                    <td>{{ item.receipt_date }}</td>
                    <td>{{ item.payer_name }}</td>
                    <td><span class="tag" :class="cashStatusClass(item.status)">{{ cashStatusLabel(item.status) }}</span></td>
                    <td>
                      <div class="table-actions">
                        <button class="text-button" @click="openReceiptApproval(item)">查看</button>
                        <button v-if="item.status === 'PENDING' && canManage('cash_approval')" class="text-button" @click="approveReceipt(item)">通过</button>
                        <button v-if="item.status === 'PENDING' && canManage('cash_approval')" class="text-button danger-text" @click="rejectReceipt(item)">驳回</button>
                        <button v-if="item.status === 'APPROVED' && canManage('cash_approval')" class="text-button" @click="reverseReceipt(item)">冲销</button>
                        <button v-if="['DRAFT', 'REJECTED'].includes(item.status)" class="text-button" @click="openReceiptForm(item)">编辑</button>
                        <button v-if="['DRAFT', 'REJECTED'].includes(item.status)" class="text-button danger-text" @click="deleteReceipt(item)">删除</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <div v-if="receiptFormOpen" class="modal-backdrop">
            <section class="modal-card v3-modal" role="dialog" aria-modal="true">
              <div class="modal-head">
                <div>
                  <div class="eyebrow">RECEIPT FORM</div>
                  <h2>{{ editingReceiptId ? "编辑收款单" : "新增收款单" }}</h2>
                </div>
                <button class="modal-close" aria-label="关闭弹窗" @click="resetReceiptForm">×</button>
              </div>
              <div class="form-grid">
                <label>
                  收入合同
                  <select v-model.number="receiptForm.contract_id" @change="receiptForm.stage_id = null; receiptForm.contract_id && loadContractStages(receiptForm.contract_id)">
                    <option :value="0" disabled>{{ incomeContractsLoading ? "正在加载收入合同…" : incomeContracts.length ? "请选择收入合同" : "暂无可用收入合同" }}</option>
                    <option v-for="item in incomeContracts" :key="item.id" :value="item.id">
                      {{ item.name }} · {{ item.counterparty_name }}
                    </option>
                  </select>
                </label>
                <label>
                  收款阶段
                  <select v-model="receiptForm.stage_id">
                    <option :value="null">不关联阶段</option>
                    <option v-for="item in stageOptionsFor(receiptForm.contract_id)" :key="item.id" :value="item.id">
                      {{ item.name }} · {{ moneyText(item.amount) }}
                    </option>
                  </select>
                  <small v-if="receiptSelectedStage" class="form-helper">
                    计划 {{ moneyText(receiptSelectedStage.amount) }} · 已收 {{ moneyText(receiptSelectedStage.settled_amount) }} · 剩余 {{ moneyText(receiptStageRemaining) }}
                  </small>
                </label>
                <label>收款金额<input v-model.number="receiptForm.amount" type="number" min="0.01" step="0.01" /></label>
                <label>收款日期<input v-model="receiptForm.receipt_date" type="date" /></label>
                <label>付款方名称<input v-model.trim="receiptForm.payer_name" placeholder="从客户带出后可修改" /></label>
                <label>付款银行<input v-model.trim="receiptForm.payer_bank_name" /></label>
                <label>付款账号<input v-model.trim="receiptForm.payer_bank_account" /></label>
                <label class="span-2">备注<textarea v-model.trim="receiptForm.comment" rows="3"></textarea></label>
              </div>
              <div class="form-footer">
                <button class="secondary" @click="resetReceiptForm">取消</button>
                <button class="primary" @click="saveReceipt">提交收款单</button>
              </div>
            </section>
          </div>
        </section>

        <section v-else-if="page === 'receiptDetail'" class="page-view narrow">
          <div class="page-head">
            <div>
              <div class="eyebrow">RECEIPT DETAIL / {{ selectedReceipt?.receipt_no }}</div>
              <h1>收款单详情</h1>
              <p class="muted">提交时间：{{ formatDateTime(selectedReceipt?.submitted_at) || "未记录" }}</p>
            </div>
            <div class="actions">
              <span v-if="selectedReceipt" class="tag" :class="cashStatusClass(selectedReceipt.status)">{{ cashStatusLabel(selectedReceipt.status) }}</span>
              <button class="secondary" @click="go('projectReceipts')">返回收款单</button>
            </div>
          </div>
          <section v-if="selectedReceipt" class="two-columns">
            <section class="card">
              <h2>收款信息</h2>
              <div class="detail-grid">
                <div><small>收款单号</small><strong>{{ selectedReceipt.receipt_no }}</strong></div>
                <div><small>收款日期</small><strong>{{ selectedReceipt.receipt_date }}</strong></div>
                <div><small>项目</small><strong>{{ selectedReceipt.project_name }}</strong></div>
                <div><small>收入合同</small><strong>{{ selectedReceipt.contract_name }}</strong></div>
                <div><small>收款阶段</small><strong>{{ selectedReceipt.stage_name || "未关联阶段" }}</strong></div>
                <div><small>收款金额</small><strong>{{ moneyText(selectedReceipt.amount) }}</strong></div>
                <div><small>付款方</small><strong>{{ selectedReceipt.payer_name }}</strong></div>
                <div><small>付款银行</small><strong>{{ selectedReceipt.payer_bank_name || "未填写" }}</strong></div>
                <div><small>付款账号</small><strong>{{ selectedReceipt.payer_bank_account || "未填写" }}</strong></div>
                <div class="full"><small>备注</small><strong>{{ selectedReceipt.comment || "无" }}</strong></div>
              </div>
              <div v-if="selectedReceipt.status === 'PENDING' && canManage('cash_approval')" class="actions">
                <button class="primary success-button" @click="approveReceipt(selectedReceipt)">通过</button>
                <button class="secondary danger-button" @click="rejectReceipt(selectedReceipt)">驳回</button>
              </div>
              <div v-if="selectedReceipt.status === 'REJECTED'" class="notice error"><strong>驳回意见</strong><span>{{ selectedReceipt.comment || "未填写" }}</span></div>
            </section>
            <section class="card">
              <h2>审批信息</h2>
              <div class="timeline">
                <div><b>提交收款单</b><small>{{ formatDateTime(selectedReceipt.submitted_at) || "未记录" }}</small></div>
                <div><b>{{ selectedReceipt.status === "PENDING" ? "等待出纳审批" : selectedReceipt.status === "APPROVED" ? "审批通过" : selectedReceipt.status === "REJECTED" ? "已驳回" : "已冲销" }}</b><small>{{ formatDateTime(selectedReceipt.approved_at) || "待处理" }}</small></div>
              </div>
            </section>
          </section>
          <section v-else class="card empty"><h2>收款单不存在</h2><button class="primary" @click="go('projectReceipts')">返回收款单</button></section>
        </section>

        <section v-else-if="page === 'projectPayments'" class="page-view v3-ops-page">
          <div class="page-head">
            <div>
              <div class="eyebrow">PROJECT / PAYMENTS</div>
              <h1>项目付款</h1>
              <p class="muted">付款单提交后由具备出纳审批权限的人员确认支付。</p>
            </div>
            <div class="actions">
              <button class="primary" @click="openPaymentForm()">＋ 新增付款单</button>
            </div>
          </div>
          <div class="v3-tabs" role="tablist" aria-label="付款单范围">
            <button type="button" :class="{ active: paymentTab === 'pending' }" @click="paymentTab = 'pending'">待我审批</button>
            <button type="button" :class="{ active: paymentTab === 'all' }" @click="paymentTab = 'all'">全部单据</button>
          </div>
          <section class="card v3-filter-card">
            <div class="v3-filters">
              <label>
                项目
                <select v-model.number="paymentFilterProject">
                  <option :value="0">全部项目</option>
                  <option v-for="item in managedProjects" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </option>
                </select>
              </label>
              <label>
                状态
                <select v-model="paymentFilterStatus">
                  <option value="">全部状态</option>
                  <option value="PENDING">待出纳审批</option>
                  <option value="APPROVED">已确认</option>
                  <option value="REJECTED">已驳回</option>
                  <option value="REVERSED">已冲销</option>
                </select>
              </label>
              <div class="v3-filter-actions">
                <button class="primary" @click="refreshPayments">查询</button>
              </div>
            </div>
          </section>
          <section class="card">
            <div class="section-head">
              <div>
                <h2>付款单列表</h2>
                <p class="muted">共 {{ visiblePayments.length }} 张付款单</p>
              </div>
            </div>
            <div v-if="paymentsLoading" class="empty">正在加载付款单…</div>
            <div v-else-if="!visiblePayments.length" class="empty">当前范围暂无付款单。</div>
            <div v-else class="table-wrap">
              <table class="v3-ops-table">
                <thead>
                  <tr>
                    <th>付款单号</th>
                    <th>项目 / 合同</th>
                    <th>阶段</th>
                    <th>金额</th>
                    <th>付款日期</th>
                    <th>收款方</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in visiblePayments" :key="item.id">
                    <td><button class="text-button" @click="openPaymentApproval(item)"><strong>{{ item.payment_no }}</strong></button></td>
                    <td><strong>{{ item.project_name }}</strong><small>{{ item.contract_name }}</small></td>
                    <td>{{ item.stage_name || "未关联阶段" }}</td>
                    <td>{{ moneyText(item.amount) }}</td>
                    <td>{{ item.payment_date }}</td>
                    <td>{{ item.payee_name }}</td>
                    <td><span class="tag" :class="cashStatusClass(item.status)">{{ cashStatusLabel(item.status) }}</span></td>
                    <td>
                      <div class="table-actions">
                        <button class="text-button" @click="openPaymentApproval(item)">查看</button>
                        <button v-if="item.status === 'PENDING' && canManage('cash_approval')" class="text-button" @click="approvePayment(item)">通过</button>
                        <button v-if="item.status === 'PENDING' && canManage('cash_approval')" class="text-button danger-text" @click="rejectPayment(item)">驳回</button>
                        <button v-if="item.status === 'APPROVED' && canManage('cash_approval')" class="text-button" @click="reversePayment(item)">冲销</button>
                        <button v-if="['DRAFT', 'REJECTED'].includes(item.status)" class="text-button" @click="openPaymentForm(item)">编辑</button>
                        <button v-if="['DRAFT', 'REJECTED'].includes(item.status)" class="text-button danger-text" @click="deletePayment(item)">删除</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <div v-if="paymentFormOpen" class="modal-backdrop">
            <section class="modal-card v3-modal" role="dialog" aria-modal="true">
              <div class="modal-head">
                <div>
                  <div class="eyebrow">PAYMENT FORM</div>
                  <h2>{{ editingPaymentId ? "编辑付款单" : "新增付款单" }}</h2>
                </div>
                <button class="modal-close" aria-label="关闭弹窗" @click="resetPaymentForm">×</button>
              </div>
              <div class="form-grid">
                <label>
                  支出合同
                  <select v-model.number="paymentForm.contract_id" @change="paymentForm.stage_id = null; paymentForm.contract_id && loadContractStages(paymentForm.contract_id)">
                    <option :value="0" disabled>{{ expenseContractsLoading ? "正在加载支出合同…" : expenseContracts.length ? "请选择支出合同" : "暂无可用支出合同" }}</option>
                    <option v-for="item in expenseContracts" :key="item.id" :value="item.id">
                      {{ item.name }} · {{ item.counterparty_name }}
                    </option>
                  </select>
                </label>
                <label>
                  付款阶段
                  <select v-model="paymentForm.stage_id">
                    <option :value="null">不关联阶段</option>
                    <option v-for="item in stageOptionsFor(paymentForm.contract_id)" :key="item.id" :value="item.id">
                      {{ item.name }} · {{ moneyText(item.amount) }}
                    </option>
                  </select>
                  <small v-if="paymentSelectedStage" class="form-helper">
                    计划 {{ moneyText(paymentSelectedStage.amount) }} · 已付 {{ moneyText(paymentSelectedStage.settled_amount) }} · 剩余 {{ moneyText(paymentStageRemaining) }}
                  </small>
                </label>
                <label>付款金额<input v-model.number="paymentForm.amount" type="number" min="0.01" step="0.01" /></label>
                <label>付款日期<input v-model="paymentForm.payment_date" type="date" /></label>
                <label>收款方名称<input v-model.trim="paymentForm.payee_name" placeholder="从供应商带出后可修改" /></label>
                <label>收款银行<input v-model.trim="paymentForm.payee_bank_name" /></label>
                <label>收款账号<input v-model.trim="paymentForm.payee_bank_account" /></label>
                <label class="span-2">备注<textarea v-model.trim="paymentForm.comment" rows="3"></textarea></label>
              </div>
              <div class="form-footer">
                <button class="secondary" @click="resetPaymentForm">取消</button>
                <button class="primary" @click="savePayment">提交付款单</button>
              </div>
            </section>
          </div>
        </section>

        <section v-else-if="page === 'paymentDetail'" class="page-view narrow">
          <div class="page-head">
            <div>
              <div class="eyebrow">PAYMENT DETAIL / {{ selectedPayment?.payment_no }}</div>
              <h1>付款单详情</h1>
              <p class="muted">提交时间：{{ formatDateTime(selectedPayment?.submitted_at) || "未记录" }}</p>
            </div>
            <div class="actions">
              <span v-if="selectedPayment" class="tag" :class="cashStatusClass(selectedPayment.status)">{{ cashStatusLabel(selectedPayment.status) }}</span>
              <button class="secondary" @click="go('projectPayments')">返回付款单</button>
            </div>
          </div>
          <section v-if="selectedPayment" class="two-columns">
            <section class="card">
              <h2>付款信息</h2>
              <div class="detail-grid">
                <div><small>付款单号</small><strong>{{ selectedPayment.payment_no }}</strong></div>
                <div><small>付款日期</small><strong>{{ selectedPayment.payment_date }}</strong></div>
                <div><small>项目</small><strong>{{ selectedPayment.project_name }}</strong></div>
                <div><small>支出合同</small><strong>{{ selectedPayment.contract_name }}</strong></div>
                <div><small>付款阶段</small><strong>{{ selectedPayment.stage_name || "未关联阶段" }}</strong></div>
                <div><small>付款金额</small><strong>{{ moneyText(selectedPayment.amount) }}</strong></div>
                <div><small>收款方</small><strong>{{ selectedPayment.payee_name }}</strong></div>
                <div><small>收款银行</small><strong>{{ selectedPayment.payee_bank_name || "未填写" }}</strong></div>
                <div><small>收款账号</small><strong>{{ selectedPayment.payee_bank_account || "未填写" }}</strong></div>
                <div class="full"><small>备注</small><strong>{{ selectedPayment.comment || "无" }}</strong></div>
              </div>
              <div v-if="selectedPayment.status === 'PENDING' && canManage('cash_approval')" class="actions">
                <button class="primary success-button" @click="approvePayment(selectedPayment)">通过</button>
                <button class="secondary danger-button" @click="rejectPayment(selectedPayment)">驳回</button>
              </div>
              <div v-if="selectedPayment.status === 'REJECTED'" class="notice error"><strong>驳回意见</strong><span>{{ selectedPayment.comment || "未填写" }}</span></div>
            </section>
            <section class="card">
              <h2>审批信息</h2>
              <div class="timeline">
                <div><b>提交付款单</b><small>{{ formatDateTime(selectedPayment.submitted_at) || "未记录" }}</small></div>
                <div><b>{{ selectedPayment.status === "PENDING" ? "等待出纳审批" : selectedPayment.status === "APPROVED" ? "审批通过" : selectedPayment.status === "REJECTED" ? "已驳回" : "已冲销" }}</b><small>{{ formatDateTime(selectedPayment.approved_at) || "待处理" }}</small></div>
              </div>
            </section>
          </section>
          <section v-else class="card empty"><h2>付款单不存在</h2><button class="primary" @click="go('projectPayments')">返回付款单</button></section>
        </section>

        <section v-else-if="page === 'suppliers' || page === 'customers'" class="page-view v3-ops-page">
          <div class="page-head">
            <div>
              <div class="eyebrow">COUNTERPARTY / MASTER DATA</div>
              <h1>{{ pageTitle }}</h1>
              <p class="muted">维护往来单位核心信息、联系人、地址和银行账户。</p>
            </div>
            <div class="actions">
              <button class="primary" @click="resetCounterpartyForm(page === 'suppliers' ? 'suppliers' : 'customers')">＋ 新增</button>
            </div>
          </div>
          <section class="card">
            <div class="section-head">
              <div>
                <h2>{{ page === "suppliers" ? "供应商列表" : "客户列表" }}</h2>
                <p class="muted">显示 {{ visibleCounterparties.length }} / {{ page === "suppliers" ? suppliers.length : customers.length }} 条记录</p>
              </div>
            </div>
            <div class="counterparty-filters">
              <label>关键词<input v-model.trim="counterpartyKeyword" type="search" placeholder="名称、编号或统一信用代码" /></label>
              <label>状态<select v-model="counterpartyStatus"><option value="">全部状态</option><option value="ACTIVE">启用</option><option value="INACTIVE">停用</option></select></label>
              <button class="secondary" @click="counterpartyKeyword = ''; counterpartyStatus = ''">重置筛选</button>
            </div>
            <div v-if="counterpartiesLoading" class="empty">正在加载…</div>
            <div v-else-if="!visibleCounterparties.length" class="empty">当前筛选范围暂无数据。</div>
            <div v-else class="table-wrap">
              <table class="v3-ops-table">
                <thead>
                  <tr>
                    <th>名称</th>
                    <th>编号</th>
                    <th>统一信用代码</th>
                    <th>联系人</th>
                    <th>联系电话</th>
                    <th>开户银行</th>
                    <th>银行账号</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in visibleCounterparties" :key="item.id">
                    <td><strong>{{ item.name }}</strong><small v-if="item.short_name">{{ item.short_name }}</small></td>
                    <td>{{ item.code }}</td>
                    <td>{{ item.unified_credit_code || "—" }}</td>
                    <td>{{ item.contact_name || "—" }}</td>
                    <td>{{ item.contact_phone || "—" }}</td>
                    <td>{{ item.bank_name || "—" }}</td>
                    <td>{{ item.bank_account || "—" }}</td>
                    <td><span class="tag" :class="item.status === 'ACTIVE' ? 'success' : 'neutral'">{{ item.status === "ACTIVE" ? "启用" : "停用" }}</span></td>
                    <td>
                      <div class="table-actions">
                        <button class="text-button" @click="editCounterparty(page === 'suppliers' ? 'suppliers' : 'customers', item)">编辑</button>
                        <button class="text-button danger-text" @click="deleteCounterparty(page === 'suppliers' ? 'suppliers' : 'customers', item)">停用</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <div v-if="customerFormOpen || supplierFormOpen" class="modal-backdrop">
            <section class="modal-card v3-modal" role="dialog" aria-modal="true">
              <div class="modal-head">
                <div>
                  <div class="eyebrow">COUNTERPARTY FORM</div>
                  <h2>{{ page === "suppliers" ? (editingSupplierId ? "编辑供应商" : "新增供应商") : (editingCustomerId ? "编辑客户" : "新增客户") }}</h2>
                </div>
                <button class="modal-close" aria-label="关闭弹窗" @click="page === 'suppliers' ? supplierFormOpen = false : customerFormOpen = false">×</button>
              </div>
              <div class="form-grid">
                <label>编号<input v-model.trim="activeCounterpartyForm.code" /></label>
                <label>名称<input v-model.trim="activeCounterpartyForm.name" /></label>
                <label>简称<input v-model.trim="activeCounterpartyForm.short_name" /></label>
                <label>统一信用代码<input v-model.trim="activeCounterpartyForm.unified_credit_code" /></label>
                <label>联系人<input v-model.trim="activeCounterpartyForm.contact_name" /></label>
                <label>联系电话<input v-model.trim="activeCounterpartyForm.contact_phone" /></label>
                <label>联系邮箱<input v-model.trim="activeCounterpartyForm.contact_email" /></label>
                <label>注册地址<input v-model.trim="activeCounterpartyForm.address" /></label>
                <label>办公地址<input v-model.trim="activeCounterpartyForm.office_address" /></label>
                <label>证照有效期<input v-model="activeCounterpartyForm.license_expiry_date" type="date" /></label>
                <label>开户银行<input v-model.trim="activeCounterpartyForm.bank_name" /></label>
                <label>开户支行<input v-model.trim="activeCounterpartyForm.bank_branch" /></label>
                <label>银行账号<input v-model.trim="activeCounterpartyForm.bank_account" /></label>
                <label>开票抬头<input v-model.trim="activeCounterpartyForm.invoice_title" /></label>
                <label>纳税人识别号<input v-model.trim="activeCounterpartyForm.taxpayer_id" /></label>
                <label>开票地址<input v-model.trim="activeCounterpartyForm.invoice_address" /></label>
                <label>开票电话<input v-model.trim="activeCounterpartyForm.invoice_phone" /></label>
                <label>
                  状态
                  <select v-model="activeCounterpartyForm.status">
                    <option value="ACTIVE">启用</option>
                    <option value="INACTIVE">停用</option>
                  </select>
                </label>
                <label class="span-2">备注<textarea v-model.trim="activeCounterpartyForm.notes" rows="3"></textarea></label>
              </div>
              <div class="form-footer">
                <button class="secondary" @click="page === 'suppliers' ? supplierFormOpen = false : customerFormOpen = false">取消</button>
                <button class="primary" @click="saveCounterparty(page === 'suppliers' ? 'suppliers' : 'customers')">保存</button>
              </div>
            </section>
          </div>
        </section>

        <section v-else-if="page === 'projectBoard'" class="page-view v3-ops-page">
          <div class="page-head">
            <div>
              <div class="eyebrow">PROJECT / FINANCE BOARD</div>
              <h1>项目看板</h1>
              <p class="muted">按项目汇总合同、收付款和毛利，并提示应收应付预警。</p>
            </div>
          </div>
          <section class="card v3-filter-card">
            <div class="v3-filters board-filters">
              <div class="scope-switch">
                <button type="button" :class="{ active: boardDataScope === 'OWNED' }" @click="boardDataScope = 'OWNED'; refreshProjectBoard()">我负责的</button>
                <button type="button" :class="{ active: boardDataScope === 'ALL' }" @click="boardDataScope = 'ALL'; refreshProjectBoard()">全部项目</button>
              </div>
              <label>
                项目
                <select v-model.number="boardFilterProject">
                  <option :value="0">全部项目</option>
                  <option v-for="item in managedProjects" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </option>
                </select>
              </label>
              <label>
                类型
                <select v-model="boardFilterType">
                  <option value="">全部类型</option>
                  <option v-for="option in activeConfigOptions('project_type')" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <label>
                状态
                <select v-model="boardFilterStatus">
                  <option value="">全部状态</option>
                  <option v-for="option in activeConfigOptions('project_status')" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <label>
                所属部门
                <select v-model.number="boardFilterDepartment">
                  <option :value="0">全部部门</option>
                  <option v-for="item in projectDepartmentOptions" :key="item.id" :value="item.id">
                    {{ item.path || item.name }}
                  </option>
                </select>
              </label>
              <label>
                负责人
                <select v-model.number="boardFilterOwner">
                  <option :value="0">全部负责人</option>
                  <option v-for="person in demoUsers" :key="person.id" :value="person.id">
                    {{ person.name }}
                  </option>
                </select>
              </label>
              <label>
                客户
                <select v-model.number="boardFilterCustomer">
                  <option :value="0">全部客户</option>
                  <option v-for="item in customers" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </option>
                </select>
              </label>
              <div class="v3-filter-actions">
                <button class="primary" @click="refreshProjectBoard">查询</button>
                <button class="secondary" @click="exportProjectBoard">导出</button>
              </div>
            </div>
          </section>
          <div v-if="boardLoading" class="card empty">正在加载项目看板…</div>
          <section v-else class="card">
            <div class="section-head">
              <div>
                <h2>项目经营汇总</h2>
                <p class="muted">共 {{ projectBoardRows.length }} 个项目</p>
              </div>
            </div>
            <div class="board-kpi-row">
              <article><span>收入（已收）</span><strong>{{ moneyText(boardTotals.received) }}</strong></article>
              <article><span>总成本</span><strong>{{ moneyText(boardTotals.paid) }}</strong></article>
              <article><span>应收</span><strong>{{ moneyText(boardTotals.receivable) }}</strong></article>
              <article><span>应付</span><strong>{{ moneyText(boardTotals.payable) }}</strong></article>
              <article><span>已收 / 已付</span><strong>{{ moneyText(boardTotals.received) }} / {{ moneyText(boardTotals.paid) }}</strong></article>
              <article><span>毛利</span><strong>{{ moneyText(boardTotals.gross_profit) }}</strong></article>
              <article><span>毛利率</span><strong>{{ boardMarginRate }}</strong></article>
            </div>
            <div class="board-chart-grid">
              <section class="card board-chart-card">
                <div class="section-head">
                  <div>
                    <h2>收支对比</h2>
                    <p class="muted">按项目对比已收与已付</p>
                  </div>
                </div>
                <div ref="boardChartEl" class="report-chart"></div>
              </section>
              <section class="card board-chart-card">
                <div class="section-head">
                  <div>
                    <h2>项目毛利排行</h2>
                    <p class="muted">正负毛利按颜色区分</p>
                  </div>
                </div>
                <div ref="boardProfitChartEl" class="report-chart"></div>
              </section>
            </div>
            <div v-if="!projectBoardRows.length" class="empty">当前范围暂无项目数据。</div>
            <div v-else class="table-wrap">
              <table class="v3-ops-table board-table">
                <thead>
                  <tr>
                    <th>项目</th>
                    <th>负责人</th>
                    <th>合同收入</th>
                    <th>合同成本</th>
                    <th>已收</th>
                    <th>已付</th>
                    <th>应收</th>
                    <th>应付</th>
                    <th>毛利</th>
                    <th>预警</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in projectBoardRows" :key="item.id" @click="openProjectDetail({ id: item.id } as Project)">
                    <td><strong>{{ item.name }}</strong><small>{{ item.code }}</small></td>
                    <td>{{ item.owner_name }}</td>
                    <td>{{ moneyText(item.contract_income) }}</td>
                    <td>{{ moneyText(item.contract_expense) }}</td>
                    <td>{{ moneyText(item.received) }}</td>
                    <td>{{ moneyText(item.paid) }}</td>
                    <td>{{ moneyText(item.receivable) }}</td>
                    <td>{{ moneyText(item.payable) }}</td>
                    <td><b :class="item.gross_profit >= 0 ? 'profit-positive' : 'profit-negative'">{{ moneyText(item.gross_profit) }}</b></td>
                    <td><span v-if="item.warning" class="tag warning">{{ item.warning }}</span><span v-else>—</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </section>

        <section
          v-else-if="page === 'adminPermissions'"
          class="page-view admin-permissions-page"
        >
          <div class="page-head">
            <div>
              <div class="eyebrow">ADMIN / ACCESS CONTROL</div>
              <h1>管理员管理</h1>
              <p class="muted">
                只维护已加入管理的人员，并配置他们可以查看和操作的菜单。
              </p>
            </div>
            <div class="actions">
              <button
                class="secondary"
                @click="go('integrations')"
                v-if="canManage('integrations')"
              >
                集成与通知</button
              ><button class="secondary" @click="queryAdminPermissions">
                查询</button
              ><button
                class="primary"
                :disabled="!adminPermissionAvailableUsers.length"
                @click="openAdminPermissionForm"
              >
                ＋ 添加管理员
              </button>
            </div>
          </div>
          <section class="card admin-permission-filter-card">
            <div class="admin-permission-filter">
              <label
                >搜索已加入人员<input
                  v-model.trim="adminPermissionKeyword"
                  type="search"
                  placeholder="按姓名或邮箱搜索"
                  @keyup.enter="queryAdminPermissions" /></label
              ><button class="primary" @click="queryAdminPermissions">
                查询
              </button>
            </div>
            <p class="form-helper">
              未加入管理权限的组织人员不会显示在此列表。勾选菜单后保存即可授予查看和操作权限。
            </p>
          </section>
          <section class="card admin-permission-list-card">
            <div class="section-head">
              <div>
                <h2>已加入管理的人员</h2>
                <p class="muted">共 {{ adminPermissions.length }} 名管理员</p>
              </div>
              <span class="tag teal">仅显示已配置人员</span>
            </div>
            <div v-if="adminPermissionLoading" class="empty">
              正在读取管理员权限…
            </div>
            <div v-else-if="!adminPermissions.length" class="empty">
              <h2>还没有加入管理的人员</h2>
              <p>点击“添加管理员”，从飞书组织架构中选择人员。</p>
              <button
                class="primary"
                :disabled="!adminPermissionAvailableUsers.length"
                @click="openAdminPermissionForm"
              >
                添加第一位管理员
              </button>
            </div>
            <div v-else class="table-wrap">
              <table class="admin-permission-table">
                <thead>
                  <tr>
                    <th>人员</th>
                    <th>可见菜单与操作权限</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in adminPermissions" :key="item.user_id">
                    <td class="admin-permission-person">
                      <strong>{{ item.user_name }}</strong
                      ><small>{{ item.department_name }}</small
                      ><span v-if="item.is_system_admin" class="tag teal"
                        >系统管理员</span
                      >
                    </td>
                    <td>
                      <div class="permission-menu-list">
                        <label
                          v-for="permission in permissionLabels"
                          :key="permission.key"
                          class="permission-menu-option"
                          ><input
                            v-model="item[permission.field]"
                            type="checkbox"
                            :disabled="item.is_system_admin"
                          /><span>{{ permission.label }}</span></label
                        >
                      </div>
                      <div class="project-data-scope-editor">
                        <label>
                          项目数据范围
                          <select
                            v-model="item.project_data_scope"
                            :disabled="item.is_system_admin"
                            @change="
                              item.project_data_scope !== 'DEPARTMENT' &&
                              (item.scope_department_id = null)
                            "
                          >
                            <option value="OWNED">仅本人负责项目</option>
                            <option value="DEPARTMENT">
                              指定部门及下级部门
                            </option>
                            <option value="ALL">全部项目</option>
                          </select>
                        </label>
                        <label v-if="item.project_data_scope === 'DEPARTMENT'">
                          数据部门
                          <select
                            v-model.number="item.scope_department_id"
                            :disabled="item.is_system_admin"
                          >
                            <option :value="null" disabled>请选择部门</option>
                            <option
                              v-for="department in projectDepartmentOptions"
                              :key="department.id"
                              :value="department.id"
                            >
                              {{ department.path || department.name }}
                            </option>
                          </select>
                        </label>
                      </div>
                    </td>
                    <td>
                      <div class="table-actions">
                        <button
                          class="secondary permission-save"
                          :disabled="
                            item.is_system_admin ||
                            adminPermissionSavingId === item.user_id
                          "
                          @click="saveAdminPermission(item)"
                        >
                          {{
                            adminPermissionSavingId === item.user_id
                              ? "保存中…"
                              : "保存权限"
                          }}</button
                        ><button
                          class="text-button danger-button"
                          :disabled="
                            item.is_system_admin ||
                            adminPermissionSavingId === item.user_id
                          "
                          @click="clearAdminPermission(item)"
                        >
                          移除
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <div v-if="adminPermissionFormOpen" class="modal-backdrop">
            <section
              class="modal-card admin-permission-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="admin-permission-modal-title"
            >
              <div class="modal-head">
                <div>
                  <div class="eyebrow">ADD ADMINISTRATOR</div>
                  <h2 id="admin-permission-modal-title">添加管理员</h2>
                  <p class="muted">
                    从已同步的飞书组织架构选择人员，并设置可以查看和操作的菜单。
                  </p>
                </div>
                <button
                  class="modal-close"
                  aria-label="关闭弹窗"
                  @click="resetAdminPermissionForm"
                >
                  ×
                </button>
              </div>
              <label
                >选择人员<select v-model.number="adminPermissionForm.user_id">
                  <option :value="0" disabled>请选择组织人员</option>
                  <option
                    v-for="person in adminPermissionAvailableUsers"
                    :key="person.id"
                    :value="person.id"
                  >
                    {{ person.name }} · {{ person.department_name }}
                  </option>
                </select></label
              >
              <div class="permission-menu-grid">
                <label
                  v-for="permission in permissionLabels"
                  :key="permission.key"
                  class="permission-menu-card"
                  ><input
                    v-model="adminPermissionForm[permission.field]"
                    type="checkbox"
                  /><span
                    ><strong>{{ permission.label }}</strong
                    ><small>允许查看并操作该管理菜单</small></span
                  ></label
                >
              </div>
              <section class="admin-scope-panel">
                <div>
                  <strong>项目数据范围</strong>
                  <p>控制项目列表、项目看板和经营数据可查看的范围。</p>
                </div>
                <div class="admin-scope-fields">
                  <label>
                    数据范围
                    <select
                      v-model="adminPermissionForm.project_data_scope"
                      @change="
                        adminPermissionForm.project_data_scope !==
                          'DEPARTMENT' &&
                        (adminPermissionForm.scope_department_id = null)
                      "
                    >
                      <option value="OWNED">仅本人负责项目</option>
                      <option value="DEPARTMENT">指定部门及下级部门</option>
                      <option value="ALL">全部项目</option>
                    </select>
                  </label>
                  <label
                    v-if="
                      adminPermissionForm.project_data_scope === 'DEPARTMENT'
                    "
                  >
                    数据部门
                    <select
                      v-model.number="adminPermissionForm.scope_department_id"
                    >
                      <option :value="null" disabled>请选择部门</option>
                      <option
                        v-for="department in projectDepartmentOptions"
                        :key="department.id"
                        :value="department.id"
                      >
                        {{ department.path || department.name }}
                      </option>
                    </select>
                  </label>
                </div>
              </section>
              <div class="form-footer">
                <button class="secondary" @click="resetAdminPermissionForm">
                  取消</button
                ><button class="primary" @click="saveNewAdminPermission">
                  保存管理员
                </button>
              </div>
            </section>
          </div>
        </section>
        <section
          v-else-if="page === 'personnelCosts'"
          class="page-view personnel-cost-page"
        >
          <div class="page-head">
            <div>
              <div class="eyebrow">ADMIN / PERSONNEL COSTS</div>
              <h1>人员成本</h1>
              <p class="muted">
                只维护已加入成本管理的人员，新增人员通过弹窗从飞书组织架构中选择。
              </p>
            </div>
            <div class="actions">
              <button class="secondary" @click="go('adminWorklogs')">
                工时管理</button
              ><button
                class="primary"
                :disabled="!personnelCostAvailableUsers.length"
                @click="openPersonnelCostForm"
              >
                ＋ 添加人员成本
              </button>
            </div>
          </div>
          <section class="card personnel-cost-filter-card">
            <div class="personnel-cost-filters">
              <label
                >部门<select v-model="personnelCostDepartment">
                  <option value="">全部部门</option>
                  <option
                    v-for="name in personnelCostDepartmentOptions"
                    :key="name"
                    :value="name"
                  >
                    {{ name }}
                  </option>
                </select></label
              ><label
                >人员<select v-model.number="personnelCostUserId">
                  <option :value="0">全部人员</option>
                  <option
                    v-for="person in personnelCostUserOptions"
                    :key="person.id"
                    :value="person.id"
                  >
                    {{ person.name }} · {{ person.department_name }}
                  </option>
                </select></label
              ><label
                >每页条数<select
                  v-model="personnelCostPageSizeMode"
                  @change="changePersonnelCostPageSizeMode"
                >
                  <option value="10">10 条</option>
                  <option value="20">20 条</option>
                  <option value="50">50 条</option>
                  <option value="custom">自定义</option></select
                ><input
                  v-if="personnelCostPageSizeMode === 'custom'"
                  v-model.number="personnelCostPageSize"
                  type="number"
                  min="1"
                  max="200"
                  placeholder="1-200"
                  @change="changePersonnelCostCustomPageSize" /></label
              ><button
                class="primary personnel-cost-query"
                @click="queryPersonnelCosts"
              >
                查询
              </button>
            </div>
            <div class="personnel-cost-summary-line">
              <span
                >已加入成本管理
                <strong>{{ personnelCostTotal }}</strong> 人</span
              ><span
                >可添加组织人员
                <strong>{{ personnelCostAvailableUsers.length }}</strong>
                人</span
              >
            </div>
          </section>
          <section class="card personnel-cost-list-card">
            <div class="section-head">
              <div>
                <h2>已加入成本管理的人员</h2>
                <p class="muted">
                  部门筛选包含下级部门；修改成本后会立即影响后续人工成本估算。
                </p>
              </div>
              <span class="tag teal"
                >第 {{ personnelCostPage }} /
                {{ personnelCostPageCount }} 页</span
              >
            </div>
            <div v-if="personnelCostLoading" class="empty">
              正在读取人员成本…
            </div>
            <div v-else-if="!personnelCosts.length" class="empty">
              <h2>还没有加入成本管理的人员</h2>
              <p>
                点击“添加人员成本”，从飞书组织架构中选择人员并填写单天成本。
              </p>
              <button
                class="primary"
                :disabled="!personnelCostAvailableUsers.length"
                @click="openPersonnelCostForm"
              >
                添加第一位人员
              </button>
            </div>
            <div v-else class="table-wrap">
              <table class="personnel-cost-table">
                <thead>
                  <tr>
                    <th>人员</th>
                    <th>所属部门</th>
                    <th>单天成本</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="person in personnelCosts" :key="person.id">
                    <td>
                      <div class="personnel-person-cell">
                        <span class="personnel-cost-avatar">{{
                          person.name.slice(0, 1)
                        }}</span
                        ><span
                          ><strong>{{ person.name }}</strong
                          ><small>组织用户 #{{ person.id }}</small></span
                        >
                      </div>
                    </td>
                    <td>
                      <div class="department-cell">
                        <span class="department-tree-mark"></span
                        ><span>{{ person.department_name }}</span>
                      </div>
                    </td>
                    <td>
                      <div class="personnel-cost-input">
                        <span>¥</span
                        ><input
                          v-model.number="person.daily_cost"
                          type="number"
                          min="0"
                          step="0.01"
                          placeholder="请输入单天成本"
                          aria-label="单天成本"
                        />
                      </div>
                      <small class="cost-input-help">按 1 天核算</small>
                    </td>
                    <td>
                      <button
                        class="secondary personnel-cost-save"
                        :disabled="personnelCostSavingId === person.id"
                        @click="savePersonnelCost(person)"
                      >
                        <span>{{
                          personnelCostSavingId === person.id
                            ? "保存中…"
                            : "保存成本"
                        }}</span>
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="admin-pagination personnel-cost-pagination">
              <span
                >第 {{ personnelCostPage }} / {{ personnelCostPageCount }} 页 ·
                共 {{ personnelCostTotal }} 人</span
              >
              <div class="admin-pagination-actions">
                <button
                  class="secondary"
                  :disabled="personnelCostPage <= 1"
                  @click="changePersonnelCostPage(personnelCostPage - 1)"
                >
                  上一页</button
                ><button
                  class="secondary"
                  :disabled="personnelCostPage >= personnelCostPageCount"
                  @click="changePersonnelCostPage(personnelCostPage + 1)"
                >
                  下一页
                </button>
              </div>
            </div>
          </section>
          <div v-if="personnelCostFormOpen" class="modal-backdrop">
            <section
              class="modal-card personnel-cost-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="personnel-cost-modal-title"
            >
              <div class="modal-head">
                <div>
                  <div class="eyebrow">ADD PERSONNEL COST</div>
                  <h2 id="personnel-cost-modal-title">添加人员成本</h2>
                  <p class="muted">
                    选择飞书组织人员并填写单天成本，保存后会加入成本管理列表。
                  </p>
                </div>
                <button
                  class="modal-close"
                  aria-label="关闭弹窗"
                  @click="resetPersonnelCostForm"
                >
                  ×
                </button>
              </div>
              <div class="personnel-cost-form-grid">
                <label
                  >选择人员<select v-model.number="personnelCostForm.user_id">
                    <option :value="0" disabled>请选择组织人员</option>
                    <option
                      v-for="person in personnelCostAvailableUsers"
                      :key="person.id"
                      :value="person.id"
                    >
                      {{ person.name }} · {{ person.department_name }}
                    </option>
                  </select></label
                ><label
                  >单天成本
                  <div class="personnel-cost-input personnel-cost-modal-input">
                    <span>¥</span
                    ><input
                      v-model.number="personnelCostForm.daily_cost"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="请输入单天成本"
                      aria-label="新增人员单天成本"
                    />
                  </div>
                  <small class="form-helper muted"
                    >按员工 1 个工作日核算</small
                  ></label
                >
              </div>
              <div class="form-footer">
                <button class="secondary" @click="resetPersonnelCostForm">
                  取消</button
                ><button
                  class="primary"
                  :disabled="
                    personnelCostSavingId === personnelCostForm.user_id
                  "
                  @click="saveNewPersonnelCost"
                >
                  {{
                    personnelCostSavingId === personnelCostForm.user_id
                      ? "保存中…"
                      : "保存并加入"
                  }}
                </button>
              </div>
            </section>
          </div>
        </section>
        <section v-else-if="page === 'integrations'" class="page-view integration-page">
          <div class="page-head">
            <div>
              <div class="eyebrow">ADMIN / INTEGRATIONS</div>
              <h1>集成与通知</h1>
              <p class="muted">组织架构来自飞书，本地系统负责业务状态，飞书应用消息负责提醒。</p>
            </div>
            <div class="actions">
              <button class="secondary" @click="queryIntegrationOverview">刷新数据</button>
              <button class="primary" @click="syncOrgUsers">同步组织架构</button>
            </div>
          </div>
          <section class="integration-kpi-grid">
            <article class="card integration-kpi"><span>飞书连接</span><strong class="integration-kpi-status">{{ notificationHealthLabel(integrationHealth.notification) }}</strong><small>{{ directoryHealthLabel(integrationHealth.directory) }}</small></article>
            <article class="card integration-kpi"><span>组织成员</span><strong>{{ integrationOverview?.summary.member_count ?? demoUsers.length }}</strong><small>{{ integrationOverview?.summary.department_count ?? departments.length }} 个部门</small></article>
            <article class="card integration-kpi"><span>已发送通知</span><strong>{{ integrationOverview?.summary.sent_count ?? 0 }}</strong><small>系统累计记录</small></article>
            <article class="card integration-kpi"><span>待处理失败</span><strong :class="(integrationOverview?.summary.retry_count || 0) ? 'negative-number' : 'positive-number'">{{ integrationOverview?.summary.retry_count ?? 0 }}</strong><small>可在下方重试</small></article>
          </section>
          <div class="two-columns integration-overview-grid">
            <section class="card">
              <div class="section-head"><div><h2>组织架构同步</h2><p class="muted">主动同步飞书组织成员和部门，项目人员字段始终读取本地最新快照。</p></div><span class="tag teal">{{ demoUsers.length }} 人 · {{ departments.length }} 部门</span></div>
              <div class="integration-sync-summary"><strong>{{ syncSummary || "尚未执行本次同步" }}</strong><span>同步不会删除历史业务数据</span></div>
              <div v-if="!integrationOverview?.sync_logs.length" class="empty">暂无组织同步记录。</div>
              <div v-else class="integration-sync-list"><div v-for="item in integrationOverview.sync_logs.slice(0, 5)" :key="item.id" class="integration-sync-row"><span class="integration-status-dot" :class="item.status === 'SUCCESS' || item.status === 'MOCK' ? 'ok' : 'error'"></span><div><strong>{{ item.status === 'MOCK' ? '演示组织架构' : item.status === 'SUCCESS' ? '飞书组织架构' : '同步失败' }}</strong><small>{{ formatDateTime(item.created_at) }} · {{ item.user_count }} 人 · {{ item.department_count }} 部门</small></div><span class="tag" :class="item.status === 'SUCCESS' || item.status === 'MOCK' ? 'success' : 'danger'">{{ item.status === 'SUCCESS' || item.status === 'MOCK' ? '完成' : '失败' }}</span></div></div>
            </section>
            <section class="card">
              <div class="section-head"><div><h2>通知策略</h2><p class="muted">所有业务提醒进入发送记录，失败不影响审批和经营数据。</p></div><span class="tag" :class="integrationHealth.notification === 'app' ? 'success' : 'warning'">{{ notificationHealthLabel(integrationHealth.notification) }}</span></div>
              <div class="integration-policy-list"><div><strong>工时审批</strong><span>提交、通过、驳回</span></div><div><strong>收付款审批</strong><span>审批结果通知申请人</span></div><div><strong>合同阶段</strong><span>临期、到期、逾期提醒</span></div><div><strong>项目预警</strong><span>成本、人天预算和待审批事项</span></div></div>
              <p class="integration-boundary"><b>业务边界</b> 本地审批状态是唯一业务依据，飞书只作为通知和内置浏览器入口。</p>
            </section>
          </div>
          <section class="card integration-notification-card">
            <div class="section-head"><div><h2>最近通知记录</h2><p class="muted">收付款审批、项目预算、人天预算及合同阶段提醒。</p></div><span class="tag teal">共 {{ integrationOverview?.notification_total ?? 0 }} 条</span></div>
            <div class="integration-filters"><label>通知类型<select v-model="integrationNotificationType"><option value="">全部类型</option><option v-for="type in integrationNotificationTypes" :key="type" :value="type">{{ integrationNotificationTypeLabel(type) }}</option></select></label><label>发送状态<select v-model="integrationNotificationStatus"><option value="">全部状态</option><option value="SENT">发送成功</option><option value="FAILED">发送失败</option><option value="PENDING">发送中</option></select></label><button class="secondary" @click="integrationNotificationType = ''; integrationNotificationStatus = ''">重置筛选</button></div>
            <div v-if="integrationOverviewLoading" class="empty">正在读取通知记录…</div>
            <div v-else-if="!integrationNotificationRows.length" class="empty">当前没有匹配的通知记录。</div>
            <div v-else class="table-wrap"><table class="integration-notification-table"><thead><tr><th>时间</th><th>通知类型</th><th>业务对象</th><th>接收人</th><th>通道</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="item in integrationNotificationRows" :key="item.id"><td>{{ formatDateTime(item.created_at) }}</td><td><strong>{{ integrationNotificationTypeLabel(item.notification_type) }}</strong><small v-if="item.retry_count">已重试 {{ item.retry_count }} 次</small></td><td>{{ item.source_label }}</td><td>{{ item.recipient_name }}</td><td>{{ notificationHealthLabel(item.channel) }}</td><td><span class="tag" :class="integrationNotificationStatusClass(item.status)">{{ integrationNotificationStatusLabel(item.status) }}</span><small v-if="item.error_message" class="integration-error-text">{{ notificationErrorLabel(item.error_message) }}</small></td><td><button v-if="item.status === 'FAILED'" class="text-button" @click="retryIntegrationNotification(item)">重新发送</button><span v-else class="muted">—</span></td></tr></tbody></table></div>
          </section>
        </section>
        <section
          v-else-if="page === 'configuration'"
          class="page-view configuration-page"
        >
          <div class="page-head">
            <div>
              <div class="eyebrow">ADMIN / CONFIGURATION</div>
              <h1>基础配置</h1>
              <p class="muted">
                维护项目和工时表单中的下拉选项；选项值用于系统存储，显示名称可随时调整。
              </p>
            </div>
            <button class="primary" @click="openConfigurationForm">
              ＋ 新增选项
            </button>
          </div>
          <section class="card configuration-layout">
            <aside class="configuration-categories">
              <button
                v-for="category in Object.keys(adminConfigOptions)"
                :key="category"
                :class="{ active: configurationCategory === category }"
                @click="configurationCategory = category"
              >
                <span>{{ configCategoryLabel(category) }}</span
                ><small
                  >{{ (adminConfigOptions[category] || []).length }} 项</small
                >
              </button>
            </aside>
            <section class="configuration-list">
              <div class="section-head">
                <div>
                  <h2>{{ configCategoryLabel(configurationCategory) }}</h2>
                  <p class="muted">
                    停用后不会出现在新增表单中，已使用的选项不能停用或删除。
                  </p>
                </div>
                <span class="tag teal"
                  >{{
                    visibleConfigOptions.filter((option) => option.is_active)
                      .length
                  }}
                  项启用</span
                >
              </div>
              <div v-if="configurationLoading" class="empty">
                正在读取配置项…
              </div>
              <div v-else-if="!visibleConfigOptions.length" class="empty">
                当前分类还没有配置项。
              </div>
              <div v-else class="configuration-options">
                <div
                  v-for="option in visibleConfigOptions"
                  :key="option.id"
                  class="configuration-option-row"
                  :class="{ inactive: !option.is_active }"
                >
                  <div>
                    <strong>{{ option.label }}</strong
                    ><small
                      >值：{{ option.value
                      }}<span v-if="option.is_builtin"> · 系统默认</span></small
                    >
                  </div>
                  <span class="configuration-order">{{
                    option.sort_order
                  }}</span
                  ><span
                    class="tag"
                    :class="option.is_active ? 'success' : 'neutral'"
                    >{{ option.is_active ? "启用" : "停用" }}</span
                  >
                  <div class="table-actions">
                    <button
                      class="text-button"
                      @click="editConfigurationOption(option)"
                    >
                      编辑</button
                    ><button
                      class="text-button danger-button"
                      :disabled="option.is_builtin"
                      @click="deleteConfigurationOption(option)"
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
            </section>
          </section>
          <div v-if="configurationFormOpen" class="modal-backdrop">
            <section
              class="modal-card configuration-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="configuration-modal-title"
            >
              <div class="modal-head">
                <div>
                  <div class="eyebrow">CONFIGURATION OPTION</div>
                  <h2 id="configuration-modal-title">
                    {{ configurationEditingId ? "编辑配置项" : "新增配置项" }}
                  </h2>
                  <p class="muted">新增项请使用唯一值；系统默认项不能删除。</p>
                </div>
                <button
                  class="modal-close"
                  aria-label="关闭弹窗"
                  @click="resetConfigurationForm"
                >
                  ×
                </button>
              </div>
              <div class="form-grid">
                <label
                  >配置分类<select
                    v-model="configurationForm.category"
                    :disabled="Boolean(configurationEditingId)"
                  >
                    <option
                      v-for="category in Object.keys(adminConfigOptions)"
                      :key="category"
                      :value="category"
                    >
                      {{ configCategoryLabel(category) }}
                    </option>
                  </select></label
                ><label
                  >存储值<input
                    v-model.trim="configurationForm.value"
                    :disabled="Boolean(configurationEditingId)"
                    placeholder="如 CUSTOMER_PROJECT" /></label
                ><label
                  >显示名称<input
                    v-model.trim="configurationForm.label"
                    placeholder="如 客户项目" /></label
                ><label
                  >排序<input
                    v-model.number="configurationForm.sort_order"
                    type="number"
                    min="0"
                    step="1" /></label
                ><label class="configuration-active-field"
                  ><input
                    v-model="configurationForm.is_active"
                    type="checkbox"
                  />启用此选项</label
                >
              </div>
              <div class="form-footer">
                <button class="secondary" @click="resetConfigurationForm">
                  取消</button
                ><button class="primary" @click="saveConfigurationOption">
                  保存配置项
                </button>
              </div>
            </section>
          </div>
        </section>
        <section
          v-else-if="page === 'adminWorklogs'"
          class="page-view admin-worklogs-page"
        >
          <div class="page-head">
            <div>
              <div class="eyebrow">ADMIN / WORKLOGS</div>
              <h1>工时管理</h1>
              <p class="muted">
                查看和维护全体人员工时，修改不会重置原审批状态。
              </p>
            </div>
            <div class="actions">
              <button class="primary" @click="queryAdminWorklogs">查询</button>
            </div>
          </div>
          <section class="card admin-worklog-filter-card">
            <div class="admin-worklog-filters">
              <label
                >开始日期<input v-model="adminPeriodStart" type="date"
              /></label>
              <label
                >结束日期<input v-model="adminPeriodEnd" type="date"
              /></label>
              <label
                >部门<select v-model="adminDepartment">
                  <option value="">全部部门</option>
                  <option
                    v-for="name in adminDepartmentOptions"
                    :key="name"
                    :value="name"
                  >
                    {{ name }}
                  </option>
                </select></label
              >
              <label
                >填报人<select v-model.number="adminUserId">
                  <option :value="0">全部人员</option>
                  <option
                    v-for="person in demoUsers"
                    :key="person.id"
                    :value="person.id"
                  >
                    {{ person.name }} · {{ person.department_name }}
                  </option>
                </select></label
              >
              <label
                >状态<select v-model="adminStatus">
                  <option value="">全部状态</option>
                  <option value="APPROVED">已通过</option>
                  <option value="PENDING_APPROVAL">审批中</option>
                  <option value="DRAFT">草稿</option>
                  <option value="REJECTED">已驳回</option>
                  <option value="LOCKED">已锁定</option>
                </select></label
              >
              <label class="admin-project-field"
                >项目<select v-model.number="adminProjectId">
                  <option :value="0">全部项目</option>
                  <option
                    v-for="project in projects"
                    :key="project.id"
                    :value="project.id"
                  >
                    {{ project.name }} · {{ project.code }}
                  </option>
                </select></label
              >
              <label class="admin-page-size-field"
                >每页条数<select
                  v-model="adminPageSizeMode"
                  @change="changeAdminPageSizeMode"
                >
                  <option value="10">10 条</option>
                  <option value="20">20 条</option>
                  <option value="50">50 条</option>
                  <option value="custom">自定义</option></select
                ><input
                  v-if="adminPageSizeMode === 'custom'"
                  v-model.number="adminPageSize"
                  type="number"
                  min="1"
                  max="200"
                  placeholder="1-200"
                  @change="changeAdminCustomPageSize"
              /></label>
            </div>
            <div class="admin-summary-strip">
              <span>当前 {{ adminWorklogTotal }} 条</span
              ><span>合计 {{ adminSummary.quantity || 0 }} 天</span
              ><span>已通过 {{ adminSummary.approved_count || 0 }} 条</span
              ><span>待审批 {{ adminSummary.pending_count || 0 }} 条</span>
            </div>
          </section>
          <section class="card admin-worklog-list-card">
            <div class="section-head">
              <div>
                <h2>全部工时明细</h2>
                <p class="muted">按工时开始日期倒序排列，操作仅管理员可见。</p>
              </div>
              <span class="tag teal"
                >总计 {{ adminSummary.quantity || 0 }} 天</span
              >
            </div>
            <div v-if="adminLoading" class="empty">正在查询工时明细…</div>
            <div v-else-if="!adminWorklogs.length" class="empty">
              <h2>没有匹配的工时</h2>
              <p>请调整日期、部门或人员条件后重新查询。</p>
            </div>
            <div v-else class="table-wrap">
              <table class="admin-worklog-table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>人员 / 部门</th>
                    <th>项目与工作内容</th>
                    <th>阶段</th>
                    <th>工时</th>
                    <th>审批人</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in adminWorklogs" :key="item.id">
                    <td class="admin-worklog-date">
                      {{ item.start_date
                      }}<small v-if="item.end_date !== item.start_date"
                        >至 {{ item.end_date }}</small
                      >
                    </td>
                    <td>
                      <strong>{{ item.user_name_snapshot }}</strong
                      ><small>{{ item.user_department_name }}</small>
                    </td>
                    <td class="admin-worklog-summary">
                      <strong>{{ item.project_name_snapshot }}</strong
                      ><span>{{ item.description }}</span>
                    </td>
                    <td>
                      {{ item.stage
                      }}<small>{{ workTypeLabel(item.work_type) }}</small>
                    </td>
                    <td class="admin-worklog-quantity">
                      <strong>{{ item.quantity }}</strong
                      ><small>天</small>
                    </td>
                    <td>{{ item.approver_name_snapshot || "未配置" }}</td>
                    <td>
                      <span class="tag" :class="statusClass(item.status)">{{
                        statusLabel(item.status)
                      }}</span
                      ><small v-if="item.serial_no">{{ item.serial_no }}</small>
                    </td>
                    <td>
                      <div class="table-actions">
                        <button
                          class="text-button"
                          @click="openAdminWorklogEditor(item)"
                        >
                          编辑</button
                        ><button
                          class="text-button danger-button"
                          @click="deleteAdminWorklog(item)"
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="admin-pagination">
              <span
                >第 {{ adminPage }} / {{ adminPageCount }} 页 · 共
                {{ adminWorklogTotal }} 条</span
              >
              <div class="admin-pagination-actions">
                <button
                  class="secondary"
                  :disabled="adminPage <= 1"
                  @click="changeAdminPage(adminPage - 1)"
                >
                  上一页</button
                ><button
                  class="secondary"
                  :disabled="adminPage >= adminPageCount"
                  @click="changeAdminPage(adminPage + 1)"
                >
                  下一页
                </button>
              </div>
            </div>
          </section>
          <div v-if="adminWorklogFormOpen" class="modal-backdrop">
            <section
              class="modal-card admin-worklog-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="admin-worklog-modal-title"
            >
              <div class="modal-head">
                <div>
                  <div class="eyebrow">ADMIN WORKLOG</div>
                  <h2 id="admin-worklog-modal-title">编辑工时</h2>
                  <p class="muted">
                    只修改工时内容，当前审批状态和审批记录保持不变。
                  </p>
                </div>
                <button
                  class="modal-close"
                  aria-label="关闭弹窗"
                  @click="resetAdminWorklogForm"
                >
                  ×
                </button>
              </div>
              <div class="form-grid">
                <label
                  >项目类型<select v-model="adminForm.project_type">
                    <option value="" disabled>请选择项目类型</option>
                    <option
                      v-for="option in activeConfigOptions('project_type')"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select></label
                ><label
                  >项目<select v-model.number="adminForm.project_id">
                    <option :value="0" disabled>请选择项目</option>
                    <option
                      v-for="project in adminFilteredProjects"
                      :key="project.id"
                      :value="project.id"
                    >
                      {{ project.code }} · {{ project.name }}
                    </option>
                  </select></label
                ><label
                  >项目阶段<select v-model="adminForm.stage">
                    <option value="" disabled>请选择项目阶段</option>
                    <option
                      v-for="option in activeConfigOptions('project_stage')"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select></label
                ><label
                  >工时类型<select v-model="adminForm.work_type">
                    <option value="" disabled>请选择工时类型</option>
                    <option
                      v-for="option in activeConfigOptions('work_type')"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select></label
                ><label
                  >工作状态<select v-model="adminForm.work_status">
                    <option value="" disabled>请选择工作状态</option>
                    <option
                      v-for="option in activeConfigOptions('work_status')"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select></label
                ><label
                  >开始日期<input
                    v-model="adminForm.start_date"
                    type="date" /></label
                ><label
                  >结束日期<input
                    v-model="adminForm.end_date"
                    type="date" /></label
                ><label
                  >工时天数<input
                    v-model.number="adminForm.quantity"
                    type="number"
                    min="0.25"
                    step="0.25" /></label
                ><label class="full"
                  >工作描述<textarea
                    v-model="adminForm.description"
                    placeholder="请输入工作内容"
                  ></textarea>
                </label>
              </div>
              <div class="form-footer">
                <button class="secondary" @click="resetAdminWorklogForm">
                  取消</button
                ><button class="primary" @click="saveAdminWorklog">
                  保存修改
                </button>
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
    <div
      v-if="mobileManagementOpen"
      class="mobile-management-backdrop"
      @click="mobileManagementOpen = false"
    ></div>
    <section
      v-if="mobileManagementOpen"
      class="mobile-management-sheet"
      aria-label="管理菜单"
    >
      <div class="mobile-sheet-head">
        <strong>管理菜单</strong>
        <button
          class="modal-close"
          aria-label="关闭管理菜单"
          @click="mobileManagementOpen = false"
        >
          ×
        </button>
      </div>
      <div class="mobile-sheet-grid">
        <button
          v-for="item in mobileManagementItems"
          :key="item.page"
          class="mobile-sheet-item"
          :class="{ active: page === item.page }"
          @click="go(item.page)"
        >
          <span>{{ item.glyph }}</span>{{ item.label }}
        </button>
      </div>
    </section>
    <div
      v-if="attachmentPreviewOpen"
      class="modal-backdrop attachment-preview-backdrop"
      @click.self="closeAttachmentPreview"
    >
      <section
        class="modal-card attachment-preview-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="attachment-preview-title"
      >
        <div class="modal-head">
          <div class="attachment-preview-title">
            <div class="eyebrow">CONTRACT ATTACHMENT</div>
            <h2 id="attachment-preview-title">{{ attachmentPreviewItem?.file_name }}</h2>
            <p class="muted">{{ attachmentPreviewItem ? attachmentKindLabel(attachmentPreviewItem.preview_kind) : "附件" }}预览</p>
          </div>
          <button class="modal-close" aria-label="关闭预览" @click="closeAttachmentPreview">×</button>
        </div>
        <div v-if="attachmentPreviewLoading" class="attachment-preview-state">
          <div class="loading-spinner"></div>
          <strong>正在生成预览…</strong>
        </div>
        <div v-else-if="attachmentPreviewError" class="attachment-preview-state error-state">
          <strong>暂时无法预览此附件</strong>
          <span class="muted">{{ attachmentPreviewError }}</span>
          <button v-if="attachmentPreviewItem" class="secondary" @click="downloadContractAttachment(attachmentPreviewItem)">下载原文件</button>
        </div>
        <iframe
          v-else-if="attachmentPreviewUrl"
          class="attachment-preview-frame"
          :src="attachmentPreviewUrl"
          :title="`预览 ${attachmentPreviewItem?.file_name || '合同附件'}`"
        ></iframe>
        <div class="attachment-preview-footer">
          <span class="muted">预览内容为只读视图，原文件不会被修改。</span>
          <div class="actions">
            <button v-if="attachmentPreviewItem" class="secondary" @click="downloadContractAttachment(attachmentPreviewItem)">下载原文件</button>
            <button class="primary" @click="closeAttachmentPreview">关闭</button>
          </div>
        </div>
      </section>
    </div>
    <nav
      class="mobile-nav"
      :class="{ 'mobile-nav-with-management': canManageAny }"
      aria-label="移动端导航"
    >
      <button
        class="mobile-nav-item"
        :class="{ active: page === 'workbench' }"
        @click="go('workbench')"
      >
        <span class="nav-glyph">⌂</span><span>工作台</span></button
      ><button
        class="mobile-nav-item"
        :class="{ active: ['worklogs', 'editor', 'detail'].includes(page) }"
        @click="go('worklogs')"
      >
        <span class="nav-glyph">▤</span><span>我的工时</span></button
      ><button
        class="mobile-nav-item"
        :class="{ active: ['approvals', 'approvalDetail'].includes(page) }"
        @click="go('approvals')"
      >
        <span class="nav-glyph">✓</span><span>工时审批</span
        ><b v-if="pendingApprovals.length">{{
          pendingApprovals.length
        }}</b></button
      ><button
        class="mobile-nav-item"
        :class="{ active: page === 'reports' }"
        @click="go('reports')"
      >
        <span class="nav-glyph">◫</span><span>工时看板</span></button
      ><button
        v-if="canManageAny"
        class="mobile-nav-item"
        :class="{
          active: [
            'projects',
            'integrations',
            'adminWorklogs',
            'personnelCosts',
            'adminPermissions',
            'configuration',
          ].includes(page),
        }"
        @click="mobileManagementOpen = !mobileManagementOpen"
      >
        <span class="nav-glyph">⋯</span><span>管理</span>
        <b v-if="mobileManagementItems.length">{{ mobileManagementItems.length }}</b>
      </button>
    </nav>
  </div>
</template>
