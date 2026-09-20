/* Article editor: drag-and-drop ordering for content blocks and a live
   preview button. Adapts to unfold's nested inline DOM: a block row is
   the smallest ancestor of a block control that also holds its DELETE
   input. Reordering works visually (flex order) and writes fresh
   sort_order values so the next save persists it. */
(function () {
  "use strict";

  var GROUP_SELECTOR = "#blocks-group";

  function blockRows(group) {
    var seen = [];
    var selects = group.querySelectorAll("select[name$='-kind']");
    Array.prototype.forEach.call(selects, function (select) {
      if (select.name.indexOf("__prefix__") !== -1) return;
      var deleteName = select.name.replace(/-kind$/, "-DELETE");
      var deleteInput = group.querySelector("[name='" + deleteName + "']");
      var el = select;
      while (el && el !== group) {
        if (deleteInput && el.contains(deleteInput)) break;
        el = el.parentElement;
      }
      if (el && el !== group && seen.indexOf(el) === -1) seen.push(el);
    });
    seen.sort(function (a, b) {
      return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    });
    return seen;
  }

  function flexParent(rows) {
    if (!rows.length) return null;
    var parent = rows[0].parentElement;
    parent.style.display = "flex";
    parent.style.flexDirection = "column";
    return parent;
  }

  function applyOrder(group, rows) {
    rows.forEach(function (row, index) {
      row.style.order = index;
      var field = row.querySelector('input[name$="-sort_order"]');
      if (field) field.value = (index + 1) * 10;
    });
  }

  function orderedRows(group, rows) {
    return rows.slice().sort(function (a, b) {
      return (parseInt(a.style.order, 10) || 0) - (parseInt(b.style.order, 10) || 0);
    });
  }

  function moveRow(group, row, direction) {
    var rows = blockRows(group);
    var flat = orderedRows(group, rows);
    var index = flat.indexOf(row);
    var target = flat[index + direction];
    if (!target) return;
    flat.splice(index, 1);
    flat.splice(flat.indexOf(target) + (direction < 0 ? 0 : 1), 0, row);
    applyOrder(group, flat);
  }

  function addControls(group, row) {
    if (row.querySelector(".block-drag-handle")) return;
    var handle = document.createElement("div");
    handle.className = "block-drag-handle";
    handle.setAttribute("aria-hidden", "true");

    var grip = document.createElement("span");
    grip.className = "block-grip";
    grip.textContent = "\u22ee\u22ee";
    grip.title = "Drag to reorder";
    grip.draggable = true;
    grip.addEventListener("dragstart", function (event) {
      row.classList.add("block-dragging");
      event.dataTransfer.setData("text/plain", String(Date.now()));
      event.dataTransfer.effectAllowed = "move";
    });
    grip.addEventListener("dragend", function () {
      row.classList.remove("block-dragging");
      applyOrder(group, orderedRows(group, blockRows(group)));
    });
    row.addEventListener("dragover", function (event) {
      if (!document.querySelector(".block-dragging")) return;
      event.preventDefault();
      var dragged = group.querySelector(".block-dragging");
      if (!dragged || dragged === row) return;
      var rect = row.getBoundingClientRect();
      var rows = blockRows(group);
      var flat = orderedRows(group, rows);
      var from = flat.indexOf(dragged);
      var to = flat.indexOf(row);
      var before = event.clientY < rect.top + rect.height / 2;
      if (from === to) return;
      flat.splice(from, 1);
      flat.splice(flat.indexOf(row) + (before ? 0 : 1), 0, dragged);
      applyOrder(group, flat);
    });

    var up = document.createElement("button");
    up.type = "button";
    up.className = "block-move block-move-up";
    up.textContent = "\u2191";
    up.title = "Move up";
    up.addEventListener("click", function () {
      moveRow(group, row, -1);
    });

    var down = document.createElement("button");
    down.type = "button";
    down.className = "block-move block-move-down";
    down.textContent = "\u2193";
    down.title = "Move down";
    down.addEventListener("click", function () {
      moveRow(group, row, 1);
    });

    handle.appendChild(grip);
    handle.appendChild(up);
    handle.appendChild(down);
    var anchor = row.firstElementChild;
    row.insertBefore(handle, anchor || null);
  }

  function initDrag() {
    var group = document.querySelector(GROUP_SELECTOR);
    if (!group || group._blocksDnd) return;
    group._blocksDnd = true;
    var rows = blockRows(group);
    flexParent(rows);
    rows.forEach(function (row) {
      addControls(group, row);
    });
    applyOrder(group, rows);

    document.addEventListener("formset:added", function () {
      var fresh = blockRows(group);
      flexParent(fresh);
      fresh.forEach(function (row) {
        addControls(group, row);
      });
      applyOrder(group, fresh);
    });
    if (window.django && window.django.jQuery) {
      window.django.jQuery(document).on("formset:added", function () {
        var fresh = blockRows(group);
        flexParent(fresh);
        fresh.forEach(function (row) {
          if (!row.querySelector(".block-drag-handle")) addControls(group, row);
        });
        applyOrder(group, fresh);
      });
    }
  }

  function initPreview() {
    var form = document.querySelector("#article_form");
    var submitRow = document.querySelector("#submit-row");
    if (!form || !submitRow || submitRow.querySelector("[data-preview-button]")) return;

    var button = document.createElement("button");
    button.type = "button";
    button.className = "button";
    button.setAttribute("data-preview-button", "");
    button.textContent = "Preview (opens a new tab)";
    button.addEventListener("click", function () {
      var payload = document.createElement("form");
      payload.method = "post";
      payload.action = "/articles/preview/";
      payload.target = "_blank";

      var pkMatch = (form.getAttribute("action") || "").match(/\/(\d+)\/change\//);
      function add(name, value) {
        var input = document.createElement("input");
        input.type = "hidden";
        input.name = name;
        input.value = value;
        payload.appendChild(input);
      }
      add("csrfmiddlewaretoken", form.querySelector("[name=csrfmiddlewaretoken]").value);
      add("pk", pkMatch ? pkMatch[1] : "");
      add("inline_prefix", "blocks");

      Array.prototype.forEach.call(form.querySelectorAll("input, select, textarea"), function (control) {
        if (!control.name || control.disabled || control.type === "submit") return;
        if (control.name.indexOf("__prefix__") !== -1) return;
        if ((control.type === "checkbox" || control.type === "radio") && !control.checked) return;
        var copy = document.createElement("input");
        copy.type = control.type === "file" ? "file" : "hidden";
        copy.name = control.name;
        if (control.type === "file") {
          if (control.files.length) copy.files = control.files;
        } else {
          copy.value = control.value;
        }
        payload.appendChild(copy);
      });

      document.body.appendChild(payload);
      payload.submit();
      setTimeout(function () {
        payload.remove();
      }, 2000);
    });

    submitRow.insertBefore(button, submitRow.firstChild);
  }

  function init() {
    if (!document.querySelector(GROUP_SELECTOR) && !document.querySelector("#article_form")) return;
    initDrag();
    initPreview();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
