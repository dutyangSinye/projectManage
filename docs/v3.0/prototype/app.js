const page = document.getElementById('page')
const breadcrumb = document.getElementById('breadcrumb')
const modalBackdrop = document.getElementById('modalBackdrop')
const modal = modalBackdrop.querySelector('.modal')
const modalEyebrow = document.getElementById('modalEyebrow')
const modalTitle = document.getElementById('modalTitle')
const modalBody = document.getElementById('modalBody')
const modalFoot = document.getElementById('modalFoot')
const toast = document.getElementById('toast')

const money = value => `¥${Number(value).toLocaleString('zh-CN')}`
const tag = (text, tone = '') => `<span class="tag ${tone}">${text}</span>`
const progress = (value, tone = '') => `<span class="progress ${tone}"><span style="width:${Math.min(value, 100)}%"></span></span>`

const projects = [
  { id: 1, code: 'SS-2026-008', name: '智慧工地机器人协同平台', type: '实施项目', status: '进行中', owner: '杨阳', dept: '产品研发部 / 信息化中心', customer: '四川华西集团', worklog: true, days: 36, budgetDays: 50, budget: 680000, staffCost: 36000, paid: 285000, payable: 95000, received: 420000, receivable: 180000, risk: '1 项逾期' },
  { id: 2, code: 'RD-2026-003', name: '建筑物流搬运机器人研发与应用', type: '研发项目', status: '进行中', owner: '杨阳', dept: '产品研发部 / 机器人中心', customer: '内部研发', worklog: true, days: 88, budgetDays: 120, budget: 520000, staffCost: 163000, paid: 86000, payable: 120000, received: 0, receivable: 0, risk: '成本正常' },
  { id: 3, code: 'KT-2026-012', name: '机器人集群智能调度管理系统课题', type: '课题项目', status: '进行中', owner: '樊公海', dept: '产品研发部 / 信息化中心', customer: '四川省科技厅', worklog: true, days: 62, budgetDays: 72, budget: 310000, staffCost: 151000, paid: 92000, payable: 46000, received: 0, receivable: 0, risk: '人天预警' },
  { id: 4, code: 'SS-2025-027', name: '自动化钢筋加工产线交付项目', type: '实施项目', status: '验收中', owner: '李明', dept: '技术服务部 / 交付中心', customer: '中铁八局', worklog: true, days: 104, budgetDays: 110, budget: 980000, staffCost: 208000, paid: 510000, payable: 85000, received: 720000, receivable: 360000, risk: '2 项逾期' },
  { id: 5, code: 'GM-2026-004', name: '智能建造装备现场观摩活动', type: '观摩项目', status: '已完成', owner: '张敏', dept: '市场营销部', customer: '成都市住建局', worklog: false, days: 18, budgetDays: 20, budget: 85000, staffCost: 28000, paid: 42000, payable: 0, received: 0, receivable: 0, risk: '正常' }
]

const contracts = [
  { no: 'HT-SR-2026-014', name: '智慧工地机器人协同平台采购合同', kind: '收入合同', project: projects[0].name, partner: '四川华西集团', amount: 1200000, settled: 420000, due: 180000, nextDate: '2026-09-05', status: '生效', stages: '2 / 4' },
  { no: 'HT-ZC-2026-019', name: '视觉传感器及边缘计算设备采购', kind: '支出合同', project: projects[0].name, partner: '成都锐视科技有限公司', amount: 460000, settled: 285000, due: 95000, nextDate: '2026-08-30', status: '生效', stages: '2 / 3' },
  { no: 'HT-ZC-2026-011', name: '搬运机器人底盘委托加工合同', kind: '支出合同', project: projects[1].name, partner: '四川精工智能装备有限公司', amount: 260000, settled: 86000, due: 120000, nextDate: '2026-09-12', status: '生效', stages: '1 / 3' },
  { no: 'HT-SR-2025-033', name: '自动化钢筋加工产线销售合同', kind: '收入合同', project: projects[3].name, partner: '中铁八局', amount: 1080000, settled: 720000, due: 360000, nextDate: '2026-08-20', status: '生效', stages: '2 / 3' }
]

const projectExpenses = [
  { id: 1, no: 'FY-20260906-0018', type: '差旅费用', project: projects[0].name, projectCode: projects[0].code, applicant: '杨阳', dept: '产品研发部 / 信息化中心', occurred: '2026-09-03', amount: 3860, cost: 3860, payment: '待审批', status: '审批中', node: '会计审核', tone: 'warning', purpose: '智慧工地现场联调与阶段验收支持' },
  { id: 2, no: 'FY-20260905-0015', type: '无合同发票', project: projects[0].name, projectCode: projects[0].code, applicant: '陈露', dept: '产品研发部 / 信息化中心', occurred: '2026-09-02', amount: 12800, cost: 12800, payment: '待审批', status: '待我审批', node: '经营审批', tone: 'danger', purpose: '现场网络专线和设备临时租赁费' },
  { id: 3, no: 'FY-20260904-0012', type: '其他费用', project: projects[1].name, projectCode: projects[1].code, applicant: '樊公海', dept: '产品研发部 / 机器人中心', occurred: '2026-09-01', amount: 6200, cost: 6200, payment: '已支付', status: '已完成', node: '流程结束', tone: 'success', purpose: '样机测试材料及加工费' },
  { id: 4, no: 'FY-20260903-0009', type: '差旅费用', project: projects[3].name, projectCode: projects[3].code, applicant: '李明', dept: '技术服务部 / 交付中心', occurred: '2026-08-29', amount: 2460, cost: 2460, payment: '无需支付', status: '已审批', node: '流程结束', tone: 'success', purpose: '自动化产线验收整改支持' },
  { id: 5, no: 'FY-20260902-0007', type: '无合同发票', project: projects[2].name, projectCode: projects[2].code, applicant: '赵海', dept: '产品研发部 / 信息化中心', occurred: '2026-08-28', amount: 9800, cost: 9200, payment: '未开始', status: '已驳回', node: '申请人修改', tone: 'danger', purpose: '课题现场数据采集服务费' }
]

const approvalPositions = [
  { code: 'OPERATIONS_REVIEWER', name: '经营审批', people: ['刘洁', '王哲'], dept: '经营管理部', scenes: '付款、无合同发票、其他费用', updated: '今天 09:32' },
  { code: 'OPERATIONS_VP', name: '经营副总', people: ['周建国'], dept: '公司管理层', scenes: '付款、无合同发票、其他费用', updated: '9 月 5 日' },
  { code: 'ACCOUNTANT', name: '会计', people: ['张敏', '陈欣'], dept: '财务部', scenes: '差旅及全部费用', updated: '今天 08:46' },
  { code: 'GENERAL_MANAGER', name: '总经理', people: ['李国强'], dept: '公司管理层', scenes: '差旅及全部费用', updated: '8 月 28 日' },
  { code: 'CASHIER', name: '出纳', people: ['贺茂维', '刘芳'], dept: '财务部', scenes: '收付款及费用支付', updated: '今天 10:05' }
]

const routeNames = {
  workbench: '工作台', projects: '项目管理', 'project-detail': '项目详情', contracts: '项目合同', 'contract-detail': '合同详情', receipts: '合同收款', payments: '合同付款', 'project-expenses': '项目费用', 'expense-detail': '费用详情', 'project-board': '项目看板', suppliers: '供应商管理', customers: '客户管理', permissions: '管理员管理', 'approval-positions': '审批岗位', workflows: '审批流程', 'workflow-detail': '流程详情', 'my-worklogs': '我的工时', approvals: '工时审批', 'worklog-board': '工时看板', 'worklog-ledger': '工时台账', 'personnel-cost': '人员成本', integration: '集成与通知', configuration: '基础配置'
}

function pageHead(eyebrow, title, description, actions = '') {
  return `<header class="page-head"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div><div class="page-actions">${actions}</div></header>`
}

function filterBar(content, extra = '') {
  return `<section class="filters">${content}<div class="filter-actions"><button class="btn btn-primary" data-toast="筛选条件已应用">查询</button><button class="btn" data-reset>重置</button>${extra}</div></section>`
}

function pagination(total = 28) {
  return `<div class="pagination"><span>共 ${total} 条</span><button>‹</button><button class="active">1</button><button>2</button><button>3</button><button>›</button><select class="control" style="width:86px;height:30px"><option>20 条/页</option><option>10 条/页</option><option>50 条/页</option></select></div>`
}

function showToast(message) {
  toast.textContent = message
  toast.classList.add('show')
  window.clearTimeout(showToast.timer)
  showToast.timer = window.setTimeout(() => toast.classList.remove('show'), 2200)
}

function openModal({ eyebrow = '业务操作', title, body, foot, wide = false }) {
  modalEyebrow.textContent = eyebrow
  modalTitle.textContent = title
  modalBody.innerHTML = body
  modalFoot.innerHTML = foot || `<button class="btn" data-close-modal>取消</button><button class="btn btn-primary" data-confirm-modal>确认</button>`
  modal.classList.toggle('wide', wide)
  modalBackdrop.hidden = false
  document.body.style.overflow = 'hidden'
  bindInteractions(modalBackdrop)
}

function closeModal() {
  modalBackdrop.hidden = true
  document.body.style.overflow = ''
}

function routeTo(route, params = {}) {
  closeModal()
  const query = new URLSearchParams({ page: route, ...params })
  window.location.hash = query.toString()
}

function currentRoute() {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  return { route: params.get('page') || 'workbench', params }
}

function renderWorkbench() {
  const projectRows = projects.slice(0, 4).map((p, index) => {
    const dayRate = Math.round(p.days / p.budgetDays * 100)
    const totalCost = p.staffCost + p.paid
    const costRate = Math.round(totalCost / p.budget * 100)
    const implementation = p.type === '实施项目'
    const riskTone = p.risk.includes('逾期') ? 'danger' : p.risk.includes('预警') ? 'warning' : 'success'
    return `<tr class="click-row" data-route="project-detail" data-id="${p.id}">
      <td style="width:24%"><span class="cell-main">${p.name}</span><span class="cell-sub">${p.code} · ${p.type}</span></td>
      <td style="width:19%"><div class="ledger-line" style="grid-template-columns:1fr 50px"><div>${progress(dayRate, dayRate > 85 ? 'warning' : '')}</div><strong>${p.days}/${p.budgetDays}</strong></div><span class="cell-sub">已发生 / 人天预算</span></td>
      <td style="width:18%"><div class="ledger-line" style="grid-template-columns:1fr 46px"><div>${progress(costRate, costRate > 85 ? 'warning' : '')}</div><strong>${costRate}%</strong></div><span class="cell-sub">人员 ${money(p.staffCost)} · 外部 ${money(p.paid)}</span></td>
      <td style="width:17%"><span class="cell-main">${money(p.paid)} / ${money(p.payable)}</span><span class="cell-sub">已付 / 当前应付</span></td>
      <td style="width:16%">${implementation ? `<span class="cell-main">${money(p.received)} / ${money(p.receivable)}</span><span class="cell-sub">已收 / 当前应收</span>` : '<span class="cell-sub">不适用收入侧</span>'}</td>
      <td style="width:90px">${tag(p.risk, riskTone)}</td>
    </tr>`
  }).join('')

  page.innerHTML = `${pageHead('2026 年 8 月 28 日 · 星期五', '早上好，杨阳', '先处理风险和待办，再查看项目经营与个人工时。', `<button class="btn btn-primary" data-worklog-form>＋ 填报工时</button><button class="btn" data-action-menu>更多操作⌄</button>`)}
    <section class="section section-plain">
      <div class="section-head"><div><h2>我负责的项目</h2><p class="muted">项目经营、工时审批和到期事项</p></div><button class="btn btn-sm" data-route="projects">查看全部项目</button></div>
      <div class="owner-summary">
        <div class="summary-item"><div class="label"><span>负责项目</span><span class="tag primary">4 个在执行</span></div><div class="value">6</div><div class="hint">含 1 个验收中项目</div></div>
        <div class="summary-item warn"><div class="label"><span>待审工时</span><span>本周</span></div><div class="value">3</div><div class="hint">共 4.5 人天待确认</div></div>
        <div class="summary-item"><div class="label"><span>7 天内应收</span><span>2 个阶段</span></div><div class="value">${money(260000)}</div><div class="hint">点击查看收入合同阶段</div></div>
        <div class="summary-item warn"><div class="label"><span>7 天内应付</span><span>2 个阶段</span></div><div class="value">${money(175000)}</div><div class="hint">需要准备付款计划</div></div>
        <div class="summary-item alert"><div class="label"><span>逾期事项</span><span>需处理</span></div><div class="value">3</div><div class="hint">应收 2 项 · 应付 1 项</div></div>
      </div>
      <div class="quick-strip"><span class="label">快捷发起</span><button class="btn btn-sm" data-payment-form>＋ 付款</button><button class="btn btn-sm" data-receipt-form>＋ 收款</button><button class="btn btn-sm" data-expense-form>＋ 项目费用</button><button class="btn btn-sm" data-route="approvals">工时审批 <span class="tag warning">3</span></button><span class="spacer"></span><span class="muted">经营数据更新于 10:28</span></div>
    </section>

    <div class="workbench-grid">
      <section class="section">
        <div class="section-head"><div><h2>项目经营概况</h2><p class="muted">按风险优先展示最近活跃项目</p></div><div class="segmented"><button class="active">风险优先</button><button>最近活跃</button></div></div>
        <div class="table-wrap"><table class="data-table"><thead><tr><th>项目</th><th>人天执行</th><th>成本执行</th><th>已付 / 应付</th><th>已收 / 应收</th><th>风险</th></tr></thead><tbody>${projectRows}</tbody></table></div>
      </section>
      <section class="section">
        <div class="section-head"><div><h2>近期提醒</h2><p class="muted">到期、逾期与预算预警</p></div><button class="btn btn-quiet btn-sm" data-toast="已标记全部已读">全部已读</button></div>
        <div class="section-body reminder-list">
          <div class="reminder-item"><span class="reminder-icon danger">收</span><div><strong>收款阶段已逾期 8 天</strong><p>自动化钢筋加工产线 · 验收款</p></div><span class="amount-danger">¥360,000</span></div>
          <div class="reminder-item"><span class="reminder-icon">付</span><div><strong>设备到货款 2 天后到期</strong><p>智慧工地机器人协同平台</p></div><span class="amount-negative">¥95,000</span></div>
          <div class="reminder-item"><span class="reminder-icon">天</span><div><strong>人天预算使用 86%</strong><p>机器人集群智能调度管理系统课题</p></div><span class="tag warning">预警</span></div>
          <div class="reminder-item"><span class="reminder-icon danger">付</span><div><strong>委托加工款已逾期</strong><p>建筑物流搬运机器人研发与应用</p></div><span class="amount-danger">¥120,000</span></div>
        </div>
      </section>
    </div>

    <div class="section-title" style="margin-top:24px"><div><h2>我的工时</h2><p>员工视角：本月填报与审批状态</p></div><button class="btn btn-primary" data-worklog-form>＋ 填报工时</button></div>
    <section class="section">
      <div class="employee-band">
        <div class="employee-stat"><span class="muted">本月已审批</span><div class="value">18.5 天</div><p>较上月同期 +2 天</p></div>
        <div class="employee-stat"><span class="muted">审批中</span><div class="value">2 条</div><p>最近提交于今天 09:36</p></div>
        <div class="employee-stat"><span class="muted">已驳回</span><div class="value" style="color:var(--danger)">1 条</div><p>需要补充现场工作说明</p></div>
        <div class="employee-stat"><span class="muted">草稿</span><div class="value">1 条</div><p>8 月 28 日 · 1 天</p></div>
        <div class="employee-recent"><div class="section-title"><h3>最近工时</h3><button class="btn btn-quiet btn-sm" data-route="my-worklogs">查看全部</button></div>
          <div class="recent-row click-row" data-toast="打开 8 月 27 日工时详情"><span><strong>智慧工地机器人协同平台</strong><small class="cell-sub">8 月 27 日 · 现场联调 · 1 天</small></span>${tag('审批通过', 'success')}</div>
          <div class="recent-row click-row" data-toast="打开 8 月 26 日工时详情"><span><strong>建筑物流搬运机器人研发与应用</strong><small class="cell-sub">8 月 26 日 · 开发 · 1 天</small></span>${tag('审批中', 'warning')}</div>
          <div class="recent-row click-row" data-toast="打开 8 月 25 日工时详情"><span><strong>机器人集群智能调度管理系统课题</strong><small class="cell-sub">8 月 25 日 · 方案设计 · 0.5 天</small></span>${tag('已驳回', 'danger')}</div>
        </div>
      </div>
    </section>`
}

function departmentTree() {
  return `<div class="field tree-control"><label>所属部门</label><button class="tree-trigger" data-tree-trigger><span>全部部门</span><span>⌄</span></button><div class="tree-menu" hidden>
    <button class="tree-option active" data-tree-value="全部部门">全部部门</button>
    <button class="tree-option" data-tree-value="产品研发部">▾ 产品研发部</button>
    <button class="tree-option depth-1" data-tree-value="信息化中心">├ 信息化中心</button>
    <button class="tree-option depth-1" data-tree-value="机器人中心">└ 机器人中心</button>
    <button class="tree-option" data-tree-value="技术服务部">▾ 技术服务部</button>
    <button class="tree-option depth-1" data-tree-value="交付中心">└ 交付中心</button>
    <button class="tree-option" data-tree-value="市场营销部">▸ 市场营销部</button>
  </div></div>`
}

function renderProjects() {
  const rows = projects.map(p => `<tr class="click-row" data-route="project-detail" data-id="${p.id}">
    <td style="width:25%"><span class="cell-main">${p.name}</span><span class="cell-sub">${p.code}</span></td>
    <td style="width:9%">${tag(p.status, p.status === '已完成' ? 'success' : p.status === '验收中' ? 'warning' : 'primary')}</td>
    <td style="width:9%">${tag(p.type, 'outline')}</td>
    <td style="width:9%"><span class="cell-main">${p.owner}</span></td>
    <td style="width:18%"><span class="truncate" title="${p.dept}">${p.dept}</span></td>
    <td style="width:15%"><span class="truncate">${p.customer}</span></td>
    <td style="width:8%">${p.worklog ? tag('可填报', 'success') : tag('已关闭')}</td>
    <td style="width:120px" class="right"><button class="btn btn-quiet btn-sm" data-route="project-detail" data-id="${p.id}">查看</button><button class="btn btn-quiet btn-sm" data-edit-project>编辑</button></td>
  </tr>`).join('')
  page.innerHTML = `${pageHead('项目主数据', '项目管理', '列表只保留定位项目所需的核心信息，经营数据进入项目详情查看。', '<button class="btn btn-primary" data-edit-project>＋ 新增项目</button>')}
    ${filterBar(`<div class="field"><label>项目类型</label><select class="control"><option>全部类型</option><option>研发项目</option><option>课题项目</option><option>实施项目</option><option>观摩项目</option></select></div><div class="field"><label>项目状态</label><select class="control"><option>全部状态</option><option>进行中</option><option>验收中</option><option>已完成</option></select></div>${departmentTree()}<div class="field"><label>项目负责人</label><select class="control"><option>全部负责人</option><option>杨阳</option><option>樊公海</option><option>李明</option></select></div><div class="field"><label>客户</label><select class="control"><option>全部客户</option><option>四川华西集团</option><option>中铁八局</option></select></div><div class="field grow"><label>项目名称 / 编号</label><input class="control" placeholder="输入项目名称或编号"></div>`, `<div class="segmented"><button class="active">我的项目</button><button>全部项目</button></div>`)}
    <section class="section">
      <div class="section-head"><div><h2>项目列表</h2><p class="muted">共 28 个项目 · 其中 19 个允许填报工时</p></div><div class="inline-actions"><button class="btn btn-sm" data-toast="项目清单已导出">导出</button><button class="btn btn-sm" data-toast="项目数据已刷新">刷新</button></div></div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>项目</th><th>状态</th><th>类型</th><th>负责人</th><th>所属部门</th><th>客户</th><th>工时填报</th><th class="right">操作</th></tr></thead><tbody>${rows}</tbody></table></div>
      ${pagination(28)}
    </section>`
}

