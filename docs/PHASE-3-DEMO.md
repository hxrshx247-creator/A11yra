# Phase 3 demo

Use the built-in sample, or upload [pilot-syllabus.docx](../backend/fixtures/pilot-syllabus.docx). Demo billing is available on Pricing with the local development settings.

| Time | Action |
| --- | --- |
| 0:00–0:40 | Create an account, sign in and audit the sample in the personal workspace. Show **2 of 6 checks passed**. |
| 0:40–1:55 | Add the title “Study Group Syllabus”, language `en-IN`, chart description “Attendance doubled from 12 to 24 students”, and link label “Weekly study group schedule”. |
| 1:55–2:35 | Re-audit. Show **6 of 6 checks passed** and **four verified fixes**. Continue to Export and publish a learner link. |
| 2:35–3:15 | Open the reader link in a private browser. Tab to Skip to content, open Contents, and reach the chart description by keyboard. |
| 3:15–4:00 | Show the original and latest result in the Dashboard, then show Activity and Pricing. |

## Judge rehearsal

- **Who pays?** A department or disability-services office that needs a repeatable review process can sponsor the first pilot. Educators can try it on their own.
- **What stops Microsoft?** Word already has a checker. Test whether a shared repair history, re-audit and a standalone learner reader make this workflow worth adopting.
- **What protects course materials?** Workspace role checks, expiring working files, private storage and explicit publication. A public link is shareable by anyone who has it, so publish only material intended for that audience.
- **What happens when a check misses a problem?** Show the six checks, review the evidence and recommend a manual review of the exported document with assistive technology.
- **Why trust the prototype?** Demonstrate deletion and revocation, show tests and the threat model, and use synthetic or approved documents during the pilot.
- **What’s the first pilot?** One first-year department, a two-week course pack, five teachers and two student or accessibility reviewers.

## Load result

The local benchmark ran 10 API audits with two callers using the 39,238-byte demo syllabus. All 10 returned the expected audit. Median response time was 172.2 ms and p95 was 240.6 ms, with 11.4 requests per second over the short batch. This was an in-process FastAPI/SQLite run. Run `python -m scripts.benchmark_audit` from the backend directory to repeat it. To measure a running instance with k6, create an Institution demo key, set `A11YRA_API_KEY`, and run `k6 run backend/scripts/load-audit.js` from the repo root. The load script uses 10 requests with two callers and fits within the API key rate limit.

See the [product case](PRODUCT.md) for the cost assumptions, the [Activity screenshot](evidence/activity.png) for a synthetic account, the [axe report](evidence/axe-phase3.json) for the scanned pages, and the [CI workflow](../.github/workflows/ci.yml) for automated verification. Use the [manual accessibility checklist](ACCESSIBILITY-TEST.md) for screen-reader testing.

## Try the product features

1. **Identity and workspaces** — Create two accounts and verify both using the development mail links. Invite the second account as a viewer and check which actions are available.
2. **Activity and privacy** — Filter Activity to document uploads and download the CSV. Delete a test document and confirm that its history disappears and a deletion event appears.
3. **Plans and history** — Audit the sample, fix the four findings and re-audit. Find both audits in History. Switch to Institution in demo mode and check the new monthly limit.
4. **Reader and integrations** — Open a published reader in a private window, revoke the link and reload the window. Create an API key and try the curl example in the operations guide.
