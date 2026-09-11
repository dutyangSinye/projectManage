# 综合项目管理系统最新系统设计

> 版本：v3.0.45  
> 日期：2026-09-07  
> 状态：与当前实现对应的设计基线  
> 对应需求：[10-latest-requirements-v3.0.9.md](10-latest-requirements-v3.0.9.md)

项目费用、审批岗位、版本化流程、审批实例、任务、支付与冲销的数据模型和接口增量见 `41-project-expense-workflow-design-v3.0.44.md` 与 `42-project-expense-workflow-implementation-v3.0.45.md`。

## 1. 设计原则

1. 以项目为业务主线，把工时、合同、阶段、收付款、预算、成本和提醒关联起来。
2. 以飞书组织架构作为人员来源，以本系统作为业务数据和审批状态的权威来源。
3. 所有金额由后端按统一口径计算，前端只负责展示和筛选。
4. 审批通过后才产生经营事实；已确认事实不能通过普通编辑直接覆盖。
5. 页面权限、接口权限、数据范围和敏感字段权限必须同时校验。
6. 发布文件与 SQLite 数据卷分离，部署失败可以恢复文件和容器，不删除业务数据。

## 2. 总体架构

```text
飞书开放平台
  ├─ 用户身份 / 免登
  ├─ 组织架构 / 人员部门
  └─ 应用消息 / 互动卡片
          │ HTTPS API
          ▼
Vue 3 + Vite 前端
  ├─ 工作台
  ├─ 工时管理
  ├─ 项目管理
  └─ 系统管理
          │ REST / Session Cookie
          ▼
FastAPI 后端
  ├─ 认证与组织同步
  ├─ 权限与管理员
  ├─ 工时与审批
  ├─ 项目与预算
  ├─ 合同与阶段
  ├─ 收款与付款
  ├─ 客户与供应商
  ├─ 项目经营汇总
  ├─ 附件与预览
  ├─ 提醒与飞书通知
  └─ 审计日志
          │ SQLAlchemy / SQLite
          ▼
NAS Docker 数据卷
  ├─ workhours.db
  └─ uploads/
```

运行形态保持一个后端容器和一个 Nginx 前端容器：Nginx 提供静态页面并反向代理 `/api` 和 `/health`；后端使用 `SQLite + WAL`，附件保存到 Docker 数据卷；LibreOffice 通过固定标签的独立运行时基础镜像提供给后端，用于旧版 Office 转 PDF。NAS MCP 仅在该运行时镜像不存在时构建它，应用发布复用已有运行时镜像。

## 3. 技术选型

| 层次 | 技术 | 设计理由 |
|---|---|---|
| 前端 | Vue 3、TypeScript、Vite、ECharts | 保留现有实现，支持表单、列表、看板和图表 |
| 后端 | FastAPI、Pydantic、SQLAlchemy | 接口类型清晰，适合当前单体应用和后续领域拆分 |
| 数据库 | SQLite | NAS 单实例部署简单，当前数据规模足够；启用事务和 WAL |
| Web 服务 | Nginx | 提供静态资源、反向代理和上传大小控制 |
| 文件预览 | LibreOffice、只读 HTML 生成 | 支持旧版 Office，同时避免把文件交给不受控的在线预览服务 |
| 身份与通知 | 飞书开放平台 | 人员、部门和应用消息统一来源 |
| 部署 | Docker Compose、NAS 数据卷 | 发布文件与业务数据分离，支持备份和回滚 |

## 4. 前端模块设计

### 4.1 页面与职责

| 模块 | 页面 | 主要数据 |
|---|---|---|
| 工作台 | `/` | 项目负责人概况、员工工时、待办和提醒 |
| 工时管理 | 我的工时 | 本人工时、详情、审批时间线 |
| 工时管理 | 工时审批 | 待我审批、已审批、审批详情 |
| 工时管理 | 工时看板 | 工时分布、趋势、明细和导出 |
| 工时管理 | 工时台账 | 授权用户查看和维护全部工时 |
| 项目管理 | 项目管理 | 项目 CRUD、筛选、分页和详情入口 |
| 项目管理 | 项目合同 | 收入/支出合同、阶段列表、合同详情 |
| 项目管理 | 合同收款 | 合同收款单、新增、详情、审批 |
| 项目管理 | 合同付款 | 合同付款单、新增、详情、审批 |
| 项目管理 | 项目看板 | 项目经营指标、预警和下钻 |
| 项目管理 | 客户/供应商 | 往来单位资料和银行账户 |
| 系统管理 | 人员成本 | 单天成本维护 |
| 系统管理 | 集成与通知 | 组织同步、飞书连接和通知记录 |
| 系统管理 | 管理员管理 | 管理员与菜单权限配置 |
| 系统管理 | 基础配置 | 下拉项、类型能力和银行账户 |

