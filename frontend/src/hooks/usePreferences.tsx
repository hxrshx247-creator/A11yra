import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

export type Motion = "full" | "off";
export type Theme = "light" | "dark" | "system";
const THEME_KEY = "a11yra-theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";
const KEY = "a11yra:prefs:v1";
const QUERY = "(prefers-reduced-motion: reduce)";
const Preferences = createContext<{
  theme: Theme;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
  motion: Motion;
  setMotion: (motion: Motion) => void;
} | null>(null);

function storedMotion(): Motion | null {
  try {
    const value = localStorage.getItem(KEY);
    if (value === "full") return "full";
    if (value === "reduced" || value === "off") return "off";
  } catch { /* Some browsers block local storage. */ }
  return null;
}

function storedTheme(): Theme {
  try {
    const value = localStorage.getItem(THEME_KEY);
    if (value === "light" || value === "dark") return value;
  } catch { /* Some browsers block local storage. */ }
  return "system";
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeChoice] = useState(storedTheme);
  const [systemDark, setSystemDark] = useState(() => matchMedia(DARK_QUERY).matches);
  const resolvedTheme = theme === "system" ? (systemDark ? "dark" : "light") : theme;
  const [choice, setChoice] = useState(storedMotion);
  const [systemReduced, setSystemReduced] = useState(() => matchMedia(QUERY).matches);
  const motion = choice ?? (systemReduced ? "off" : "full");

  useEffect(() => {
    const media = matchMedia(QUERY);
    const sync = () => setSystemReduced(media.matches);
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => { document.documentElement.dataset.motion = motion; }, [motion]);

  useEffect(() => {
    const media = matchMedia(DARK_QUERY);
    const sync = () => setSystemDark(media.matches);
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => { document.documentElement.dataset.theme = resolvedTheme; }, [resolvedTheme]);

  function setTheme(value: Theme) {
    setThemeChoice(value);
    try { localStorage.setItem(THEME_KEY, value); } catch { /* Keep the choice for this page. */ }
  }

  function setMotion(value: Motion) {
    setChoice(value);
    try { localStorage.setItem(KEY, value); } catch { /* Keep the choice for this page. */ }
  }

  return <Preferences.Provider value={{ theme, resolvedTheme, setTheme, motion, setMotion }}>
    {children}
  </Preferences.Provider>;
}

export function usePreferences() {
  const preferences = useContext(Preferences);
  if (!preferences) throw new Error("PreferencesProvider is required");
  return preferences;
}
