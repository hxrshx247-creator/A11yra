import type { Finding } from "../types/contract";
import { StatusBadge } from "./StatusBadge";
import { ButtonLink } from "./Button";
import { Icon } from "./Icon";

export function FindingCard({ finding, documentId }: { finding: Finding; documentId?: string }) {

  return (
    <article className="finding-card">
      {documentId ? <h3>{finding.location}</h3> : <h2>{finding.location}</h2>}
      <div className="finding-badges">
        <StatusBadge status={finding.status} />
        <StatusBadge status={finding.severity} />
        <span className="confidence">{finding.confidence[0].toUpperCase()}{finding.confidence.slice(1)} confidence</span>
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
        <p className="finding-note"><Icon name="info" /> Recommendation only. Make changes in Word if needed.</p>
      )}
      {documentId && finding.fixable === "teacher_approved" && finding.status === "open" && (
        <ButtonLink className="finding-action" href={`/fix/${documentId}/${encodeURIComponent(finding.id)}`}>
          <span>Review fix</span><span className="visually-hidden"> for {finding.location}</span>
        </ButtonLink>
      )}
    </article>
  );
}