function renderProjectDetail(params) {
  const selected = projects.find(p => p.id === Number(params.get('id'))) || projects[0]
  const isImplementation = selected.type === '实施项目'
  const otherProjectCost = 23200
  const totalCost = selected.staffCost + selected.paid + otherProjectCost
  const margin = selected.received - totalCost
  const costRate = Math.round(totalCost / selected.budget * 100)
  const dayRate = Math.round(selected.days / selected.budgetDays * 100)
  const personnelRate = Math.round(selected.staffCost / (selected.budgetDays * 1000) * 100)
  const incomeContract = 1200000
  const expenseContract = 460000
  const incomeStages = [
    { name: '合同首付款', date: '2026-07-15', planned: 420000, settled: 420000, status: '已完成', tone: 'success', note: '合同收款单 SK-2026-0086 · 已确认' },
    { name: '阶段验收款', date: '2026-08-20', planned: 180000, settled: 0, status: '已逾期', tone: 'danger', note: '尚未发起合同收款 · 逾期 8 天' },
    { name: '系统上线款', date: '2026-09-05', planned: 300000, settled: 0, status: '即将到期', tone: 'warning', note: '提前 7 天提醒 · 结项前计划' },
    { name: '质保款', date: '2026-12-20', planned: 300000, settled: 0, status: '未到期', tone: '', note: '结项后计划 · 暂无合同收款单' }
  ]
  const expenseStages = [
    { name: '设备采购款', date: '2026-07-18', planned: 285000, settled: 285000, status: '已完成', tone: 'success', note: '合同付款单 FK-2026-0064 · 已确认' },
    { name: '设备到货款', date: '2026-08-20', planned: 95000, settled: 0, status: '已逾期', tone: 'danger', note: '尚未发起合同付款 · 逾期 8 天' },
    { name: '现场服务尾款', date: '2026-09-28', planned: 80000, settled: 0, status: '未到期', tone: '', note: '结项后计划 · 预计晚于结项 10 天' }
  ]
  const stageRows = (side, rows) => rows.map(stage => {
    const remaining = Math.max(stage.planned - stage.settled, 0)
    const ratio = stage.planned ? Math.round(stage.settled / stage.planned * 100) : 0
    return `<div class="analysis-stage-group"><div class="analysis-stage-row"><span class="stage-name"><strong>${stage.name}</strong><small>${stage.date} · ${stage.note}</small></span><span class="stage-money number">${money(stage.planned)}</span><span class="stage-settled number">${money(stage.settled)}</span><span class="stage-remaining number ${stage.tone === 'danger' ? 'amount-danger' : stage.tone === 'warning' ? 'amount-negative' : ''}">${money(remaining)}</span><span class="stage-rate number">${ratio}%</span><span class="stage-docs number">${stage.settled ? '1 笔' : '0 笔'}</span><span class="stage-status">${tag(stage.status, stage.tone)}</span></div></div>`
  }).join('')
  page.innerHTML = `<div class="detail-hero analysis-hero"><div><div class="detail-title"><h1>${selected.name}</h1>${tag(selected.status, 'primary')}${tag(selected.type, 'outline')}${tag('1 项严重预警', 'danger')}</div><div class="detail-meta"><span>项目编号 <strong>${selected.code}</strong></span><span>负责人 <strong>${selected.owner}</strong></span><span>部门 <strong>${selected.dept}</strong></span><span>客户 <strong>${selected.customer}</strong></span></div></div><div class="analysis-close-countdown"><span>距离计划结项</span><strong>21</strong><small>天 · 2026-09-18</small></div><div class="page-actions"><button class="btn" data-edit-project>编辑主信息</button>${isImplementation ? '<button class="btn" data-receipt-form>＋ 收款</button>' : ''}<button class="btn" data-payment-form>＋ 付款</button><button class="btn" data-expense-form>＋ 费用</button><button class="btn btn-primary" data-worklog-form>＋ 填报工时</button></div></div>
    <div class="detail-tabs"><div class="tabs"><button class="tab active" data-project-tab="analysis">经营分析</button><button class="tab" data-project-tab="basic">基本信息</button><button class="tab" data-project-tab="people">人员与工时</button><button class="tab" data-project-tab="budget">预算</button><button class="tab" data-project-tab="funds">合同与资金</button><button class="tab" data-project-tab="expenses">费用明细</button><button class="tab" data-project-tab="logs">操作记录</button></div></div>
    <section class="analysis-kpi-band" data-project-analysis><div><span>收入合同</span><strong class="number">${money(incomeContract)}</strong><small>已收 ${money(selected.received)}</small></div><div><span>支出合同</span><strong class="number">${money(expenseContract)}</strong><small>已付 ${money(selected.paid)}</small></div><div><span>总成本</span><strong class="number">${money(totalCost)}</strong><small>人员 ${money(selected.staffCost)} · 合同 ${money(selected.paid)} · 费用 ${money(otherProjectCost)}</small></div><div><span>毛利 / 毛利率</span><strong class="number amount-positive">${money(margin)}</strong><small>${Math.round(margin / selected.received * 1000) / 10}% · 现金口径</small></div><div><span>未完成预警</span><strong class="number amount-danger">4</strong><small>1 严重 · 2 预警 · 1 提示</small></div></section>
    <div class="analysis-main-grid" data-project-analysis><section class="section analysis-card cost-analysis-card"><div class="section-head"><div><h2>成本组成与预算执行</h2><p class="muted">已审批工时、已确认合同付款和已审批项目费用计入实际成本</p></div><span class="analysis-updated">更新于 10:28</span></div><div class="analysis-card-body"><div class="cost-summary-row"><div><span>成本预算</span><strong class="number">${money(selected.budget)}</strong></div><div><span>预算剩余</span><strong class="number amount-positive">${money(selected.budget - totalCost)}</strong></div><div><span>总成本使用率</span><strong class="number ${costRate > 85 ? 'amount-danger' : ''}">${costRate}%</strong></div></div><div class="cost-composition"><div class="composition-label"><span>成本构成</span><span class="legend"><i class="legend-personnel"></i>人员成本 <i class="legend-contract"></i>合同成本 <i class="legend-expense"></i>项目费用</span></div><div class="composition-track"><span class="composition-personnel" style="width:${Math.round(selected.staffCost / totalCost * 100)}%"></span><span class="composition-contract" style="width:${Math.round(selected.paid / totalCost * 100)}%"></span><span class="composition-expense" style="width:${Math.round(otherProjectCost / totalCost * 100)}%"></span></div><div class="composition-values"><span><strong>${money(selected.staffCost)}</strong><small>人员成本 · ${Math.round(selected.staffCost / totalCost * 100)}%</small></span><span><strong>${money(selected.paid)}</strong><small>合同成本 · ${Math.round(selected.paid / totalCost * 100)}%</small></span><span><strong>${money(otherProjectCost)}</strong><small>项目费用 · ${Math.round(otherProjectCost / totalCost * 100)}%</small></span></div></div><div class="budget-metrics"><div><div class="metric-line"><span>人天执行率</span><strong>${dayRate}%</strong></div>${progress(dayRate, dayRate > 85 ? 'warning' : '')}<small>${selected.days} / ${selected.budgetDays} 天 · 剩余 ${selected.budgetDays - selected.days} 天</small></div><div><div class="metric-line"><span>人员成本使用率</span><strong>${personnelRate}%</strong></div>${progress(personnelRate, personnelRate > 85 ? 'warning' : '')}<small>人员成本基线 ${money(selected.budgetDays * 1000)} · 加权单价 ¥1,000 / 天</small></div></div><div class="mini-trend"><div class="mini-trend-head"><span>近 4 个月成本趋势</span><span class="legend"><i class="legend-personnel"></i>人员 <i class="legend-contract"></i>合同 <i class="legend-expense"></i>项目费用</span></div><div class="trend-bars"><div class="trend-month"><div class="trend-stack"><i class="trend-personnel" style="height:25%"></i><i class="trend-contract" style="height:18%"></i><i class="trend-expense" style="height:4%"></i></div><small>5 月</small></div><div class="trend-month"><div class="trend-stack"><i class="trend-personnel" style="height:34%"></i><i class="trend-contract" style="height:28%"></i><i class="trend-expense" style="height:6%"></i></div><small>6 月</small></div><div class="trend-month"><div class="trend-stack"><i class="trend-personnel" style="height:40%"></i><i class="trend-contract" style="height:48%"></i><i class="trend-expense" style="height:8%"></i></div><small>7 月</small></div><div class="trend-month current"><div class="trend-stack"><i class="trend-personnel" style="height:18%"></i><i class="trend-contract" style="height:68%"></i><i class="trend-expense" style="height:7%"></i></div><small>8 月</small></div></div></div></div></section>
      <section class="section analysis-card closeout-card"><div class="section-head"><div><h2>结项资金风险</h2><p class="muted">围绕 2026-09-18 计划结项日判断</p></div>${tag('需要关注', 'warning')}</div><div class="analysis-card-body"><div class="closeout-hero"><div class="closeout-days"><strong>21</strong><span>天</span></div><div><strong>项目进入结项准备窗口</strong><p>结项前仍有收付款事项，建议本周完成计划。</p></div></div><div class="closeout-grid"><div class="closeout-metric income"><span>结项前待收</span><strong class="number">${money(180000)}</strong><small>1 个收入阶段 · 覆盖率 0%</small></div><div class="closeout-metric expense"><span>结项前待付</span><strong class="number">${money(95000)}</strong><small>1 个支出阶段 · 已逾期</small></div><div class="closeout-metric"><span>结项后待收</span><strong class="number">${money(600000)}</strong><small>质保及后续阶段</small></div><div class="closeout-metric"><span>结项后待付</span><strong class="number">${money(80000)}</strong><small>现场服务尾款</small></div></div><div class="closeout-status"><span class="status-marker danger"></span><div><strong>结项资金未闭合</strong><p>1 个阶段已逾期，2 个阶段计划在结项后完成。</p></div><button class="btn btn-quiet btn-sm" data-toast="原型示意：已定位风险阶段">查看风险</button></div></div></section></div>
    <section class="section analysis-card settlement-analysis" data-project-analysis><div class="section-head"><div><h2>合同阶段收付款分析</h2><p class="muted">阶段结算率和合同收付款单笔数直接展示，未审批单据不计入已收已付</p></div><div class="settlement-summary"><span>结项前待收 <strong class="amount-danger">¥180,000</strong></span><span>结项前待付 <strong class="amount-danger">¥95,000</strong></span></div></div><div class="analysis-tabs"><button class="analysis-tab active" data-analysis-tab="income">收入合同 <span>${money(incomeContract)}</span></button><button class="analysis-tab" data-analysis-tab="expense">支出合同 <span>${money(expenseContract)}</span></button></div><div class="analysis-stage-panel" data-side="income"><div class="contract-summary-line"><div><strong>智慧工地机器人协同平台采购合同</strong><small>HT-SR-2026-014 · 四川华西集团</small></div><span class="contract-summary-amount"><strong>${money(incomeContract)}</strong><small>已收 ${money(selected.received)} · 总进度 35%</small></span></div><div class="analysis-table-head"><span>合同阶段</span><span>计划金额</span><span>已收</span><span>未收</span><span>结算率</span><span>合同收款单</span><span>状态</span></div>${stageRows('income', incomeStages)}</div><div class="analysis-stage-panel" data-side="expense" hidden><div class="contract-summary-line"><div><strong>视觉传感器及边缘计算设备采购</strong><small>HT-ZC-2026-019 · 成都锐视科技有限公司</small></div><span class="contract-summary-amount"><strong>${money(expenseContract)}</strong><small>已付 ${money(selected.paid)} · 总进度 62%</small></span></div><div class="analysis-table-head"><span>合同阶段</span><span>计划金额</span><span>已付</span><span>未付</span><span>结算率</span><span>合同付款单</span><span>状态</span></div>${stageRows('expense', expenseStages)}</div></section>
    <section class="section analysis-card warning-center" data-project-analysis><div class="section-head"><div><h2>风险与待处理事项</h2><p class="muted">按严重程度和业务日期排序，点击可定位来源</p></div><span class="muted">共 4 项</span></div><div class="warning-list"><div class="warning-row danger"><span class="warning-icon">!</span><div><strong>付款阶段已逾期 8 天</strong><p>支出合同 · 设备到货款 · 未付 ${money(95000)}</p></div><button class="btn btn-sm btn-danger" data-toast="原型示意：打开付款阶段">处理</button></div><div class="warning-row danger"><span class="warning-icon">!</span><div><strong>收入阶段已逾期 8 天</strong><p>收入合同 · 阶段验收款 · 未收 ${money(180000)}</p></div><button class="btn btn-sm btn-danger" data-toast="原型示意：打开收款阶段">处理</button></div><div class="warning-row warning"><span class="warning-icon">△</span><div><strong>距离结项 21 天，结项前资金未闭合</strong><p>结项前待收 ${money(180000)} · 待付 ${money(95000)}</p></div><button class="btn btn-sm" data-toast="原型示意：打开结项风险">查看</button></div><div class="warning-row info"><span class="warning-icon">i</span><div><strong>2 条工时待审批</strong><p>合计 3 人天，审批通过后才计入人员成本</p></div><button class="btn btn-sm" data-route="approvals">处理</button></div></div></section>`
  page.insertAdjacentHTML('beforeend', projectExtraPanels(selected, incomeContract, expenseContract, totalCost, otherProjectCost))
}

function projectExtraPanels(selected, incomeContract, expenseContract, totalCost, otherProjectCost) {
  const logRows = [['2026-08-28 10:28', '系统', '刷新项目经营分析', '重新计算合同、成本和预警指标'], ['2026-08-27 18:06', '杨阳', '提交工时', '现场实施 · 1 天 · 等待审批'], ['2026-08-20 14:22', '杨阳', '更新项目客户', '客户信息已同步为最新主数据']]
  return `<section class="section project-extra-panel" data-project-extra-panel="basic" hidden><div class="section-head"><div><h2>基本信息</h2><p class="muted">项目主数据和当前经营边界</p></div><button class="btn btn-sm" data-edit-project>编辑主信息</button></div><div class="detail-info-grid"><div><span>项目编号</span><strong>${selected.code}</strong></div><div><span>项目类型</span><strong>${selected.type}</strong></div><div><span>项目状态</span><strong>${selected.status}</strong></div><div><span>项目负责人</span><strong>${selected.owner}</strong></div><div><span>所属部门</span><strong>${selected.dept}</strong></div><div><span>客户</span><strong>${selected.customer}</strong></div><div><span>工时填报</span><strong>${selected.worklog ? '允许填报' : '已关闭'}</strong></div><div><span>计划结项</span><strong>2026-09-18</strong></div></div></section>
    <section class="section project-extra-panel" data-project-extra-panel="people" hidden><div class="section-head"><div><h2>人员与工时</h2><p class="muted">审批链、填报规则和已审批投入摘要</p></div><span class="tag primary">${selected.days} / ${selected.budgetDays} 天</span></div><div class="kpi-row compact-kpi"><div class="kpi"><label>已审批工时</label><strong>${selected.days} 天</strong><small>计入人员成本</small></div><div class="kpi warning"><label>待审批工时</label><strong>2 条</strong><small>合计 3 天</small></div><div class="kpi"><label>审批人</label><strong>${selected.owner}</strong><small>项目审批节点</small></div><div class="kpi"><label>上级领导</label><strong>樊公海</strong><small>审批人是本人时启用</small></div></div><div class="detail-info-grid"><div><span>工时规则</span><strong>同一人员同一天仅能填报一次</strong></div><div><span>日期规则</span><strong>开始和结束日期不得跨月</strong></div><div><span>审批方式</span><strong>每条工时单独审批</strong></div><div><span>成本口径</span><strong>审批通过后按人员成本快照计算</strong></div></div><button class="btn btn-sm" data-route="worklog-ledger">查看项目工时台账</button></section>
    <section class="section project-extra-panel" data-project-extra-panel="budget" hidden><div class="section-head"><div><h2>预算执行</h2><p class="muted">预算值可维护，实际值只展示已审批和已确认结果</p></div><span class="tag ${totalCost / selected.budget > .85 ? 'danger' : 'success'}">成本使用 ${Math.round(totalCost / selected.budget * 100)}%</span></div><div class="budget-detail-grid"><div class="budget-detail-item"><span>人天预算</span><strong>${selected.budgetDays} 天</strong><div>${progress(Math.round(selected.days / selected.budgetDays * 100), 'warning')}</div><small>已发生 ${selected.days} 天 · 剩余 ${selected.budgetDays - selected.days} 天</small></div><div class="budget-detail-item"><span>成本预算</span><strong>${money(selected.budget)}</strong><div>${progress(Math.round(totalCost / selected.budget * 100), totalCost / selected.budget > .85 ? 'warning' : '')}</div><small>已发生 ${money(totalCost)} · 剩余 ${money(Math.max(selected.budget - totalCost, 0))}</small></div><div class="budget-detail-item"><span>人员成本</span><strong>${money(selected.staffCost)}</strong><small>已审批工时 × 加权平均人员单价</small></div><div class="budget-detail-item"><span>合同成本</span><strong>${money(selected.paid)}</strong><small>已确认合同付款累计</small></div><div class="budget-detail-item"><span>项目费用</span><strong>${money(otherProjectCost)}</strong><small>已审批差旅、无合同发票及其他费用</small></div></div></section>
    <section class="section project-extra-panel" data-project-extra-panel="funds" hidden><div class="section-head"><div><h2>合同与资金</h2><p class="muted">收入和支出合同统一查看，可继续进入合同详情</p></div><div class="inline-actions"><button class="btn btn-sm" data-route="receipts">查看收款</button><button class="btn btn-sm" data-route="payments">查看付款</button></div></div><div class="financial-split"><div class="financial-side"><h3>收入合同 <span class="tag success">${money(incomeContract)}</span></h3><div class="money-grid"><div class="money-item income"><span>已收</span><strong>${money(selected.received)}</strong></div><div class="money-item"><span>应收</span><strong>${money(selected.receivable)}</strong></div><div class="money-item"><span>待收阶段</span><strong>2 个</strong></div></div><button class="btn btn-quiet btn-sm" data-contract-detail="0">智慧工地机器人协同平台采购合同 →</button></div><div class="financial-side"><h3>支出合同 <span class="tag warning">${money(expenseContract)}</span></h3><div class="money-grid"><div class="money-item expense"><span>已付</span><strong>${money(selected.paid)}</strong></div><div class="money-item"><span>应付</span><strong>${money(selected.payable)}</strong></div><div class="money-item"><span>待付阶段</span><strong>1 个</strong></div></div><button class="btn btn-quiet btn-sm" data-contract-detail="1">视觉传感器及边缘计算设备采购 →</button></div></div></section>
    <section class="section project-extra-panel" data-project-extra-panel="expenses" hidden><div class="section-head"><div><h2>费用明细</h2><p class="muted">差旅、无合同发票和其他费用按审批通过口径计入项目成本</p></div><div class="inline-actions"><button class="btn btn-sm" data-route="project-expenses">查看全部费用</button><button class="btn btn-primary btn-sm" data-expense-form>＋ 新增费用</button></div></div><div class="project-expense-summary"><div><span>项目费用成本</span><strong>${money(otherProjectCost)}</strong><small>占项目总成本 ${Math.round(otherProjectCost / totalCost * 100)}%</small></div><div><span>差旅成本</span><strong>${money(6320)}</strong><small>3 笔已审批</small></div><div><span>无合同发票</span><strong>${money(12800)}</strong><small>1 笔审批中</small></div><div><span>其他成本</span><strong>${money(4080)}</strong><small>2 笔已完成</small></div><div><span>待支付</span><strong class="amount-negative">${money(16660)}</strong><small>审批与支付状态分开</small></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>费用单</th><th>类型</th><th>申请人</th><th>发生日期</th><th class="right">项目成本</th><th>审批状态</th></tr></thead><tbody>${projectExpenses.filter(x => x.projectCode === selected.code).slice(0,3).map(x => `<tr class="click-row" data-route="expense-detail" data-id="${x.id}"><td><span class="cell-main">${x.no}</span><span class="cell-sub">${x.purpose}</span></td><td>${x.type}</td><td>${x.applicant}</td><td>${x.occurred}</td><td class="number right"><strong>${money(x.cost)}</strong></td><td>${tag(x.status, x.tone)}</td></tr>`).join('')}</tbody></table></div></section>
    <section class="section project-extra-panel" data-project-extra-panel="logs" hidden><div class="section-head"><div><h2>操作记录</h2><p class="muted">项目主数据、工时和经营分析的关键变更</p></div><span class="muted">最近 30 天</span></div><div class="timeline">${logRows.map(row => `<div class="timeline-item done"><span class="timeline-date">${row[0]}</span><i class="timeline-dot"></i><div class="timeline-copy"><strong>${row[1]} · ${row[2]}</strong><p>${row[3]}</p></div></div>`).join('')}</div></section>`
}

