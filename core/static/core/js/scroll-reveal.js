/* Scroll reveal: selector-driven entrance animations.
   Anything with [data-reveal] plus a curated selector list joins the
   system. Staggered by 45ms within a batch, capped at three steps. */
(function () {
  "use strict";

  var STAGGLE_MS = 45;
  var MAX_STAGGER_STEPS = 3;

  var SELECTORS = [
    "[data-reveal]",
    ".section-head",
    ".section-head > *",
    ".feature-card",
    ".pattern-card",
    ".demo-box",
    ".lazy-panel",
    ".auth-card",
    ".cta-inner > *",
  ].join(", ");

  var EXCLUDES = "[data-reveal='off'], [aria-hidden='true'] .reveal-candidate, form .reveal-candidate";

  function reducedMotion() {
    return (
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.classList.contains("a11y-reduce-motion") ||
      document.documentElement.classList.contains("perf-lite")
    );
  }

  function candidates() {
    var found = document.querySelectorAll(SELECTORS);
    var list = [];
    for (var i = 0; i < found.length; i++) {
      var el = found[i];
      var rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight * 0.92 && rect.bottom > 0) continue; /* already visible */
      if (el.closest("[data-hero-entrance]")) continue; /* hero has its own choreography */
      if (el.closest("form")) continue;
      list.push(el);
    }
    return list;
  }

  function arm() {
    var list = candidates();
    if (!list.length) return;
    if (reducedMotion()) return;

    if (!("IntersectionObserver" in window)) {
      list.forEach(function (el) {
        el.classList.add("reveal-enter");
      });
      return;
    }

    var stagger = 0;
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          observer.unobserve(entry.target);
          var el = entry.target;
          var variant = el.getAttribute("data-reveal");
          if (variant && variant !== "true") el.classList.add("reveal-" + variant);
          el.style.setProperty("--reveal-delay", stagger * STAGGLE_MS + "ms");
          stagger = (stagger + 1) % (MAX_STAGGER_STEPS + 1);
          el.classList.remove("reveal-pending");
          el.classList.add("reveal-enter");
          el.addEventListener("animationend", function () {
            el.classList.remove("reveal-enter");
            el.style.removeProperty("--reveal-delay");
          });
        });
      },
      { threshold: 0, rootMargin: "0px 0px -24px 0px" }
    );
    list.forEach(function (el) {
      el.classList.add("reveal-pending");
      observer.observe(el);
    });
  }

  document.addEventListener("lazy-section-loaded", function () {
    arm();
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", arm);
  } else {
    arm();
  }
})();