### 4.2 页面状态

每个列表和详情页统一支持：加载、空数据、错误、成功和权限不足五种状态。局部接口失败时只影响对应区域，并提供重试，不用全页“正在加载”覆盖已有内容。

合同详情固定顺序：

```text
合同摘要
合同信息
阶段详情
合同说明（有内容时）
合同附件（固定在最下面）
```

新增/编辑/审批单据使用阻止误关闭的弹窗：点击遮罩不关闭，使用右上角关闭或取消按钮；提交期间锁定提交按钮，返回明确错误信息。

## 5. 后端分层和职责

当前代码仍以单体入口为主，逻辑边界按以下领域维护，后续再渐进拆分目录：

```text
app/
├─ main.py                 # 路由注册和当前兼容入口
├─ db/models.py            # 领域实体和关系
├─ schemas.py              # 请求、响应和校验模型
├─ services/feishu.py      # 飞书身份、组织和应用消息
├─ auth/                   # 登录会话和数据范围
├─ worklogs/               # 工时与审批
├─ projects/               # 项目、预算和项目详情
├─ contracts/              # 合同、阶段和附件
├─ settlements/            # 收款、付款和出纳审批
├─ counterparties/         # 客户、供应商和账户
├─ ledger/                 # 项目经营流水与汇总
├─ notifications/          # 扫描、幂等和发送记录
└─ audit/                  # 审计日志
```

公共服务方法必须明确职责、输入、输出和错误场景。汇总接口不能让前端拼接多个列表后自行计算。

## 6. 核心数据模型

### 6.1 组织和权限

`users` 保存飞书用户 ID、open_id、姓名、邮箱、手机号、状态和最近同步时间；`departments` 保存飞书部门 ID、名称、父部门 ID、路径和状态。部门树用于所有部门筛选，查询上级部门时递归包含子部门。

`admin_permissions` 保存用户、权限编码、是否启用和更新时间。权限编码示例：

```text
worklog_admin, projects, contracts, receipts, payments,
project_board, all_projects, suppliers, customers,
personnel_cost, cashier, integrations, administrators, configuration
```

### 6.2 项目和工时

`projects`：编号、名称、状态、类型、负责人、部门、客户、审批人、上级领导、执行状态、是否允许填报、人天预算、成本预算、费用预算、开始/结束日期、版本和审计字段。

`work_logs`：填报人、项目、开始日期、结束日期、天数、工作内容、审批人、状态、审批意见、审批时间、审批时人员成本快照和审计字段。

关键约束：

- 同一用户在同一自然日只能存在一条有效工时记录。
- 开始日期和结束日期必须在同一自然月。
- 工时审批任务以单条工时为单位。
- 填报人等于项目审批人时，审批人改为项目上级领导。

### 6.3 合同和阶段

`project_contracts`：项目、合同类型、编号、名称、客户/供应商、金额、签订日期、履约期间、状态、负责人、说明和版本。

`contract_stages`：合同、顺序、名称、计划金额、计划日期、提醒天数、暂停标志、状态和版本。已收/已付、剩余金额和结算率不在阶段表中手工维护。

`contract_attachments`：合同、原始文件名、随机存储名、MIME 类型、文件大小、上传人、创建时间和预览类型。数据库不保存客户端路径，文件放在 `/app/data/uploads`。

### 6.4 收付款和流水

`receipt_orders` 和 `payment_orders` 保存项目、合同、阶段、业务日期、金额、账户快照、银行流水号、凭证、申请人、审批人、状态、版本和时间线。

`cashier_approval_tasks` 保存单据类型、单据 ID、版本、实际审批人、状态、意见和处理时间；`document_type + document_id + version` 唯一，避免重复任务。

`project_ledger_entries` 保存项目、流水类型、来源单据、金额、业务日期、冲销关系和幂等键。流水类型包括：

```text
PERSONNEL_COST、PAYMENT、RECEIPT、REVERSAL
```

审批通过时在同一事务中更新业务状态、写入流水、更新阶段可计算结果并写审计日志；通知发送在事务提交后执行。

## 7. 统一计算服务

所有项目看板、项目详情和工作台项目摘要复用同一计算服务。

