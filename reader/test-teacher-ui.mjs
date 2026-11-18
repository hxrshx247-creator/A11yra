import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, test } from "node:test";
import axe from "axe-core";
import { chromium } from "playwright-core";
import { register } from "./product-helpers.mjs";

const app = process.env.A11YRA_TEACHER_URL || "http://127.0.0.1:5173/";
const screenshots = process.env.A11YRA_SCREENSHOTS;
const fixture = (name) => fileURLToPath(new URL(`../backend/fixtures/${name}.docx`, import.meta.url));
const widths = [360, 390, 768, 1024, 1280, 1536];
const missingId = "00000000-0000-0000-0000-000000000000";
let browser;

before(async () => {
  if (screenshots) await mkdir(screenshots, { recursive: true });
  browser = await chromium.launch({ channel: process.env.A11YRA_BROWSER_CHANNEL || (process.platform === "win32" ? "msedge" : undefined) });
});
after(async () => browser?.close());

async function scan(page) {
  await page.evaluate(() => Promise.all(document.getAnimations()
    .filter((animation) => animation.playState === "running" && animation.effect?.getTiming().iterations !== Infinity)
    .map((animation) => animation.finished.catch(() => undefined))));
  await page.evaluate(axe.source);
  const violations = await page.evaluate(async () => (await window.axe.run()).violations.map(
    ({ id, impact, nodes }) => ({ id, impact, targets: nodes.map((node) => node.target) }),
  ));
  assert.deepEqual(violations, [], page.url());
}

async function checkLayout(page, name) {
  await page.evaluate(() => document.fonts.ready);
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width, `${name} at ${width}`);
    if (screenshots && [360, 768, 1280].includes(width)) {
      await page.screenshot({ path: join(screenshots, `${name}-${width}.png`), fullPage: true, animations: "disabled" });
    }
  }
  await page.setViewportSize({ width: 360, height: 900 });
  const larger = await page.addStyleTag({ content: "html { font-size: 200%; }" });
  const layout = await page.evaluate(() => ({
    width: document.documentElement.scrollWidth,
    overflow: [...document.querySelectorAll("main *")].filter((node) => node.getBoundingClientRect().right > 360)
      .slice(0, 12).map((node) => node.tagName + "." + node.className),
  }));
  assert.equal(layout.width, 360, `${name} with 200% text (${layout.overflow.join(", ")})`);
  await larger.evaluate((style) => style.remove());
  await page.setViewportSize({ width: 1280, height: 900 });
}

async function upload(page, name, activate) {
  await page.goto(new URL("/upload", app).href);
  await page.getByLabel("Word document (required)").setInputFiles(fixture(name));
  await activate(page.getByRole("button", { name: "Upload document" }));
  await page.getByRole("progressbar", { name: "Audit progress" }).waitFor();
}

async function reAudit(page, activate) {
  await activate(page.getByRole("link", { name: "Re-audit document", exact: true }));
  await activate(page.getByRole("button", { name: "Run re-audit" })).catch(async (reason) => {
    throw new Error(`${page.url()}: ${await page.locator("main").innerText()}`, { cause: reason });
  });
  await page.getByRole("heading", { name: "Re-audit results" }).waitFor();
}

async function save(page, button, activate, filename) {
  const pending = page.waitForEvent("download");
  await activate(button);
  const download = await pending;
  assert.equal(download.suggestedFilename(), filename);
  assert.equal(await download.failure(), null);
  await page.getByRole("status").filter({ hasText: `Download started: ${filename}.` }).waitFor();
}

