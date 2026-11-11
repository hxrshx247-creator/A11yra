import { useState } from "react";
import { FindingCard } from "../components/FindingCard";
import { FixForm, FIX_TYPES } from "../components/FixForm";
import { useAudit } from "../hooks/useAudit";
import { usePageHeading } from "../hooks/usePageHeading";

export function FixPage({ documentId, findingId }: { documentId: string; findingId: string }) {
  const { audit, error } = useAudit(documentId);
  const heading = usePageHeading("Review fix");
  const [applied, setApplied] = useState(false);
  const finding = audit?.findings.find((item) => item.id === findingId);
  const shownFinding = finding && applied ? { ...finding, status: "fixed_unverified" as const } : finding;
  const type = finding && FIX_TYPES[finding.check_id];
  const canFix = shownFinding?.status === "open" && shownFinding.fixable === "teacher_approved";
  const back = `/audit/${documentId}${finding ? `?check=${finding.check_id}` : ""}`;
  const message = error || (!audit ? "Loading finding…" : !finding ? "This finding could not be found." : "");

  return (
    <main id="main" className="audit-page" tabIndex={-1}>
      <h1 ref={heading} tabIndex={-1}>Review fix</h1>
      <a className="back-to-upload" href={back}>Back to audit</a>
      <div className={message || applied ? "page-status" : "visually-hidden"} role="status">
        {applied ? "Fix applied. Run a new audit to verify it." : message}
      </div>
      {shownFinding && (
        <div className="fix-layout">
          <FindingCard finding={shownFinding} />
          {type && canFix && (
            <FixForm documentId={documentId} finding={shownFinding} type={type} onApplied={() => {
              setApplied(true);
              heading.current?.focus();
            }} />
          )}
        </div>
      )}
    </main>
  );
}
