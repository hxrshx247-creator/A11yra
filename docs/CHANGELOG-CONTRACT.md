# Contract implementation notes

## Phase 3 hardening

- Published learner snapshots use an HTTP Content Security Policy with hashes of the bundled reader assets and `Cache-Control: private, no-store`. External reader links receive `rel="noopener noreferrer"`.
- Public audit requests that exceed the deadline return HTTP 408 with `request_timeout` in the existing error envelope. Email verification submissions can return HTTP 429 with the existing `rate_limit` code.

## Phase 3 amendment

Phase 3 lifts the restrictions on databases and accounts. Existing document request and response bodies, errors, enums and audit shapes remain compatible. Workspace authentication, role checks and CSRF apply to the existing document API. Working files now default to 24-hour retention, audit history defaults to 30 days, and downloads leave the workspace document available until it expires or is deleted. Explicitly published reader snapshots are the only document content served publicly. Configured mail and Stripe test billing are permitted server-side integrations.

The product schema adds users, workspaces, memberships, sessions, account tokens, invitations, documents, audits, fixes, exports, audit logs, subscriptions, usage events, reader shares and API keys. Documents and their children belong to one workspace. Audit history retains check summaries and bounded evidence, while original and working DOCX files live in private file storage.

New routes cover authentication and account data under `/api/auth`, workspace membership, invitations, activity, dashboard, usage and billing under `/api/workspaces/{workspace_id}`, history and shares under `/api/documents/{id}`, plans at `/api/plans`, Stripe events at `/api/billing/webhook`, and the authenticated integration API at `/api/public/v1/audit`. Published readers resolve at `/r/{token}`. Readiness and token-protected metrics supplement the existing health route.

- Phase 2 implements the existing GET /api/documents/{id}/export/html endpoint. The offline=true representation is an HTML attachment with inline assets. The offline=false representation transports the HTML and its sibling assets together in a ZIP. Extract the ZIP and open index.html. Both representations use local assets and close the temporary upload session after download.
