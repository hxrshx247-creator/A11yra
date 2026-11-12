import { useEffect } from "react";
import type { ReactNode } from "react";
import { productRequest, selectedWorkspace, selectWorkspace } from "../api/client";
import { useProduct, WorkspaceContext } from "../hooks/useProduct";
import type { Profile } from "../types/product";
import { Button } from "./Button";
import { ProductPage, ProductStatus } from "./ProductPage";

export function WorkspaceGate({ children }: { children: ReactNode }) {
  const { data: profile, error, status, refresh } = useProduct<Profile>("/api/auth/me");
  const needsSignIn = status === 401;

  useEffect(() => {
    if (needsSignIn) {
      const next = encodeURIComponent(location.pathname + location.search + location.hash);
      location.replace(`/account/login?next=${next}`);
    }
  }, [needsSignIn]);

  if (!profile) {
    if (error && !needsSignIn) return <ProductPage title="Workspace unavailable">
      <ProductStatus error={error} />
      <div><Button variant="secondary" onClick={refresh}>Reload workspace</Button></div>
    </ProductPage>;
    return <main id="main" tabIndex={-1}>
      <p role="status">{needsSignIn ? "Opening sign-in…" : "Opening your workspace…"}</p>
    </main>;
  }
  const selected = selectedWorkspace();
  const workspace = profile.workspaces.find((item) => item.id === selected)
    ?? profile.workspaces.find((item) => item.personal) ?? profile.workspaces[0];
  if (!workspace) return <ProductPage title="Workspace unavailable" />;
  if (selected !== workspace.id) selectWorkspace(workspace.id);
  return <WorkspaceContext.Provider value={{ profile, workspace }}>{children}</WorkspaceContext.Provider>;
}

export async function signOut() {
  await productRequest("/api/auth/logout", "POST");
  sessionStorage.removeItem("a11yra-workspace");
  location.assign("/");
}
