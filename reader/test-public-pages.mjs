import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { test } from "node:test";
import axe from "axe-core";
import { chromium } from "playwright-core";
import { randomUUID } from "node:crypto";
import { register } from "./product-helpers.mjs";

const site = process.env.A11YRA_TEACHER_URL;
const screenshots = process.env.A11YRA_PUBLIC_SCREENSHOTS;
const baseline = process.env.A11YRA_SCREENSHOT_BASELINE === "1";
const navLabels = ["Engine", "Checks", "Reader", "Workspace"];
const footerLabels = ["Pricing", "Security & privacy", "Accessibility", "Privacy policy", "Terms", "Support", "Changelog", "Status"];
const pages = {
  product: "/", pricing: "/pricing", security: "/security", privacy: "/privacy",
  terms: "/terms", accessibility: "/accessibility", support: "/support", changelog: "/changelog",
  status: "/status", checks: "/checks", signup: "/account/signup?sample=1",
  signin: "/account/login?sample=1", forgot: "/account/forgot", reset: "/account/reset",
  verify: "/account/verify", invite: "/account/invite",
};

async function scan(page, width) {
  assert.equal(await page.locator("h1").count(), 1, page.url());
  assert.equal(await page.locator("html").getAttribute("lang"), "en", page.url());
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width, page.url());
  await page.evaluate(axe.source);
  const violations = await page.evaluate(async () =>
    (await window.axe.run()).violations.map(({ id, nodes }) => ({ id, targets: nodes.map((node) => node.target) })));
  assert.deepEqual(violations, [], `${page.url()} at ${width}px`);
}

test("public pages at desktop and 320 px", { timeout: 180_000, skip: !site }, async () => {
  const browser = await chromium.launch({
    channel: process.env.A11YRA_BROWSER_CHANNEL || (process.platform === "win32" ? "msedge" : undefined),
  });
  if (screenshots) await mkdir(screenshots, { recursive: true });
  try {
    const titles = new Set();
    for (const [name, path] of Object.entries(pages)) {
      const page = await browser.newPage({ reducedMotion: "reduce" });
      try {
        await page.goto(new URL(path, site).href);
        await page.locator("main h1").waitFor();
        if (name === "pricing") await page.locator("table caption").waitFor();
        if (name === "status") await page.getByRole("status").filter({ hasText: /passed/i }).waitFor();
        if (!baseline) {
          assert.deepEqual(await page.getByRole("navigation", { name: "Main", exact: true }).getByRole("link").allTextContents(), navLabels);
          assert.deepEqual(await page.getByRole("navigation", { name: "About A11yra" }).getByRole("link").allTextContents(), footerLabels);
        }
        await page.evaluate(() => document.fonts.ready);
        for (const width of [1280, 320]) {
          await page.setViewportSize({ width, height: 900 });
          if (screenshots) await page.screenshot({
            path: join(screenshots, `${name}-${width}.png`), fullPage: true, animations: "disabled",
          });
          if (!baseline) await scan(page, width);
        }
        if (!baseline) {
          const title = await page.title();
          assert.ok(title && !titles.has(title), `${path} needs a unique page title`);
          titles.add(title);
        }
      } finally {
        await page.close();
      }
    }
  } finally {
    await browser.close();
  }
});

