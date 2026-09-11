# 综合项目管理系统 —— 项目长期记录

## 基本事实

- 项目根：`D:/myproject`。**不是 git 仓库**（无 .git），版本靠文档 + 目录快照管理。
- 后端：FastAPI + SQLAlchemy，入口 `backend/app/main.py`（单体，8474 行），默认 SQLite（`backend/data/workhours.db`），可切 PostgreSQL。
- 前端：Vue 3 + TS + Vite，`frontend/src/App.vue` 单体 12000 行，`styles.css` 11482 行，无组件拆分目录。
- 版本号常量：`backend/app/main.py` 的 `API_VERSION`。文档索引：`docs/00-document-index.md`；变更记录：`docs/v3.0/07-change-log.md`。

## 常用命令

后端启动（根目录）：

```powershell
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

前端启动：

```powershell
cd frontend; pnpm dev   # http://127.0.0.1:5173
```

跑测试（**必须两个路径都在 PYTHONPATH**，否则 collection error）：

```bash
cd D:/myproject && PYTHONPATH="D:/myproject;D:/myproject/backend" ./.venv/Scripts/python.exe -m pytest backend/tests -q
```

## 部署

- NAS 部署包结构：包根下并列 `deploy/`、`dist/`、`backend/app`，`deploy/docker-compose.yml` 里 `../dist` 指向包根的 dist。
- 发布工具：`tools/nas-deploy-mcp/`（stdio MCP，工具 nas_status/nas_health/nas_logs/nas_backup/nas_deploy/nas_rollback），只管理固定目录，不做任意远程 Shell，发布/回滚需显式确认，数据库 volume 不参与替换。
- 发布内容：`pnpm build` 产物 `frontend/dist` → 打成 staging 包上传。
- 生产端口 8088，容器 `xinye-workhours-api` / `xinye-workhours-web`。

## 约定

- 文档驱动开发：改动必须先查 `docs/v3.0/` 对应的状态机、错误码、接口契约和防呆规则；只在当前版本文档追加，历史文档不回写。
- 生产密钥（飞书 app_secret、SSH、Cloudflare token、.env）绝不进源码/文档/发布包。
- 时区统一 `Asia/Shanghai`（`backend/app/time_utils.py` 的 now_local/today_local，禁止直接用 datetime.now()）。
- 工时天数只统计周一至周五，周末区间禁止提交。
- 飞书只负责身份 + 通知，不创建真实飞书审批实例；审批任务在本地系统内。

## 数据模型要点

44 张表，分域：
- 组织/权限：departments, users, roles, menus, role_permissions, user_roles, role_data_scopes, user_role_scopes, permission_audits, admin_permissions
- 业务主体：customers, suppliers, projects, budget_item_templates, project_budget_items
- 工时：worklogs, timesheets, approval_tasks
- 合同资金：contracts, contract_stages, receipts, payments, contract_attachments, cash_document_attachments, project_ledger_entries
- 项目费用：project_expenses, project_expense_attachments, project_expense_payments
- 审批工作流：approval_positions(+members), workflow_definitions, workflow_versions, workflow_nodes, workflow_instances, workflow_tasks, workflow_action_logs
- 通知/审计：notifications, system_notifications, notification_policies, reminder_events, org_sync_logs, audit_logs, config_options