function renderContracts() {
  const rows = contracts.map((c, index) => {
    const ratio = Math.round(c.settled / c.amount * 100)
    const overdue = c.nextDate < '2026-08-28'
    return `<tr class="click-row" data-contract-detail="${index}"><td style="width:19%"><span class="cell-main">${c.name}</span><span class="cell-sub">${c.no}</span></td><td style="width:17%"><span class="cell-main">${c.project}</span></td><td style="width:13%">${c.partner}</td><td style="width:10%" class="right strong number">${money(c.amount)}</td><td style="width:11%"><div class="contract-progress">${progress(ratio, c.kind === '收入合同' ? '' : 'warning')}<span>${ratio}%</span></div><span class="cell-sub">阶段 ${c.stages}</span></td><td style="width:10%" class="right number">${money(c.settled)}</td><td style="width:10%"><span class="${overdue ? 'amount-danger' : 'amount-negative'}">${money(c.due)}</span><span class="cell-sub">${c.nextDate}</span></td><td style="width:7%">${tag(c.status,'success')}</td><td style="width:94px" class="right"><button class="btn btn-quiet btn-sm" data-contract-detail="${index}">查看</button></td></tr>`
  }).join('')
  page.innerHTML = `${pageHead('合同与结算阶段', '项目合同', '收入、支出合同统一管理，每份合同可拆分多个收款或付款阶段。', '<button class="btn btn-primary" data-contract-form>＋ 新增合同</button>')}
    <div class="tabs" style="margin-bottom:14px"><button class="tab active">全部合同 <span class="tag">18</span></button><button class="tab">收入合同 <span class="tag success">7</span></button><button class="tab">支出合同 <span class="tag warning">11</span></button></div>
    ${filterBar(`<div class="field wide"><label>项目</label><select class="control"><option>全部项目</option>${projects.map(p=>`<option>${p.name}</option>`).join('')}</select></div><div class="field"><label>合同状态</label><select class="control"><option>全部状态</option><option>草稿</option><option>生效</option><option>已完成</option></select></div><div class="field"><label>到期状态</label><select class="control"><option>全部</option><option>即将到期</option><option>已逾期</option><option>已完成</option></select></div><div class="field"><label>签订日期</label><input type="month" class="control" value="2026-08"></div><div class="field grow"><label>合同 / 往来单位</label><input class="control" placeholder="合同编号、名称、客户或供应商"></div>`)}
    <section class="section"><div class="section-head"><div><h2>合同清单</h2><p class="muted">合同金额 ${money(4810000)} · 当前应收 ${money(540000)} · 当前应付 ${money(315000)}</p></div><button class="btn btn-sm" data-toast="合同清单已导出">导出</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>合同</th><th>项目</th><th>客户 / 供应商</th><th class="right">合同金额</th><th>结算进度</th><th class="right">已收 / 已付</th><th>待收 / 待付</th><th>状态</th><th class="right">操作</th></tr></thead><tbody>${rows}</tbody></table></div>${pagination(18)}</section>`
}

function receiptPaymentRows(kind) {
  const receipt = kind === 'receipt'
  const rows = receipt ? [
    ['SK-2026-0091', '智慧工地机器人协同平台', '阶段验收款', '四川华西集团', '2026-08-27', 180000, '待审批', '杨阳'],
    ['SK-2026-0086', '智慧工地机器人协同平台', '合同首付款', '四川华西集团', '2026-07-15', 420000, '已通过', '杨阳'],
    ['SK-2026-0081', '自动化钢筋加工产线交付项目', '发货款', '中铁八局', '2026-07-02', 360000, '已通过', '李明']
  ] : [
    ['FK-2026-0072', '智慧工地机器人协同平台', '设备到货款', '成都锐视科技有限公司', '2026-08-28', 95000, '待审批', '杨阳'],
    ['FK-2026-0068', '建筑物流搬运机器人研发与应用', '底盘预付款', '四川精工智能装备有限公司', '2026-08-18', 86000, '已通过', '杨阳'],
    ['FK-2026-0061', '自动化钢筋加工产线交付项目', '控制柜采购款', '成都电气成套有限公司', '2026-08-03', 210000, '已通过', '李明']
  ]
  return rows.map((r,index) => `<tr class="click-row" data-cash-detail="${kind}-${index}"><td><span class="cell-main">${r[0]}</span><span class="cell-sub">${r[4]}</span></td><td><span class="cell-main">${r[1]}</span><span class="cell-sub">${r[2]}</span></td><td>${r[3]}</td><td class="right strong number">${money(r[5])}</td><td>${tag(r[6], r[6] === '已通过' ? 'success' : 'warning')}</td><td>${r[7]}</td><td class="right"><button class="btn btn-quiet btn-sm" data-cash-detail="${kind}-${index}">${r[6] === '待审批' ? '审批' : '查看'}</button></td></tr>`).join('')
}

function renderCashList(kind) {
  const receipt = kind === 'receipt'
  const title = receipt ? '合同收款' : '合同付款'
  const noun = receipt ? '收款' : '付款'
  const route = receipt ? 'receipts' : 'payments'
  page.innerHTML = `${pageHead('资金单据与出纳确认', title, `${noun}单关联项目合同阶段，通过出纳审批后才计入项目经营数据。`, `<button class="btn btn-primary" data-${receipt ? 'receipt' : 'payment'}-form>＋ 新增${noun}单</button>`)}
    <div class="tabs" style="margin-bottom:14px"><button class="tab active">待我审批 ${tag(receipt ? '2' : '1','warning')}</button><button class="tab">全部单据</button><button class="tab">我发起的</button></div>
    ${filterBar(`<div class="field"><label>单据状态</label><select class="control"><option>全部状态</option><option>待审批</option><option>已通过</option><option>已驳回</option><option>已冲销</option></select></div><div class="field wide"><label>项目</label><select class="control"><option>全部项目</option>${projects.map(p=>`<option>${p.name}</option>`).join('')}</select></div><div class="field wide"><label>${receipt ? '客户' : '供应商'}</label><select class="control"><option>全部${receipt ? '客户' : '供应商'}</option></select></div><div class="field"><label>${noun}日期</label><input type="month" class="control" value="2026-08"></div><div class="field grow"><label>关键字</label><input class="control" placeholder="单号、合同或阶段名称"></div>`)}
    <section class="section"><div class="section-head"><div><h2>${noun}单据</h2><p class="muted">待审批金额 ${receipt ? money(180000) : money(95000)}</p></div><button class="btn btn-sm" data-toast="${noun}明细已导出">导出</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th style="width:15%">单据</th><th style="width:27%">项目 / 合同阶段</th><th style="width:19%">${receipt ? '客户' : '供应商'}</th><th class="right" style="width:13%">${noun}金额</th><th style="width:10%">状态</th><th style="width:9%">发起人</th><th class="right" style="width:90px">操作</th></tr></thead><tbody>${receiptPaymentRows(kind)}</tbody></table></div>${pagination(12)}</section>`
}

function renderProjectBoard() {
  page.innerHTML = `${pageHead('项目经营分析', '项目看板', '收入、成本、应收、应付、毛利和风险均可下钻到项目与单据。', '<button class="btn" data-toast="项目经营明细已导出">导出明细</button>')}
    ${filterBar(`<div class="field"><label>数据范围</label><div class="segmented"><button class="active">我的项目</button><button>全部项目</button></div></div><div class="field"><label>项目类型</label><select class="control"><option>全部类型</option><option>实施项目</option><option>研发项目</option><option>课题项目</option></select></div>${departmentTree()}<div class="field"><label>负责人</label><select class="control"><option>全部负责人</option><option>杨阳</option><option>樊公海</option></select></div><div class="field wide"><label>项目</label><select class="control"><option>全部项目</option>${projects.map(p=>`<option>${p.name}</option>`).join('')}</select></div><div class="field"><label>统计截止</label><input type="date" class="control" value="2026-08-28"></div>`)}
    <section class="section"><div class="section-head"><div><h2>经营结果</h2><p class="muted">实际收付款口径 · 截止 2026-08-28</p></div>${tag('6 个项目','primary')}</div><div class="kpi-row"><div class="kpi"><label>项目收入</label><strong>${money(1140000)}</strong><small>已审批收款</small></div><div class="kpi"><label>总成本</label><strong>${money(1019000)}</strong><small>人员 ${money(386000)} · 外部 ${money(633000)}</small></div><div class="kpi"><label>当前毛利</label><strong class="amount-positive">${money(121000)}</strong><small>毛利率 10.6%</small></div><div class="kpi warning"><label>经营风险</label><strong>5 项</strong><small>逾期 3 · 超预算 2</small></div></div></section>
    <section class="section"><div class="owner-summary"><div class="summary-item"><div class="label">已收</div><div class="value">${money(1140000)}</div><div class="hint">收入合同确认收款</div></div><div class="summary-item warn"><div class="label">应收</div><div class="value">${money(540000)}</div><div class="hint">逾期 ${money(360000)}</div></div><div class="summary-item"><div class="label">已付</div><div class="value">${money(633000)}</div><div class="hint">审批通过的付款</div></div><div class="summary-item warn"><div class="label">应付</div><div class="value">${money(346000)}</div><div class="hint">逾期 ${money(120000)}</div></div><div class="summary-item alert"><div class="label">预算预警</div><div class="value">2</div><div class="hint">人天 1 · 成本 1</div></div></div></section>
    <div class="chart-grid"><section class="chart wide"><div class="chart-head"><h3>近 6 个月收支趋势</h3><div class="legend"><span><i class="income"></i>已收</span><span><i class="expense"></i>已付</span><span><i class="cost"></i>人员成本</span></div></div><div class="bar-chart">${[['3月',35,22,16],['4月',52,31,19],['5月',44,40,25],['6月',70,48,28],['7月',83,63,31],['8月',66,54,34]].map(x=>`<div class="bar-group"><i class="bar income" style="height:${x[1]}%"></i><i class="bar expense" style="height:${x[2]}%"></i><i class="bar cost" style="height:${x[3]}%"></i><span class="bar-label">${x[0]}</span></div>`).join('')}</div></section>
      <section class="chart"><div class="chart-head"><h3>项目毛利排行</h3><span class="muted">实施项目</span></div><div class="horizontal-bars"><div class="hbar-row"><label>智慧工地机器人协同平台</label><div class="hbar-track"><span class="success" style="width:88%"></span></div><strong>¥99,000</strong></div><div class="hbar-row"><label>自动化钢筋加工产线</label><div class="hbar-track"><span class="success" style="width:64%"></span></div><strong>¥72,000</strong></div><div class="hbar-row"><label>智能仓储交付项目</label><div class="hbar-track"><span class="success" style="width:38%"></span></div><strong>¥43,000</strong></div><div class="hbar-row"><label>移动喷涂机器人项目</label><div class="hbar-track"><span class="warning" style="width:22%"></span></div><strong>-¥18,000</strong></div></div></section>
      <section class="chart"><div class="chart-head"><h3>应收应付账龄</h3><span class="muted">共 ${money(886000)}</span></div><div class="donut-layout"><div class="donut"></div><div class="donut-legend"><div><span>${tag('已逾期','danger')} 30 天以上</span><strong>${money(142000)}</strong></div><div><span>${tag('临近到期','warning')} 0-30 天</span><strong>${money(240000)}</strong></div><div><span>${tag('计划中','info')} 31-90 天</span><strong>${money(168000)}</strong></div><div><span>${tag('远期','primary')} 90 天以上</span><strong>${money(336000)}</strong></div></div></div></section>
    </div>`
}

function renderEntities(kind) {
  const supplier = kind === 'supplier'
  const title = supplier ? '供应商管理' : '客户管理'
  const entities = supplier ? [
    ['SUP-00018','成都锐视科技有限公司','成都锐视','91510100MA6CF2****','周经理 · 138****6638','招商银行成都高新支行 · 尾号 7821'],
    ['SUP-00011','四川精工智能装备有限公司','四川精工','91510114MA63K8****','刘工 · 139****2806','中国银行郫都支行 · 尾号 0916'],
    ['SUP-00007','成都电气成套有限公司','成都电气','91510107MA6A9F****','王经理 · 135****4472','建设银行武侯支行 · 尾号 3058'],
    ['SUP-00022','上海智联传感技术有限公司','智联传感','91310115MA1K4D****','陈工 · 186****1209','浦发银行张江支行 · 尾号 6125']
  ] : [
    ['CUS-00006','四川华西集团有限公司','四川华西','915100002018088****','谢经理 · 138****5182','一般纳税人 · 尾号 6018'],
    ['CUS-00009','中铁八局集团有限公司','中铁八局','915101002019735****','赵经理 · 189****0266','一般纳税人 · 尾号 1142'],
    ['CUS-00013','成都市住房和城乡建设局','成都市住建局','11510100MB0U995****','李老师 · 028-****3156','政府单位'],
    ['CUS-00017','四川省建筑科学研究院有限公司','四川建科院','915100004507174****','袁工 · 136****9087','一般纳税人 · 尾号 2280']
  ]
  const cards = entities.map(x=>`<article class="entity-card click-row" data-entity-form="${kind}"><div class="entity-head"><div><h3>${x[1]}</h3><small class="muted">${x[0]} · ${x[2]}</small></div>${tag('启用','success')}</div><div class="entity-info"><span>信用代码</span><strong>${x[3]}</strong><span>联系人</span><strong>${x[4]}</strong><span>${supplier ? '默认账户' : '开票信息'}</span><strong>${x[5]}</strong></div></article>`).join('')
  page.innerHTML = `${pageHead('往来单位主数据', title, `${supplier ? '供应商账户可在合同付款单中自动带出并形成单据快照。' : '客户信息用于收入合同、合同收款单和开票资料。'}`, `<button class="btn btn-primary" data-entity-form="${kind}">＋ 新增${supplier ? '供应商' : '客户'}</button>`)}
    ${filterBar(`<div class="field"><label>状态</label><select class="control"><option>全部状态</option><option>启用</option><option>停用</option></select></div><div class="field"><label>所在地区</label><select class="control"><option>全部地区</option><option>四川省</option><option>上海市</option></select></div><div class="field grow"><label>${supplier ? '供应商' : '客户'}名称 / 编码</label><input class="control" placeholder="输入名称、简称、编码或信用代码"></div>`)}
    <section class="section"><div class="section-head"><div><h2>${supplier ? '供应商' : '客户'}列表</h2><p class="muted">共 ${supplier ? 23 : 17} 家 · 启用 ${supplier ? 21 : 16} 家</p></div><button class="btn btn-sm" data-toast="往来单位清单已导出">导出</button></div><div class="directory-grid">${cards}</div>${pagination(supplier ? 23 : 17)}</section>`
}

