# 预算项与成本分类合并（v3.0.62）

## 1. 改因

v3.0.60 起的口径是「预算项 + 成本分类」两套维度并存：

- **预算项**：8 项，负责"钱花在哪一项预算上"；
- **成本分类**：7 个大类 / 23 个小类，负责"这笔钱在财务上属于什么性质"。

实际使用中两套维度高度重叠（"材料、设备采购"预算项必然落在"材料成本 / 设备采购"小类），
录入一笔费用要选两次，报表也要按两套口径各出一次，运维成本与理解成本都偏高。

本次改动把**成本分类整个维度砍掉**，由统一的 8 项预算项独自承担归集职责：

1. 人工费用
2. 材料、设备采购
3. 水、电、燃气费用
4. 委托、分包、外包费用
5. 差旅费用
6. 包装、运输费用
7. 租赁费、折旧费
8. 其他费用

经营项目与研发项目共用这一套，不再区分大小类。费用添加（项目费用、人工成本结转、
合同付款、支出合同）时只选预算项，不再选成本大类 / 成本小类。

## 2. 决策口径（已确认）

| 事项 | 决策 |
| --- | --- |
| 成本分类树（`config_options` 里 7 大类 / 23 小类） | **物理删除**，配置页不再出现 |
| 历史单据上的成本大类 / 小类快照 | 随列一起**下线**（列被 DROP，快照自然消失） |
| 8 项预算项的增删 | **固定 8 项，不可新增 / 删除 / 改名**，只可切换启用状态 |

## 3. 数据模型变更

### 3.1 下线的数据列

`upgrade_schema()` 中对以下列执行 `ALTER TABLE ... DROP COLUMN`（幂等，已存在才删）：

| 表 | 下线列 |
| --- | --- |
| `budget_item_templates` | `cost_major`、`cost_minor`、`cost_minor_options` |
| `project_budget_items` | `cost_major`、`cost_minor`、`cost_minor_options` |
| `contracts` | `cost_major_snapshot`、`cost_minor_snapshot` |
| `payments` | `cost_major_snapshot`、`cost_minor_snapshot` |
| `project_expenses` | `cost_major_snapshot`、`cost_minor_snapshot` |
| `project_ledger_entries` | `cost_major_snapshot`、`cost_minor_snapshot` |
| `project_cost_entries` | `cost_major_snapshot`、`cost_minor_snapshot` |

同时执行：

```sql
DELETE FROM config_options WHERE category IN ('cost_category', 'cost_sub_category');
```

**回滚方式**：`_archive/db-backup/workhours.pre-merge-costcategory-20260911-140858.db`
是执行前的完整备份；列一旦 DROP 无法在线恢复，只能整体还原备份文件。

### 3.2 `DEFAULT_BUDGET_ITEM_TEMPLATES` 简化

模板种子由 `(code, name, major, minor, minor_options, source_kind)` 简化为
`(code, name, source_kind)`，经营 / 研发两套内容完全一致。

`LEGACY_BUDGET_ITEM_CODE_MAP` 保留，用于把历史预算项编码收敛到新的 8 项编码。

### 3.3 移除的后端代码

- `parse_cost_minor_options()`、`dump_cost_minor_options()`、`validate_cost_minor_options()`
- `cost_item_minor_options()`（原用于给出预算项可归集的成本小类候选）
- `CONFIG_CATEGORY_LABELS` / `CLASSIFICATION_TREE_CATEGORIES` / `DEFAULT_CLASSIFICATION_TREES`
  中的 `cost_category`、`cost_sub_category` 分支
- `ClassificationCatalog` 的 `cost_category` 字段
- 成本单列表的 `cost_major` / `cost_minor` 筛选参数（改为统一的 `keyword` 搜索）

## 4. 接口变更

| 接口 | 变化 |
| --- | --- |
| `GET /api/v1/admin/config/classifications` | 只返回 `project_category` 一棵树 |
| `GET /api/v1/admin/budget-item-templates` | 返回 16 条（两类各 8），响应不再含成本分类字段 |
| `POST /api/v1/admin/budget-item-templates` | **恒返回 409 `BUDGET_TEMPLATE_FIXED`** |
| `DELETE /api/v1/admin/budget-item-templates/{id}` | **恒返回 409 `BUDGET_TEMPLATE_FIXED`** |
| `PATCH /api/v1/admin/budget-item-templates/{id}` | 只接受 `is_active`，其余字段一律忽略 |
| `GET /api/v1/project-cost-entries` | 去掉 `cost_major` / `cost_minor` 筛选，新增 `keyword` |
| 成本单 / 合同 / 付款的创建与视图 | 不再接受、不再返回成本分类字段 |

## 5. 前端变更

- 类型：`Contract` / `Payment` / `ProjectExpense` / `BudgetItemTemplate` /
  `ProjectBudgetItem` 去掉成本分类字段；`ClassificationCatalog` 只保留 `project_category`
- 配置页：分类树页签只剩「项目分类树」；分类目录不再出现成本树
- 预算项模板页：表头去掉「成本大类 / 成本小类 / 可归集小类」三列；「＋ 新增预算项」
  按钮改为「固定 8 项 · 不支持新增或删除」标签；删除按钮恒禁用
- 预算项模板弹窗：去掉成本大类、默认成本小类、可归集小类三组控件；项目类别 / 编码 /
  排序 / 适用来源均为只读，名称只读，只保留「启用此模板」开关
- 项目预算项表、项目分析预算项表、支出合同表、合同表单、费用表单与费用详情：
  去掉成本分类列与提示

## 6. 验收记录

| 项 | 结果 |
| --- | --- |
| `pytest -q` | **51 passed** |
| `smoke-stage1.py` | 全部通过 |
| `smoke-stage2.py` | 全部通过 |
| `smoke-migration-on-copy.py` | 全部通过 |
| `smoke-merge-costcategory.py`（本次新增，25 项） | **全部通过** |
| `pnpm build`（含 `tsc -b`） | 通过，产物 `frontend/dist` |
| 开发库迁移前备份 | `_archive/db-backup/workhours.pre-merge-costcategory-20260911-140858.db` |
| 开发库实测 | 7 张表成本列全部下线；`cost_category` 0 行、`cost_sub_category` 0 行；两类模板各 8 项且名称与统一口径一致 |
| 线上接口实测 | 模板接口 16 条、分类目录仅 `project_category`、新增/删除返回 409 |

## 7. 后续事项

- 阶段 2 前端（项目成本单页、人工成本结转页、费用复核页、付款详情改单节点）尚未实现
- 原型目录 `docs/v3.0/prototype-v3.0.59/` 仍写着两套预算项口径，需同步为统一 8 项
- 旧 `project_expenses` 单据与接口保留双向兼容，待新前端上线后再下线
