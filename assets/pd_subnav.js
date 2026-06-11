/* Section sub-navigation behaviour for #pd-subnav.

   Port of `setMonitoringPdSubnavActive` / `updateMonitoringPdSubnavActiveState`
   / `jumpToMonitoringSection` from components/monitoring_layout.py: clicking a
   link smooth-scrolls to its target section, and the link/group whose section
   is currently at the top of the viewport is highlighted as "active" while
   the page scrolls. Implemented as a plain client-side script (Dash
   auto-loads any .js file placed in assets/) since this is purely
   presentational and has no effect on chart data or callback state. */
(function () {
  var SECTION_IDS = [
    "pd-analysis-scope",
    "pd-calibration-rag",
    "pd-discrimination-rag",
    "pd-balance-sheet-calibration",
    "pd-post-subjective-overview",
    "pd-transition-matrix-distance",
    "pd-population-stability-index",
    "pd-rank-ordering",
    "pd-sensitivity-analysis",
    "pd-mev-range",
  ];

  var scrollFrame = null;

  function getScrollContainer() {
    return document.querySelector(".content");
  }

  function setActive(sectionId) {
    var subnav = document.getElementById("pd-subnav");
    if (!subnav) return;
    subnav.querySelectorAll("[data-pd-subnav-target]").forEach(function (link) {
      var isActive = link.getAttribute("data-pd-subnav-target") === sectionId;
      link.classList.toggle("active", isActive);
      link.setAttribute("aria-current", isActive ? "location" : "false");
    });
    subnav.querySelectorAll(".pd-subnav-group").forEach(function (group) {
      group.classList.toggle("active", !!group.querySelector("[data-pd-subnav-target].active"));
    });
  }

  function updateActiveFromScroll() {
    var subnav = document.getElementById("pd-subnav");
    if (!subnav) return;
    var anchorLine = subnav.getBoundingClientRect().bottom + 36;
    var activeSectionId = SECTION_IDS[0];
    for (var i = 0; i < SECTION_IDS.length; i++) {
      var section = document.getElementById(SECTION_IDS[i]);
      if (!section) continue;
      if (section.getBoundingClientRect().top <= anchorLine) {
        activeSectionId = SECTION_IDS[i];
      } else {
        break;
      }
    }
    setActive(activeSectionId);
  }

  function onScroll() {
    if (scrollFrame !== null) return;
    scrollFrame = window.requestAnimationFrame(function () {
      scrollFrame = null;
      updateActiveFromScroll();
    });
  }

  function onClick(evt) {
    var link = evt.target.closest("[data-pd-subnav-target]");
    if (!link) return;
    var target = document.getElementById(link.getAttribute("data-pd-subnav-target"));
    var subnav = document.getElementById("pd-subnav");
    var scrollContainer = getScrollContainer();
    if (!target || !subnav) return;
    evt.preventDefault();
    setActive(link.getAttribute("data-pd-subnav-target"));
    if (scrollContainer) {
      var contentRect = scrollContainer.getBoundingClientRect();
      var targetRect = target.getBoundingClientRect();
      var top = scrollContainer.scrollTop + targetRect.top - contentRect.top - 10;
      scrollContainer.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
      return;
    }
    var windowTop = target.getBoundingClientRect().top + window.scrollY - subnav.getBoundingClientRect().height - 20;
    window.scrollTo({ top: Math.max(0, windowTop), behavior: "smooth" });
  }

  function bind() {
    var subnav = document.getElementById("pd-subnav");
    if (!subnav) {
      window.requestAnimationFrame(bind);
      return;
    }
    if (subnav.dataset.pdSubnavBound) return;
    subnav.dataset.pdSubnavBound = "true";
    subnav.addEventListener("click", onClick);
    var scrollContainer = getScrollContainer();
    if (scrollContainer) {
      scrollContainer.addEventListener("scroll", onScroll, { passive: true });
    } else {
      window.addEventListener("scroll", onScroll, { passive: true });
    }
    updateActiveFromScroll();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
