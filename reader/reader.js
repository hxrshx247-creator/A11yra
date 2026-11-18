(() => {
  "use strict";

  const contents = document.querySelector("#contents");
  const contentsSummary = contents.querySelector("summary");
  const links = Array.from(document.querySelectorAll("#contents-list a"));
  const sections = links.map((link) => document.getElementById(link.hash.slice(1)));
  const narrow = window.matchMedia("(max-width: 51.99rem)");
  const setContentsLayout = () => { contents.open = !narrow.matches; };
  setContentsLayout();
  narrow.addEventListener("change", setContentsLayout);

  let currentSection = -1;
  function markCurrent(index) {
    currentSection = index;
    links.forEach((link, position) => {
      if (position === index) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }

  let linkScrollOffset;
  function updateCurrent() {
    if (!sections.length || (linkScrollOffset !== undefined &&
        Math.abs(window.scrollY - linkScrollOffset) < 1)) return;
    linkScrollOffset = undefined;
    let current = 0;
    for (let index = 0; index < sections.length; index += 1) {
      if (sections[index].getBoundingClientRect().top <= 80) current = index;
    }
    markCurrent(current);
  }

  links.forEach((link, index) => {
    link.addEventListener("click", (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (narrow.matches) contents.open = false;
      const section = sections[index];
      section.focus({ preventScroll: true });
      section.scrollIntoView({ block: "start" });
      linkScrollOffset = window.scrollY;
      try { history.replaceState(null, "", link.hash); } catch { /* Some file URLs restrict history. */ }
      markCurrent(index);
    });
    link.addEventListener("keydown", (event) => {
      const offsets = { ArrowDown: 1, ArrowUp: -1 };
      if (event.key in offsets) {
        event.preventDefault();
        links[(index + offsets[event.key] + links.length) % links.length].focus();
      } else if (event.key === "Home" || event.key === "End") {
        event.preventDefault();
        links[event.key === "Home" ? 0 : links.length - 1].focus();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        contents.open = false;
        contentsSummary.focus();
      }
    });
  });
  contentsSummary.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      contents.open = event.key === "ArrowRight";
    }
  });

  window.addEventListener("scroll", updateCurrent, { passive: true });
  window.addEventListener("resize", updateCurrent);
  const initial = links.findIndex((link) => link.hash === window.location.hash);
  if (initial >= 0) {
    linkScrollOffset = window.scrollY;
    markCurrent(initial);
  } else {
    updateCurrent();
  }

  const settingsKey = "a11yra-reader-settings-v1";
  const preset = document.querySelector("#reader-preset");
  const root = document.documentElement;
  const selects = {
    size: document.querySelector("#text-size"),
    spacing: document.querySelector("#line-spacing"),
    theme: document.querySelector("#reading-theme"),
    font: document.querySelector("#reading-font"),
  };
  const shortcuts = document.querySelector("#reader-shortcuts");
  const motion = document.querySelector("#reader-motion");
  const motionSource = document.querySelector("#reader-motion-source");
  const motionMedia = window.matchMedia("(prefers-reduced-motion: reduce)");
  const article = document.querySelector("main article");
  const ruler = document.querySelector("#reading-ruler");
  const rulerEnabled = document.querySelector("#ruler-enabled");
  const rulerPosition = document.querySelector("#ruler-position");
  const rulerControls = document.querySelector("#ruler-controls");
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(settingsKey)) || {}; } catch { /* Storage is optional. */ }
  let motionChoice = saved.motion === "full" ? "full"
    : saved.motion === "off" || saved.motion === "reduced" ? "off" : null;
  const presets = {
    "low-vision": { size: "175", spacing: "wide", theme: "contrast", font: "standard", ruler: false },
    dyslexia: { size: "125", spacing: "roomy", theme: "light", font: "spaced", ruler: false },
    focus: { size: "125", spacing: "roomy", theme: "light", font: "standard", ruler: true },
  };

  function positionRuler() {
    ruler.style.setProperty("--ruler-position", rulerPosition.value + "%");
  }

  rulerPosition.addEventListener("input", positionRuler);
  article.parentElement.addEventListener("pointermove", (event) => {
    if (!rulerEnabled.checked || event.pointerType === "touch") return;
    const mainBounds = article.parentElement.getBoundingClientRect();
    const offset = Math.max(0, Math.min(mainBounds.height, event.clientY - mainBounds.top));
    rulerPosition.value = String(100 * offset / mainBounds.height);
    ruler.style.setProperty("--ruler-position", offset + "px");
  });

  function applySettings() {
    const settings = { shortcuts: shortcuts.checked, motion: motionChoice, ruler: rulerEnabled.checked, preset: preset.value };
    const motionMode = motionChoice ?? (motionMedia.matches ? "off" : "full");
    root.dataset.motion = motionMode;
    motion.value = motionMode;
    motionSource.textContent = motionChoice ? "" : "Following your device setting.";
    ruler.hidden = rulerControls.hidden = !rulerEnabled.checked;
    positionRuler();
    for (const [key, select] of Object.entries(selects)) {
      root.dataset[key] = select.value;
      settings[key] = select.value;
    }
    root.dataset.preset = preset.value;
    try { localStorage.setItem(settingsKey, JSON.stringify(settings)); } catch { /* Settings still work in this tab. */ }
  }

  for (const [key, select] of Object.entries(selects)) {
    if (Array.from(select.options).some((option) => option.value === saved[key])) {
      select.value = saved[key];
    }
    select.addEventListener("change", () => { preset.value = "custom"; applySettings(); });
  }
  if (["custom", ...Object.keys(presets)].includes(saved.preset)) preset.value = saved.preset;
  if (preset.value !== "custom") {
    const values = presets[preset.value];
    Object.entries(values).forEach(([key, value]) => {
      if (key === "ruler") rulerEnabled.checked = value;
      else selects[key].value = value;
    });
  }
  preset.addEventListener("change", () => {
    const values = presets[preset.value];
    if (values) Object.entries(values).forEach(([key, value]) => {
      if (key === "ruler") rulerEnabled.checked = value;
      else selects[key].value = value;
    });
    applySettings();
  });
  shortcuts.checked = saved.shortcuts !== false;
  shortcuts.addEventListener("change", applySettings);
  rulerEnabled.checked = saved.ruler === true;
  rulerEnabled.addEventListener("change", () => { preset.value = "custom"; applySettings(); });
  motion.addEventListener("change", () => {
    motionChoice = motion.value;
    applySettings();
  });
  motionMedia.addEventListener("change", () => { if (motionChoice === null) applySettings(); });
  document.querySelector("#reset-settings").addEventListener("click", () => {
    Object.values(selects).forEach((select) => { select.selectedIndex = 0; });
    shortcuts.checked = true;
    rulerEnabled.checked = false;
    rulerPosition.value = rulerPosition.defaultValue;
    motionChoice = null;
    preset.value = "custom";
    applySettings();
  });
  applySettings();

  const shortcutsDialog = document.querySelector("#shortcuts-dialog");
  document.querySelector("#open-shortcuts").addEventListener("click", () => shortcutsDialog.showModal());
  document.querySelector("#close-shortcuts").addEventListener("click", () => shortcutsDialog.close());

  const speechStatus = document.querySelector("#speech-status");
  const synthesis = window.speechSynthesis;
  const speechSupported = Boolean(synthesis && window.SpeechSynthesisUtterance);
  const play = document.querySelector("#speech-play");
  const pause = document.querySelector("#speech-pause");
  const stop = document.querySelector("#speech-stop");
  const readable = "h1,h2,h3,h4,h5,h6,p,li,th,td,caption,blockquote";
  let speechMode = "stopped";
  let utterance;
  let highlighted;
  let queue = [];
  let voice;

  function setSpeechMode(mode, message) {
    speechMode = mode;
    play.textContent = mode === "paused" ? "Resume" : "Play";
    play.setAttribute("aria-disabled", String(mode === "playing"));
    pause.setAttribute("aria-disabled", String(mode !== "playing"));
    stop.setAttribute("aria-disabled", String(mode === "stopped"));
    speechStatus.textContent = message;
  }

  function clearHighlight() {
    highlighted?.classList.remove("is-reading");
    highlighted = undefined;
  }

  function readNext() {
    clearHighlight();
    const item = queue.shift();
    if (!item) {
      utterance = undefined;
      setSpeechMode("stopped", "Read-along finished.");
      return;
    }
    highlighted = item.node;
    highlighted.classList.add("is-reading");
    highlighted.scrollIntoView({ block: "nearest" });
    const current = new SpeechSynthesisUtterance(item.text);
    utterance = current;
    current.voice = voice;
    current.lang = voice.lang;
    current.onend = () => { if (utterance === current) readNext(); };
    current.onerror = () => {
      if (utterance !== current) return;
      utterance = undefined;
      queue = [];
      clearHighlight();
      setSpeechMode("stopped", "Read-along could not play with the selected device voice.");
    };
    synthesis.speak(current);
  }

  function playReading() {
    if (!speechSupported || speechMode === "playing") return;
    if (speechMode === "paused") {
      synthesis.resume();
      setSpeechMode("playing", "Read-along resumed.");
      return;
    }

    const language = root.lang.toLowerCase();
    const primary = (tag) => tag.toLowerCase().split(/[-_]/)[0];
    const local = synthesis.getVoices().filter((candidate) => candidate.localService);
    voice = local.find((candidate) => candidate.lang.toLowerCase() === language)
      || local.find((candidate) => primary(candidate.lang) === primary(language))
      || (language === "und" && (local.find((candidate) => candidate.default) || local[0]));
    if (!voice) {
      speechStatus.textContent = "No offline voice is available for this document’s language.";
      return;
    }
    const start = sections[currentSection];
    queue = Array.from(document.querySelectorAll("article :is(" + readable + ")"))
      .filter((node) => !node.closest("details:not([open]), [hidden]") &&
        (!start || node === start || Boolean(start.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING)))
      .map((node) => {
        const copy = node.cloneNode(true);
        copy.querySelectorAll(readable).forEach((child) => child.remove());
        return { node, text: copy.textContent.trim() };
      })
      .filter((item) => item.text);
    if (!queue.length) {
      speechStatus.textContent = "There is no readable text in this section.";
      return;
    }
    synthesis.resume();
    setSpeechMode("playing", "Read-along started.");
    readNext();
  }

  function pauseReading() {
    if (speechMode !== "playing") return;
    synthesis.pause();
    setSpeechMode("paused", "Read-along paused.");
  }

  function stopReading() {
    if (speechMode === "stopped") return;
    utterance = undefined;
    queue = [];
    synthesis.cancel();
    clearHighlight();
    setSpeechMode("stopped", "Read-along stopped.");
  }

  if (speechSupported) {
    document.querySelector("#speech-controls").hidden = false;
    play.addEventListener("click", playReading);
    pause.addEventListener("click", pauseReading);
    stop.addEventListener("click", stopReading);
    window.addEventListener("pagehide", stopReading);
  } else {
    speechStatus.textContent = "Read-along is unavailable in this browser.";
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      const expanded = event.target.closest?.("details[open]");
      if (expanded) {
        expanded.open = false;
        expanded.querySelector("summary").focus();
        event.preventDefault();
      }
      return;
    }
    if (!shortcuts.checked || event.altKey || event.ctrlKey || event.metaKey ||
        !event.target.closest?.("main, .contents") ||
        event.target.closest("input, select, textarea, button, [contenteditable]")) return;

    const key = event.key.toLowerCase();
    if (key === "[" || key === "]") {
      const offset = key === "[" ? -1 : 1;
      const next = Math.max(0, Math.min(links.length - 1, currentSection + offset));
      links[next]?.click();
    } else if (key === "c") {
      contents.open = true;
      contentsSummary.focus();
    } else if (key === "+" || key === "-") {
      const size = selects.size;
      const offset = key === "+" ? 1 : -1;
      size.selectedIndex = Math.max(0, Math.min(size.length - 1, size.selectedIndex + offset));
      applySettings();
    } else if (key === "r" && speechSupported) {
      if (speechMode === "playing") pauseReading();
      else playReading();
    } else {
      return;
    }
    event.preventDefault();
  });
})();