function renderPermissions() {
  const people = [
    ['杨阳','产品研发部 / 信息化中心','系统管理员','全部项目',['✓','✓','✓','✓']],
    ['贺茂维','财务部','出纳','全部项目',['—','✓','✓','—']],
    ['樊公海','产品研发部','项目管理员','指定部门及下级',['✓','✓','—','—']],
    ['李明','技术服务部 / 交付中心','项目负责人','本人负责项目',['✓','—','—','—']]
  ]
  const rows = people.map((p,i)=>`<div class="permission-row"><div class="person"><span class="avatar">${p[0][0]}</span><span class="person-copy"><strong>${p[0]}</strong><small>${p[1]}</small></span></div><div>${tag(p[2], i===0?'primary':i===1?'warning':'outline')}</div><div><span class="cell-main">${p[3]}</span></div>${p[4].map(x=>`<div class="center ${x==='✓'?'permission-mark':'permission-empty'}">${x}</div>`).join('')}<div class="right"><button class="btn btn-quiet btn-sm" data-permission-form>配置</button></div></div>`).join('')
  page.innerHTML = `${pageHead('系统权限与数据范围', '管理员管理', '这里只显示已加入的管理员，普通员工不会出现在列表中。', '<button class="btn btn-primary" data-permission-form>＋ 添加管理员</button>')}
    <div class="notice" style="margin-bottom:14px"><span>i</span><div><strong>角色与数据范围分别控制</strong><p>模块权限决定能做什么，数据范围决定能查看哪些项目。出纳审批为独立权限。</p></div></div>
    ${filterBar(`<div class="field"><label>管理角色</label><select class="control"><option>全部角色</option><option>系统管理员</option><option>项目管理员</option><option>出纳</option></select></div><div class="field"><label>数据范围</label><select class="control"><option>全部范围</option><option>本人负责项目</option><option>指定部门及下级</option><option>全部项目</option></select></div><div class="field grow"><label>管理员</label><input class="control" placeholder="输入姓名或部门"></div>`)}
    <section class="section"><div class="section-head"><div><h2>已配置管理员</h2><p class="muted">4 人 · 系统管理员 1 人 · 出纳 1 人</p></div></div><div class="permission-row header"><span>管理员</span><span>角色</span><span>数据范围</span><span class="center">项目管理</span><span class="center">收付款</span><span class="center">系统管理</span><span class="center">出纳审批</span><span class="right">操作</span></div>${rows}</section>`
}

function renderMyWorklogs() {
  const rows = [
    ['2026-08-28', '智慧工地机器人协同平台', '现场实施', '现场完成机器人调度服务联调', '1 天', '审批通过', 'success'],
    ['2026-08-27', '建筑物流搬运机器人研发与应用', '开发', '完成路径规划模块接口联调', '1 天', '审批中', 'warning'],
    ['2026-08-26', '机器人集群智能调度管理系统课题', '方案设计', '整理课题技术路线和阶段成果', '0.5 天', '已驳回', 'danger'],
    ['2026-08-25', '智慧工地机器人协同平台', '测试', '补充现场异常场景测试记录', '1 天', '审批通过', 'success'],
    ['2026-08-22', '建筑物流搬运机器人研发与应用', '评审', '参加研发方案评审并输出纪要', '0.5 天', '审批通过', 'success']
  ]
  const body = rows.map((r, i) => `<tr class="click-row" data-worklog-detail="${i}"><td><span class="cell-main">${r[0]}</span><span class="cell-sub">${r[4]}</span></td><td><span class="cell-main">${r[1]}</span><span class="cell-sub">${r[2]}</span></td><td><span class="truncate">${r[3]}</span></td><td>${tag(r[5], r[6])}</td><td class="right"><button class="btn btn-quiet btn-sm" data-worklog-detail="${i}">查看</button></td></tr>`).join('')
  page.innerHTML = `${pageHead('工时管理 / 个人记录', '我的工时', '按天填报项目投入，查看完整审批状态和处理时间线。', '<button class="btn btn-primary" data-worklog-form>＋ 填报工时</button>')}
    <section class="section"><div class="owner-summary"><div class="summary-item"><div class="label">本月已审批</div><div class="value">18.5 天</div><div class="hint">较上月增加 2.5 天</div></div><div class="summary-item warn"><div class="label">待审批</div><div class="value">2 条</div><div class="hint">合计 2 天</div></div><div class="summary-item alert"><div class="label">待修改</div><div class="value">1 条</div><div class="hint">请补充工作内容</div></div><div class="summary-item"><div class="label">本月填报天数</div><div class="value">21 天</div><div class="hint">覆盖 3 个项目</div></div><div class="summary-item"><div class="label">审批通过率</div><div class="value">90.5%</div><div class="hint">按工时单统计</div></div></div></section>
    ${filterBar(`<div class="field"><label>审批状态</label><select class="control"><option>全部状态</option><option>草稿</option><option>审批中</option><option>审批通过</option><option>已驳回</option></select></div><div class="field wide"><label>项目</label><select class="control"><option>全部项目</option>${projects.slice(0, 3).map(p => `<option>${p.name}</option>`).join('')}</select></div><div class="field"><label>填报月份</label><input type="month" class="control" value="2026-08"></div><div class="field grow"><label>工作内容</label><input class="control" placeholder="搜索工作内容"></div>`)}
    <section class="section"><div class="section-head"><div><h2>工时记录</h2><p class="muted">每条记录单独审批，点击行查看完整详情</p></div><button class="btn btn-sm" data-toast="工时明细导出已开始">导出明细</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th style="width:14%">填报日期</th><th style="width:31%">项目 / 工作阶段</th><th>工作内容</th><th style="width:15%">审批状态</th><th class="right" style="width:82px">操作</th></tr></thead><tbody>${body}</tbody></table></div>${pagination(21)}</section>`
}

function worklogDetail(index = 0) {
  const details = [
    ['2026-08-28', '智慧工地机器人协同平台', '现场实施', '现场完成机器人调度服务联调，并核对设备状态上报结果。', '杨阳', '审批通过', 'success'],
    ['2026-08-27', '建筑物流搬运机器人研发与应用', '开发', '完成路径规划模块接口联调，补充异常路径日志。', '樊公海', '审批中', 'warning'],
    ['2026-08-26', '机器人集群智能调度管理系统课题', '方案设计', '整理课题技术路线和阶段成果。', '上级领导待处理', '已驳回', 'danger']
  ]
  const item = details[index % details.length]
  openModal({ eyebrow: '工时详情 · 单条审批', title: `${item[0]} · ${item[1]}`, wide: true, body: `<div class="notice ${item[6]}" style="margin-bottom:16px"><span>${item[6] === 'success' ? '✓' : item[6] === 'danger' ? '!' : 'i'}</span><div><strong>${item[5]}</strong><p>该工时单独计算审批状态，审批通过后计入项目已发生人天和人员成本。</p></div></div><div class="form-grid cols-3"><div class="form-field"><label>项目</label><strong>${item[1]}</strong></div><div class="form-field"><label>工作阶段</label><strong>${item[2]}</strong></div><div class="form-field"><label>工时</label><strong>1 天</strong></div><div class="form-field"><label>开始日期</label><strong>${item[0]}</strong></div><div class="form-field"><label>结束日期</label><strong>${item[0]}</strong></div><div class="form-field"><label>审批人</label><strong>${item[4]}</strong></div><div class="form-field span-3"><label>工作内容</label><div class="readonly detail-copy">${item[3]}</div></div></div><h3 style="margin:22px 0 12px">审批时间线</h3><div class="timeline"><div class="timeline-item done"><span class="timeline-date">${item[0]} 18:06</span><i class="timeline-dot"></i><div class="timeline-copy"><strong>杨阳提交工时</strong><p>单条工时审批任务已生成</p></div></div><div class="timeline-item ${item[6] === 'danger' ? 'danger' : item[6] === 'success' ? 'done' : 'warn'}"><span class="timeline-date">${item[5] === '审批中' ? '待处理' : item[0] + ' 19:20'}</span><i class="timeline-dot"></i><div class="timeline-copy"><strong>${item[4]} · ${item[5]}</strong><p>${item[6] === 'danger' ? '请补充实际工作内容后重新提交' : item[5] === '审批中' ? '飞书卡片已发送，等待审批' : '已通过，已计入项目工时'}</p></div></div></div>`, foot: `<button class="btn" data-close-modal>关闭</button>${item[6] === 'danger' ? '<button class="btn btn-primary" data-worklog-form>修改并重新提交</button>' : ''}` })
}

function renderApprovals() {
  const pending = [
    ['2026-08-27', '杨阳', '建筑物流搬运机器人研发与应用', '开发', '1 天', '等待审批'],
    ['2026-08-26', '李明', '自动化钢筋加工产线交付项目', '现场实施', '1 天', '等待审批'],
    ['2026-08-25', '张敏', '智能建造装备现场观摩活动', '观摩准备', '0.5 天', '等待审批']
  ]
  const approved = [
    ['2026-08-28', '杨阳', '智慧工地机器人协同平台', '现场实施', '1 天', '已通过'],
    ['2026-08-22', '李明', '自动化钢筋加工产线交付项目', '验收支持', '1 天', '已通过'],
    ['2026-08-21', '张敏', '智能建造装备现场观摩活动', '活动执行', '1 天', '已驳回']
  ]
  const rows = (items, offset = 0) => items.map((r, i) => `<tr class="click-row" data-worklog-detail="${i + offset}"><td><span class="cell-main">${r[0]}</span><span class="cell-sub">${r[4]}</span></td><td><span class="cell-main">${r[1]}</span><span class="cell-sub">${r[2]}</span></td><td>${r[3]}</td><td>${tag(r[5], r[5] === '已通过' ? 'success' : r[5] === '已驳回' ? 'danger' : 'warning')}</td><td class="right"><button class="btn btn-quiet btn-sm" data-worklog-detail="${i + offset}">${r[5] === '等待审批' ? '审批' : '查看'}</button></td></tr>`).join('')
  page.innerHTML = `${pageHead('工时管理 / 审批中心', '工时审批', '逐条处理工时审批任务，审批通过后才计入项目工时和人员成本。', '<button class="btn" data-toast="审批列表已刷新">刷新</button>')}
    <div class="tabs page-tabs"><button class="tab active">待我审批 <span class="tag warning">3</span></button><button class="tab">已审批 <span class="tag">18</span></button></div>
    <section class="section"><div class="section-head"><div><h2>待我审批</h2><p class="muted">共 3 条 · 合计 2.5 人天</p></div><span class="tag warning">需要处理</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th style="width:14%">提交日期</th><th style="width:32%">提交人 / 项目</th><th>工作阶段</th><th style="width:16%">状态</th><th class="right" style="width:82px">操作</th></tr></thead><tbody>${rows(pending)}</tbody></table></div>${pagination(3)}</section>
    <section class="section"><div class="section-head"><div><h2>审批规则</h2><p class="muted">每个工时填报单单独审批；审批人是填报人时自动转上级领导。</p></div><span class="muted">飞书消息已接入</span></div><div class="section-body"><div class="timeline"><div class="timeline-item done"><span class="timeline-date">提交工时</span><i class="timeline-dot"></i><div class="timeline-copy"><strong>生成单条审批任务</strong><p>审批人收到飞书应用消息，可从卡片进入系统详情</p></div></div><div class="timeline-item warn"><span class="timeline-date">审批处理</span><i class="timeline-dot"></i><div class="timeline-copy"><strong>通过或驳回</strong><p>结果同步到我的工时、工作台和项目统计</p></div></div></div></div></section>`
}

function renderWorklogBoard() {
  page.innerHTML = `${pageHead('工时管理 / 数据分析', '工时看板', '只看工时投入、人员分布和审批效率，不混入项目成本与资金指标。', '<button class="btn" data-toast="工时看板已查询">查询</button>')}
    ${filterBar(`<div class="field"><label>时间范围</label><select class="control"><option>本月</option><option>上月</option><option>本季度</option></select></div>${departmentTree()}<div class="field"><label>项目类型</label><select class="control"><option>全部类型</option><option>研发项目</option><option>课题项目</option><option>实施项目</option></select></div><div class="field wide"><label>项目</label><select class="control"><option>全部项目</option>${projects.map(p => `<option>${p.name}</option>`).join('')}</select></div><div class="field"><label>审批状态</label><select class="control"><option>全部状态</option><option>审批通过</option><option>审批中</option><option>已驳回</option></select></div>`)}
    <section class="section"><div class="owner-summary"><div class="summary-item"><div class="label">工时总量</div><div class="value">286.5 天</div><div class="hint">较上月 +12.8%</div></div><div class="summary-item"><div class="label">填报人数</div><div class="value">32 人</div><div class="hint">覆盖 4 个一级部门</div></div><div class="summary-item"><div class="label">涉及项目</div><div class="value">18 个</div><div class="hint">12 个允许填报</div></div><div class="summary-item warn"><div class="label">待审批</div><div class="value">8 条</div><div class="hint">合计 10.5 天</div></div><div class="summary-item"><div class="label">审批通过率</div><div class="value">93.2%</div><div class="hint">按工时单统计</div></div></div></section>
    <div class="chart-grid"><section class="chart wide"><div class="chart-head"><h3>近 6 个月工时趋势</h3><div class="legend"><span><i class="income"></i>审批通过</span><span><i class="expense"></i>审批中</span><span><i class="cost"></i>已驳回</span></div></div><div class="bar-chart">${[['3月',48,8,4],['4月',56,9,3],['5月',62,7,5],['6月',71,10,4],['7月',84,12,6],['8月',92,8,5]].map(x => `<div class="bar-group"><i class="bar income" style="height:${x[1]}%"></i><i class="bar expense" style="height:${x[2]}%"></i><i class="bar cost" style="height:${x[3]}%"></i><span class="bar-label">${x[0]}</span></div>`).join('')}</div></section><section class="chart"><div class="chart-head"><h3>一级部门工时</h3><span class="muted">本月</span></div><div class="horizontal-bars"><div class="hbar-row"><label>产品研发部</label><div class="hbar-track"><span class="success" style="width:88%"></span></div><strong>142 天</strong></div><div class="hbar-row"><label>技术服务部</label><div class="hbar-track"><span class="success" style="width:72%"></span></div><strong>86 天</strong></div><div class="hbar-row"><label>市场营销部</label><div class="hbar-track"><span class="warning" style="width:36%"></span></div><strong>38 天</strong></div><div class="hbar-row"><label>综合管理部</label><div class="hbar-track"><span class="info" style="width:19%"></span></div><strong>20.5 天</strong></div></div></section><section class="chart"><div class="chart-head"><h3>工时项目分布</h3><span class="muted">按天数</span></div><div class="donut-layout"><div class="donut worklog-donut"></div><div class="donut-legend"><div><span>${tag('实施项目','success')}</span><strong>132 天</strong></div><div><span>${tag('研发项目','primary')}</span><strong>91 天</strong></div><div><span>${tag('课题项目','warning')}</span><strong>43.5 天</strong></div><div><span>${tag('观摩项目','info')}</span><strong>20 天</strong></div></div></div></section></div>
    <section class="section"><div class="section-head"><div><h2>工时明细</h2><p class="muted">可以进入工时台账查看全部日志</p></div><button class="btn btn-sm" data-route="worklog-ledger">查看明细</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>部门</th><th>人员</th><th>工时天数</th><th>审批通过率</th><th>主要项目</th></tr></thead><tbody><tr><td>产品研发部 / 信息化中心</td><td>杨阳</td><td class="number">36 天</td><td>${tag('100%', 'success')}</td><td>智慧工地机器人协同平台</td></tr><tr><td>技术服务部 / 交付中心</td><td>李明</td><td class="number">28.5 天</td><td>${tag('96%', 'success')}</td><td>自动化钢筋加工产线交付项目</td></tr><tr><td>产品研发部 / 机器人中心</td><td>樊公海</td><td class="number">24 天</td><td>${tag('88%', 'warning')}</td><td>建筑物流搬运机器人研发与应用</td></tr></tbody></table></div></section>`
}

function renderWorklogLedger() {
  const rows = [
    ['2026-08-28', '杨阳', '产品研发部 / 信息化中心', '智慧工地机器人协同平台', '现场实施', '1 天', '审批通过'],
    ['2026-08-27', '李明', '技术服务部 / 交付中心', '自动化钢筋加工产线交付项目', '现场实施', '1 天', '审批中'],
    ['2026-08-26', '樊公海', '产品研发部 / 信息化中心', '机器人集群智能调度管理系统课题', '方案设计', '0.5 天', '已驳回'],
    ['2026-08-25', '张敏', '市场营销部', '智能建造装备现场观摩活动', '活动执行', '1 天', '审批通过'],
    ['2026-08-22', '周涛', '技术服务部 / 交付中心', '自动化钢筋加工产线交付项目', '调试', '1 天', '审批通过']
  ]
  const body = rows.map((r, i) => `<tr><td>${r[0]}</td><td><span class="cell-main">${r[1]}</span><span class="cell-sub">${r[2]}</span></td><td><span class="truncate">${r[3]}</span></td><td>${r[4]}</td><td class="number">${r[5]}</td><td>${tag(r[6], r[6] === '审批通过' ? 'success' : r[6] === '已驳回' ? 'danger' : 'warning')}</td><td class="right"><button class="btn btn-quiet btn-sm" data-worklog-detail="${i}">查看</button></td></tr>`).join('')
  page.innerHTML = `${pageHead('工时管理 / 后台台账', '工时台账', '授权管理员查看和维护全部工时日志，支持层级部门筛选和明细导出。', '<button class="btn btn-primary" data-toast="工时明细导出已开始">导出明细</button>')}
    ${filterBar(`<div class="field"><label>日期</label><input type="date" class="control" value="2026-08-01"></div><div class="field"><label>至</label><input type="date" class="control" value="2026-08-31"></div>${departmentTree()}<div class="field"><label>人员</label><select class="control"><option>全部人员</option><option>杨阳</option><option>李明</option><option>樊公海</option></select></div><div class="field wide"><label>项目</label><select class="control"><option>全部项目</option>${projects.map(p => `<option>${p.name}</option>`).join('')}</select></div><div class="field"><label>状态</label><select class="control"><option>全部状态</option><option>审批通过</option><option>审批中</option><option>已驳回</option></select></div>`)}
    <section class="section"><div class="section-head"><div><h2>全部工时日志</h2><p class="muted">当前筛选共 286 条，修改和删除受管理员权限及数据状态限制</p></div><span class="tag primary">管理员专属</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th style="width:12%">日期</th><th style="width:18%">人员 / 部门</th><th style="width:23%">项目</th><th>工作阶段</th><th style="width:9%">工时</th><th style="width:12%">状态</th><th class="right" style="width:104px">操作</th></tr></thead><tbody>${body}</tbody></table></div>${pagination(286)}</section>`
}

