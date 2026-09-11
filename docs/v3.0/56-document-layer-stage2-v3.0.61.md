# 56 · v3.0.61 阶段2：单据层改造（项目成本单 + 一级费用复核）

- 版本：`3.0.61`
- 范围：阶段 2（单据层），对应 `docs/v3.0/prototype-v3.0.59/` 原型与 53 号文档确认的新口径
- 前置：55 号文档（阶段 1 基础层：项目分类树、成本分类树、统一 8 项预算项）

## 1. 改因

53 号文档把「研发项目/经营项目两套预算项」统一为 8 项，并要求取消线上七级合同付款审批、改为一级费用复核。
55 号文档落地了基础层，但单据层仍停留在旧模型：

- 合同付款仍走 `WorkflowDefinition/Version/Node/Instance/Task` 七级审批，出纳末节点确认才计入已付；
- 项目费用是一套独立单据（`project_expenses`），带收款方、银行账号、付款状态、发票和三类费用类型；
- 人工成本由「工时 × 人员单天成本」自动折算，只在维护单天成本时回填，财务无法按项目 + 月份录入；
- 三套单据各有一条审批链，没有一个统一的费用复核待办。

阶段 2 把这三件事收敛成一套模型：**项目成本单（`project_cost_entries`）+ 一级费用复核**。

## 2. 数据模型

### 2.1 新增两张表

`project_cost_entries`（项目成本单）

| 字段 | 说明 |
| --- | --- |
| `cost_no` | 单号，项目费用 `CE-` 前缀，人工成本 `LC-` 前缀 |
| `entry_kind` | `PROJECT_EXPENSE` 项目费用单 / `PERSONNEL_COST` 人工成本结转单 |
| `project_id` | 归属项目 |
| `applicant_user_id` / `applicant_name` / `applicant_department_name` | 申请人与部门快照 |
| `budget_item_id` | 归集预算项 |
| `budget_item_name_snapshot` / `cost_major_snapshot` / `cost_minor_snapshot` | 预算项与成本分类快照 |
| `amount` | 金额 |
| `occurred_on` | 发生日期（项目费用必填） |
| `accounting_month` | 核算月份 `YYYY-MM`（人工成本必填） |
| `status` | `DRAFT` → `PENDING_REVIEW` → `APPROVED` / `REJECTED` → `REVERSED` |
| `version` | 乐观锁版本号 |
| `submitted_by/at`、`reviewed_by/at`、`review_comment` | 提交与复核轨迹 |

`project_cost_attachments`（项目成本单附件）：`entry_id`、`file_name`、随机 `storage_name`、`mime_type`、`file_size`、`uploaded_by`。

### 2.2 状态机

```
草稿 DRAFT ──提交──> 待复核 PENDING_REVIEW ──通过──> 已通过 APPROVED ──冲销──> 已冲销 REVERSED
   ▲                        │
   └────驳回 REJECTED <─────┘
```

- 只有 `DRAFT / REJECTED` 可修改、删除、加删附件；
- `PENDING_REVIEW` 只读，只允许复核人处理；
- 通过写流水并计入项目成本；驳回不计入；冲销追加反向流水，原流水保留。

## 3. 归集规则

| 单据类型 | 预算项 | 必填字段 | 成本分类 |
| --- | --- | --- | --- |
| 项目费用单 | 必须显式选择项目内启用中的预算项 | `occurred_on` | 按所选预算项的 `cost_minor_options` 候选范围选择，超范围返回 `INVALID_COST_MINOR` |
| 人工成本结转单 | 自动归入 `source_kind = "LABOR"` 的人工费用预算项 | `accounting_month` | 同上 |

同项目同核算月份允许录入多张人工成本单，列表返回 `same_month_count` 作为**提示**，不阻止录入。

## 4. 一级费用复核

### 4.1 岗位与权限

- 新增复核岗位 `COST_REVIEWER`（费用复核）与 `RECEIPT_REVIEWER`（收款复核）；
- 新增资源 `cost_review`（费用复核，`VIEW/APPROVE`）、`labor_costs`（人工成本结转）、`project_budget`（项目预算项）；
- 菜单下线：`personnel_costs`（人员成本）、`approval_workflows`（审批流程）。**注意**：两者仍保留在 `RBAC_MENU_SEED` 中，只是 `RETIRED_MENU_SEED` 会让 `disable_retired_menus()` 把菜单置为停用。原因见第 7 节。

