# Phase 3 schema and endpoints

The API keeps the original document payloads and audit enums in the [contract](../A11YRA_CONTRACT.md). The [OpenAPI reference](http://127.0.0.1:5173/api/docs) describes requests and responses.

## Schema

| Tables | Purpose |
| --- | --- |
| `users`, `sessions`, `account_tokens` | Email, password hash, verification flag, hashed session credentials, and short-lived single-use account links |
| `workspaces`, `memberships`, `invitations` | Personal workspace ownership, owner/editor/viewer roles and email-bound invitations |
| `documents`, `audits`, `fixes`, `exports` | Document metadata, audit versions and bounded evidence, applied finding IDs and export formats |
| `audit_logs` | Append-only activity events with workspace, actor, event type and operational metadata. Retention and account erasure apply. |
| `subscriptions`, `usage_events` | Workspace plan, test subscription reference and metered audits/exports |
| `reader_shares`, `api_keys` | Hashed reader link and API key credentials, expiry or revocation, and last-used time for keys |

## Routes added in Phase 3

| Method | Path | Access |
| --- | --- | --- |
| GET | `/api/auth/csrf` | Public CSRF bootstrap |
| POST | `/api/auth/signup`, `/api/auth/login`, `/api/auth/forgot`, `/api/auth/reset`, `/api/auth/verify` | Public with CSRF |
| POST | `/api/auth/refresh`, `/api/auth/logout` | Refresh or clear session cookies |
| GET | `/api/auth/me`, `/api/auth/data` | Account holder |
| POST | `/api/auth/verify/resend` | Account holder |
| DELETE | `/api/auth/account` | Account holder with password and confirmation |
| POST | `/api/invites/accept` | Verified invitee |
| GET | `/api/workspaces/{workspace_id}/documents`, `/api/workspaces/{workspace_id}/usage` | Viewer and above |
| GET | `/api/workspaces/{workspace_id}/activity` | Editor and above |
| GET | `/api/workspaces/{workspace_id}/dashboard`, `/api/workspaces/{workspace_id}/members` | Owner |
| POST | `/api/workspaces/{workspace_id}/invites` | Verified owner |
| PATCH | `/api/workspaces/{workspace_id}/members/{user_id}` | Owner |
| POST | `/api/documents/sample` | Editor and above |
| GET | `/api/documents/{id}/history` | Viewer and above |
| GET, POST | `/api/documents/{id}/shares` | Editor and above |
| DELETE | `/api/documents/{id}/shares/{share_id}` | Editor and above |
| GET | `/r/{token}` | Anyone holding the valid reader link |
| GET | `/api/plans` | Public |
| POST | `/api/workspaces/{workspace_id}/billing/demo`, `/api/workspaces/{workspace_id}/billing/checkout` | Owner, subject to billing configuration |
| POST | `/api/billing/webhook` | Stripe-signed test events |
| GET, POST | `/api/workspaces/{workspace_id}/keys` | Owner. Creation requires Institution. |
| DELETE | `/api/workspaces/{workspace_id}/keys/{key_id}` | Owner |
| POST | `/api/public/v1/audit` | Institution API key |
| GET | `/api/ready`, `/api/docs`, `/api/openapi.json` | Public |
| GET | `/api/metrics` | Deployment metrics token |

For uploads, `X-Workspace-Id` selects the target workspace. Omitting it selects the caller’s personal workspace. Document-specific routes derive the workspace from the document and return 404 to callers outside that workspace.

## Workspace role matrix

| Operation | Viewer | Editor | Owner |
| --- | --- | --- | --- |
| List documents, read usage, view audits and history, download DOCX or HTML | Yes | Yes | Yes |
| Upload or use sample, apply fixes, re-audit, delete document | 403 | Yes | Yes |
| List, create or revoke published reader links | 403 | Yes | Yes |
| Read activity as JSON or CSV | 403 | Yes | Yes |
| Read dashboard as JSON or CSV, list members, change a member's role | 403 | 403 | Yes |
| Invite a member | 403 | 403 | Verified owner |
| List, create or revoke API keys | 403 | 403 | Yes, with an eligible plan for creation |
| Start checkout or change the demo plan | 403 | 403 | Yes, subject to billing configuration |

A signed-in outsider gets 404 on workspace-scoped routes. The published `/r/{token}` route is intentionally public to holders of a valid token. The public audit API uses the key’s workspace and does not accept a workspace override.

Public audits have a 30-second request deadline. A timeout returns HTTP 408 with `request_timeout` in the standard error envelope.
