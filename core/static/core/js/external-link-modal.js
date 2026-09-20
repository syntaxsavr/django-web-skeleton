/* External link modal: intercepts clicks on [data-external] anchors and
   asks for confirmation. The data-external attribute itself is added by
   the ExternalLinkMiddleware on the server. Optional Turnstile challenge
   inside the modal (when a sitekey is present on the modal element). */
(function () {
  "use strict";

  function init() {
    var modal = document.querySelector("[data-external-modal]");
    if (!modal) return;

    var targetDisplay = modal.querySelector("[data-external-target]");
    var proceed = modal.querySelector("[data-external-proceed]");
    var turnstileHost = modal.querySelector("[data-external-turnstile]");
    var sitekey = modal.getAttribute("data-turnstile-sitekey");
    var challengeSolved = !sitekey;

    window.skeletonExternalTurnstileOk = function () {
      challengeSolved = true;
      if (proceed) proceed.classList.remove("is-locked");
    };
    window.skeletonExternalTurnstileGone = function () {
      challengeSolved = false;
      if (proceed) proceed.classList.add("is-locked");
    };

    if (turnstileHost && sitekey && window.turnstile) {
      window.turnstile.render(turnstileHost, {
        sitekey: sitekey,
        theme: "dark",
        callback: "skeletonExternalTurnstileOk",
        "expired-callback": "skeletonExternalTurnstileGone",
        "error-callback": "skeletonExternalTurnstileGone",
      });
    }

    document.addEventListener(
      "click",
      function (event) {
        var anchor = event.target.closest("a[data-external]");
        if (!anchor) return;
        var href = anchor.getAttribute("href") || "";
        if (!/^https?:/i.test(href)) return;
        event.preventDefault();
        if (targetDisplay) targetDisplay.textContent = href.length > 80 ? href.slice(0, 77) + "..." : href;
        if (proceed) {
          proceed.setAttribute("href", href);
          proceed.classList.toggle("is-locked", !challengeSolved);
        }
        window.skeletonModal.open(modal);
      },
      true
    );

    document.addEventListener("skeleton:modal-close", function (event) {
      if (event.detail && event.detail.modal === modal && proceed) {
        setTimeout(function () {
          proceed.removeAttribute("href");
        }, 0);
      }
    });

    if (sitekey && !window.turnstile) {
      var script = document.createElement("script");
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
      script.defer = true;
      document.head.appendChild(script);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
