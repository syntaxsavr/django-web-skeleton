/* Klaro boot: waits for both the config and the library, respects the
   data-consent-suppress flag on <body> (legal pages never auto-open the
   ask screen), and toggles the klaro-open scroll lock class. */
(function () {
  "use strict";

  var attempts = 0;
  var timer = null;

  function boot() {
    if (!window.klaro || !window.klaroConfig) return false;
    var suppressed = document.body.hasAttribute("data-consent-suppress");
    var manager = window.klaro.getManager();
    if (!suppressed && !manager.confirmed) {
      window.klaro.show();
    }

    var target = document.body;
    function syncOpenState() {
      var open = !!document.querySelector(".klaro .cm-modal, .klaro .cm-notice");
      open = open || !!document.querySelector(".klaro .cookie-modal, .klaro .cookie-notice:not(.cookie-notice-hidden)");
      document.documentElement.classList.toggle("klaro-open", open);
      document.body.classList.toggle("klaro-open", open);
    }
    var observer = new MutationObserver(syncOpenState);
    observer.observe(target, { childList: true, subtree: true });
    syncOpenState();

    if (manager.confirmed) {
      document.dispatchEvent(new CustomEvent("skeleton:consent", { detail: null }));
    }
    return true;
  }

  function retry() {
    attempts += 1;
    if (boot()) {
      if (timer) clearInterval(timer);
      return;
    }
    if (attempts > 40) {
      if (timer) clearInterval(timer);
      return;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      retry();
      timer = setInterval(retry, 50);
    });
  } else {
    retry();
    timer = setInterval(retry, 50);
  }
})();
