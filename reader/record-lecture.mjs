import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import axe from "axe-core";
import { chromium } from "playwright-core";
import { register } from "./product-helpers.mjs";

const evidence = new URL("../docs/evidence/", import.meta.url);
const app = process.env.A11YRA_TEACHER_URL;

async function scan(page) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(axe.source);
  const violations = await page.evaluate(async () =>
    (await window.axe.run()).violations.map(({ id, nodes }) => ({ id, targets: nodes.map(({ target }) => target) })));
  assert.deepEqual(violations, [], page.url());
  return violations;
}

test("record the Stacks and Queues repair and offline reader evidence", { timeout: 120_000 }, async () => {
  assert.ok(app, "Run this through reader/run-browser-tests.mjs");
  const browser = await chromium.launch({
    channel: process.env.A11YRA_BROWSER_CHANNEL || (process.platform === "win32" ? "msedge" : undefined),
  });
  const temporary = await mkdtemp(join(tmpdir(), "a11yra-lecture-"));
  try {
    const page = await browser.newPage({ reducedMotion: "reduce" });
    const result = { environment: "local Vite and FastAPI", browser: browser.version(), axe: {} };
    await page.goto(app);
    await page.getByRole("heading", { level: 1 }).waitFor();
    result.axe.landing = await scan(page);
    await register(page, app);
    await page.goto(new URL("/upload", app).href);
    const input = page.getByLabel("Word document (required)");
    await input.waitFor();
    result.axe.upload = await scan(page);
    await input.setInputFiles(fileURLToPath(new URL("original-lecture.docx", evidence)));
    await page.getByRole("button", { name: "Upload document" }).click();
    result.originalScore = await page.getByText("2 of 6 checks passed", { exact: true }).textContent();
    const original = page.getByRole("list", { name: "Original document preview" });
    const originalLines = [
      "Document title: none (file name will be read instead)", "Language: not set",
      "Image: no description", "Link: click here",
    ];
    for (const line of originalLines) await original.getByText(line, { exact: true }).waitFor();
    result.originalPreviewFindings = originalLines;
    result.axe.originalAudit = await scan(page);

    for (const [check, field, value] of [
      ["title", "Document title", "Stacks and Queues"],
      ["language", "Language tag", "en-IN"],
      ["images", "Alt text", "Stacks remove the most recently added item first. Queues remove the earliest added item first."],
      ["links", "New link label", "Further reading on stacks and queues"],
    ]) {
      await page.locator(`#check-${check}`).click();
      await page.locator(`#findings-${check}`).getByRole("link", { name: /^Review fix/ }).click();
      await page.getByLabel(`${field} (required)`).fill(value);
      await page.getByRole("button", { name: "Apply fix" }).click();
      await page.getByRole("status").filter({ hasText: "Fix applied." }).waitFor();
      await page.getByRole("link", { name: "Back to audit" }).click();
    }
    await page.getByRole("link", { name: "Re-audit document" }).click();
    await page.getByRole("button", { name: "Run re-audit" }).click();
    result.repairedScore = await page.getByText("6 of 6 checks passed", { exact: true }).textContent();
    result.verifiedFixes = Number((await page.getByRole("heading", { name: /^Verified fixed/ }).textContent()).match(/\((\d+)\)/)[1]);
    assert.equal(result.verifiedFixes, 4);
    await page.getByRole("link", { name: "View repaired screen reader view" }).click();
    const repaired = page.getByRole("list", { name: "Repaired document preview" });
    await repaired.getByText("Document title: Stacks and Queues", { exact: true }).waitFor();
    for (const line of originalLines) assert.equal(await repaired.getByText(line, { exact: true }).count(), 0);
    await page.getByRole("button", { name: "Working copy" }).press("Tab");
    assert.equal(await repaired.evaluate((list) => document.activeElement === list), true);
    const top = await repaired.evaluate((list) => list.scrollTop);
    await page.keyboard.press("PageDown");
    await page.waitForFunction((previous) => document.activeElement.scrollTop > previous, top);
    await page.keyboard.press("Tab");
    assert.equal(await repaired.evaluate((list) => document.activeElement === list), false);
    result.previewKeyboard = { tabFocus: true, scroll: true, tabLeavesPreview: true };
    result.axe.repairedAudit = await scan(page);

    await page.getByRole("link", { name: "Export document" }).click();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download offline HTML" }).click();
    const html = join(temporary, "lecture.html");
    await (await download).saveAs(html);
    const offline = await browser.newPage({
      offline: true, viewport: { width: 640, height: 800 }, deviceScaleFactor: 2, reducedMotion: "reduce",
    });
    const requests = [];
    offline.on("request", (request) => {
      if (/^https?:/.test(request.url())) requests.push(request.url());
    });
    await offline.goto(pathToFileURL(html).href);
    const preset = offline.getByLabel("Reading preset");
    result.offline = await offline.evaluate(() => ({
      headings: document.querySelectorAll("article :is(h1,h2,h3,h4,h5,h6)").length,
      columnHeaderScopes: document.querySelectorAll('article th[scope="col"]').length,
      viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth, devicePixelRatio,
    }));
    assert.equal(result.offline.viewport, result.offline.scrollWidth);
    result.axe.offlineReader = await scan(offline);
    result.offline.presets = await preset.locator('option:not([value="custom"])').allTextContents();
    await preset.selectOption("low-vision");
    await offline.reload();
    assert.equal(await preset.inputValue(), "low-vision");
    result.offline.lowVision = await offline.locator("html").evaluate(({ dataset }) => ({
      textSize: dataset.size, spacing: dataset.spacing, theme: dataset.theme, motion: dataset.motion,
    }));
    await offline.getByLabel("Reading ruler").check();
    assert.equal(await offline.locator("#reading-ruler").isVisible(), true);
    const shortcuts = offline.getByRole("button", { name: "Keyboard shortcuts" });
    await shortcuts.press("Enter");
    await offline.getByRole("dialog").waitFor();
    await offline.keyboard.press("Escape");
    assert.equal(await shortcuts.evaluate((button) => document.activeElement === button), true);
    assert.deepEqual(requests, []);
    Object.assign(result.offline, { networkRequests: requests.length, persistedPreset: true, ruler: true, escapeReturnsFocus: true });
    await writeFile(new URL("live-results.json", evidence), JSON.stringify(result, null, 2) + "\n");
  } finally {
    await browser.close();
    await rm(temporary, { recursive: true, force: true });
  }
});
