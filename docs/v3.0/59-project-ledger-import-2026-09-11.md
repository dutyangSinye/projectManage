# 项目台账导入生产系统（2026-09-11）

## 背景

生产环境部署 v3.0.63 后项目数为 0。杨总提供《综合项目管理平台.xls》（工作表「项目台账」，12 行 × 9 列），要求把项目导入系统。

导入目标：**生产环境**（`116.169.217.29:8088`，版本 3.0.63），不是本地开发库。

## 源数据

| 项目大类 | 合同类型 | 项目名称 | 项目编号 | 项目负责人 | 工时审批人 | 主管领导 | 所属部门 | 项目状态 |
|---|---|---|---|---|---|---|---|---|
| 经营项目 | 委托研发 | 爬壁焊接辅助机器人项目课题研发 | XM-YF-20251101 | 牛智祥 | 樊公海 | 林宗奇 | 产品研发部 | 进行中 |
| 经营项目 | 设备销售 | 灵巧型（机械臂式）激光追踪焊接机器人设备销售 | XM-XS-20260101 | 李晓天 | 樊公海 | 林宗奇 | 产品研发部 | 进行中 |
| 经营项目 | 委托研发 | 《面向智能建造的预制构件结构光三维检测技术研究及应用》课题研发 | XM-YF-20260201 | 李晓天 | 樊公海 | 林宗奇 | 产品研发部 | 进行中 |
| 经营项目 | 委托研发 | 《用于爬附既有建筑非磁性墙面的足尺吸盘足》课题研发 | XM-YF-20260203 | 李晓天 | 樊公海 | 林宗奇 | 产品研发部 | 进行中 |
| 经营项目 | 委托研发 | 《建筑钻孔植筋机器人》课题研发 | XM-YF-20260301 | 李晓天 | 樊公海 | 林宗奇 | 产品研发部 | 进行中 |
| 经营项目 | 技术服务 | 郑东新区算力产业园项目技术服务 | XM-JS-20260401 | 王卓 | 王卓 | 甘丹 | 技术服务部 | 进行中 |
| 经营项目 | 设备销售 | 中国五冶（第一批）智能建造设备采购 | XM-XS-20260501 | — | — | — | — | — |
| 研发项目 | 外部申报项目 | 施工机器人高鲁棒性通信与多机协同技术研究与应用 | YF-G-2026-001 | 牛智祥 | 樊公海 | 林宗奇 | 产品研发部 | 进行中 |
| 研发项目 | 自主研发 | 智能建造施工调度与管理平台 | YF-D-2025-001 | 杨阳 | 樊公海 | 林宗奇 | 产品研发部 | 进行中 |
| 研发项目 | 自主研发 | 自动化钢筋加工产线研发 | YF-D-2025-002 | 杜连腾 | 樊公海 | 林宗奇 | 产品研发部 | 进行中 |
| 研发项目 | 自主研发 | 室内乳胶漆喷涂机器人研发与应用 | YF-D-2025-003 | 牛智祥 | 樊公海 | 林宗奇 | 产品研发部 | 进行中 |
| 研发项目 | 自主研发 | 建筑物流搬运机器人研发与应用 | YF-D-2025-004 | 李晓天 | 樊公海 | 林宗奇 | 产品研发部 | 进行中 |

## 字段映射

| 台账列 | 系统字段 | 取值来源 |
|---|---|---|
| 项目大类 | `projects.project_type` | 经营项目 → `BUSINESS_PROJECT`；研发项目 → `RND_PROJECT` |
| 合同类型 | `projects.project_sub_category` | 委托研发 → `ENTRUSTED_RND`；设备销售 → `EQUIPMENT_SALES`；技术服务 → `TECHNICAL_SERVICE`；外部申报项目 → `EXTERNAL_DECLARATION`；自主研发 → `SELF_DEVELOPED_RND` |
| 项目名称 | `projects.name` | 原样 |
| 项目编号 | `projects.code` | 原样（唯一键，重复即拒绝） |
| 项目负责人 | `owner_user_id` / `owner_name` | 按姓名匹配 `users` |
| 工时审批人 | `approver_user_id` / `approver_name` | 按姓名匹配 `users` |
| 主管领导 | `leader_user_id` / `leader_name` | 按姓名匹配 `users` |
| 所属部门 | `department_id` / `department_name` | 按名称匹配启用的 `departments` |
| 项目状态 | `projects.status` | 进行中 → `ACTIVE` |

