import type { Audit, Fix, FixResponse, ReaderPreview, ReauditResponse, UploadResponse } from "../types/contract";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

const unsafe = new Set(["POST", "PATCH", "DELETE", "PUT"]);
const noRefresh = new Set(["/api/auth/login", "/api/auth/signup", "/api/auth/forgot", "/api/auth/reset",
  "/api/auth/verify", "/api/auth/logout", "/api/auth/refresh"]);
let refreshing: Promise<Response> | undefined;
let bootstrap: Promise<string> | undefined;

function readCsrf() {
  return document.cookie.split("; ").find((part) => part.startsWith("a11yra_csrf="))?.slice(12);
}

async function csrfToken(reissue = false) {
  const existing = readCsrf();
  if (existing && !reissue) return existing;
  bootstrap ??= fetch("/api/auth/csrf").then((response) =>
    readJson<{ csrf_token: string }>(response, "The session could not be prepared."),
  ).then((result) => result.csrf_token).finally(() => { bootstrap = undefined; });
  return bootstrap;
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const isMutation = unsafe.has(init.method ?? "GET");
  const send = async () => {
    if (isMutation) headers.set("X-CSRF-Token", await csrfToken());
    return fetch(path, { ...init, headers, credentials: "same-origin" });
  };
  let first = await send();
  if (isMutation && first.status === 403 &&
      (await first.clone().json().catch(() => null))?.error?.code === "csrf_failed") {
    await csrfToken(true);
    first = await send();
  }
  if (first.status !== 401 || noRefresh.has(path)) return first;
  const refresh = refreshing ??= apiFetch("/api/auth/refresh", { method: "POST" })
    .finally(() => { refreshing = undefined; });
  return (await refresh).ok ? send() : first;
}

export async function productRequest<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await apiFetch(path, {
    method, ...(body === undefined ? {} : {
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),
  });
  if (response.status === 204) return undefined as T;
  return readJson(response, "The request could not be completed. Try again.");
}

export async function downloadProductFile(path: string, filename: string) {
  const response = await apiFetch(path);
  if (!response.ok) return readJson(response, "The file could not be downloaded.");
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function selectedWorkspace(): string | null {
  return sessionStorage.getItem("a11yra-workspace");
}

export function selectWorkspace(id: string) {
  sessionStorage.setItem("a11yra-workspace", id);
}

function workspaceHeaders() {
  const workspace = selectedWorkspace();
  return workspace ? { "X-Workspace-Id": workspace } : undefined;
}

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(payload?.error?.message ?? fallback, response.status);
  }
  return response.json();
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const body = new FormData();
  body.append("file", file);

  const response = await apiFetch("/api/documents", { method: "POST", body, headers: workspaceHeaders() });
  return readJson(response, "The server could not upload the file. Try again.");
}

export async function uploadSample(kind: "syllabus" | "lecture" | "messy" = "syllabus"): Promise<UploadResponse> {
  const response = await apiFetch(`/api/documents/sample?kind=${kind}`, { method: "POST", headers: workspaceHeaders() });
  return readJson(response, "The sample document could not be opened.");
}

export async function getAudit(documentId: string, signal: AbortSignal): Promise<Audit> {
  const response = await apiFetch(`/api/documents/${encodeURIComponent(documentId)}/audit`, { signal });
  return readJson(response, "The server could not open this audit. Try again.");
}

export async function getReaderPreview(documentId: string, version: "original" | "repaired", signal: AbortSignal): Promise<ReaderPreview> {
  const response = await apiFetch(`/api/documents/${encodeURIComponent(documentId)}/reader-preview?version=${version}`, { signal });
  return readJson(response, "The screen reader preview could not be loaded.");
}

export async function getDocumentPreview(documentId: string, signal: AbortSignal, mode: "layout" | "readable" | "flagged" = "layout"): Promise<{
  filename: string; html: string; pages?: string[]; truncated?: boolean;
}> {
  const query = mode === "flagged" ? "annotated=true" : `layout=${mode === "layout"}`;
  const response = await apiFetch(`/api/documents/${encodeURIComponent(documentId)}/preview?${query}`, { signal });
  return readJson(response, "The document preview could not be loaded.");
}

export async function submitFix(documentId: string, fix: Fix): Promise<FixResponse> {
  const response = await apiFetch(`/api/documents/${encodeURIComponent(documentId)}/fixes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fixes: [fix] }),
  });
  return readJson(response, "The server could not apply this fix. Try again.");
}

export async function dismissHeadingCandidate(documentId: string, findingId: string): Promise<void> {
  await productRequest(`/api/documents/${encodeURIComponent(documentId)}/findings/${encodeURIComponent(findingId)}/dismiss`, "POST");
}

export async function runReaudit(documentId: string): Promise<ReauditResponse> {
  const response = await apiFetch(`/api/documents/${encodeURIComponent(documentId)}/reaudit`, {
    method: "POST",
  });
  return readJson(response, "The server could not run a new audit. Try again.");
}

export async function downloadDocx(documentId: string): Promise<Blob> {
  const response = await apiFetch(`/api/documents/${encodeURIComponent(documentId)}/export/docx`);
  if (!response.ok) return readJson(response, "The repaired document could not be downloaded.");
  return response.blob();
}

export async function downloadLearnerHtml(documentId: string, offline: boolean): Promise<Blob> {
  const response = await apiFetch(
    `/api/documents/${encodeURIComponent(documentId)}/export/html?offline=${offline}`,
  );
  if (!response.ok) return readJson(response, "The learner reader could not be downloaded.");
  return response.blob();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await apiFetch(`/api/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
  if (!response.ok) await readJson(response, "The upload could not be deleted. Try again.");
}
