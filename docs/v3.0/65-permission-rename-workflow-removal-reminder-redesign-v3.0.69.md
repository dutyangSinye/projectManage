# v3.0.69 权限管理改名、审批流程删除与填报提醒改版

- 日期：2026-09-12
- 版本：`API_VERSION = 3.0.69`
- 范围：后端 `backend/app/main.py`、`backend/app/schemas.py`；前端 `frontend/src/App.vue`、`frontend/src/styles.css`

## 1. 背景

三条来自使用现场的反馈：

1. 「管理员管理」这个名字对使用者不友好，它实际管的是角色、菜单、操作和数据范围，叫权限管理更准确。
2. 「审批流程」页面只剩一个只读的流程定义列表，没有任何可维护内容。费用与付款的流转已由审批岗位和一级费用复核接管，继续挂着只会让人以为还要去那里配流程。
3. 工时填报提醒的配置项混在「通知策略」的统一编辑弹窗里，时刻要手敲 `09:00, 17:30` 这样的逗号串，还要在弹窗里统一保存，看不出当前配置长什么样，也不好改。

## 2. 权限管理改名

### 后端

`RBAC_MENU_SEED` 中 `admins` 的 label 由「管理员管理」改为「权限管理」。`seed_rbac()` 每次启动都会回写 `menu.label`，因此生产库无需额外迁移脚本，重启即生效。

### 前端

改名位置（`frontend/src/App.vue`）：

| 位置 | 原值 | 新值 |
| --- | --- | --- |
| 管理权限勾选标签 | 管理员管理 | 权限管理 |
| 管理页面清单 | 管理员管理 | 权限管理 |
| 页面标题映射 | 管理员管理 | 权限管理 |
| 侧边导航 | 管理员管理 | 权限管理 |
| 两个页面 `<h1>` | 管理员管理 | 权限管理 |

页面 `<h1>` 上方的 eyebrow 统一改为 `ADMIN / ACCESS CONTROL`（原来其中一处直接写了中文「权限管理」）。

资源码 `admins`、字段名 `can_manage_admins`、接口路径均未变动，已配置的授权不受影响。

## 3. 删除审批流程功能

### 后端

- `RBAC_MENU_SEED` 移除 `approval_workflows`，加入 `PURGED_MENU_SEED`。
- `purge_personnel_cost_menu()` 更名为 `purge_deleted_menus()`，按 `PURGED_MENU_SEED` 清理，现覆盖 `personnel_costs` 与 `approval_workflows`：删除菜单行，并删除 `role_permissions`、`role_data_scopes`、`user_role_scopes` 中的对应记录。
- 删除 `GET /api/v1/admin/workflows` 接口及其视图函数 `workflow_definition_view()`，删除 `WorkflowDefinitionView` schema 与 `main.py` 中的导入。

### 保留部分

`workflow_definitions / workflow_versions / workflow_nodes / workflow_instances / workflow_tasks / workflow_action_logs` 六张表与项目费用提交时创建实例的逻辑**原样保留**。合同付款的历史流程实例已由 v3.0.5x 的迁移关闭，项目费用仍在生成实例；动这些表会影响历史单据的审批轨迹展示。本次删除的只是「配置入口」和「管理接口」。

### 前端

删除：

- `approvalWorkflows` 页面（原系统管理 → 审批流程，含流程节点轨道展示）
- 侧边导航项与 `canManage('approval_workflows')` 判断
- `Page` 联合类型、`ManagementPermission` 联合类型、页面标题映射中的对应项
- `ApprovalWorkflow` 类型定义、`approvalWorkflows` ref、`refreshApprovalWorkflows()`

## 4. 工时填报提醒改版

### 交互调整

填报提醒从「通知策略」的分组列表和统一编辑弹窗中移出，`integrationPolicyGroups` 直接跳过 `WORKLOG_FILL_REMINDER`，避免同一项两处可改。

集成与通知页新增独立的「工时填报提醒」卡片，三块内容横向排布（窄屏自动堆叠）：

1. **提醒时刻**：时刻以标签展示，编辑态下可点 `×` 删除；提供 `<input type="time">` 添加，另有 09:00 / 12:00 / 17:30 常用时刻快捷按钮。最多 6 个，自动排序去重，格式不符直接提示而不是写进库里。
2. **通知范围**：分段按钮切换 全部在职人员 / 指定部门 / 指定人员；部门和人员为勾选网格，人员支持按姓名或部门搜索。
3. **发送条件**：「只提醒当天还没有填报的人」开关 + 通知通道下拉。

底部显示「下次发送」预览（自动跳过周末，若当天时刻已过则顺延到下一个工作日）与当前覆盖范围。

### 保存方式

- 顶部开关点击即调用 `PATCH /api/v1/integrations/policies/WORKLOG_FILL_REMINDER` 保存，不需要进编辑态。
- 点「配置提醒」进入编辑态，改完点「保存设置」提交同一接口；保存前校验：至少一个提醒时刻、指定范围时至少选一项。
- 「立即发送一次」保留在只读态，策略停用时按钮禁用。

## 5. 验证

| 项目 | 结果 |
| --- | --- |
| `tsc -b`（frontend） | 通过 |
| `vite build` | 通过，564 modules，4.18s |
| 后端测试 | 83 项通过（新增 2 项） |

新增回归用例（`backend/tests/test_v3_rbac_retired_menus.py`）：

- `test_approval_workflows_menu_is_purged`：code 不在 `RBAC_MENU_SEED` 与 `RETIRED_MENU_SEED`，在 `PURGED_MENU_SEED`；`seed_rbac` + `purge_deleted_menus` 后菜单行与数据范围记录均为空。
- `test_admins_menu_is_renamed`：`admins` 菜单 label 为「权限管理」。

两个用例都会重新执行 `seed_rbac()`（会把菜单重新激活），因此用例末尾恢复 `disable_retired_menus` + `drop_retired_menu_grants`，避免污染共享临时库中的其它用例。

同步修改：`test_v3_personnel_cost_removed.py` 中的 `purge_personnel_cost_menu` 更名为 `purge_deleted_menus`；原用例里以 `approval_workflows` 作为「已下线菜单」样例的位置改用 `budget_templates`。

## 6. 部署注意

- 生产启动时会删除 `approval_workflows` 菜单行及其全部授权，属于预期行为，无需人工处理。
- 若某角色此前只靠 `approval_workflows` 授权，删除后该角色少一个勾选项，其它权限不受影响。
