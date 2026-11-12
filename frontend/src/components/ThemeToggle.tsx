import { usePreferences } from "../hooks/usePreferences";
import type { Theme } from "../hooks/usePreferences";

export function ThemeToggle() {
  const { theme, setTheme } = usePreferences();
  return <label className="theme-control">
    Theme
    <select className="theme-select" value={theme} onChange={(event) => setTheme(event.currentTarget.value as Theme)}>
      <option value="system">System</option>
      <option value="light">Light</option>
      <option value="dark">Dark</option>
    </select>
  </label>;
}
