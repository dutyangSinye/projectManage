# v3.0.68 删除旧「人员成本」模块与日成本口径

日期：2026-09-11
状态：已发布至 `116.169.217.29:8088`（健康检查 `v3.0.68`，备份 `.backup-mcp-20260912-003321-20733fb6`，提交 `d770e6e`）
版本：`API_VERSION = "3.0.68"`

## 一、诉求

「人员成本那个功能直接删掉」，并确认连带把日成本口径一起删、历史日成本数据一并清理。

## 二、为什么可以删

日成本折算其实早在 **v3.0.61 就已停用**——`refresh_missing_worklog_cost()` 当时改成空实现，
注释写明「工时不再折算人员成本，人工成本由财务录入」。但以下残留没有清干净：

| 残留 | 说明 |
| --- | --- |
| `personnel_costs` 菜单 | 界面已隐藏，行仍在，授权也还在 |
| `GET/PATCH /api/v1/admin/personnel-costs` | 维护 `users.daily_cost` 的两个接口 |
| `users.daily_cost`、`worklogs.daily_cost_snapshot / cost_amount_snapshot` | 日成本字段 |
| `admin_permissions.can_manage_personnel_costs` | 管理员权限勾选项 |
| 工时负荷看板 `workload_report()` | **仍按 `daily_cost × 天数` 折算金额**，是漏网的一处 |
| 前端 `personnelCosts` 整页 | 页面、导航、移动端菜单、弹窗、类型 |

而项目人工成本早已由 **人工成本结转单**（`PERSONNEL_COST` 类型的成本单 → `project_ledger_entries`）
承接：项目详情的 `personnel_cost` 取的就是这个口径。两个口径并存只会让数字对不上。

## 三、变更清单

### 后端（`backend/app/`）

| 位置 | 变更 |
| --- | --- |
| `main.py` | 删除 `GET/PATCH /api/v1/admin/personnel-costs` 两个路由与 `personnel_cost_view()` |
| `main.py` | `RBAC_MENU_SEED` 移除 `personnel_costs`；新增 `PURGED_MENU_SEED` 与 `purge_personnel_cost_menu()`，启动时删除菜单行及其全部授权（`role_permissions` / `role_data_scopes` / `user_role_scopes`） |
| `main.py` | `seed_rbac()` 的角色授权本来就会跳过 `RETIRED_MENU_SEED`，菜单行删除后不再被重建 |
| `main.py` | `workload_report()` 不再按日成本折算：`project_actual_cost` 改为汇总期间内的 `PERSONNEL_COST` 流水，与项目明细口径一致；移除 `missing_cost_user_count` 指标 |
| `main.py` | `upgrade_schema()` 新增 `retired_personnel_cost_columns`，DROP 上述三个日成本列与 `can_manage_personnel_costs` |
| `schemas.py` | 删除 `PersonnelCostView / PersonnelCostList / PersonnelCostUpdate` |
| `db/models.py` | 删除 `User.daily_cost`、`Worklog.daily_cost_snapshot`、`Worklog.cost_amount_snapshot`、`AdminPermission.can_manage_personnel_costs` |

DROP COLUMN 同时清空了历史日成本值，符合「一并清理」的要求；SQLite 与 v3.0.62 删除成本分类列走的是同一条路径，已在生产验证过。

### 前端（`frontend/src/App.vue`）

- 删除 `personnelCosts` 整页模板（含新增日成本弹窗）与其全部 ref / reactive / 分页逻辑 / 接口调用；
- 删除 `Page`、`ManagementPermission`、`AdminPermissionField` 类型里的对应成员、`PersonnelCost*` 类型；
- 删除侧边导航「人员成本」按钮、移动端管理入口、默认落地页兜底、页面标题映射、`go()` 里的刷新分支；
- 删除管理员权限里的「人员成本」勾选项及其表单回填 / 清除逻辑；
- `rbac` 用户角色保存时的 resources 列表去掉 `personnel_costs`。

`frontend/src/styles.css` 中仅服务于该页的 `.personnel-cost-*` 规则已无元素使用，
但它们与 `@media` 嵌套和共享规则组交织，批量改写风险大于收益，本次保留（死样式不影响运行）。

## 四、影响面

- **工时负荷看板的金额口径变了**：原先按「日成本 × 工时天数」估算，现在只统计期间内**已复核通过的人工成本结转单**。
  没有结转单的项目，实际成本显示为 0——这是真实口径，不再是估算值。
- 项目明细、项目分析的人员成本口径不变（本来就取结转单）。
- 合同付款、项目费用、人工成本结转流程不受影响。

## 五、回归用例

`backend/tests/test_v3_personnel_cost_removed.py`（新增 5 项）：

- `personnel_costs` 不在 `RBAC_MENU_SEED` / `RETIRED_MENU_SEED`，菜单行已删除；
- 手工补写失效授权后，`purge_personnel_cost_menu()` 清干净，且不残留指向已删菜单的孤儿 `role_permissions`；
- `users` / `worklogs` / `admin_permissions` 的日成本列均已 DROP；
- FastAPI 路由里不再有 `/api/v1/admin/personnel-costs*`；
- `workload_report()` 源码不再出现 `daily_cost` 与 `missing_cost_user_count`，改为读 `PERSONNEL_COST` 流水。

`test_v3_rbac_retired_menus.py` 中引用 `personnel_costs` 的三处改用 `approval_workflows`（同为已下线菜单）。

后端全量测试由 76 项增至 **81 项**，全部通过；前端 `npm run build`（含 vue-tsc）通过。

发布后生产核对：`personnel_costs` 菜单行 0 条，失效授权与孤儿 `role_permissions` 均为 0，
四列日成本字段全部 DROP，users 22 / departments 12 / projects 12 / project_budget_items 96 / roles 9 保全。
