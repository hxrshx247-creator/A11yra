import { useEffect, useRef, useState } from "react";
import { runReaudit } from "../api/client";
import { BeforeAfterPanel } from "../components/BeforeAfterPanel";
import { useAudit } from "../hooks/useAudit";
import { usePageHeading } from "../hooks/usePageHeading";
import type { ReauditResponse } from "../types/contract";

export function ComparePage({ documentId }: { documentId: string }) {
  const heading = usePageHeading("Re-audit document");
  const { audit, error: loadError } = useAudit(documentId);
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
      <h1 ref={heading} tabIndex={-1}>Re-audit document</h1>
      <a className="back-to-upload" href={`/audit/${documentId}`}>Back to audit</a>
      {audit && !result && (
        <div className="workflow-card">
          <p>Run all six checks again on the working copy to see which fixes are verified.</p>
          <button type="button" aria-disabled={pending} onClick={reaudit}>Run re-audit</button>
        </div>
      )}
      <p role="status" className={result ? "visually-hidden" : "page-status"}>
        {loadError || error || (pending ? "Running re-audit…" : result ? "Re-audit complete." : !audit ? "Loading audit…" : "")}
      </p>
      {result && (
        <div className="comparison">
          <h2 ref={resultsHeading} tabIndex={-1}>Re-audit results</h2>
          <BeforeAfterPanel result={result} />
          <div><a className="button-link" href={`/export/${documentId}`}>Continue to export</a></div>
        </div>
      )}
    </main>
  );
}
