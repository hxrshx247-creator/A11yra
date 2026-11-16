import { PageHeading } from "../components/PageHeading";
import { useRef, useState } from "react";
import type { DragEvent, FormEvent } from "react";
import { uploadDocument, uploadSample } from "../api/client";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { usePageHeading } from "../hooks/usePageHeading";
import { useProduct, useWorkspace } from "../hooks/useProduct";
import type { Usage } from "../types/product";

const MAX_UPLOAD_BYTES = 10_000_000;
const DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function validate(file: File | null) {
  if (!file) return "";
  if (!/\.docx$/i.test(file.name) || (file.type && ![DOCX_MIME, "application/octet-stream"].includes(file.type))) {
    return "Choose a Word document ending in .docx.";
  }
  return file.size > MAX_UPLOAD_BYTES ? "This file exceeds 10 MB. Choose a smaller Word document." : "";
}

function readableSize(size: number) {
  if (size < 1000) return `${size} bytes`;
  const megabytes = size >= 1_000_000;
  const value = size / (megabytes ? 1_000_000 : 1000);
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)} ${megabytes ? "MB" : "kB"}`;
}

export function Upload() {
  const heading = usePageHeading("Upload a Word document");
  const { workspace } = useWorkspace();
  const { data: usage } = useProduct<Usage>(`/api/workspaces/${workspace.id}/usage`);
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState("");
  const problem = validate(file) || message;

  async function openSample() {
    setPending(true);
    setMessage("");
    try {
      const result = await uploadSample("messy");
      location.assign(`/audit/${result.document_id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The sample could not be opened.");
    } finally {
      setPending(false);
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (pending || !input.current) return;
    const files = event.dataTransfer.files;
    if (files.length !== 1) {
      input.current.value = "";
      setFile(null);
      setMessage("Choose one Word document at a time.");
      return;
    }
    input.current.files = files;
    setFile(files[0]);
    setMessage("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || validate(file) || pending) return;
    setMessage("");
    setPending(true);
    try {
      const result = await uploadDocument(file);
      window.location.assign(`/audit/${encodeURIComponent(result.document_id)}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The upload failed. Try again.");
    } finally {
      setPending(false);
    }
  }

  return <main id="main" className="upload-page" tabIndex={-1}>
    <PageHeading headingRef={heading} title="Upload a Word document" eyebrow="Document engine"
      description="Start with the handout, notes, or syllabus you want students to read." />
    {usage && import.meta.env.VITE_SHOW_ADVANCED === "true" && <p className="workspace-usage">You’ve used <strong>{usage.documents_used} of {usage.plan.documents_per_month}</strong> documents this month. <a href="/pricing">See plans</a></p>}
    {workspace.role === "viewer" ? <p>Your workspace role allows you to view audits. {import.meta.env.VITE_SHOW_ADVANCED === "true" && <a href="/workspace">Back to workspace</a>}</p> :
    <form className="upload-form" onSubmit={handleSubmit}>
      <div className="drop-zone" data-dragging={dragging} onDrop={onDrop}
        onDragOver={(event) => { event.preventDefault(); if (!pending) setDragging(true); }}
        onDragLeave={(event) => {
          if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) setDragging(false);
        }}>
        <Icon name="upload" />
        <label htmlFor="document">Word document (required)</label>
        <p id="file-help">Drop a file here or choose a .docx file up to {usage ? usage.plan.max_file_bytes / 1_000_000 : 10} MB.</p>
        <input ref={input} id="document" name="file" type="file" accept={`.docx,${DOCX_MIME}`}
          aria-describedby="file-help selected-file upload-status" aria-invalid={problem ? true : undefined}
          required disabled={pending}
          onChange={(event) => { setFile(event.currentTarget.files?.[0] ?? null); setMessage(""); }} />
      </div>
      <div className="upload-feedback">
        <p id="selected-file">{file ? `${file.name} · ${readableSize(file.size)}` : ""}</p>
        <p id="upload-status" role="status" className={problem ? "form-error" : "status"}>
          {problem && <Icon name="error" />}
          {pending ? "Uploading and checking your document…" : problem}
        </p>
        {pending && <div className="upload-track" aria-hidden="true" />}
      </div>
      <div className="product-actions">
        <Button type="submit" aria-disabled={pending || Boolean(validate(file))}>Upload document</Button>
        <Button variant="secondary" disabled={pending} onClick={openSample}>Try a messy handout for demo/judging purposes</Button>
      </div>
      <p className="retention">Uploads are stored privately. Working files expire after {usage?.file_hours ?? 24} hours; you can delete a document sooner from its audit page. <a href="/privacy">Retention and privacy</a></p>
    </form>}
  </main>;
}
