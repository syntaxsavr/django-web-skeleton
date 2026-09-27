/* Live preview pane: keep the iframe in sync with the saved site.
 *
 * Every reload appends a timestamp query so heuristic browser caching can
 * never serve a stale page. Reloads happen on: page restores from the
 * back/forward cache, any form field change, drag reorders of result rows
 * (Alpine's sort writes values programmatically, so a MutationObserver
 * catches those), and the manual reload button. A save navigates the whole
 * admin page, which refetches the iframe anyway - the timestamp query is
 * what keeps that refetch honest.
 */
(function () {
  "use strict";

  function init() {
    var frame = document.querySelector(".admin-preview-frame");
    if (!frame) return;
    var base = frame.getAttribute("data-preview-base-src") || frame.getAttribute("src");
    var sep = base.indexOf("?") === -1 ? "?" : "&";
    var timer = null;

    function reload() {
      frame.src = base + sep + "preview=" + Date.now();
    }

    function reloadSoon() {
      window.clearTimeout(timer);
      timer = window.setTimeout(reload, 800);
    }

    // Stamp the very first load as well, so the fetch right after a save
    // (which navigates the whole admin page) can never come from cache.
    if (frame.src.indexOf("preview=") === -1) {
      reload();
    }

    window.addEventListener("pageshow", function (event) {
      if (event.persisted) reload();
    });

    document.addEventListener("change", function (event) {
      if (event.target && event.target.closest && event.target.closest("form")) {
        reloadSoon();
      }
    });

    var results =
      document.querySelector(".admin-preview-results") || document.getElementById("changelist");
    if (results && "MutationObserver" in window) {
      new MutationObserver(reloadSoon).observe(results, { childList: true, subtree: true });
    }

    var button = document.querySelector("[data-preview-reload]");
    if (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        reload();
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
