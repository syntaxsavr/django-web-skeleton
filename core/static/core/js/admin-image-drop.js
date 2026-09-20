(function () {
  "use strict";

  function fileName(input) {
    return input.files && input.files.length ? input.files[0].name : "Drop an image here or choose a file";
  }

  function mount(input) {
    if (input.getAttribute("data-drop-ready") === "true") return;
    input.setAttribute("data-drop-ready", "true");
    input.setAttribute("accept", "image/*");

    var zone = document.createElement("div");
    zone.className = "admin-image-drop";
    var status = document.createElement("span");
    status.className = "admin-image-drop-status";
    status.textContent = fileName(input);
    input.parentNode.insertBefore(zone, input);
    zone.appendChild(input);
    zone.appendChild(status);

    zone.addEventListener("dragover", function (event) {
      event.preventDefault();
      zone.classList.add("is-dragging");
    });
    zone.addEventListener("dragleave", function () {
      zone.classList.remove("is-dragging");
    });
    zone.addEventListener("drop", function (event) {
      event.preventDefault();
      zone.classList.remove("is-dragging");
      if (!event.dataTransfer || !event.dataTransfer.files.length) return;
      input.files = event.dataTransfer.files;
      status.textContent = fileName(input);
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    input.addEventListener("change", function () {
      status.textContent = fileName(input);
    });
  }

  function scan() {
    var inputs = document.querySelectorAll('input[type="file"]');
    var index;
    for (index = 0; index < inputs.length; index += 1) mount(inputs[index]);
  }

  document.addEventListener("DOMContentLoaded", function () {
    scan();
    new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
  });
})();
