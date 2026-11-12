import { PageHeading } from "../components/PageHeading";
import { useState } from "react";
import { dismissHeadingCandidate } from "../api/client";
import { FindingCard } from "../components/FindingCard";
import { FixForm, FIX_TYPES } from "../components/FixForm";
import { Button, ButtonLink } from "../components/Button";
import { Icon } from "../components/Icon";
import { useAudit } from "../hooks/useAudit";
import { usePageHeading } from "../hooks/usePageHeading";
import { useWorkspace } from "../hooks/useProduct";

export function FixPage({ documentId, findingId }: { documentId: string; findingId: string }) {
  const { audit, error } = useAudit(documentId);
  const heading = usePageHeading("Review fix");
  const { workspace } = useWorkspace();
  const [applied, setApplied] = useState(false);
  const [dismissError, setDismissError] = useState("");
  const finding = audit?.findings.find((item) => item.id === findingId);
  const shownFinding = finding && applied ? { ...finding, status: "fixed_unverified" as const } : finding;
  const type = finding && FIX_TYPES[finding.check_id];
  const canFix = workspace.role !== "viewer" && (shownFinding?.status === "open" || shownFinding?.status === "needs_review") && shownFinding.fixable === "teacher_approved";
  const back = `/audit/${documentId}${finding ? `?check=${finding.check_id}` : ""}`;
  const message = error || (!audit ? "Loading finding…" : !finding ? "This finding could not be found." : "");

  return (
    <main id="main" className="audit-page" tabIndex={-1}>
      <PageHeading headingRef={heading} title="Review fix" eyebrow="Document engine" />
      <a className="back-to-upload" href={back}>Back to audit</a>
      <div className={applied ? "page-status workflow-success" : error || (audit && !finding) ? "page-status form-error" : message ? "page-status" : "visually-hidden"} role="status">
        {applied && <Icon name="success" />}
        {!applied && (error || (audit && !finding)) && <Icon name="error" />}
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
      {finding?.id.startsWith("heading-lookalike-") && finding.status === "needs_review" && workspace.role !== "viewer" &&
        <Button className="finding-action" variant="secondary" onClick={async () => {
          try { await dismissHeadingCandidate(documentId, finding.id); location.assign(back); }
          catch (reason) { setDismissError(reason instanceof Error ? reason.message : "The decision could not be saved."); }
        }}>Not a heading</Button>}
      {dismissError && <p role="alert" className="form-error">{dismissError}</p>}
      {applied && <ButtonLink className="finding-action" href={`/compare/${documentId}`}>Re-audit to verify</ButtonLink>}
    </main>
  );
}
