/* Hero entrance: index the data-hero-item children and unlock the
   choreography defined in hero-entrance.css. */
(function () {
  "use strict";

  function init() {
    var sections = document.querySelectorAll("[data-hero-entrance]");
    for (var i = 0; i < sections.length; i++) {
      (function (section) {
        var items = section.querySelectorAll("[data-hero-item]");
        for (var j = 0; j < items.length; j++) {
          items[j].style.setProperty("--hero-index", j);
        }
        var reduced =
          window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
          document.documentElement.classList.contains("a11y-reduce-motion");
        if (reduced) {
          section.classList.add("hero-entered", "hero-instant");
        } else {
          requestAnimationFrame(function () {
            requestAnimationFrame(function () {
              section.classList.add("hero-entered");
            });
          });
        }
      })(sections[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
