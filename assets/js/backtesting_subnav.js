/* Section sub-navigation behaviour for #bt-subnav.

   Modelled on assets/js/monitoring_pd_subnav.js: clicking a link smooth-scrolls
   to its target section, and the link/group whose section is currently at the
   top of the viewport is highlighted as "active" while the page scrolls.

   A separate file rather than a shared one because the existing sub-nav scripts
   are each id-scoped (#pd-subnav, #saas-subnav) and keyed to their own
   data-attribute; generalising all three is a refactor of two working
   dashboards, which this milestone does not touch.

   Plain client-side script (Dash auto-loads any .js in assets/) since this is
   purely presentational and has no effect on chart data or callback state. */
(function () {
  var SECTION_IDS = [
    "bt-overview",
    "bt-pd",
    "bt-pd-crr",
    "bt-lgd",
    "bt-ead",
    "bt-nco",
  ];

  var TARGET_ATTR = "data-bt-subnav-target";
  var scrollFrame = null;

  function getScrollContainer() {
    return document.querySelector(".content");
  }

  function setActive(sectionId) {
    var subnav = document.getElementById("bt-subnav");
    if (!subnav) return;
    subnav.querySelectorAll("[" + TARGET_ATTR + "]").forEach(function (link) {
      var isActive = link.getAttribute(TARGET_ATTR) === sectionId;
      link.classList.toggle("active", isActive);
      link.setAttribute("aria-current", isActive ? "location" : "false");
    });
    subnav.querySelectorAll(".bt-subnav-group").forEach(function (group) {
      group.classList.toggle("active", !!group.querySelector("[" + TARGET_ATTR + "].active"));
    });
  }

  function updateActiveFromScroll() {
    var subnav = document.getElementById("bt-subnav");
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
    var link = evt.target.closest("[" + TARGET_ATTR + "]");
    if (!link) return;
    var target = document.getElementById(link.getAttribute(TARGET_ATTR));
    var subnav = document.getElementById("bt-subnav");
    var scrollContainer = getScrollContainer();
    if (!target || !subnav) return;
    evt.preventDefault();
    setActive(link.getAttribute(TARGET_ATTR));
    if (scrollContainer) {
      var contentRect = scrollContainer.getBoundingClientRect();
      var targetRect = target.getBoundingClientRect();
      var top = scrollContainer.scrollTop + targetRect.top - contentRect.top - 10;
      scrollContainer.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
      return;
    }
    var windowTop =
      target.getBoundingClientRect().top +
      window.scrollY -
      subnav.getBoundingClientRect().height -
      20;
    window.scrollTo({ top: Math.max(0, windowTop), behavior: "smooth" });
  }

  function bind() {
    var subnav = document.getElementById("bt-subnav");
    if (!subnav || subnav.dataset.btSubnavBound) return;
    subnav.dataset.btSubnavBound = "true";
    subnav.addEventListener("click", onClick);
    var scrollContainer = getScrollContainer();
    if (scrollContainer) {
      scrollContainer.addEventListener("scroll", onScroll, { passive: true });
    } else {
      window.addEventListener("scroll", onScroll, { passive: true });
    }
    updateActiveFromScroll();
  }

  /* #bt-subnav is rebuilt whenever Dash re-renders #page-content (including
     once right after initial load, since the router callback fires on the
     initial call too). Watch for that and (re)bind to whichever instance is
     currently live. The bound flag above makes repeat calls cheap. */
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
