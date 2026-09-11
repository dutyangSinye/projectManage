# v3.0.65 权限保存修复与预算项入口收拢

日期：2026-09-11
状态：已实现，待发布
版本：`API_VERSION = "3.0.65"`

## 一、问题一：管理员管理 → 权限管理 保存失败

### 现象

生产日志出现：

```
INFO: 172.21.0.3:40046 - "PATCH /api/v1/admin/roles/2/permissions HTTP/1.1" 400 Bad Request
```

前端提示「权限保存失败」，且任何勾选都保存不进去。

### 根因

v3.0.58/3.0.63 起把不再作为入口的菜单停用（`personnel_costs`、`approval_workflows`），但**历史授权行保留在库里**：

| 表 | 残留数据（生产实测） |
| --- | --- |
| `role_permissions` | role 1 有 `approval_workflows`、`personnel_costs`；role 2、role 8 有 `personnel_costs` |
| `role_data_scopes` | 同样残留这两个资源 |

而：

1. `GET /api/v1/admin/roles/{id}/permissions` 的 `role_permissions_view()` 用**全量菜单**拼结果，把已停用菜单的授权也返回给前端；
2. `GET /api/v1/admin/menus` 只返回 `is_active = True` 的菜单，界面上**看不到**这些菜单，用户无法取消勾选；
3. 点保存时前端把整份 `permissions / scopes` 原样回传，后端 `update_role_permissions()` 用「启用菜单」字典去查，查不到就 `raise HTTPException(400, "INVALID_MENU")`。

结果就是：**保存整单被拒，而用户永远改不掉那条看不见的授权**——死锁。

### 修复

1. 新增 `drop_retired_menu_grants(db)`：启动时清理已下线菜单的历史授权（`role_permissions`、`role_data_scopes`、`user_role_scopes`）。在 `seed_data()` 里 `disable_retired_menus(db)` 之后调用，每次启动幂等执行。
2. `role_permissions_view()` 只回传**启用菜单**的权限与数据范围，界面拿不到就回传不了。
3. `update_role_permissions()` 遇到失效菜单/资源改为**跳过**（`continue`），不再让历史数据阻断整单保存；同类的 `update_user_roles()` 也跳过已下线资源。
4. 非法动作仍保留 `400 INVALID_MENU_ACTION`，避免真正填错时静默通过。

### 回归用例

`backend/tests/test_v3_rbac_retired_menus.py`：

- `budget_templates` / `personnel_costs` 属于已下线菜单且库中已停用；
- 手工插入失效授权后，`drop_retired_menu_grants()` 能清干净；
- `role_permissions_view()` 不再返回已下线菜单的权限与范围；
- 接口级：新建角色后回传含已下线菜单的 `permissions + scopes`，返回 200 且结果里只剩启用菜单。

## 二、问题二：预算项不再单独拎出来管理

### 调整

| 位置 | 变更 |
| --- | --- |
| 系统管理 / 基础配置 | **删除**「预算项模板」区块（经营/研发两个 tab 与编辑弹窗） |
| 菜单 `budget_templates` | 加入 `RETIRED_MENU_SEED`，随启动停用，权限管理里不再显示、历史授权同步清理 |
| 项目管理（列表操作列「预算项」、项目详情「维护预算项」） | 保留并作为**唯一**维护入口：金额、启用状态、备注、按模板补齐 |

### 为什么可以下线

- v3.0.62 起预算项已固定为统一 8 项，模板接口只剩「切换启用状态」有意义；
- 预算项模板接口本身鉴权用的是 `configuration` 资源，停用 `budget_templates` 菜单不影响任何接口；
- 项目侧 `GET/POST/PATCH /api/v1/projects/{id}/budget-items` 已具备完整维护能力（金额、启用、备注、按模板补齐），总预算由启用项合计自动回写到 `projects.budget_cost`。

### 前端清理

删除 `App.vue` 中的 `budgetTemplateLoading / budgetTemplateCategory / budgetItemTemplates / budgetTemplateFormOpen / editingBudgetTemplateId / budgetTemplateForm / visibleBudgetItemTemplates / budgetTemplateErrorMessage / loadBudgetItemTemplates / resetBudgetTemplateForm / editBudgetTemplate / saveBudgetTemplate` 以及 `BudgetItemTemplate` 类型；`refreshAdminConfiguration()` 不再拉取模板列表。预算项弹窗提示改为「预算项统一固定为 8 项，在这里维护本项目的预算金额与启用状态」。

保留 `budgetSourceLabel()`，项目预算项表格仍在使用。

## 三、验证

- 后端全量测试 **67 项通过**（新增 4 项）。
- 前端 `npm run build`（含 vue-tsc 类型检查）通过。
- 临时库复现脚本 `test-artifacts/_rbac_repro.py`：修复前「回传已停用菜单」返回 `400 INVALID_MENU`，修复路径已由回归用例覆盖。

## 四、发布注意

生产库 role 1/2/8 存在失效授权行，发布后首次启动会由 `drop_retired_menu_grants()` 自动清理，无需手工处理数据库。清理只影响已下线菜单（`personnel_costs`、`approval_workflows`、`budget_templates`）的授权，这些菜单界面已不可见、接口鉴权也不再依赖它们。
