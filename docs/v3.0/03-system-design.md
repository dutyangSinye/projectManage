# 综合项目管理系统系统设计

> 文档基线：v3.0.44 ｜ 日期：2026-09-06 ｜ 对应生产版本：v3.0.43 ｜ 状态：生产基线已验证；v3.0.44 方案已确认，高保真原型已完成，未开发

## 1. 设计目标

- 在不破坏现有工时、审批、飞书登录和 NAS 部署的前提下增加项目经营能力。
- 金额和状态变化可追溯、可重算、可冲销，不能靠页面临时累加。
- 权限同时作用于菜单、接口、数据范围和敏感字段。
- 合同阶段、合同收付款审批和提醒任务重复执行时不产生重复数据。
- v2.0 数据原地升级，部署失败可恢复旧容器和数据库备份。

## 2. 总体架构

```text
Vue 3 前端
  ├─ 工作台
  ├─ 工时模块
  ├─ 项目模块
  └─ 系统管理模块
        │ REST / Session
FastAPI 应用
  ├─ auth / org
  ├─ worklogs / approvals / reports
  ├─ projects / budgets
  ├─ counterparties / contracts
  ├─ receipts / payments / cashier approvals
  ├─ project ledger / dashboard
  ├─ permissions / config / audit
  └─ notifications / reminder scheduler
        │
SQLite + NAS 持久化数据卷
  ├─ workhours.db
  └─ uploads/
        │
飞书开放平台
  ├─ 免登与组织架构
  └─ 应用卡片消息
```

v3.0 继续部署为一个后端容器和一个 Nginx 前端容器。后端内部按领域拆分路由、服务和数据访问，不再继续扩大单个 `main.py`；前端按页面和业务组件拆分，不再继续扩大单个 `App.vue`。

## 3. 建议目录

```text
backend/app/
├─ main.py
├─ core/          # 配置、认证、权限、错误、数据库
├─ auth/
├─ org/
├─ worklogs/
├─ projects/
├─ counterparties/
├─ contracts/
├─ settlements/   # 收款、付款、出纳审批、冲销
├─ ledger/        # 项目经营流水和汇总
├─ notifications/
└─ audit/

frontend/src/
├─ app/
├─ api/
├─ components/
├─ modules/workbench/
├─ modules/worklogs/
├─ modules/projects/
├─ modules/system/
└─ styles/
```

模块化改造分阶段进行，避免一次性重写现有可用工时功能。

## 4. 核心数据模型

### 4.1 项目

`projects` 在现有字段上新增：

| 字段 | 类型 | 规则 |
|---|---|---|
| customer_id | FK nullable | 实施项目建议必填，引用启用客户 |
| start_date | date nullable | 项目开始日期 |
| end_date | date nullable | 不得早于开始日期 |
| description | text nullable | 项目说明 |
| version | int | 乐观锁版本 |

现有负责人、部门、审批人、上级领导、人天预算、成本预算、状态和是否可填报字段保留。

项目类型需要保存合同能力标记：

- `allow_income_contract`：是否允许收入合同和收款。
- `allow_expense_contract`：是否允许支出合同和付款。
- 实施项目两个标记固定为 `true`，同时支持对甲收款和对供应商付款。
- 研发、课题、观摩项目默认 `allow_income_contract=false`、`allow_expense_contract=true`，是否开放收入侧由需求确认。

### 4.2 往来单位

建议客户和供应商使用统一主体表，避免同一公司同时作为客户和供应商时重复维护。

`counterparties`：

- `id`
- `code`
- `name`
- `short_name`
- `roles`：`CUSTOMER`、`SUPPLIER`，允许同时拥有。
- `unified_social_credit_code`
- `status`：`ACTIVE`、`INACTIVE`
- `registered_address`
- `office_address`
- `license_file_id`
- `license_expiry_date`
- `invoice_title`
- `taxpayer_id`
- `invoice_address`
- `invoice_phone`
- `remarks`
- `created_by`、`created_at`、`updated_at`、`version`

`counterparty_contacts`：姓名、职务、手机、电话、邮箱、是否主要联系人。

