/* Password visibility toggles: the eye button swaps password <-> text on
   the paired input. */
(function () {
  "use strict";

  var EYE_ON =
    '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg>';
  var EYE_OFF =
    '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path d="M2.5 12S6 5.5 12 5.5c1.8 0 3.4.6 4.7 1.4M21.5 12S18 18.5 12 18.5c-1.8 0-3.4-.6-4.7-1.4" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M4 20 20 4" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg>';

  function init() {
    document.querySelectorAll("[data-password-view]").forEach(function (button) {
      if (button._pwBound) return;
      button._pwBound = true;
      var target = document.getElementById(button.getAttribute("data-password-view"));
      if (!target) return;
      button.innerHTML = EYE_ON;
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", function () {
        var show = target.type === "password";
        target.type = show ? "text" : "password";
        button.innerHTML = show ? EYE_OFF : EYE_ON;
        button.setAttribute("aria-pressed", show ? "true" : "false");
        button.setAttribute(
          "title",
          show ? "Hide password" : "Show password"
        );
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
