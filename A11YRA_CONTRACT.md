# A11yra — Build Contract (v1)

Single source of truth for **Build Phase 1** (teacher engine) and **Build Phase 2** (learner reader/export).
If any other prompt, README or code disagrees with this file, **this file wins**. Do not rename anything defined here without updating this file first.

---

## 0. Rules for the coding agent (opencode)

1. Read this whole file before writing code. Re-read sections 1–3 before touching any API or shared type.
2. Never rename, reorder or retype anything in sections 2–3. Additive changes only, and record each in `docs/CHANGELOG-CONTRACT.md`.
3. Work in small milestones. After each: run tests, run the app, summarise in 3 lines, stop for my go-ahead.
4. Explain new concepts simply — I'm a 2nd-year B.Tech student learning full-stack. Give me one small exercise per milestone.
5. Deterministic logic only. No AI/ML calls. No network calls at runtime except frontend → own backend.
6. Never log document text. Never claim "WCAG compliant" anywhere in the UI or docs.
7. Phase 2 must not restructure Phase 1 code. It imports and extends it.

---

## 1. Repository layout (fixed)

```
a11yra/
├─ CONTRACT.md                  ← this file (copy here)
├─ backend/
│  ├─ app/
│  │  ├─ main.py                ← FastAPI app, CORS, router mount
│  │  ├─ api/routes.py          ← all endpoints (thin)
│  │  ├─ core/config.py         ← limits, paths, env
│  │  ├─ core/storage.py        ← temp session dirs, cleanup
│  │  ├─ models.py              ← Pydantic models == section 3
│  │  ├─ audit/                 ← one file per check + runner.py + score.py
│  │  │   ├─ title.py language.py headings.py images.py tables.py links.py
│  │  ├─ repair/                ← one function per fix type
│  │  ├─ export/docx_export.py  ← Phase 1
│  │  └─ export/html_export.py  ← Phase 2
│  ├─ tests/ (pytest) · fixtures/ (generated DOCX) · scripts/make_fixtures.py
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ api/client.ts          ← ONLY place that calls fetch
│  │  ├─ types/contract.ts      ← TS mirror of section 3 (hand-kept in sync)
│  │  ├─ styles/tokens.css      ← section 4 tokens, verbatim
│  │  ├─ styles/base.css        ← reset, typography, focus, utilities
│  │  ├─ components/            ← section 8
│  │  ├─ pages/                 ← Landing, Upload, Audit, Fix, Compare, Export
│  │  └─ hooks/useRovingFocus.ts useShortcuts.ts useReducedMotion.ts
│  └─ vite.config.ts            ← dev proxy /api → http://localhost:8000
└─ reader/                      ← Phase 2: reader template (vanilla HTML/CSS/JS) inlined into exports
   ├─ reader.html · reader.css · reader.js
```

Ports: backend `8000`, frontend `5173`. Frontend only uses relative `/api/...` URLs (Vite proxy in dev). Max upload 10 MB, `.docx` only, validate extension + MIME + ZIP signature (`PK`) + that `word/document.xml` exists.

---

## 2. API contract (fixed)

Base path `/api`. JSON, `snake_case`. Errors always: `{"error": {"code": "string", "message": "plain-language sentence"}}` with the right HTTP status.

| Method | Path | Body | Success response |
|---|---|---|---|
| POST | `/api/documents` | multipart `file` | `201 {document_id, filename, audit: Audit}` |
| GET | `/api/documents/{id}/audit` | – | `200 Audit` |
| POST | `/api/documents/{id}/fixes` | `{fixes: Fix[]}` | `200 {applied: [{finding_id, status}], skipped: [{finding_id, reason}]}` |
| POST | `/api/documents/{id}/reaudit` | – | `200 {audit: Audit, diff: AuditDiff}` |
| GET | `/api/documents/{id}/export/docx` | – | DOCX download (`Content-Disposition: attachment`) |
| GET | `/api/documents/{id}/export/html?offline=true\|false` | – | HTML download (Phase 2) |
| DELETE | `/api/documents/{id}` | – | `204` |
| GET | `/api/health` | – | `{"status":"ok"}` |

Error codes: `invalid_file_type`, `file_too_large`, `corrupt_docx`, `document_not_found`, `fix_not_supported`, `fix_invalid`, `export_failed`.