test("teacher flow by keyboard and mouse preserves all five repairs", { timeout: 120_000 }, async () => {
  for (const method of ["keyboard", "mouse"]) {
    const page = await browser.newPage({ reducedMotion: "reduce" });
    page.setDefaultTimeout(8000);
    const activate = (target) => method === "keyboard" ? target.press("Enter") : target.click();
    try {
      await page.goto(app);
      if (method === "keyboard") {
        await scan(page);
        await checkLayout(page, "landing");
        await page.keyboard.press("Tab");
        assert.equal(await page.evaluate(() => document.activeElement.textContent), "Skip to main content");
        await page.keyboard.press("Enter");
        assert.equal(await page.evaluate(() => document.activeElement.id), "main");
      }
      await activate(page.getByRole("main").getByRole("link", { name: "Sign in", exact: true }));
      await page.getByRole("heading", { name: "Sign in", exact: true }).waitFor();
      await page.goto(new URL("/upload?source=workspace#main", app).href);
      await page.waitForURL((url) => url.pathname === "/account/login");
      assert.equal(new URL(page.url()).searchParams.get("next"), "/upload?source=workspace#main");
      await page.getByRole("heading", { name: "Sign in", exact: true }).waitFor();
      // Each input method gets its own account and request budget.
      await register(page, app);
      await page.goto(new URL("/upload", app).href);
      await page.getByLabel("Word document (required)").waitFor();
      if (method === "keyboard") {
        await scan(page);
        await checkLayout(page, "upload");
      }
      await page.getByLabel("Word document (required)").setInputFiles(fixture("broken"));
      await page.locator("#selected-file").filter({ hasText: "broken.docx" }).waitFor();
      await activate(page.getByRole("button", { name: "Upload document" }));
      await page.getByText("0 of 6 checks passed", { exact: true }).waitFor();
      if (method === "keyboard") {
        await scan(page);
        await checkLayout(page, "audit");
        await page.getByRole("tab", { selected: true }).press("ArrowDown");
        assert.match(await page.getByRole("tab", { selected: true }).getAttribute("id"), /language/);
        await page.getByRole("tab", { selected: true }).press("Home");
      }
      for (const [check, label, value] of [
        ["title", "Document title (required)", "Study group handout"],
        ["language", "Language tag (required)", "en-IN"],
        ["images", "Alt text (required)", "Attendance doubled from 12 to 24 students."],
        ["tables", "", ""],
        ["links", "New link label (required)", "Weekly study group schedule"],
      ]) {
        const tab = page.locator(`#check-${check}`);
        await activate(tab);
        const panel = page.getByRole("tabpanel").and(page.locator(`#findings-${check}`));
        await activate(panel.getByRole("link", { name: /^Review fix/ }));
        await page.getByRole("button", { name: "Apply fix" }).waitFor();
        if (method === "keyboard") {
          await scan(page);
          if (check === "images") await checkLayout(page, "fix");
          if (check === "language") {
            await page.getByLabel(label).fill("invalid_tag");
            await activate(page.getByRole("button", { name: "Apply fix" }));
            await page.locator("#repair-error").waitFor();
            assert.equal(await page.locator("#repair-error").evaluate((node) => node === document.activeElement), true);
            await scan(page);
          }
        }
        if (label) await page.getByLabel(label).fill(value);
        else if (method === "keyboard") await page.getByRole("checkbox", { name: /Mark the first row/ }).press("Space");
        else await page.getByRole("checkbox", { name: /Mark the first row/ }).click();
        await activate(page.getByRole("button", { name: "Apply fix" }));
        await page.getByRole("status").filter({ hasText: "Fix applied." }).waitFor().catch(async (cause) => {
          throw new Error(`${method} ${check} repair at ${page.url()}: ${await page.locator("#repair-error").textContent().catch(() => "no form error")}`, { cause });
        });
        await activate(page.getByRole("link", { name: "Back to audit" }));
        const findings = page.getByRole("tabpanel");
        await findings.getByText("Fixed, awaiting verification", { exact: true }).waitFor();
        assert.equal(await findings.getAttribute("aria-labelledby"), `check-${check}`);
      }
      await reAudit(page, activate);
      await page.getByRole("heading", { name: "Verified fixed (5)" }).waitFor();
      await page.getByText("5 of 6 checks passed", { exact: true }).waitFor();
      if (method === "keyboard") {
        await scan(page);
        await checkLayout(page, "compare");
        const glyphs = await page.locator(".compare-card .badge svg").evaluateAll(
          (icons) => icons.map((icon) => icon.innerHTML),
        );
        assert.equal(new Set(glyphs).size, 4);
        if (screenshots) {
          const monochrome = await page.addStyleTag({ content: "html { filter: grayscale(1); }" });
          await page.screenshot({ path: join(screenshots, "compare-greyscale.png"), fullPage: true });
          await monochrome.evaluate((style) => style.remove());
        }
      }
      await activate(page.getByRole("link", { name: "Continue to export" }));
      await page.getByRole("button", { name: "Download DOCX" }).waitFor();
      if (method === "keyboard") {
        await scan(page);
        await checkLayout(page, "export");
        await save(page, page.getByRole("button", { name: "Download DOCX" }), activate, "a11yra-repaired.docx");
        await save(page, page.getByRole("button", { name: "Download offline HTML" }), activate, "a11yra-reader.html");
        await save(page, page.getByRole("button", { name: "Download HTML ZIP" }), activate, "a11yra-reader.zip");
      } else {
        await save(page, page.getByRole("button", { name: "Download offline HTML" }), activate, "a11yra-reader.html");
      }
      await scan(page);
    } finally { await page.close(); }
  }
});

