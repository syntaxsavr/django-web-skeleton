/* Contact form: Turnstile callback bridge and submit feedback.
   Turnstile calls window.skeletonTurnstileOk/Gone; the hidden response
   token is copied into the form field by Turnstile itself. */
(function () {
  "use strict";

  function init() {
    var form = document.getElementById("contact-form");
    if (!form) return;

    window.skeletonTurnstileOk = function () {
      var response = document.getElementById("cf-turnstile-response");
      if (response && window.turnstile) {
        var widgetId = turnstileFirstWidget();
        if (widgetId !== null) response.value = window.turnstile.getResponse(widgetId) || "ok";
        else response.value = "ok";
      } else {
        var fallback = document.querySelector("[name='cf-turnstile_response']");
        if (fallback) response.value = fallback.value;
      }
      var submit = form.querySelector(".cf-submit");
      if (submit) submit.disabled = false;
    };
    window.skeletonTurnstileGone = function () {
      var response = document.getElementById("cf-turnstile-response");
      if (response) response.value = "";
      var submit = form.querySelector(".cf-submit");
      if (submit) submit.disabled = true;
    };

    form.addEventListener("submit", function () {
      var submit = form.querySelector(".cf-submit");
      if (submit) {
        submit.disabled = true;
        submit.textContent = "Sending...";
      }
    });
  }

  function turnstileFirstWidget() {
    if (!window.turnstile || typeof window.turnstile.getResponse !== "function") return null;
    try {
      for (var i = 0; i < 5; i++) {
        var value = window.turnstile.getResponse(i);
        if (value) return i;
      }
    } catch (e) {
      return null;
    }
    return null;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
