/* First-party tracking layer: consent-gated dataLayer pushes.
   Events are queued always, pushed only when analytics consent exists.
   Public API: window.skeletonTrack(event, params). */
(function () {
  "use strict";

  window.dataLayer = window.dataLayer || [];
  var queue = [];
  var seen = {};
  var consentReady = false;

  function getPrefs() {
    if (typeof window.getConsentPrefs === "function") return window.getConsentPrefs();
    return null;
  }

  function push(event, params) {
    var key = event + ":" + (params && params.event_id ? params.event_id : "");
    if (seen[key]) return;
    seen[key] = true;
    window.dataLayer.push(Object.assign({ event: event }, params || {}));
  }

  function flush() {
    var prefs = getPrefs();
    if (!prefs || !prefs.analytics) return;
    while (queue.length) {
      var item = queue.shift();
      push(item.event, item.params);
    }
  }

  window.skeletonTrack = function (event, params) {
    var prefs = getPrefs();
    if (prefs && prefs.analytics) {
      push(event, params);
    } else if (!prefs || !consentReady) {
      queue.push({ event: event, params: params });
      if (consentReady) flush();
    }
  };

  function uuid() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "e-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10);
  }

  function locationOf(target) {
    var tracked = target.closest("[data-track]");
    if (tracked) return tracked.getAttribute("data-track");
    if (target.closest(".site-footer")) return "footer";
    if (target.closest(".site-header")) return "header";
    if (target.closest(".cta-band")) return "cta_band";
    var section = target.closest("section[id]");
    if (section) return "section_" + section.id;
    return "body";
  }

  function bindClicks() {
    document.addEventListener(
      "click",
      function (event) {
        var target = event.target.closest("a, button, [data-track]");
        if (!target) return;
        var params = { event_id: uuid(), click_location: locationOf(target) };

        var href = target.getAttribute("href") || "";
        if (/^tel:/i.test(href)) {
          params.value = href.replace(/^tel:/i, "");
          window.skeletonTrack("phone_click", params);
        } else if (/^mailto:/i.test(href)) {
          params.value = href.replace(/^mailto:/i, "");
          window.skeletonTrack("email_click", params);
        } else if (/\.pdf$/i.test(href)) {
          params.value = href;
          window.skeletonTrack("file_download", params);
        } else if (/^https?:/i.test(href) && target.hostname && target.hostname !== window.location.hostname) {
          params.value = target.hostname;
          window.skeletonTrack("outbound_click", params);
        } else if (target.getAttribute("data-track")) {
          window.skeletonTrack("cta_click", params);
        }
      },
      true
    );
  }

  function bindScrollDepth() {
    var marks = [25, 50, 75, 100];
    var fired = {};
    var queued = false;
    window.addEventListener(
      "scroll",
      function () {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function () {
          queued = false;
          var depth = (window.scrollY + window.innerHeight) / document.documentElement.scrollHeight * 100;
          marks.forEach(function (mark) {
            if (depth >= mark && !fired[mark]) {
              fired[mark] = true;
              window.skeletonTrack("scroll_depth", { event_id: uuid() + "-d" + mark, percent: mark });
            }
          });
        });
      },
      { passive: true }
    );
  }

  function bindSectionView() {
    if (!("IntersectionObserver" in window)) return;
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          observer.unobserve(entry.target);
          window.skeletonTrack("section_view", {
            event_id: uuid() + "-" + entry.target.id,
            section_id: entry.target.id,
          });
        });
      },
      { threshold: 0.4 }
    );
    document.querySelectorAll("section[id]").forEach(function (section) {
      observer.observe(section);
    });
  }

  document.addEventListener("skeleton:consent", function () {
    consentReady = true;
    flush();
  });

  function init() {
    bindClicks();
    bindScrollDepth();
    bindSectionView();
    window.skeletonTrack("page_view", {
      event_id: uuid(),
      page_path: window.location.pathname,
      page_type: window.location.pathname === "/" ? "home" : window.location.pathname.split("/")[1] || "home",
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
