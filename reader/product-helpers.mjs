import { randomUUID } from "node:crypto";

export async function register(page, app, { scan } = {}) {
  const email = `teacher-${randomUUID()}@example.test`;
  const password = "a test password 123";
  await page.goto(new URL("/account/signup", app).href);
  await page.getByLabel("Email address (required)").waitFor();
  if (scan) await scan(page);
  await page.getByLabel("Email address (required)").fill(email);
  await page.getByLabel("Password (required)").fill(password);
  await page.getByRole("button", { name: "Create an account" }).click();
  await page.getByText("If this email can be registered", { exact: false }).waitFor();
  await page.getByRole("navigation", { name: "Account options" }).getByRole("link", { name: "Sign in", exact: true }).click();
  await finishSignIn(page, { email, password }, scan);
  return { email, password };
}

export async function signIn(page, app, credentials) {
  await page.goto(new URL("/account/login", app).href);
  await finishSignIn(page, credentials);
}

async function finishSignIn(page, { email, password }, scan) {
  await page.getByRole("heading", { name: "Sign in", exact: true }).waitFor();
  if (scan) await scan(page);
  await page.getByLabel("Email address (required)").fill(email);
  await page.getByLabel("Password (required)").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("heading", { name: "Documents", exact: true }).waitFor();
}