test("sample signup opens one audit with the next step", { timeout: 60_000, skip: !site }, async () => {
  const browser = await chromium.launch({
    channel: process.env.A11YRA_BROWSER_CHANNEL || (process.platform === "win32" ? "msedge" : undefined),
  });
  try {
    const page = await browser.newPage({ reducedMotion: "reduce" });
    if (baseline) {
      await register(page, site);
      await page.getByRole("button", { name: "Audit the sample syllabus" }).click();
    } else {
      await page.goto(new URL("/account/login", site).href);
      const nav = page.getByRole("navigation", { name: "Main", exact: true });
      assert.deepEqual(await nav.getByRole("link").allTextContents(), navLabels);
      await nav.getByRole("link", { name: "Reader", exact: true }).press("Enter");
      await page.waitForURL("**/#reader");
      await page.waitForFunction(() => document.activeElement?.id === "reader");
      await page.getByRole("main").getByRole("link", { name: "Sign in", exact: true }).press("Enter");
      await page.waitForURL("**/account/login?next=%2Fupload");
      await page.goto(new URL("/account/signup?sample=1", site).href);
      await page.getByLabel("Email address (required)").fill(`sample-${randomUUID()}@example.test`);
      await page.getByLabel("Password (required)").fill("a test password 123");
      await page.getByRole("button", { name: "Create an account" }).press("Enter");
      await page.getByRole("heading", { name: "Document audit", exact: true }).waitFor();
      const findings = page.getByRole("tabpanel");
      await findings.getByText("Why it matters", { exact: true }).waitFor();
      await findings.getByRole("link", { name: "Review fix for Document properties", exact: true }).waitFor();
    }
    await page.getByText("2 of 6 checks passed", { exact: true }).waitFor();
    if (!baseline) {
      const profile = await (await page.request.get(new URL("/api/auth/me", site).href)).json();
      const documents = await (await page.request.get(new URL(`/api/workspaces/${profile.workspaces[0].id}/documents`, site).href)).json();
      assert.equal(documents.length, 1);
      const usage = await (await page.request.get(new URL(`/api/workspaces/${profile.workspaces[0].id}/usage`, site).href)).json();
      assert.deepEqual(Object.keys(usage.plan).sort(), planFields);
    }
    if (screenshots) await mkdir(screenshots, { recursive: true });
    for (const width of [1280, 320]) {
      await page.setViewportSize({ width, height: 900 });
      if (screenshots) await page.screenshot({ path: join(screenshots, `sample-audit-${width}.png`), fullPage: true, animations: "disabled" });
      if (!baseline) await scan(page, width);
    }
  } finally {
    await browser.close();
  }
});

const planFields = ["api_access", "documents_per_month", "history_days", "max_file_bytes", "name", "reader_branding", "seats"];

test("pricing uses the unchanged plan limits and support contact configuration", {
  timeout: 30_000, skip: !site || baseline,
}, async () => {
  const browser = await chromium.launch({
    channel: process.env.A11YRA_BROWSER_CHANNEL || (process.platform === "win32" ? "msedge" : undefined),
  });
  try {
    const page = await browser.newPage({ reducedMotion: "reduce" });
    await page.goto(new URL("/pricing", site).href);
    const table = page.getByRole("table", { name: "Compare plans" });
    await table.waitFor();
    const data = await (await page.request.get(new URL("/api/plans", site).href)).json();
    const plans = [data.plans.free, data.plans.educator, data.plans.institution];
    for (const plan of plans) assert.deepEqual(Object.keys(plan).sort(), planFields);
    for (const [name, values] of [
      [/^Documents per month/, plans.map((plan) => String(plan.documents_per_month))],
      [/^Maximum upload size/, plans.map((plan) => `${plan.max_file_bytes / 1_000_000} MB`)],
      [/^Workspace seats/, plans.map((plan) => String(plan.seats))],
      [/^Audit history/, plans.map((plan) => `Up to ${plan.history_days} days`)],
      [/^Price/, ["Free during the pilot", "Pricing set after the pilot", "Pricing set after the pilot"]],
    ]) {
      assert.deepEqual(await table.getByRole("row", { name }).getByRole("cell").allTextContents(), values);
    }
    assert.equal(await page.getByRole("link", { name: "Join the pilot" }).getAttribute("href"), "/account/signup");
    const email = process.env.A11YRA_TEST_SUPPORT_EMAIL;
    if (email === undefined) return;
    const pilot = page.getByRole("link", { name: "Request a pilot" });
    if (email) assert.equal(await pilot.getAttribute("href"), `mailto:${email}`);
    else assert.equal(await pilot.count(), 0);
    await page.goto(new URL("/support", site).href);
    await page.getByRole("heading", { name: "What to include in a report" }).waitFor();
    const mailto = page.locator('main a[href^="mailto:"]');
    if (email) assert.equal(await mailto.getAttribute("href"), `mailto:${email}`);
    else assert.equal(await mailto.count(), 0);
    const warning = page.getByText(/Development only/);
    assert.equal(await warning.count(), !email && process.env.A11YRA_TEST_PREVIEW !== "1" ? 1 : 0);
  } finally {
    await browser.close();
  }
});
