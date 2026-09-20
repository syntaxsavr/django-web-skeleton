/* Lazy sections: fetch-on-approach engine.
   Contract:
   - <section data-lazy-section data-lazy-url="/lazy-section/<name>/">
   - On approach (500px margin) the loader inserts a placeholder, fetches
     the fragment, swaps innerHTML and re-executes any <script> in it.
   - Dispatches document CustomEvent "lazy-section-loaded" on the section.
   - Hash navigation loads all lazy sections above the target first.
*/
(function () {
  "use strict";

  var ROOT_MARGIN = "500px 0px";
  var sections = [];

  function placeholder() {
    var box = document.createElement("div");
    box.className = "lazy-placeholder";
    box.setAttribute("aria-hidden", "true");
    return box;
  }

  function reexecuteScripts(section) {
    var scripts = section.querySelectorAll("script");
    for (var i = 0; i < scripts.length; i++) {
      var old = scripts[i];
      var fresh = document.createElement("script");
      for (var a = 0; a < old.attributes.length; a++) {
        fresh.setAttribute(old.attributes[a].name, old.attributes[a].value);
      }
      fresh.text = old.textContent;
      old.parentNode.replaceChild(fresh, old);
    }
  }

  function load(section) {
    if (section.getAttribute("data-lazy-state") === "loaded" || section._loading) return;
    var url = section.getAttribute("data-lazy-url");
    if (!url) return;
    section._loading = true;
    section.setAttribute("data-lazy-state", "loading");
    section.classList.add("loading");
    section.setAttribute("aria-busy", "true");

    var holder = section.querySelector(".lazy-placeholder");
    if (!holder) {
      holder = placeholder();
      var sink = document.createElement("div");
      sink.className = "lazy-sink";
      sink.setAttribute("data-lazy-sink", "");
      section.appendChild(sink);
      sink.appendChild(holder);
    }

    fetch(url, { credentials: "same-origin", headers: { "X-Lazy-Section": "1" } })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.text();
      })
      .then(function (html) {
        var sink = section.querySelector("[data-lazy-sink]") || section;
        sink.innerHTML = html;
        section.classList.remove("loading");
        section.classList.add("lazy-loaded");
        section.setAttribute("data-lazy-state", "loaded");
        section.removeAttribute("aria-busy");
        reexecuteScripts(sink);
        document.dispatchEvent(
          new CustomEvent("lazy-section-loaded", { bubbles: true, detail: { section: section, url: url } })
        );
      })
      .catch(function () {
        section.classList.remove("loading");
        section.classList.add("lazy-error");
        section.setAttribute("data-lazy-state", "error");
        section.removeAttribute("aria-busy");
      });
  }

  function indexOf(section) {
    for (var i = 0; i < sections.length; i++) {
      if (sections[i] === section) return i;
    }
    return -1;
  }

  function loadLazySectionsBefore(target) {
    var position = indexOf(target);
    for (var i = 0; i <= position; i++) {
      load(sections[i]);
    }
  }

  function init() {
    sections = Array.prototype.slice.call(document.querySelectorAll("[data-lazy-section]"));

    if (!("IntersectionObserver" in window)) {
      sections.forEach(load);
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            observer.unobserve(entry.target);
            load(entry.target);
          }
        });
      },
      { rootMargin: ROOT_MARGIN }
    );
    sections.forEach(function (section) {
      observer.observe(section);
    });

    document.addEventListener("click", function (event) {
      var anchor = event.target.closest('a[href*="#"]');
      if (!anchor) return;
      var hashIndex = anchor.getAttribute("href").indexOf("#");
      if (hashIndex === -1) return;
      var id = anchor.getAttribute("href").slice(hashIndex + 1);
      if (!id) return;
      var target = document.getElementById(id);
      if (target) loadLazySectionsBefore(target);
    });

    if (window.location.hash) {
      var target = document.getElementById(window.location.hash.slice(1));
      if (target) loadLazySectionsBefore(target);
    }

    window.addEventListener("pageshow", function (event) {
      if (event.persisted) sections.forEach(load);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
