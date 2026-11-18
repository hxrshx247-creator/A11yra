import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { after, before, test } from "node:test";
import axe from "axe-core";
import { chromium } from "playwright-core";
import { register } from "./product-helpers.mjs";

const project = fileURLToPath(new URL("../", import.meta.url));
const python = process.env.A11YRA_PYTHON || join(project, ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const teacherUrl = process.env.A11YRA_TEACHER_URL;
const screenshots = process.env.A11YRA_SCREENSHOTS;
const description = "Attendance doubled from 12 students on Monday to 24 on Thursday.";
let browser;
let temporary;

function runPython(args) {
  const result = spawnSync(python, args, { cwd: join(project, "backend"), encoding: "utf8" });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr);
}

before(async () => {
  temporary = await mkdtemp(join(tmpdir(), "a11yra-reader-test-"));
  if (screenshots) await mkdir(screenshots, { recursive: true });
  const bundle = join(temporary, "reader.zip");
  runPython(["-m", "scripts.export_html", "--reader", "fixtures/clean.docx", join(temporary, "offline.html")]);
  runPython(["-m", "scripts.export_html", "--bundle", "fixtures/clean.docx", bundle]);
  await mkdir(join(temporary, "bundle"));
  runPython(["-m", "zipfile", "-e", bundle, join(temporary, "bundle")]);
  browser = await chromium.launch({ channel: process.env.A11YRA_BROWSER_CHANNEL || (process.platform === "win32" ? "msedge" : undefined) });
});

after(async () => {
  await browser?.close();
  if (temporary) await rm(temporary, { recursive: true, force: true });
});

async function checkAxe(page) {
  await page.evaluate(axe.source);
  const violations = await page.evaluate(async () => (await window.axe.run()).violations.map(
    ({ id, impact, nodes }) => ({ id, impact, targets: nodes.map((node) => node.target) }),
  ));
  assert.deepEqual(violations, []);
}

async function openOffline(context, filename) {
  const page = await context.newPage();
  page.setDefaultTimeout(6000);
  const remote = [];
  page.on("request", (request) => {
    if (/^https?:/.test(request.url())) remote.push(request.url());
  });
  await page.goto(pathToFileURL(filename).href);
  return { page, remote };
}

