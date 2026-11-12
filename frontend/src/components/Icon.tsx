const PATHS = {
  success: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.6 2.6 5.4-5.4" /></>,
  error: <><path d="M8 3h8l5 5v8l-5 5H8l-5-5V8Z" fill="currentColor" stroke="none" /><path d="M12 7v6m0 3v.1" stroke="var(--status-error-fill, white)" /></>,
  review: <><path d="m12 2 10 10-10 10L2 12Z" /><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 1.5-2.5 2-2.5 4m0 3v.1" /></>,
  warning: <><path d="m12 3 10 18H2Z" /><path d="M12 9v5m0 3v.1" /></>,
  open: <circle cx="12" cy="12" r="7" />,
  unchecked: <path d="M5 12h14" />,
  waiting: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v.1" /></>,
  upload: <><path d="M12 16V3m-4 4 4-4 4 4M4 15v5h16v-5" /></>,
  settings: <><path d="M4 6h16M4 12h16M4 18h16" /><path d="M9 3v6m6 0v6m-6 0v6" strokeWidth="3" /></>,
  arrow: <path d="M4 12h15m-6-6 6 6-6 6" />,
};

export function Icon({ name }: { name: keyof typeof PATHS }) {
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{PATHS[name]}</svg>;
}
