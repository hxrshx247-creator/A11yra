# Public-page cleanup review

## Changed files

| File | Change |
| --- | --- |
| `.env.example` | Documented the public build-time `SUPPORT_EMAIL` setting. |
| `compose.yaml` | Passed `SUPPORT_EMAIL` to the frontend build. |
| `backend/app/product/plan_prices.json` | Added shared pilot prices with three null values. |
| `backend/app/product/plans.py` | Added the internal price field and serialized the original public limits. |
| `backend/app/product/billing.py` | Kept the plans API response fields unchanged. |
| `backend/app/product/workspaces.py` | Kept the workspace usage plan fields unchanged. |
| `frontend/Dockerfile` | Included the shared prices and the support email build argument. |
| `frontend/vite.config.ts` | Loaded the public contact and allowed access to the shared prices in development. |
| `frontend/src/main.tsx` | Applied the public navigation to the landing, public information and public account pages. |
| `frontend/src/components/AppShell.tsx` | Simplified public navigation and moved display controls outside it. |
| `frontend/src/pages/Landing.tsx` | Made the closing copy explicit about the six checks and compliance limit. |
| `frontend/src/pages/PublicPages.tsx` | Updated pricing, security, privacy, terms, support, accessibility, changelog and status copy. |
| `frontend/src/pages/AccountPage.tsx` | Carried the sample selection through existing signup and sign-in requests. |
| `frontend/src/pages/AuditDashboard.tsx` | Added the inline hint when opened by the sample signup flow. |
| `frontend/src/styles/landing.css` | Removed the retired landing navigation rules. |
| `frontend/src/styles/product.css` | Styled public navigation, headed sections and the pricing table with existing tokens. |
| `reader/product-helpers.mjs` | Scoped sign-in to account navigation. |
| `reader/test-teacher-ui.mjs` | Scoped the landing sign-in interaction to the primary nav. |
| `reader/test-product.mjs` | Updated assertions to match public page copy. |
| `reader/test-public-pages.mjs` | Added screenshots, public axe scans, layout checks and sample signup coverage. |
| `reader/run-browser-tests.mjs` | Included the public-page suite in the default browser run. |
| `docs/DEPLOYMENT.md` | Documented how to configure the public support address. |
| `docs/OPERATIONS.md` | Updated the public support setting name. |
| `docs/PUBLIC-PAGES-CLEANUP.md` | Recorded the file list, copy removals and editorial choices. |

## Removed or replaced copy

- Public header links “Engine”, “Checks”, “Reader” and “Workspace”. The landing sections and teacher workflow still have their existing entry points. Removed the duplicate footer “Pricing” link on the landing page.
- Landing’s “Accessible by design, verified by audit” and “Check your next course document for accessibility barriers.” The replacement describes the six checks and says the audit is not a compliance guarantee.
- Pricing’s “Start with a small set of course materials. Test higher limits as more teachers join.” and “Intended for” table row. One introductory sentence now names the audiences.
- Pricing’s em dashes for missing features, “Paid pricing is a pilot hypothesis”, and the old public demo plan switch, test checkout buttons and their status messages. The demo billing banner and underlying billing endpoints remain.
- Security’s “A11yra is designed with privacy in mind” tagline, the separate link-sharing caution, and duplicate deletion and backup paragraphs. The summary covers five topics and links to the full policy.
- The duplicate privacy tagline and “operator” wording on the Privacy and Terms pages. Retention, deletion, backup and legal limits are still described in headed sections.
- The support placeholder “Pilot operators should publish a support email on this page” and the original single-sentence report prompt. The support page now gives three report items and uses the configured address when present.
- The long accessibility testing and limitations paragraphs. Their contents appear as separate “What we test” and “Known gaps” lists.
- Changelog’s “Phase 1”, “Phase 2” and “Phase 3” headings and their longer descriptions. Each entry is now one dated release line.
- Status’s “API and storage readiness check passed”, “The readiness check is currently unavailable”, and the explanation about incident history. The footer link remains and the page shows the result and check time.

The changelog dates reflect implementation milestones in the working copy. They do not indicate public deployment dates. The before and after screenshots use the local app without a configured support address.
