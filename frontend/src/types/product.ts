import type { Audit } from "./contract";

export type WorkspaceRole = "owner" | "editor" | "viewer";
export type Workspace = { id: string; name: string; role: WorkspaceRole; personal: boolean };
export type Profile = { id: string; email: string; email_verified: boolean; workspaces: Workspace[] };

export type Plan = {
  name: string;
  documents_per_month: number;
  max_file_bytes: number;
  seats: number;
  history_days: number;
  api_access: boolean;
  reader_branding: boolean;
};
export type Plans = { plans: Record<string, Plan>; billing_demo: boolean; demo_changes: boolean };
export type Usage = { plan: Plan; documents_used: number; exports: number; file_hours: number; billing_demo: boolean };

export type WorkspaceDocument = { id: string; filename: string; status: string; created_at: string; expires_at: string };
export type History = { filename: string; status: string; expires_at: string; versions: Omit<Audit, "findings">[] };
export type Member = { id: string; email: string; role: WorkspaceRole };
export type Activity = {
  created_at: string; actor: string | null; actor_id: string | null; action: string;
  target_type: string; target_id: string | null;
};
export type Dashboard = {
  documents: number; open: number; verified: number; average_percent: number | null;
  common_issues: { check: string; count: number }[];
  attention: { document_id: string; filename: string; versions: number; before: string; after: string; open: number; verified: number }[];
};
export type Share = { id: string; created_at: string; expires_at: string };
export type IntegrationKey = { id: string; name: string; created_at: string; last_used_at: string | null; revoked_at: string | null };
