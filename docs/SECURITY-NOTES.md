# Security notes

## Build dependencies

The frontend pins the reviewed `@ryotsu/picomatch@4.0.7-a` fork through npm overrides to address CVE-2026-112366 in Vite's glob matcher. All upstream picomatch releases through 4.0.7 are affected, and the advisory currently lists no patched upstream release. The lockfile records the exact tarball integrity. Remove the override when an upstream release fixes the advisory and passes the glob regression check.

Run `node frontend/scripts/check-glob-security.mjs` after a clean frontend install to check the affected repeated wildcard patterns and ordinary build globs. The check isolates hostile matching in a subprocess with a deadline and also runs in CI. [GitHub advisory](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) · [Patched fork source](https://github.com/ryotsu-kankichi/secured-picomatch)

## Published readers

Published learners receive an HTML snapshot built from a DOCX fragment. The BeautifulSoup allow-list removes active elements and attributes, checks link schemes, and accepts base64 raster image URLs only when the file signature matches an allowed MIME type. Markup supplied as Word text or alt text stays escaped and readable. The HTTP Content Security Policy allows inline CSS and JavaScript only when they match the bundled reader assets' hashes. Published readers use the teacher application's origin. A separate reader origin remains a defense-in-depth option.
