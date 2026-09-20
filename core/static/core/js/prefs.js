/* Display preferences and perf tiering. Runs before other UI scripts. */
(function () {
  "use strict";

  var STORE_KEY = "skeleton.a11y";
  var prefs = { light: false, text: 0, motion: false };
  try {
    var raw = window.localStorage.getItem(STORE_KEY);
    if (raw) {
      var saved = JSON.parse(raw);
      if (saved && typeof saved === "object") {
        prefs.light = !!saved.light;
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
    root.classList.toggle("a11y-light", prefs.light);
    root.classList.toggle("a11y-text-110", prefs.text === 1);
    root.classList.toggle("a11y-text-125", prefs.text === 2);
    root.classList.toggle("a11y-reduce-motion", prefs.motion);
    root.classList.toggle("a11y-motion", !prefs.motion);
  }

  function bind() {
    document.addEventListener("click", function (event) {
      var target = event.target.closest("[data-a11y-action]");
      if (!target) return;
      var action = target.getAttribute("data-a11y-action");
      if (action === "toggle-light") prefs.light = !prefs.light;
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
    var frames = [];
    var start = performance.now();
    function tick(now) {
      frames.push(now - start);
      start = now;
      if (frames.length < 40) {
        requestAnimationFrame(tick);
        return;
      }
      frames.sort(function (a, b) {
        return a - b;
      });
      var median = frames[Math.floor(frames.length / 2)];
      if (median > 22) root.classList.add("perf-lite");
    }
    requestAnimationFrame(tick);
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
