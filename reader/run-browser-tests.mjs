import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = process.env.A11YRA_PYTHON || join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const temp = await mkdtemp(join(tmpdir(), "a11yra-browser-"));
const apiPort = process.env.A11YRA_DEV_API_PORT || "8000";
const webPort = process.env.A11YRA_DEV_WEB_PORT || "5173";
const teacherUrl = `http://127.0.0.1:${webPort}`;
const env = {
  ...process.env,
  A11YRA_ENV: "dev",
  A11YRA_TEACHER_URL: teacherUrl,
  A11YRA_PUBLIC_URL: teacherUrl,
  A11YRA_CORS_ORIGINS: teacherUrl,
  A11YRA_IP_REQUESTS_PER_MINUTE: "1500",
  A11YRA_DATA_DIR: join(temp, "files"),
  A11YRA_PYTHON: python,
  DATABASE_URL: `sqlite:///${join(temp, "test.db").replaceAll("\\", "/")}`,
  SMTP_HOST: "",
  STRIPE_TEST_ENABLED: "0",
};
const services = [];

function launch(program, args, cwd, { quiet = false } = {}) {
  const child = spawn(program, args, { cwd, env, stdio: quiet ? "ignore" : "inherit", windowsHide: true });
  const done = new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", (code) => resolve(code));
  });
  done.catch(() => {});
  return { child, done };
}

async function waitFor(url) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const response = await fetch(url).catch(() => null);
    if (response?.ok) return;
    if (services.some(({ child }) => child.exitCode !== null)) throw new Error("An A11yra service exited early.");
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error(`A11yra did not become ready at ${url}`);
}

try {
  services.push(launch(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", apiPort, "--no-access-log"], join(root, "backend"), { quiet: true }));
  const viteMode = process.env.A11YRA_TEST_PREVIEW === "1" ? ["preview", "--strictPort"] : [];
  services.push(launch(process.execPath, ["node_modules/vite/bin/vite.js", ...viteMode, "--port", webPort], join(root, "frontend")));
  await waitFor(`http://127.0.0.1:${apiPort}/api/ready`);
  await waitFor(teacherUrl);
  const specs = process.argv.slice(2);
  const tests = specs.length ? specs : ["test-product.mjs", "test-teacher-ui.mjs", "test-reader.mjs", "test-public-pages.mjs"];
  process.exitCode = await launch(process.execPath, ["--test", "--test-concurrency=1", ...tests], join(root, "reader")).done;
} finally {
  for (const { child } of services) child.kill();
  await Promise.allSettled(services.map(({ done }) => done));
  if (dirname(resolve(temp)) === resolve(tmpdir())) await rm(temp, { recursive: true, force: true });
}
