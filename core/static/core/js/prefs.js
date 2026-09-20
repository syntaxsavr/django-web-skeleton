/* Display preferences and perf tiering. Runs before other UI scripts.
   Footer controls: dark mode, larger text, reduced motion. */
(function () {
  "use strict";

  var STORE_KEY = "skeleton.a11y";
  var prefs = { dark: false, text: 0, motion: false };
  try {
    var raw = window.localStorage.getItem(STORE_KEY);
    if (raw) {
      var saved = JSON.parse(raw);
      if (saved && typeof saved === "object") {
        prefs.dark = !!saved.dark || !!saved.light;
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

  function apply() {
    var root = document.documentElement;
    root.classList.toggle("theme-dark", prefs.dark);
    root.classList.toggle("a11y-text-110", prefs.text === 1);
    root.classList.toggle("a11y-text-125", prefs.text === 2);
    root.classList.toggle("a11y-reduce-motion", prefs.motion);
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
      if (action === "toggle-dark") prefs.dark = !prefs.dark;
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
      bind();
      perfTier();
    });
  } else {
    bind();
    perfTier();
  }
})();