for (const name of ["offline.html", join("bundle", "index.html")]) {
  test(`opens ${name} offline with keyboard navigation and saved settings`, async () => {
    const context = await browser.newContext({
      offline: true, viewport: { width: 320, height: 800 }, reducedMotion: "reduce",
    });
    try {
      const { page, remote } = await openOffline(context, join(temporary, name));
      await page.waitForFunction(() => document.documentElement.dataset.size === "100");
      assert.equal(await page.locator("html").getAttribute("data-motion"), "off");
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 320);
      assert.equal(await page.locator("img").evaluate((image) => image.complete && image.naturalWidth > 0), true);
      assert.equal(await page.getByRole("columnheader", { name: "Day" }).getAttribute("scope"), "col");
      await page.keyboard.press("Tab");
      assert.equal(await page.evaluate(() => document.activeElement.textContent), "Skip to content");
      await page.keyboard.press("Enter");
      assert.equal(await page.evaluate(() => document.activeElement.id), "main");
      await page.keyboard.press("c");
      assert.equal(await page.locator("#contents").getAttribute("open"), "");
      await page.keyboard.press("Tab");
      await page.keyboard.press("Enter");
      assert.equal(await page.evaluate(() => document.activeElement.id), "section-1");
      assert.equal(await page.locator("#contents-list a").getAttribute("aria-current"), "location");

      const shortcuts = page.getByRole("button", { name: "Keyboard shortcuts", exact: true });
      await shortcuts.press("Enter");
      await page.getByRole("dialog", { name: "Keyboard shortcuts" }).waitFor();
      await checkAxe(page);
      await page.keyboard.press("Escape");
      await page.getByRole("dialog", { name: "Keyboard shortcuts" }).waitFor({ state: "hidden" });
      assert.equal(await shortcuts.evaluate((node) => node === document.activeElement), true);
      for (const value of ["full", "off"]) {
        await page.getByLabel("Motion", { exact: true }).selectOption(value);
        assert.equal(await page.locator("html").getAttribute("data-motion"), value);
      }
      await page.getByLabel("Text size").selectOption("200");
      await page.getByLabel("Line spacing").selectOption("wide");
      await page.getByLabel("Theme").selectOption("dark");
      await page.getByLabel("Font", { exact: true }).selectOption("spaced");
      await page.getByLabel("Reading ruler").check();
      const rulerPosition = page.getByRole("slider", { name: "Ruler position" });
      await rulerPosition.press("End");
      assert.equal(await rulerPosition.inputValue(), "100");
      assert.equal(await page.locator("#reading-ruler").evaluate((node) =>
        node.style.getPropertyValue("--ruler-position")), "100%");
      const movement = await page.locator("main").evaluate((main) => {
        const ruler = main.querySelector("#reading-ruler");
        const center = main.getBoundingClientRect().top + main.offsetHeight / 2;
        const move = (clientY, pointerType = "mouse") =>
          main.dispatchEvent(new PointerEvent("pointermove", { clientY, pointerType }));
        move(center);
        const before = ruler.getBoundingClientRect();
        move(center + 2);
        const after = ruler.getBoundingClientRect();
        move(center + 20, "touch");
        return {
          distance: after.top - before.top,
          height: after.height,
          fontSize: parseFloat(getComputedStyle(ruler).fontSize),
          touchDistance: ruler.getBoundingClientRect().top - after.top,
        };
      });
      assert.ok(Math.abs(movement.distance - 2) < .1, "Ruler follows small pointer movements without percentage jumps");
      assert.ok(Math.abs(movement.height - movement.fontSize * 2.4) < 1, "Ruler matches the homepage band height");
      assert.equal(movement.touchDistance, 0);
      await rulerPosition.press("Home");
      assert.equal(await page.locator("#reading-ruler").evaluate((node) =>
        node.style.getPropertyValue("--ruler-position")), "0%");
      await page.getByLabel("Enable single-key shortcuts").uncheck();
      await page.reload();
      assert.equal(await page.locator("html").getAttribute("data-motion"), "off");
      assert.equal(await page.getByLabel("Reading ruler").isChecked(), true);
      assert.equal(await page.locator("#reading-ruler").isVisible(), true);
      assert.equal(await page.getByLabel("Text size").inputValue(), "200");
      assert.equal(await page.getByLabel("Line spacing").inputValue(), "wide");
      assert.equal(await page.getByLabel("Theme").inputValue(), "dark");
      assert.equal(await page.getByLabel("Font", { exact: true }).inputValue(), "spaced");
      assert.equal(await page.getByLabel("Enable single-key shortcuts").isChecked(), false);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 320);
      await checkAxe(page);
      await page.getByLabel("Theme").selectOption("contrast");
      await checkAxe(page);
      await page.getByRole("button", { name: "Reset settings" }).press("Enter");
      assert.equal(await page.getByLabel("Text size").inputValue(), "100");
      await checkAxe(page);
      if (screenshots && name === "offline.html") {
        for (const width of [360, 390, 768, 1024, 1280, 1536]) {
          await page.setViewportSize({ width, height: 900 });
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
          if ([360, 768, 1280].includes(width)) {
            await page.screenshot({ path: join(screenshots, `reader-${width}.png`), fullPage: true });
          }
        }
      }
      assert.deepEqual(remote, []);
    } finally {
      await context.close();
    }
  });
}

test("reading presets apply bundled settings and persist offline", async () => {
  const context = await browser.newContext({ offline: true });
  try {
    const { page, remote } = await openOffline(context, join(temporary, "offline.html"));
    await page.getByLabel("Reading preset").selectOption("low-vision");
    assert.equal(await page.getByLabel("Text size").inputValue(), "175");
    assert.equal(await page.getByLabel("Line spacing").inputValue(), "wide");
    assert.equal(await page.getByLabel("Theme").inputValue(), "contrast");
    await page.reload();
    assert.equal(await page.getByLabel("Reading preset").inputValue(), "low-vision");
    assert.equal(await page.locator("html").getAttribute("data-preset"), "low-vision");
    await page.getByLabel("Font", { exact: true }).selectOption("spaced");
    assert.equal(await page.getByLabel("Reading preset").inputValue(), "custom");
    await page.getByLabel("Reading preset").selectOption("focus");
    assert.equal(await page.getByLabel("Reading ruler").isChecked(), true);
    assert.equal(await page.locator("html").getAttribute("data-preset"), "focus");
    assert.deepEqual(remote, []);
  } finally { await context.close(); }
});