`counterparty_bank_accounts`：

- 户名。
- 开户银行。
- 支行。
- 银行账号密文和末四位。
- 是否默认。
- 启用状态。

银行账号使用应用级密钥加密保存；列表只读取末四位，详情按权限解密。

### 4.3 公司银行账户

`company_bank_accounts` 由基础配置管理：公司名称、户名、开户行、支行、账号密文、末四位、用途、启用状态。收款和付款单必须保存账户快照。

### 4.4 项目合同

`project_contracts`：

| 字段 | 说明 |
|---|---|
| id | 主键 |
| project_id | 一个合同只属于一个项目 |
| contract_type | 固定 `INCOME` 或 `EXPENSE` |
| contract_no | 合同编号，启用数据中唯一 |
| name | 合同名称 |
| counterparty_id | 收入合同为客户，支出合同为供应商 |
| category_code | 可配置业务分类 |
| amount | Numeric(16,2)，大于 0 |
| currency | v3.0 固定 CNY |
| signing_date | 签订日期 |
| start_date / end_date | 合同有效期 |
| status | 状态机字段 |
| owner_user_id | 合同责任人，默认项目负责人 |
| attachment_file_id | 合同附件 |

合同附件实际使用独立表 `contract_attachments`，合同主表不直接存文件内容：

| 字段 | 说明 |
| --- | --- |
| contract_id | 所属合同 |
| file_name | 原始文件名，仅用于展示和下载 |
| storage_name | 数据卷内随机存储名，不接受客户端路径 |
| mime_type / file_size | 文件类型和字节数 |
| uploaded_by / created_at | 上传人和上传时间 |

附件接口统一沿用合同管理权限和项目数据范围。`.docx`、`.xlsx`、`.pptx` 预览时优先只读取 Office XML 文本并生成无脚本 HTML；PDF、图片以内嵌方式返回；`.doc`、`.xls`、`.ppt` 通过后端无界面 LibreOffice 转为 PDF 后以内嵌方式返回，转换失败时仍可下载原文件，不执行宏或嵌入对象。
| remarks | 备注 |
| version | 乐观锁 |

`contract_stages`：

- `contract_id`
- `sequence`
- `name`
- `planned_amount`
- `due_date`
- `remind_days_before`
- `reminder_paused`
- `cancelled_at`
- `version`

阶段的已收、已付和剩余金额不直接手工维护，由已确认且未冲销的收付款单汇总。

### 4.5 收款单

`receipt_orders`：

- 单号、项目、收入合同、合同阶段。
- 客户和付款方名称快照。
- 付款户名、付款开户行、付款账号密文和末四位。
- 公司收款账户 ID 和账户快照。
- 收款日期、金额、方式、银行流水号。
- 凭证附件、备注。
- 发起人、实际审批人、状态、版本。
- 提交、审批、驳回、冲销时间和原因。

### 4.6 付款单

`payment_orders`：

- 单号、项目、支出合同、合同阶段。
- 供应商 ID 和供应商快照。
- 收款户名、开户行、账号密文和末四位。
- 公司付款账户 ID 和账户快照。
- 付款日期、金额、方式、银行流水号、付款用途。
- 凭证附件、备注。
- 发起人、实际审批人、状态、版本。
- 提交、审批、驳回、冲销时间和原因。

### 4.7 出纳审批任务

`cashier_approval_tasks`：

- `document_type`：`RECEIPT`、`PAYMENT`、`RECEIPT_REVERSAL`、`PAYMENT_REVERSAL`。
- `document_id`
- `version`
- `approver_user_id`
- `status`
- `comment`
- `submitted_at`、`processed_at`
- 唯一约束：`document_type + document_id + version`

出纳人员来自权限配置。任务创建时保存实际审批人快照，后续角色人员变化不修改已提交任务；系统管理员提供待办转交操作。

### 4.8 项目经营流水

`project_ledger_entries` 是项目经营数字的权威变化记录：

