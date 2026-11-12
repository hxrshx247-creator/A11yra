import { PageHeading } from "../components/PageHeading";
import { useEffect, useRef, useState } from "react";
import { runReaudit } from "../api/client";
import { BeforeAfterPanel } from "../components/BeforeAfterPanel";
import { Button, ButtonLink } from "../components/Button";
import { useAudit } from "../hooks/useAudit";
import { usePageHeading } from "../hooks/usePageHeading";
import { useWorkspace } from "../hooks/useProduct";
import type { ReauditResponse } from "../types/contract";

export function ComparePage({ documentId }: { documentId: string }) {
  const heading = usePageHeading("Re-audit document");
  const { audit, error: loadError } = useAudit(documentId);
  const { workspace } = useWorkspace();
  const [result, setResult] = useState<ReauditResponse>();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (result) resultsHeading.current?.focus(); }, [result]);

  async function reaudit() {
    if (pending) return;
    setPending(true);
    setError("");
    try {
      setResult(await runReaudit(documentId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The new audit could not be completed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main id="main" className="audit-page" tabIndex={-1}>
      <PageHeading headingRef={heading} title="Re-audit document" eyebrow="Document engine" />
      <a className="back-to-upload" href={`/audit/${documentId}`}>Back to audit</a>
      {audit && !result && (
        <div className="workflow-card">
          {workspace.role === "viewer" ? <p>Ask a workspace editor to run a new audit.</p> : <>
            <p>Run all six checks again on the working copy to see which fixes are verified.</p>
            <Button aria-disabled={pending} onClick={reaudit}>Run re-audit</Button>
          </>}
        </div>
      )}
      <p role="status" className={result ? "visually-hidden" : "page-status"}>
        {loadError || error || (pending ? "Running re-audit…" : result ? "Re-audit complete." : !audit ? "Loading audit…" : "")}
      </p>
      {loadError && <a className="action-link" href="/upload">Return to upload</a>}
      {result && (
        <div className="comparison">
          <h2 ref={resultsHeading} tabIndex={-1}>Re-audit results</h2>
          <BeforeAfterPanel result={result} />
          <div><ButtonLink href={`/export/${documentId}`}>Continue to export</ButtonLink></div>
        </div>
      )}
    </main>
  );
}
