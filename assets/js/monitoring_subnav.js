/* Generic section sub-navigation for all monitoring page subnavs.

   Works for any element with class `monitoring-section-subnav`: clicking a
   link smooth-scrolls to its target section, and the link/group whose section
   is currently at the top of the viewport is highlighted as "active". */
(function () {
  var SUBNAV_IDS = [
    "overview-subnav",
    "lgd-subnav",
    "ead-subnav",
    "loss-subnav",
  ];

  var scrollFrames = {};

  function getScrollContainer() {
    return document.querySelector(".content");
  }

  function getSectionIds(subnav) {
    var ids = [];
    subnav.querySelectorAll("[data-pd-subnav-target]").forEach(function (link) {
      var id = link.getAttribute("data-pd-subnav-target");
      if (id && ids.indexOf(id) === -1) ids.push(id);
    });
    return ids;
  }

  function setActive(subnav, sectionId) {
    subnav.querySelectorAll("[data-pd-subnav-target]").forEach(function (link) {
      var isActive = link.getAttribute("data-pd-subnav-target") === sectionId;
      link.classList.toggle("active", isActive);
      link.setAttribute("aria-current", isActive ? "location" : "false");
    });
    subnav.querySelectorAll(".pd-subnav-group").forEach(function (group) {
      group.classList.toggle("active", !!group.querySelector("[data-pd-subnav-target].active"));
    });
  }

  function updateActiveFromScroll(subnavId) {
    var subnav = document.getElementById(subnavId);
    if (!subnav) return;
    var sectionIds = getSectionIds(subnav);
    if (!sectionIds.length) return;
    var anchorLine = subnav.getBoundingClientRect().bottom + 36;
    var activeSectionId = sectionIds[0];
    for (var i = 0; i < sectionIds.length; i++) {
      var section = document.getElementById(sectionIds[i]);
      if (!section) continue;
      if (section.getBoundingClientRect().top <= anchorLine) {
        activeSectionId = sectionIds[i];
      } else {
        break;
      }
    }
    setActive(subnav, activeSectionId);
  }

  function onScroll(subnavId) {
    if (scrollFrames[subnavId]) return;
    scrollFrames[subnavId] = window.requestAnimationFrame(function () {
      scrollFrames[subnavId] = null;
      updateActiveFromScroll(subnavId);
    });
  }

  function onClick(evt) {
    var link = evt.target.closest("[data-pd-subnav-target]");
    if (!link) return;
    var subnav = link.closest(".monitoring-section-subnav");
    if (!subnav) return;
    var target = document.getElementById(link.getAttribute("data-pd-subnav-target"));
    var scrollContainer = getScrollContainer();
    if (!target) return;
    evt.preventDefault();
    setActive(subnav, link.getAttribute("data-pd-subnav-target"));
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

  function bindSubnav(subnavId) {
    var subnav = document.getElementById(subnavId);
    if (!subnav || subnav.dataset.subnavBound) return;
    subnav.dataset.subnavBound = "true";
    subnav.addEventListener("click", onClick);
    var scrollContainer = getScrollContainer();
    if (scrollContainer) {
      scrollContainer.addEventListener("scroll", function () { onScroll(subnavId); }, { passive: true });
    } else {
      window.addEventListener("scroll", function () { onScroll(subnavId); }, { passive: true });
    }
    updateActiveFromScroll(subnavId);
  }

  function bindAll() {
    SUBNAV_IDS.forEach(bindSubnav);
  }

  function observePageContent() {
    var pageContent = document.getElementById("page-content");
    if (!pageContent) {
      window.requestAnimationFrame(observePageContent);
      return;
    }
    new MutationObserver(bindAll).observe(pageContent, { childList: true, subtree: true });
    bindAll();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", observePageContent);
  } else {
    observePageContent();
  }
})();
