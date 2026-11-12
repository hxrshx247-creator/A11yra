import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { test } from "node:test";
import axe from "axe-core";
import { chromium } from "playwright-core";
import { register } from "./product-helpers.mjs";

const app = process.env.A11YRA_TEACHER_URL || "http://127.0.0.1:5173";
const evidence = process.env.A11YRA_EVIDENCE;
const results = [];

async function scan(page) {
  await page.evaluate(axe.source);
  const violations = await page.evaluate(async () => (await window.axe.run()).violations.map(
    ({ id, impact, nodes }) => ({ id, impact, targets: nodes.map((node) => node.target) }),
  ));
  assert.deepEqual(violations, [], page.url());
  const route = new URL(page.url()).pathname.replace(/^\/r\/[^/]+$/, "/r/{token}")
    .replace(/^\/history\/[^/]+$/, "/history/{id}");
  results.push({ route, violations });
  await page.setViewportSize({ width: 320, height: 850 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 320, page.url());
  await page.setViewportSize({ width: 1280, height: 850 });
}

test("signup, four verified repairs, public reader, workspace and public pages", { timeout: 120_000 }, async () => {
  const browser = await chromium.launch({
    channel: process.env.A11YRA_BROWSER_CHANNEL || (process.platform === "win32" ? "msedge" : undefined),
  });
  try {
    const page = await browser.newPage({ reducedMotion: "reduce", viewport: { width: 1280, height: 850 } });
    page.setDefaultTimeout(9000);
    await register(page, app, { scan });
    await scan(page);
    await page.getByRole("button", { name: "Audit the sample syllabus" }).press("Enter");
    await page.getByText("2 of 6 checks passed", { exact: true }).waitFor();
    const documentId = page.url().split("/").at(-1);
    const base = `/api/documents/${documentId}`;
    for (const [check, label, value] of [
      ["title", "Document title (required)", "Study Group Syllabus"],
      ["language", "Language tag (required)", "en-IN"],
      ["images", "Alt text (required)", "Attendance doubled from 12 to 24 students."],
      ["links", "New link label (required)", "Weekly study group schedule"],
    ]) {
      await page.locator(`#check-${check}`).press("Enter");
      await page.getByRole("link", { name: /^Review fix/ }).press("Enter");
      await page.getByLabel(label).fill(value);
      await page.getByRole("button", { name: "Apply fix" }).press("Enter");
      await page.getByRole("status").filter({ hasText: "Fix applied." }).waitFor();
      await page.getByRole("link", { name: "Back to audit" }).press("Enter");
    }
    await page.getByRole("link", { name: "Re-audit document" }).press("Enter");
    await page.getByRole("button", { name: "Run re-audit" }).press("Enter");
    await page.getByRole("heading", { name: "Verified fixed (4)" }).waitFor();
    await page.getByText("6 of 6 checks passed", { exact: true }).waitFor();
    await page.getByRole("link", { name: "View repaired screen reader view" }).press("Enter");
    await page.getByRole("heading", { name: "Screen reader view" }).waitFor();
    await page.getByRole("button", { name: "Repaired" }).waitFor();
    assert.doesNotMatch(await page.locator(".reader-preview-list").innerText(), /Image: no description|Link: click here|Document title: none|Language: not set/);
    await scan(page);
    await page.getByRole("link", { name: "Export document" }).press("Enter");
    await page.getByRole("button", { name: "Publish reader link" }).click();
    const link = page.getByRole("link", { name: "Open published reader (new tab)" });
    await link.waitFor();
    const student = await browser.newPage({ reducedMotion: "reduce" });
    const opened = await student.goto(await link.getAttribute("href"));
    assert.equal(opened.headers()["cache-control"], "private, no-store");
    assert.match(opened.headers()["content-security-policy"], /script-src 'sha256-/);
    await student.keyboard.press("Tab");
    assert.equal(await student.evaluate(() => document.activeElement.textContent.trim()), "Skip to content");
    await student.keyboard.press("Enter");
    assert.equal(await student.evaluate(() => document.activeElement.id), "main");
    await student.getByText("Report a problem").waitFor();
    const background = () => student.locator("html").evaluate((root) => getComputedStyle(root).backgroundColor);
    const beforeTheme = await background();
    await student.getByLabel("Theme", { exact: true }).selectOption("dark");
    assert.equal(await student.locator("html").getAttribute("data-theme"), "dark");
    assert.notEqual(await background(), beforeTheme);
    await student.getByLabel("Theme", { exact: true }).selectOption("light");
    await student.getByLabel("Reading ruler").check();
    await student.getByRole("slider", { name: "Ruler position" }).press("End");
    assert.equal(await student.locator("#reading-ruler").evaluate((node) =>
      node.style.getPropertyValue("--ruler-position")), "100%");
    await scan(student);
    await page.getByRole("button", { name: "Revoke link" }).click();
    await page.getByText("Reader link revoked.").waitFor();
    const revoked = await student.reload();
    assert.equal(revoked.status(), 404);
    assert.equal(revoked.headers()["cache-control"], "private, no-store");
    await student.close();
    assert.equal((await page.request.get(new URL(`${base}/audit`, app).href)).status(), 200);
    const views = {
      [`/history/${documentId}`]: "Audit versions",
      "/workspace/dashboard": "Documents by open findings",
      "/workspace/activity": "Workspace activity",
      "/workspace/members": "Workspace members",
      "/workspace/keys": "API access is available",
      "/account/settings": "Delete my account and data",
      "/account/forgot": "Send",
      "/account/verify": "Open the link from your email",
      "/account/reset": "Open the link from your email",
      "/account/invite": "Open the link from your email",
      "/pricing": "Compare plans",
      "/status": "Readiness check: passed",
      "/checks": "Review with a person",
      "/security": "Read the full privacy policy",
      "/accessibility": "Report an accessibility problem",
      "/terms": "Use A11yra to review",
      "/privacy": "What we store",
      "/support": "What to include in a report",
      "/changelog": "0.3 Accounts, workspaces and published links",
    };
    for (const [path, text] of Object.entries(views)) {
      await page.goto(new URL(path, app).href);
      if (path === "/account/forgot") await page.getByLabel("Email address (required)").waitFor();
      else await page.getByText(text, { exact: false }).first().waitFor();
      await scan(page);
      if (evidence && path === "/workspace/activity") {
        await mkdir(evidence, { recursive: true });
        await page.screenshot({ path: join(evidence, "activity.png"), fullPage: true, animations: "disabled" });
      }
    }
    if (evidence) await writeFile(join(evidence, "axe-phase3.json"), JSON.stringify(results, null, 2) + "\n");
  } finally {
    await browser.close();
  }
});
