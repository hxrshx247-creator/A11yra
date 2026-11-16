import { useEffect, useRef, useState } from "react";
import { getDocumentPreview } from "../api/client";
import type { Finding } from "../types/contract";

export function DocumentPreview({ documentId, findings, currentFindingId }: {
  documentId: string;
  findings: Finding[];
  currentFindingId?: string;
}) {
  const openFindings = findings.filter((finding) => finding.status === "open" || finding.status === "needs_review");
  const [mode, setMode] = useState<"flagged" | "layout">(openFindings.length ? "flagged" : "layout");

  return <section className="document-preview" aria-labelledby="document-preview-heading">
    <h2 id="document-preview-heading">Document preview</h2>
    <div className="reader-preview-tabs" role="group" aria-label="Document preview mode">
      <button type="button" aria-pressed={mode === "flagged"} onClick={() => setMode("flagged")}>Flagged preview</button>
      <button type="button" aria-pressed={mode === "layout"} onClick={() => setMode("layout")}>Word layout</button>
    </div>
    {mode === "flagged"
      ? <FlaggedPreview documentId={documentId} findings={openFindings} currentFindingId={currentFindingId} />
      : <WordLayout documentId={documentId} />}
  </section>;
}

function FlaggedPreview({ documentId, findings, currentFindingId }: {
  documentId: string;
  findings: Finding[];
  currentFindingId?: string;
}) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof getDocumentPreview>>>();
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState(currentFindingId);

  useEffect(() => {
    const controller = new AbortController();
    getDocumentPreview(documentId, controller.signal, "flagged").then((result) => {
      if (!controller.signal.aborted) setPreview(result);
    }).catch(() => {
      if (!controller.signal.aborted) setError(true);
    });
    return () => controller.abort();
  }, [documentId]);

  function showFlag(id: string, focus = false) {
    const mark = frame.current?.contentDocument?.getElementById("finding-" + id);
    const view = frame.current?.contentWindow;
    if (!mark || !view) return;
    if (focus) mark.focus({ preventScroll: true });
    view.scrollTo(0, view.scrollY + mark.getBoundingClientRect().top - 20);
  }

  if (!preview) return <p role="status">{error ? "The flagged preview could not be loaded." : "Loading flagged preview…"}</p>;

  return <>
    <p>{preview.filename} · Working copy</p>
    {findings.length ? <ul className="preview-flags" aria-label="Findings in the preview">
      {findings.map((finding) => (
        <li key={finding.id}>
          <button type="button" aria-pressed={selected === finding.id} onClick={() => {
            setSelected(finding.id);
            showFlag(finding.id, true);
          }}>⚑ {finding.location}</button>
        </li>
      ))}
    </ul> : <p>No unresolved findings to flag.</p>}
    <iframe ref={frame} title={`Flagged preview of ${preview.filename}`} sandbox="allow-same-origin" srcDoc={preview.html}
      onLoad={() => { if (selected) showFlag(selected); }} />
  </>;
}
function WordLayout({ documentId }: { documentId: string }) {
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof getDocumentPreview>>>();
  const [loadingLayout, setLoadingLayout] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    const readable = getDocumentPreview(documentId, controller.signal, "readable").then((result) => {
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

  return <div>

    {preview ? <>
      <p>{preview.filename} · Working copy</p>
      {preview.pages?.length ? <>
        <div className="document-pages" role="region" aria-label="Working copy page layout" tabIndex={0}>
          {preview.pages.map((page, index) => <img key={index} src={page} alt={`Page ${index + 1}`} loading="lazy" />)}
        </div>
        {preview.truncated && <p>Showing the first {preview.pages.length} pages.</p>}

      </> : <>
        <p role="status">{loadingLayout ? "Loading formatted pages…" : "Showing a simplified preview."}</p>
        <iframe title={`Working copy of ${preview.filename}`} sandbox="" srcDoc={preview.html} />
      </>}
    </> : <p role="status">{loadingLayout ? "Loading document preview…" : "The document preview could not be loaded."}</p>}
  </div>;
}
