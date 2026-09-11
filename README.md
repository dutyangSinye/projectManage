# 综合项目管理系统

基于飞书组织架构和飞书消息通知的工时与项目经营管理系统。

当前生产运行版本：`v3.0.60`（预算项统一、后台模板配置与新预算口径）。版本号以后端常量 `API_VERSION`（`backend/app/main.py`）为准，可通过 `/health` 查询运行实例的实际版本。项目文档统一从 [docs/00-document-index.md](docs/00-document-index.md) 进入；历史版本文档保留在 `docs/v1.0/` 和 `docs/v2.0/`，临时发布与测试产物位于 `_archive/`，不参与运行。

## 当前实现

- FastAPI + SQLAlchemy 后端，默认 SQLite，可通过 `DATABASE_URL` 切换 PostgreSQL。
- Vue 3 + TypeScript + Vite 前端。
- 工作台、我的工时、单条提交、待我审批、审批详情、管理报表、项目审批人、集成与通知。
- 管理报表支持按项目所属一级部门查看工时看板，包含日期筛选、部门对比、项目/人员/阶段/状态/类型分布。
- 工时填报支持按项目名称/编码筛选，单位固定为天；管理报表包含项目、人员、阶段、状态、项目×阶段占比和工时类型 6 类 ECharts 图表，统一按天统计。
- 集成与通知仅对 `SYSTEM_ADMIN_USER_IDS` 配置的系统管理员显示；组织架构同步入口位于该页面，并提供连接概况、同步统计时间线、通知策略、统一通知中心、详情和失败重试；策略通道会实际控制后续飞书通知发送。
- 管理员管理支持“角色 + 菜单 + 操作权限 + 数据访问范围”配置；用户可绑定多个角色，权限取并集，管理员可查看最终生效权限和授权来源，授权变更保留审计记录。
- 项目详情提供概况、基本信息、人员与工时、预算、合同与资金、操作记录六个页签；合同与资金页签可切换查看合同阶段、合同收款单和合同付款单，并可下钻到合同或单据详情。
- 合同、合同收款单和合同付款单新建时均可先选择多个附件，保存业务实体后自动关联上传；附件支持列表、预览、下载、删除，Office 预览失败时可下载原文件。新建合同提供“保存草稿”入口，草稿可继续补充附件后再保存为正式合同。
- 客户、供应商和项目合同支持按模板批量导入；客户/供应商编码由系统按日期流水自动生成，导入模板不再要求填写编码；合同导入填写客户/供应商名称并自动匹配，默认为草稿且不包含合同阶段。
- 人员成本为独立管理员功能，支持按部门、人员筛选和分页维护单天成本；组织同步仍位于集成与通知。
- 工时管理仅对系统管理员显示，支持全量工时按日期、部门、人员、状态和关键词查询，并可编辑、删除工时。
- 工时日期必须在同一自然月内；同一人员所有项目的日期区间不允许重叠，同一天不能重复填报不同项目。
- 每条工时单独创建本地审批任务；飞书只发送提醒，不创建真实飞书审批实例。
- 飞书能力通过 `backend/app/services/feishu.py` 隔离；组织同步支持 `FEISHU_MODE=mock/app`，通知支持 `FEISHU_NOTIFICATION_MODE=mock/webhook/app`。`app` 通知会按审批人的飞书 `open_id` 发送私聊应用消息。
- 首次启动自动生成演示用户、项目和工时数据。

## 本地运行

后端：

```powershell
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
$env:PATH="C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;$env:PATH"
pnpm dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。

## 生产构建

```powershell
cd frontend
pnpm build
```

构建产物位于 `frontend/dist/`。

## 测试

在项目根目录运行即可，`pytest.ini` 已配置 `pythonpath=backend`，不需要手动设置 `PYTHONPATH`：

```powershell
& .\.venv\Scripts\python.exe -m pytest
```

共 50 个用例。根目录 `conftest.py` 会在导入应用代码前把 `DATABASE_URL` 指向一次性临时库，因此测试不会读写 `backend/data/workhours.db`。

> `backend/tests/test_imports.py` 刻意使用 `backend.app.*`（而非 `app.*`）导入，以获得独立的 engine 和自己的临时库；`app/db/session.py` 在 import 时就绑定数据库且无法重指，改成统一导入会让测试连到开发库。调整导入方式前请先看该文件与 `conftest.py` 的说明。

## 版本控制

仓库为 git 管理。`.gitattributes` 强制 `Dockerfile*`、`*.conf`、`*.yml`、`*.sh` 使用 LF —— 这些文件一旦被检出成 CRLF，NAS 上的 Docker 构建会失败。不要移除这些规则。

## NAS 部署 MCP

`tools/nas-deploy-mcp/` 提供独立的 stdio MCP Server，用于通过 SSH 检查和发布 NAS 上的工时系统。它只管理固定部署目录，不提供任意远程 Shell；发布和回滚都要求显式确认，数据库 Docker volume 不参与文件替换。

安装依赖：

```powershell
cd tools/nas-deploy-mcp
.\install.ps1 -Python "C:\path\to\python.exe"
Copy-Item .env.example .env
```

支持的工具、客户端配置和安全边界见 `tools/nas-deploy-mcp/README.md` 与 `docs/v2.0/07-nas-deploy-mcp-design.md`。

## 飞书通知配置

组织同步配置（仅放在 NAS 的 Compose `.env`，不要写入源码或提交记录）：

```dotenv
FEISHU_MODE=app
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
SYSTEM_ADMIN_USER_IDS=23
```

`SYSTEM_ADMIN_USER_IDS` 填写本地用户 ID，多个管理员用英文逗号分隔。生产环境必须显式配置，组织同步接口会拒绝非管理员调用。

群机器人通知：在 NAS Compose 环境变量中设置 `FEISHU_NOTIFICATION_MODE=webhook` 和 `FEISHU_ROBOT_WEBHOOK`，再重建 API 容器。Webhook 只发送待审批提醒，审批人仍需登录系统处理。

应用私聊通知：在 NAS Compose 环境变量中设置 `FEISHU_NOTIFICATION_MODE=app`、`FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`，组织同步后用户必须有可用的 `open_id`。飞书应用需要发布并开通 `im:message:send_as_bot` 权限。通知使用互动卡片，审批人点击“打开工时系统”按钮后通过飞书 AppLink 在内置 WebView 中打开系统地址。通知失败不会回滚本地审批任务，审批人可在系统审批详情中重新发送。

本版本不需要飞书审批回调，因此不需要额外配置 HTTPS 回调地址。应用消息发送使用服务端租户令牌和组织同步得到的审批人 `open_id`。

合同、合同收款单和合同付款单附件保存在后端数据卷内，默认目录分别为 `/app/data/contract-attachments` 和 `/app/data/cash-attachments`，随 Docker volume 持久化；可用 `CASH_ATTACHMENT_DIR` 覆盖收付款附件目录。

详细设计见 `docs/00-document-index.md`，当前统一基线见 `docs/v3.0/27-current-baseline-v3.0.27.md`，当前版本设计与测试资料位于 `docs/v3.0/`。

导入模板位于 `frontend/public/templates/`：`customer-import-template.xlsx`、`supplier-import-template.xlsx`、`contract-import-template.xlsx`。构建后可从客户、供应商和项目合同页面的“导入”入口下载。

