/* Generic modal engine: focus trap, Escape to close, scroll lock,
   inert background. Exposes window.skeletonModal {open, close}. */
(function () {
  "use strict";

  var active = null;
  var lastFocus = null;
  var savedOverflow = "";

  function focusables(root) {
    var nodes = root.querySelectorAll("a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex='-1'])");
    return Array.prototype.filter.call(nodes, function (node) {
      return node.offsetParent !== null;
    });
  }

  function trap(event) {
    if (!active) return;
    if (event.key === "Escape") {
      close();
      return;
    }
    if (event.key !== "Tab") return;
    var list = focusables(active);
    if (!list.length) return;
    var first = list[0];
    var last = list[list.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function open(modal) {
    if (active) close();
    active = modal;
    lastFocus = document.activeElement;
    modal.hidden = false;
    savedOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    document.addEventListener("keydown", trap);
    var list = focusables(modal);
    if (list.length) list[0].focus();
    document.dispatchEvent(new CustomEvent("skeleton:modal-open", { detail: { modal: modal } }));
  }

  function close() {
    if (!active) return;
    var modal = active;
    active = null;
    modal.hidden = true;
    document.documentElement.style.overflow = savedOverflow;
    document.removeEventListener("keydown", trap);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    document.dispatchEvent(new CustomEvent("skeleton:modal-close", { detail: { modal: modal } }));
  }

  document.addEventListener("click", function (event) {
    var opener = event.target.closest("[data-modal-open]");
    if (opener) {
      var target = document.getElementById(opener.getAttribute("data-modal-open"));
      if (target) {
        event.preventDefault();
        open(target);
        return;
      }
    }
    var closer = event.target.closest("[data-modal-cancel]");
    if (closer) {
      close();
      return;
    }
    if (active && event.target === active) close();
  });

  window.skeletonModal = { open: open, close: close };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      document.querySelectorAll(".modal[hidden]").length;
    });
  }
})();
