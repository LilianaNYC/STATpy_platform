/* Section sub-navigation behaviour for #saas-subnav: highlights the "Models
   in Scope" chip whose model card is currently in view, and clicking a chip
   smooth-scrolls to that card. */
(function () {
  var scrollFrame = null;
  var resizeQueued = false;
  var refreshQueued = false;

  // Coalesce work to at most once per animation frame. Opening many cards at
  // once (Expand all) fires a burst of `toggle` events and Plotly redraws; a
  // separate resize / button-refresh per event would jam the main thread.
  function scheduleResize() {
    if (resizeQueued) return;
    resizeQueued = true;
    window.requestAnimationFrame(function () {
      resizeQueued = false;
      window.dispatchEvent(new Event("resize"));
    });
  }

  function scheduleRefreshButton() {
    if (refreshQueued) return;
    refreshQueued = true;
    window.requestAnimationFrame(function () {
      refreshQueued = false;
      refreshExpandButton();
    });
  }

  // Parent and child cards are collapsible <details>. A chart first drawn while
  // its card is collapsed has zero width; when a card opens, nudge Plotly
  // (dcc.Graph responsive:true re-fits on window resize). `toggle` does not
  // bubble, so listen in the capture phase to catch every card. Also keep the
  // "Expand/Collapse all charts" button label in sync as child panels toggle.
  document.addEventListener(
    "toggle",
    function (evt) {
      var el = evt.target;
      if (!el || el.tagName !== "DETAILS") return;
      if (el.open) scheduleResize();
      if (el.classList.contains("pd-mev-model-panel")) {
        scheduleRefreshButton();
        // Lazy-load this panel's charts the first time it opens: click the
        // hidden trigger so the server builds them (they aren't rendered up
        // front). Once loaded, later opens reuse the built charts.
        if (el.open && el.dataset.saasChartsLoaded !== "true") {
          var trigger = el.querySelector(".saas-chart-trigger");
          if (trigger) {
            el.dataset.saasChartsLoaded = "true";
            trigger.click();
          }
        }
      }
    },
    true
  );

  // "Expand/Collapse all charts": the collapsed state keeps parent cards open
  // (so each child's segment summary stays visible) with the child chart panels
  // closed; the expanded state opens every child panel to reveal its charts.
  // IMPORTANT: only write when the value actually changes. This function runs
  // from mutation observers, and `textContent` assignment replaces the text
  // node even when the string is identical -- an unconditional write re-fires
  // the observer and locks the main thread in an infinite mutation loop.
  function setExpandButton(btn, expanded) {
    var state = expanded ? "expanded" : "collapsed";
    if (btn.getAttribute("data-saas-expand-all") !== state) {
      btn.setAttribute("data-saas-expand-all", state);
      btn.setAttribute("aria-expanded", expanded ? "true" : "false");
    }
    var label = expanded ? "Collapse all charts" : "Expand all charts";
    if (btn.textContent !== label) {
      btn.textContent = label;
    }
  }

  function applyExpandState(expanded) {
    document.querySelectorAll("#saas-mev-model-panels .pd-mev-model-group").forEach(function (card) {
      card.open = true;
    });
    document.querySelectorAll("#saas-mev-model-panels .pd-mev-model-panel").forEach(function (panel) {
      panel.open = expanded;
    });
    scheduleResize();
  }

  function refreshExpandButton() {
    var btn = document.querySelector(".saas-expand-all-btn");
    if (!btn) return;
    var panels = document.querySelectorAll("#saas-mev-model-panels .pd-mev-model-panel");
    // Hide the control when there are no chart panels (e.g. the apply prompt).
    // Change-only write: see setExpandButton.
    var display = panels.length ? "" : "none";
    if (btn.style.display !== display) {
      btn.style.display = display;
    }
    var anyOpen = Array.prototype.some.call(panels, function (panel) {
      return panel.open;
    });
    setExpandButton(btn, anyOpen);
  }

  function bindExpandAll() {
    var btn = document.querySelector(".saas-expand-all-btn");
    if (!btn || btn.dataset.saasExpandBound) return;
    btn.dataset.saasExpandBound = "true";
    btn.addEventListener("click", function () {
      var expanded = btn.getAttribute("data-saas-expand-all") !== "expanded";
      applyExpandState(expanded);
      setExpandButton(btn, expanded);
    });
  }

  function getScrollContainer() {
    return document.querySelector(".content");
  }

  function scrollToTarget(targetId) {
    var target = document.getElementById(targetId);
    var scrollContainer = getScrollContainer();
    if (!target || !scrollContainer) return;
    // Parent cards are collapsible <details>; expand before scrolling so the
    // navigated-to model is actually visible.
    if (target.tagName === "DETAILS") target.open = true;
    var contentRect = scrollContainer.getBoundingClientRect();
    var targetRect = target.getBoundingClientRect();
    var top = scrollContainer.scrollTop + targetRect.top - contentRect.top - 10;
    scrollContainer.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }

  function setActiveChip(targetId) {
    document.querySelectorAll("[data-saas-scroll-target]").forEach(function (chip) {
      chip.classList.toggle("active", chip.getAttribute("data-saas-scroll-target") === targetId);
    });
  }

  function updateActiveChipFromScroll() {
    var subnav = document.getElementById("saas-subnav");
    var chips = subnav ? subnav.querySelectorAll("[data-saas-scroll-target]") : [];
    if (!chips.length) return;
    var anchorLine = subnav.getBoundingClientRect().bottom + 36;
    var activeTargetId = chips[0].getAttribute("data-saas-scroll-target");
    chips.forEach(function (chip) {
      var targetId = chip.getAttribute("data-saas-scroll-target");
      var section = document.getElementById(targetId);
      if (section && section.getBoundingClientRect().top <= anchorLine) {
        activeTargetId = targetId;
      }
    });
    setActiveChip(activeTargetId);
  }

  function onScroll() {
    if (scrollFrame !== null) return;
    scrollFrame = window.requestAnimationFrame(function () {
      scrollFrame = null;
      updateActiveChipFromScroll();
    });
  }

  function onClick(evt) {
    var chip = evt.target.closest("[data-saas-scroll-target]");
    if (!chip) return;
    evt.preventDefault();
    setActiveChip(chip.getAttribute("data-saas-scroll-target"));
    scrollToTarget(chip.getAttribute("data-saas-scroll-target"));
  }

  function bind() {
    // The expand/collapse-all button lives in the static page layout, so bind
    // it (idempotently) and sync its state on every (re)bind. bind() fires from
    // the #page-content MutationObserver, so the refresh is rAF-coalesced.
    bindExpandAll();
    scheduleRefreshButton();

    var subnav = document.getElementById("saas-subnav");
    if (!subnav || subnav.dataset.saasSubnavBound) return;
    subnav.dataset.saasSubnavBound = "true";
    subnav.addEventListener("click", onClick);

    var scrollContainer = getScrollContainer();
    (scrollContainer || window).addEventListener("scroll", onScroll, { passive: true });

    var panels = document.getElementById("saas-mev-model-panels");
    if (panels) {
      // Deep (subtree) mutations fire constantly while Plotly draws; keep the
      // scroll-spy on them but throttle it (onScroll is rAF-guarded).
      new MutationObserver(onScroll).observe(panels, { childList: true, subtree: true });
      // A filter re-render only replaces the direct children (the parent cards),
      // which collapses every panel -- refresh the button then, not on every
      // deep Plotly mutation.
      new MutationObserver(scheduleRefreshButton).observe(panels, { childList: true });
    }

    updateActiveChipFromScroll();
  }

  // `#saas-subnav` is rebuilt whenever Dash re-renders `#page-content`
  // (e.g. navigating away from /saas and back). Watch for that and
  // (re)bind to whichever `#saas-subnav` instance is currently live.
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
