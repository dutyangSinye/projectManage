# v3.0.84 合同收付款审批飞书卡片直达详情修复

版本：v3.0.84  
日期：2026-09-22  
状态：已实现

## 1. 问题

飞书应用消息中的「待审批合同收款单」卡片按钮文案为「打开综合项目管理系统」，点击后只进入系统首页，审批人还需要手动进入合同收款列表查找单据。

## 2. 修复范围

- 不调整收件人权限配置和通知策略。
- 仅修复出纳审批通用通知的系统内打开地址。
- 合同收款卡片打开：`?page=receiptDetail&id=收款单ID`。
- 合同付款卡片打开：`?page=paymentDetail&id=付款单ID`。

## 3. 实现说明

后端新增 `cash_approval_detail_url(source_type, source_id)`，由 `send_cash_approval_notifications()` 统一调用：

- `source_type = receipt` 时生成合同收款详情地址；
- `source_type = payment` 时生成合同付款详情地址；
- 未识别类型保留根地址兜底，避免异常业务阻断通知发送。

飞书适配器仍会把系统地址包装成飞书 AppLink，以便在飞书内置浏览器打开。

## 4. 验证

- 后端编译通过。
- 新增回归断言：发送合同收款待审批通知时，传给飞书卡片的地址必须以 `/?page=receiptDetail&id=收款单ID` 结尾。
- 合同付款地址生成规则同步覆盖为 `/?page=paymentDetail&id=付款单ID`。
