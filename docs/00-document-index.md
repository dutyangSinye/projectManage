# 综合项目管理系统文档索引

本文档索引对应当前项目目录中的需求、交互、系统设计、测试、用户体验、原型和部署说明。

当前生产功能阅读入口：`docs/v3.0/27-current-baseline-v3.0.27.md`。生产运行版本为 `v3.0.60`，已落地项目预算项统一、后台模板配置和新预算口径。

## 文档版本

- `v1.0`：初始需求、交互设计、系统设计、原型和评审记录。
- `v2.0`：飞书组织架构、应用消息、本地审批、项目/成本/管理员管理、工时看板、NAS MCP 以及迭代变更记录。
- `v2.0.46`：修复未配置项目成本预算导致工时看板 HTTP 500，进而阻断项目列表初始化的问题。
- `v3.0`：已实现并部署的工时与项目经营一体化版本，包含四大模块、合同、收付款、往来单位、项目看板和出纳审批。
- `v3.0.9`：历史统一基线，记录合同附件预览与合同详情布局变更；当前实现以 `v3.0.27` 文档基线为准。
- `v3.0.10`：已实现并验证的原型差异补齐版本，覆盖四大模块、项目详情六个 TAB、合同阶段分层、附件区、集成通知中心和移动端交互。
- `v3.0.11`：集成中心组织同步后刷新 500 修复版本。
- `v3.0.12`：原型差异闭环版本，补齐通知策略实际通道、通知详情、项目/合同/收付款下钻和旧同步记录兼容。
- `v3.0.13`：原型差异完整交付版本，补齐通知中心和组织同步记录分页、收付款审批时间线及项目看板图表下钻，并完成 NAS 发布验证。
- `v3.0.14`：原型差异页面闭环版本，明确通知中心独立视图，项目详情补齐合同阶段/收付款子视图，并修复项目看板图表首次加载时序。
- `v3.0.15`：原型差异完成回归版本，补齐集成通知、项目详情、项目看板、合同与收付款详情，并修复项目看板首次进入图表空白问题。
- `v3.0.16`：收付款单附件与合同保存草稿版本，补齐收款/付款附件的上传、预览、下载、删除和审批详情读取。
- `v3.0.19`：统一 `Asia/Shanghai` 应用时区、前后端时间生成与展示，并增加 SQLite 历史 UTC 时间一次性迁移。
- `v3.0.20`：收付款提交后向所有出纳审批权限用户发送飞书通知，并记录实际审批人姓名。
- `v3.0.21`：合同、收款单和付款单新建时暂存附件，保存成功后自动关联上传。
- `v3.0.22`：工作台将本月已审批天数改为当前月份的工时审批单据数量。
- `v3.0.23`：角色、菜单操作权限与数据访问范围的 RBAC 实现，包含角色库、人员多角色授权、权限预览、后端接口校验、旧权限迁移和授权审计。
- `v3.0.24`：按确认要求重置角色配置，仅保留系统管理员，清空其他角色和历史授权，管理员可从零重新配置。
- `v3.0.25`：项目看板全部项目动态选项、收付款合同往来单位账户自动带出，已完成 NAS 发布验证。
- `v3.0.26`：通知策略改为只读总览、弹窗统一编辑和一次性保存，已完成 NAS 发布验证。
- `v3.0.27`：当前文档统一基线，整合 v3.0.4 至 v3.0.26 已实现功能、业务口径、权限、提醒、时区、附件、部署和边界说明。
- `v3.0.28`：客户、供应商和合同批量导入设计与实现，包含模板下载、文件预览校验、权限控制和事务性导入。
- `v3.0.30`：合同导入改为按项目名称匹配，合同类型使用中文下拉选项，匹配失败禁止写入并支持修正后重新导入。
- `v3.0.31`：修复工时日期未自动计算天数，统一按包含首尾日期的自然日整数计算并增加后端一致性校验。
- `v3.0.32`：工时天数改为只统计周一至周五，周末区间禁止提交，前后端算法统一。
- `v3.0.43`：飞书 WebView 会话兼容、首次管理员初始化、无演示数据生产启动、项目及 RBAC 配置迁移能力。
- `v3.0.44`：项目费用与动态审批工作流设计及高保真原型，覆盖差旅、无合同发票、其他费用、审批岗位、流程版本和费用支付；未开发。
- `v3.0.45`：项目费用与动态审批工作流实施版本，统一“人天预算”术语并增加独立费用预算；已发布。
- `v3.0.46`：合同付款七级动态审批闭环版本，包含阶段额度占用、飞书直达、通知重试和历史付款兼容；已发布。
- `v3.0.47`：审批岗位与项目经营概况界面优化，补齐费用审批结果、出纳支付提醒和失败重试；已发布。
- `v3.0.48`：角色权限界面全面中文化并核查系统管理员来源与业务口径；已发布。
- `v3.0.49`：客户/供应商编码系统自动生成，客户和供应商导入模板移除编码列；本地验证完成，待发布。
- `v3.0.59`：项目预算项与成本复核重构设计稿，覆盖项目大类/小类、经营/研发项目预算项模板、预算项总和作为总预算、成本大/小类、合同付款一级费用复核、项目费用简化和人工成本结转；页面原型已生成，待确认，未开发。
- `v3.0.60`：研发项目和经营项目统一 8 个预算项；后台基础配置维护预算项模板；项目预算项自动生成并作为总预算来源；支出合同、项目费用和人工费用按预算项归集；本地构建、回归和生产发布通过。

