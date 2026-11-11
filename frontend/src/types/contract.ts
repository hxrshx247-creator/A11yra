export type CheckId = "title" | "language" | "headings" | "images" | "tables" | "links";
export type CheckResult = "passed" | "issues" | "needs_review" | "not_evaluated";
export type Severity = "high" | "medium" | "low";
export type Confidence = "high" | "medium" | "low";
export type FindingStatus = "open" | "fixed_unverified" | "verified_fixed" | "needs_review";
export type FixType = "set_title" | "set_language" | "set_alt_text" | "set_link_text" | "set_table_header";

export interface Finding {
  id: string;
  check_id: CheckId;
  location: string;
  locator: Record<string, number | string>;
  evidence: string;
  barrier: string;
  suggestion: string;
  severity: Severity;
  confidence: Confidence;
  status: FindingStatus;
  fixable: "teacher_approved" | "recommendation_only";
  preview?: string;
}

export interface Check {
  id: CheckId;
  label: string;
  result: CheckResult;
  summary: string;
  finding_ids: string[];
}

export interface Audit {
  audit_id: string;
  document_id: string;
  created_at: string;
  checks: Check[];
  findings: Finding[];
  progress: { passed: number; evaluated: number; percent: number | null };
}

export interface Fix {
  finding_id: string;
  type: FixType;
  payload: { title?: string; lang?: string; alt_text?: string; decorative?: boolean; new_text?: string };
}

export interface FixResponse {
  applied: { finding_id: string; status: "fixed_unverified" }[];
  skipped: { finding_id: string; reason: string }[];
}

export interface AuditDiff {
  verified_fixed: string[];
  still_open: string[];
  new_findings: string[];
  needs_review: string[];
  progress_before: Audit["progress"];
  progress_after: Audit["progress"];
}

export interface ReauditResponse {
  audit: Audit;
  diff: AuditDiff;
}

export interface UploadResponse {
  document_id: string;
  filename: string;
  audit: Audit;
}