function personnelCostForm() {
  openModal({ eyebrow: '人员成本', title: '新增 / 编辑人员成本', body: `<div class="form-grid"><div class="form-field"><label class="required">人员</label><select class="control"><option>请选择飞书组织成员</option><option>杨阳 · 信息化中心</option><option>李明 · 交付中心</option><option>樊公海 · 产品研发部</option></select></div><div class="form-field"><label class="required">单天成本</label><input class="control" type="number" value="1000"><small class="form-tip">当前版本暂不设置生效日期，审批时会保留成本快照。</small></div><div class="form-field span-2"><label>备注</label><textarea class="control" rows="3" placeholder="填写成本维护说明"></textarea></div></div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn btn-primary" data-confirm-modal>保存成本</button>' })
}

function renderPersonnelCost() {
  const people = [['杨阳', '产品研发部 / 信息化中心', '1,000', '2026-08-18'], ['樊公海', '产品研发部 / 机器人中心', '1,200', '2026-08-18'], ['李明', '技术服务部 / 交付中心', '900', '2026-08-16'], ['张敏', '市场营销部', '800', '2026-08-12'], ['周涛', '技术服务部 / 交付中心', '850', '2026-08-10']]
  const body = people.map((p, i) => `<tr><td><span class="cell-main">${p[0]}</span><span class="cell-sub">来自飞书组织架构</span></td><td>${p[1]}</td><td class="right number">¥${p[2]} / 天</td><td>${p[3]}</td><td class="right"><button class="btn btn-quiet btn-sm" data-cost-form="${i}">编辑</button></td></tr>`).join('')
  page.innerHTML = `${pageHead('系统管理 / 成本基础数据', '人员成本', '维护已加入人员的单天成本，供审批通过的工时计算项目人员成本。', '<button class="btn btn-primary" data-cost-form>＋ 添加人员成本</button>')}
    <div class="notice" style="margin-bottom:14px"><span>i</span><div><strong>人员均来自飞书组织架构</strong><p>成本值只影响后续审批计算；已审批工时使用审批时保留的单天成本快照。</p></div></div>
    ${filterBar(`<div class="field">${departmentTree().replace('<div class="field tree-control">', '<div class="field tree-control">')}</div><div class="field"><label>人员</label><select class="control"><option>全部人员</option><option>杨阳</option><option>樊公海</option><option>李明</option></select></div><div class="field grow"><label>关键词</label><input class="control" placeholder="搜索姓名或部门"></div>`)}
    <section class="section"><div class="section-head"><div><h2>人员成本清单</h2><p class="muted">已维护 32 人 · 成本数据仅授权管理员可见</p></div><span class="tag primary">分页：20 条/页</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th style="width:18%">人员</th><th>所属部门</th><th class="right" style="width:18%">单天成本</th><th style="width:16%">最近维护</th><th class="right" style="width:80px">操作</th></tr></thead><tbody>${body}</tbody></table></div>${pagination(32)}</section>`
}

function renderIntegration() {
  page.innerHTML = `${pageHead('系统管理 / 飞书连接', '集成与通知', '同步组织架构、检查连接状态并查看飞书应用消息发送记录。', '<button class="btn btn-primary" data-org-sync>同步组织架构</button>')}
    <div class="kpi-row"><div class="kpi"><label>飞书连接</label><strong class="amount-positive">正常</strong><small>最近检查 2 分钟前</small></div><div class="kpi"><label>组织成员</label><strong>128</strong><small>最近同步于今天 09:12</small></div><div class="kpi"><label>今日已发送</label><strong>36</strong><small>应用消息 31 · 卡片 5</small></div><div class="kpi warning"><label>待重试</label><strong>2</strong><small>不会改变业务状态</small></div></div>
    <div class="workbench-grid"><section class="section"><div class="section-head"><div><h2>组织架构同步</h2><p class="muted">人员和部门全部来源于飞书，系统保留业务历史引用。</p></div>${tag('已连接','success')}</div><div class="section-body"><div class="timeline"><div class="timeline-item done"><span class="timeline-date">今天 09:12</span><i class="timeline-dot"></i><div class="timeline-copy"><strong>同步完成</strong><p>新增 3 人、更新 8 人、更新 2 个部门</p></div></div><div class="timeline-item"><span class="timeline-date">昨天 18:00</span><i class="timeline-dot"></i><div class="timeline-copy"><strong>定时检查</strong><p>组织架构无变化</p></div></div></div><button class="btn btn-sm" data-org-sync>立即同步</button></div></section><section class="section"><div class="section-head"><div><h2>通知策略</h2><p class="muted">业务动作和定时预警统一记录。</p></div><button class="btn btn-quiet btn-sm" data-toast="通知策略已保存">保存</button></div><div class="section-body"><div class="setting-line"><span>工时审批通知</span>${tag('已启用','success')}</div><div class="setting-line"><span>合同收付款审批结果</span>${tag('已启用','success')}</div><div class="setting-line"><span>合同到期与逾期</span>${tag('已启用','success')}</div><div class="setting-line"><span>预算 / 人天预警</span>${tag('已启用','success')}</div></div></section></div>
    <section class="section"><div class="section-head"><div><h2>最近通知记录</h2><p class="muted">发送失败会进入重试队列，审批状态不受影响。</p></div><button class="btn btn-sm" data-toast="通知记录已刷新">刷新</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>时间</th><th>通知类型</th><th>接收人</th><th>业务对象</th><th>状态</th><th class="right">操作</th></tr></thead><tbody><tr><td>09:18</td><td>工时待审批</td><td>樊公海</td><td>杨阳 · 8 月 27 日工时</td><td>${tag('已发送','success')}</td><td class="right"><button class="btn btn-quiet btn-sm" data-toast="卡片详情已打开">查看</button></td></tr><tr><td>08:44</td><td>合同付款审批通过</td><td>杨阳</td><td>FK-2026-0072</td><td>${tag('已发送','success')}</td><td class="right"><button class="btn btn-quiet btn-sm" data-toast="卡片详情已打开">查看</button></td></tr><tr><td>08:20</td><td>成本预算接近</td><td>李明</td><td>自动化钢筋加工产线</td><td>${tag('待重试','warning')}</td><td class="right"><button class="btn btn-quiet btn-sm" data-toast="已加入重试队列">重试</button></td></tr></tbody></table></div></section>`
}

function optionForm() {
  openModal({ eyebrow: '基础配置', title: '新增可配置选项', body: `<div class="form-grid"><div class="form-field"><label class="required">配置分类</label><select class="control"><option>项目类型</option><option>项目状态</option><option>执行状态</option><option>工时类型</option><option>收付款方式</option></select></div><div class="form-field"><label class="required">显示名称</label><input class="control" placeholder="例如：研发项目"></div><div class="form-field"><label>编码</label><input class="control" placeholder="系统自动生成"></div><div class="form-field"><label>启用状态</label><select class="control"><option>启用</option><option>停用</option></select></div><div class="form-field span-2"><label>说明</label><textarea class="control" rows="3" placeholder="说明该选项的使用范围"></textarea></div></div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn btn-primary" data-confirm-modal>保存配置</button>' })
}

function renderConfiguration() {
  const options = [['项目类型', '研发项目', '启用', '可用于项目和工时筛选'], ['项目类型', '课题项目', '启用', '可用于项目和工时筛选'], ['项目类型', '实施项目', '启用', '支持收入合同和支出合同'], ['项目类型', '观摩项目', '启用', '可用于项目筛选'], ['项目状态', '进行中', '启用', '固定状态，仅可改显示名称'], ['收付款方式', '银行转账', '启用', '合同收款单和合同付款单']]
  const body = options.map((r, i) => `<tr><td>${r[0]}</td><td><strong>${r[1]}</strong></td><td>${tag(r[2], 'success')}</td><td>${r[3]}</td><td class="right"><button class="btn btn-quiet btn-sm" data-option-form="${i}">编辑</button></td></tr>`).join('')
  page.innerHTML = `${pageHead('系统管理 / 业务选项', '基础配置', '维护业务下拉选项和项目类型能力，固定业务状态不允许随意删除。', '<button class="btn btn-primary" data-option-form>＋ 新增配置</button>')}
    <div class="directory-grid config-cards"><article class="entity-card"><div class="entity-head"><div><h3>项目类型</h3><small class="muted">决定项目可用合同能力</small></div>${tag('4 项','primary')}</div><div class="entity-info"><span>收入合同</span><strong>实施项目开启</strong><span>支出合同</span><strong>实施 / 研发 / 课题开启</strong></div><button class="btn btn-quiet btn-sm" data-toast="已定位项目类型配置">管理选项 →</button></article><article class="entity-card"><div class="entity-head"><div><h3>提醒规则</h3><small class="muted">合同阶段和项目预警</small></div>${tag('已启用','success')}</div><div class="entity-info"><span>阶段提前提醒</span><strong>7 天</strong><span>后台扫描间隔</span><strong>10 分钟</strong></div><button class="btn btn-quiet btn-sm" data-toast="提醒规则编辑已打开">编辑规则 →</button></article><article class="entity-card"><div class="entity-head"><div><h3>公司银行账户</h3><small class="muted">合同收付款单默认账户</small></div>${tag('2 个账户','primary')}</div><div class="entity-info"><span>默认收款</span><strong>中国银行 · 尾号 6682</strong><span>默认付款</span><strong>招商银行 · 尾号 4301</strong></div><button class="btn btn-quiet btn-sm" data-toast="银行账户配置已打开">管理账户 →</button></article></div>
    ${filterBar(`<div class="field"><label>配置分类</label><select class="control"><option>全部分类</option><option>项目类型</option><option>项目状态</option><option>收付款方式</option></select></div><div class="field"><label>状态</label><select class="control"><option>全部状态</option><option>启用</option><option>停用</option></select></div><div class="field grow"><label>配置名称</label><input class="control" placeholder="搜索选项名称或编码"></div>`)}
    <section class="section"><div class="section-head"><div><h2>配置项列表</h2><p class="muted">固定状态会保留业务编码，已被历史数据引用的选项不能物理删除。</p></div><span class="tag primary">6 项</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>分类</th><th>显示名称</th><th style="width:13%">状态</th><th>用途说明</th><th class="right" style="width:76px">操作</th></tr></thead><tbody>${body}</tbody></table></div>${pagination(6)}</section>`
}

function approvalRail(nodes, currentIndex = 0) {
  return `<div class="approval-rail" role="list" aria-label="审批路径">${nodes.map((node, index) => {
    const state = currentIndex < 0 ? 'defined' : index < currentIndex ? 'done' : index === currentIndex ? 'current' : 'waiting'
    const stateText = state === 'done' ? '已通过' : state === 'current' ? '当前处理' : state === 'defined' ? '已配置' : '等待中'
    return `<div class="approval-node ${state}" role="listitem"><div class="approval-node-index">${state === 'done' ? '✓' : index + 1}</div><div class="approval-node-copy"><strong>${node.name}</strong><span>${node.people}</span><small>${node.mode || '单人审批'} · ${stateText}</small></div></div>`
  }).join('')}</div>`
}

function renderProjectExpenses() {
  const rows = projectExpenses.map(item => `<tr class="click-row" data-route="expense-detail" data-id="${item.id}">
    <td style="width:18%"><span class="cell-main">${item.no}</span><span class="cell-sub">${item.type}</span></td>
    <td style="width:24%"><span class="cell-main">${item.project}</span><span class="cell-sub">${item.projectCode}</span></td>
    <td style="width:12%"><span class="cell-main">${item.applicant}</span><span class="cell-sub">${item.dept.split(' / ').pop()}</span></td>
    <td style="width:11%">${item.occurred}</td>
    <td style="width:11%" class="number right"><strong>${money(item.cost)}</strong></td>
    <td style="width:10%">${tag(item.payment, item.payment === '已支付' ? 'success' : item.payment === '待支付' ? 'warning' : 'outline')}</td>
    <td style="width:14%">${tag(item.status, item.tone)}<span class="cell-sub">${item.node}</span></td>
  </tr>`).join('')
  page.innerHTML = `${pageHead('项目管理 / 成本归集', '项目费用', '差旅、无合同发票和其他费用统一归集，审批与实际支付分开记录。', '<button class="btn" data-route="workflows">查看审批流程</button><button class="btn btn-primary" data-expense-form>＋ 新增费用</button>')}
    <section class="expense-overview" aria-label="费用概览"><div><span>本月已确认成本</span><strong class="number">${money(87420)}</strong><small>12 笔已完成业务审批</small></div><div><span>待我审批</span><strong class="number amount-danger">4</strong><small>最早等待 19 小时</small></div><div><span>待出纳支付</span><strong class="number amount-negative">${money(16660)}</strong><small>3 笔已完成业务审批</small></div><div><span>预算影响项目</span><strong class="number">2</strong><small>1 个接近预算 · 1 个正常</small></div></section>
    <div class="page-tabs expense-page-tabs"><button class="tab active">全部费用 <span class="tab-count">28</span></button><button class="tab">待我审批 <span class="tab-count warning">4</span></button><button class="tab">我提交的</button><button class="tab">已审批</button></div>
    ${filterBar(`<div class="field"><label>费用类型</label><select class="control"><option>全部类型</option><option>差旅费用</option><option>无合同发票</option><option>其他费用</option></select></div><div class="field"><label>审批状态</label><select class="control"><option>全部状态</option><option>待我审批</option><option>审批中</option><option>已审批</option><option>已驳回</option></select></div>${departmentTree()}<div class="field"><label>申请人</label><select class="control"><option>全部人员</option><option>杨阳</option><option>陈露</option><option>樊公海</option></select></div><div class="field"><label>发生日期</label><input type="month" class="control" value="2026-09"></div><div class="field grow"><label>项目 / 单号</label><input class="control" placeholder="输入项目名称或费用单号"></div>`) }
    <section class="section expense-ledger"><div class="section-head"><div><h2>费用台账</h2><p class="muted">金额按费用审批通过口径统计，支付状态单独展示</p></div><div class="inline-actions"><button class="btn btn-sm" data-toast="费用明细已按当前筛选导出">导出</button><span class="tag primary">共 28 笔</span></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>费用单</th><th>项目</th><th>申请人</th><th>发生日期</th><th class="right">项目成本</th><th>支付状态</th><th>审批状态</th></tr></thead><tbody>${rows}</tbody></table></div>${pagination(28)}</section>`
}

function renderExpenseDetail(params) {
  const item = projectExpenses.find(x => x.id === Number(params.get('id'))) || projectExpenses[1]
  const isTravel = item.type === '差旅费用'
  const nodes = isTravel
    ? [{ name: '项目审批', people: '樊公海' }, { name: '上级领导', people: '赵明' }, { name: '会计审核', people: '张敏 / 陈欣', mode: '任一人审批' }, { name: '总经理', people: '李国强', mode: '任一人审批' }, { name: '出纳支付', people: '贺茂维 / 刘芳', mode: '任一人确认' }]
    : [{ name: '项目审批', people: '樊公海' }, { name: '经营审批', people: '刘洁 / 王哲', mode: '任一人审批' }, { name: '上级领导', people: '赵明' }, { name: '经营副总', people: '周建国', mode: '任一人审批' }, { name: '会计审核', people: '张敏 / 陈欣', mode: '任一人审批' }, { name: '总经理', people: '李国强', mode: '任一人审批' }, { name: '出纳支付', people: '贺茂维 / 刘芳', mode: '任一人确认' }]
  const activeIndex = isTravel ? 2 : 1
  const currentIndex = ['已完成', '已审批'].includes(item.status) ? nodes.length : item.status === '已驳回' ? 0 : activeIndex
  const currentPeople = currentIndex < nodes.length ? nodes[currentIndex].people : '流程已完成'
  const paymentDone = item.payment === '已支付'
  const detailAction = ['待我审批', '审批中'].includes(item.status) ? '<button class="btn btn-primary" data-expense-approve>处理当前审批</button>' : '<button class="btn" data-route="projects">查看所属项目</button>'
  page.innerHTML = `${pageHead(`${item.type} · ${item.no}`, '费用详情', '业务审批、成本确认和实际支付使用同一条可追溯记录。', '<button class="btn" data-route="project-expenses">← 返回费用列表</button>' + detailAction)}
    <section class="expense-detail-hero"><div class="expense-state-mark ${item.tone}"><span>${item.status === '待我审批' ? '待' : '审'}</span></div><div><div class="detail-title"><h1>${item.purpose}</h1>${tag(item.type, 'outline')}${tag(item.status, item.tone)}</div><div class="detail-meta"><span>费用单号 <strong>${item.no}</strong></span><span>项目 <strong>${item.project}</strong></span><span>申请人 <strong>${item.applicant}</strong></span><span>发生日期 <strong>${item.occurred}</strong></span></div></div><div class="expense-hero-money"><span>计入项目成本</span><strong class="number">${money(item.cost)}</strong><small>申请金额 ${money(item.amount)}</small></div></section>
    <section class="section approval-track-section"><div class="section-head"><div><h2>当前审批路径</h2><p class="muted">流程版本 V3 · 提交后人员和顺序已固定</p></div>${currentIndex < nodes.length ? `<span class="tag warning">${nodes[currentIndex].name}处理中</span>` : tag('流程已完成', 'success')}</div>${approvalRail(nodes, currentIndex)}</section>
    <div class="expense-detail-grid"><section class="section"><div class="section-head"><div><h2>费用信息</h2><p class="muted">费用发生事实与项目归属</p></div><button class="btn btn-quiet btn-sm" data-toast="审批中单据为只读状态">只读</button></div><div class="expense-info-grid"><div><span>费用类型</span><strong>${item.type}</strong></div><div><span>费用发生日期</span><strong>${item.occurred}</strong></div><div><span>申请部门</span><strong>${item.dept}</strong></div><div><span>是否需要支付</span><strong>是</strong></div><div class="span-2"><span>所属项目</span><strong>${item.project}</strong><small>${item.projectCode}</small></div><div class="span-2"><span>费用说明</span><strong>${item.purpose}</strong><small>${isTravel ? '成都 → 绵阳 · 2026-09-02 至 2026-09-03' : '无支出合同，已上传增值税普通发票和现场服务确认单'}</small></div></div><div class="expense-breakdown"><div><span>${isTravel ? '交通费' : '发票含税金额'}</span><strong>${money(isTravel ? 860 : item.amount)}</strong></div><div><span>${isTravel ? '住宿费' : '计入项目成本'}</span><strong>${money(isTravel ? 1800 : item.cost)}</strong></div><div><span>${isTravel ? '餐费 / 补贴' : '待支付金额'}</span><strong>${money(isTravel ? 800 : item.amount)}</strong></div><div><span>${isTravel ? '其他费用' : '预算影响'}</span><strong>${isTravel ? money(400) : '使用率 +1.8%'}</strong></div></div></section>
      <section class="section payment-fact"><div class="section-head"><div><h2>支付信息</h2><p class="muted">业务审批完成后由出纳确认</p></div>${tag(paymentDone ? '已支付' : '等待业务审批', paymentDone ? 'success' : 'warning')}</div><div class="payment-account"><span>收款方</span><strong>${isTravel ? item.applicant : '成都云联技术服务有限公司'}</strong><small>招商银行成都高新支行 · 账号尾号 7821</small></div><div class="payment-metrics"><div><span>应付金额</span><strong class="number">${money(item.amount)}</strong></div><div><span>已付金额</span><strong class="number">${money(paymentDone ? item.amount : 0)}</strong></div><div><span>${paymentDone ? '实际支付日' : '付款到期日'}</span><strong>${paymentDone ? '2026-09-04' : '2026-09-12'}</strong></div></div><div class="notice ${paymentDone ? '' : 'warning'}"><span>${paymentDone ? '✓' : '!'}</span><div><strong>${paymentDone ? '资金流水已确认' : '当前不能支付'}</strong><p>${paymentDone ? '出纳贺茂维已完成支付，支付凭证和账户快照已锁定。' : '完成会计、总经理等业务审批后，出纳节点才会开放支付确认。'}</p></div></div></section></div>
    <section class="section"><div class="section-head"><div><h2>附件与凭证</h2><p class="muted">新建费用时已上传，审批过程不可替换</p></div><span class="muted">2 个文件</span></div><div class="attachment-list"><div class="attachment-row"><span class="attachment-type pdf">P</span><div><strong>${isTravel ? '差旅费用票据汇总.pdf' : '增值税普通发票.pdf'}</strong><small>${item.applicant} 上传 · 今天 09:18 · 2.4 MB</small></div><span class="tag success">可预览</span><div class="inline-actions"><button class="btn btn-quiet btn-sm" data-toast="正在打开附件预览">预览</button><button class="btn btn-quiet btn-sm" data-toast="附件下载已开始">下载</button></div></div><div class="attachment-row"><span class="attachment-type word">W</span><div><strong>${isTravel ? '现场联调记录.docx' : '现场服务确认单.docx'}</strong><small>${item.applicant} 上传 · 今天 09:19 · 860 KB</small></div><span class="tag success">可预览</span><div class="inline-actions"><button class="btn btn-quiet btn-sm" data-toast="正在打开附件预览">预览</button><button class="btn btn-quiet btn-sm" data-toast="附件下载已开始">下载</button></div></div></div></section>
    <div class="expense-detail-grid"><section class="section"><div class="section-head"><div><h2>审批记录</h2><p class="muted">每一步均保留人员与意见快照</p></div></div><div class="timeline section-body"><div class="timeline-item done"><span class="timeline-date">今天 09:20</span><span class="timeline-dot"></span><div class="timeline-copy"><strong>${item.applicant} · 提交申请</strong><p>流程版本 V3，审批路径校验通过</p></div></div><div class="timeline-item done"><span class="timeline-date">今天 10:06</span><span class="timeline-dot"></span><div class="timeline-copy"><strong>樊公海 · 项目审批通过</strong><p>费用与项目现场工作相关，同意列支</p></div></div><div class="timeline-item ${currentIndex < nodes.length ? 'warn' : 'done'}"><span class="timeline-date">今天 10:07</span><span class="timeline-dot"></span><div class="timeline-copy"><strong>${currentPeople} · ${currentIndex < nodes.length ? '待处理' : '审批完成'}</strong><p>${currentIndex < nodes.length ? '飞书应用消息已送达，等待当前节点处理' : '所有业务审批和支付确认均已留痕'}</p></div></div></div></section><section class="section"><div class="section-head"><div><h2>成本与资金流水</h2><p class="muted">业务审批通过后自动生成，不允许手工修改</p></div></div>${currentIndex < nodes.length ? '<div class="empty-state compact"><span class="ledger-empty-icon">账</span><strong>尚未生成项目流水</strong><p>全部业务审批通过后确认费用成本；出纳支付后另记资金流水。</p></div>' : `<div class="ledger-facts"><div><span>项目费用成本</span><strong>${money(item.cost)}</strong><small>审批完成自动确认</small></div><div><span>费用支付</span><strong>${money(paymentDone ? item.amount : 0)}</strong><small>${paymentDone ? '出纳已确认' : '无需支付'}</small></div></div>`}</section></div>`
}

function renderApprovalPositions() {
  const cards = approvalPositions.map((position, index) => `<article class="position-card"><div class="position-card-head"><span class="position-symbol">${position.name.slice(0, 1)}</span><div><h3>${position.name}</h3><small>${position.code}</small></div>${tag('已启用', 'success')}</div><div class="position-members">${position.people.map(name => `<span><i>${name.slice(0,1)}</i>${name}</span>`).join('')}</div><dl><dt>所属范围</dt><dd>${position.dept}</dd><dt>应用流程</dt><dd>${position.scenes}</dd><dt>最近修改</dt><dd>${position.updated}</dd></dl><button class="btn btn-sm" data-position-form="${index}">配置人员</button></article>`).join('')
  page.innerHTML = `${pageHead('系统管理 / 审批配置', '审批岗位', '岗位决定审批任务分给谁；菜单和数据权限仍由管理员角色单独控制。', '<button class="btn" data-route="workflows">审批流程</button><button class="btn btn-primary" data-position-form>＋ 配置岗位</button>')}
    <div class="notice position-notice"><span>i</span><div><strong>岗位与权限分开管理</strong><p>加入“会计”或“出纳”岗位不会自动获得菜单权限。实际审批人由运行中的任务授权，并记录真实处理人姓名。</p></div></div>
    <section class="position-grid">${cards}</section>
    <section class="section"><div class="section-head"><div><h2>岗位健康检查</h2><p class="muted">被已发布流程引用的岗位必须至少配置一名有效人员</p></div><span class="tag success">5 个岗位正常</span></div><div class="health-list"><div><span class="health-dot success"></span><strong>审批人员均为飞书有效用户</strong><small>8 人 · 最近组织同步：今天 08:30</small></div><div><span class="health-dot success"></span><strong>已发布流程不存在空岗位</strong><small>2 个流程 · 12 个岗位节点</small></div><div><span class="health-dot warning"></span><strong>1 名出纳同时属于会计岗位</strong><small>系统允许重复，但出纳支付节点不会自动通过</small></div></div></section>`
}

function workflowCard(code, title, subtitle, nodes, version) {
  return `<article class="workflow-card"><header><div><div class="eyebrow">${code}</div><h2><button class="link-button" data-route="workflow-detail" data-id="${code}">${title}</button></h2><p>${subtitle}</p></div><div class="workflow-version"><span>当前版本</span><strong>${version}</strong>${tag('已发布', 'success')}</div></header>${approvalRail(nodes, -1)}<footer><span>最近发布：2026-09-06 10:16 · 李晓天</span><div class="inline-actions"><button class="btn btn-sm" data-workflow-preview="${code}">路径演练</button><button class="btn btn-primary btn-sm" data-route="workflow-detail" data-id="${code}">查看流程</button></div></footer></article>`
}

function renderWorkflows() {
  const travelNodes = [{ name: '项目审批', people: '项目动态', mode: '动态单人' }, { name: '上级领导', people: '飞书动态', mode: '动态单人' }, { name: '会计', people: '岗位成员', mode: '或签' }, { name: '总经理', people: '岗位成员', mode: '或签' }, { name: '出纳支付', people: '岗位成员', mode: '或签' }]
  const paymentNodes = [{ name: '项目审批', people: '项目动态', mode: '动态单人' }, { name: '经营审批', people: '岗位成员', mode: '或签' }, { name: '上级领导', people: '飞书动态', mode: '动态单人' }, { name: '经营副总', people: '岗位成员', mode: '或签' }, { name: '会计', people: '岗位成员', mode: '或签' }, { name: '总经理', people: '岗位成员', mode: '或签' }, { name: '出纳支付', people: '岗位成员', mode: '或签' }]
  page.innerHTML = `${pageHead('系统管理 / 审批配置', '审批流程', '发布后的流程版本不可修改，新配置只影响之后提交的单据。', '<button class="btn" data-route="approval-positions">审批岗位</button><button class="btn btn-primary" data-workflow-version>＋ 新建流程版本</button>')}
    <section class="workflow-summary"><div><span>已发布流程</span><strong>2</strong></div><div><span>运行中实例</span><strong>17</strong></div><div><span>今日完成审批</span><strong>26</strong></div><div><span>人员解析异常</span><strong class="amount-positive">0</strong></div><p>配置检查通过 · 所有必需岗位均已设置人员</p></section>
    <div class="workflow-list">${workflowCard('TRAVEL_EXPENSE', '差旅费用审批', '用于员工项目差旅费用，先确认项目和人员行为，再进入财务与支付。', travelNodes, 'V2')}${workflowCard('PROJECT_PAYMENT', '付款与项目费用审批', '用于合同付款、无合同发票和其他费用，增加经营条线复核。', paymentNodes, 'V3')}</div>`
}

function renderWorkflowDetail(params) {
  const payment = params.get('id') !== 'TRAVEL_EXPENSE'
  const title = payment ? '付款与项目费用审批' : '差旅费用审批'
  const code = payment ? 'PROJECT_PAYMENT' : 'TRAVEL_EXPENSE'
  const nodes = payment
    ? [{ name: '项目审批', people: '项目审批人', mode: '动态单人' }, { name: '经营审批', people: '经营审批岗位', mode: '或签' }, { name: '上级领导', people: '申请人直属上级', mode: '动态单人' }, { name: '经营副总', people: '经营副总岗位', mode: '或签' }, { name: '会计审核', people: '会计岗位', mode: '或签' }, { name: '总经理', people: '总经理岗位', mode: '或签' }, { name: '出纳支付', people: '出纳岗位', mode: '或签·必须确认支付' }]
    : [{ name: '项目审批', people: '项目审批人', mode: '动态单人' }, { name: '上级领导', people: '申请人直属上级', mode: '动态单人' }, { name: '会计审核', people: '会计岗位', mode: '或签' }, { name: '总经理', people: '总经理岗位', mode: '或签' }, { name: '出纳支付', people: '出纳岗位', mode: '或签·必须确认支付' }]
  const nodeRows = nodes.map((node, index) => `<div class="workflow-node-row"><span class="node-order">${index + 1}</span><div><strong>${node.name}</strong><small>${index === 0 ? '从单据项目读取' : node.people}</small></div><span>${node.mode}</span><span>${node.name === '出纳支付' ? tag('不可自动通过', 'warning') : tag('提交时固化', 'outline')}</span><button class="btn btn-quiet btn-sm" data-toast="已打开节点配置说明">查看规则</button></div>`).join('')
  page.innerHTML = `${pageHead(`${code} · 已发布`, title, '查看当前发布版本、节点解析规则和历史版本。', '<button class="btn" data-route="workflows">← 返回流程列表</button><button class="btn" data-workflow-preview="' + code + '">路径演练</button><button class="btn btn-primary" data-workflow-version>复制为新版本</button>')}
    <section class="workflow-detail-hero"><div><span>当前发布版本</span><strong>V${payment ? '3' : '2'}</strong><small>发布于 2026-09-06 10:16 · 李晓天</small></div><p>运行中的单据继续使用提交时的人员与节点快照；新版本发布后只影响新提交单据。</p>${tag('配置检查通过', 'success')}</section>
    <section class="section approval-track-section"><div class="section-head"><div><h2>流程路径</h2><p class="muted">节点顺序具有业务含义，发布版本中不可拖动或编辑</p></div><span class="tag primary">${nodes.length} 个节点</span></div>${approvalRail(nodes, -1)}</section>
    <div class="workflow-detail-grid"><section class="section"><div class="section-head"><div><h2>节点规则</h2><p class="muted">审批人来源、审批方式和自动处理规则</p></div></div><div class="workflow-node-table">${nodeRows}</div></section><section class="section version-panel"><div class="section-head"><div><h2>版本记录</h2><p class="muted">发布版本不可修改</p></div></div><div class="version-row current"><span>V${payment ? '3' : '2'}</span><div><strong>当前版本</strong><small>李晓天 · 今天 10:16</small></div>${tag('已发布', 'success')}</div><div class="version-row"><span>V${payment ? '2' : '1'}</span><div><strong>上一版本</strong><small>李晓天 · 2026-08-28</small></div>${tag('已停用')}</div><div class="version-diff"><strong>当前版本变化</strong><p>${payment ? '增加经营副总节点；出纳节点改为必须登记实际支付信息。' : '会计岗位调整为多人或签；增加审批超时提醒。'}</p></div></section></div>`
}

function expenseTypeFields(type) {
  if (type === 'TRAVEL') return `<div class="form-field"><label class="required">出差开始日期</label><input type="date" class="control" value="2026-09-08"></div><div class="form-field"><label class="required">出差结束日期</label><input type="date" class="control" value="2026-09-09"></div><div class="form-field"><label class="required">出发地</label><input class="control" value="成都"></div><div class="form-field"><label class="required">目的地</label><input class="control" value="绵阳"></div><div class="form-field span-2"><label class="required">出差事由</label><input class="control" value="现场设备联调及阶段验收"></div><div class="form-field"><label>交通费</label><input class="control" value="860.00"></div><div class="form-field"><label>住宿费</label><input class="control" value="1,800.00"></div><div class="form-field"><label>餐费 / 补贴</label><input class="control" value="800.00"></div><div class="form-field"><label>其他差旅费</label><input class="control" value="400.00"></div>`
  if (type === 'INVOICE') return `<div class="form-field"><label>供应商</label><select class="control"><option>成都云联技术服务有限公司</option><option>不从供应商库选择</option></select></div><div class="form-field"><label class="required">发票类型</label><select class="control"><option>增值税普通发票</option><option>增值税专用发票</option></select></div><div class="form-field"><label>发票代码</label><input class="control" value="051002600111"></div><div class="form-field"><label class="required">发票号码</label><input class="control" value="24856317"></div><div class="form-field"><label class="required">开票日期</label><input type="date" class="control" value="2026-09-04"></div><div class="form-field"><label class="required">发票含税金额</label><input class="control" value="12,800.00"></div><div class="form-field span-2"><label class="required">无合同原因</label><input class="control" value="现场临时网络专线服务，未签订支出合同"></div>`
  return `<div class="form-field"><label class="required">费用类别</label><select class="control"><option>测试材料费</option><option>业务招待费</option><option>办公费</option><option>服务费</option></select></div><div class="form-field"><label>供应商</label><select class="control"><option>四川精工智能装备有限公司</option><option>不从供应商库选择</option></select></div><div class="form-field span-2"><label class="required">费用事项</label><input class="control" value="样机测试耗材与临时加工"></div>`
}

function expenseForm() {
  openModal({ eyebrow: '项目成本 / 新增费用', title: '新增项目费用', wide: true, body: `<div class="expense-form-progress"><span class="active">1 填写费用</span><span>2 核对审批路径</span><span>3 提交完成</span></div><div class="form-section"><h3>基本信息</h3><div class="form-grid cols-3"><div class="form-field"><label class="required">费用类型</label><select class="control" data-expense-type><option value="TRAVEL">差旅费用</option><option value="INVOICE">无合同发票</option><option value="OTHER">其他费用</option></select></div><div class="form-field span-2"><label class="required">所属项目</label><select class="control"><option>${projects[0].name}</option><option>${projects[1].name}</option><option>${projects[2].name}</option></select></div><div class="form-field"><label class="required">费用发生日期</label><input type="date" class="control" value="2026-09-06"></div><div class="form-field"><label class="required">是否需要支付</label><select class="control"><option>是，审批后由出纳支付</option><option>否，已由公司支付</option></select></div><div class="form-field"><label>申请人</label><div class="control readonly">杨阳 · 信息化中心</div></div></div></div><div class="form-section"><h3 data-expense-type-title>差旅明细</h3><div class="form-grid cols-3" data-expense-type-fields>${expenseTypeFields('TRAVEL')}</div></div><div class="form-section"><h3>金额与收款信息</h3><div class="form-grid cols-3"><div class="form-field"><label class="required">申请金额</label><input class="control" value="3,860.00"></div><div class="form-field"><label class="required">计入项目成本</label><input class="control" value="3,860.00"></div><div class="form-field"><label class="required">付款到期日</label><input type="date" class="control" value="2026-09-15"></div><div class="form-field"><label class="required">收款方名称</label><input class="control" value="杨阳"></div><div class="form-field"><label class="required">收款银行</label><input class="control" value="招商银行成都高新支行"></div><div class="form-field"><label class="required">银行账号</label><input class="control" value="6225 8800 0000 7821"></div></div></div><div class="form-section"><h3>说明与附件</h3><div class="form-grid"><div class="form-field span-2"><label class="required">费用说明</label><textarea class="control">智慧工地机器人协同平台现场联调和阶段验收支持。</textarea></div><div class="form-field span-2"><label class="required">费用凭证</label><div class="upload-box expense-upload"><span>＋</span><strong>选择或拖放附件</strong><small>PDF、图片、Word、Excel、PPT，单个文件不超过 50 MB</small></div><div class="queued-file"><span class="attachment-type pdf">P</span><div><strong>差旅票据汇总.pdf</strong><small>2.4 MB · 等待单据保存后上传</small></div><button class="icon-btn" title="移除附件">×</button></div></div></div></div><div class="approval-preview"><div class="approval-preview-head"><div><strong>审批路径预览</strong><small>所有审批人已成功解析 · 流程版本 V2</small></div>${tag('可以提交', 'success')}</div>${approvalRail([{ name: '项目审批', people: '樊公海' }, { name: '上级领导', people: '赵明' }, { name: '会计', people: '张敏 / 陈欣', mode: '或签' }, { name: '总经理', people: '李国强', mode: '或签' }, { name: '出纳支付', people: '贺茂维 / 刘芳', mode: '或签' }], -1)}</div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn" data-toast="费用草稿已保存">保存草稿</button><button class="btn btn-primary" data-expense-submit>提交审批</button>' })
}

function expenseApproval() {
  openModal({ eyebrow: '费用审批 / 经营审批', title: '确认审批意见', body: `<div class="approval-confirm-summary"><div><span>项目</span><strong>${projects[0].name}</strong></div><div><span>费用类型</span><strong>无合同发票</strong></div><div><span>计入项目成本</span><strong class="number">${money(12800)}</strong></div><div><span>待支付金额</span><strong class="number">${money(12800)}</strong></div></div><div class="notice warning" style="margin:16px 0"><span>!</span><div><strong>本节点负责经营合理性复核</strong><p>通过后单据将进入上级领导审批；此时尚不确认成本，也不会进入支付。</p></div></div><div class="form-field"><label>审批意见</label><textarea class="control" placeholder="可填写审批说明">费用与现场服务内容一致，同意进入下一节点。</textarea></div>`, foot: '<button class="btn" data-expense-reject>驳回</button><button class="btn btn-primary" data-confirm-modal>确认通过</button>' })
}

function positionForm(index = 0) {
  const position = approvalPositions[index] || approvalPositions[0]
  openModal({ eyebrow: '审批配置 / 岗位人员', title: `配置${position.name}`, body: `<div class="notice"><span>i</span><div><strong>岗位编码 ${position.code}</strong><p>编码由系统使用，不能修改；人员必须来自已同步的飞书组织架构。</p></div></div><div class="form-field" style="margin-top:18px"><label class="required">岗位人员</label><div class="member-picker">${position.people.map(name => `<span><i>${name.slice(0,1)}</i>${name}<button title="移除">×</button></span>`).join('')}<button data-toast="已打开飞书人员选择器">＋ 添加人员</button></div></div><div class="form-field" style="margin-top:16px"><label>岗位说明</label><textarea class="control">${position.scenes}</textarea></div><div class="notice warning" style="margin-top:16px"><span>!</span><div><strong>保存后只影响新提交单据</strong><p>运行中的审批任务继续使用提交时固定的审批人快照。</p></div></div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn btn-primary" data-confirm-modal>保存岗位人员</button>' })
}

function workflowPreview(code = 'PROJECT_PAYMENT') {
  const payment = code !== 'TRAVEL_EXPENSE'
  const nodes = payment ? [{ name: '项目审批', people: '樊公海' }, { name: '经营审批', people: '刘洁 / 王哲', mode: '或签' }, { name: '上级领导', people: '赵明' }, { name: '经营副总', people: '周建国', mode: '或签' }, { name: '会计', people: '张敏 / 陈欣', mode: '或签' }, { name: '总经理', people: '李国强', mode: '或签' }, { name: '出纳支付', people: '贺茂维 / 刘芳', mode: '或签' }] : [{ name: '项目审批', people: '樊公海' }, { name: '上级领导', people: '赵明' }, { name: '会计', people: '张敏 / 陈欣', mode: '或签' }, { name: '总经理', people: '李国强', mode: '或签' }, { name: '出纳支付', people: '贺茂维 / 刘芳', mode: '或签' }]
  openModal({ eyebrow: '发布前检查', title: '审批路径演练', wide: true, body: `<div class="form-grid"><div class="form-field"><label>模拟申请人</label><select class="control"><option>杨阳 · 信息化中心</option></select></div><div class="form-field"><label>模拟项目</label><select class="control"><option>${projects[0].name}</option></select></div></div><div class="preview-result"><div><span class="health-dot success"></span><strong>人员解析成功</strong><small>未发现空岗位、自审死循环或无效飞书用户</small></div></div>${approvalRail(nodes, -1)}<div class="rule-checks"><span>✓ 项目审批人已配置</span><span>✓ 直属上级已同步</span><span>✓ 5 个审批岗位有效</span><span>✓ 出纳节点不会自动通过</span></div>`, foot: '<button class="btn" data-close-modal>关闭</button><button class="btn btn-primary" data-toast="演练结果已刷新">重新演练</button>' })
}

function workflowVersionForm() {
  openModal({ eyebrow: '审批流程 / 草稿版本', title: '新建流程版本', wide: true, body: `<div class="notice warning"><span>!</span><div><strong>新版本不会影响运行中的单据</strong><p>发布后仅用于新提交单据，上一版本保留用于历史追溯。</p></div></div><div class="form-grid" style="margin-top:18px"><div class="form-field"><label class="required">流程</label><select class="control"><option>付款与项目费用审批</option><option>差旅费用审批</option></select></div><div class="form-field"><label>新版本</label><div class="control readonly">V4 · 草稿</div></div></div><div class="workflow-draft-nodes">${['项目审批人','经营审批','上级领导','经营副总','会计','总经理','出纳支付'].map((name,index)=>`<div><span>${index+1}</span><strong>${name}</strong><small>${index === 0 ? '项目动态人员' : index === 2 ? '飞书直属上级' : '审批岗位 · 或签'}</small><button class="icon-btn" title="调整节点">⋮</button></div>`).join('')}</div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn" data-toast="流程草稿已保存">保存草稿</button><button class="btn btn-primary" data-toast="发布前请先执行路径演练">保存并检查</button>' })
}

function renderExistingModule(route) {
  const renderers = {
    'my-worklogs': renderMyWorklogs,
    approvals: renderApprovals,
    'worklog-board': renderWorklogBoard,
    'worklog-ledger': renderWorklogLedger,
    'personnel-cost': renderPersonnelCost,
    integration: renderIntegration,
    configuration: renderConfiguration
  }
  ;(renderers[route] || renderWorkbench)()
}

function projectForm() {
  openModal({ eyebrow: '项目主数据', title: '新增 / 编辑项目', wide: true, body: `<div class="form-grid cols-3"><div class="form-field"><label class="required">项目编号</label><input class="control" value="SS-2026-008"></div><div class="form-field span-2"><label class="required">项目名称</label><input class="control" value="智慧工地机器人协同平台"></div><div class="form-field"><label class="required">项目状态</label><select class="control"><option>进行中</option><option>验收中</option><option>已完成</option></select></div><div class="form-field"><label class="required">项目类型</label><select class="control"><option>实施项目</option><option>研发项目</option><option>课题项目</option><option>观摩项目</option></select></div><div class="form-field"><label class="required">负责人</label><select class="control"><option>杨阳 · 信息化中心</option><option>樊公海 · 产品研发部</option></select></div><div class="form-field"><label class="required">所属部门</label><select class="control"><option>产品研发部 / 信息化中心</option><option>产品研发部 / 机器人中心</option></select></div><div class="form-field"><label>客户</label><select class="control"><option>四川华西集团</option><option>中铁八局</option></select></div><div class="form-field"><label>工时填报</label><select class="control"><option>允许填报</option><option>暂停填报</option></select></div><div class="form-field"><label>开始日期</label><input type="date" class="control" value="2026-03-01"></div><div class="form-field"><label>计划结束</label><input type="date" class="control" value="2026-12-31"></div><div class="form-field span-3"><label>项目说明</label><textarea class="control">面向大型施工现场的机器人调度、状态监测与协同作业平台。</textarea></div></div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn" data-toast="项目草稿已保存">保存草稿</button><button class="btn btn-primary" data-confirm-modal>保存项目</button>' })
}

function contractForm() {
  openModal({ eyebrow: '合同主信息', title: '新增项目合同', wide: true, body: `<div class="form-grid cols-3"><div class="form-field"><label class="required">合同类型</label><select class="control"><option>收入合同</option><option>支出合同</option></select></div><div class="form-field"><label class="required">所属项目</label><select class="control"><option>${projects[0].name}</option><option>${projects[1].name}</option><option>${projects[3].name}</option></select></div><div class="form-field"><label class="required">客户 / 供应商</label><select class="control"><option>四川华西集团有限公司</option><option>成都锐视科技有限公司</option></select></div><div class="form-field"><label class="required">合同编号</label><input class="control" value="HT-SR-2026-014"></div><div class="form-field span-2"><label class="required">合同名称</label><input class="control" value="智慧工地机器人协同平台采购合同"></div><div class="form-field"><label class="required">合同金额</label><input class="control" value="1,200,000"></div><div class="form-field"><label>签订日期</label><input type="date" class="control" value="2026-03-12"></div><div class="form-field"><label>合同状态</label><select class="control"><option>草稿</option><option>生效</option></select></div><div class="form-field span-3"><label>合同说明</label><textarea class="control" rows="3" placeholder="补充合同范围、结算约定和责任边界"></textarea></div></div><div class="stage-entry-panel"><div><strong>结算阶段</strong><p>合同保存后，在阶段列表中查看和维护收款 / 付款计划。</p></div><div class="stage-entry-actions"><span class="tag primary">暂未配置</span><button class="btn btn-sm" data-stage-list>查看阶段列表</button><button class="btn btn-primary btn-sm" data-stage-form>＋ 新增阶段</button></div></div><div class="notice" style="margin-top:16px"><span>i</span><div><strong>阶段独立维护</strong><p>先保存合同主信息，再按合同类型添加多个阶段；不会在合同弹窗里混入阶段编辑内容。</p></div></div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn" data-toast="合同草稿已保存">保存草稿</button><button class="btn btn-primary" data-contract-save>保存合同并进入阶段列表</button>' })
}

function stageList() {
  const rows = [
    ['合同首付款', '2026-07-15', 420000, '已完成', 'success'],
    ['阶段验收款', '2026-09-05', 360000, '未到期', 'warning']
  ].map((stage, index) => `<tr><td><span class="cell-main">${stage[0]}</span><span class="cell-sub">第 ${index + 1} 阶段 · 提前 7 天提醒</span></td><td class="number right">${money(stage[2])}</td><td>${stage[1]}</td><td>${tag(stage[3], stage[4])}</td><td class="right"><button class="btn btn-quiet btn-sm" data-stage-form>编辑</button></td></tr>`).join('')
  openModal({ eyebrow: '合同结算计划', title: '阶段列表', wide: true, body: `<div class="section-head compact-head"><div><h3>智慧工地机器人协同平台采购合同</h3><p class="muted">HT-SR-2026-014 · 收入合同 · 共 2 个阶段</p></div><button class="btn btn-primary btn-sm" data-stage-form>＋ 新增阶段</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>阶段名称</th><th class="right">计划金额</th><th>计划日期</th><th>状态</th><th class="right">操作</th></tr></thead><tbody>${rows}</tbody></table></div><div class="notice warning" style="margin-top:16px"><span>!</span><div><strong>阶段金额合计低于合同金额</strong><p>当前阶段合计 ${money(780000)}，合同金额 ${money(1200000)}，仍有 ${money(420000)} 待拆分。</p></div></div>`, foot: '<button class="btn" data-close-modal>关闭</button><button class="btn btn-primary" data-stage-form>＋ 新增阶段</button>' })
}

function stageForm() {
  openModal({ eyebrow: '合同结算计划', title: '新增结算阶段', body: `<div class="form-grid"><div class="form-field"><label class="required">阶段名称</label><input class="control" placeholder="例如：阶段验收款"></div><div class="form-field"><label class="required">计划金额</label><input class="control" type="number" placeholder="请输入金额"></div><div class="form-field"><label class="required">计划日期</label><input type="date" class="control" value="2026-09-05"></div><div class="form-field"><label>提前提醒</label><select class="control"><option>提前 7 天</option><option>提前 3 天</option><option>提前 1 天</option><option>不提醒</option></select></div><div class="form-field span-2"><label>阶段说明</label><textarea class="control" rows="3" placeholder="补充阶段验收条件或付款依据"></textarea></div></div><div class="notice" style="margin-top:16px"><span>i</span><div><strong>保存后将进入合同阶段列表</strong><p>到期未完成的收入阶段或支出阶段，会按提醒规则通知项目负责人。</p></div></div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn btn-primary" data-confirm-modal>保存阶段</button>' })
}

function cashForm(kind) {
  const receipt = kind === 'receipt'
  const noun = receipt ? '收款' : '付款'
  openModal({ eyebrow: `${noun}单 · 关联合同阶段`, title: `新增${noun}单`, wide: true, body: `<div class="amount-context"><div><span>阶段计划金额</span><strong>${money(receipt ? 360000 : 180000)}</strong></div><div><span>已${receipt ? '收' : '付'}</span><strong>${money(receipt ? 180000 : 85000)}</strong></div><div><span>剩余应${receipt ? '收' : '付'}</span><strong class="amount-negative">${money(receipt ? 180000 : 95000)}</strong></div></div><div class="form-grid cols-3"><div class="form-field"><label class="required">项目</label><select class="control"><option>${projects[0].name}</option></select></div><div class="form-field"><label class="required">${receipt ? '收入' : '支出'}合同</label><select class="control"><option>${receipt ? contracts[0].name : contracts[1].name}</option></select></div><div class="form-field"><label class="required">合同阶段</label><select class="control"><option>${receipt ? '阶段验收款' : '设备到货款'}</option></select></div><div class="form-field"><label>${receipt ? '客户' : '供应商'}</label><input class="control readonly" readonly value="${receipt ? '四川华西集团' : '成都锐视科技有限公司'}"></div><div class="form-field"><label class="required">本次${noun}金额</label><input class="control" value="${receipt ? '180,000' : '95,000'}"></div><div class="form-field"><label class="required">${noun}日期</label><input type="date" class="control" value="2026-08-28"></div><div class="form-field"><label class="required">${receipt ? '付款' : '收款'}户名</label><input class="control" value="${receipt ? '四川华西集团有限公司' : '成都锐视科技有限公司'}"></div><div class="form-field"><label class="required">开户银行</label><input class="control" value="招商银行成都高新支行"></div><div class="form-field"><label class="required">银行账号</label><input class="control" value="**** **** **** 7821"><small class="form-tip">默认脱敏，提交前需再次核对</small></div><div class="form-field"><label>银行流水号</label><input class="control" placeholder="确认到账后填写"></div><div class="form-field"><label>${noun}方式</label><select class="control"><option>银行转账</option><option>承兑汇票</option></select></div><div class="form-field"><label>公司${noun}账户</label><select class="control"><option>中国银行基本户 · 尾号 6682</option></select></div><div class="form-field span-3"><label>凭证附件</label><div class="upload-box"><span><strong>＋ 上传${noun}凭证</strong><br><small>支持 PDF、JPG、PNG，单个文件不超过 20 MB</small></span></div></div><div class="form-field span-3"><label>备注</label><textarea class="control" placeholder="补充${noun}说明"></textarea></div></div>`, foot: `<button class="btn" data-close-modal>取消</button><button class="btn" data-toast="${noun}单草稿已保存">保存草稿</button><button class="btn btn-primary" data-confirm-modal>提交出纳审批</button>` })
}

function approvalDetail(kind) {
  const receipt = kind === 'receipt'
  const noun = receipt ? '收款' : '付款'
  openModal({ eyebrow: `待我审批 · ${noun}单`, title: `${receipt ? 'SK-2026-0091' : 'FK-2026-0072'} · ${money(receipt ? 180000 : 95000)}`, wide: true, body: `<div class="notice warning" style="margin-bottom:16px"><span>!</span><div><strong>审批通过后不可直接编辑或删除</strong><p>该单据将计入项目${receipt ? '收入、增加已收并核减应收' : '外部成本、增加已付并核减应付'}，错误需通过冲销修正。</p></div></div><div class="form-grid cols-3"><div class="form-field"><label>项目</label><strong>${projects[0].name}</strong></div><div class="form-field"><label>${receipt ? '收入' : '支出'}合同</label><strong>${receipt ? contracts[0].no : contracts[1].no}</strong></div><div class="form-field"><label>合同阶段</label><strong>${receipt ? '阶段验收款' : '设备到货款'}</strong></div><div class="form-field"><label>${receipt ? '客户' : '供应商'}</label><strong>${receipt ? '四川华西集团' : '成都锐视科技有限公司'}</strong></div><div class="form-field"><label>${noun}日期</label><strong>2026-08-28</strong></div><div class="form-field"><label>${noun}金额</label><strong style="font-size:18px">${money(receipt ? 180000 : 95000)}</strong></div><div class="form-field"><label>${receipt ? '付款' : '收款'}户名</label><strong>${receipt ? '四川华西集团有限公司' : '成都锐视科技有限公司'}</strong></div><div class="form-field"><label>开户银行</label><strong>招商银行成都高新支行</strong></div><div class="form-field"><label>银行账号</label><strong>**** **** **** 7821</strong></div></div><h3 style="margin-top:22px">审批记录</h3><div class="timeline"><div class="timeline-item done"><span class="timeline-date">今天 09:18</span><i class="timeline-dot"></i><div class="timeline-copy"><strong>杨阳提交审批</strong><p>飞书应用消息已发送给贺茂维</p></div></div><div class="timeline-item warn"><span class="timeline-date">待处理</span><i class="timeline-dot"></i><div class="timeline-copy"><strong>贺茂维 · 出纳审批</strong><p>等待核对到账、金额与账户信息</p></div></div></div>`, foot: `<button class="btn" data-close-modal>关闭</button><button class="btn btn-danger" data-reject>驳回</button><button class="btn btn-primary" data-approve>通过并确认${noun}</button>` })
}

function contractDetail(index) {
  routeTo('contract-detail', { id: index })
}

function renderContractDetail(params) {
  const c = contracts[Number(params.get('id'))] || contracts[0]
  const receipt = c.kind === '收入合同'
  const noun = receipt ? '收款' : '付款'
  const stages = receipt ? [
    ['合同首付款', '2026-07-15', 420000, 420000, '已完成', 'success'],
    ['阶段验收款', c.nextDate, 180000, 0, '已逾期', 'danger'],
    ['系统上线款', '2026-09-05', 300000, 0, '即将到期', 'warning'],
    ['质保款', '2026-12-20', 300000, 0, '未到期', '']
  ] : [
    ['设备采购款', '2026-07-18', 285000, 285000, '已完成', 'success'],
    ['设备到货款', c.nextDate, 95000, 0, '已逾期', 'danger'],
    ['现场服务尾款', '2026-09-28', 80000, 0, '未到期', '']
  ]
  const rows = stages.map((stage, index) => {
    const rate = stage[2] ? Math.round(stage[3] / stage[2] * 100) : 0
    const remaining = Math.max(stage[2] - stage[3], 0)
    return `<div class="contract-stage-row"><div><strong>${stage[0]}</strong><small>第 ${index + 1} 阶段 · ${stage[1]}</small></div><strong class="number">${money(stage[2])}</strong><strong class="number">${money(stage[3])}</strong><strong class="number ${remaining ? 'amount-negative' : 'amount-positive'}">${money(remaining)}</strong><strong class="number">${rate}%</strong><span>${stage[3] ? '1 笔' : '0 笔'}</span><span>${tag(stage[4], stage[5])}</span></div>`
  }).join('')
  const settledRate = Math.round(c.settled / c.amount * 100)
  page.innerHTML = `${pageHead(`${c.kind} · ${c.no}`, '合同详情', '合同主数据、阶段计划和结算进度集中查看。', `<button class="btn" data-route="contracts">← 返回合同列表</button><button class="btn" data-${receipt ? 'receipt' : 'payment'}-form>＋ 发起${noun}</button><button class="btn btn-primary" data-contract-form>编辑合同</button>`)}
    <section class="contract-detail-hero"><div><div class="eyebrow">${c.kind}</div><h1>${c.name}</h1><p>${c.no} · ${c.project}</p></div>${tag(c.status, 'success')}</section>
    <section class="section contract-detail-kpis"><div><span>合同金额</span><strong class="number">${money(c.amount)}</strong><small>${c.kind}</small></div><div><span>结算率</span><strong class="number">${settledRate}%</strong><small>${c.settled ? '已确认 ' + money(c.settled) : '暂无已确认金额'}</small></div><div><span>已${noun}</span><strong class="number">${money(c.settled)}</strong><small>已审批确认</small></div><div><span>待${noun}</span><strong class="number amount-negative">${money(Math.max(c.amount - c.settled, 0))}</strong><small>尚未确认</small></div><div><span>阶段数</span><strong class="number">${stages.length}</strong><small>已配置计划</small></div><div><span>${noun}单</span><strong class="number">${stages.filter(stage => stage[3] > 0).length}</strong><small>已确认单据</small></div></section>
    <section class="section contract-info-card"><div class="section-head"><div><h2>合同信息</h2><p class="muted">合同主数据和履约对象</p></div>${tag(c.status, 'success')}</div><div class="contract-info-grid"><div><span>合同名称</span><strong>${c.name}</strong></div><div><span>合同编号</span><strong>${c.no}</strong></div><div><span>所属项目</span><strong>${c.project}</strong></div><div><span>${receipt ? '客户' : '供应商'}</span><strong>${c.partner}</strong></div><div><span>签订日期</span><strong>2026-03-12</strong></div><div><span>履约期间</span><strong>2026-03-12 至 2026-12-31</strong></div></div></section>
    <section class="section contract-stages-card"><div class="section-head"><div><h2>阶段详情</h2><p class="muted">${noun}计划、结算率和关联单据一览</p></div><div class="stage-entry-actions"><span class="muted">共 ${stages.length} 个阶段</span><button class="btn btn-primary btn-sm" data-stage-form>＋ 新增阶段</button></div></div><div class="contract-stage-table"><div class="contract-stage-head"><span>阶段</span><span>计划金额</span><span>已${noun}</span><span>未${noun}</span><span>结算率</span><span>${noun}单</span><span>状态</span></div>${rows}</div></section>`
  page.insertAdjacentHTML('beforeend', `<section class="section contract-attachments"><div class="section-head"><div><h2>合同附件</h2><p class="muted">合同详情、阶段和资金信息确认后，在页面底部统一管理附件。</p></div><button class="btn btn-sm" data-toast="附件选择器已打开">＋ 上传附件</button></div><div class="attachment-list"><div class="attachment-row"><span class="attachment-type word">W</span><div><strong>智慧工地机器人协同平台采购合同.docx</strong><small>杨阳上传 · 2026-03-12 16:20 · 1.8 MB</small></div><span class="tag success">可预览</span><div class="inline-actions"><button class="btn btn-quiet btn-sm" data-toast="正在打开 Word 预览">预览</button><button class="btn btn-quiet btn-sm" data-toast="文件下载已开始">下载</button></div></div><div class="attachment-row"><span class="attachment-type pdf">P</span><div><strong>合同技术附件及验收标准.pdf</strong><small>杨阳上传 · 2026-03-12 16:22 · 4.2 MB</small></div><span class="tag success">可预览</span><div class="inline-actions"><button class="btn btn-quiet btn-sm" data-toast="正在打开 PDF 预览">预览</button><button class="btn btn-quiet btn-sm" data-toast="文件下载已开始">下载</button></div></div></div></section>`)
}

function entityForm(kind) {
  const supplier = kind === 'supplier'
  openModal({ eyebrow: '往来单位主数据', title: `新增 / 编辑${supplier ? '供应商' : '客户'}`, wide: true, body: `<div class="form-grid cols-3"><div class="form-field span-2"><label class="required">单位全称</label><input class="control" value="${supplier ? '成都锐视科技有限公司' : '四川华西集团有限公司'}"></div><div class="form-field"><label>简称</label><input class="control" value="${supplier ? '成都锐视' : '四川华西'}"></div><div class="form-field"><label class="required">统一社会信用代码</label><input class="control" value="91510100MA6CF2XXXX"></div><div class="form-field"><label>状态</label><select class="control"><option>启用</option><option>停用</option></select></div><div class="form-field"><label>联系人</label><input class="control" value="周经理"></div><div class="form-field"><label>手机</label><input class="control" value="13800006638"></div><div class="form-field"><label>邮箱</label><input class="control" value="contact@example.com"></div><div class="form-field"><label>注册地址</label><input class="control" value="成都市高新区天府大道"></div></div><h3 style="margin-top:22px">${supplier ? '银行账户' : '开票与银行信息'}</h3><div class="form-grid cols-3"><div class="form-field"><label class="required">账户户名</label><input class="control" value="${supplier ? '成都锐视科技有限公司' : '四川华西集团有限公司'}"></div><div class="form-field"><label class="required">开户银行</label><input class="control" value="招商银行成都高新支行"></div><div class="form-field"><label class="required">银行账号</label><input class="control" value="6225 8800 0000 7821"></div></div><div class="form-field" style="margin-top:16px"><label>营业执照</label><div class="upload-box">＋ 上传营业执照扫描件</div></div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn btn-primary" data-confirm-modal>保存</button>' })
}

function permissionForm() {
  openModal({ eyebrow: '权限配置', title: '添加 / 配置管理员', wide: true, body: `<div class="form-grid"><div class="form-field"><label class="required">管理员</label><select class="control"><option>请选择飞书组织成员</option><option>樊公海 · 产品研发部</option><option>李明 · 技术服务部</option></select></div><div class="form-field"><label class="required">数据范围</label><select class="control"><option>仅本人负责项目</option><option>指定部门及下级部门</option><option>全部项目</option></select></div></div><h3 style="margin-top:22px">可见菜单与操作权限</h3><div class="permission-row header" style="grid-template-columns:1fr 100px 100px"><span>模块</span><span class="center">可查看</span><span class="center">可管理</span></div>${['工时管理','项目管理','项目合同','合同收款','合同付款','项目费用','项目看板','供应商管理','客户管理','人员成本','审批岗位','审批流程','系统管理'].map((x,i)=>`<div class="permission-row" style="grid-template-columns:1fr 100px 100px"><strong>${x}</strong><div class="center"><input type="checkbox" ${i<10?'checked':''}></div><div class="center"><input type="checkbox" ${i<6?'checked':''}></div></div>`).join('')}<div class="notice warning" style="margin-top:16px"><span>!</span><div><strong>审批岗位不等于菜单权限</strong><p>菜单权限控制能否查看和操作，审批岗位控制任务分给谁；两项必须分别配置。</p></div></div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn btn-primary" data-confirm-modal>保存权限</button>' })
}

function worklogForm() {
  openModal({ eyebrow: '个人工时', title: '填报工时', body: `<div class="form-grid"><div class="form-field"><label class="required">项目类型</label><select class="control"><option>实施项目</option><option>研发项目</option><option>课题项目</option></select></div><div class="form-field"><label class="required">项目</label><select class="control"><option>${projects[0].name}</option></select></div><div class="form-field"><label class="required">开始日期</label><input type="date" class="control" value="2026-08-28"></div><div class="form-field"><label class="required">结束日期</label><input type="date" class="control" value="2026-08-28"></div><div class="form-field"><label>工作阶段</label><select class="control"><option>现场实施</option><option>开发</option><option>测试</option></select></div><div class="form-field"><label>工时</label><div class="control readonly">1 天</div></div><div class="form-field span-2"><label class="required">工作内容</label><textarea class="control">现场完成机器人调度服务联调，并核对设备状态上报结果。</textarea><small class="form-tip">同一人员同一天只能填报一次，开始和结束日期不能跨月。</small></div></div>`, foot: '<button class="btn" data-close-modal>取消</button><button class="btn">保存草稿</button><button class="btn btn-primary" data-confirm-modal>保存并提交</button>' })
}

function bindInteractions(root = document) {
  root.querySelectorAll('[data-route]').forEach(el => {
    el.onclick = event => {
      event.stopPropagation()
      routeTo(el.dataset.route, el.dataset.id ? { id: el.dataset.id } : {})
    }
  })
  root.querySelectorAll('[data-toast]').forEach(el => {
    el.onclick = event => {
      event.stopPropagation()
      showToast(el.dataset.toast)
    }
  })
  root.querySelectorAll('[data-close-modal]').forEach(el => el.onclick = closeModal)
  root.querySelectorAll('[data-confirm-modal]').forEach(el => el.onclick = () => { closeModal(); showToast('操作已完成，原型数据未实际写入') })
  root.querySelectorAll('[data-edit-project]').forEach(el => el.onclick = event => { event.stopPropagation(); projectForm() })
  root.querySelectorAll('[data-contract-form]').forEach(el => el.onclick = event => { event.stopPropagation(); contractForm() })
  root.querySelectorAll('[data-receipt-form]').forEach(el => el.onclick = event => { event.stopPropagation(); cashForm('receipt') })
  root.querySelectorAll('[data-payment-form]').forEach(el => el.onclick = event => { event.stopPropagation(); cashForm('payment') })
  root.querySelectorAll('[data-worklog-form]').forEach(el => el.onclick = event => { event.stopPropagation(); worklogForm() })
  root.querySelectorAll('[data-expense-form]').forEach(el => el.onclick = event => { event.stopPropagation(); expenseForm() })
  root.querySelectorAll('[data-expense-approve]').forEach(el => el.onclick = event => { event.stopPropagation(); expenseApproval() })
  root.querySelectorAll('[data-position-form]').forEach(el => el.onclick = event => { event.stopPropagation(); positionForm(Number(el.dataset.positionForm || 0)) })
  root.querySelectorAll('[data-workflow-preview]').forEach(el => el.onclick = event => { event.stopPropagation(); workflowPreview(el.dataset.workflowPreview) })
  root.querySelectorAll('[data-workflow-version]').forEach(el => el.onclick = event => { event.stopPropagation(); workflowVersionForm() })
  root.querySelectorAll('[data-expense-submit]').forEach(el => el.onclick = event => { event.stopPropagation(); closeModal(); routeTo('expense-detail', { id: 1 }); showToast('费用单已提交，审批任务已生成') })
  root.querySelectorAll('[data-expense-reject]').forEach(el => el.onclick = event => {
    event.stopPropagation()
    modalBody.insertAdjacentHTML('afterbegin', '<div class="form-field" style="margin-bottom:14px"><label class="required">驳回原因</label><textarea class="control" placeholder="请说明需补充或修正的内容"></textarea></div>')
    modalFoot.innerHTML = '<button class="btn" data-close-modal>取消</button><button class="btn btn-danger" data-confirm-modal>确认驳回</button>'
    bindInteractions(modalFoot)
  })
  root.querySelectorAll('[data-expense-type]').forEach(el => el.onchange = () => {
    const fields = el.closest('.modal-body').querySelector('[data-expense-type-fields]')
    const heading = el.closest('.modal-body').querySelector('[data-expense-type-title]')
    fields.innerHTML = expenseTypeFields(el.value)
    heading.textContent = el.value === 'TRAVEL' ? '差旅明细' : el.value === 'INVOICE' ? '发票信息' : '费用明细'
    showToast('费用类型已切换，专属字段已重新加载')
  })
  root.querySelectorAll('[data-worklog-detail]').forEach(el => el.onclick = event => { event.stopPropagation(); worklogDetail(Number(el.dataset.worklogDetail)) })
  root.querySelectorAll('[data-contract-detail]').forEach(el => el.onclick = event => { event.stopPropagation(); contractDetail(Number(el.dataset.contractDetail)) })
  root.querySelectorAll('[data-cash-detail]').forEach(el => el.onclick = event => { event.stopPropagation(); approvalDetail(el.dataset.cashDetail.startsWith('receipt') ? 'receipt' : 'payment') })
  root.querySelectorAll('[data-entity-form]').forEach(el => el.onclick = event => { event.stopPropagation(); entityForm(el.dataset.entityForm) })
  root.querySelectorAll('[data-permission-form]').forEach(el => el.onclick = event => { event.stopPropagation(); permissionForm() })
  root.querySelectorAll('[data-cost-form]').forEach(el => el.onclick = event => { event.stopPropagation(); personnelCostForm() })
  root.querySelectorAll('[data-option-form]').forEach(el => el.onclick = event => { event.stopPropagation(); optionForm() })
  root.querySelectorAll('[data-org-sync]').forEach(el => el.onclick = event => { event.stopPropagation(); showToast('组织架构同步已开始，完成后将更新人员和部门') })
  root.querySelectorAll('[data-stage-list]').forEach(el => el.onclick = event => { event.stopPropagation(); stageList() })
  root.querySelectorAll('[data-stage-form]').forEach(el => el.onclick = event => { event.stopPropagation(); stageForm() })
  root.querySelectorAll('[data-contract-save]').forEach(el => el.onclick = event => { event.stopPropagation(); closeModal(); stageList() })
  root.querySelectorAll('[data-approve]').forEach(el => el.onclick = () => {
    modalBody.insertAdjacentHTML('afterbegin','<div class="notice warning" style="margin-bottom:14px"><span>!</span><div><strong>请再次确认金额与到账信息</strong><p>确认后将生成不可直接修改的项目经营流水。</p></div></div>')
    modalFoot.innerHTML = '<button class="btn" data-close-modal>返回核对</button><button class="btn btn-primary" data-confirm-modal>确认通过</button>'
    bindInteractions(modalFoot)
  })
  root.querySelectorAll('[data-reject]').forEach(el => el.onclick = () => {
    modalBody.insertAdjacentHTML('afterbegin','<div class="form-field" style="margin-bottom:14px"><label class="required">驳回原因</label><textarea class="control" placeholder="请说明账户、金额或凭证存在的问题"></textarea></div>')
    modalFoot.innerHTML = '<button class="btn" data-close-modal>取消</button><button class="btn btn-danger" data-confirm-modal>确认驳回</button>'
    bindInteractions(modalFoot)
  })
  root.querySelectorAll('.segmented button').forEach(el => el.onclick = event => {
    event.stopPropagation()
    el.parentElement.querySelectorAll('button').forEach(x => x.classList.remove('active'))
    el.classList.add('active')
  })
  root.querySelectorAll('.tabs .tab').forEach(el => {
    if (el.dataset.route || el.dataset.projectTab) return
    el.onclick = () => {
      el.parentElement.querySelectorAll('.tab').forEach(x => x.classList.remove('active'))
      el.classList.add('active')
      showToast(`已切换到“${el.textContent.trim()}”`)
    }
  })
  root.querySelectorAll('[data-project-tab]').forEach(el => el.onclick = event => {
    event.stopPropagation()
    const key = el.dataset.projectTab
    root.querySelectorAll('[data-project-tab]').forEach(tab => tab.classList.toggle('active', tab === el))
    root.querySelectorAll('[data-project-analysis]').forEach(panel => { panel.hidden = key !== 'analysis' })
    root.querySelectorAll('[data-project-extra-panel]').forEach(panel => { panel.hidden = panel.dataset.projectExtraPanel !== key })
  })
  root.querySelectorAll('[data-analysis-tab]').forEach(el => el.onclick = event => {
    event.stopPropagation()
    const panel = el.closest('.settlement-analysis')
    panel.querySelectorAll('[data-analysis-tab]').forEach(x => x.classList.toggle('active', x === el))
    panel.querySelectorAll('.analysis-stage-panel').forEach(x => { x.hidden = x.dataset.side !== el.dataset.analysisTab })
  })
  root.querySelectorAll('[data-stage-toggle]').forEach(el => el.onclick = event => {
    event.stopPropagation()
    const detail = document.getElementById(el.dataset.stageToggle)
    if (!detail) return
    detail.hidden = !detail.hidden
    el.classList.toggle('expanded', !detail.hidden)
  })
  root.querySelectorAll('[data-tree-trigger]').forEach(el => el.onclick = event => {
    event.stopPropagation()
    const menu = el.nextElementSibling
    menu.hidden = !menu.hidden
  })
  root.querySelectorAll('[data-tree-value]').forEach(el => el.onclick = event => {
    event.stopPropagation()
    const menu = el.closest('.tree-menu')
    menu.querySelectorAll('.tree-option').forEach(x => x.classList.remove('active'))
    el.classList.add('active')
    menu.previousElementSibling.querySelector('span').textContent = el.dataset.treeValue
    menu.hidden = true
  })
  root.querySelectorAll('[data-reset]').forEach(el => el.onclick = () => {
    const filters = el.closest('.filters')
    filters.querySelectorAll('input').forEach(input => { if (!['date','month'].includes(input.type)) input.value = '' })
    filters.querySelectorAll('select').forEach(select => select.selectedIndex = 0)
    const tree = filters.querySelector('.tree-trigger span')
    if (tree) tree.textContent = '全部部门'
    showToast('筛选条件已重置')
  })
  root.querySelectorAll('[data-action-menu]').forEach(el => el.onclick = () => openModal({ eyebrow: '快捷操作', title: '发起业务', body: '<div class="directory-grid" style="padding:0;grid-template-columns:repeat(2,1fr)"><button class="entity-card" data-receipt-form><h3>＋ 增加收款</h3><p class="muted">关联收入合同阶段</p></button><button class="entity-card" data-payment-form><h3>＋ 发起合同付款</h3><p class="muted">关联支出合同阶段</p></button><button class="entity-card" data-worklog-form><h3>＋ 填报工时</h3><p class="muted">提交个人项目投入</p></button><button class="entity-card" data-route="approvals"><h3>处理工时审批</h3><p class="muted">当前 3 条待办</p></button></div>', foot: '<button class="btn" data-close-modal>关闭</button>' }))
}

function render() {
  closeModal()
  const { route, params } = currentRoute()
  breadcrumb.textContent = routeNames[route] || '工作台'
  document.title = `${breadcrumb.textContent} · 综合项目管理系统 v3.0.44 原型`
  document.querySelectorAll('.nav-link').forEach(el => el.classList.toggle('active', el.dataset.route === route || (route === 'project-detail' && el.dataset.route === 'projects') || (route === 'expense-detail' && el.dataset.route === 'project-expenses') || (route === 'workflow-detail' && el.dataset.route === 'workflows')))
  if (route === 'workbench') renderWorkbench()
  else if (route === 'projects') renderProjects()
  else if (route === 'project-detail') renderProjectDetail(params)
  else if (route === 'contracts') renderContracts()
  else if (route === 'contract-detail') renderContractDetail(params)
  else if (route === 'receipts') renderCashList('receipt')
  else if (route === 'payments') renderCashList('payment')
  else if (route === 'project-expenses') renderProjectExpenses()
  else if (route === 'expense-detail') renderExpenseDetail(params)
  else if (route === 'project-board') renderProjectBoard()
  else if (route === 'suppliers') renderEntities('supplier')
  else if (route === 'customers') renderEntities('customer')
  else if (route === 'permissions') renderPermissions()
  else if (route === 'approval-positions') renderApprovalPositions()
  else if (route === 'workflows') renderWorkflows()
  else if (route === 'workflow-detail') renderWorkflowDetail(params)
  else if (routeNames[route]) renderExistingModule(route)
  else renderWorkbench()
  bindInteractions(page)
  document.getElementById('sidebar').classList.remove('open')
  window.scrollTo({ top: 0, behavior: 'instant' })
}

document.querySelectorAll('.nav-group-title').forEach(button => button.onclick = () => {
  const items = button.nextElementSibling
  items.hidden = !items.hidden
  button.lastElementChild.textContent = items.hidden ? '›' : '⌄'
})
document.getElementById('mobileMenu').onclick = () => document.getElementById('sidebar').classList.toggle('open')
modalBackdrop.addEventListener('click', event => {
  if (event.target !== modalBackdrop) return
  modal.classList.remove('attention')
  void modal.offsetWidth
  modal.classList.add('attention')
  showToast('表单未关闭，请使用取消或右上角关闭按钮')
})
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !modalBackdrop.hidden) showToast('为避免丢失内容，请使用表单内的关闭按钮')
})
document.addEventListener('click', event => {
  if (!event.target.closest('.tree-control')) document.querySelectorAll('.tree-menu').forEach(menu => menu.hidden = true)
})
window.addEventListener('hashchange', render)
bindInteractions(document.querySelector('.sidebar'))
render()


