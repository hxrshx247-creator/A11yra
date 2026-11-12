import { PageHeading } from "../components/PageHeading";
import { useRef, useState } from "react";
import { deleteDocument, downloadDocx, downloadLearnerHtml } from "../api/client";
import { useAudit } from "../hooks/useAudit";
import { usePageHeading } from "../hooks/usePageHeading";
import { Button, ButtonLink } from "../components/Button";
import { closeDetailsOnEscape } from "../components/detailsKeyboard";
import { Icon } from "../components/Icon";
import { useWorkspace } from "../hooks/useProduct";
import { ReaderLinks } from "./DocumentHistory";

const formats = {
  docx: "a11yra-repaired.docx",
  html: "a11yra-reader.html",
  zip: "a11yra-reader.zip",
};
type Format = keyof typeof formats;

export function ExportPage({ documentId }: { documentId: string }) {
  const { audit, error: loadError } = useAudit(documentId);
  const heading = usePageHeading("Export Word document");
  const { workspace } = useWorkspace();
  const [pending, setPending] = useState<Format | "delete">();
  const [finished, setFinished] = useState<Format | "deleted">();
  const [error, setError] = useState("");
  const busy = useRef(false);
  const needsVerification = audit?.findings.some((finding) => finding.status === "fixed_unverified");
  const outstanding = audit?.findings.filter((finding) => finding.status !== "verified_fixed").length ?? 0;

  async function finish(action: Format | "delete") {
    if (busy.current) return;
    busy.current = true;
    setPending(action);
    setError("");
    try {
      if (action !== "delete") {
        const file = action === "docx" ? await downloadDocx(documentId) : await downloadLearnerHtml(documentId, action === "html");
        const url = URL.createObjectURL(file);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = formats[action];
        document.body.append(anchor);
        anchor.click();
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        setFinished(action);
      } else {
        await deleteDocument(documentId);
        setFinished("deleted");
        heading.current?.focus();
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The request could not be completed.");
    } finally {
      busy.current = false;
      setPending(undefined);
    }
  }

  let message = loadError || error;
  if (!message) {
    if (pending) message = pending === "delete" ? "Deleting the upload…" : `Preparing ${formats[pending]}…`;
    else if (finished === "deleted") message = "The upload has been deleted.";
    else if (finished) message = `Download started: ${formats[finished]}.`;
    else if (!audit) message = "Loading audit…";
  }

  const hasError = Boolean(loadError || error);
  const showSuccess = Boolean(finished && !pending && !hasError);

  return (
    <main id="main" className="audit-page" tabIndex={-1}>
      <PageHeading headingRef={heading} title="Export Word document" eyebrow="Document engine" />
      {audit && finished !== "deleted" && (
        <>
          <div className="product-actions">
            <a className="back-to-upload" href={`/audit/${documentId}`}>Back to audit</a>
            <a href="/workspace">Back to workspace</a>
          </div>
          <div className="export-grid">
            <section className="workflow-card" aria-labelledby="export-format">
              <h2 id="export-format">Word document (.docx)</h2>
              {outstanding > 0 && (
                <p>{outstanding} {outstanding === 1 ? "finding still needs" : "findings still need"} attention. Review them in the audit or finish the remaining changes in Word.</p>
              )}
              <p>Download any of these formats from the same audit until its working files expire.</p>
              <p>For a reading guide in Word, open View → Immersive Reader → Line Focus.</p>
              {needsVerification ? (
                workspace.role === "viewer" ? <p>Ask a workspace editor to verify the fixes before you download.</p>
                  : <ButtonLink href={`/compare/${documentId}`}>Re-audit before downloading</ButtonLink>
              ) : <Button variant="secondary" aria-disabled={Boolean(pending)} onClick={() => finish("docx")}>Download DOCX</Button>}
            </section>
            {!needsVerification && (
              <section className="workflow-card" aria-labelledby="learner-export-heading">
                <h2 id="learner-export-heading">Learner reader</h2>
                <p>Both formats include the reading ruler and work offline.</p>
                <div className="export-options">
                  <div>
                    <Button aria-disabled={Boolean(pending)} onClick={() => finish("html")}>Download offline HTML</Button>
                    <p>Open the single file directly.</p>
                  </div>
                  <div>
                    <Button variant="secondary" aria-disabled={Boolean(pending)} onClick={() => finish("zip")}>Download HTML ZIP</Button>
                    <p>Extract the ZIP, then open index.html.</p>
                  </div>
                </div>
              </section>
            )}
          </div>
          {workspace.role !== "viewer" && !needsVerification && <ReaderLinks id={documentId} publish />}
          {workspace.role !== "viewer" && <details className="delete-upload" onKeyDown={closeDetailsOnEscape}>
            <summary>Delete this document</summary>
            <form className="product-form" onSubmit={(event) => { event.preventDefault(); void finish("delete"); }}>
              <p>This removes the file, audit history, and published reader links.</p>
              <label className="product-checkbox"><input type="checkbox" required /> I confirm permanent deletion of this document.</label>
              <Button variant="secondary" type="submit" disabled={Boolean(pending)}>Delete my document now</Button>
            </form>
          </details>}
        </>
      )}
      <div className={showSuccess ? "complete-state" : undefined}>
        <p className={hasError ? "page-status form-error" : showSuccess ? "page-status success-message" : "page-status"} role="status">
          {showSuccess && <Icon name="success" />}{message}
        </p>
      </div>
      {loadError && <a className="action-link" href="/upload">Return to upload</a>}
      {finished === "deleted" && <ButtonLink href="/workspace">Back to workspace</ButtonLink>}
    </main>
  );
}
