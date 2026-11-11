import { useRef } from "react";

export function KeyboardHelp() {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  function openHelp() {
    trigger.current?.focus();
    dialog.current?.showModal();
  }

  return (
    <footer className="site-footer">
      <button ref={trigger} type="button" onClick={openHelp}>Keyboard help</button>
      <dialog ref={dialog} aria-labelledby="keyboard-help-heading">
        <h2 id="keyboard-help-heading">Keyboard help</h2>
        <ul>
          <li>Press Tab or Shift+Tab to move between controls.</li>
          <li>On the audit dashboard, use the up and down arrow keys to switch checks. Home and End jump to the first and last checks.</li>
          <li>Press Enter to follow a link, and Escape to close this help.</li>
        </ul>
        <button type="button" autoFocus onClick={() => dialog.current?.close()}>Close keyboard help</button>
      </dialog>
    </footer>
  );
}
