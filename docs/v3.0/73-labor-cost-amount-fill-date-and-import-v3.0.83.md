# v3.0.83 人工成本结转：金额口径、填报日期与批量导入

> 变更日期：2026-09-18
> 影响模块：人工成本结转（`PERSONNEL_COST`）、项目费用共用表 `project_cost_entries`、导入框架
> 相关文档：`docs/v3.0/69-tax-inclusive-amount-design-v3.0.78.md`（含税口径）、`docs/v3.0/07-change-log.md`

---

## 1. 背景与需求

1. 人工成本结转是**内部结转**，不存在进项税，v3.0.78 引入的「含税金额 / 税率 / 未税金额 / 税额」四件套在这类单据上属于多余字段，财务人员填表时还要先选税率，属于无效操作。
2. 业务需要区分「单据归属的业务月份」（`accounting_month`）与「实际录入当天」（填报日期），用于事后追溯与对账。
3. 人工成本按月结转，一个会计期往往涉及几十个项目，逐条新增不现实，需要批量导入。

## 2. 需求与实现对应

| 需求 | 实现 |
|---|---|
| 含税金额 → 金额 | 前端标签改为「金额」；后端 PERSONNEL_COST 分支强制 `amount_without_tax = amount`、`tax_rate = 0`、`tax_amount = 0` |
| 去掉税率 / 未税金额 / 税额 | 前端 PERSONNEL_COST 分支不再渲染这三个控件；台账、详情同理 |
| 新增填报日期，不可修改，默认填报日 | 新增列 `project_cost_entries.fill_date`；`CREATE` 时由服务端取 `today_local()` 写入，接口**不接受**客户端传值（Pydantic 忽略未声明字段），`PATCH` 不覆盖；前端以 disabled 输入框展示 |
| 新增导入功能，只需项目名称 / 结转月份 / 金额 | 复用现有导入框架，新增资源 `labor_costs` |

> 项目费用（`PROJECT_EXPENSE`）**完全不受影响**，仍然保留税率三件套。

## 3. 数据变更

### 3.1 新增列

```python
# backend/app/db/models.py  ProjectCostEntry
fill_date: Mapped[date | None] = mapped_column(Date, nullable=True)
```

迁移：

- `main.py` schema 升级映射 `project_cost_entries` 增加 `("fill_date", "DATE")`。
- 历史回填：升级时按 `created_at` 补写 `fill_date`（SQLite 用 `DATE(created_at)`，PostgreSQL 用 `created_at::date`），
  保证老单据在按填报日期筛选/导出时不为空。
- 只对 `fill_date IS NULL AND created_at IS NOT NULL` 的行生效，可重复执行。

### 3.2 接口字段

`ProjectCostEntryView` 新增 `fill_date: date | None`，`cost_entry_view()` 输出 `entry.fill_date`。
`ProjectCostEntryCreate / Update` **不新增**该字段，从契约层面禁止客户端修改。

## 4. 金额口径

后端统一收敛在 `apply_tax_amount_fields` 调用处（`create_project_cost_entry` / `update_project_cost_entry`）：

```python
if entry_kind == "PERSONNEL_COST":
    # 人工成本结转是内部成本结转，不产生进项税：金额即入账金额，税额恒为 0。
    apply_tax_amount_fields(entry, payload.amount, 0, payload.amount)
else:
    apply_tax_amount_fields(entry, payload.amount, payload.tax_rate, payload.amount_without_tax)
```

即使调用方误传 `tax_rate`，人工成本结转单落库后 `tax_rate` 也一定是 0，报表与项目成本汇总不会受污染。

## 5. 批量导入

### 5.1 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/imports/labor_costs/preview` | 读取并校验，返回预览与逐行错误，不写库 |
| POST | `/api/v1/imports/labor_costs` | 全量校验通过后一次性写入，任一异常整体回滚 |
| Query | `?submit=true` | 导入后直接提交费用复核（默认生成草稿） |

权限：走 `labor_costs` 菜单权限，预览需 `VIEW`、导入需 `CREATE`（`IMPORT_RESOURCE_PERMISSIONS`）。

### 5.2 模板列

`项目名称` / `结转月份` / `金额`（必填）、`备注`（可选）。
模板文件：`frontend/public/templates/labor-cost-import-template.xlsx`，生成脚本 `test-artifacts/_gen_labor_cost_template.py`。

> 模板刻意**只有表头没有示例行**：导入程序会把任何含非空单元格的行当成数据行，写示例或说明会导致批量报错。
> 格式要求改为展示在弹窗里的提示文案。

### 5.3 校验规则

| 校验项 | 规则 | 错误提示 |
|---|---|---|
| 必填 | 项目名称、结转月份、金额不能为空 | 「不能为空」 |
| 项目存在性 | 项目必须存在、未被删除，且在当前账号 `labor_costs` 数据范围内 | 「未找到匹配的项目名称或项目不在当前数据范围」 |
| 项目唯一性 | 同名项目多个时拒绝，避免归错项目 | 「匹配到多个同名项目」 |
| 月份格式 | 容错解析见下 | 「请填写 2026-09 这样的年月」 |
| 金额 | 必须为大于 0 的数字，允许 `1,234.50`、`¥` 前缀 | 「必须是大于 0 的数字」 |
| 重复结转 | 同项目 + 同月份已存在 `status != REVERSED` 的单据，或同一文件内重复 | 「该项目已存在 YYYY-MM 的人工成本结转单」 |
| 文件 | `.xlsx` / `.csv`，≤ 5MB，≤ 5000 行 | 沿用框架既有错误 |

