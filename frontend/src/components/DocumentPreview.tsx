import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getDocumentPreview } from "../api/client";
import type { Finding } from "../types/contract";

type Preview = Awaited<ReturnType<typeof getDocumentPreview>>;

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
  const pagesRegion = useRef<HTMLDivElement>(null);
  const [readable, setReadable] = useState<Preview>();
  const [formatted, setFormatted] = useState<Preview>();
  const [pending, setPending] = useState(true);
  const [selected, setSelected] = useState(currentFindingId);
  const positions = formatted?.positions;
  const showPages = Boolean(formatted?.pages?.length && (!selected || positions?.[selected] || !readable));

  useEffect(() => {
    const controller = new AbortController();
    const html = getDocumentPreview(documentId, controller.signal, "flagged").then((result) => {
      if (!controller.signal.aborted) setReadable(result);
    });
    const pages = getDocumentPreview(documentId, controller.signal, "formatted-flags").then((result) => {
      if (!controller.signal.aborted) setFormatted(result);
    });
    void Promise.allSettled([html, pages]).then(() => {
      if (!controller.signal.aborted) setPending(false);
    });
    return () => controller.abort();
  }, [documentId]);

  useLayoutEffect(() => {
    const region = pagesRegion.current;
    const position = selected && positions?.[selected];
    if (!region || !position) return;
    const page = region.children[position.page - 1];
    if (page) {
      const offset = page.getBoundingClientRect().top - region.getBoundingClientRect().top;
      region.scrollTop += offset + (page.clientHeight * position.y / 100) - 30;
    }
  }, [showPages, positions, selected]);

  function showFlag(id: string, focus = false) {
    const mark = frame.current?.contentDocument?.getElementById("finding-" + id);
    const view = frame.current?.contentWindow;
    if (!mark || !view) return;
    if (focus) mark.focus({ preventScroll: true });
    view.scrollTo(0, view.scrollY + mark.getBoundingClientRect().top - 20);
  }

  const preview = readable ?? formatted;
  if (!preview) return <p role="status">{pending ? "Loading flagged preview…" : "The flagged preview could not be loaded."}</p>;

  return <>
    <p>{preview.filename} · Working copy</p>
    {findings.length ? <ul className="preview-flags" aria-label="Findings in the preview">
      {findings.map((finding, index) => (
        <li key={finding.id}>
          <button type="button" aria-pressed={selected === finding.id} onClick={() => {
            setSelected(finding.id);
            if (!positions?.[finding.id]) showFlag(finding.id, true);
          }}>⚑ {index + 1}. {finding.location}</button>
        </li>
      ))}
    </ul> : <p>No unresolved findings to flag.</p>}
    {showPages ? <>
      <div className="document-pages" role="region" aria-label="Flagged Word pages" tabIndex={0} ref={pagesRegion}>
        {formatted?.pages?.map((page, index) => {
          // The PNG header contains dimensions, which reserve each page's space before lazy loading.
          const header = atob(page.slice("data:image/png;base64,".length, "data:image/png;base64,".length + 32));
          const dimensions = new DataView(Uint8Array.from(header, (byte) => byte.charCodeAt(0)).buffer);
          return <div key={index} className="flagged-word-page">
            <img src={page} alt={`Page ${index + 1}`} loading="lazy"
              width={dimensions.getUint32(16)} height={dimensions.getUint32(20)} />
            {findings.map((finding, flagIndex) => {
              const position = positions?.[finding.id];
              return position?.page === index + 1 && <span key={finding.id} aria-hidden="true"
                className="word-page-flag" data-selected={selected === finding.id}
                style={{ left: `${position.x}%`, top: `${position.y}%` }}>⚑ {flagIndex + 1}</span>;
            })}
          </div>;
        })}
      </div>
      {selected && !positions?.[selected] && <p role="status">This flag could not be placed on a formatted page.</p>}
      {formatted?.truncated && <p>Showing the first {formatted.pages?.length} pages.</p>}
    </> : <>
      <p role="status">{pending ? "Loading formatted pages…" : "Showing a readable preview for this location."}</p>
      <iframe ref={frame} title={`Flagged preview of ${preview.filename}`} sandbox="allow-same-origin"
        srcDoc={readable?.html || formatted?.html}
        onLoad={() => { if (selected) showFlag(selected); }} />
    </>}
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
