import { PageHeading } from "../components/PageHeading";
import { CheckList } from "../components/CheckList";
import { ProgressMeter } from "../components/ProgressMeter";
import { ButtonLink } from "../components/Button";
import { useAudit } from "../hooks/useAudit";
import { usePageHeading } from "../hooks/usePageHeading";
import { useWorkspace } from "../hooks/useProduct";
import "../styles/audit.css";

export function AuditDashboard({ documentId }: { documentId: string }) {
  const { audit, error } = useAudit(documentId);
  const heading = usePageHeading("Document audit");
  const { workspace } = useWorkspace();
  const canEdit = workspace.role !== "viewer";
  const sample = new URLSearchParams(location.search).get("sample") === "1";

  return (
    <main className="audit-page" id="main" tabIndex={-1}>
      <PageHeading headingRef={heading} title="Document audit" eyebrow="Document engine" />
      <div className={audit ? "visually-hidden" : "audit-message"} role="status">
        {error || (audit ? "Audit loaded. Select a check to review its findings." : "Loading audit…")}
      </div>
      {error && <a className="back-to-upload" href="/upload">Return to upload</a>}
      {audit && (
        <>
          {sample && <p>Choose a finding to see what it means, then review a fix.</p>}
          <ProgressMeter progress={audit.progress} />
          <div className="product-actions audit-action">
            {canEdit && <ButtonLink href={`/compare/${documentId}`}>Re-audit document</ButtonLink>}
            <ButtonLink variant={canEdit ? "secondary" : "primary"} href={`/export/${documentId}`}>Export document</ButtonLink>
            <a href={`/history/${documentId}`}>View audit history</a>
          </div>
          <CheckList audit={audit} canEdit={canEdit} />
        </>
      )}
    </main>
  );
}
