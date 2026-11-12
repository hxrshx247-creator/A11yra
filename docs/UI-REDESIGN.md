# A11yra UI redesign

## Implementation

| Files | Change |
| --- | --- |
| `frontend/index.html`, `public/fonts/`, `styles/tokens.css` | Preload the Latin WOFF2 files and apply the saved motion choice before paint. Self-host Latin and Latin Extended subsets with the font licenses. |
| `styles/base.css`, `styles/layout.css`, `styles/audit.css` | Split typography, focus, shell, page layouts, and audit treatments. Add reduced-motion, motion-off, increased-contrast, and forced-colour rules. |
| `main.tsx`, `AppShell.tsx`, `Stepper.tsx` | Shared header and footer with a numbered desktop stepper and a compact mobile disclosure. Keep pathname navigation. |
| `Icon.tsx`, `StatusBadge.tsx`, `Button.tsx`, `Dialog.tsx` | Reusable controls, labelled status icons, and native dialogs with focus return. |
| `usePreferences.tsx`, `SettingsDialog.tsx` | Three motion choices with local persistence, an operating-system default, and status announcements. |
| `CubicPattern.tsx`, `Landing.tsx` | A light hero and restrained isometric artwork, with the six checks and three workflow steps in plain language. |
| `Upload.tsx` | Drop zone around the native file input, file name and size, validation, and an indeterminate processing indicator. |
| `AuditDashboard.tsx`, `CheckList.tsx`, `FindingCard.tsx` | Status badges, selected check rows, finding hierarchy, and a clear review action. |
| `FixPage.tsx`, `FixForm.tsx` | Consistent field borders, icon-led messages, and a direct re-audit link after applying a fix. |
| `ComparePage.tsx`, `BeforeAfterPanel.tsx` | Compare counts and a text delta with status badges for each finding group. |
| `ExportPage.tsx`, `detailsKeyboard.ts` | Separate Word and learner formats with rules, add export-complete feedback, and return focus when Escape closes a disclosure. |
| `reader/reader.html`, `reader.css`, `reader.js` | Shared visual language for the exported learner reader, local motion choice, and a keyboard-shortcuts dialog. Keep existing themes and read-along. |
| `reader/test-teacher-ui.mjs`, `reader/test-reader.mjs`, `reader/package.json` | Browser checks for the teacher workflow, motion, dialogs, learner exports, and responsive layout. |
| `frontend/scripts/check-contrast.mjs` | Calculate contrast from the actual colour tokens. |

Fraunces with optical sizing and Atkinson Hyperlegible Next replace the unavailable Rafaella and Circe Slab B. The four local font subsets total about 176 KiB. Adding them to each standalone reader would cost about 234 KiB after base64 encoding, so both learner formats use the Georgia and system sans-serif fallbacks.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest backend -q
npm.cmd --prefix frontend run build
node frontend/scripts/check-contrast.mjs
$env:A11YRA_TEACHER_URL = 'http://127.0.0.1:5173/'
npm.cmd --prefix reader run test:teacher
npm.cmd --prefix reader test
```

Set `A11YRA_SCREENSHOTS` to a local output directory for screenshots. The browser tests use Microsoft Edge by default. See the [calculated contrast pairs](UI-CONTRAST.md) and [manual accessibility checklist](ACCESSIBILITY-TEST.md).
