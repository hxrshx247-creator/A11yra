import { execFileSync } from "node:child_process";

// Run hostile patterns in a subprocess so a vulnerable matcher cannot hang CI.
execFileSync(process.execPath, ["--input-type=module", "--eval", `
  import assert from "node:assert/strict";
  import picomatch from "picomatch";

  for (const pattern of ["+(*)", "+(*a)", "*(*)", "*(*a)"]) {
    assert.equal(picomatch.isMatch("a".repeat(48) + "/!", pattern), false, pattern);
    assert.equal(picomatch.isMatch("aaaa", pattern), true, pattern);
  }

  for (const [pattern, matching, excluded] of [
    ["**/*.{ts,tsx}", "src/pages/Landing.tsx", "src/styles/base.css"],
    ["**/node_modules/**", "frontend/node_modules/vite/index.js", "frontend/src/main.tsx"],
    ["**/*.@(png|jpg)", "docs/evidence/reader.png", "docs/evidence/report.pdf"],
  ]) {
    assert.equal(picomatch.isMatch(matching, pattern), true, pattern);
    assert.equal(picomatch.isMatch(excluded, pattern), false, pattern);
  }
`], {
  cwd: new URL("../", import.meta.url),
  timeout: 3000,
  stdio: "pipe",
});

console.log("Glob security and build-pattern compatibility checks passed.");