| 字段 | 说明 |
|---|---|
| project_id | 项目 |
| entry_type | `RECEIPT`、`PAYMENT`、`PERSONNEL_COST`、`REVERSAL` |
| source_type / source_id | 来源单据或工时 |
| amount | 正金额，方向由类型决定 |
| occurred_on | 业务日期 |
| reversal_of_id | 冲销时关联原流水 |
| idempotency_key | 唯一，防止重复记账 |
| created_at | 创建时间 |

流水只追加不更新。收付款冲销增加反向流水，不删除原流水。

人员成本流水在工时审批通过时生成，保存：

- 工时天数。
- 单天成本快照。
- 人员成本金额。
- 用户和工时来源。

工时被合法更正或冲销时生成反向人员成本流水。

### 4.9 附件

`files` 保存文件元数据，实际文件保存到 `/app/data/uploads/{year}/{month}/`。字段包括原始文件名、存储名、MIME、大小、SHA-256、上传人和业务用途。

允许类型初步限定为 PDF、PNG、JPG、JPEG，单文件建议不超过 20MB。下载必须经过认证和权限检查，Nginx 不直接暴露上传目录。

## 5. 状态机

### 5.1 合同

```text
DRAFT → ACTIVE → COMPLETED
   └──────→ VOID
ACTIVE ───→ VOID（无未冲销收付款且填写原因）
```

- 草稿可编辑和删除。
- 生效前阶段金额合计必须等于合同金额。
- 已有收付款时不能作废合同，只能先处理相关单据。
- 完成状态在所有阶段余额为 0 时自动建议，最终可由有权限人员确认。

### 5.2 合同阶段

阶段状态由日期和结算金额计算，不直接编辑：

```text
未到期 PLANNED
即将到期 UPCOMING
已到期 DUE
部分完成 PARTIALLY_SETTLED
已完成 SETTLED
已逾期 OVERDUE
已取消 CANCELLED
```

状态优先级：取消 > 完成 > 部分完成 > 逾期 > 即将到期 > 未到期。

### 5.3 收款单和付款单

```text
DRAFT → PENDING_APPROVAL → APPROVED
                         ↘ REJECTED → DRAFT → PENDING_APPROVAL
APPROVED → REVERSAL_PENDING → REVERSED
                            ↘ REVERSAL_REJECTED → APPROVED
```

- `APPROVED` 事务中同时更新单据状态、审批任务和经营流水。
- `REVERSED` 事务中生成反向流水并恢复阶段剩余金额。
- 不允许从 `APPROVED` 直接改回草稿。

## 6. 金额口径与计算

所有金额使用 `Decimal` 和数据库 `Numeric`，接口用字符串或两位小数序列化，禁止二进制浮点累加。

```text
已收 = Σ 已确认收款 - Σ 已确认收款冲销
已付 = Σ 已确认付款 - Σ 已确认付款冲销

阶段应收 = max(0, 到期收入阶段计划金额 - 阶段已收)
阶段应付 = max(0, 到期支出阶段计划金额 - 阶段已付)

收入 = 已收
人员成本 = Σ 已审批工时的人员成本流水
外部成本 = 已付
总成本 = 人员成本 + 外部成本
毛利 = 收入 - 总成本
毛利率 = 收入 > 0 ? 毛利 / 收入 : null
```

预算执行：

```text
人天执行率 = 已审批工时天数 / 人天预算
成本执行率 = 总成本 / 成本预算
```

预算为 0 时执行率显示“未设置”，不能显示 0%。

## 7. 审批事务与并发

合同收付款审批通过必须在单个数据库事务中完成：

1. 校验当前用户是任务实际审批人且具有出纳权限。
2. 校验任务和单据仍为待审批，版本一致。
3. 重新计算阶段剩余金额。
4. 校验本次金额不超过剩余金额。
5. 更新任务和单据状态。
6. 创建唯一经营流水。
7. 写审计日志。
8. 提交事务后发送飞书结果通知。

通知失败不回滚已完成审批。重复审批请求依靠版本号、状态和流水幂等键返回原结果，不创建第二笔流水。

## 8. 权限模型

### 8.1 功能权限

