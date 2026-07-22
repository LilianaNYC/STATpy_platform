/* Expand / collapse all escalation cards in an Overview governance board.

   The escalation rows are native `<details>` (`.overview-esc-row`), so there is
   no Dash callback to drive -- this small script toggles their `open` state. A
   board's "Expand all" / "Collapse all" button (`.overview-esc-expand-all`)
   opens every row when any is closed, and closes every row when all are open.
   Each governance board (Models 1.4, Segments 2.4) has its own button and is
   scoped independently via the nearest `.overview-governance-board`.

   Implemented as a plain client-side asset (Dash auto-loads any .js in assets/)
   since this is purely presentational, mirroring the subnav scripts. Clicks are
   delegated at the document level so the buttons keep working across the full
   content re-renders Dash performs; labels are kept in sync with a Mutation
   observer plus per-row `toggle` listeners. */
(function () {
  function rowsFor(button) {
    var board = button.closest(".overview-governance-board");
    return board ? board.querySelectorAll(".overview-esc-row") : [];
  }

  function anyClosed(rows) {
    return Array.prototype.some.call(rows, function (row) {
      return !row.open;
    });
  }

  function updateLabel(button) {
    var rows = rowsFor(button);
    if (!rows.length) return;
    var label = anyClosed(rows) ? "Expand all" : "Collapse all";
    // Only write when the text actually changes: the MutationObserver below
    // watches #page-content's subtree, and setting textContent is itself a
    // childList mutation there -- writing unconditionally would retrigger the
    // observer in an infinite loop.
    if (button.textContent !== label) button.textContent = label;
  }

  function onClick(evt) {
    var button = evt.target.closest(".overview-esc-expand-all");
    if (!button) return;
    evt.preventDefault();
    var rows = rowsFor(button);
    if (!rows.length) return;
    var shouldOpen = anyClosed(rows);
    Array.prototype.forEach.call(rows, function (row) {
      row.open = shouldOpen;
    });
    updateLabel(button);
  }

  function bind() {
    document.querySelectorAll(".overview-esc-expand-all").forEach(function (button) {
      updateLabel(button);
      if (button.dataset.expandAllBound) return;
      button.dataset.expandAllBound = "true";
      var board = button.closest(".overview-governance-board");
      if (!board) return;
      // Keep the button label accurate when rows are toggled one at a time.
      board.querySelectorAll(".overview-esc-row").forEach(function (row) {
        row.addEventListener("toggle", function () {
          updateLabel(button);
        });
      });
    });
  }

  document.addEventListener("click", onClick);

  function observePageContent() {
    var pageContent = document.getElementById("page-content");
    if (!pageContent) {
      window.requestAnimationFrame(observePageContent);
      return;
    }
    new MutationObserver(bind).observe(pageContent, { childList: true, subtree: true });
    bind();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", observePageContent);
  } else {
    observePageContent();
  }
})();