## 文档目录

### 总体方案

- `docs/00-development-plan.md`
- `docs/01-user-manual.md`：员工、审批人、项目负责人、出纳和管理员使用手册
- `docs/01-user-manual.docx`：v3.0.29 逐步图文 Word 版用户使用手册
- `docs/系统使用手册-v3.0.27.docx`：历史 Word 手册；当前请使用 v3.0.29 文件
- `docs/系统使用手册-v3.0.28.docx`：上一版逐步图文 Word 手册；当前请使用 v3.0.29 文件
- `docs/系统使用手册-v3.0.29.docx`：当前逐步图文 Word 版用户使用手册（使用裁切后的页面截图）
- `docs/系统使用手册.docx`：历史 Word 手册副本；因文件当前被其他程序占用，未覆盖，当前请使用上面的 v3.0.29 文件
- `README.md`

### v1.0

- `docs/v1.0/00-opensource-research.md`
- `docs/v1.0/01-prd.md`
- `docs/v1.0/02-interaction.md`
- `docs/v1.0/03-system-design.md`
- `docs/v1.0/04-function-test-report.md`
- `docs/v1.0/05-ui-test-report.md`
- `docs/v1.0/06-ux-review-report.md`
- `docs/v1.0/prototype/`：初始 HTML 原型

### v2.0

- `docs/v2.0/00-opensource-research.md`
- `docs/v2.0/01-prd.md`
- `docs/v2.0/02-interaction.md`
- `docs/v2.0/03-system-design.md`
- `docs/v2.0/04-function-test-report.md`
- `docs/v2.0/05-ui-test-report.md`
- `docs/v2.0/06-ux-review-report.md`
- `docs/v2.0/07-nas-deploy-mcp-design.md`
- `docs/v2.0/08-worklog-admin-change-v2.0.26.md`
- `docs/v2.0/09-approval-tabs-change-v2.0.27.md`
- `docs/v2.0/10-worklog-refresh-cost-pagination-v2.0.28.md`
- `docs/v2.0/11-worklog-date-validation-v2.0.29.md`
- `docs/v2.0/12-personnel-cost-standalone-v2.0.30.md`
- `docs/v2.0/13-report-loading-fix-v2.0.46.md`
- `docs/v2.0/prototype/`：v2.0 页面原型

### v3.0（已实现并部署）