test("read-along plays, pauses, advances and stops with a local voice", async () => {
  const context = await browser.newContext({ offline: true });
  await context.addInitScript(() => {
    window.readerSpeechTest = {};
    Object.defineProperty(window, "SpeechSynthesisUtterance", {
      value: class { constructor(text) { this.text = text; } },
    });
    Object.defineProperty(window, "speechSynthesis", { value: {
      getVoices: () => [{ lang: "en-US", localService: false }, { lang: "en-GB", localService: true }],
      speak: (utterance) => { window.readerSpeechTest.current = utterance; },
      pause: () => {},
      resume: () => {},
      cancel: () => {},
    } });
  });
  try {
    const { page } = await openOffline(context, join(temporary, "offline.html"));
    await page.getByRole("button", { name: "Play", exact: true }).press("Enter");
    assert.equal(await page.locator("article .is-reading").textContent(), "Study group handout");
    assert.equal(await page.evaluate(() => window.readerSpeechTest.current.voice.localService), true);
    await page.getByRole("button", { name: "Pause", exact: true }).press("Enter");
    assert.equal(await page.locator("#speech-status").textContent(), "Read-along paused.");
    await page.getByRole("button", { name: "Resume", exact: true }).press("Enter");
    await page.evaluate(() => window.readerSpeechTest.current.onend());
    assert.match(await page.locator("article .is-reading").textContent(), /chart compares attendance/);
    await page.getByRole("button", { name: "Stop", exact: true }).press("Enter");
    assert.equal(await page.locator("article .is-reading").count(), 0);
  } finally {
    await context.close();
  }
});

test("reading settings work when storage and speech are unavailable", async () => {
  const context = await browser.newContext({ offline: true });
  await context.addInitScript(() => {
    Object.defineProperty(window, "speechSynthesis", { value: undefined });
    Object.defineProperty(window, "localStorage", { get() { throw new Error("Storage blocked"); } });
  });
  try {
    const { page } = await openOffline(context, join(temporary, "offline.html"));
    await page.getByLabel("Text size").selectOption("150");
    assert.equal(await page.locator("html").getAttribute("data-size"), "150");
    assert.equal(await page.getByRole("button", { name: "Play", exact: true }).count(), 0);
    assert.equal(await page.locator("#speech-status").textContent(), "Read-along is unavailable in this browser.");
  } finally {
    await context.close();
  }
});

test("teacher verifies the syllabus repair and a student reaches its description offline", {
  skip: !teacherUrl,
  timeout: 45_000,
}, async () => {
  const context = await browser.newContext();
  const teacher = await context.newPage();
  teacher.setDefaultTimeout(8000);
  const exported = join(temporary, "teacher-export.html");
  try {
    await register(teacher, teacherUrl);
    await teacher.goto(new URL("/upload", teacherUrl).href);
    await teacher.getByLabel("Word document (required)").setInputFiles(join(project, "backend/fixtures/syllabus.docx"));
    await teacher.getByRole("button", { name: "Upload document" }).press("Enter");
    await teacher.getByText("5 of 6 checks passed", { exact: true }).waitFor();
    await teacher.getByRole("link", { name: /Review fix for Image/ }).press("Enter");
    await teacher.getByLabel("Alt text (required)").fill(description);
    await teacher.getByRole("button", { name: "Apply fix" }).press("Enter");
    await teacher.getByRole("status").filter({ hasText: "Fix applied." }).waitFor();
    await teacher.getByRole("link", { name: "Back to audit" }).press("Enter");
    await teacher.getByRole("link", { name: "Re-audit document" }).press("Enter");
    await teacher.getByRole("button", { name: "Run re-audit" }).press("Enter");
    await teacher.getByRole("heading", { name: "Verified fixed (1)" }).waitFor();
    await teacher.getByText("6 of 6 checks passed", { exact: true }).waitFor();
    const documentId = teacher.url().split("/").at(-1);
    await teacher.getByRole("link", { name: "Continue to export" }).press("Enter");
    const downloadPromise = teacher.waitForEvent("download");
    await teacher.getByRole("button", { name: "Download offline HTML" }).press("Enter");
    const download = await downloadPromise;
    assert.equal(download.suggestedFilename(), "a11yra-reader.html");
    await download.saveAs(exported);
    assert.equal((await teacher.request.get(new URL(`/api/documents/${documentId}/audit`, teacherUrl).href)).status(), 200);
  } finally {
    await context.close();
  }

  const student = await browser.newContext({ offline: true, viewport: { width: 320, height: 800 } });
  try {
    const { page, remote } = await openOffline(student, exported);
    await page.keyboard.press("Tab");
    await page.keyboard.press("Enter");
    await page.keyboard.press("c");
    await page.keyboard.press("Tab");
    await page.keyboard.press("ArrowDown");
    assert.equal(await page.evaluate(() => document.activeElement.textContent), "Attendance example");
    await page.keyboard.press("Enter");
    assert.equal(await page.evaluate(() => document.activeElement.id), "section-2");
    await page.keyboard.press("Tab");
    assert.equal(await page.evaluate(() => document.activeElement.textContent), "Image description");
    await page.keyboard.press("Enter");
    await page.locator("details[open] p").filter({ hasText: description }).waitFor();
    assert.match(await page.locator("main").ariaSnapshot(), /heading "Attendance example"/);
    await checkAxe(page);
    assert.deepEqual(remote, []);
  } finally {
    await student.close();
  }
});