复核资格判定 `cost_can_review()`：持 `cost_review` 的 `APPROVE`，**或**属于费用复核岗位有效成员。
同时 `effective_permission_details()` 会给岗位成员补上 `cost_review` 的 `VIEW/APPROVE`，
保证「只被拉进复核岗位、没有单独授权业务角色」的人也能看到费用复核入口。

### 4.2 三类单据统一待办

`GET /api/v1/cost-review` 把合同付款、项目费用单、人工成本结转单合并为一个待办队列：

- `tab=pending|processed|all`，`kind=PROJECT_EXPENSE|PERSONNEL_COST|PAYMENT`；
- 返回 `pending_count` / `processed_count`；
- **复核是岗位制全局职责，不叠加项目数据范围**，否则仅被纳入复核岗位的人会看不到任何待办。

### 4.3 合同付款改造

| 项目 | 改造前 | 改造后 |
| --- | --- | --- |
| 提交 | 生成 `WorkflowInstance`，状态 `PENDING_APPROVAL`，8 个节点 | 状态 `PENDING_REVIEW`，`version += 1`，不生成流程实例 |
| 通过 | 逐级推进，出纳末节点确认 | 一级复核通过即计入已付并写 `PAYMENT` 流水 |
| 驳回 | 动态工作流驳回 | `REJECTED`，不写流水 |
| 冲销 | 出纳确认后可冲销 | 复核人可冲销，追加 `REVERSAL` 流水 |
| 审批路径 | 多节点 `approval_path` | 单节点「费用复核」，`assignees` 为岗位成员 |
| 收款方 | 必须手填 | 留空时按支出合同的供应商主数据带出名称/开户行/账号 |

`payee_name` 由必填改为可选，`resolve_payment_payee()` 统一处理创建与修改两条路径。

### 4.4 迁移

`upgrade_schema()` 新增（幂等）：

```sql
UPDATE workflow_tasks SET status='CLOSED'
  WHERE status='PENDING' AND workflow_instance_id IN
        (SELECT id FROM workflow_instances WHERE document_type='PAYMENT');
UPDATE workflow_instances SET status='CLOSED', completed_at=... 
  WHERE document_type='PAYMENT' AND status='RUNNING';
UPDATE payments SET status='PENDING_REVIEW', current_workflow_instance_id=NULL
  WHERE status IN ('PENDING','PENDING_APPROVAL');
```

历史在途付款单据挂到新状态并解绑旧流程实例，否则 `can_approve` 会因为仍挂着工作流实例而拒绝复核人。
历史已生成的 `source_type='WORKLOG'` 人员成本流水**保留不删**，便于追溯。

## 5. 工时不再折算人员成本

| 位置 | 改造 |
| --- | --- |
| `approve_task()` | 只推进审批状态，不再写 `daily_cost_snapshot` / `cost_amount_snapshot`，不再创建 `PERSONNEL_COST` 流水 |
| `refresh_missing_worklog_cost()` | 退役为空实现（保留签名兼容调用点），返回 0 |
| `update_personnel_cost()` | 不再触发工时成本回填 |
| 迁移 | 删除原「按单天成本回填工时快照 + 补写流水」的四条语句 |

原逻辑会让「工时折算」与「财务录入」同时写入 `entry_type='PERSONNEL_COST'` 的流水，造成项目人工成本重复计算。

## 6. 冲销净额口径

新增 `reversal_target_types(rows)`：把 `REVERSAL` 流水按 `reversal_of_id` 归回被冲销的原始类型，
历史数据没有关联时按 `source_type` 回退（`PAYMENT` / `PROJECT_EXPENSE` / 其余按人工成本）。

`project_analysis_view()` 改为一次加载项目全部流水后按类型净额汇总，
修正了「成本单冲销不计入净额」的问题；成本单冲销流水同时带上 `budget_item_id`，
使 `project_budget_item_actuals()` 的预算项已发生额也能净额扣回。

## 7. 已退役菜单为什么必须留在 `RBAC_MENU_SEED`

`require_access()` 对未知资源直接 `raise RuntimeError`。阶段 2a 一度把
`personnel_costs` / `approval_workflows` 从 `RBAC_MENU_SEED` 移除，导致
`/api/v1/admin/personnel-costs*` 与审批流程只读接口在调用时 500。

现在的处理：两个 code 保留在 `RBAC_MENU_SEED`（可解析权限），由 `RETIRED_MENU_SEED` +
`disable_retired_menus()` 把菜单置为停用（不出现在导航）。系统管理员仍可访问这两个历史只读入口。

