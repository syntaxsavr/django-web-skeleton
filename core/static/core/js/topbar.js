/* Topbar scroll state: adds .scrolled to the sticky header after 24px. */
(function () {
  "use strict";

  function init() {
    var header = document.querySelector("[data-site-header]");
    if (!header) return;

    var toggle = header.querySelector("[data-nav-toggle]");
    var navigation = header.querySelector("[data-site-navigation]");

    function setOpen(open) {
      if (!toggle || !navigation) return;
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      navigation.hidden = !open;
      header.classList.toggle("nav-is-open", open);
      document.documentElement.classList.toggle("nav-open", open);
    }

    if (toggle && navigation) {
      setOpen(false);
      toggle.addEventListener("click", function () {
        setOpen(toggle.getAttribute("aria-expanded") !== "true");
      });
      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
          setOpen(false);
          toggle.focus();
        }
      });
      document.addEventListener("click", function (event) {
        if (toggle.getAttribute("aria-expanded") === "true" && !header.contains(event.target)) {
          setOpen(false);
        }
      });
      navigation.addEventListener("click", function (event) {
        if (event.target.closest("a")) setOpen(false);
      });
    }

    var ticking = false;
    window.addEventListener(
      "scroll",
      function () {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(function () {
          header.classList.toggle("scrolled", window.scrollY > 24);
          ticking = false;
        });
      },
      { passive: true }
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