预算（`budget_days` / `budget_cost` / `expense_budget`）、日期、客户台账未给，一律留 0 / 空，后续在界面维护。

## 杨总拍板的两个口径

1. **第 7 行「中国五冶（第一批）智能建造设备采购」**（XM-XS-20260501）负责人、审批人、主管领导、部门、状态全空 → **只导编号和名称，其余留空**。据此该项目的 `owner_name` 为空串、人员与部门为 NULL、`status` 取默认值 `ACTIVE`（字段 NOT NULL，无法留空）。**没有审批人意味着无法提交工时审批**，需后续补人。
2. **所属部门按表格字面填**，不按负责人实际所属子部门。表格写「产品研发部」即挂 id=5 产品研发部（即使牛智祥/李晓天在应用创新中心、杜连腾在技术研发中心、杨阳在信息化中心）。

## 导入方式

在容器 `xinye-workhours-api` 内直接调用项目自身的业务函数，等价于调用 `POST /api/v1/admin/projects`，因此预算项会自动按大类带出：

```
resolve_project_classification()   # 校验大类/小类从属
active_org_department()            # 校验部门启用
Project(...)                       # 建对象
apply_project_users()              # 写三个人员 + 姓名/open_id 快照
ensure_project_budget_items()      # 按大类复制 8 项预算项
audit()                            # 审计日志，comment = "台账导入"
```

未走 HTTP 接口的原因：生产关闭 demo 登录态，`X-Demo-User-Id` 一律 401，无可用鉴权。

远程执行体经 base64 走 stdin 送入容器内的 python（`base64 -d | python -`），规避多层 shell 引号转义问题。

## 可复用工具

`tools/project-import/`：

```
python tools/project-import/import_projects.py --xls <台账.xls>              # 备份 + dry-run
python tools/project-import/import_projects.py --xls <台账.xls> --apply       # 备份 + 真正写入
python tools/project-import/import_projects.py --xls <台账.xls> --no-backup   # 跳过备份
```

- 表头顺序固定为 9 列，不符直接报错退出。
- **默认 dry-run**，只有 `--apply` 才写库。
- `--apply` 前自动做 `sqlite3.backup()` 一致性备份到容器内 `/app/data/backups/`。
- 编号重复、人员不存在、部门未启用、小类不属于大类都会中止整批导入（全成功或全回滚）。

依赖：`xlrd`（解析 .xls）已装在项目 `.venv` 与 `tools/nas-deploy-mcp/.venv`。

## 验收结果

| 项 | 结果 |
|---|---|
| 导入项目数 | 12（经营 7 / 研发 5） |
| 项目预算项 | 96（每个项目 8 项，统一口径） |
| 审计日志 | 12 条，`object_type='project'`、`action='CREATE'`、`comment='台账导入'`，操作人 id=4（杨阳） |
| 基础数据保全 | users 22 / departments 12 / customers 2 / suppliers 31 / config_options 31 / budget_item_templates 16 |
| 完整性 | 无空编号、无重复编号、无缺预算项的项目 |
| 服务健康 | `GET /health` → 200，version 3.0.63 |
| 重复导入保护 | 再次 dry-run 12 条全部判定「项目编号已存在」，未写入 |

## 回滚

导入前备份：`_archive/prod-backup/workhours-preimport-20260911-160448.db`（458 KB，md5 `fabce6c96299bd0a14f748bff0dfdcf8`）。

需要回滚时停容器 → 用该备份覆盖 `/app/data/workhours.db` → 起容器。注意：回滚会一并丢失导入后新增的其他数据。

## 遗留事项

1. 项目 7（XM-XS-20260501）缺负责人/审批人/主管领导/部门，需补齐后才能报工时。
2. 12 个项目的预算金额、开始/计划结束日期、客户、项目阶段都还是空的，需要在界面上补。
3. 台账里的「合同类型」目前映射到项目小类；如果后续合同管理需要独立的合同类型字段，得再单独加维度。
