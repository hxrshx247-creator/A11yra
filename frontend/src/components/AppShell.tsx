import { useRef } from "react";
import type { ReactNode } from "react";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { LandingControls } from "./LandingControls";
import { Icon } from "./Icon";
import { SettingsDialog } from "./SettingsDialog";
import { ThemeToggle } from "./ThemeToggle";
import { Stepper } from "./Stepper";
import type { WorkflowStep } from "./Stepper";

export function AppShell({ landing, publicPage, step, children }: {
  landing: boolean; publicPage: boolean; step?: WorkflowStep; children: ReactNode;
}) {
  const help = useRef<HTMLDialogElement>(null);
  const settings = useRef<HTMLDialogElement>(null);
  const openSettings = () => settings.current?.showModal();
  const brand = <a className="wordmark" href="/"><span className="brand-mark" aria-hidden="true" />A11yra</a>;
  const path = location.pathname;
  const showAdvanced = import.meta.env.VITE_SHOW_ADVANCED === "true";

  return <>
    <a className="skip-link" href="#main">Skip to main content</a>
    <header className={publicPage ? "site-header site-header--public" : "site-header"}>
      {publicPage ? <div className="site-nav">
        {brand}
        <nav className="public-nav" aria-label="Main">
          <a href={landing ? "#engine" : "/#engine"}>Engine</a>
          <a href={landing ? "#checks" : "/#checks"}>Checks</a>
          <a href={landing ? "#reader" : "/#reader"}>Reader</a>
          {showAdvanced && <a href="/workspace">Workspace</a>}
        </nav>
        <LandingControls />
      </div> : <nav className="site-nav" aria-label="Main">
        {brand}
        <div className="header-actions">
          {showAdvanced && <a className="nav-upload" href="/workspace" aria-current={path.startsWith("/workspace") ? "page" : undefined}>Workspace</a>}
          {step && step !== "Upload" && <a className="nav-upload" href="/upload">Upload another document</a>}
          <ThemeToggle />
          <Button variant="secondary" onClick={openSettings}><Icon name="settings" /> Settings</Button>
        </div>
      </nav>}
      {step && <Stepper current={step} />}
    </header>
    {children}
    <footer className="site-footer">
      <span className="footer-name">A11yra</span>
      <nav className="product-footer-links" aria-label="About A11yra">
        {showAdvanced && <a href="/pricing" aria-current={path === "/pricing" ? "page" : undefined}>Pricing</a>}
        <a href="/security">Security &amp; privacy</a>
        <a href="/accessibility">Accessibility</a>
        <a href="/privacy">Privacy policy</a>
        <a href="/terms">Terms</a>
        <a href="/support">Support</a>
        <a href="/changelog">Changelog</a>
        <a href="/status">Status</a>
      </nav>
      <div>
        <Button variant="quiet" onClick={() => help.current?.showModal()}>Keyboard help</Button>
        <Button variant="quiet" onClick={openSettings}>Settings</Button>
      </div>
    </footer>
    <Dialog dialogRef={help} title="Keyboard help" closeLabel="Close keyboard help">
      <ul>
        <li>Press Tab or Shift+Tab to move between controls.</li>
        <li>In the audit, use Up and Down to switch checks. Home and End jump to the first and last checks.</li>
        <li>Press Enter to follow a link and Escape to close this help.</li>
      </ul>
    </Dialog>
    <SettingsDialog dialogRef={settings} />
  </>;
}
