/* Display preferences and perf tiering. Runs before other UI scripts.
   Options live in the accessibility panel: dark mode, contrast, text
   size (with live percentage), reduced motion, print, reset. Every
   element with [data-a11y-state] shows the current state, and option
   buttons carry aria-pressed. */
(function () {
  "use strict";

  var STORE_KEY = "skeleton.a11y";
  var prefs = { dark: false, contrast: false, text: 0, motion: false };
  var TEXT_LABELS = ["100%", "110%", "125%"];
  try {
    var raw = window.localStorage.getItem(STORE_KEY);
    if (raw) {
      var saved = JSON.parse(raw);
      if (saved && typeof saved === "object") {
        prefs.dark = !!saved.dark || !!saved.light;
        prefs.contrast = !!saved.contrast;
        prefs.text = saved.text === 1 || saved.text === 2 ? saved.text : 0;
        prefs.motion = !!saved.motion;
      }
    }
  } catch (e) {
    /* storage unavailable: fall back to defaults */
  }

  function persist() {
    try {
      window.localStorage.setItem(STORE_KEY, JSON.stringify(prefs));
    } catch (e) {
      /* ignore */
    }
  }

  function isOn(action) {
    if (action === "toggle-dark") return prefs.dark;
    if (action === "toggle-contrast") return prefs.contrast;
    if (action === "toggle-motion") return prefs.motion;
    if (action === "toggle-text") return prefs.text > 0;
    return false;
  }

  function stateLabel(action) {
    if (action === "toggle-text") return TEXT_LABELS[prefs.text];
    if (isOn(action)) return "On";
    if (action === "toggle-dark" || action === "toggle-contrast" || action === "toggle-motion") return "Off";
    return "";
  }

  function applyDocument() {
    var root = document.documentElement;
    root.classList.toggle("theme-dark", prefs.dark);
    root.classList.toggle("a11y-contrast", prefs.contrast);
    root.classList.toggle("a11y-text-110", prefs.text === 1);
    root.classList.toggle("a11y-text-125", prefs.text === 2);
    root.classList.toggle("a11y-reduce-motion", prefs.motion);
    /* native controls (inputs, scrollbars, date pickers) follow the theme */
    root.style.colorScheme = prefs.dark ? "dark" : "light";
    var meta = document.querySelector("meta[name='theme-color']");
    if (meta) meta.setAttribute("content", prefs.dark ? "#111110" : "#fcfcfa");
  }

  function updateStates() {
    var nodes = document.querySelectorAll("[data-a11y-state]");
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var action = el.getAttribute("data-a11y-state");
      var label = stateLabel(action);
      if (label) el.textContent = label;
      var button = el.closest("[data-a11y-action]");
      if (button && action !== "toggle-text") {
        button.setAttribute("aria-pressed", isOn(action) ? "true" : "false");
      } else if (button && action === "toggle-text") {
        button.setAttribute("aria-pressed", prefs.text > 0 ? "true" : "false");
      }
    }
  }

  function apply() {
    applyDocument();
    updateStates();
  }

  function bind() {
    document.addEventListener("click", function (event) {
      var target = event.target.closest("[data-a11y-action]");
      if (!target) return;
      var action = target.getAttribute("data-a11y-action");
      if (action === "print-page") {
        window.print();
        return;
      }
      if (action === "a11y-reset") {
        prefs = { dark: false, contrast: false, text: 0, motion: false };
      } else if (action === "toggle-dark") prefs.dark = !prefs.dark;
      else if (action === "toggle-contrast") prefs.contrast = !prefs.contrast;
      else if (action === "toggle-text") prefs.text = (prefs.text + 1) % 3;
      else if (action === "toggle-motion") prefs.motion = !prefs.motion;
      else return;
      apply();
      persist();
    });
  }

  function perfTier() {
    var root = document.documentElement;
    var cores = navigator.hardwareConcurrency || 4;
    if (cores <= 2) root.classList.add("perf-lite");
  }

  apply();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      apply();
      bind();
      perfTier();
    });
  } else {
    bind();
    perfTier();
  }
})();
