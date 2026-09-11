from pathlib import Path
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
OUT_FILES = [ROOT / "docs" / "01-user-manual.docx", ROOT / "docs" / "系统使用手册-v3.0.29.docx"]

BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
MUTED = "667085"
LIGHT_BLUE = "E8EEF5"
LIGHT_GRAY = "F2F4F7"
WHITE = "FFFFFF"


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths):
    table.autofit = False
    for row in table.rows:
        for idx, width in enumerate(widths):
            row.cells[idx].width = Inches(width)
            row.cells[idx].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(row.cells[idx])
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(int(w * 1440) for w in widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")


def mark_header_row(row):
    tr_pr = row._tr.get_or_add_trPr()
    if tr_pr.find(qn("w:tblHeader")) is None:
        tr_pr.append(OxmlElement("w:tblHeader"))


def set_run_font(run, name="Microsoft YaHei", size=None, color=None, bold=None, italic=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def add_text(doc, text, size=10.5, color="1F2937", bold=False, italic=False, align=None, after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.25
    if align is not None:
        p.alignment = align
    set_run_font(p.add_run(text), size=size, color=color, bold=bold, italic=italic)
    return p


def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.375 + 0.2 * level)
    p.paragraph_format.first_line_indent = Inches(-0.188)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.25
    set_run_font(p.add_run(text), size=10.5, color="1F2937")
    return p


def add_number(doc, text):
    p = doc.add_paragraph(style="List Number")
    p.paragraph_format.left_indent = Inches(0.375)
    p.paragraph_format.first_line_indent = Inches(-0.188)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.25
    set_run_font(p.add_run(text), size=10.5, color="1F2937")
    return p


def add_table(doc, headers, rows, widths):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    set_table_geometry(table, widths)
    mark_header_row(table.rows[0])
    for idx, text in enumerate(headers):
        cell = table.rows[0].cells[idx]
        set_cell_shading(cell, LIGHT_BLUE)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(text)
        set_run_font(r, size=9.5, color=DARK_BLUE, bold=True)
    for row_data in rows:
        cells = table.add_row().cells
        for idx, text in enumerate(row_data):
            p = cells[idx].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(str(text))
            set_run_font(r, size=9.2, color="1F2937")
            if len(table.rows) % 2 == 0:
                set_cell_shading(cells[idx], "FBFCFE")
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def add_heading(doc, text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    p.paragraph_format.keep_with_next = True
    p.add_run(text)
    return p


def add_screenshot(doc, filename, caption, width=5.8):
    cropped = ASSETS / "manual-crops" / filename
    path = cropped if cropped.exists() else ASSETS / filename
    if not path.exists():
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run()
    inline = run.add_picture(str(path), width=Inches(width))
    inline._inline.docPr.set("descr", caption)
    inline._inline.docPr.set("title", caption)
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(8)
    set_run_font(cap.add_run(caption), size=9, color=MUTED, italic=True)


def add_step(doc, number, title, detail, image=None, caption=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.25
    set_run_font(p.add_run(f"步骤 {number}｜{title}"), size=11, color=DARK_BLUE, bold=True)
    add_text(doc, detail, size=10.2, after=3)
    if image:
        add_screenshot(doc, image, caption or f"步骤 {number} 对应界面", width=4.9)


def add_page_field(paragraph):
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr)
    run._r.append(fld_char2)


def configure_document(doc):
    section = doc.sections[0]
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.9)
    section.right_margin = Inches(0.9)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)

    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25
    for level, size, color, before, after in ((1, 16, BLUE, 16, 8), (2, 13, BLUE, 12, 6), (3, 11.5, DARK_BLUE, 8, 4)):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.paragraph_format.space_after = Pt(0)
    set_run_font(header.add_run("综合项目管理系统 | 用户使用手册"), size=8.5, color=MUTED)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.paragraph_format.space_before = Pt(0)
    set_run_font(footer.add_run("文档版本 v3.0.29 | 页码 "), size=8.5, color=MUTED)
    page_run = footer.add_run()
    set_run_font(page_run, size=8.5, color=MUTED)
    add_page_field(footer)


def build_manual():
    doc = Document()
    configure_document(doc)

    add_text(doc, "综合项目管理系统", size=25, color="0B2545", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=3)
    add_text(doc, "用户使用手册", size=17, color=BLUE, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=16)
    add_text(doc, "文档版本 v3.0.29 | 对应生产运行版本 v3.0.26 | 2026-09-03", size=10, color=MUTED, align=WD_ALIGN_PARAGRAPH.CENTER, after=20)
    callout = doc.add_table(rows=1, cols=1)
    callout.style = "Table Grid"
    set_table_geometry(callout, [6.5])
    cell = callout.cell(0, 0)
    mark_header_row(callout.rows[0])
    set_cell_shading(cell, "F4F6F9")
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    set_run_font(p.add_run("用途："), size=10, color=DARK_BLUE, bold=True)
    set_run_font(p.add_run("本手册用于指导员工、审批人、项目负责人、出纳和系统管理员使用综合项目管理系统。"), size=10, color="1F2937")
    add_text(doc, "", after=4)
    add_heading(doc, "目录", 1)
    for item in ["1. 系统说明与登录", "2. 工作台", "3. 工时管理", "4. 项目管理", "5. 合同与阶段", "6. 合同收款单、合同付款单与出纳审批", "7. 工时看板与项目看板", "8. 系统管理", "9. 提醒、通知与权限", "10. 常见问题与安全提示", "附录：当前版本变更摘要"]:
        add_bullet(doc, item)
    doc.add_page_break()

    add_heading(doc, "1. 系统说明与登录", 1)
    add_text(doc, "综合项目管理系统用于管理工时、项目、合同、收付款和项目经营数据。飞书负责登录、组织架构和应用消息通知；业务详情、填报、审批和报表操作在本系统完成。系统不是银行转账系统，也不替代财务总账。")
    add_step(doc, 1, "打开系统", "在飞书工作台打开系统应用，或在浏览器访问系统地址。首次访问会进入登录页面。", "manual-workbench.png", "图 1  登录成功后的工作台入口")
    add_step(doc, 2, "完成飞书登录", "点击“使用飞书登录”，按飞书提示完成授权。授权完成后系统会回到工作台，不需要另设系统密码。", "manual-workbench.png", "图 2  登录后进入工作台")
    add_step(doc, 3, "确认菜单范围", "登录后先看左侧菜单。系统根据当前账号权限显示菜单；看不到某个菜单时，先联系系统管理员配置角色和数据范围。", "manual-workbench.png", "图 3  按权限展示的左侧菜单")
    add_table(doc, ["一级模块", "主要菜单", "用途"], [
        ("工作台", "工作台", "查看个人工时、负责项目、待办和提醒"),
        ("工时管理", "我的工时 / 工时审批 / 工时看板 / 工时台账", "填报、审批和统计工时"),
        ("项目管理", "项目、合同、收款、付款、项目看板", "维护项目经营数据"),
        ("系统管理", "人员成本、集成与通知、管理员管理、基础配置", "维护敏感配置和系统权限"),
    ], [1.25, 2.25, 3.0])

    add_heading(doc, "2. 工作台", 1)
    add_text(doc, "工作台根据用户权限分为上下两部分：上方是项目负责人工作区，下方是员工工作区。没有项目负责人权限时，上方区域会自动隐藏。")
    add_step(doc, 1, "查看项目负责人区", "上方区域查看负责项目数量、预算执行、已发生成本、工时审批、应收应付和项目预警。没有项目负责人权限时，此区域自动隐藏。", "manual-workbench.png", "图 4  工作台上方的项目负责人区")
    add_step(doc, 2, "查看员工区", "下方区域查看本月工时审批单据数量、审批中、已驳回、草稿和最近工时。点击最近工时的某一条会进入对应详情。", "manual-workbench.png", "图 5  工作台下方的员工工时区")
    add_step(doc, 3, "处理快捷任务", "根据需要点击“填报工时”“工时审批”“增加收款”或“发起付款”。按钮是否显示由当前权限和项目类型决定。", "manual-workbench.png", "图 6  工作台快捷操作入口")
    add_step(doc, 4, "查看提醒", "右侧提醒展示未来 30 天内到期、已逾期、预算接近/超支、人天接近/超支和待审批事项；点击事项可进入对应页面。", "manual-workbench.png", "图 7  工作台项目提醒列表")

    add_heading(doc, "3. 工时管理", 1)
    add_heading(doc, "3.1 填报工时", 2)
    add_step(doc, 1, "打开新增表单", "进入“工时管理 > 我的工时”，点击右上角“新增工时”，打开填报弹窗。", "manual-worklogs.png", "图 8  我的工时页面的新增入口")
    add_step(doc, 2, "选择项目", "先选择项目类型，再选择项目。项目下拉框支持名称或编号筛选，只显示与所选类型匹配且允许填报的项目；项目选择不会带出审批人。", "manual-worklog-form.png", "图 9  项目类型和项目选择")
    add_step(doc, 3, "填写日期和工时", "填写开始日期和结束日期。系统按自然日计算天数，开始日期和结束日期必须在同一月份内，单位固定为天。", "manual-worklog-form.png", "图 10  开始日期、结束日期和工时")
    add_step(doc, 4, "填写工作内容", "选择工作阶段和工作状态，在“工作内容”中写清实际完成的事项、产出和需要跟进的问题。", "manual-worklog-form.png", "图 11  工作阶段和工作内容")
    add_step(doc, 5, "保存或提交", "需要稍后继续时点击“保存草稿”；确认无误后点击“保存并提交”。提交后本条工时独立进入审批任务，并通知实际审批人。", "manual-worklog-form.png", "图 12  保存草稿与提交审批")
    add_heading(doc, "3.2 工时校验和状态", 2)
    add_step(doc, 1, "检查日期规则", "单位固定为天，不计算小时；日期不能跨月，开始日期不能晚于结束日期。", "manual-worklog-form.png", "图 13  日期校验提示位置")
    add_step(doc, 2, "检查重复填报", "同一人员同一天无论项目是否不同都不能重复填报；已有日期区间与新日期区间相交也会被拦截。", "manual-worklogs.png", "图 14  已有工时记录和状态")
    add_step(doc, 3, "查看处理状态", "列表中的状态用于区分草稿、审批中、已通过和已驳回。草稿或驳回记录可进入编辑，审批中和已通过记录不能由普通用户直接改动。", "manual-worklogs.png", "图 15  工时状态和查看入口")
    add_heading(doc, "3.3 工时审批", 2)
    add_step(doc, 1, "打开审批列表", "进入“工时管理 > 工时审批”，默认查看“待我审批”；点击“已审批”查看自己已经处理过的记录。", "manual-approvals.png", "图 16  工时审批页签")
    add_step(doc, 2, "打开工时详情", "点击工时记录的名称或“查看”，进入该条工时的完整详情，核对填报人、项目、日期、天数、工作描述和审批链。", "manual-approvals.png", "图 17  工时审批记录入口")
    add_step(doc, 3, "通过或驳回", "确认无误点击“通过”；需要修改时点击“驳回”并填写具体原因。审批完成后系统向申请人发送结果通知。", "manual-approvals.png", "图 18  工时审批处理操作")
    add_step(doc, 4, "确认统计更新", "通过后刷新列表，项目已发生人天、人员成本、工作台和工时看板会按最新审批状态更新。", "manual-approvals.png", "图 19  审批结果和刷新后的状态")

    add_heading(doc, "4. 项目管理", 1)
    add_text(doc, "项目管理主页面只展示项目主信息，经营数据进入项目详情或项目看板查看。项目新增和编辑均使用弹窗。")
    add_step(doc, 1, "打开项目管理", "进入“项目管理 > 项目管理”。页面只展示项目名称、编号、状态、类型、负责人、部门、客户和是否允许填报等主信息。", "manual-projects.png", "图 20  项目管理列表")
    add_step(doc, 2, "设置筛选条件", "按项目类型、项目状态、项目部门、项目负责人、客户筛选；在标题输入框中输入项目名称或编号关键词。", "manual-projects.png", "图 21  项目管理筛选区")
    add_step(doc, 3, "选择部门层级", "打开项目部门下拉框后按组织树选择部门。选择上级部门会同时筛选该部门下的所有子部门；选中子部门则只筛选该子部门。", "manual-projects.png", "图 22  项目部门层级选择")
    add_step(doc, 4, "查询和分页", "点击“查询”加载结果；点击“重置”清除条件。列表底部可以切换页码和每页条数。", "manual-projects.png", "图 23  项目列表查询和分页")
    add_step(doc, 5, "查看或编辑项目", "点击项目名称或“查看”进入项目详情；点击“编辑”打开弹窗修改主信息。保存后返回列表，列表数据自动刷新。", "manual-projects.png", "图 24  项目查看和编辑入口")
    add_step(doc, 6, "查看预算和经营数据", "在项目详情的预算和经营页签查看预算人天、已发生人天、剩余人天、成本预算、已发生合同成本、预算剩余和执行率；这些已发生数据只读。", "manual-projects.png", "图 25  项目预算信息入口")

    add_heading(doc, "5. 合同与阶段", 1)
    add_heading(doc, "5.1 合同", 2)
    add_step(doc, 1, "选择合同类型", "进入“项目管理 > 项目合同”，点击“收入合同”查看客户合同，点击“支出合同”查看供应商合同。实施项目两类合同都可以建立。", "manual-contract-detail.png", "图 26  合同收入/支出页签")
    add_step(doc, 2, "新建合同", "点击“新增合同”，选择项目和客户/供应商，填写合同编号、名称、金额、签订日期和履约期间等核心信息。", "manual-contract-detail.png", "图 27  合同主信息区域")
    add_step(doc, 3, "上传附件或保存草稿", "在新建页面直接选择合同附件；资料不完整时点击“保存草稿”，后续可以继续编辑和补充附件。资料完整时保存为正式合同。", "manual-contract-detail.png", "图 28  合同附件和保存操作")
    add_step(doc, 4, "打开合同详情", "在合同列表点击合同名称，进入合同详情。详情页不需要额外点击即可看到合同主信息、结算率、合同收付款单笔数和全部阶段。", "manual-contract-detail.png", "图 29  合同详情概览")
    add_step(doc, 5, "管理合同阶段", "在阶段区域先查看阶段列表；只有点击“新增阶段”才打开新增弹窗。填写阶段名称、计划金额、计划日期和提醒规则。", "manual-contract-detail.png", "图 30  合同阶段列表")
    add_step(doc, 6, "查看阶段结算", "阶段的已收/已付、剩余应收/应付和结算率由审批通过的合同收付款单自动计算；已发生收付款的阶段不能随意删除或调低计划金额。", "manual-contract-detail.png", "图 31  阶段金额和结算状态")
    add_heading(doc, "5.2 合同阶段", 2)
    add_bullet(doc, "点击“阶段”只查看阶段列表；点击“新增阶段”才打开新增弹窗，避免误操作。")
    add_bullet(doc, "阶段填写名称、计划金额、计划日期和提醒规则；阶段计划金额应与合同金额一致。")
    add_bullet(doc, "已收/已付、剩余应收/应付和结算率由已确认收付款自动计算。")
    add_screenshot(doc, "manual-contract-detail.png", "图 6  合同详情：合同主信息与阶段详情")

    add_heading(doc, "6. 合同收款单、合同付款单与出纳审批", 1)
    add_heading(doc, "6.1 新增合同收款单", 2)
    add_step(doc, 1, "选择收入阶段", "点击“新增合同收款单”，依次选择项目、收入合同和有剩余应收的收入阶段。合同和阶段不匹配时不能提交。", "manual-receipt-form.png", "图 32  合同收款单关联收入合同和阶段（界面示意）")
    add_step(doc, 2, "填写收款信息", "填写收款日期、金额、付款方名称、付款银行和付款账号。姓名、银行和账号均为必填项。", "manual-receipt-form.png", "图 33  收款方账户信息（界面示意）")
    add_step(doc, 3, "上传附件并校验金额", "在表单中选择回单、合同或其他材料；确认本次金额不超过阶段剩余应收。", "manual-receipt-form.png", "图 34  合同收款单附件和金额校验（界面示意）")
    add_step(doc, 4, "提交出纳审批", "点击保存或提交审批。提交后，所有具备出纳审批权限的人员收到飞书通知。", "manual-receipt-form.png", "图 35  合同收款单提交审批（界面示意）")
    add_heading(doc, "6.2 新增合同付款单", 2)
    add_step(doc, 1, "选择支出阶段", "点击“新增合同付款单”，依次选择项目、支出合同和有剩余应付的支出阶段。新增合同付款单不能选择收入合同。", "manual-payment-form.png", "图 36  合同付款单关联支出合同和阶段（界面示意）")
    add_step(doc, 2, "带出并核对供应商账户", "选择供应商后系统自动带出收款方名称、收款银行和收款账号；提交前检查本单账户，必要时可修改，系统保存本单快照。", "manual-payment-form.png", "图 37  供应商收款账户（界面示意）")
    add_step(doc, 3, "填写付款信息和附件", "填写付款日期、金额和付款账户信息，确认金额不超过阶段剩余应付，再选择付款凭证或合同附件。", "manual-payment-form.png", "图 38  合同付款单金额和附件（界面示意）")
    add_step(doc, 4, "提交出纳审批", "点击保存或提交审批。提交后，所有具备出纳审批权限的人员收到飞书通知。", "manual-payment-form.png", "图 39  合同付款单提交审批（界面示意）")
    add_heading(doc, "6.3 出纳审批", 2)
    add_step(doc, 1, "进入待审批列表", "进入对应的合同收款或合同付款页面，查看“待我审批”列表。具备出纳审批权限的人员会收到飞书卡片。", "manual-approvals.png", "图 40  待审批单据列表")
    add_step(doc, 2, "打开单据详情", "点击单据名称或“查看”，检查项目、合同、阶段、金额、收付款账户、附件和审批时间线。", "manual-approvals.png", "图 41  合同收付款单据详情入口")
    add_step(doc, 3, "通过或驳回", "确认无误点击“通过”；信息不完整时点击“驳回”并填写原因。系统记录实际审批人姓名，并向申请人发送结果通知。", "manual-approvals.png", "图 42  出纳审批处理")
    add_step(doc, 4, "核对经营结果", "收款通过后增加已收、减少应收；付款通过后增加已付、减少应付并计入外部成本。已审批单据只能通过冲销修正。", "manual-project-board.png", "图 43  审批通过后的项目经营更新")

    add_heading(doc, "7. 工时看板与项目看板", 1)
    add_heading(doc, "7.1 工时看板", 2)
    add_step(doc, 1, "设置统计条件", "进入“工时管理 > 工时看板”，选择日期范围、一级部门、项目、项目类型、人员、阶段和审批状态。", "manual-project-board.png", "图 44  工时看板筛选区示意")
    add_step(doc, 2, "查询工时图表", "点击“查询”刷新数据。工时看板只展示工时指标，包括工时总量、填报人数、项目数、审批数量、趋势、排行和分布，不包含成本和资金。", "manual-project-board.png", "图 45  工时看板统计区示意")
    add_step(doc, 3, "查看或导出明细", "点击图表或明细入口查看对应项目、人员和日期的工时记录；点击“导出明细”下载当前筛选条件下的明细文件。", "manual-project-board.png", "图 46  工时看板明细和导出入口示意")
    add_heading(doc, "7.2 项目看板", 2)
    add_step(doc, 1, "选择项目范围", "进入“项目管理 > 项目看板”。默认查看“我的项目”；拥有全部项目权限的用户可以切换“全部项目”。", "manual-project-board.png", "图 47  项目看板数据范围")
    add_step(doc, 2, "筛选并查询", "按项目类型、状态、部门、负责人、客户、项目和统计截止日期设置条件，点击“查询”刷新经营结果。", "manual-project-board.png", "图 48  项目看板筛选区")
    add_step(doc, 3, "读取经营指标", "查看收入、总成本、应收、应付、已收、已付、毛利、毛利率、预算执行和预警。应收/应付只统计已到期阶段的未收/未付金额。", "manual-project-board.png", "图 49  项目看板经营汇总")
    add_step(doc, 4, "下钻明细", "点击项目、合同阶段、趋势、账龄或预警事项，进入项目详情、合同详情、合同收付款单或工时明细，核对指标来源。", "manual-project-board.png", "图 50  项目看板下钻入口")
    add_table(doc, ["指标", "口径"], [
        ("应收", "已到期收入阶段金额 - 该阶段已确认收款"),
        ("应付", "已到期支出阶段金额 - 该阶段已确认付款"),
        ("已收/已付", "审批通过且未冲销的合同收付款单"),
        ("总成本", "已审批工时人员成本 + 已确认外部付款成本"),
        ("毛利", "已收 - 总成本"),
    ], [1.55, 4.95])
    add_screenshot(doc, "manual-project-board.png", "图 7  项目看板：经营指标、趋势和预警")

    add_heading(doc, "8. 系统管理", 1)
    add_heading(doc, "8.1 人员成本", 2)
    add_step(doc, 1, "打开人员成本", "进入“系统管理 > 人员成本”。该菜单只对具备对应权限的用户显示。", "manual-admin-console.png", "图 51  系统管理菜单和人员成本入口示意")
    add_step(doc, 2, "筛选人员", "按部门和人员筛选目标人员；部门筛选支持组织层级，选择上级部门会包含下级部门。", "manual-admin-console.png", "图 52  人员成本筛选示意")
    add_step(doc, 3, "维护单天成本", "在人员行中填写单天成本并保存。后续审批通过的工时使用该成本生成成本快照，历史已生成成本不自动重算。", "manual-admin-console.png", "图 53  人员成本维护示意")
    add_heading(doc, "8.2 集成与通知", 2)
    add_step(doc, 1, "检查飞书连接", "进入“系统管理 > 集成与通知”，查看连接状态、组织人数、最近同步时间和通知状态。", "manual-admin-console.png", "图 54  集成与通知入口示意")
    add_step(doc, 2, "同步组织架构", "点击“同步组织架构”发起同步；同步完成后查看新增/更新人员和部门统计以及同步记录。该功能仅管理员可见。", "manual-admin-console.png", "图 55  组织架构同步入口示意")
    add_step(doc, 3, "统一保存通知策略", "点击页面右上角“修改”，在弹窗中一次性调整各类通知的开关、接收人和发送渠道，点击“统一保存”。", "manual-admin-console.png", "图 56  通知策略修改入口示意")
    add_step(doc, 4, "查看失败通知", "切换到通知中心，按接收人、业务对象和发送状态筛选；打开失败记录查看原因，点击“重试”重新发送。", "manual-admin-console.png", "图 57  通知中心和重试入口示意")
    add_heading(doc, "8.3 管理员管理", 2)
    add_step(doc, 1, "创建或选择角色", "进入“系统管理 > 管理员管理”，创建角色或选择已有角色。系统初始只保留系统管理员，其他角色由管理员重新配置。", "manual-admin-console.png", "图 58  管理员管理入口示意")
    add_step(doc, 2, "配置菜单和操作", "为角色勾选需要开放的一级模块、菜单和业务操作，例如审批、编辑、删除、导出、附件、同步组织和修改配置。", "manual-admin-console.png", "图 59  角色菜单和操作权限示意")
    add_step(doc, 3, "配置数据范围", "为角色选择本人负责项目、指定部门及下级部门或全部项目。没有全部项目权限时，用户看不到其他范围的数据。", "manual-admin-console.png", "图 60  数据访问范围示意")
    add_step(doc, 4, "授权并验证", "将角色绑定到飞书组织人员，保存后让用户重新加载系统，检查菜单是否按权限显示。授权变更会写入审计记录。", "manual-admin-console.png", "图 61  人员授权和验证示意")
    add_heading(doc, "8.4 基础配置", 2)
    add_text(doc, "基础配置维护项目类型、项目状态、执行状态、工时类型、合同分类、收付款方式和提醒策略等动态下拉选项。已被业务数据引用的选项不能删除，只能停用。")

    add_heading(doc, "9. 提醒、通知与权限", 1)
    add_bullet(doc, "合同阶段未来 30 天内到期、已到期未收/未付时，工作台展示提醒，系统按策略发送飞书消息。")
    add_bullet(doc, "成本预算或人天预算接近/超过阈值时，项目负责人收到预警。")
    add_bullet(doc, "待审批工时、合同收款单和合同付款单通知实际审批人；审批结果通知申请人。")
    add_bullet(doc, "通知记录包含接收人、业务对象、发送状态、失败原因、重试次数和飞书消息 ID。")
    add_bullet(doc, "项目数据范围支持本人负责项目、指定部门及下级部门、全部项目。没有全部项目权限时，前端和接口都不会返回全量数据。")

    add_heading(doc, "10. 常见问题与安全提示", 1)
    add_heading(doc, "10.1 看不到项目", 2)
    add_text(doc, "确认管理员是否完成组织同步、项目负责人是否正确绑定飞书用户、当前账号是否有项目菜单和对应数据范围。选择部门时，上级部门会包含下级部门。")
    add_heading(doc, "10.2 工时提交失败", 2)
    add_text(doc, "依次检查是否跨月、同日已有填报、日期区间重叠、项目是否允许填报、项目类型是否匹配以及工作描述是否为空。")
    add_heading(doc, "10.3 飞书没有收到通知", 2)
    add_text(doc, "检查应用是否发布、组织是否已同步、应用消息权限是否开通，以及集成与通知中的通知策略和通知记录。通知失败不会回滚已经完成的本地审批。")
    add_heading(doc, "10.4 安全提示", 2)
    add_bullet(doc, "不要在聊天、截图或文档中发送飞书 App Secret、Cloudflare token、SSH 密码或完整银行账号。")
    add_bullet(doc, "银行账号在列表和飞书卡片中默认脱敏；附件下载、导出和详情查看都经过权限校验。")
    add_bullet(doc, "不要直接修改数据库或删除 Docker 数据卷；数据异常请记录页面、筛选条件、单据编号和时间交给管理员。")

    add_heading(doc, "附录：当前版本变更摘要", 1)
    for text in [
        "统一四大模块导航和工作台双布局，项目负责人区与员工区按权限展示。",
        "项目管理增加类型、状态、部门层级、负责人、客户和标题筛选，支持分页、弹窗 CRUD 和项目预算分析。",
        "合同收入/支出双侧、合同详情、阶段列表分离、新建合同草稿和新建时附件上传。",
        "合同收款单、合同付款单支持附件、账户自动带出、完整单据详情和出纳审批结果通知。",
        "管理员管理升级为角色、菜单、操作权限和数据访问范围；集成与通知统一保存策略并提供通知中心。",
        "应收/应付统一按已到期阶段的未收/未付金额统计；系统时间统一为 `Asia/Shanghai`。",
    ]:
        add_bullet(doc, text)

    for target in OUT_FILES:
        doc.save(target)


if __name__ == "__main__":
    build_manual()
    print("wrote", len(OUT_FILES), "docx files")

