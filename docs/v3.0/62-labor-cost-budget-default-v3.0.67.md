# v3.0.67 人工成本结转固定归集到「人工费用」

日期：2026-09-11
状态：已实现，待发布
版本：`API_VERSION = "3.0.67"`

## 一、诉求

「人工成本结转不用选预算项，默认就是人工成本。」

人工成本结转（`entry_kind = PERSONNEL_COST`）本质上只有一种归集去向——人工费用预算项。
界面上给出预算项下拉，既多余又容易选错，选错了还会把人工成本记到材料费、差旅费上。

## 二、现状核对

后端其实早就这么做了：`resolve_cost_entry_budget_item()` 对 `PERSONNEL_COST`
直接调用 `labor_budget_item()`，**完全忽略**请求里传的 `budget_item_id`；
新建 `POST /api/v1/project-cost-entries` 与编辑 `PATCH /api/v1/project-cost-entries/{id}`
都走这个解析函数。所以这次改动主要是**把界面与实现对齐**，顺带加固归集项的识别。

## 三、变更

### 前端（`frontend/src/App.vue`）

| 位置 | 变更 |
| --- | --- |
| 成本单弹窗「预算归集」区块 | `entry_kind === 'PERSONNEL_COST'` 时下拉替换为只读输入框，固定显示「人工费用」并附注「人工成本结转固定归集到『人工费用』，无需选择」；项目费用仍保留下拉 |
| `saveCostEntry()` | 人工成本结转提交 `budget_item_id: null`，不再带上界面残留值 |
| `resetCostEntryForm()` / `editCostEntry()` | 人工成本结转不再请求项目预算项列表，省掉一次无谓接口调用 |

列表页与详情页的「预算项 / 归集预算项」展示不变，值来自后端快照，本来就是「人工费用」。

### 后端（`backend/app/main.py`）

`labor_budget_item()` 过去是「找 `source_kind == 'LABOR'`，找不到就取第一项」，
一旦模板被改名或排序调整，就可能把人工成本归到别的预算项上。现改为三级优先匹配：

1. 预算项编码 `LABOR_COST`；
2. 来源类型 `source_kind == 'LABOR'`；
3. 名称含「人工」。

每一级**优先取启用项**；该级全部被停用则继续往下一级找，而不是硬塞一个已停用的项。
最终仍找不到才回落到第一个启用项。

## 四、回归用例

`backend/tests/test_v3_labor_cost_budget.py`（新增 7 项）：

- 优先取编码为 `LABOR_COST` 的预算项；
- 编码对不上时按 `source_kind == 'LABOR'` 匹配；
- 再退化为名称含「人工」；
- 同优先级下取启用项，停用的 `LABOR_COST` 不会盖住启用的其他人工项；
- 无任何预算项时返回 `None`；
- `resolve_cost_entry_budget_item('PERSONNEL_COST', ...)` 忽略传入的 `budget_item_id`，仍返回人工项；
- 项目没有人工预算项时抛 `400 LABOR_BUDGET_ITEM_MISSING`。

后端全量测试由 69 项增至 **76 项**，全部通过。

## 五、影响面

- 只影响「人工成本结转」这一类单据的录入界面与归集解析；项目费用、合同付款的预算项选择不变。
- 历史数据无需迁移：存量人工成本单的 `budget_item_id` 与快照本来就是人工费用项。
- 若某个项目把人工费用预算项停用了，人工成本会归到下一个匹配项（如名称含「人工」的自定义项），
  而不是直接报错；项目一个预算项都没有时才会 `400 LABOR_BUDGET_ITEM_MISSING`。
