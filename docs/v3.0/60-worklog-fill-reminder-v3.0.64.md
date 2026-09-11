# 60 · 工时填报定时飞书提醒（v3.0.64）

- 版本：v3.0.64
- 日期：2026-09-11
- 依赖：58 号文档（阶段 2 前端与费用复核权限迁移，v3.0.63）
- 范围：新增「工时填报提醒」通知策略——每个工作日按配置时刻给配置范围内的人员发飞书提醒

## 1. 需求与口径

1. 系统定时提醒成员填报工时，提醒走飞书（通道沿用通知策略的 app / webhook / mock 三态）。
2. 提醒**时刻**和**通知对象**都在「集成与通知 → 通知策略」里配置，不写死在代码或环境变量里。
3. 时刻按**工作日**生效（周一至周五），与工时只统计工作日一致；周末和未配置时刻不发。
4. 默认只提醒**当天尚未填报**的人（`only_unfilled`），已填报的人自动跳过；可关闭该过滤。
5. 同一时刻、同一人、同一天只发一次，靠幂等键保证，重复扫描不会骚扰。

## 2. 数据模型（`notification_policies`）

新增 4 列，全部可空或带默认值，历史库直接 `ALTER TABLE ADD COLUMN`：

| 列 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `schedule_time` | VARCHAR(200) | `NULL` | 提醒时刻，多个用逗号分隔，如 `09:00,17:30`；留空回落到默认 `09:00` |
| `target_scope` | VARCHAR(20) | `ALL` | `ALL` 全部在职人员 / `DEPARTMENT` 指定部门 / `USER` 指定人员 |
| `target_ids` | TEXT | `NULL` | 范围对应的 id 数组 JSON 文本，如 `[3, 8]` |
| `only_unfilled` | BOOLEAN | `1` | 只提醒当天未填报的人 |

- 只有 `WORKLOG_FILL_REMINDER` 这一种策略使用这几个字段，其它策略保持空值不影响原有行为。
- 新策略默认 **停用**（`enabled=False`），管理员配置完成并点保存后才会真正发送，避免升级后立刻全员推送。

## 3. 扫描机制（`backend/app/main.py`）

- `reminder_scan_loop()` 拆成两条节奏：填报提醒每 60 秒检查一次（保证分钟级精度），合同/预算/收付款类扫描仍按 `REMINDER_SCAN_INTERVAL_SECONDS`（默认 600 秒）执行。
- `worklog_fill_reminder_due(policy, now)`：
  - 非工作日直接返回 `None`；
  - 命中条件 `0 <= 当前分钟数 - 配置时刻分钟数 < 10`（`WORKLOG_FILL_REMINDER_MATCH_WINDOW_MINUTES`），覆盖扫描间隔，保证配置时刻一定被扫到且只发一次。
- `worklog_reminder_recipients(db, policy)` 按 `target_scope` 解析在职人员；`DEPARTMENT` / `USER` 在目标为空时返回空集合，**绝不回落到全量**，避免误发全员。
- `has_worklog_on(db, user_id, day)` 用 `start_date <= day <= end_date` 判断，草稿也算已填报。
- `run_worklog_fill_reminder_scan_once(force=False)`：
  - 幂等键 `worklog-fill-reminder:{user_id}:{日期}:{时刻}`；手动触发使用 `manual{HHMM}` 作为时刻标签；
  - 发送结果写入 `system_notifications`（`source_type=WORKLOG_REMINDER`），通知中心可查、可重试；
  - 返回 `{scanned, sent, failed, skipped}`。

## 4. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/integrations/policies` | 返回体新增 `schedule_time` / `target_scope` / `target_ids` / `only_unfilled` |
| PUT | `/api/v1/integrations/policies` | 批量保存，新增字段可选；未提交的字段保持原值 |
| PATCH | `/api/v1/integrations/policies/{notification_type}` | 单个策略保存，同样支持新字段 |
| POST | `/api/v1/integrations/worklog-fill-reminder/run` | 按当前策略立即发送一次，用于配置后验证 |

- 权限：`integrations` 的 `CONFIGURE` 动作，与原有策略接口一致。
- 错误码：
  - `400 NOTIFICATION_POLICY_REMIND_TIME_INVALID`：提醒时刻不是合法的 `HH:MM` 列表；
  - `400 NOTIFICATION_POLICY_TARGET_IDS_INVALID`：`target_ids` 不是整数数组 JSON；
  - `409 WORKLOG_FILL_REMINDER_DISABLED`：策略未启用时调用立即发送。

## 5. 飞书消息（`backend/app/services/feishu.py`）

新增 `notify_worklog_fill_reminder(recipient_name, work_date, system_url, open_id, channel)`：

- mock 通道直接返回 `SENT`，便于本地和未配置飞书时验证链路；
- webhook 通道发文本；
- app 通道发蓝色交互卡片，按钮「去填报工时」直达 `{SYSTEM_PUBLIC_URL}/?page=worklogs`。

## 6. 前端（`frontend/src/App.vue`）

- 通知策略新增「填报提醒」分组，只读行显示：`工作日 09:00、18:00 · 全部在职人员 · 仅未填报`。
- 编辑弹窗对该策略展开配置块：
  - 提醒时间（文本，提示「每个工作日生效，多个时刻用逗号分隔」）；
  - 通知范围下拉（全部在职 / 指定部门 / 指定人员），选择范围后展示部门或人员多选；
  - 「只提醒当天未填报的人」勾选。
- 策略卡片新增「立即发送一次」按钮，调用 run 接口并提示成功/失败/跳过数量。
- 通知中心类型标签新增 `工时填报提醒`。

## 7. 兼容与迁移

- `upgrade_schema()` 的 `additions["notification_policies"]` 补齐 4 列；PostgreSQL 同样走标准 `ALTER TABLE`。
- `seed_notification_policies()` 新建策略时写入默认时刻 `09:00`；已存在的策略仅在时刻为空时补默认值，不覆盖管理员配置。
- 老前端提交 PUT 时不带新字段（值为 `None`），后端保持原值，不会出现配置被清空的情况。

## 8. 验收

| 项目 | 结果 |
| --- | --- |
| 后端全量测试 | 63 项通过（新增 `backend/tests/test_v3_worklog_fill_reminder.py` 10 项） |
| 接口冒烟 | GET 返回新字段；PUT 保存生效；非法时刻 400；立即发送 `sent=3`；停用后 409 |
| 扫描逻辑自检 | 工作日窗口命中、周末跳过、超窗口不命中、幂等第二次全跳过、已填报跳过 |
| 前端生产构建 | `pnpm build` 通过（tsc + vite） |
| 开发库保护 | 测试与冒烟均使用一次性临时库，本地开发库无新增列、无新策略 |