## 8. 接口清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/project-cost-entries` | 成本单分页列表（`entry_kind` 区分两类） |
| POST | `/api/v1/project-cost-entries` | 新建草稿 |
| GET/PATCH/DELETE | `/api/v1/project-cost-entries/{id}` | 详情 / 修改 / 删除 |
| POST | `/api/v1/project-cost-entries/{id}/submit` | 提交一级复核 |
| POST | `/api/v1/project-cost-entries/{id}/approve` | 复核通过 |
| POST | `/api/v1/project-cost-entries/{id}/reject` | 复核驳回 |
| POST | `/api/v1/project-cost-entries/{id}/reverse` | 冲销 |
| GET/POST | `/api/v1/project-cost-entries/{id}/attachments` | 附件列表 / 上传 |
| DELETE | `/api/v1/project-cost-attachments/{id}` | 删除附件 |
| GET | `/api/v1/project-cost-attachments/{id}/preview` | 预览（Office 转 PDF / 图片直出） |
| GET | `/api/v1/project-cost-attachments/{id}/download` | 下载 |
| GET | `/api/v1/cost-review` | 费用复核统一待办 |

### 错误码

`COST_ENTRY_KIND_INVALID`、`COST_ENTRY_KIND_IMMUTABLE`、`PROJECT_COST_ENTRY_NOT_FOUND`、
`PROJECT_COST_ENTRY_READ_ONLY`、`PROJECT_COST_ENTRY_NOT_RESUBMITTABLE`、
`PROJECT_COST_ENTRY_AMOUNT_REQUIRED`、`PROJECT_COST_ENTRY_ATTACHMENT_REQUIRED`、
`PROJECT_COST_ENTRY_NOT_PENDING_REVIEW`、`PROJECT_COST_ENTRY_NOT_APPROVED`、
`PROJECT_COST_ENTRY_VERSION_CONFLICT`、`PROJECT_COST_ATTACHMENT_NOT_FOUND`、
`PROJECT_COST_ATTACHMENT_FILE_NOT_FOUND`、`BUDGET_ITEM_REQUIRED`、`BUDGET_ITEM_INVALID`、
`BUDGET_ITEM_INACTIVE`、`LABOR_BUDGET_ITEM_MISSING`、`INVALID_COST_MINOR`、
`COST_REVIEW_FORBIDDEN`、`PAYMENT_NOT_PENDING_REVIEW`。

### 通知

| 类型 | 触发 | 接收人 |
| --- | --- | --- |
| `PENDING_PAYMENT_REVIEW` | 合同付款提交 | 费用复核岗位全员 |
| `PENDING_EXPENSE_REVIEW` | 项目费用单提交 | 费用复核岗位全员 |
| `PENDING_LABOR_REVIEW` | 人工成本结转单提交 | 费用复核岗位全员 |
| `COST_REVIEW_RESULT` | 复核通过 / 驳回 | 申请人 |

旧类型 `PENDING_PAYMENT` / `PENDING_RECEIPT` / `PAYMENT_RESULT` 等由 `RETIRED_NOTIFICATION_TYPES`
在播种时置为停用。通知重试统一走 `cost_review_notification_payload()` 解析来源单据口径。

## 9. 验收记录

| 项 | 结果 |
| --- | --- |
| `pytest -q` | 51 passed |
| `test-artifacts/smoke-stage1.py` | 39 项全通过 |
| `test-artifacts/smoke-stage2.py` | 64 项全通过 |
| `test-artifacts/smoke-migration-on-copy.py` | 13 项全通过 |
| 开发库 md5（跑测试前后） | 一致，测试未写入 `backend/data/workhours.db` |

回归用例改造：`backend/tests/test_v3_migration.py` 中 4 个断言七级付款审批的用例改写为一级复核口径，
新增 `test_payment_defaults_payee_from_supplier_bank_account`。

迁移前备份：`_archive/db-backup/workhours.pre-v3.0.61-stage2-20260911-115420.db`。

## 10. 待办

- **阶段 2 前端**：项目成本单页（项目费用 / 人工成本结转）、费用复核页（三页签）、
  合同付款页去掉多级审批轨道改为单节点、菜单补 `labor_costs` 与 `cost_review` 入口。
- 旧 `project_expenses` 单据与接口在新前端上线后下线（当前保留双向兼容）。
- `ProjectCreate.project_type` 仍为必填但语义已由 `project_category` 接管，待收敛。
- 开发库 8 个在册项目的 `project_sub_category` 是否回填，待杨总确认。