- `docs/v3.0/01-prd.md`
- `docs/v3.0/02-product-design.md`
- `docs/v3.0/03-system-design.md`
- `docs/v3.0/04-single-project-analysis-design.md`：单项目成本、合同阶段、结项资金和预警分析设计
- `docs/v3.0/05-function-test-report.md`：单项目经营分析功能测试报告
- `docs/v3.0/06-ui-test-report.md`：单项目经营分析 UI 测试报告
- `docs/v3.0/07-change-log.md`：v3.0.4 及后续维护变更记录
- `docs/v3.0/09-change-note-2026-08-31.md`：前天与昨天的功能、修复、部署和验证对比说明
- `docs/v3.0/10-latest-requirements-v3.0.9.md`：当前版本统一需求基线
- `docs/v3.0/11-latest-system-design-v3.0.9.md`：当前版本统一系统设计基线
- `docs/v3.0/12-prototype-parity-v3.0.10.md`：原型差异补齐、实现范围和最终验证记录
- `docs/v3.0/13-integrations-overview-orm-fix-v3.0.11.md`：集成中心同步后刷新 500 修复说明
- `docs/v3.0/14-prototype-parity-completion-v3.0.12.md`：原型差异闭环实施说明、接口约定、下钻交互和验收范围
- `docs/v3.0/15-prototype-parity-closure-v3.0.14.md`：原型差异页面闭环修改说明和本轮验收口径
- `docs/v3.0/16-prototype-parity-completion-v3.0.15.md`：原型差异清单完整实现、回归结果和交付说明
- `docs/v3.0/17-cash-attachments-and-contract-draft-v3.0.16.md`：收付款附件和合同保存草稿的需求、接口、权限与验收说明
- `docs/v3.0/20-shanghai-timezone-standard-v3.0.19.md`：上海时区统一、历史时间迁移、前后端时间处理和 NAS 配置说明
- `docs/v3.0/21-create-attachments-before-save-v3.0.21.md`：新建合同与收付款单预选附件、保存后自动上传的交互和验收说明
- `docs/v3.0/22-monthly-approved-worklog-count-v3.0.22.md`：工作台本月工时审批数统计口径和验收说明
- `docs/v3.0/23-rbac-menu-data-scope-design-v3.0.23.md`：角色、菜单与数据访问范围设计、实现和验证记录
- `docs/v3.0/24-rbac-role-reset-v3.0.24.md`：仅保留系统管理员的角色配置重置说明
- `docs/v3.0/25-board-contract-counterparty-autofill-v3.0.25.md`：项目看板项目选项和收付款账户自动带出说明
- `docs/v3.0/26-notification-policy-batch-edit-v3.0.26.md`：通知策略只读总览、弹窗编辑和批量保存说明
- `docs/v3.0/27-current-baseline-v3.0.27.md`：当前生产实现的统一文档基线和功能对照
- `docs/v3.0/28-import-master-data-v3.0.28.md`：客户、供应商和合同导入功能设计、校验规则和验收口径（已更新至 v3.0.30）
- `docs/v3.0/30-docker-runtime-image-cache-v3.0.33.md`：LibreOffice 运行时镜像复用和 NAS MCP 按需构建说明
- `docs/v3.0/31-feishu-login-bootstrap-v3.0.34.md`：真实飞书模式首次登录用户自动引导和管理员初始化说明
- `docs/v3.0/32-auth-gate-message-v3.0.35.md`：未登录状态提示和飞书登录入口展示说明
- `docs/v3.0/33-feishu-auth-timeout-v3.0.36.md`：飞书授权 SDK 无回调时的超时兜底和登录提示说明
- `docs/v3.0/34-feishu-auth-standard-api-v3.0.37.md`：标准飞书授权码接口优先和兼容回退说明
- `docs/v3.0/35-feishu-sdk-ready-fallback-v3.0.38.md`：飞书 SDK 初始化无回调时的直接授权兜底说明
- `docs/v3.0/36-nas-mcp-sudo-password-v3.0.39.md`：NAS MCP 普通 sudo 账号兼容说明
- `docs/v3.0/37-feishu-auth-direct-start-v3.0.40.md`：飞书授权方法已注入时立即启动说明
- `docs/v3.0/38-feishu-session-credentials-v3.0.41.md`：飞书换码成功后 Session Cookie 显式携带说明
- `docs/v3.0/39-feishu-bearer-session-fallback-v3.0.42.md`：飞书 WebView 的 Cookie + Bearer 双通道认证设计和验收说明
- `docs/v3.0/40-feishu-webview-auth-compatibility-v3.0.43.md`：飞书 WebView 兼容认证、首次管理员、生产演示数据关闭和迁移工具说明
- `docs/v3.0/41-project-expense-workflow-design-v3.0.44.md`：项目费用、动态审批岗位、版本化流程、费用支付和项目成本口径设计稿（未开发）
- `docs/v3.0/42-project-expense-workflow-implementation-v3.0.45.md`：项目费用与动态审批工作流实施说明、费用预算口径和回归范围
- `docs/v3.0/43-contract-payment-workflow-closure-v3.0.46.md`：合同付款七级动态审批闭环、通知与阶段额度一致性说明
- `docs/v3.0/44-approval-position-project-analysis-ui-v3.0.47.md`：审批岗位名册、项目成本预算分层及费用飞书通知闭环说明
- `docs/v3.0/45-rbac-localization-and-rule-audit-v3.0.48.md`：角色权限中文化与系统管理员、审批流程、成本口径核查说明
- `docs/v3.0/46-counterparty-auto-code-import-v3.0.49.md`：客户/供应商自动编码与导入简化说明
- `docs/v3.0/53-cost-budget-review-redesign-v3.0.59.md`：项目预算项、成本分类、合同付款一级复核、项目费用简化和人工成本结转重构设计稿
- `docs/v3.0/54-budget-item-implementation-v3.0.60.md`：统一 8 项预算模板、后台配置、项目预算项、合同/费用归集和兼容迁移实现说明
- `docs/v3.0/55-classification-tree-stage1-v3.0.60.md`：第 1 阶段（基础层）项目分类树与成本分类树、项目大类/小类联动、扁平项目类型下线的实现与验收说明
- `docs/v3.0/56-document-layer-stage2-v3.0.61.md`：第 2 阶段（单据层）项目成本单（项目费用 / 人工成本结转）、一级费用复核、工时不再折算人员成本与冲销净额口径的实现与验收说明
- `docs/v3.0/57-budget-cost-category-merge-v3.0.62.md`：预算项与成本分类合并——成本分类维度整体下线、统一 8 项预算项固定不可增删、历史列与分类数据清理的实现与验收说明
- `docs/v3.0/58-cost-entry-frontend-and-review-access-v3.0.63.md`：阶段 2 前端（项目费用 / 人工成本结转 / 成本单详情 / 费用复核三页签）、合同付款改一级复核口径，以及费用复核权限迁移与生产升级预演的实现与验收说明
- `docs/v3.0/59-project-ledger-import-2026-09-11.md`：生产环境项目台账导入记录——xls 字段映射、两个拍板口径（空行只导编号名称、部门按表格字面）、导入方式、可复用工具与验收结果
- `docs/v3.0/60-worklog-fill-reminder-v3.0.64.md`：工时填报定时飞书提醒——通知策略新增提醒时刻/通知范围/仅未填报配置、每工作日定时扫描、立即发送接口与前端配置界面的实现与验收说明
- `docs/v3.0/prototype/`：v3.0.44 完整可点击高保真原型，新增项目费用、费用审批、审批岗位和审批流程
- `docs/v3.0/prototype-v3.0.59/`：v3.0.59 项目预算项与成本复核重构可点击原型，覆盖工作台、项目管理、项目预算项、项目详情、合同、合同收款、合同付款、项目费用、人工成本结转、费用复核、项目看板和基础配置

