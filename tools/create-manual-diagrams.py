from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).resolve().parents[1] / "docs" / "assets"
FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD_PATH = r"C:\Windows\Fonts\msyhbd.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD_PATH if bold else FONT_PATH, size)


def text(draw, xy, value, size=24, color="#243247", bold=False):
    draw.text(xy, value, font=font(size, bold), fill=color)


def box(draw, xy, fill="#FFFFFF", outline="#D8E0E8", radius=14, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def header(draw, title, subtitle):
    text(draw, (64, 42), "综合项目管理系统", 24, "#65758B", True)
    text(draw, (64, 86), title, 42, "#0B2545", True)
    text(draw, (66, 148), subtitle, 20, "#667085")
    draw.line((64, 195, 1536, 195), fill="#D8E0E8", width=2)


def field(draw, x, y, label, value, width=470, required=False):
    text(draw, (x, y), label + (" *" if required else ""), 19, "#344054", True)
    box(draw, (x, y + 34, x + width, y + 94), fill="#FFFFFF")
    text(draw, (x + 18, y + 51), value, 19, "#667085")


def make_cash(kind):
    is_receipt = kind == "receipt"
    title = "新增收款单" if is_receipt else "新增付款单"
    subtitle = "界面示意：先关联合同阶段，再核对账户和附件"
    image = Image.new("RGB", (1600, 980), "#F5F7FA")
    draw = ImageDraw.Draw(image)
    header(draw, title, subtitle)
    box(draw, (64, 228, 1536, 900), fill="#FFFFFF", outline="#E4E7EC")
    text(draw, (98, 260), "单据基本信息", 26, "#0B2545", True)
    field(draw, 98, 320, "项目", "请选择项目", required=True)
    field(draw, 620, 320, "合同", "请选择收入合同" if is_receipt else "请选择支出合同", required=True)
    field(draw, 98, 440, "阶段", "请选择收款阶段" if is_receipt else "请选择付款阶段", required=True)
    field(draw, 620, 440, "业务日期", "2026/09/03", required=True)
    field(draw, 98, 560, "金额", "¥ 0.00", required=True)
    counterparty = "付款方名称" if is_receipt else "收款方姓名"
    bank = "付款银行" if is_receipt else "收款银行"
    account = "付款账号" if is_receipt else "收款账号"
    field(draw, 620, 560, counterparty, "选择后自动带出，可修改", required=True)
    field(draw, 98, 680, bank, "请输入开户行", required=True)
    field(draw, 620, 680, account, "请输入银行账号", required=True)
    box(draw, (98, 795, 1090, 865), fill="#F7FAFC", outline="#B8C5D3")
    text(draw, (120, 813), "附件：点击选择文件，新建时即可暂存，保存后自动关联", 18, "#475467")
    box(draw, (1190, 795, 1360, 865), fill="#FFFFFF", outline="#D0D5DD")
    text(draw, (1225, 813), "取消", 18, "#344054", True)
    box(draw, (1380, 795, 1490, 865), fill="#087F73", outline="#087F73")
    text(draw, (1403, 813), "提交", 18, "#FFFFFF", True)
    path = OUT / f"manual-{kind}-form.png"
    image.save(path)


def make_admin():
    image = Image.new("RGB", (1600, 980), "#F5F7FA")
    draw = ImageDraw.Draw(image)
    header(draw, "集成与权限管理", "界面示意：组织同步、通知策略和角色权限集中维护")
    box(draw, (64, 228, 1536, 900), fill="#FFFFFF", outline="#E4E7EC")
    for i, (label, value, color) in enumerate([
        ("飞书连接", "正常", "#087F73"),
        ("组织人数", "126 人", "#0B2545"),
        ("待重试通知", "3 条", "#B54708"),
    ]):
        x = 98 + i * 470
        box(draw, (x, 270, x + 410, 390), fill="#F8FAFC", outline="#E4E7EC")
        text(draw, (x + 24, 294), label, 18, "#667085")
        text(draw, (x + 24, 332), value, 32, color, True)
    box(draw, (98, 430, 1490, 520), fill="#ECFDF3", outline="#ABEFC6")
    text(draw, (124, 446), "同步组织架构", 20, "#027A48", True)
    text(draw, (420, 448), "上次同步：2026-09-03 09:30 | 新增 2 人 | 更新 5 个部门", 18, "#475467")
    box(draw, (1290, 440, 1460, 500), fill="#087F73", outline="#087F73")
    text(draw, (1310, 453), "立即同步", 18, "#FFFFFF", True)
    text(draw, (98, 570), "通知策略", 25, "#0B2545", True)
    text(draw, (98, 622), "页面默认只读；点击右上角“修改”进入弹窗，一次调整全部策略后统一保存。", 18, "#667085")
    box(draw, (98, 690, 1490, 770), fill="#FFFFFF", outline="#D0D5DD")
    text(draw, (124, 715), "工时审批", 19, "#344054", True)
    text(draw, (420, 715), "应用消息 | 审批人", 18, "#667085")
    text(draw, (850, 715), "启用", 18, "#027A48", True)
    text(draw, (98, 810), "管理员管理：角色 → 菜单 → 业务操作 → 数据范围 → 绑定人员", 20, "#0B2545", True)
    image.save(OUT / "manual-admin-console.png")


if __name__ == "__main__":
    make_cash("receipt")
    make_cash("payment")
    make_admin()
    print("created manual diagrams")
