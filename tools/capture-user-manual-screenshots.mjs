import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "docs", "assets", "manual-v3.0.56");
const BASE = "http://127.0.0.1:5173/";

async function waitReady(page) {
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await page.locator(".app-shell, .login-card").first().waitFor({ timeout: 15000 });
  await page.waitForTimeout(600);
}

async function gotoPage(page, name) {
  await page.goto(name ? `${BASE}?page=${name}` : BASE, { waitUntil: "domcontentloaded" });
  await waitReady(page);
}

async function selectIdentity(page, label) {
  const selector = page.locator(".identity-select");
  if (await selector.count()) {
    await selector.selectOption({ label }).catch(async () => {
      await selector.selectOption({ index: 0 });
    });
    await waitReady(page);
  }
}

async function screenshot(page, name) {
  await page.screenshot({
    path: path.join(OUT, `${name}.png`),
    fullPage: false,
    animations: "disabled",
  });
}

async function clickVisibleText(page, text) {
  const locator = page.getByText(text, { exact: false }).first();
  if (await locator.count()) {
    await locator.click({ timeout: 4000 }).catch(() => {});
    await waitReady(page);
  }
}

async function main() {
  await fs.rm(OUT, { recursive: true, force: true });
  await fs.mkdir(OUT, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1365, height: 768 },
    deviceScaleFactor: 1,
  });

  await gotoPage(page, "");
  await screenshot(page, "01-workbench");

  await gotoPage(page, "worklogs");
  await screenshot(page, "02-worklogs");
  await clickVisibleText(page, "＋ 新增工时");
  await screenshot(page, "03-worklog-form");

  await gotoPage(page, "approvals");
  await selectIdentity(page, "樊公海");
  await screenshot(page, "04-worklog-approvals");
  await clickVisibleText(page, "查看");
  await screenshot(page, "05-worklog-approval-detail");

  await gotoPage(page, "projects");
  await screenshot(page, "06-projects");
  await clickVisibleText(page, "＋ 新增项目");
  await screenshot(page, "07-project-form");
  await page.keyboard.press("Escape").catch(() => {});
  await gotoPage(page, "projects");
  await clickVisibleText(page, "室内乳胶漆喷涂机器人研发与应用");
  await screenshot(page, "08-project-detail");

  await gotoPage(page, "projectContracts");
  await screenshot(page, "09-contracts");
  await clickVisibleText(page, "＋ 新增合同");
  await screenshot(page, "10-contract-form");
  await page.keyboard.press("Escape").catch(() => {});
  await gotoPage(page, "projectContracts");
  await clickVisibleText(page, "导入测试合同");
  await screenshot(page, "11-contract-detail");

  await gotoPage(page, "projectReceipts");
  await screenshot(page, "12-receipts");
  await clickVisibleText(page, "＋ 新增收款");
  await screenshot(page, "13-receipt-form");

  await gotoPage(page, "projectPayments");
  await screenshot(page, "14-payments");
  await clickVisibleText(page, "＋ 新增付款");
  await screenshot(page, "15-payment-form");

  await gotoPage(page, "projectExpenses");
  await screenshot(page, "16-expenses");
  await clickVisibleText(page, "＋ 新增费用");
  await screenshot(page, "17-expense-form");

  await gotoPage(page, "projectBoard");
  await screenshot(page, "18-project-board");

  await gotoPage(page, "reports");
  await screenshot(page, "19-worklog-board");

  await gotoPage(page, "personnelCosts");
  await screenshot(page, "20-personnel-costs");

  await gotoPage(page, "integrations");
  await screenshot(page, "21-integrations");
  await clickVisibleText(page, "通知中心");
  await screenshot(page, "22-notification-center");

  await gotoPage(page, "adminPermissions");
  await screenshot(page, "23-admin-permissions");

  await gotoPage(page, "approvalPositions");
  await screenshot(page, "24-approval-positions");

  await gotoPage(page, "approvalWorkflows");
  await screenshot(page, "25-approval-workflows");

  await gotoPage(page, "configuration");
  await screenshot(page, "26-configuration");

  await browser.close();
  console.log(OUT);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
