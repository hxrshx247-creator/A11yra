import { useState } from "react";
import type { FormEvent } from "react";
import { uploadDocument } from "../api/client";

const MAX_UPLOAD_BYTES = 10_000_000;

export function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const fileTooLarge = file !== null && file.size > MAX_UPLOAD_BYTES;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || fileTooLarge || pending) return;

    setPending(true);
    setMessage("Uploading and checking your document…");
    try {
      const result = await uploadDocument(file);
      window.location.assign(`/audit/${encodeURIComponent(result.document_id)}`);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "The upload failed. Try again.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main id="main" tabIndex={-1}>
      <h1>Upload a Word document</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="document">Word document (required)</label>
        <p id="file-help">Choose a .docx file up to 10 MB.</p>
        <input
          id="document"
          name="file"
          type="file"
          accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          aria-describedby={fileTooLarge ? "file-help upload-status" : "file-help"}
          aria-invalid={fileTooLarge || undefined}
          required
          disabled={pending}
          onChange={(event) => {
            setFile(event.currentTarget.files?.[0] ?? null);
            setMessage("");
          }}
        />
        <button type="submit" aria-disabled={pending || fileTooLarge}>Upload document</button>
      </form>
      <p>Uploads are temporary. The server clears them after download or after 60 minutes.</p>
      <p id="upload-status" className="status" role="status">
        {fileTooLarge ? "This file exceeds 10 MB. Choose a smaller Word document." : message}
      </p>
    </main>
  );
}
