const page = document.getElementById('page')
const pageTitle = document.getElementById('pageTitle')
const crumb = document.getElementById('crumb')
const modalMask = document.getElementById('modalMask')
const modalTitle = document.getElementById('modalTitle')
const modalSub = document.getElementById('modalSub')
const modalBody = document.getElementById('modalBody')
const modalFoot = document.getElementById('modalFoot')
const toast = document.getElementById('toast')

const money = n => `¥${Number(n || 0).toLocaleString('zh-CN')}`
const pct = (n, d) => d ? `${Math.round(n / d * 100)}%` : '—'
const tag = (text, tone = '') => `<span class="tag ${tone}">${text}</span>`
const bar = (n, d, tone = '') => `<span class="bar ${tone}"><span style="width:${Math.min(d ? n / d * 100 : 0, 100)}%"></span></span>`

const categories = [
  { major: '材料成本', children: ['材料成本'] },
  { major: '人工成本', children: ['人工成本'] },
  { major: '机械使用费', children: ['机械使用费'] },
  { major: '其他直接/间接费用', children: ['差旅费', '运输', '包装费', '技术服务费', '修理费', '招标投标费', '劳务费', '检测试验费', '安全经费', '临时设施费', '办公费', '保险费', '其他'] },
  { major: '加工成本、工程分包成本', children: ['内部加工费', '外部加工费', '工程分包成本'] },
  { major: '设备采购', children: ['设备采购'] },
  { major: '部门制造费用', children: ['部门制造费用'] }
]

const budgetTemplates = {
  '经营项目': [
    { name: '人工成本', major: '人工成本', minor: '人工成本', budget: 90000, actual: 36000, source: '人工成本结转' },
    { name: '材料成本', major: '材料成本', minor: '材料成本', budget: 120000, actual: 38000, source: '合同付款 / 项目费用' },
    { name: '设备采购', major: '设备采购', minor: '设备采购', budget: 300000, actual: 285000, source: '支出合同付款' },
    { name: '技术服务费', major: '其他直接/间接费用', minor: '技术服务费', budget: 70000, actual: 0, source: '合同付款 / 项目费用' },
    { name: '运输包装费', major: '其他直接/间接费用', minor: '运输', budget: 30000, actual: 12600, source: '项目费用' },
    { name: '工程分包成本', major: '加工成本、工程分包成本', minor: '工程分包成本', budget: 70000, actual: 0, source: '支出合同付款' }
  ],
  '研发项目': [
    { name: '人工成本', major: '人工成本', minor: '人工成本', budget: 260000, actual: 168000, source: '人工成本结转' },
    { name: '材料成本', major: '材料成本', minor: '材料成本', budget: 80000, actual: 22000, source: '合同付款 / 项目费用' },
    { name: '测试试验费', major: '其他直接/间接费用', minor: '检测试验费', budget: 60000, actual: 8400, source: '项目费用' },
    { name: '外部加工费', major: '加工成本、工程分包成本', minor: '外部加工费', budget: 90000, actual: 64000, source: '支出合同付款' },
    { name: '设备采购', major: '设备采购', minor: '设备采购', budget: 30000, actual: 12000, source: '支出合同付款' }
  ]
}

const projects = [
  { id: 1, code: 'BUS-2026-008', name: '智慧工地机器人协同平台', major: '经营项目', sub: '技术服务', status: '进行中', owner: '杨阳', dept: '产品研发部 / 信息化中心', customer: '四川华西集团', days: 36, income: 1200000, received: 420000, costBudget: 680000, contractCost: 285000, projectCost: 12600, laborCost: 36000 },
  { id: 2, code: 'RND-2026-003', name: '机器人集群智能调度系统', major: '研发项目', sub: '自主研发', status: '进行中', owner: '樊公海', dept: '产品研发部 / 机器人中心', customer: '内部研发', days: 88, income: 0, received: 0, costBudget: 520000, contractCost: 86000, projectCost: 20400, laborCost: 168000 },
  { id: 3, code: 'RND-2026-011', name: '智能建造外部申报课题', major: '研发项目', sub: '外部申报', status: '立项中', owner: '林宗奇', dept: '产品研发部 / 信息化中心', customer: '省科技厅', days: 20, income: 300000, received: 0, costBudget: 310000, contractCost: 0, projectCost: 3200, laborCost: 0 },
  { id: 4, code: 'BUS-2025-027', name: '自动化钢筋加工产线交付项目', major: '经营项目', sub: '设备销售', status: '验收中', owner: '李明', dept: '技术服务部 / 交付中心', customer: '中铁八局', days: 104, income: 1080000, received: 720000, costBudget: 980000, contractCost: 510000, projectCost: 42600, laborCost: 208000 }
]

const projectBudgetItems = budgetTemplates['经营项目']

const contracts = [
  { no: 'HT-SR-2026-014', name: '智慧工地机器人协同平台采购合同', kind: '收入合同', project: '智慧工地机器人协同平台', partner: '四川华西集团', amount: 1200000, category: '—', settled: 420000, due: 180000 },
  { no: 'HT-ZC-2026-019', name: '视觉传感器及边缘计算设备采购', kind: '支出合同', project: '智慧工地机器人协同平台', partner: '成都锐视科技有限公司', amount: 460000, category: '设备采购 / 设备采购', settled: 285000, due: 95000 },
  { no: 'HT-ZC-2026-022', name: '现场联调技术服务合同', kind: '支出合同', project: '智慧工地机器人协同平台', partner: '四川精工智能装备有限公司', amount: 180000, category: '其他直接/间接费用 / 技术服务费', settled: 0, due: 60000 }
]

