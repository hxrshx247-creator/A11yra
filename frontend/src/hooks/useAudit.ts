import { useEffect, useState } from "react";
import { getAudit } from "../api/client";
import type { Audit } from "../types/contract";

export function useAudit(documentId: string) {
  const [audit, setAudit] = useState<Audit>();
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getAudit(documentId, controller.signal)
      .then(setAudit)
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "The audit could not be loaded.");
        }
      });
    return () => controller.abort();
  }, [documentId]);

  return { audit, error };
}
