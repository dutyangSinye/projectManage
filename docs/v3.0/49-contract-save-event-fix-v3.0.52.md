# v3.0.52 合同新增保存状态参数修复

- 日期：2026-09-07
- 版本：v3.0.52
- 模式：快速迭代

## 1. 问题

合同新增/编辑弹窗中“保存合同”按钮直接绑定 `@click="saveContract"`，Vue 会把点击事件对象作为第一个参数传入。`saveContract(statusOverride?)` 将事件对象当作状态值提交，后端收到非 `ACTIVE/COMPLETED/TERMINATED/DRAFT` 的状态值，报 `Input should be 'ACTIVE', 'COMPLETED', 'TERMINATED' or 'DRAFT'`。

## 2. 修复

- 两处合同表单的“保存合同”按钮改为 `@click="saveContract()"`，不再把点击事件对象传给 `statusOverride`。
- “保存草稿”继续通过 `saveContractDraft()` 显式传入 `DRAFT`。

## 3. 验收

1. 新增合同默认状态为“执行中（ACTIVE）”，可正常保存。
2. 保存草稿仍固定提交 `DRAFT`。
3. 前端生产构建通过后发布。