const costEntries = [
  { no: 'CP-20260908-0001', type: '合同付款', project: '智慧工地机器人协同平台', category: '设备采购 / 设备采购', amount: 95000, person: '杨阳', status: '待复核' },
  { no: 'CE-20260908-0003', type: '项目费用', project: '智慧工地机器人协同平台', category: '其他直接/间接费用 / 运输', amount: 6800, person: '陈露', status: '待复核' },
  { no: 'LC-202609-0002', type: '人工成本结转', project: '智慧工地机器人协同平台', category: '人工成本 / 人工成本', amount: 36000, person: '贺茂维', status: '待复核' }
]

const names = {
  workbench: '工作台', worklogs: '我的工时', 'worklog-approval': '工时审批', 'worklog-board': '工时看板',
  projects: '项目管理', 'project-detail': '项目详情', 'project-budget-items': '项目预算项', contracts: '项目合同', 'contract-payments': '合同付款',
  'contract-receipts': '合同收款',
  'project-costs': '项目费用', 'labor-costs': '人工成本结转', 'cost-review': '费用复核',
  'project-board': '项目看板', counterparties: '客户/供应商', configuration: '基础配置',
  integration: '集成与通知', permissions: '角色权限'
}

function route() {
  return new URLSearchParams(location.hash.replace(/^#/, '')).get('page') || 'workbench'
}

function go(name) {
  location.hash = `page=${name}`
}

function pageHead(eyebrow, title, desc, action = '') {
  return `<div class="page-head"><div><div class="eyebrow">${eyebrow}</div><h2>${title}</h2><p class="muted">${desc}</p></div><div class="top-actions">${action}</div></div>`
}

function filters(fields, action = '查询') {
  return `<section class="filter">${fields}<div class="filter-actions"><button class="primary" data-toast="${action}完成">${action}</button><button class="ghost">重置</button></div></section>`
}

function openModal(kind) {
  const map = {
    project: ['新增项目', formProject()],
    contract: ['新增合同', formContract()],
    payment: ['新增合同付款', formPayment()],
    'new-cost': ['新增项目费用', formCost()],
    labor: ['新增人工成本结转', formLabor()],
    budget: ['新增预算项', formBudget()]
  }
  const [title, body] = map[kind] || map['new-cost']
  modalTitle.textContent = title
  modalSub.textContent = 'v3.0.59 原型弹窗'
  modalBody.innerHTML = body
  modalFoot.innerHTML = `<button class="ghost" data-close>取消</button><button class="primary" data-toast="已保存，原型不写入真实数据" data-close>保存</button>`
  modalMask.hidden = false
}

function field(label, inner, full = false) {
  return `<div class="field ${full ? 'full' : ''}"><label>${label}</label>${inner}</div>`
}

function select(opts) {
  return `<select class="control">${opts.map(x => `<option>${x}</option>`).join('')}</select>`
}

function formProject() {
  return `<div class="form-grid">
    ${field('项目名称', '<input class="control" value="智慧工地机器人协同平台">')}
    ${field('项目编号', '<input class="control" value="BUS-2026-008">')}
    ${field('项目大类', select(['经营项目', '研发项目']))}
    ${field('项目小类', select(['委托研发', '设备销售', '技术服务', '机器人施工', '设备租赁']))}
    ${field('项目状态', select(['立项中', '进行中', '验收中', '已完成', '已终止']))}
    ${field('项目负责人', select(['杨阳', '樊公海', '林宗奇', '李明']))}
    ${field('所属部门', select(['产品研发部 / 信息化中心', '产品研发部 / 机器人中心', '技术服务部 / 交付中心']))}
    ${field('客户', select(['四川华西集团', '中铁八局', '内部研发']))}
    ${field('工时填报', select(['允许填报', '暂停填报']))}
    ${field('说明', '<textarea class="control">新增项目只维护主信息。保存成功后，系统会按项目大类自动生成该项目的预算项。经营/研发预算项模板只在后台基础配置维护。</textarea>', true)}
  </div>`
}

function formContract() {
  return `<div class="form-grid">
    ${field('合同类型', select(['收入合同', '支出合同']))}
    ${field('所属项目', select(projects.map(p => p.name)))}
    ${field('合同名称', '<input class="control" value="视觉传感器及边缘计算设备采购">')}
    ${field('往来单位', select(['四川华西集团', '成都锐视科技有限公司', '四川精工智能装备有限公司']))}
    ${field('合同金额', '<input class="control" value="460000">')}
    ${field('签订日期', '<input class="control" type="date" value="2026-09-08">')}
    ${field('预算项（支出合同必填）', select(['设备采购', '技术服务费', '运输包装费', '工程分包成本']))}
    ${field('成本分类（按项目类型联动）', '<input class="control" value="设备采购 / 设备采购" readonly>')}
    ${field('合同附件', '<div class="upload">拖入或选择合同附件；保存草稿也保留附件</div>', true)}
  </div>`
}

function formPayment() {
  return `<div class="form-grid">
    ${field('项目', select(projects.map(p => p.name)))}
    ${field('支出合同', select(['视觉传感器及边缘计算设备采购', '现场联调技术服务合同']))}
    ${field('付款阶段', select(['首付款 95,000 · 2026-09-08 到期', '验收款 190,000 · 2026-10-20 到期']))}
    ${field('付款金额', '<input class="control" value="95000">')}
    ${field('收款方名称', '<input class="control" value="成都锐视科技有限公司">')}
    ${field('收款银行', '<input class="control" value="招商银行成都高新支行">')}
    ${field('收款账号', '<input class="control" value="6214 **** **** 9182">')}
    ${field('预算项/成本分类', '<input class="control" value="设备采购 · 设备采购 / 设备采购" readonly>')}
    ${field('附件', '<div class="upload">上传付款依据、发票或合同补充材料</div>', true)}
  </div>`
}

function formCost() {
  return `<div class="form-grid">
    ${field('项目', select(projects.map(p => p.name)))}
    ${field('预算项', select(['人工成本', '材料成本', '设备采购', '技术服务费', '运输包装费', '工程分包成本']))}
    ${field('成本分类（联动）', '<input class="control" value="其他直接/间接费用 / 运输" readonly>')}
    ${field('发生时间', '<input class="control" type="date" value="2026-09-08">')}
    ${field('金额', '<input class="control" value="6800">')}
    ${field('说明', '<input class="control" value="现场设备运输与临时包装费用">')}
    ${field('附件', '<div class="upload">只上传成本凭证；不再填写收款方、银行、付款状态</div>', true)}
  </div>`
}

function formLabor() {
  return `<div class="form-grid">
    ${field('项目', select(projects.map(p => p.name)))}
    ${field('核算月份', '<input class="control" type="month" value="2026-09">')}
    ${field('预算项/成本分类', '<input class="control" value="人工成本 · 人工成本 / 人工成本" readonly>')}
    ${field('金额', '<input class="control" value="36000">')}
    ${field('月结依据', '<div class="upload">上传人工成本分摊表</div>', true)}
    ${field('提示', '<textarea class="control" readonly>该项目本月已有 1 笔人工成本记录，系统允许继续录入，用于分批或按来源结转。</textarea>', true)}
  </div>`
}

function formBudget() {
  return `<div class="form-grid">
    ${field('项目大类', select(['经营项目', '研发项目']))}
    ${field('所属项目', select(projects.map(p => p.name)))}
    ${field('预算项名称', '<input class="control" value="设备采购">')}
    ${field('关联成本分类', '<input class="control" value="设备采购 / 设备采购" readonly>')}
    ${field('预算金额', '<input class="control" value="120000">')}
    ${field('备注', '<input class="control" value="首版预算拆分">')}
  </div>`
}

function renderWorkbench() {
  const total = projects.reduce((s, p) => s + p.contractCost + p.projectCost + p.laborCost, 0)
  page.innerHTML = `${pageHead('负责人 + 员工双区工作台', '今天先看风险，再处理待办', '上半区面向项目负责人，下半区面向员工个人填报和审批状态。', '<button class="primary" data-modal="payment">发起合同付款</button><button class="ghost" data-modal="new-cost">新增项目费用</button><button class="ghost" data-modal="labor">人工成本结转</button>')}
  <section class="card ledger-hero">
    <div class="ledger-title"><div><div class="eyebrow">OWNER LEDGER</div><h2>我负责项目的经营账本</h2><p class="muted">预算、成本、合同收付款和复核待办在一个视图里汇合。</p></div><div class="stamp">费用复核制</div></div>
    <div class="grid cols-5 card-body">
      <div class="kpi"><label>负责项目</label><strong>4</strong><small>经营 2 / 研发 2</small></div>
      <div class="kpi"><label>实际总成本</label><strong>${money(total)}</strong><small>合同 + 项目费用 + 人工</small></div>
      <div class="kpi warn"><label>待费用复核</label><strong>3</strong><small>合同付款/项目费用/人工成本</small></div>
      <div class="kpi"><label>到期应收</label><strong>${money(180000)}</strong><small>只统计已到期未收</small></div>
      <div class="kpi danger"><label>预算预警</label><strong>2</strong><small>成本或人天接近上限</small></div>
    </div>
  </section>
  <div class="split" style="margin-top:16px">
    <section class="card">
      <div class="card-head"><div><h2>项目负责人视图</h2><p class="muted">按项目看预算执行和当前动作</p></div><button class="quiet" data-route="project-board">进入项目看板</button></div>
      <div class="table-wrap"><table><thead><tr><th>项目</th><th>预算执行</th><th>成本组成</th><th>提醒</th></tr></thead><tbody>${projects.map(projectRow).join('')}</tbody></table></div>
    </section>
    <section class="card">
      <div class="card-head"><div><h2>员工视图</h2><p class="muted">工时填报和个人提交单据</p></div><button class="primary" data-toast="进入工时填报">填报工时</button></div>
      <div class="card-body mini-list">
        <div class="mini-item"><div><strong>本月已提交工时 8 单</strong><small>已审批 6 单，待审批 2 单；工作日自动计算天数</small></div>${tag('待确认', 'warn')}</div>
        <div class="mini-item"><div><strong>项目费用 CE-20260908-0003</strong><small>运输费用 ¥6,800，等待费用复核</small></div>${tag('待复核', 'warn')}</div>
        <div class="mini-item"><div><strong>飞书通知直达</strong><small>工时、费用、付款卡片点击进入对应单据详情</small></div>${tag('已设计', 'success')}</div>
      </div>
    </section>
  </div>`
}

function projectRow(p) {
  const actual = p.contractCost + p.projectCost + p.laborCost
  const tone = actual / p.costBudget > .9 ? 'danger' : actual / p.costBudget > .75 ? 'warn' : ''
  return `<tr data-route="project-detail"><td><span class="main-cell">${p.name}</span><span class="sub-cell">${p.code} · ${p.major}/${p.sub}</span></td><td>${bar(actual, p.costBudget, tone)}<span class="sub-cell">${money(actual)} / 总预算 ${money(p.costBudget)}</span></td><td><span class="sub-cell">人工 ${money(p.laborCost)}</span><span class="sub-cell">合同/费用 ${money(p.contractCost + p.projectCost)}</span></td><td>${actual / p.costBudget > .9 ? tag('成本预警', 'danger') : tag('正常', 'success')}</td></tr>`
}

function renderProjects() {
  page.innerHTML = `${pageHead('项目主数据 + 预算摘要', '项目管理', '列表只保留项目主信息和关键经营摘要，预算明细进入项目详情维护。', '<button class="primary" data-modal="project">新增项目</button><button class="ghost">导入项目</button>')}
  ${filters(`${field('项目大类', select(['全部', '经营项目', '研发项目']))}${field('项目小类', select(['全部', '委托研发', '设备销售', '技术服务', '机器人施工', '设备租赁', '自主研发', '外部申报']))}${field('所属部门', select(['全部部门', '产品研发部', '产品研发部 / 信息化中心', '技术服务部']))}${field('负责人', select(['全部', '杨阳', '樊公海', '林宗奇']))}${field('项目状态', select(['全部', '立项中', '进行中', '验收中']))}${field('标题模糊查询', '<input class="control" placeholder="输入项目名称或编号">')}`)}
  <section class="card"><div class="table-wrap"><table><thead><tr><th style="width:24%">项目</th><th>状态/分类</th><th>负责人/部门</th><th>客户</th><th>已审批工时</th><th>总预算</th><th>预算剩余</th><th>操作</th></tr></thead><tbody>${projects.map(p => {
    const actual = p.contractCost + p.projectCost + p.laborCost
    return `<tr><td><span class="main-cell">${p.name}</span><span class="sub-cell">${p.code}</span></td><td>${tag(p.status, 'primary')}<span class="sub-cell">${p.major} / ${p.sub}</span></td><td><span class="main-cell">${p.owner}</span><span class="sub-cell">${p.dept}</span></td><td>${p.customer}</td><td>${p.days} 天<span class="sub-cell">只用于工时分析</span></td><td>${money(p.costBudget)}<span class="sub-cell">预算项合计</span></td><td>${money(p.costBudget - actual)}<span class="sub-cell">使用率 ${pct(actual, p.costBudget)}</span></td><td><button class="quiet" data-route="project-detail">查看</button><button class="quiet" data-modal="project">编辑</button><button class="quiet" data-route="project-budget-items">预算项</button></td></tr>`
  }).join('')}</tbody></table></div></section>`
}

function renderBudgetItems() {
  const currentProject = projects[0]
  const items = budgetTemplates[currentProject.major]
  const totalBudget = items.reduce((sum, item) => sum + item.budget, 0)
  const totalActual = items.reduce((sum, item) => sum + item.actual, 0)
  page.innerHTML = `${pageHead('项目预算金额维护', '项目预算项', '本页只维护当前项目的预算金额、启用状态和备注；经营/研发两套预算项模板统一在后台基础配置维护。', '<button class="primary" data-modal="budget">调整预算项</button><button class="ghost" data-route="configuration">后台模板配置</button>')}
  <section class="card ledger-hero"><div class="grid cols-4 card-body">
    <div class="kpi"><label>当前项目</label><strong style="font-size:20px">${currentProject.name}</strong><small>${currentProject.major} / ${currentProject.sub}</small></div>
    <div class="kpi"><label>总预算</label><strong>${money(totalBudget)}</strong><small>预算项金额合计</small></div>
    <div class="kpi warn"><label>已发生</label><strong>${money(totalActual)}</strong><small>复核通过后累计</small></div>
    <div class="kpi"><label>预算剩余</label><strong>${money(totalBudget - totalActual)}</strong><small>使用率 ${pct(totalActual, totalBudget)}</small></div>
  </div></section>
  ${filters(`${field('预算项', '<input class="control" placeholder="输入预算项名称">')}${field('启用状态', select(['全部', '启用', '停用']))}${field('发生来源', select(['全部', '人工成本结转', '支出合同付款', '项目费用']))}`)}
  <section class="card"><div class="card-head"><div><h2>当前项目预算项</h2><p class="muted">创建项目时已按“${currentProject.major}”后台模板自动生成，项目内不修改模板结构。</p></div>${tag('来自后台模板','primary')}</div><div class="table-wrap"><table><thead><tr><th>预算项</th><th>关联成本分类</th><th>预算金额</th><th>已发生</th><th>剩余</th><th>使用率</th><th>来源</th><th>操作</th></tr></thead><tbody>${items.map(i => `<tr><td><span class="main-cell">${i.name}</span><span class="sub-cell">项目内金额项</span></td><td>${i.major} / ${i.minor}</td><td>${money(i.budget)}</td><td>${money(i.actual)}</td><td>${money(i.budget - i.actual)}</td><td>${pct(i.actual, i.budget)}</td><td>${i.source}</td><td><button class="quiet" data-modal="budget">改金额</button><button class="quiet">停用</button></td></tr>`).join('')}</tbody></table></div></section>
  <section class="card" style="margin-top:16px"><div class="card-head"><h2>规则说明</h2></div><div class="card-body mini-list">
    <div class="mini-item"><div><strong>模板在后台维护</strong><small>经营项目、研发项目各一套模板；项目创建后自动复制为项目自己的预算项。</small></div>${tag('后台配置','success')}</div>
    <div class="mini-item"><div><strong>项目内只改金额和启用状态</strong><small>如果要新增全局预算项，去基础配置改模板，避免单项目误改全局规则。</small></div>${tag('边界清楚','primary')}</div>
    <div class="mini-item"><div><strong>人工成本固定入人工成本预算项</strong><small>合同付款和项目费用按单据选择的预算项归集。</small></div>${tag('成本归集','primary')}</div>
  </div></section>`
}

function renderProjectDetail() {
  const p = projects[0]
  const actual = p.contractCost + p.projectCost + p.laborCost
  page.innerHTML = `${pageHead('单项目经营分析', p.name, `${p.code} · ${p.major}/${p.sub} · ${p.owner}`, '<button class="primary" data-modal="budget">新增预算项</button><button class="ghost" data-modal="payment">新增合同付款</button><button class="ghost" data-modal="new-cost">新增项目费用</button>')}
  <section class="card ledger-hero">
    <div class="grid cols-5 card-body">
      <div class="kpi"><label>合同收入</label><strong>${money(p.income)}</strong><small>已收 ${money(p.received)}</small></div>
      <div class="kpi"><label>总预算</label><strong>${money(p.costBudget)}</strong><small>预算项金额合计</small></div>
      <div class="kpi warn"><label>实际总成本</label><strong>${money(actual)}</strong><small>合同 + 费用 + 人工</small></div>
      <div class="kpi"><label>预算剩余</label><strong>${money(p.costBudget - actual)}</strong><small>使用率 ${pct(actual, p.costBudget)}</small></div>
      <div class="kpi success"><label>预计毛利</label><strong>${money(p.income - p.costBudget)}</strong><small>按合同收入 - 总预算</small></div>
    </div>
  </section>
  <section class="card" style="margin-top:16px">
    <div class="tabs"><button class="tab active">经营分析</button><button class="tab">基本信息</button><button class="tab">预算项执行</button><button class="tab">合同与资金</button><button class="tab">成本明细</button><button class="tab">工时明细</button><button class="tab">操作记录</button></div>
    <div class="card-body split">
      <div>
        <h2>预算项执行</h2>
        <div class="budget-ruler">${projectBudgetItems.map(i => `<div class="ruler-line"><div class="ruler-name">${i.name}</div>${bar(i.actual,i.budget,i.actual/i.budget>.9?'danger':i.actual/i.budget>.75?'warn':'')}<div class="ruler-num">${money(i.actual)} / ${money(i.budget)}</div></div>`).join('')}</div>
      </div>
      <div class="card" style="box-shadow:none"><div class="card-head"><h2>经营口径</h2></div><div class="card-body mini-list">
        <div class="mini-item"><div><strong>人工成本</strong><small>来自人工成本结转，固定归入人工成本预算项</small></div><b>${money(p.laborCost)}</b></div>
        <div class="mini-item"><div><strong>其他预算项成本</strong><small>来自支出合同付款和项目费用填报</small></div><b>${money(p.contractCost + p.projectCost)}</b></div>
        <div class="mini-item"><div><strong>总成本</strong><small>人工成本 + 其他预算项成本</small></div><b>${money(actual)}</b></div>
      </div></div>
    </div>
  </section>
  <section class="card" style="margin-top:16px"><div class="card-head"><h2>合同与资金</h2><button class="quiet" data-route="contracts">查看合同管理</button></div><div class="table-wrap"><table><thead><tr><th>合同名称</th><th>类型</th><th>往来单位</th><th>成本分类</th><th>合同金额</th><th>已结算</th><th>到期未结</th></tr></thead><tbody>${contracts.map(c => `<tr><td><span class="main-cell">${c.name}</span><span class="sub-cell">${c.no}</span></td><td>${tag(c.kind, c.kind === '支出合同' ? 'warn' : 'success')}</td><td>${c.partner}</td><td>${c.category}</td><td>${money(c.amount)}</td><td>${money(c.settled)}</td><td>${money(c.due)}</td></tr>`).join('')}</tbody></table></div></section>`
}

function renderContracts() {
  page.innerHTML = `${pageHead('合同主信息与阶段分离', '项目合同', '收入合同不填成本分类；支出合同按所选项目大类联动可选预算项和成本分类。', '<button class="primary" data-modal="contract">新增合同</button><button class="ghost">下载导入模板</button>')}
  ${filters(`${field('合同类型', select(['全部', '收入合同', '支出合同']))}${field('项目', select(['全部项目', ...projects.map(p => p.name)]))}${field('往来单位', '<input class="control" placeholder="客户或供应商">')}${field('状态', select(['全部', '草稿', '生效', '已完成']))}`)}
  <section class="card"><div class="table-wrap"><table><thead><tr><th>合同名称</th><th>类型</th><th>项目</th><th>往来单位</th><th>成本分类</th><th>合同金额</th><th>阶段</th><th>操作</th></tr></thead><tbody>${contracts.map(c => `<tr><td><button class="quiet" data-route="contract-detail">${c.name}</button><span class="sub-cell">${c.no}</span></td><td>${tag(c.kind, c.kind === '支出合同' ? 'warn' : 'success')}</td><td>${c.project}</td><td>${c.partner}</td><td>${c.category}</td><td>${money(c.amount)}</td><td>${c.kind === '收入合同' ? '收款 2/4' : '付款 2/3'}</td><td><button class="quiet" data-route="contract-detail">详情</button><button class="quiet" data-modal="contract">编辑</button></td></tr>`).join('')}</tbody></table></div></section>`
}

function renderContractDetail() {
  const c = contracts[1]
  page.innerHTML = `${pageHead('合同详情', c.name, `${c.no} · ${c.project}`, '<button class="primary" data-modal="payment">新增付款单</button><button class="ghost">新增阶段</button><button class="ghost" data-modal="contract">编辑合同</button>')}
  <section class="card ledger-hero"><div class="grid cols-5 card-body">
    <div class="kpi"><label>合同金额</label><strong>${money(c.amount)}</strong><small>${c.kind}</small></div>
    <div class="kpi"><label>已付/已收</label><strong>${money(c.settled)}</strong><small>复核通过单据</small></div>
    <div class="kpi warn"><label>到期未结</label><strong>${money(c.due)}</strong><small>只统计已到期阶段</small></div>
    <div class="kpi"><label>结算率</label><strong>${pct(c.settled, c.amount)}</strong><small>已结 / 合同金额</small></div>
    <div class="kpi"><label>款单笔数</label><strong>2</strong><small>通过 1 / 待复核 1</small></div>
  </div></section>
  <div class="split" style="margin-top:16px">
    <section class="card"><div class="card-head"><h2>合同主信息</h2></div><div class="card-body grid cols-2">
      <div><span class="sub-cell">往来单位</span><strong>${c.partner}</strong></div><div><span class="sub-cell">成本分类</span><strong>${c.category}</strong></div>
      <div><span class="sub-cell">签订日期</span><strong>2026-08-26</strong></div><div><span class="sub-cell">状态</span><strong>生效</strong></div>
      <div><span class="sub-cell">附件</span><strong>采购合同.pdf、补充协议.docx</strong></div>
    </div></section>
    <section class="card"><div class="card-head"><h2>复核路径</h2></div><div class="card-body"><div class="flow"><span>申请人提交</span><i>→</i><span>费用复核</span><i>→</i><span>复核通过即已付入成本</span></div></div></section>
  </div>
  <section class="card" style="margin-top:16px"><div class="card-head"><h2>付款阶段</h2><button class="ghost">新增阶段</button></div><div class="table-wrap"><table><thead><tr><th>阶段</th><th>计划日期</th><th>计划金额</th><th>已付</th><th>剩余应付</th><th>状态</th></tr></thead><tbody><tr><td>首付款</td><td>2026-09-08</td><td>${money(95000)}</td><td>${money(95000)}</td><td>${money(0)}</td><td>${tag('已完成','success')}</td></tr><tr><td>验收款</td><td>2026-10-20</td><td>${money(190000)}</td><td>${money(0)}</td><td>${money(190000)}</td><td>${tag('未到期','info')}</td></tr></tbody></table></div></section>`
}

function renderCostList(kind) {
  const title = kind === 'labor' ? '人工成本结转' : kind === 'payment' ? '合同付款' : '项目费用'
  const btn = kind === 'labor' ? 'labor' : kind === 'payment' ? 'payment' : 'new-cost'
  page.innerHTML = `${pageHead('一级费用复核', title, kind === 'labor' ? '财务按项目和月份录入人工成本，不限制同月多次结转。' : kind === 'payment' ? '合同付款复核通过即视为已付并计入合同成本。' : '项目费用只保留成本凭证字段，去掉收款方、银行账号和付款状态。', `<button class="primary" data-modal="${btn}">新增${title}</button>`)}
  ${filters(`${field('日期/月度', '<input class="control" type="month" value="2026-09">')}${field('项目', select(['全部项目', ...projects.map(p => p.name)]))}${field('成本大类', select(['全部', ...categories.map(c => c.major)]))}${field('状态', select(['全部', '草稿', '待复核', '已通过', '已驳回']))}`)}
  <section class="card"><div class="table-wrap"><table><thead><tr><th>单号</th><th>类型</th><th>项目</th><th>成本分类</th><th>金额</th><th>申请人</th><th>状态</th><th>操作</th></tr></thead><tbody>${costEntries.map(e => `<tr><td><span class="main-cell">${e.no}</span><span class="sub-cell">2026-09-08</span></td><td>${e.type}</td><td>${e.project}</td><td>${e.category}</td><td>${money(e.amount)}</td><td>${e.person}</td><td>${tag(e.status,'warn')}</td><td><button class="quiet" data-route="cost-review">查看</button></td></tr>`).join('')}</tbody></table></div></section>`
}

function renderReceiptList() {
  page.innerHTML = `${pageHead('收入合同阶段收款', '合同收款', '选择收入合同和收款阶段，复核通过后计入已收并核减已到期应收。', '<button class="primary">新增合同收款</button>')}
  ${filters(`${field('项目', select(['全部项目', ...projects.map(p => p.name)]))}${field('收入合同', select(['全部收入合同', '智慧工地机器人协同平台采购合同']))}${field('客户', select(['全部客户', '四川华西集团', '中铁八局']))}${field('状态', select(['全部', '草稿', '待复核', '已通过', '已驳回']))}`)}
  <section class="card"><div class="table-wrap"><table><thead><tr><th>收款单号</th><th>项目/合同</th><th>客户</th><th>阶段</th><th>计划金额</th><th>已收金额</th><th>剩余应收</th><th>状态</th></tr></thead><tbody>
    <tr><td><span class="main-cell">REC-20260908-0001</span><span class="sub-cell">2026-09-08</span></td><td><span class="main-cell">智慧工地机器人协同平台</span><span class="sub-cell">智慧工地机器人协同平台采购合同</span></td><td>四川华西集团</td><td>第二阶段验收款</td><td>${money(260000)}</td><td>${money(80000)}</td><td>${money(180000)}</td><td>${tag('待复核','warn')}</td></tr>
    <tr><td><span class="main-cell">REC-20260828-0008</span><span class="sub-cell">2026-08-28</span></td><td><span class="main-cell">自动化钢筋加工产线交付项目</span><span class="sub-cell">自动化钢筋加工产线销售合同</span></td><td>中铁八局</td><td>首付款</td><td>${money(720000)}</td><td>${money(720000)}</td><td>${money(0)}</td><td>${tag('已通过','success')}</td></tr>
  </tbody></table></div></section>`
}

function renderCostReview() {
  page.innerHTML = `${pageHead('合同付款 / 项目费用 / 人工成本', '费用复核', '复核岗位多人可见，任一人通过即可关闭其他待办，记录实际复核人。', '')}
  <section class="card"><div class="tabs"><button class="tab active">待我复核</button><button class="tab">已复核</button><button class="tab">全部复核记录</button></div><div class="card-body mini-list">${costEntries.map(e => `<div class="mini-item"><div><strong>${e.type} · ${e.no}</strong><small>${e.project} · ${e.category} · ${money(e.amount)} · 飞书卡片直达本详情</small></div><div><button class="primary" data-toast="已复核通过，写入项目成本流水">通过</button> <button class="danger" data-toast="已驳回">驳回</button></div></div>`).join('')}</div></section>
  <section class="card" style="margin-top:16px"><div class="card-head"><h2>一级复核说明</h2></div><div class="card-body"><div class="flow"><span>提交单据</span><i>→</i><span>通知费用复核岗位全部成员</span><i>→</i><span>任一人复核</span><i>→</i><span>通过后入项目成本流水</span></div></div></section>`
}

function renderBoard() {
  page.innerHTML = `${pageHead('按预算项看经营执行', '项目看板', '看板以“总预算、人工成本、其他预算项成本”为主线；预算项由项目大类决定，可下钻到合同付款、项目费用和人工成本结转。', '<button class="primary" data-toast="看板已刷新">查询</button>')}
  ${filters(`${field('项目大类', select(['全部', '经营项目', '研发项目']))}${field('项目小类', select(['全部', '技术服务', '设备销售', '自主研发', '外部申报']))}${field('所属部门', select(['全部部门', '产品研发部', '技术服务部']))}${field('负责人', select(['全部', '杨阳', '樊公海', '林宗奇']))}`)}
  <section class="card ledger-hero"><div class="grid cols-5 card-body"><div class="kpi"><label>合同收入</label><strong>${money(2580000)}</strong><small>收入合同合计</small></div><div class="kpi"><label>已收</label><strong>${money(1140000)}</strong><small>复核通过收款</small></div><div class="kpi warn"><label>实际总成本</label><strong>${money(1409800)}</strong><small>人工成本 + 其他预算项成本</small></div><div class="kpi"><label>总预算</label><strong>${money(2490000)}</strong><small>项目预算项合计</small></div><div class="kpi success"><label>预计毛利</label><strong>${money(90000)}</strong><small>合同收入 - 总预算</small></div></div></section>
  <div class="split" style="margin-top:16px"><section class="card"><div class="card-head"><h2>预算项执行排行</h2><button class="quiet" data-route="project-budget-items">维护预算项</button></div><div class="card-body budget-ruler">${projectBudgetItems.map(i => `<div class="ruler-line"><div class="ruler-name">${i.name}</div>${bar(i.actual,i.budget,i.actual/i.budget>.9?'danger':i.actual/i.budget>.75?'warn':'')}<div class="ruler-num">${pct(i.actual,i.budget)}</div></div>`).join('')}</div></section><section class="card"><div class="card-head"><h2>项目风险排行</h2></div><div class="card-body mini-list">${projects.map(p => `<div class="mini-item"><div><strong>${p.name}</strong><small>${p.major}/${p.sub} · 已审批工时 ${p.days} 天</small></div>${tag((p.contractCost+p.projectCost+p.laborCost)/p.costBudget>.8?'预算预警':'正常',(p.contractCost+p.projectCost+p.laborCost)/p.costBudget>.8?'warn':'success')}</div>`).join('')}</div></section></div>
  <section class="card" style="margin-top:16px"><div class="card-head"><h2>成本归集拆分</h2></div><div class="grid cols-3 card-body"><div class="kpi"><label>人工成本</label><strong>${money(448000)}</strong><small>人工成本结转单复核通过</small></div><div class="kpi"><label>合同付款成本</label><strong>${money(881000)}</strong><small>支出合同付款复核通过</small></div><div class="kpi"><label>项目费用成本</label><strong>${money(80800)}</strong><small>项目费用复核通过</small></div></div></section>`
}

function renderConfiguration() {
  page.innerHTML = `${pageHead('层级配置', '基础配置', '项目分类树、预算项模板和成本分类树统一维护，不再使用扁平静态下拉框。', '<button class="primary">新增配置项</button>')}
  <div class="split"><section class="card"><div class="card-head"><h2>项目分类</h2></div><div class="card-body category-tree">
    <div class="tree-node"><header><strong>经营项目</strong>${tag('大类','primary')}</header><div class="tree-children">${['委托研发','设备销售','技术服务','机器人施工','设备租赁'].map(x=>tag(x)).join('')}</div></div>
    <div class="tree-node"><header><strong>研发项目</strong>${tag('大类','primary')}</header><div class="tree-children">${['自主研发','外部申报'].map(x=>tag(x)).join('')}</div></div>
  </div></section><section class="card"><div class="card-head"><h2>后台预算项模板</h2><button class="quiet" data-toast="进入后台模板维护弹窗">维护模板</button></div><div class="card-body category-tree"><div class="tree-node"><header><strong>经营项目模板</strong>${tag(`${budgetTemplates['经营项目'].length} 项`)}</header><div class="tree-children">${budgetTemplates['经营项目'].map(i=>tag(i.name)).join('')}</div></div><div class="tree-node"><header><strong>研发项目模板</strong>${tag(`${budgetTemplates['研发项目'].length} 项`)}</header><div class="tree-children">${budgetTemplates['研发项目'].map(i=>tag(i.name)).join('')}</div></div></div></section></div>
  <section class="card" style="margin-top:16px"><div class="card-head"><h2>成本分类</h2></div><div class="card-body category-tree">${categories.map(c => `<div class="tree-node"><header><strong>${c.major}</strong>${tag(`${c.children.length} 小类`)}</header><div class="tree-children">${c.children.map(x=>tag(x)).join('')}</div></div>`).join('')}</div></section>`
}

function renderSimple(title, desc) {
  page.innerHTML = `${pageHead('原型覆盖页面', title, desc, '')}<section class="card"><div class="card-body"><p class="muted">本页面在 v3.0.59 中保持原功能，视觉会跟随新的筛选、卡片和表格规范统一。重点改造集中在项目预算、成本分类、合同付款、项目费用、人工成本结转和费用复核。</p></div></section>`
}

function render() {
  const r = route()
  document.querySelectorAll('.nav-link').forEach(btn => btn.classList.toggle('active', btn.dataset.route === r))
  pageTitle.textContent = names[r] || '工作台'
  crumb.textContent = names[r] || '工作台'
  if (r === 'workbench') renderWorkbench()
  else if (r === 'projects') renderProjects()
  else if (r === 'project-budget-items') renderBudgetItems()
  else if (r === 'project-detail') renderProjectDetail()
  else if (r === 'contracts') renderContracts()
  else if (r === 'contract-detail') renderContractDetail()
  else if (r === 'contract-receipts') renderReceiptList()
  else if (r === 'contract-payments') renderCostList('payment')
  else if (r === 'project-costs') renderCostList('cost')
  else if (r === 'labor-costs') renderCostList('labor')
  else if (r === 'cost-review') renderCostReview()
  else if (r === 'project-board') renderBoard()
  else if (r === 'configuration') renderConfiguration()
  else if (r === 'counterparties') renderSimple('客户/供应商', '客户和供应商继续保留自动编码、导入、银行账户和联系人管理。')
  else if (r === 'integration') renderSimple('集成与通知', '保留飞书连接状态、组织同步、通知策略和通知记录；费用复核新增飞书待办卡片。')
  else if (r === 'permissions') renderSimple('角色权限', '保留角色 + 菜单 + 数据范围，新增项目预算、项目费用、人工成本结转和费用复核权限点。')
  else renderSimple(names[r] || r, '该页面非本次核心重构，但会跟随统一视觉规范。')
}

document.addEventListener('click', e => {
  const routeBtn = e.target.closest('[data-route]')
  if (routeBtn) go(routeBtn.dataset.route)
  const modalBtn = e.target.closest('[data-modal]')
  if (modalBtn) openModal(modalBtn.dataset.modal)
  const closeBtn = e.target.closest('[data-close]')
  if (closeBtn) modalMask.hidden = true
  const toastBtn = e.target.closest('[data-toast]')
  if (toastBtn) {
    toast.textContent = toastBtn.dataset.toast
    toast.classList.add('show')
    setTimeout(() => toast.classList.remove('show'), 1800)
  }
})

window.addEventListener('hashchange', render)
render()
