import { readFileSync } from "node:fs";

const css = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const extract = (text) => Object.fromEntries(Array.from(
  text.matchAll(/--([\w-]+):\s*(#[\da-f]{6}|#[\da-f]{3})\s*;/gi), (match) => [match[1], match[2]],
));
const luminance = (hex) => {
  const color = hex.length === 4 ? [...hex.slice(1)].map((digit) => digit.repeat(2)).join("") : hex.slice(1);
  return [0.2126, 0.7152, 0.0722].reduce((sum, weight, index) => {
    const channel = parseInt(color.slice(index * 2, index * 2 + 2), 16) / 255;
    return sum + weight * (channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  }, 0);
};

const results = [];
function check(theme, tokens, foreground, background, minimum) {
  const levels = [luminance(tokens[foreground]), luminance(tokens[background])].sort((a, b) => b - a);
  const ratio = (levels[0] + 0.05) / (levels[1] + 0.05);
  results.push({ theme, foreground, background, ratio, minimum });
}

const teacherCss = css("../src/styles/tokens.css");
const teacherLight = extract(teacherCss.split("}")[0]);
const teacherDark = extract(teacherCss.match(/:root\[data-theme="dark"\]\s*\{([^}]+)\}/)[1]);
for (const [theme, teacher] of [["light", teacherLight], ["dark", { ...teacherLight, ...teacherDark }]]) {
  for (const surface of ["paper", "surface", "mist", "wash"]) {
    for (const text of ["ink", "ink-muted", "steel-deep"]) check(`Teacher ${theme}`, teacher, text, surface, 4.5);
    check(`Teacher ${theme}`, teacher, "steel-deep", surface, 3);
  }
  for (const surface of ["surface", "paper", "wash", "mist"]) {
    check(`Teacher ${theme}`, teacher, "line-strong", surface, 3);
    check(`Teacher ${theme}`, teacher, "steel", surface, 3);
  }
  check(`Teacher ${theme}`, teacher, "steel-deep", "mist", 7);
  check(`Teacher ${theme}`, teacher, "steel-deep", "surface", 7);
  check(`Teacher ${theme}`, teacher, "surface", "steel", 4.5);
  check(`Teacher ${theme}`, teacher, "surface", "steel-deep", 4.5);
  check(`Teacher ${theme}`, teacher, "steel", "mist", 3);
  for (const status of ["success", "warning", "error"]) {
    const border = status === "warning" ? "status-warning-border" : `status-${status}-ink`;
    const fill = `status-${status}-fill`;
    check(`Teacher ${theme}`, teacher, `status-${status}-ink`, fill, 4.5);
    for (const surface of [fill, "paper", "surface", "mist"]) check(`Teacher ${theme}`, teacher, border, surface, 3);
  }
  for (const surface of ["paper", "surface", "mist", "wash"]) {
    check(`Teacher ${theme}`, teacher, "focus-ring", surface, 3);
  }
}

const readerCss = css("../../reader/reader.css");
const readerDefault = extract(readerCss.split("}")[0]);
for (const theme of ["light", "dark", "contrast"]) {
  const override = readerCss.match(new RegExp(`:root\\[data-theme="${theme}"\\]\\s*\\{([^}]+)\\}`));
  const tokens = { ...readerDefault, ...extract(override?.[1] ?? "") };
  for (const surface of ["paper", "surface", "selected"]) {
    for (const text of ["ink", "muted", "accent"]) check(`Reader ${theme}`, tokens, text, surface, 4.5);
    check(`Reader ${theme}`, tokens, "line-strong", surface, 3);
  }
}

console.log("| Theme | Foreground | Background | Ratio | Minimum |");
console.log("| --- | --- | --- | ---: | ---: |");
for (const { theme, foreground, background, ratio, minimum } of results) {
  console.log(`| ${theme} | ${foreground} | ${background} | ${ratio.toFixed(2)}:1 | ${minimum}:1 |`);
}
if (results.some(({ ratio, minimum }) => ratio < minimum)) process.exitCode = 1;
