# 58 · 阶段 2 前端与费用复核权限迁移（v3.0.63）

- 版本：v3.0.63
- 日期：2026-09-11
- 依赖：57 号文档（预算项与成本分类合并，v3.0.62）、56 号文档（阶段 2 单据层，v3.0.61）
- 范围：前端补完阶段 2 的三块页面 + 后端补一条一级费用复核的权限迁移

## 1. 为什么补这一版

v3.0.61 已经把后端改成一级费用复核，v3.0.62 又把预算项与成本分类合并。但前端仍停留在旧的
`project_expenses` 页面，造成一个真实阻塞：

- 合同付款提交后状态是 `PENDING_REVIEW`，不再生成工作流实例，因此不会出现在老的「审批待办」里；
- 新的 `/api/v1/cost-review` 没有前端入口；
- 结果就是**付款单提交后无人可处理**。

本版把前端补齐，并把权限一次性授权到位，保证升级后复核链路可用。

## 2. 前端改动（`frontend/src/App.vue`）

### 2.1 契约层

- `Page` 新增 `"laborCosts"`、`"costReview"`；`ManagementPermission` 新增 `"labor_costs"`、`"cost_review"`。
- 新增类型 `ProjectCostEntry` / `ProjectCostEntryList` / `CostReviewItem` / `CostReviewList`，
  字段与后端 `schemas.py` 一一对应。
- `attachmentApiName()` 增加 `entry_id` 分支 → `project-cost-attachments`，成本单附件可预览/下载。
- `expenseStatusLabel()` / `expenseStatusClass()` 增加 `PENDING_REVIEW`（待复核）。

### 2.2 页面

| 页面 | 路由 | 说明 |
| --- | --- | --- |
| 项目费用 | `projectExpenses` | 对接 `GET /api/v1/project-cost-entries?entry_kind=PROJECT_EXPENSE` |
| 人工成本结转 | `laborCosts` | 同一模板块，按 `page` 切换 `entry_kind=PERSONNEL_COST` |
| 成本单详情 | `expenseDetail` | 单节点「费用复核」轨道 + 复核/驳回/冲销动作条 |
| 费用复核 | `costReview` | 三页签（待复核 / 已处理 / 全部），对接 `GET /api/v1/cost-review` |

- 两页共用一套筛选与表格，列按类型切换：项目费用显示「发生日期」，人工成本结转显示「会计期间」。
- 表单按 `entry_kind` 切换必填项：`occurred_on` 与 `accounting_month` 二选一，由后端 `@model_validator` 兜底。
- 预算项改为可「不归集」（`budget_item_id` 传 `null`），人工成本结转默认归到人工费用预算项。
- 详情页动作条按状态切换：草稿/驳回 → 提交复核；待复核且有权 → 通过/驳回；已通过 → 冲销。
- 费用复核列表里付款单与成本单混排，通过 `kind === "PAYMENT"` 分流到付款详情或成本单详情。

### 2.3 合同付款改为一级复核口径

- 详情「当前节点」默认文案由「出纳审批」改为「费用复核」，提示语改为「复核通过后计入项目成本与已付」。
- 通过按钮固定为「复核通过」，时间线末节点文案改为「等待费用复核」。
- 列表状态筛选项加 `PENDING_REVIEW`（待复核），「待我审批」改为「待我复核」。
- 审批轨道仍渲染 `approval_path`，后端无实例时返回单节点「费用复核」，前端无需特殊分支。

### 2.4 项目详情「费用」页签

表头与字段同步到成本单口径：单据编号 / 预算项 / 申请人 / 发生日期 / 金额 / 状态。

## 3. 后端改动（`backend/app/main.py`）

新增幂等迁移 `grant_cost_review_permissions(db)`，在 `disable_retired_menus(db)` 之后执行：

1. 给**原本就能审批合同付款或项目费用**的角色补发 `cost_review: [VIEW, APPROVE]`。
2. 给同一批角色补发 `labor_costs`，动作集合沿用其 `project_expenses` 的动作（与菜单可用动作取交集）。
3. 若不存在「费用复核」岗位（`COST_REVIEWER`），则创建，并把现有「会计」岗位（`ACCOUNTANT`）成员纳入。

设计取舍：

- 只补发给已有 `APPROVE` 能力的角色，不泛化到只读角色 —— 复核是审批动作，不该给所有人。
- 全部走「不存在才写入」，管理员后续在界面上的调整不会被覆盖。
- 费用复核岗位制仍然生效：`effective_permission_details()` 会为岗位成员补 `cost_review` 权限，
  本迁移只是保证升级瞬间就有人能处理在途单据。

## 4. 部署前检查（生产环境实测）

| 项 | 结果 |
| --- | --- |
| 生产地址 | `116.169.217.29:8088`（公网），升级前版本 3.0.60 |
| SQLite | 3.46.1，支持 `DROP COLUMN` |
| 数据卷 | `xinye-project-management_xinye-workhours-data` |
| RBAC 重置标记 | `RBAC_ROLE_RESET_V3_0_24` 已存在 → `reset_rbac_configuration()` 不会清空自定义角色 |
| 生产数据量 | 项目 0 / 合同 0 / 付款 0 / 工时 0 / 费用 0；用户 22、客户 2、供应商 31、部门 12 |
| 生产库备份 | `_archive/prod-backup/workhours-predeploy-v3.0.62-20260911-152354.db` |

升级预演（在生产库副本上执行 `seed_data()`，脚本 `test-artifacts/_prod_migration_rehearsal.py`）：

- 迁移无异常；
- 5 个角色获得 `cost_review`，5 个角色获得 `labor_costs`；
- 新建「费用复核」岗位，成员 = 原会计岗位成员（闫家蜜）；
- 成本分类配置 0 行，7 张表相关列全部下线；
- 业务数据无丢失。

## 5. 验收

| 项 | 结果 |
| --- | --- |
| `pytest -q` | 51 passed |
| `pnpm build`（含 `tsc -b`） | 通过 |
| 本地 `/health` | 3.0.63 |
| `/api/v1/project-cost-entries`（两类） | 200 |
| `/api/v1/cost-review?tab=all` | 200，待复核 5 / 已处理 1 |
| `/api/v1/admin/menus` | 20 个菜单，含 `labor_costs` 与 `cost_review` |

## 6. 遗留

- 旧的 `project_expenses` 接口与 `ProjectExpense` 前端类型仍在，仅保留兼容，不再被新页面引用。
- 原型目录 `docs/v3.0/prototype-v3.0.59/` 仍写着两套预算项口径，待同步为统一 8 项。
- `ProjectCreate.project_type` 仍必填，语义已由 `project_category` 接管，待收敛。
