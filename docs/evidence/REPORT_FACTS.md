# Report facts for the judging release

Checked on November 17, 2026. The current PDF uses checkout `FA4E4B8` in its footer. Replace it with the short hash supplied for the final judging-prep commit.

## Verification

| Report claim | Current result | Status |
| --- | --- | --- |
| 126 backend tests passed | 126 passed, 0 failed on Python 3.12. | Matches |
| Frontend TypeScript check and production build passed | Clean install and production build passed on Node.js 24. | Matches |
| 132/132 contrast checks passed | 132 passed across the teacher light and dark themes and the reader’s three themes. | Matches |
| 12 browser tests passed, zero failed | 12 passed, 0 failed, and 0 skipped across four specs. | Matches |
| The public-pages spec passed on retry after a timeout | All three tests in that spec passed on the first attempt in the latest full run. | Update the retry wording |

See the [verification commands](../../CONTRIBUTING.md), [contrast script](../../frontend/scripts/check-contrast.mjs), and [browser runner](../../reader/run-browser-tests.mjs). The lecture recording is a separate invocation.

## Lecture walkthrough and accessibility evidence

| Report claim | Current result | Status |
| --- | --- | --- |
| Six evaluated checks, from 2/6 to 6/6 | Direct audits of both saved DOCX files returned 2/6 and 6/6. The fresh browser walkthrough reproduced both scores. | Matches |
| Four verified repairs | Title, default language, image description, and link label. Headings and tables passed before and after. | Matches |
| Title and language changed from unset | The working copy displays **Stacks and Queues** and **en-IN**. | Matches |
| Missing alt text and generic link repaired | “Stacks remove the most recently added item first. Queues remove the earliest added item first.” The link label is “Further reading on stacks and queues.” | Matches |
| 20 headings and six column header scopes | 20 article headings and six `th[scope="col"]` elements in the newly downloaded HTML. | Matches |
| Zero network requests | Zero HTTP(S) requests observed while opening and interacting with the lecture HTML offline. | Matches |
| 640 px reflow at device pixel ratio 2 | 640 CSS px viewport and 640 CSS px document scroll width at DPR 2. | Matches |
| Zero axe violations on five tested views | Landing, upload, original audit, repaired screen reader view, and offline reader each returned zero violations. | Matches |
| Keyboard navigation and saved reader preferences | Tab entered and left the preview, Page Down scrolled it, the preset persisted after reload, and Escape restored focus to the shortcuts button. The reading ruler was visible when enabled. | Matches |
| Low vision uses 175% text, wide spacing, high contrast, and motion off | The preset sets 175% text, wide spacing, and high contrast. Motion was off because the browser requested reduced motion. Motion has its own control. | Clarify what controls motion |

The fresh [browser evidence](live-results.json) comes from the [lecture recorder](../../reader/record-lecture.mjs). The saved inputs are the [original lecture](original-lecture.docx) and [repaired lecture](repaired-lecture.docx).

## Retention and launch instructions

| Report claim | Current value | Status |
| --- | --- | --- |
| Working files expire after 24 hours by default | The API defaults to 24 hours. A teacher can delete the document sooner. | Matches |
| Audit history expires after 30 days | The deployment cap defaults to 30 days. Document audit history defaults to 7 days for free workspaces and 30 days on paid plans. Workspace activity has a separate 30-day default. | Correct the blanket 30-day claim |
| The hosted demo opens the guest sample | Select **Try a messy handout**. The guest session opens the bundled Stacks and Queues lecture. | Use this label in the hosted instructions |
| Docker opens the sample after sign-in | Select **Try a sample audit**, then create an account or sign in. | Use this label in the Docker instructions |

Sources include the [API defaults](../../backend/app/main.py#L86), [history expiry calculation](../../backend/app/api/routes.py#L91), [plan limits](../../backend/app/product/plans.py#L27), [retention sweep](../../backend/app/product/retention.py#L48), and [landing buttons](../../frontend/src/pages/Landing.tsx#L120).

## Source excerpts

| Report citation | Corrected range | What the excerpt shows |
| --- | --- | --- |
| `score.py` 6–10 | [`score.py` 6–11](../../backend/app/audit/score.py#L6-L11) | Counts passes, excludes `not_evaluated` from the denominator, and returns no percentage when no checks were evaluated. |
| `service.py` 49–50 | [`service.py` 50–51](../../backend/app/repair/service.py#L50-L51) | Marks a successful repair `fixed_unverified`. |
| `reaudit.py` 33–36 | [`reaudit.py` 34–37](../../backend/app/audit/reaudit.py#L34-L37) | Verifies a previously applied fix when the finding is absent and the check was evaluated. |

## Architecture, workflow, and design

- React 19, TypeScript, and Vite power the teacher views. FastAPI and Pydantic define the API and its payloads, with corresponding TypeScript types. The engine uses Python and python-docx, keeps the original and working DOCX privately, and supports SQLite locally and PostgreSQL in Compose. [Frontend dependencies](../../frontend/package.json) · [API routes](../../backend/app/api/routes.py) · [TypeScript contracts](../../frontend/src/types/contract.ts) · [Private storage](../../backend/app/core/storage.py) · [Compose configuration](../../compose.yaml)
- The five report steps match the app flow. Upload and validate, review six checks and the linear preview, approve repairs, re-audit the working copy, then download or publish. Published reader links can expire or be revoked. The preview approximates the document’s linear reading order. Complex content and the meaning of descriptions, headings, and tables still require human review. A11yra does not certify WCAG conformance. [Audit contract](../../A11YRA_CONTRACT.md) · [Reader preview](../../backend/app/audit/reader_preview.py) · [Data inventory](../DATA-INVENTORY.md)
- Clarify two phrases in the capabilities table. The title check detects missing metadata and a known placeholder. The link check flags common generic labels and bare URLs. Teachers judge whether the titles and links are meaningful in context. The other checks examine the default language, heading structure and visual lookalikes, image descriptions or decorative markers, and table header markup. [Audit checks](../../backend/app/audit/)
- The light theme still uses `#F5F8FA` for the page, `#E9F0F5` for panels, `#CADDEB` for accents, `#3B5B77` for secondary controls, `#19354D` for primary controls, and `#0F1E2B` for text. The teacher app also offers a dark theme. Fraunces and Atkinson Hyperlegible Next are bundled. The reader offers high contrast and controls for size, line spacing, font, motion, ruler, and single-key shortcuts. [Theme tokens](../../frontend/src/styles/tokens.css) · [Bundled fonts](../../frontend/public/fonts/) · [Reader controls](../../reader/reader.html)
