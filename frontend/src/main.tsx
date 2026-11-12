import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuditDashboard } from "./pages/AuditDashboard";
import { ComparePage } from "./pages/ComparePage";
import { ExportPage } from "./pages/ExportPage";
import { FixPage } from "./pages/FixPage";
import { Landing } from "./pages/Landing";
import { Upload } from "./pages/Upload";
import { AccountPage, AccountSettings } from "./pages/AccountPage";
import type { AccountMode } from "./pages/AccountPage";
import { DocumentHistory } from "./pages/DocumentHistory";
import { Pricing, PublicPage, publicRoutes } from "./pages/PublicPages";
import type { PublicRoute } from "./pages/PublicPages";
import { WorkspacePage } from "./pages/WorkspacePage";
import type { WorkspaceSection } from "./pages/WorkspacePage";
import { AppShell } from "./components/AppShell";
import { WorkspaceGate } from "./components/WorkspaceGate";
import { PreferencesProvider } from "./hooks/usePreferences";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/layout.css";
import "./styles/product.css";
import "./styles/landing.css";

const auditRoute = /^\/audit\/([^/]+)\/?$/.exec(window.location.pathname);
const fixRoute = /^\/fix\/([^/]+)\/([^/]+)\/?$/.exec(window.location.pathname);
const compareRoute = /^\/compare\/([^/]+)\/?$/.exec(window.location.pathname);
const exportRoute = /^\/export\/([^/]+)\/?$/.exec(window.location.pathname);
const isLanding = window.location.pathname === "/";
const path = window.location.pathname.replace(/\/$/, "") || "/";
const account = /^\/account\/(login|signup|forgot|reset|verify|invite)$/.exec(path);
const workspace = /^\/workspace(?:\/(dashboard|activity|members|keys))?$/.exec(path);
const history = /^\/history\/([0-9a-f-]{36})$/i.exec(path);
const isWorkflow = Boolean(exportRoute || fixRoute || compareRoute || auditRoute || path === "/upload");
const isPublic = isLanding || Boolean(account) || path === "/pricing" || Object.hasOwn(publicRoutes, path);
const step = exportRoute ? "Export" : compareRoute ? "Re-audit" : fixRoute ? "Fix" : auditRoute ? "Audit" : "Upload";
if (isLanding) document.title = "A11yra | Accessible learning, end to end";

function App() {
  if (isLanding) return <Landing />;
  if (account) return <AccountPage mode={account[1] as AccountMode} />;
  if (path === "/pricing") return <Pricing />;
  if (Object.hasOwn(publicRoutes, path)) return <PublicPage route={path as PublicRoute} />;
  if (path === "/account/settings") return <WorkspaceGate><AccountSettings /></WorkspaceGate>;
  if (workspace) return <WorkspaceGate><WorkspacePage section={(workspace[1] ?? "documents") as WorkspaceSection} /></WorkspaceGate>;
  if (history) return <WorkspaceGate><DocumentHistory id={history[1]} /></WorkspaceGate>;
  if (isWorkflow) return <WorkspaceGate>
    {exportRoute ? <ExportPage documentId={exportRoute[1]} />
      : fixRoute ? <FixPage documentId={fixRoute[1]} findingId={fixRoute[2]} />
      : compareRoute ? <ComparePage documentId={compareRoute[1]} />
      : auditRoute ? <AuditDashboard documentId={auditRoute[1]} /> : <Upload />}
  </WorkspaceGate>;
  return <main id="main" tabIndex={-1}><h1>Page unavailable</h1><a href="/">Return to A11yra</a></main>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PreferencesProvider><AppShell landing={isLanding} publicPage={isPublic} step={isWorkflow ? step : undefined}>
      <App />
    </AppShell></PreferencesProvider>
  </StrictMode>,
);
