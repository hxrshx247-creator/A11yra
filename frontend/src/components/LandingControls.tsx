import { Button } from "./Button";
import { usePreferences } from "../hooks/usePreferences";
import type { Motion } from "../hooks/usePreferences";

export function LandingControls() {
  const { resolvedTheme, setTheme, motion, setMotion } = usePreferences();
  return <div className="landing-controls">
    <select className="theme-select" aria-label="Motion" value={motion}
      onChange={(event) => setMotion(event.currentTarget.value as Motion)}>
      <option value="full">Motion: on</option>
      <option value="off">Motion: off</option>
    </select>
    <Button variant="secondary" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
      {resolvedTheme === "dark" ? "Light mode" : "Dark mode"}
    </Button>
  </div>;
}
