import type { Audit, Fix, FixResponse, ReauditResponse, UploadResponse } from "../types/contract";

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error?.message ?? fallback);
  }
  return response.json();
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const body = new FormData();
  body.append("file", file);

  const response = await fetch("/api/documents", { method: "POST", body });
  return readJson(response, "The server could not upload the file. Try again.");
}

export async function getAudit(documentId: string, signal: AbortSignal): Promise<Audit> {
  const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}/audit`, { signal });
  return readJson(response, "The server could not open this audit. Try again.");
}

export async function submitFix(documentId: string, fix: Fix): Promise<FixResponse> {
  const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}/fixes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fixes: [fix] }),
  });
  return readJson(response, "The server could not apply this fix. Try again.");
}

export async function runReaudit(documentId: string): Promise<ReauditResponse> {
  const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}/reaudit`, {
    method: "POST",
  });
  return readJson(response, "The server could not run a new audit. Try again.");
}

export async function downloadDocx(documentId: string): Promise<Blob> {
  const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}/export/docx`);
  if (!response.ok) return readJson(response, "The repaired document could not be downloaded.");
  return response.blob();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
  if (!response.ok) await readJson(response, "The upload could not be deleted. Try again.");
}
