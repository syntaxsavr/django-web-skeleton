/* Lottie mount runtime.
   Contract:
   - [data-lottie]          JSON url
   - [data-lottie-loop]     loop playback ("true")
   - [data-lottie-speed]    playback rate (float)
   - [data-lottie-scroll]   scrub frames from scroll position ("true")
   - [data-lottie-ratio]    aspect ratio ("w/h") set as --lot-ar before load
   - [data-lottie-poster]   static poster element hidden on ready
   Behavior: mounts 250px before entering view, pauses offscreen, parks on
   the last frame for reduced motion, picks up mounts inside lazy sections
   via the lazy-section-loaded event. The player script itself is injected
   once, on demand. */
(function () {
  "use strict";

  var PLAYER_ATTR = "data-lottie-player";
  var playerUrl = document.documentElement.getAttribute(PLAYER_ATTR);
  var playerPromise = null;
  var jsonCache = {};
  var mounted = [];

  function loadPlayer() {
    if (playerPromise) return playerPromise;
    playerPromise = new Promise(function (resolve, reject) {
      if (window.lottie) {
        resolve(window.lottie);
        return;
      }
      if (!playerUrl) {
        reject(new Error("no player url"));
        return;
      }
      var script = document.createElement("script");
      script.src = playerUrl;
      script.onload = function () {
        resolve(window.lottie);
      };
      script.onerror = function () {
        reject(new Error("player failed"));
      };
      document.head.appendChild(script);
    });
    return playerPromise;
  }

  function fetchJson(url) {
    if (jsonCache[url]) return jsonCache[url];
    jsonCache[url] = fetch(url, { credentials: "same-origin" }).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    });
    return jsonCache[url];
  }

  function reducedMotion() {
    return (
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.classList.contains("a11y-reduce-motion") ||
      document.documentElement.classList.contains("perf-lite")
    );
  }

  function mount(el) {
    if (el._lottie) return;
    var url = el.getAttribute("data-lottie");
    if (!url) return;

    var ratio = el.getAttribute("data-lottie-ratio");
    if (ratio && !el.style.getPropertyValue("--lot-ar")) {
      var parts = ratio.split("/").map(Number);
      if (parts.length === 2 && parts[0] > 0 && parts[1] > 0) {
        el.style.setProperty("--lot-ar", parts[0] + " / " + parts[1]);
      }
    }

    el._lottie = "pending";
    Promise.all([loadPlayer(), fetchJson(url)]).then(function (results) {
      var lottie = results[0];
      var data = results[1];
      var anim = lottie.loadAnimation({
        container: el,
        renderer: "svg",
        loop: el.getAttribute("data-lottie-loop") === "true",
        autoplay: false,
        animationData: data,
      });
      var speed = parseFloat(el.getAttribute("data-lottie-speed"));
      if (speed > 0) anim.setSpeed(speed);
      el._lottie = anim;
      mounted.push({ el: el, anim: anim, scrub: el.getAttribute("data-lottie-scroll") === "true" });

      var poster = el.querySelector("[data-lottie-poster]");
      if (poster) poster.hidden = true;

      if (reducedMotion()) {
        anim.goToAndStop(anim.totalFrames - 1, true);
        return;
      }
      if (el.getAttribute("data-lottie-scroll") === "true") {
        scrubAll();
        return;
      }
      anim.play();

      anim.addEventListener("complete", function () {
        document.dispatchEvent(new CustomEvent("lottie:complete", { detail: { el: el } }));
      });
    }).catch(function () {
      el._lottie = null;
    });
  }

  function scrubAll() {
    var viewportMid = window.scrollY + window.innerHeight / 2;
    mounted.forEach(function (entry) {
      if (!entry.scrub) return;
      var rect = entry.el.getBoundingClientRect();
      var elMid = rect.top + window.scrollY + rect.height / 2;
      var span = Math.max(rect.height / 2 + window.innerHeight / 2, 1);
      var progress = 1 - Math.min(Math.abs(viewportMid - elMid) / span, 1);
      var frame = Math.max(0, Math.min(entry.anim.totalFrames - 1, Math.round(progress * (entry.anim.totalFrames - 1))));
      entry.anim.goToAndStop(frame, true);
    });
  }

  var scrollQueued = false;
  window.addEventListener(
    "scroll",
    function () {
      if (scrollQueued) return;
      scrollQueued = true;
      requestAnimationFrame(function () {
        scrollQueued = false;
        scrubAll();
      });
    },
    { passive: true }
  );

  function mountVisible() {
    var elements = document.querySelectorAll("[data-lottie]");
    for (var i = 0; i < elements.length; i++) {
      mount(elements[i]);
    }
    watchVisibility();
  }

  var visibilityObserver = null;
  function watchVisibility() {
    if (!("IntersectionObserver" in window)) return;
    if (!visibilityObserver) {
      visibilityObserver = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            var anim = entry.target._lottie;
            if (!anim || typeof anim === "string" || anim.scrub) return;
            if (entry.isIntersecting) {
              if (!reducedMotion()) anim.play();
            } else {
              anim.pause();
            }
          });
        },
        { rootMargin: "120px 0px" }
      );
    }
    var elements = document.querySelectorAll("[data-lottie]");
    for (var i = 0; i < elements.length; i++) {
      visibilityObserver.observe(elements[i]);
    }
  }

  document.addEventListener("visibilitychange", function () {
    mounted.forEach(function (entry) {
      if (document.hidden) {
        entry.anim.pause();
      } else if (!reducedMotion() && !entry.scrub) {
        var rect = entry.el.getBoundingClientRect();
        if (rect.bottom > 0 && rect.top < window.innerHeight) entry.anim.play();
      }
    });
  });

  document.addEventListener("lazy-section-loaded", function (event) {
    if (!event.detail || !event.detail.section) return;
    var elements = event.detail.section.querySelectorAll("[data-lottie]");
    for (var i = 0; i < elements.length; i++) {
      mount(elements[i]);
    }
    watchVisibility();
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountVisible);
  } else {
    mountVisible();
  }
})();
