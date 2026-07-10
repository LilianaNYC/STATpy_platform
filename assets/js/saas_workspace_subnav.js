/* Section sub-navigation behaviour for #saas-subnav: highlights the "Models
   in Scope" chip whose model card is currently in view, and clicking a chip
   smooth-scrolls to that card. */
(function () {
  var scrollFrame = null;
  var resizeQueued = false;

  // Coalesce resize to at most once per animation frame (opening a card fires a
  // toggle + Plotly redraw; a resize per event would thrash the main thread).
  function scheduleResize() {
    if (resizeQueued) return;
    resizeQueued = true;
    window.requestAnimationFrame(function () {
      resizeQueued = false;
      window.dispatchEvent(new Event("resize"));
    });
  }

  // Parent and child cards are collapsible <details>. A chart first drawn while
  // its card is collapsed has zero width; when a card opens, nudge Plotly
  // (dcc.Graph responsive:true re-fits on window resize). `toggle` does not
  // bubble, so listen in the capture phase to catch every card.
  document.addEventListener(
    "toggle",
    function (evt) {
      var el = evt.target;
      if (!el || el.tagName !== "DETAILS") return;
      if (el.open) scheduleResize();
      // Lazy-load a child panel's charts the first time it opens: click the
      // hidden trigger so the server builds them (they aren't rendered up
      // front). Once loaded, later opens reuse the built charts.
      if (
        el.open &&
        el.classList.contains("pd-mev-model-panel") &&
        el.dataset.saasChartsLoaded !== "true"
      ) {
        var trigger = el.querySelector(".saas-chart-trigger");
        if (trigger) {
          el.dataset.saasChartsLoaded = "true";
          trigger.click();
        }
      }
    },
    true
  );

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
    var subnav = document.getElementById("saas-subnav");
    if (!subnav || subnav.dataset.saasSubnavBound) return;
    subnav.dataset.saasSubnavBound = "true";
    subnav.addEventListener("click", onClick);

    var scrollContainer = getScrollContainer();
    (scrollContainer || window).addEventListener("scroll", onScroll, { passive: true });

    var panels = document.getElementById("saas-mev-model-panels");
    if (panels) {
      // Deep (subtree) mutations fire while Plotly draws; keep the scroll-spy on
      // them but throttle it (onScroll is rAF-guarded).
      new MutationObserver(onScroll).observe(panels, { childList: true, subtree: true });
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