test("motion preferences, dialog focus, loading, error, ZIP, and deletion", { timeout: 90_000 }, async () => {
  const page = await browser.newPage({ colorScheme: "light", reducedMotion: "reduce" });
  page.setDefaultTimeout(8000);
  try {
    await page.goto(app);
    assert.equal(await page.locator("html").getAttribute("data-motion"), "off");
    const settingsButton = page.getByRole("button", { name: "Settings" });
    await settingsButton.press("Enter");
    const dialog = page.getByRole("dialog", { name: "Settings" });
    await dialog.waitFor();
    await scan(page);
    for (const [label, value] of [["Motion on", "full"], ["Motion off", "off"]]) {
      await dialog.getByRole("radio", { name: label }).check();
      assert.equal(await page.locator("html").getAttribute("data-motion"), value);
    }
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "hidden" });
    assert.equal(await settingsButton.evaluate((node) => node === document.activeElement), true);
    await page.reload();
    assert.equal(await page.locator("html").getAttribute("data-motion"), "off");
    await page.emulateMedia({ forcedColors: "active" });
    const theme = page.getByRole("switch", { name: "Dark mode" });
    await theme.press("Space");
    assert.equal(await theme.getAttribute("aria-checked"), "true");
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    await page.reload();
    assert.equal(await theme.getAttribute("aria-checked"), "true");
    await page.emulateMedia({ forcedColors: "none" });
    await scan(page);

    const help = page.getByRole("button", { name: "Keyboard help", exact: true });
    await help.click();
    await page.getByRole("dialog", { name: "Keyboard help" }).waitFor();
    await scan(page);
    await page.keyboard.press("Escape");
    assert.equal(await help.evaluate((node) => node === document.activeElement), true);

    await register(page, app);
    let release;
    const waiting = new Promise((resolve) => { release = resolve; });
    await page.route(`**/api/documents/${missingId}/audit`, async (route) => {
      await waiting;
      await route.continue();
    });
    await page.goto(new URL(`/audit/${missingId}`, app).href);
    await page.getByRole("status").filter({ hasText: "Loading audit…" }).waitFor();
    try { await scan(page); } finally { release(); }
    await page.getByRole("status").filter({ hasText: "This document could not be found" }).waitFor();
    await page.unroute(`**/api/documents/${missingId}/audit`);
    await scan(page);
    for (const path of [`/fix/${missingId}/title-missing`, `/compare/${missingId}`, `/export/${missingId}`]) {
      await page.goto(new URL(path, app).href);
      await page.getByRole("status").filter({ hasText: "This document could not be found" }).waitFor().catch(async (reason) => {
        throw new Error(`${path}: ${await page.locator("main").innerText()}`, { cause: reason });
      });
      await scan(page);
    }

    const click = (target) => target.click();
    await page.goto(new URL("/upload", app).href);
    const invalid = await page.evaluateHandle(() => {
      const transfer = new DataTransfer();
      transfer.items.add(new File(["Text"], "notes.txt", { type: "text/plain" }));
      return transfer;
    });
    await page.locator(".drop-zone").dispatchEvent("drop", { dataTransfer: invalid });
    await page.getByRole("status").filter({ hasText: "Choose a Word document ending in .docx" }).waitFor();
    await scan(page);
    await page.getByLabel("Word document (required)").setInputFiles({
      name: "too-big.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      buffer: Buffer.alloc(10_000_001),
    });
    await page.getByRole("status").filter({ hasText: "This file exceeds 10 MB" }).waitFor();

    const bytes = Array.from(await readFile(fixture("clean")));
    const word = await page.evaluateHandle((buffer) => {
      const transfer = new DataTransfer();
      transfer.items.add(new File([new Uint8Array(buffer)], "clean.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }));
      return transfer;
    }, bytes);
    await page.locator(".drop-zone").dispatchEvent("drop", { dataTransfer: word });
    await page.locator("#selected-file").filter({ hasText: "clean.docx" }).waitFor();
    let sendUpload;
    const uploadHold = new Promise((resolve) => { sendUpload = resolve; });
    await page.route("**/api/documents", async (route) => {
      await uploadHold;
      await route.continue();
    }, { times: 1 });
    await click(page.getByRole("button", { name: "Upload document" }));
    try {
      await page.getByRole("status").filter({ hasText: "Uploading and checking your document…" }).waitFor();
      assert.equal(await page.locator(".upload-track").isVisible(), true);
      await scan(page);
    } finally { sendUpload(); }
    await page.getByText("No findings for this check.").waitFor().catch(async (reason) => {
      throw new Error(`${page.url()}: ${await page.locator("main").innerText()}`, { cause: reason });
    });
    await scan(page);
    await reAudit(page, click);
    await click(page.getByRole("link", { name: "Continue to export" }));
    await save(page, page.getByRole("button", { name: "Download HTML ZIP" }), click, "a11yra-reader.zip");

    await upload(page, "syllabus", click);
    await reAudit(page, click);
    await click(page.getByRole("link", { name: "Continue to export" }));
    const deleteSummary = page.getByText("Delete this document", { exact: true });
    await deleteSummary.press("Enter");
    await page.getByRole("button", { name: "Delete my document now" }).press("Escape");
    assert.equal(await deleteSummary.evaluate((node) => document.activeElement === node), true);
    await deleteSummary.click();
    await page.getByRole("checkbox", { name: /I confirm permanent deletion/ }).check();
    await page.getByRole("button", { name: "Delete my document now" }).click();
    await page.getByRole("status").filter({ hasText: "The upload has been deleted." }).waitFor();
  } finally { await page.close(); }
});