```text
已发生人天 = Σ 已审批工时天数
人员成本 = Σ（已审批工时天数 × 审批时人员单天成本快照）
加权平均单天成本 = Σ（工时天数 × 审批时单天成本）÷ Σ 工时天数
人员成本预算基线 = 人天预算 × 加权平均单天成本
人员成本使用率 = 已发生人员成本 ÷ 人员成本预算基线 × 100%
已发生合同成本 = Σ 已审批且未冲销付款
总成本 = 人员成本 + 已发生合同成本
已收 = Σ 已审批且未冲销收款
已付 = Σ 已审批且未冲销付款
应收 = Σ max（已到期收入阶段金额 - 阶段已收，0）
应付 = Σ max（已到期支出阶段金额 - 阶段已付，0）
毛利 = 已收 - 总成本
```

边界规则：预算为 0、没有已审批工时或没有计划日期时，返回 `null`/状态值，由前端显示“暂无基准”或明确空状态；不把缺失数据当作 0 参与百分比计算。成本预算和人天预算剩余允许返回负数，以便显示超支金额。

## 8. 接口契约

### 8.1 认证与组织

```text
GET  /api/v1/auth/me
POST /api/v1/auth/feishu
GET  /api/v1/departments/tree
POST /api/v1/integrations/feishu/sync
GET  /api/v1/integrations/notifications
```

组织同步必须幂等：以飞书用户 ID 和部门 ID 更新本地记录，不删除仍被业务数据引用的历史人员或部门。

### 8.2 工时

```text
GET    /api/v1/worklogs
POST   /api/v1/worklogs
GET    /api/v1/worklogs/{id}
PATCH  /api/v1/worklogs/{id}
DELETE /api/v1/worklogs/{id}
POST   /api/v1/worklogs/{id}/submit
GET    /api/v1/worklog-approvals?status=pending|approved
POST   /api/v1/worklog-approvals/{id}/approve
POST   /api/v1/worklog-approvals/{id}/reject
GET    /api/v1/reports/worklogs
GET    /api/v1/reports/worklogs/export
```

重复日期返回业务错误；跨月返回校验错误；无权限返回 `403`；未登录返回 `401 AUTH_REQUIRED`。

### 8.3 项目、合同和阶段

```text
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}
DELETE /api/v1/projects/{id}
GET    /api/v1/projects/{id}/analysis
GET    /api/v1/contracts
POST   /api/v1/contracts
PATCH  /api/v1/contracts/{id}
DELETE /api/v1/contracts/{id}
GET    /api/v1/contracts/{id}/stages
POST   /api/v1/contracts/{id}/stages
PATCH  /api/v1/contract-stages/{id}
DELETE /api/v1/contract-stages/{id}
GET    /api/v1/contracts/{id}/attachments
POST   /api/v1/contracts/{id}/attachments
GET    /api/v1/contract-attachments/{id}/preview
GET    /api/v1/contract-attachments/{id}/download
DELETE /api/v1/contract-attachments/{id}
```

项目列表筛选支持项目类型、层级部门、负责人和名称模糊查询。合同详情接口一次返回合同主信息、摘要指标和阶段明细，避免页面自行拼接。

### 8.4 收款、付款和经营看板

```text
GET  /api/v1/receipts
POST /api/v1/receipts
GET  /api/v1/receipts/{id}
POST /api/v1/receipts/{id}/submit
POST /api/v1/receipts/{id}/approve
POST /api/v1/receipts/{id}/reject

GET  /api/v1/payments
POST /api/v1/payments
GET  /api/v1/payments/{id}
POST /api/v1/payments/{id}/submit
POST /api/v1/payments/{id}/approve
POST /api/v1/payments/{id}/reject

GET  /api/v1/project-board
GET  /api/v1/projects/{id}/ledger
```

收付款新增接口提交前校验项目、合同、阶段、金额、业务日期和账户信息；收款方姓名、开户行和账号缺一不可。审批通过后才进入已收/已付、应收/应付核销、成本和毛利。

### 8.5 管理和配置

```text
GET/PATCH /api/v1/admin/permissions
GET/POST/PATCH/DELETE /api/v1/personnel-costs
GET/POST/PATCH/DELETE /api/v1/customers
GET/POST/PATCH/DELETE /api/v1/suppliers
GET/POST/PATCH/DELETE /api/v1/config/options
```

所有管理接口除管理员管理本身外，均按对应权限编码校验；基础配置只允许修改可配置项，固定业务状态不允许随意新增和删除。

## 9. 合同附件预览设计