Rules: a fix sets its finding to `fixed_unverified`. **Only** `/reaudit` may produce `verified_fixed`. Documents expire and are deleted after 60 minutes or on DELETE.

---

## 3. Data model (fixed enums and shapes)

```ts
type CheckId = "title" | "language" | "headings" | "images" | "tables" | "links";
type CheckResult = "passed" | "issues" | "needs_review" | "not_evaluated";
type Severity = "high" | "medium" | "low";
type Confidence = "high" | "medium" | "low";
type FindingStatus = "open" | "fixed_unverified" | "verified_fixed" | "needs_review";
type FixType = "set_title" | "set_language" | "set_alt_text" | "set_link_text" | "set_table_header";

interface Finding {
  id: string;                 // stable, e.g. "img-002", "link-001"
  check_id: CheckId;
  location: string;           // human text: "Image 2, after paragraph 14"
  locator: Record<string, number | string>;  // machine: {image_index:2} | {table_index:0} | {paragraph_index:14, link_index:1}
  evidence: string;           // what was detected
  barrier: string;            // plain-language impact, not "this violates WCAG"
  suggestion: string;
  severity: Severity;
  confidence: Confidence;
  status: FindingStatus;
  fixable: "teacher_approved" | "recommendation_only";
  preview?: string;           // short text/image-reference for the UI (never full doc text)
}
interface Check {
  id: CheckId; label: string; result: CheckResult;
  summary: string; finding_ids: string[];
}
interface Audit {
  audit_id: string; document_id: string; created_at: string; // ISO 8601
  checks: Check[]; findings: Finding[];
  progress: { passed: number; evaluated: number; percent: number | null }; // null if evaluated == 0
}
interface Fix {
  finding_id: string; type: FixType;
  payload: { title?: string; lang?: string; alt_text?: string; decorative?: boolean; new_text?: string; };
}
interface AuditDiff {
  verified_fixed: string[]; still_open: string[]; new_findings: string[]; needs_review: string[];
  progress_before: Audit["progress"]; progress_after: Audit["progress"];
}
```

`progress.percent` = `passed / evaluated * 100` (rounded), excluding `not_evaluated`. UI always shows "N of M checks passed". Label it **"Audit progress"**, never "accessibility score".

Severity badge text and colour come from section 4.4; colour is never the only signal.

---

## 4. Design system

### 4.1 Palette (derived from the supplied swatch image)

The image labels were partly garbled, so these hex values are **estimated by eye from the swatches**. Keep them only in `tokens.css`; if you have exact values, change them there and re-run the contrast table.

| Token | Hex | Role |
|---|---|---|
| `--navy-950` | `#0A1128` | deepest background, primary text on light |
| `--navy-800` | `#1E3D5C` | cards on dark, headings on light |
| `--steel-700` | `#3C5F7E` | secondary text on light, button fill (derived darker step of steel) |
| `--steel-600` | `#4F7494` | borders, large UI, icons (not small text) |
| `--sky-300` | `#8FB3CF` | **primary accent** on dark, focus ring on dark |
| `--mist-100` | `#CADDEB` | light surfaces, text on dark |
| `--mist-50` | `#F3F8FC` | page background (light) |
| `--white` | `#FFFFFF` | text on dark fills |

