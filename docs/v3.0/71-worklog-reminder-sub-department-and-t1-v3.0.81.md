# v3.0.81 工时提醒范围包含子部门 + T-1 补漏提醒

## 背景

生产上「工时填报提醒」配置为**指定部门 [5 产品研发部, 8 技术服务部]**，但李晓天（应用创新中心 dept 12）、
杜连腾（技术研发中心 dept 14）从未收到提醒。原因：两个中心都是**产品研发部的子部门**，
而 `worklog_reminder_recipients` 用的是 `User.department_id.in_(ids)` **精确匹配**，不含下级部门。

同时，当天提醒只能提醒「今天还没填」，对**昨天忘填**毫无办法，需要一条 T-1 补漏通道。

## 一、提醒范围包含子部门（行为变更）

- 后端新增 `expand_department_ids(db, department_ids)`：复用已有的 `DepartmentIndex`
  （层级靠 `parent_feishu_department_id` 表达，无整数父 id），把选中的部门递归展开为
  「自身 + 全部后代部门」。
- `worklog_reminder_recipients` 在 `target_scope == "DEPARTMENT"` 时先展开再查人，
  `ALL` / `USER` 范围行为不变（`USER` 仍为精确匹配）。
- 部门已被组织架构同步删除时按空集合处理，**不会退化成全量发送**。
- 前端「指定部门」文案改为「指定部门（含下级）」，避免管理员误判覆盖范围。

生效方式：无需改配置，升级后按现有配置自动覆盖子部门成员。

## 二、T-1 补漏提醒（新增策略）

| 项 | 说明 |
|---|---|
| 类型 | `WORKLOG_FILL_REMINDER_T1`（显示名「工时补填提醒（T-1）」） |
| 默认状态 | **停用**，管理员在集成与通知里启用后生效 |
| 默认时刻 | `09:30`，可配多个时刻（`09:00,17:30` 写法同样支持） |
| 默认范围 | 首次创建时**继承**已有「工时填报提醒」的 `target_scope / target_ids / only_unfilled / send_channel` |
| 触发日 | 周一至周五，命中窗口同为配置时刻起 10 分钟内 |
| 检查对象 | **上一个工作日**（`previous_workday`，跳过周六周日）是否已有工时记录 |
| 幂等键 | `worklog-fill-reminder-t1:{用户ID}:{目标日期}:{时刻}` |
| 渠道 | 与当天提醒一致：`app` / `webhook` / `mock` |
| 文案 | 「你这一天还没有填报工时，请在今天补填提交」，卡片为橙色标题，按钮「去补填工时」 |

扫描器 `reminder_scan_loop` 每次 tick 依次执行当天提醒与 T-1 提醒，两串逻辑互不影响。

手动触发：`POST /api/v1/integrations/worklog-fill-reminder-t1/run`
（策略未启用返回 409 `WORKLOG_FILL_REMINDER_T1_DISABLED`；force 运行的幂等键时刻为 `manual{HHMM}`，
所以手动可以重复发，自动扫描同一天同一时刻只发一次）。

## 三、改动清单

后端：

- `backend/app/main.py`
  - 新增常量 `WORKLOG_FILL_REMINDER_T1_TYPE`、`WORKLOG_FILL_REMINDER_T1_DEFAULT_TIME`
  - `DEFAULT_NOTIFICATION_POLICIES` 增加 T-1 策略（默认停用）
  - `seed_notification_policies`：T-1 首次创建时继承当天提醒的范围配置；已有的 T-1 缺时刻时补默认 `09:30`
  - 新增 `expand_department_ids` / `previous_workday` / `run_worklog_fill_reminder_t1_scan_once`
  - `worklog_reminder_recipients` 改为展开子部门
  - `reminder_scan_loop` 增加 T-1 扫描
  - 新增 `POST /api/v1/integrations/worklog-fill-reminder-t1/run`
- `backend/app/services/feishu.py`：新增 `notify_worklog_fill_reminder_t1`
- `backend/tests/test_v3_worklog_reminder_t1.py`：新增 15 条用例（工作日推算、子部门展开、
  子部门成员入列、已补填跳过、幂等、策略停用、飞书通道）

前端（`frontend/src/App.vue`）：

- 新增 `createReminderCard` 工厂，T-1 复刻当天提醒卡片的全部交互（时刻标签、范围分段按钮、
  部门/人员勾选、下次发送预览、立即发送一次），`t1Reminder` 用 `reactive` 包装以便在模板里解包 ref
- 通知策略分组里排除 T-1，避免同一项两处可改
- 通知类型中文名、策略说明补充 T-1

## 四、验证

- 后端全量测试 98 通过（新增 15 条）。
- `vue-tsc --noEmit` 仅剩 4 条历史告警（ECharts 类型、contractDetail 页面键、project.expense_budget、
  Page 类型），与本次改动无关。
- `vite build` 通过。
- 种子逻辑冒烟：生产库场景下（当天提醒已配 `DEPARTMENT [5,8]`）T-1 首次创建即为
  `DEPARTMENT [5,8] / 09:30 / 仅未填报 / app 通道`，默认停用。

## 五、遗留

- 法定节假日未纳入：T-1 只按周一至周五推算，遇到调休/法定假日仍会提醒，需要时再加节假日表。
- T-1 默认 `09:30` 与当天提醒 `16:30`，杨总可按实际作息在界面上调整。