月份解析 `parse_import_month()` 兼容：`2026-09`、`2026/9`、`2026年9月`、`202609`，以及 Excel 日期单元格被读成
`2026-09-01` / `2026-09-01 00:00:00` 的情况，统一输出 `YYYY-MM`。

### 5.4 写入内容

每条明细生成一张结转单：

- `entry_kind = PERSONNEL_COST`，编号前缀 `LC`（`LC-YYYYMMDD-000N`）
- `budget_item` 由 `resolve_cost_entry_budget_item()` 固定归到项目「人工费用」预算项
- `fill_date = today_local()`，`amount_without_tax = amount`，`tax_rate = 0`，`tax_amount = 0`
- `description` 取备注，缺省「批量导入」
- 初始状态 `DRAFT`；`submit=true` 时经 `mark_cost_entry_submitted()` 置为 `PENDING_REVIEW`，并在统一 commit 后
  调用 `notify_cost_review_submitted()` 通知费用复核岗位

### 5.5 提交逻辑抽取

`submit_project_cost_entry` 的状态推进部分抽成 `mark_cost_entry_submitted(db, entry, user)`：

- 校验状态可提交、金额 > 0
- 写 `submitted_by / submitted_at`，清 `reviewed_*`，`version += 1`，状态 -> `PENDING_REVIEW`
- 写审计，**不提交事务、不发通知**

单张提交与批量提交共用该函数，避免两条路径行为分叉。

## 6. 前端改动

- 台账：人工成本结转页列头改为「会计期间 / 填报日期 / 金额」，项目费用页保持「发生日期 / 含税金额 / 未税金额」。
- 表单：PERSONNEL_COST 只显示「会计期间 / 填报日期（只读）/ 金额」；PROJECT_EXPENSE 保持原四件套。
- 详情：PERSONNEL_COST 的 KPI 首卡显示「结转金额」+ 填报日期小字，隐藏「未税金额 / 税额」卡；单据信息区补「填报日期」。
- 台账页新增「导入结转单」按钮（需 `labor_costs: CREATE`），复用通用导入弹窗；弹窗内针对该资源额外显示
  填写提示与「导入后直接提交费用复核」勾选框。
- 样式新增 `.import-submit-check` / `.import-template-hint`，显式声明 flex 方向，规避全局 `label` 纵向污染
  （与 v3.0.82 同源问题）。

## 7. 验证

| 项 | 结果 |
|---|---|
| 后端全量 pytest | **106 passed**（新增 `backend/tests/test_v3_labor_cost_entry.py` 8 条） |
| 开发库隔离 | `backend/data/workhours.db` mtime 未变，测试未触碰开发库 |
| 端到端冒烟 | 用 openpyxl 生成带数据 xlsx 导入：2 条 `LC` 草稿、金额/税额/填报日期/预算项均正确；表单创建同口径 |
| vue-tsc | 无新增错误（仍为 4 条历史告警） |
| vite build | 通过（`index-C5jggQM2.js` / `index-CbBLaic1.css`），模板文件已进 `dist/templates/` |

补充：新增测试最初占用了共享临时库里 `id=1` 的演示管理员，导致 `test_v3_migration` 的 OWNED 范围用例取不到项目。
已改为使用自建用户并临时扩展 `SYSTEM_ADMIN_USER_IDS`，tearDown 恢复 —— **后续写集成测试不要占用 id=1 演示身份**。

## 8. 遗留与待确认

1. 同一「项目 + 结转月份」目前只允许一条未冲销单据，重复导入会被拦截。若实际业务允许拆多张，需要改成行级提示并可放行。
2. 节假日/调休同样未参与结转月份校验（与工时提醒一致）。
3. 导入后的人工成本结转单仍需费用复核通过后才会计入项目成本，若希望导入即入账，需要另行开放「免复核」通道。

## 9. 发布与热修（2026-09-18）

| 步骤 | 结果 |
|---|---|
| git 提交 | `dda8ee0`（10 文件 +750/−34） |
| 发布前备份 | 部署文件 `.backup-mcp-20260918-122014-51df5be8`；数据库 `workhours-preimport-20260918-202044.db`（847 KB，已拉回 `_archive/prod-backup`） |
| 首次发布 | health 返回 3.0.83，但核对发现 `project_cost_entries` **没有 fill_date 列** |
| 热修 | `0f8f075`：`additions["project_cost_entries"]` 补 `("fill_date", "DATE")`，重发 |
| 生产核对 | 列已存在；25 条全部回填（PERSONNEL_COST 3 / PROJECT_EXPENSE 22）；前端产物 `index-C5jggQM2.js`、`index-CbBLaic1.css`，`templates/labor-cost-import-template.xlsx` 已上线 |

### 漏列的原因与两个教训

1. **自查脚本用裸片段判断不可靠**：`'("fill_date", "DATE"),' in src` 会命中 `worklogs` 的同名列定义而假通过；
   `'"project_cost_entries": ['` 在 `main.py` 里出现两次（retired 字典在前、additions 在后），取段时必须锁定
   含 `amount_without_tax` 的那一段。**核对迁移改动一律带表级上下文。**
2. **health 通过 ≠ 发布成功**：缺列时 `/health` 照样 200，只有打开人工成本结转页才会 500。
   发布后要用只读脚本核对表结构（`test-artifacts/_prod_verify_v3083.py`）。
   另注：web 容器是 nginx 镜像**没有 python**，核对静态资源要用 `sh -c`。

### 迁移前验证（推荐沿用）

用生产库副本验证，不动真实数据：`_archive/prod-backup/*.db` → copy 到临时目录 → `DATABASE_URL` 指向副本 →
`upgrade_schema()` → 检查列与回填（`test-artifacts/_verify_fill_date_migration_on_prod_copy.py`）。
