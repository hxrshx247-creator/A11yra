import { PageHeading } from "../components/PageHeading";
import { CheckList } from "../components/CheckList";
import { ProgressMeter } from "../components/ProgressMeter";
import { ButtonLink } from "../components/Button";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { useEffect, useState } from "react";
import { deleteDocument, getDocumentPreview, getReaderPreview } from "../api/client";
import type { ReaderPreview } from "../types/contract";
import { useAudit } from "../hooks/useAudit";
import { usePageHeading } from "../hooks/usePageHeading";
import { useWorkspace } from "../hooks/useProduct";
import "../styles/audit.css";

export function AuditDashboard({ documentId }: { documentId: string }) {
  const { audit, error } = useAudit(documentId);
  const heading = usePageHeading("Document audit");
  const { workspace } = useWorkspace();
  const canEdit = workspace.role !== "viewer";
  const [version, setVersion] = useState<"original" | "repaired">(() =>
    new URLSearchParams(location.search).get("preview") === "repaired" ? "repaired" : "original");
  const [preview, setPreview] = useState<ReaderPreview>();
  const [previewError, setPreviewError] = useState("");
  const [deleteMessage, setDeleteMessage] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setPreview(undefined);
    setPreviewError("");
    getReaderPreview(documentId, version, controller.signal).then(setPreview).catch((reason) => {
      if (!controller.signal.aborted) setPreviewError(reason instanceof Error ? reason.message : "Preview unavailable.");
    });
    return () => controller.abort();
  }, [documentId, version]);
  async function deleteUpload() {
    if (!window.confirm("Delete this document and its stored working files?")) return;
    try {
      await deleteDocument(documentId);
      location.assign("/upload");
    } catch (reason) {
      setDeleteMessage(reason instanceof Error ? reason.message : "The document could not be deleted.");
    }
  }

  return (
    <main className="audit-page" id="main" tabIndex={-1}>
      <PageHeading headingRef={heading} title="Document audit" eyebrow="Document engine" />
      <div className={audit ? "visually-hidden" : `audit-message${error ? " form-error" : ""}`} role="status">
        {error && <Icon name="info" />}
        {error || (audit ? "Audit loaded. Select a check to review its findings." : "Loading audit…")}
      </div>
      {error && <a className="back-to-upload" href="/upload">Return to upload</a>}
      {audit && (
        <>
          <div className="audit-overview">
            <ProgressMeter progress={audit.progress} />
            <section className="audit-actions" aria-labelledby="audit-actions-heading">
              <h2 id="audit-actions-heading">Document actions</h2>
              <div className="product-actions">
                {canEdit && <ButtonLink href={`/compare/${documentId}`}>Re-audit document</ButtonLink>}
                <ButtonLink variant={canEdit ? "secondary" : "primary"} href={`/export/${documentId}`}>Export document</ButtonLink>
                {import.meta.env.VITE_SHOW_ADVANCED === "true" && <a href={`/history/${documentId}`}>View audit history</a>}
                {canEdit && <Button variant="quiet" onClick={deleteUpload}>Delete this document</Button>}
              </div>
              {deleteMessage && <p role="alert" className="form-error">{deleteMessage}</p>}
            </section>
          </div>
          <DocumentPreview key={documentId} documentId={documentId} />
          <CheckList audit={audit} canEdit={canEdit} />
          <section className="reader-preview" id="screen-reader-view" aria-labelledby="reader-preview-heading">
            <h2 id="reader-preview-heading">Screen reader view</h2>
            <div className="reader-preview-tabs" role="group" aria-label="Preview version">
              <button type="button" aria-pressed={version === "original"} onClick={() => setVersion("original")}>Original</button>
              <button type="button" aria-pressed={version === "repaired"} onClick={() => setVersion("repaired")}>Repaired</button>
            </div>
            <p className="preview-caveat">Approximation of linear screen reader output; real behavior varies by software.</p>
            {previewError && <p role="status">{previewError}</p>}
            {!preview && !previewError && <p role="status">Loading preview…</p>}
            {preview && <ol role="list" className="reader-preview-list" tabIndex={0}
              aria-label={version === "original" ? "Original document preview" : "Repaired document preview"}>{preview.items.map((item, index) => {
              const finding = item.finding_id && audit.findings.find((row) => row.id === item.finding_id);
              return <li key={`${item.type}-${index}`}>
                <span className="preview-item-text">{item.text}</span>
                {item.issue && <span className="preview-issue"><Icon name="info" /> Issue{finding ? `: ${finding.barrier}` : ": needs review"}</span>}
                {finding && <a href={`/audit/${documentId}?check=${finding.check_id}`}>View {finding.check_id} finding</a>}
              </li>;
            })}</ol>}
          </section>
        </>
      )}
    </main>
  );
}

function DocumentPreview({ documentId }: { documentId: string }) {
  const [preview, setPreview] = useState<{ filename: string; html: string }>();
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    getDocumentPreview(documentId, controller.signal).then(setPreview).catch((reason) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Preview unavailable.");
    });
    return () => controller.abort();
  }, [documentId]);

  return <section className="document-preview" aria-labelledby="document-preview-heading">
    <h2 id="document-preview-heading">Document preview</h2>
    {preview ? <>
      <p>{preview.filename} · Working copy</p>
      <iframe title={`Working copy of ${preview.filename}`} sandbox="" srcDoc={preview.html} />
    </> : <p role="status">{error || "Loading document preview…"}</p>}
  </section>;
}
