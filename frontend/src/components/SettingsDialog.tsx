import { useState } from "react";
import type { RefObject } from "react";
import { usePreferences } from "../hooks/usePreferences";
import { Dialog } from "./Dialog";

const choices = [
  ["full", "Motion on", "Use scroll effects and transitions."],
  ["off", "Motion off", "Show changes immediately."],
] as const;

export function SettingsDialog({ dialogRef }: { dialogRef: RefObject<HTMLDialogElement | null> }) {
  const { motion, setMotion } = usePreferences();
  const [announcement, setAnnouncement] = useState("");
  return <Dialog dialogRef={dialogRef} title="Settings" closeLabel="Close settings">
    <fieldset className="motion-options">
      <legend>Motion</legend>
      {choices.map(([value, label, help]) => <div key={value} className="motion-choice">
        <label className="choice">
          <input type="radio" name="motion" checked={motion === value}
            aria-describedby={`motion-${value}-help`}
            onChange={() => { setMotion(value); setAnnouncement(`${label} selected.`); }} />
          {label}
        </label>
        <p id={`motion-${value}-help`}>{help}</p>
      </div>)}
    </fieldset>
    <p className="status" role="status">{announcement}</p>
  </Dialog>;
}
