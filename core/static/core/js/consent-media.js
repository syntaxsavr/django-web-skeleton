/* Consent-gated media: videos and Stripe buy buttons in articles.
   Elements marked data-consent-embed="<service>" stay inert until the
   matching Klaro service has consent. With the consent manager disabled
   they render immediately. */
(function () {
  "use strict";

  var config = null;
  var stripeScriptStarted = false;

  function readConfig() {
    if (config) return config;
    var node = document.getElementById("skeleton-tracking-config");
    try {
      config = JSON.parse(node.textContent);
    } catch (e) {
      config = {};
    }
    return config;
  }

  function consentOff() {
    return !readConfig().consentEnabled;
  }

  function hasConsent(service) {
    return typeof window.hasServiceConsent === "function" && window.hasServiceConsent(service);
  }

  function renderIframe(el) {
    if (el.querySelector("iframe")) return;
    var frame = document.createElement("iframe");
    frame.src = el.getAttribute("data-embed-src");
    frame.title = "Embedded video";
    frame.loading = "lazy";
    frame.setAttribute("allow", "autoplay; fullscreen; picture-in-picture");
    frame.setAttribute("allowfullscreen", "");
    frame.className = "consent-media-frame";
    var fallback = el.querySelector(".consent-media-fallback");
    if (fallback) fallback.remove();
    el.insertBefore(frame, el.firstChild);
  }

  function loadStripeLibrary() {
    if (stripeScriptStarted) return;
    stripeScriptStarted = true;
    var script = document.createElement("script");
    script.src = "https://js.stripe.com/v3/buy-button.js";
    script.async = true;
    document.head.appendChild(script);
  }

  function renderStripe(el) {
    var buyId = el.getAttribute("data-buy-button-id");
    var publishable = (readConfig().stripe || {}).publishableKey || "";
    if (!buyId || !publishable || el.querySelector("stripe-buy-button")) return;
    loadStripeLibrary();
    var button = document.createElement("stripe-buy-button");
    button.setAttribute("buy-button-id", buyId);
    button.setAttribute("publishable-key", publishable);
    var fallback = el.querySelector(".consent-media-fallback");
    if (fallback) fallback.remove();
    el.appendChild(button);
  }

  function refresh(scope) {
    var root = scope || document;
    var elements = root.querySelectorAll("[data-consent-embed]");
    for (var i = 0; i < elements.length; i++) {
      (function (el) {
        var service = el.getAttribute("data-consent-embed");
        if (consentOff() || hasConsent(service)) {
          if (service === "stripe") renderStripe(el);
          else renderIframe(el);
        }
      })(elements[i]);
    }
  }

  function bind() {
    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-consent-load]");
      if (!trigger) return;
      var service = trigger.getAttribute("data-consent-load");
      if (typeof window.handleConsent === "function") {
        window.handleConsent("merge", { services: [service] });
      }
      refresh();
    });
    document.addEventListener("skeleton:consent", function () {
      refresh();
    });
  }

  function init() {
    bind();
    refresh();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
