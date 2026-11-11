import { useState } from "react";
import { deleteDocument, downloadDocx } from "../api/client";
import { useAudit } from "../hooks/useAudit";
import { usePageHeading } from "../hooks/usePageHeading";

export function ExportPage({ documentId }: { documentId: string }) {
  const { audit, error: loadError } = useAudit(documentId);
  const heading = usePageHeading("Export Word document");
  const [pending, setPending] = useState<"download" | "delete">();
  const [finished, setFinished] = useState<"downloaded" | "deleted">();
  const [error, setError] = useState("");
  const needsVerification = audit?.findings.some((finding) => finding.status === "fixed_unverified");
  const outstanding = audit?.findings.filter((finding) => finding.status !== "verified_fixed").length ?? 0;

  async function finish(action: "download" | "delete") {
    if (pending) return;
    setPending(action);
    setError("");
    try {
      if (action === "download") {
        const file = await downloadDocx(documentId);
        const url = URL.createObjectURL(file);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = "a11yra-repaired.docx";
        document.body.append(anchor);
        anchor.click();
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        setFinished("downloaded");
      } else {
        await deleteDocument(documentId);
        setFinished("deleted");
      }
      heading.current?.focus();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The request could not be completed.");
    } finally {
      setPending(undefined);
    }
  }

  let message = loadError || error;
  if (!message) {
    if (finished === "downloaded") message = "Download started. The server session has been cleared.";
    else if (finished === "deleted") message = "The upload has been deleted.";
    else if (pending) message = pending === "download" ? "Preparing your download…" : "Deleting the upload…";
    else if (!audit) message = "Loading audit…";
  }

  return (
    <main id="main" className="audit-page" tabIndex={-1}>
      <h1 ref={heading} tabIndex={-1}>Export Word document</h1>
      {audit && !finished && (
        <>
          <a className="back-to-upload" href={`/audit/${documentId}`}>Back to audit</a>
          <section className="workflow-card" aria-labelledby="export-format">
            <h2 id="export-format">Word document (.docx)</h2>
            {outstanding > 0 && (
              <p>{outstanding} {outstanding === 1 ? "finding still needs" : "findings still need"} attention. Review them in the audit or finish the remaining changes in Word.</p>
            )}
            <p>Downloading clears the temporary upload, audit, and working copy from the server.</p>
            {needsVerification ? (
              <a className="button-link" href={`/compare/${documentId}`}>Re-audit before downloading</a>
            ) : <button type="button" aria-disabled={Boolean(pending)} onClick={() => finish("download")}>Download DOCX</button>}
          </section>
          <details className="delete-upload">
            <summary>Delete upload without downloading</summary>
            <p>This removes the working copy and audit from the server.</p>
            <button type="button" aria-disabled={Boolean(pending)} onClick={() => finish("delete")}>Delete this upload</button>
          </details>
        </>
      )}
      <p className="page-status" role="status">{message}</p>
      {finished && <a className="button-link" href="/upload">Check another document</a>}
    </main>
  );
}