**"Pop" trio** (use these three for emphasis): `--sky-300` (accents, active states, hero glow), `--mist-100` (highlights, selected rows, soft panels), `--steel-600` (borders, illustrations, secondary buttons' outlines).

Status colours (the palette is all blue, so status needs its own hues, always paired with an icon and a text label):

| Token | Dark-surface | Light-surface |
|---|---|---|
| `--ok` | `#6FD3A0` | `#1B7F4B` |
| `--warn` | `#F2C14E` | `#8A5A00` |
| `--bad` | `#FF8A80` | `#B3261E` |

### 4.2 Verified contrast (computed with the WCAG formula)

| Foreground on background | Ratio | Use |
|---|---|---|
| white on navy-950 | 18.7 | body text on dark |
| mist-100 on navy-950 | 13.4 | secondary text on dark |
| sky-300 on navy-950 | 8.5 | accent text/links/focus on dark |
| sky-300 on navy-800 | 5.1 | accent text on cards (AA) |
| white on navy-800 | 11.2 | text on cards |
| navy-950 on sky-300 | 8.5 | primary button (dark text) |
| navy-950 on mist-50 | 17.5 | body text on light |
| navy-800 on mist-50 | 10.5 | headings on light |
| steel-700 on mist-50 | 6.3 | secondary text on light |
| white on steel-700 | 6.7 | secondary button fill |
| ok/warn/bad (dark variants) on navy-950 | 10.2 / 11.1 / 8.2 | status on dark |
| ok/warn/bad (light variants) on mist-50 | 4.7 / 5.5 / 6.1 | status on light |

**Forbidden combinations:** steel-600 for text under 18.66px bold/24px (only 3.8 on navy-950, 4.6 on mist-50); sky-300 on steel-600 (2.2); sky-300 text on light backgrounds.
Non-text UI (borders, icons, focus ring) needs ≥ 3:1 against its neighbours.

### 4.3 `tokens.css` (paste verbatim)

```css
:root {
  --navy-950:#0A1128; --navy-800:#1E3D5C; --steel-700:#3C5F7E; --steel-600:#4F7494;
  --sky-300:#8FB3CF; --mist-100:#CADDEB; --mist-50:#F3F8FC; --white:#FFFFFF;

  --ok-d:#6FD3A0; --warn-d:#F2C14E; --bad-d:#FF8A80;
  --ok-l:#1B7F4B; --warn-l:#8A5A00; --bad-l:#B3261E;

  /* semantic: light surface (default for content & forms) */
  --bg: var(--mist-50); --surface: var(--white); --surface-2: var(--mist-100);
  --text: var(--navy-950); --text-muted: var(--steel-700); --heading: var(--navy-800);
  --border: var(--steel-600); --accent: var(--navy-800); --on-accent: var(--white);
  --focus: var(--navy-950); --ok: var(--ok-l); --warn: var(--warn-l); --bad: var(--bad-l);

  --font-body: "Atkinson Hyperlegible", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-display: "Fraunces", Georgia, "Times New Roman", serif;
  --font-mono: ui-monospace, "Cascadia Code", Consolas, monospace;

  --fs-0: clamp(1rem, .96rem + .2vw, 1.125rem);       /* body 16–18px */
  --fs-1: clamp(1.125rem, 1.05rem + .4vw, 1.3rem);
  --fs-2: clamp(1.35rem, 1.2rem + .8vw, 1.7rem);
  --fs-3: clamp(1.7rem, 1.4rem + 1.5vw, 2.4rem);
  --fs-4: clamp(2.2rem, 1.6rem + 3vw, 3.75rem);       /* hero */
  --lh-body: 1.6; --lh-tight: 1.2; --measure: 68ch;

  --s-1:.25rem; --s-2:.5rem; --s-3:.75rem; --s-4:1rem; --s-5:1.5rem; --s-6:2rem; --s-7:3rem; --s-8:5rem;
  --radius-s:10px; --radius-m:16px; --radius-pill:999px;
  --shadow: 0 10px 30px rgba(10,17,40,.12);
  --ring: 0 0 0 3px var(--bg), 0 0 0 6px var(--focus);
  --target: 44px;                                      /* min hit area */
  --dur: 180ms; --ease: cubic-bezier(.2,.7,.2,1);
}
/* dark surface: hero, learner "night" theme, nav */
.theme-dark {
  --bg: var(--navy-950); --surface: var(--navy-800); --surface-2:#16304a;
  --text: var(--white); --text-muted: var(--mist-100); --heading: var(--white);
  --border: var(--steel-600); --accent: var(--sky-300); --on-accent: var(--navy-950);
  --focus: var(--sky-300); --ok: var(--ok-d); --warn: var(--warn-d); --bad: var(--bad-d);
}
@media (prefers-reduced-motion: reduce) { :root { --dur: 0ms; } *{animation:none!important;scroll-behavior:auto!important} }
@media (prefers-contrast: more) { :root { --border: var(--navy-950); } .theme-dark{ --border: var(--mist-100); } }
```

### 4.4 Status and severity badges (never colour-only)

| Item | Icon + label | Style |
|---|---|---|
| passed | ✓ "Passed" | `--ok` text, tinted bg |
| issues | ▲ "Needs attention" | `--bad` |
| needs_review | ? "Needs your review" | `--warn` |
| not_evaluated | – "Not checked" | `--text-muted` |
| severity high / medium / low | ●●● / ●● / ● + word | outline pills |
| status fixed_unverified | ⟳ "Fixed — not yet verified" | `--warn` |
| status verified_fixed | ✓ "Verified fixed" | `--ok` |

Use inline SVG icons with `aria-hidden="true"` next to visible text.

---

## 5. Typography rules

- Fonts: **Atkinson Hyperlegible** (body/UI, designed for low-vision legibility) and **Fraunces** (display headings only, ≥ `--fs-2`). Self-host WOFF2 in `frontend/public/fonts` (reader must work offline); `font-display: swap`; fall back to the system stack.
- Body `--fs-0`, line-height 1.6, paragraphs max `--measure` (68ch), left-aligned, **never justified**.
- Headings: one `<h1>` per page, no skipped levels, `--lh-tight`, weight 600–700. Hero uses `--fs-4`.
- Never set text below 16px. Never use all-caps for sentences; small caps/uppercase labels only ≤ 3 words, letter-spacing .04em.
- Use `rem`, never `px`, for font sizes. Layout must survive 200% zoom and 400% reflow at 320 px width without horizontal scroll.
- Links are underlined always, `text-underline-offset: .2em`, distinct visited colour is optional.
- Plain-language microcopy: short sentences, active voice, say what happened and what to do next.

---

## 6. Layout rules

- Mobile-first. Breakpoints: 40em, 64em, 80em. Content container max 72rem, side gutter `clamp(1rem, 4vw, 2rem)`.
- Spacing only from `--s-*` tokens. Use an 8-pt rhythm, generous whitespace, one primary action per view.
- Landmarks on every page: skip link → `<header>` → `<nav aria-label="Main">` → `<main id="main">` → `<footer>`. Exactly one `<main>`.
- Skip link is the first focusable element and becomes visible on focus.
- Visual order = DOM order (no `tabindex > 0`, no CSS `order` that breaks reading order).
- Audit page: two columns at ≥ 64em (left: check list as a vertical list; right: selected check's findings). One column below.
- Fix page: finding on the left, input form on the right, sticky "Apply fix" bar at the bottom on mobile.
- Cards: `--surface`, 1px `--border`, radius `--radius-m`, padding `--s-5`. Max 3 levels of nesting. No tables for layout.
- Interactive targets ≥ 44×44 px with ≥ 8 px between neighbours.
- Content never relies on hover: every hover affordance has a focus and tap equivalent.
- Respect `prefers-color-scheme` only for the learner reader; the teacher app is light surface + dark hero, with no automatic switching.

---

## 7. Keyboard navigation contract (all pages)

**Universal**
- **Tab / Shift+Tab**: logical DOM order, all interactive things reachable, no traps.
- **Enter**: activates links and buttons, submits forms. **Space**: buttons, checkboxes.
- **Esc**: closes any dialog, popover or menu and returns focus to the control that opened it.
- Focus ring: always visible, `box-shadow: var(--ring)`, ≥ 3:1 contrast, never `outline: none` without replacement. Use `:focus-visible`.
- After route change or dialog open, move focus to the page `<h1>` (`tabindex="-1"`) or the dialog heading; announce status changes through one global `aria-live="polite"` region.
- Provide a **"?" shortcuts dialog** (`?` key, or the "Keyboard help" button in the footer). Any single-character shortcut is **off by default except inside the reader**, and can be turned off in Reader settings (WCAG 2.1.4).

**Arrow-key composite widgets (roving tabindex via `useRovingFocus`)**
| Widget | Keys |
|---|---|
| Check list (audit page, vertical listbox-style list of buttons) | ↑/↓ move, Home/End jump, Enter select, the group is one Tab stop |
| Tabs (e.g. Before / After) | ←/→ move, Home/End, Enter or auto-activate on focus |
| Finding cards list | ↑/↓ move between cards, Enter opens the fix panel |
| Radio groups (Decorative vs Informative; theme picker) | arrows move and select, Tab leaves the group |
| Menu button / dropdown (language picker) | Enter/Space/↓ opens, ↑/↓ move, Esc closes, type-ahead optional |
| Stepper (Upload → Audit → Fix → Re-audit → Export) | non-interactive; `aria-current="step"` |
| Contents panel (reader) | ↑/↓ between sections, → expands, ← collapses, Enter jumps and moves focus to that heading |

**Reader-only shortcuts** (active only while focus is inside the reader; list in the "?" dialog)
`[` previous section · `]` next section · `c` focus Contents · `+` / `-` text size · `r` toggle read-along · `Space` pause/resume read-along when the read-along control has focus.

Rules: never override browser/screen-reader keys (no Ctrl/Alt combos); no custom key may be the only way to do something.

---

## 8. Components (each in its own file, each keyboard- and screen-reader-complete)

`SkipLink`, `AppHeader`, `Stepper`, `FileDropzone` (a real `<input type="file">` behind the drop area; drop optional, button + keyboard primary), `ProgressMeter` (`role="progressbar"` with `aria-valuenow`/`valuetext` "4 of 6 checks passed"; empty state text when `percent === null`), `CheckList`, `CheckCard`, `FindingCard`, `Badge`, `SeverityPill`, `FixForm` (one variant per `FixType`, labels above inputs, error text linked via `aria-describedby`), `ImagePreview` (alt="" because the surrounding text describes it; the teacher writes the description in the field), `BeforeAfterPanel` (two columns on desktop, tabs on mobile), `ExportCard`, `Toast` (live region, ≥ 8 s or persistent, dismissible), `Dialog` (native `<dialog>` + focus return), `ShortcutsDialog`, `EmptyState`, `ErrorState`.

Forms: every input has a visible `<label>`; required fields marked in text ("required"), not colour; validate on submit; error summary at top gets focus.

---

## 9. Creative and interactive direction (must not harm accessibility)

**Concept: "clarity coming into focus."** The product turns a messy, blurry document into a sharp, navigable one. Use that single idea consistently.

1. **Hero (dark theme)**: navy-950 background with a soft radial glow of `--steel-600` → transparent (like the swatch image), headline in Fraunces, tagline "Accessibility, reimagined." Right side: an inline-SVG "document" card whose blurred lines sharpen as a CSS animation plays once (a CSS `filter: blur()` → 0 over ~1.2 s); under `prefers-reduced-motion`, it renders already sharp. One primary CTA "Check a document" (sky-300 fill, navy text) and one secondary "See the student view".
2. **Stacked "pill" cards**: echo the supplied palette image, with rounded-pill shaped check cards stacked vertically in tone steps (navy-800 → steel-700 → mist-100). Each shows icon + check name + result badge. On focus/hover, the card lifts 4 px and the border shifts to `--sky-300`.
3. **Progress ring/bar**: animated fill on re-audit (≤ 600 ms), always paired with the text "N of M checks passed". A passed check gets a small "tick draws itself" SVG animation.
4. **Before/After**: a draggable **and keyboard-operable** slider is NOT required; use a simple two-pane "Before | After" with `<ins>`/`<del>`-style markers and text labels. Simpler and more accessible.
5. **Micro-interactions**: button press scale .98, card lift, focus ring grow, toast slide-in. Duration `--dur`, ease `--ease`. No parallax, no auto-playing motion longer than 5 s, nothing flashing (≤ 3 flashes/s), motion never carries essential meaning.
6. **Reader contrast**: the reader is calmer and warmer than the teacher app — wide margins, large type, mist-50 page with navy text by default, a sky-300 "you are here" marker in the Contents panel.
7. **Illustrations**: simple inline SVG shapes only (documents, magnifier, tick, headphone). Decorative SVGs get `aria-hidden="true" focusable="false"`.
8. **Do not add**: confetti, sounds, auto-playing video, carousels, animated backgrounds that run continuously, quizzes, points, accounts, tracking.

---

## 10. Screens and their jobs

| Route | Page | Core elements |
|---|---|---|
| `/` | Landing | hero, "How it works" (4 steps), teacher vs student explainer, honest limits ("checks six common issues; not a full WCAG audit") |
| `/upload` | Upload | stepper, dropzone, format/size rules, privacy note ("deleted after 60 min") |
| `/audit/:id` | Audit | `ProgressMeter`, `CheckList`, findings per check, severity/confidence badges, empty state when nothing evaluated |
| `/fix/:id/:findingId` | Fix | finding detail (evidence, barrier, suggestion), the right `FixForm`, "Apply" → status becomes "Fixed — not yet verified" |
| `/compare/:id` | Re-audit | `BeforeAfterPanel`, diff lists (Verified fixed / Still open / Needs review / New), progress before→after |
| `/export/:id` | Export | DOCX (primary), HTML, Offline HTML (Phase 2), plain list of limitations per format |
| (exported file) | Reader | see section 11 |

Heading-structure findings are **recommendation only**: show a clear "Fix this in Word" instruction, no Apply button.

---

## 11. Learner reader contract (Phase 2; all in `reader/`, vanilla JS, zero network calls)

- Output is one HTML file; offline variant inlines CSS, JS, fonts (base64) and images (base64). Online variant may reference nothing external either — both variants must work with the network off. They differ only in whether assets are inlined or sibling files.
- Structure: skip link → header (title, language) → `<nav aria-label="Contents">` → `<main>` with the converted article → `<aside aria-label="Reading settings">`.
- `<html lang>` and `<title>` come from the repaired document.
- Contents panel is built from real `h1–h6`; every heading gets a stable `id`; selecting an item moves focus to the heading.
- Reading settings (persist in `localStorage`, wrapped in try/catch): text size (A−, A, A+, 100–200 %), line spacing, theme (Light / Night / High-contrast), font (Default / Dyslexia-friendly stack), reduced-motion respected.
- Read-along: `speechSynthesis`; Play / Pause / Stop; highlights the current block using a background **and** a left border (not colour alone); unsupported → visible message and hides controls; never autoplays.
- Images: `<figure>` with the alt text as `alt` and an optional visible "Image description" disclosure; decorative images get `alt=""`.
- Tables: `<caption>` if known, `<th scope="col">` for header cells, horizontal scroll container with `tabindex="0"` and an accessible name.
- Links: keep descriptive text; external ones get "(opens in new tab)" visually hidden text if `target=_blank`.
- Print stylesheet: hide controls, black on white.

---

## 12. Definition of done (per milestone and overall)

Frontend/UI
- [ ] Every page passes keyboard-only use start to finish; focus never lost or trapped.
- [ ] All text meets contrast table in 4.2; no forbidden combinations.
- [ ] 200 % zoom and 320 px width have no loss of content or horizontal scroll.
- [ ] No information conveyed by colour alone.
- [ ] `prefers-reduced-motion` and `prefers-contrast` honoured.
- [ ] axe-core run on every page and on the exported reader shows 0 serious/critical violations; known remaining items are listed in the README.
- [ ] Manual pass: NVDA (or the browser accessibility tree) on the upload → audit → fix → export path.

Backend/engine
- [ ] Every API response matches section 3 exactly (add contract tests that validate against Pydantic models).
- [ ] Fixture "broken.docx" → audited → fixed → re-audited produces `verified_fixed` for the fixed findings and keeps the others.
- [ ] Re-opening every exported DOCX with python-docx succeeds.
- [ ] No document text in logs; temp folders cleaned.

Honesty
- [ ] UI and README say "audit progress", list what is not checked, and avoid compliance claims.

---

## 13. Ready-to-paste kickoff prompt for opencode

```
Read CONTRACT.md fully before doing anything. It is the single source of truth; do not rename or retype anything in sections 1–4 without recording it in docs/CHANGELOG-CONTRACT.md.

You are building A11yra in two phases. Today we do BUILD PHASE 1 only (teacher engine: upload, six-check audit, teacher-approved fixes, re-audit, repaired DOCX export, and the teacher UI). Phase 2 (HTML export + learner reader) comes later and must be able to import our Phase 1 modules without restructuring.

Backend: FastAPI + python-docx + lxml, no database, temp session folders. Frontend: React + Vite + TypeScript with the design tokens in CONTRACT.md section 4.3 pasted verbatim into src/styles/tokens.css. Follow the layout (section 6), typography (section 5), keyboard contract (section 7), components (section 8), creative direction (section 9) and screens (section 10) exactly. Visual quality matters: the product should feel calm, modern, friendly and trustworthy, using the navy/steel/sky/mist palette, with the stacked pill-card motif and the "blur to sharp" hero. Accessibility of our own UI is non-negotiable.

Work milestone by milestone: (a) repo setup + upload/validation + shared types, (b) fixtures + title/language checks, (c) headings/links/images/tables checks, (d) findings, score, audit endpoint, (e) design system, landing and upload pages, (f) audit dashboard, (g) repair functions + fix UI, (h) re-audit + compare page, (i) DOCX export, cleanup, README. After each milestone: run pytest and the frontend build, summarise in three lines, give me one small exercise to try myself, and stop for my go-ahead.

Start by creating the folder structure from section 1 and writing backend/app/models.py and frontend/src/types/contract.ts from section 3, then show me both files before continuing.
```