### 设计素材

- `docs/assets/business-flowchart.svg`：当前业务流程图
- `docs/assets/business-flowchart.md`：流程图 Mermaid 源文件和口径说明
- `docs/assets/manual-receipt-form.png`、`docs/assets/manual-payment-form.png`、`docs/assets/manual-admin-console.png`：用户手册收付款与系统管理界面示意图

### 归档说明

- `_archive/2026-08-31/`：历史发布包、构建 staging、测试数据库/日志及重复文档发布包。
- 归档内容仅作为追溯和恢复材料，不参与构建、部署或运行。
- `docs/v3.0/10-latest-requirements-v3.0.9.md` 和 `docs/v3.0/11-latest-system-design-v3.0.9.md` 为 v3.0.9 历史统一基线，当前实现以 v3.0.27 文档基线为准。

### 部署与运维

- `tools/nas-deploy-mcp/README.md`
- `deploy/docker-compose.yml`
- `deploy/Dockerfile.runtime`
- `deploy/Dockerfile.backend`
- `deploy/nginx.conf`
- `backend/.env.example`

## 安全说明

文档包只包含示例配置、设计资料和部署说明，不包含 `.env`、飞书 `app_secret`、Cloudflare token、SSH 密码、私钥或数据库文件。实际运行参数应继续保存在 NAS 或 MCP 的本地环境配置中。
