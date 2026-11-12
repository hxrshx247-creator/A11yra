(() => {
  let mode, theme;
  try {
    mode = localStorage.getItem("a11yra:prefs:v1");
    theme = localStorage.getItem("a11yra-theme");
  } catch {}

  const root = document.documentElement;
  root.dataset.theme = theme === "light" || theme === "dark" ? theme
    : matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  root.dataset.motion = mode === "full" ? "full"
    : mode === "off" || mode === "reduced" || matchMedia("(prefers-reduced-motion: reduce)").matches ? "off" : "full";
  for (const event of ["pageswap", "pagereveal"]) {
    window.addEventListener(event, (change) => {
      change.viewTransition?.ready.catch(() => {});
      if (root.dataset.motion !== "full") change.viewTransition?.skipTransition();
    });
  }
})();
