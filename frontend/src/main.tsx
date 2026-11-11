import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuditDashboard } from "./pages/AuditDashboard";
import { ComparePage } from "./pages/ComparePage";
import { ExportPage } from "./pages/ExportPage";
import { FixPage } from "./pages/FixPage";
import { Landing } from "./pages/Landing";
import { Upload } from "./pages/Upload";
import { KeyboardHelp } from "./components/KeyboardHelp";
import { WorkflowSteps } from "./components/WorkflowSteps";
import "./styles/base.css";

const auditRoute = /^\/audit\/([^/]+)\/?$/.exec(window.location.pathname);
const fixRoute = /^\/fix\/([^/]+)\/([^/]+)\/?$/.exec(window.location.pathname);
const compareRoute = /^\/compare\/([^/]+)\/?$/.exec(window.location.pathname);
const exportRoute = /^\/export\/([^/]+)\/?$/.exec(window.location.pathname);
const isLanding = window.location.pathname === "/";
const step = exportRoute ? "Export" : compareRoute ? "Re-audit" : fixRoute ? "Fix" : auditRoute ? "Audit" : "Upload";
if (isLanding) document.title = "A11yra | Check Word documents";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <a className="skip-link" href="#main">Skip to main content</a>
    <header className="site-header">
      <nav className="site-nav" aria-label="Main">
        <a className="wordmark" href="/">A11yra</a>
        {step !== "Upload" && <a className="nav-upload" href="/upload">Upload another document</a>}
      </nav>
      {!isLanding && <WorkflowSteps current={step} />}
    </header>
    {isLanding ? <Landing />
      : exportRoute ? <ExportPage documentId={exportRoute[1]} />
      : fixRoute ? <FixPage documentId={fixRoute[1]} findingId={fixRoute[2]} />
      : compareRoute ? <ComparePage documentId={compareRoute[1]} />
      : auditRoute ? <AuditDashboard documentId={auditRoute[1]} /> : <Upload />}
    <KeyboardHelp />
  </StrictMode>,
);