| 权限代码 | 说明 |
|---|---|
| worklog_ledger | 工时台账管理 |
| project_manage | 项目主数据管理 |
| contract_manage | 合同新增编辑 |
| receipt_manage | 收款单新增和查看 |
| payment_manage | 付款单新增和查看 |
| cashier_approve | 收付款及冲销审批 |
| project_dashboard | 项目看板 |
| project_view_all | 查看全部项目 |
| counterparty_manage | 客户和供应商管理 |
| personnel_cost_manage | 人员成本维护 |
| integration_manage | 集成与通知 |
| admin_manage | 管理员管理 |
| config_manage | 基础配置 |

### 8.2 数据范围

- `OWNED_PROJECTS`：项目负责人是当前用户。
- `DEPARTMENT_PROJECTS`：指定部门及全部下级部门。
- `ALL_PROJECTS`：全部项目。

数据范围由后端统一构造查询条件，前端传入的项目 ID 不能扩大范围。

### 8.3 字段权限

- 普通项目成员：不显示完整银行账号、人员单天成本和系统权限。
- 项目负责人：可查看负责项目的经营金额，银行账号只显示后四位。
- 收付款编辑人员：编辑期间可查看本单完整账户。
- 出纳：审批期间可查看完整账户和凭证。
- 人员成本管理员：可查看和编辑单天成本。
- 系统管理员：不自动获得完整银行账号，仍需对应业务权限。

## 9. API 分组

### 9.1 工作台

- `GET /api/v1/workbench/owner-summary`
- `GET /api/v1/workbench/employee-summary`
- `GET /api/v1/workbench/reminders`

两个摘要独立请求，局部失败不阻塞整页。

### 9.2 项目

- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{id}`
- `PATCH /api/v1/projects/{id}`
- `GET /api/v1/projects/{id}/overview`
- `GET /api/v1/projects/{id}/ledger`
- `GET /api/v1/projects/{id}/audit`

### 9.3 往来单位

- `GET/POST /api/v1/counterparties`
- `GET/PATCH /api/v1/counterparties/{id}`
- `POST /api/v1/counterparties/{id}/contacts`
- `POST /api/v1/counterparties/{id}/bank-accounts`
- `PATCH /api/v1/counterparties/{id}/status`

接口按角色过滤客户或供应商。

### 9.4 合同与阶段

- `GET/POST /api/v1/contracts`
- `GET/PATCH /api/v1/contracts/{id}`
- `POST /api/v1/contracts/{id}/activate`
- `POST /api/v1/contracts/{id}/void`
- `POST/PATCH /api/v1/contracts/{id}/stages`
- `GET /api/v1/contract-stages/due`

### 9.5 收款与付款

- `GET/POST /api/v1/receipts`
- `GET/PATCH /api/v1/receipts/{id}`
- `POST /api/v1/receipts/{id}/submit`
- `POST /api/v1/receipts/{id}/approve`
- `POST /api/v1/receipts/{id}/reject`
- `POST /api/v1/receipts/{id}/request-reversal`
- 付款接口使用同样结构：`/api/v1/payments/...`
- `GET /api/v1/cashier-approvals/pending`
- `GET /api/v1/cashier-approvals/processed`

### 9.6 看板

- `GET /api/v1/reports/workload`：仅工时口径。
- `GET /api/v1/reports/projects`：项目经营汇总。
- `GET /api/v1/reports/projects/export`：项目经营明细导出。
- `GET /api/v1/projects/board/options?data_scope=OWNED|ALL`：返回按项目看板数据范围过滤的项目选择项；不返回已删除项目。

项目看板接口必须返回统计口径时间、数据范围和金额来源数量，便于对账。

## 10. 提醒任务

使用可靠计划任务定期扫描合同阶段：

1. 查询启用合同和未完成阶段。
2. 根据到期日计算即将到期或逾期状态。
3. 生成 `reminder_events`，幂等键包含阶段、提醒类型和业务日期。
4. 创建通知并发送飞书卡片。
5. 保存发送结果和重试次数。

建议默认每 10 分钟扫描一次，但同一提醒每天最多发送一次。任务重启或重复执行不能重复发送同一业务日提醒。

提醒接收人默认项目负责人。后续可在合同上增加协同接收人，不纳入首版强制字段。

## 11. 基础配置边界

### 可动态维护

- 项目类型及能力标记：是否允许收入合同、是否允许支出合同、是否展示收入指标；实施项目固定同时允许两类合同。
- 项目业务状态的显示名称和排序。
- 合同业务分类。
- 收付款方式。
- 项目阶段、工时类型、执行状态。
- 默认提醒天数。
- 公司银行账户。

### 固定状态机

- 合同类型：收入、支出。
- 合同状态。
- 合同阶段结算状态。
- 收款单、付款单和审批任务状态。
- 经营流水类型。

固定状态机代码不可通过后台删除或任意新增，否则会破坏业务逻辑。

## 12. 通知契约

新增通知类型：

- `RECEIPT_APPROVAL_SUBMITTED`
- `PAYMENT_APPROVAL_SUBMITTED`
- `SETTLEMENT_APPROVED`
- `SETTLEMENT_REJECTED`
- `CONTRACT_STAGE_UPCOMING`
- `CONTRACT_STAGE_OVERDUE`
- `PROJECT_BUDGET_WARNING`

飞书卡片不展示完整银行账号、营业执照或凭证内容。卡片 URL 使用现有 AppLink WebView 方案，进入详情后再次校验登录和权限。

## 13. 数据迁移

### 13.1 保留数据

- 用户、部门和飞书身份。
- 项目及负责人、审批人、上级领导。
- 工时、审批任务、通知和审计。
- 人员单天成本。
- 管理员权限和基础配置。

### 13.2 迁移步骤

1. 停止写入并备份数据库和上传目录。
2. 创建 v3.0 新表和新增字段，迁移脚本必须幂等。
3. 为现有项目补充 `version`，客户保持空值。
4. 为现有已审批工时生成或补齐人员成本快照和经营流水。
5. 将现有权限映射到新权限，系统管理员保留全部管理能力。
6. 校验项目已发生人天和人员成本与 v2.0 报表一致。
7. 启动新版本并执行冒烟测试。

现有项目成本预算和人员成本不删除。历史成本若缺少审批时单价，迁移时使用当前单价并标记 `MIGRATED_CURRENT_RATE`，看板允许识别迁移口径。

### 13.3 回滚

- 发布前保留数据库、上传目录和部署文件备份。
- v3.0 迁移只新增表和字段，不删除 v2.0 字段。
- 回滚时恢复旧数据库备份和旧容器，避免旧代码读取部分迁移数据。

## 14. 非功能要求

### 性能

- 常用列表 P95 小于 500ms。
- 工作台摘要 P95 小于 800ms。
- 项目看板默认范围 P95 小于 2 秒。
- 所有大列表服务端分页，默认 20 条，最大 200 条。

### 安全

- Session、CSRF、权限和数据范围沿用并加强现有后端校验。
- 银行账号加密密钥只存 NAS 环境变量，不进入源码、镜像和日志。
- 附件下载使用授权接口，不暴露真实路径。
- 导出同样校验数据范围和字段权限。

### 可用性

- 所有列表、详情和表单具备加载、空、错误、成功状态。
- 审批按钮防重复点击。
- 到期任务和飞书通知失败可重试。
- 系统健康检查增加数据库和上传目录可写性检查。

## 15. 测试策略

### 单元测试

- 应收应付、部分收付、冲销、毛利和预算执行计算。
- 合同和单据状态机。
- 部门树和项目数据范围。
- 银行账号脱敏和字段权限。
- 提醒幂等键和到期日期计算。

### API 测试

- 项目、往来单位、合同、阶段和收付款 CRUD。
- 出纳审批、驳回、重提、冲销。
- 越权访问和跨项目访问。
- 重复审批和并发超额付款。
- 附件权限和非法文件类型。

### 端到端测试

1. 实施项目 → 收入合同 → 阶段 → 收款 → 出纳审批 → 收入侧看板更新。
2. 同一实施项目 → 支出合同 → 阶段 → 付款 → 出纳审批 → 支出侧看板更新。
3. 研发项目 → 支出合同 → 阶段 → 付款 → 出纳审批 → 成本更新。
4. 员工工时 → 审批通过 → 人天和人员成本更新。
5. 阶段到期 → 飞书提醒 → 详情跳转。
6. 已确认收付款 → 冲销 → 应收应付和看板恢复。

### 对账测试

任一项目的看板指标必须能由经营流水和阶段明细重新计算得到。发布验收随机抽取不少于 5 个项目逐笔对账。

## 16. 主要风险

| 风险 | 影响 | 控制措施 |
|---|---|---|
| 收入成本口径未确认 | 看板数字反复修改 | 开发前冻结现金口径 |
| 出纳单人审批不可用 | 单据积压 | 配置备用出纳和任务转交 |
| 银行账户泄露 | 严重安全问题 | 加密、脱敏、字段权限和审计 |
| 重复审批或并发超额支付 | 金额错误 | 事务、版本号、唯一流水和余额复核 |
| 提醒重复发送 | 用户干扰 | 业务日期幂等键 |
| 单文件继续膨胀 | 后续维护困难 | 按领域渐进拆分 |
| SQLite 写并发增加 | 锁等待 | WAL、短事务；达到阈值后迁移 PostgreSQL |

## 17. 开发门禁

以下内容确认前不开始数据库和接口编码：

1. 现金口径及毛利公式。
2. 收付款部分结算和冲销规则。
3. 出纳本人发起时的审批规则和备用出纳。
4. 非实施项目类型是否允许收入合同；实施项目固定允许收入合同和支出合同。
5. 客户、供应商和合同字段。
6. 权限矩阵和数据范围。
7. 工作台、项目详情、合同、合同收付款审批和项目看板原型。

## 18. 当前基线同步说明

本设计已按当前生产实现补齐并确认：本地单条工时审批任务、项目类工时二级审批、非项目工时部门审批、预立项工时转管理工时、工时月度台账、国家法定工作日历、飞书应用消息通知、角色/菜单/操作/数据范围 RBAC、部门树下级包含规则、统一 8 项预算项、人工成本结转、项目费用、费用复核、合同收入/支出双侧、阶段余额核销、收付款账户快照、创建前暂存附件、通知策略统一保存、应用时区 `Asia/Shanghai`、SQLite 持久化和 Docker Compose 发布。

文档前面的“开发门禁”保留为历史设计流程记录；当前版本对应接口和数据模型已经实现，后续修改须同步更新本文档、变更记录和测试报告。系统当前不创建真实飞书审批实例，不使用审批回调作为业务闭环，飞书仅负责免登、组织架构和应用消息通知。当前生产范围、已实现/未实现边界和文档对齐状态以 [82-current-baseline-v3.0.91.md](82-current-baseline-v3.0.91.md) 为准。

## 19. v3.0.44 项目费用与工作流架构扩展

新增项目费用域和轻量工作流域。费用域负责差旅、无合同发票、其他费用、费用附件、费用支付和项目流水；工作流域负责审批岗位、流程定义、不可变发布版本、流程实例、审批任务和操作日志。

核心技术约束如下：

- 审批岗位与 RBAC 角色分离，前者决定任务分给谁，后者决定菜单、操作和数据范围。
- 项目审批人、飞书直属上级和审批岗位在提交前解析，缺失任何必需审批人则禁止提交。
- 单据提交时固化工作流版本及审批人快照，配置变更不影响运行实例。
- 最后一个业务审批节点通过时写入唯一费用成本流水；出纳支付写资金流水，不重复计入成本。
- 审批、成本确认和支付均使用事务、乐观锁和幂等键，防止重复审批及重复记账。
- 飞书消息在业务事务提交后发送，失败进入现有通知中心，不回滚单据状态。

数据表、状态机、事务边界、API 契约和测试要求见 [41-project-expense-workflow-design-v3.0.44.md](41-project-expense-workflow-design-v3.0.44.md)。

