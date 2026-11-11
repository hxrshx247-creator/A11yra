import type { Finding } from "../types/contract";
import { Badge } from "./Badge";

const STATUS_LABELS: Record<Finding["status"], string> = {
  open: "Open",
  fixed_unverified: "Fixed, awaiting verification",
  verified_fixed: "Verified fixed",
  needs_review: "Needs review",
};

const SEVERITY_TONES = { high: "danger", medium: "warning", low: "neutral" } as const;

export function FindingCard({ finding, documentId }: { finding: Finding; documentId?: string }) {
  const statusTone = finding.status === "verified_fixed" ? "success"
    : finding.status === "open" ? "neutral" : "warning";

  return (
    <article className="finding-card">
      {documentId ? <h3>{finding.location}</h3> : <h2>{finding.location}</h2>}
      <div className="finding-badges">
        <Badge tone={statusTone}>{STATUS_LABELS[finding.status]}</Badge>
        <Badge tone={SEVERITY_TONES[finding.severity]}>{finding.severity} severity</Badge>
        <Badge tone="neutral">{finding.confidence} confidence</Badge>
      </div>
      <dl>
        <dt>What we found</dt>
        <dd>{finding.evidence}</dd>
        <dt>Why it matters</dt>
        <dd>{finding.barrier}</dd>
        <dt>Suggested fix</dt>
        <dd>{finding.suggestion}</dd>
      </dl>
      {finding.fixable === "recommendation_only" && (
        <p className="finding-note">Recommendation only. Make changes in Word if needed.</p>
      )}
      {documentId && finding.fixable === "teacher_approved" && finding.status === "open" && (
        <a className="action-link finding-action" href={`/fix/${documentId}/${encodeURIComponent(finding.id)}`}>
          <span>Review fix</span><span className="visually-hidden"> for {finding.location}</span>
        </a>
      )}
    </article>
  );
}
