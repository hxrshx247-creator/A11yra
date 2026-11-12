import { createContext, useContext, useEffect, useState } from "react";
import { ApiError, productRequest } from "../api/client";
import type { Profile, Workspace } from "../types/product";

export const WorkspaceContext = createContext<{ profile: Profile; workspace: Workspace } | null>(null);

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error("A signed-in workspace is required.");
  return context;
}

export function useProduct<T>(path: string | null) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ path: string; data?: T; error?: string; status?: number }>();
  useEffect(() => {
    if (!path) return;
    let active = true;
    productRequest<T>(path).then((data) => {
      if (active) setResult({ path, data });
    }).catch((reason) => {
      if (active) setResult({
        path, error: errorMessage(reason), status: reason instanceof ApiError ? reason.status : undefined,
      });
    });
    return () => { active = false; };
  }, [path, revision]);
  const current = result?.path === path ? result : undefined;
  return { data: current?.data, error: current?.error, status: current?.status, refresh: () => setRevision((value) => value + 1) };
}

export function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "Something went wrong. Try again.";
}

export function formatDate(date: string) {
  const utc = /(?:Z|[+-]\d\d:\d\d)$/.test(date) ? date : date + "Z";
  return new Date(utc).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
