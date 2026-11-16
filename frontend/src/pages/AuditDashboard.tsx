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
  const [selectedVersion, setVersion] = useState<"original" | "repaired" | null>(() => {
    const requested = new URLSearchParams(location.search).get("preview");
    return requested === "repaired" || requested === "original" ? requested : null;
  });
  const version = selectedVersion ?? (audit?.findings.some(
    (finding) => finding.status === "fixed_unverified" || finding.status === "verified_fixed",
  ) ? "repaired" : "original");
  const [preview, setPreview] = useState<ReaderPreview>();
  const [previewError, setPreviewError] = useState("");
  const [deleteMessage, setDeleteMessage] = useState("");
  useEffect(() => {
    if (!audit) return;
    const controller = new AbortController();
    setPreview(undefined);
    setPreviewError("");
    getReaderPreview(documentId, version, controller.signal).then(setPreview).catch((reason) => {
      if (!controller.signal.aborted) setPreviewError(reason instanceof Error ? reason.message : "Preview unavailable.");
    });
    return () => controller.abort();
  }, [audit, documentId, version]);
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
              <button type="button" aria-pressed={version === "repaired"} onClick={() => setVersion("repaired")}>Working copy</button>
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
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof getDocumentPreview>>>();
  const [loadingLayout, setLoadingLayout] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    const readable = getDocumentPreview(documentId, controller.signal, false).then((result) => {
      if (!controller.signal.aborted) setPreview((current) => current ?? result);
    });
    const formatted = getDocumentPreview(documentId, controller.signal).then((result) => {
      if (!controller.signal.aborted) setPreview(result);
    });
    void Promise.allSettled([readable, formatted]).then(() => {
      if (!controller.signal.aborted) setLoadingLayout(false);
    });
    return () => controller.abort();
  }, [documentId]);

  return <section className="document-preview" aria-labelledby="document-preview-heading">
    <h2 id="document-preview-heading">Document preview</h2>
    {preview ? <>
      <p>{preview.filename} · Working copy</p>
      {preview.pages?.length ? <>
        <div className="document-pages" role="region" aria-label="Working copy page layout" tabIndex={0}>
          {preview.pages.map((page, index) => <img key={index} src={page} alt={`Page ${index + 1}`} loading="lazy" />)}
        </div>
        {preview.truncated && <p>Showing the first {preview.pages.length} pages.</p>}
        <p><a href="#screen-reader-view">Read this document in the screen reader view</a></p>
      </> : <>
        <p role="status">{loadingLayout ? "Loading formatted pages…" : "Showing a simplified preview."}</p>
        <iframe title={`Working copy of ${preview.filename}`} sandbox="" srcDoc={preview.html} />
      </>}
    </> : <p role="status">{loadingLayout ? "Loading document preview…" : "The document preview could not be loaded."}</p>}
  </section>;
}
