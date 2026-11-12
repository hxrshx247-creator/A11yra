import type { Finding } from "../types/contract";
import { StatusBadge } from "./StatusBadge";
import { ButtonLink } from "./Button";
import { Icon } from "./Icon";

export function FindingCard({ finding, documentId, headingLevel = "h2" }: {
  finding: Finding; documentId?: string; headingLevel?: "h2" | "h3";
}) {
  const Heading = headingLevel;
  return (
    <article className="finding-card">
      <Heading>{finding.location}</Heading>
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
