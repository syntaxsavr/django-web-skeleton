/* Topbar scroll state: adds .scrolled to the sticky header after 24px. */
(function () {
  "use strict";

  function init() {
    var header = document.querySelector("[data-site-header]");
    if (!header) return;

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
