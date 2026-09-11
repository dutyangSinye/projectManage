import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "D:/myproject";
const outputDir = `${root}/outputs/import-templates-20260903-name-based`;
const publicDir = `${root}/frontend/public/templates`;

const templates = [
  {
    file: "customer-import-template.xlsx",
    title: "客户导入模板",
    sheetName: "客户导入",
    headers: ["客户名称*", "付款银行", "付款账号"],
    widths: [30, 28, 26],
    fields: [
      ["客户名称", "是", "客户的完整名称，不能重复；客户编码由系统自动生成"],
      ["付款银行", "否", "用于新建收款单时自动带出"],
      ["付款账号", "否", "用于新建收款单时自动带出"],
    ],
  },
  {
    file: "supplier-import-template.xlsx",
    title: "供应商导入模板",
    sheetName: "供应商导入",
    headers: ["供应商名称*", "收款银行", "收款账号"],
    widths: [30, 28, 26],
    fields: [
      ["供应商名称", "是", "供应商的完整名称，不能重复；供应商编码由系统自动生成"],
      ["收款银行", "否", "用于新建付款单时自动带出"],
      ["收款账号", "否", "用于新建付款单时自动带出"],
    ],
  },
  {
    file: "contract-import-template.xlsx",
    title: "合同导入模板",
    sheetName: "合同导入",
    headers: ["合同编号*", "合同名称*", "项目名称*", "合同类型*", "往来单位名称*", "合同金额*"],
    widths: [20, 32, 20, 18, 22, 18],
    fields: [
      ["合同编号", "是", "系统内唯一合同编号"],
      ["合同名称", "是", "合同名称"],
      ["项目名称", "是", "必须填写系统中已存在且唯一的项目名称，匹配不到时请修正后重新导入"],
      ["合同类型", "是", "使用下拉框选择收入合同或支出合同，系统内部自动保存对应类型编码"],
      ["往来单位名称", "是", "收入合同填写客户名称，支出合同填写供应商名称；系统会自动转换为对应编码"],
      ["合同金额", "是", "填写数字，不带千分位符号或货币符号"],
    ],
  },
];

const colors = {
  ink: "#17324D",
  muted: "#64748B",
  teal: "#0F766E",
  pale: "#E6FFFA",
  line: "#CBD5E1",
  note: "#F8FAFC",
};

async function buildTemplate(template) {
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add(template.sheetName);
  const notes = workbook.worksheets.add("填写说明");
  sheet.showGridLines = false;
  notes.showGridLines = false;

  sheet.getRangeByIndexes(0, 0, 1, template.headers.length).values = [template.headers];
  const headerRange = sheet.getRangeByIndexes(0, 0, 1, template.headers.length);
  headerRange.format = {
    fill: colors.teal,
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: colors.teal },
  };
  headerRange.format.rowHeight = 28;
  template.widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width;
  });
  sheet.getRangeByIndexes(1, 0, 199, template.headers.length).format = {
    font: { color: colors.ink },
    verticalAlignment: "center",
    borders: { preset: "insideHorizontal", style: "thin", color: colors.line },
  };
  sheet.getRangeByIndexes(1, 0, 199, template.headers.length).format.rowHeight = 22;
  sheet.getRangeByIndexes(1, 0, 199, template.headers.length).format.borders = {
    preset: "outside",
    style: "thin",
    color: colors.line,
  };
  sheet.freezePanes.freezeRows(1);
  if (template.file === "contract-import-template.xlsx") {
    sheet.getRange("D2:D200").dataValidation = {
      rule: { type: "list", values: ["收入合同", "支出合同"] },
    };
    sheet.getRange("F2:F200").format.numberFormat = "#,##0.00";
  }

  notes.getRange("A1:C1").merge();
  notes.getRange("A1").values = [[template.title]];
  notes.getRange("A1:C1").format = {
    fill: colors.teal,
    font: { bold: true, color: "#FFFFFF", size: 14 },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  notes.getRange("A1:C1").format.rowHeight = 30;
  notes.getRange("A2:C2").merge();
  notes.getRange("A2").values = [["只填写“导入模板”页，空白行会自动忽略；带 * 字段为必填。导入前系统会先完整校验，校验失败不会写入任何数据。"]];
  notes.getRange("A2:C2").format = {
    fill: colors.note,
    font: { color: colors.muted },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: colors.line },
  };
  notes.getRange("A2:C2").format.rowHeight = 42;
  notes.getRange("A4:C4").values = [["字段", "必填", "填写要求"]];
  notes.getRange("A4:C4").format = {
    fill: colors.pale,
    font: { bold: true, color: colors.ink },
    horizontalAlignment: "center",
    borders: { preset: "all", style: "thin", color: colors.line },
  };
  notes.getRangeByIndexes(4, 0, template.fields.length, 3).values = template.fields;
  notes.getRangeByIndexes(4, 0, template.fields.length, 3).format = {
    font: { color: colors.ink },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: colors.line },
  };
  notes.getRange("A:A").format.columnWidth = 22;
  notes.getRange("B:B").format.columnWidth = 12;
  notes.getRange("C:C").format.columnWidth = 58;
  notes.getRangeByIndexes(4, 0, template.fields.length, 3).format.rowHeight = 30;
  notes.freezePanes.freezeRows(4);

  const previewMain = await workbook.render({ sheetName: template.sheetName, range: `A1:${String.fromCharCode(64 + template.headers.length)}8`, scale: 1, format: "png" });
  const previewNotes = await workbook.render({ sheetName: "填写说明", range: "A1:C10", scale: 1, format: "png" });
  await fs.writeFile(`${outputDir}/${template.file.replace(".xlsx", "-preview.png")}`, new Uint8Array(await previewMain.arrayBuffer()));
  await fs.writeFile(`${outputDir}/${template.file.replace(".xlsx", "-notes-preview.png")}`, new Uint8Array(await previewNotes.arrayBuffer()));

  const inspect = await workbook.inspect({ kind: "region", sheetId: template.sheetName, range: `A1:${String.fromCharCode(64 + template.headers.length)}5`, maxChars: 1800 });
  console.log(template.file, inspect.ndjson);
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(`${outputDir}/${template.file}`);
}

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(publicDir, { recursive: true });
for (const template of templates) {
  await buildTemplate(template);
  await fs.copyFile(`${outputDir}/${template.file}`, `${publicDir}/${template.file}`);
}
console.log(`wrote ${templates.length} templates to ${outputDir} and ${publicDir}`);