1. 上传时校验扩展名、MIME、空文件和 50MB 业务上限。
2. Nginx `client_max_body_size` 配置为 64MB，避免网关先于后端拦截合法请求。
3. `.docx`、`.xlsx`、`.pptx` 优先生成无脚本只读 HTML。
4. `.doc`、`.xls`、`.ppt` 使用 LibreOffice 无界面转换 PDF。
5. PDF 和图片以内嵌方式预览。
6. 预览响应失败时前端保留下载原文件入口。
7. 预览文件不执行宏、脚本或嵌入对象；临时转换目录在请求完成后清理。
8. 附件接口沿用合同权限和项目数据范围，文件名用于展示，随机存储名用于磁盘路径。

## 10. 提醒和通知设计

### 10.1 扫描任务

后台任务默认每 10 分钟扫描一次，最小间隔 30 秒。扫描范围包括：

- 今天至未来 30 天内的收入/支出阶段，以及已逾期阶段。
- 成本预算和人天预算达到 80% 或超支。
- 待审批合同收款和合同付款。
- 距离项目结项 7 天以内仍有未收/未付。

### 10.2 幂等

通知事件使用：

```text
业务对象类型 + 业务对象 ID + 提醒类型 + 业务日期
```

作为幂等键。同一日不重复发送；失败写入错误原因和重试次数，后续扫描可重试。发送失败不回滚已完成审批或经营记账。

### 10.3 消息内容

飞书应用消息采用卡片形式，至少包含项目、合同/阶段或单据、金额、日期、风险状态和系统内打开地址。打开按钮优先使用飞书 AppLink/内置 WebView，系统地址不可硬编码为本机开发地址。

## 11. 权限和安全

- 认证优先使用 HttpOnly Session Cookie；飞书 WebView 不接受 HTTP IP Cookie 时，使用后端签发、默认 8 小时有效的签名 Bearer 令牌作为会话级兼容通道。前端仅保存到 `sessionStorage`，401 或登出时立即清除；生产 HTTPS 时启用 Secure Cookie。
- 所有业务接口先认证，再校验模块权限，最后校验项目数据范围。
- 银行账号列表默认脱敏，合同收付款审批和授权管理场景才返回完整信息。
- 合同附件、营业执照、收付款凭证必须通过受保护接口读取。
- 合同和收付款确认后不能普通编辑或删除，使用冲销流程保留原记录。
- 数据库写操作使用事务；金额使用 Decimal/数据库定点类型，禁止浮点累计。
- 所有新增、修改、提交、审批、驳回、删除、冲销、同步和权限变更写入审计日志。

## 12. 部署设计

```text
/volume1/docker/xinye-workhours/
├─ deploy/
│  ├─ docker-compose.yml
│  ├─ Dockerfile.backend
│  └─ nginx.conf
├─ dist/
├─ backend/
│  ├─ app/
│  ├─ Dockerfile
│  └─ requirements.txt
└─ .backup-*/              # 发布文件备份，不含 Docker 数据卷
```

Compose 使用：

- `backend`：Python 3.12、FastAPI、LibreOffice、CJK 字体。
- `frontend`：Nginx 1.27 Alpine，映射 NAS 8088 端口。
- `xinye-workhours-data`：挂载到 `/app/data`，保存数据库和附件。

发布顺序：本地构建前端 → 上传 staging → 创建备份 → 替换发布文件 → `docker compose config` → 重建后端和前端 → 检查 `/health` → 失败恢复备份。严禁删除或覆盖数据卷。

## 13. 测试重点

### 功能

- 部门树筛选上级包含子部门、子部门不包含兄弟部门。
- 工时同日重复、跨月、本人审批转上级领导。
- 收付款合同/阶段关联、账户必填、审批后记账和驳回重提。
- 应收/应付只统计已到期阶段剩余金额。
- 人员成本、合同成本、预算剩余和毛利边界值。
- 附件上传大小、类型、权限、旧版 Office 转 PDF 和下载兜底。
- 飞书通知幂等、失败重试和应用内打开地址。

### UI

- 项目管理首页无横向滚动。
- 合同详情附件始终位于页面底部。
- 新增、编辑和审批弹窗遮罩点击不会误关闭。
- 工作台负责人区和员工区按角色显示且表格对齐。
- 390×844 移动端无横向溢出，详情和预览操作可用。

## 14. 后续架构演进

当前系统优先保持单体可部署和现有数据兼容。后续按风险拆分：

1. 先把认证、权限、通知和附件服务抽离为稳定基础层。
2. 再拆分项目、合同、收付款和经营流水领域服务。
3. 当并发、审计或数据量超过 SQLite 适用范围时迁移 PostgreSQL。
4. 人员成本生效日期、历史成本版本、发票和对账作为独立后续版本，不提前混入当前核心流程。

