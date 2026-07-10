/* Section sub-navigation behaviour for #saas-subnav: highlights the "Models
   in Scope" chip whose model card is currently in view, and clicking a chip
   smooth-scrolls to that card. */
(function () {
  var scrollFrame = null;

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
      if (el.open) {
        window.requestAnimationFrame(function () {
          window.dispatchEvent(new Event("resize"));
        });
      }
      if (el.classList.contains("pd-mev-model-panel")) {
        refreshExpandButton();
      }
    },
    true
  );

  // "Expand/Collapse all charts": the collapsed state keeps parent cards open
  // (so each child's segment summary stays visible) with the child chart panels
  // closed; the expanded state opens every child panel to reveal its charts.
  function setExpandButton(btn, expanded) {
    btn.setAttribute("data-saas-expand-all", expanded ? "expanded" : "collapsed");
    btn.setAttribute("aria-expanded", expanded ? "true" : "false");
    btn.textContent = expanded ? "Collapse all charts" : "Expand all charts";
  }

  function applyExpandState(expanded) {
    document.querySelectorAll("#saas-mev-model-panels .pd-mev-model-group").forEach(function (card) {
      card.open = true;
    });
    document.querySelectorAll("#saas-mev-model-panels .pd-mev-model-panel").forEach(function (panel) {
      panel.open = expanded;
    });
    window.requestAnimationFrame(function () {
      window.dispatchEvent(new Event("resize"));
    });
  }

  function refreshExpandButton() {
    var btn = document.querySelector(".saas-expand-all-btn");
    if (!btn) return;
    var panels = document.querySelectorAll("#saas-mev-model-panels .pd-mev-model-panel");
    // Hide the control when there are no chart panels (e.g. the apply prompt).
    btn.style.display = panels.length ? "" : "none";
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
    // it (idempotently) and sync its state on every (re)bind.
    bindExpandAll();
    refreshExpandButton();

    var subnav = document.getElementById("saas-subnav");
    if (!subnav || subnav.dataset.saasSubnavBound) return;
    subnav.dataset.saasSubnavBound = "true";
    subnav.addEventListener("click", onClick);

    var scrollContainer = getScrollContainer();
    (scrollContainer || window).addEventListener("scroll", onScroll, { passive: true });

    var panels = document.getElementById("saas-mev-model-panels");
    if (panels) {
      // A filter re-render replaces the panels (collapsing every child); keep the
      // active chip and the expand-all button label in sync when that happens.
      new MutationObserver(function () {
        onScroll();
        refreshExpandButton();
      }).observe(panels, { childList: true, subtree: true });
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
