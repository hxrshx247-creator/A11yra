import { CheckList } from "../components/CheckList";
import { ProgressMeter } from "../components/ProgressMeter";
import { useAudit } from "../hooks/useAudit";
import { usePageHeading } from "../hooks/usePageHeading";
import "../styles/audit.css";

export function AuditDashboard({ documentId }: { documentId: string }) {
  const { audit, error } = useAudit(documentId);
  const heading = usePageHeading("Document audit");

  return (
    <main className="audit-page" id="main" tabIndex={-1}>
      <h1 ref={heading} tabIndex={-1}>Document audit</h1>
      <div className={audit ? "visually-hidden" : "audit-message"} role="status">
        {error || (audit ? "Audit loaded. Select a check to review its findings." : "Loading audit…")}
      </div>
      {error && <a className="back-to-upload" href="/upload">Return to upload</a>}
      {audit && (
        <>
          <ProgressMeter progress={audit.progress} />
          <a className="button-link audit-action" href={`/compare/${documentId}`}>Re-audit document</a>
          <CheckList audit={audit} />
        </>
      )}
    </main>
  );
}
