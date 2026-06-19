/* Section sub-navigation behaviour for monitoring pages.

   Dash auto-loads this file from assets/. It handles both the PD page and the
   Overview page by reading the section ids from each rendered subnav's
   data-pd-subnav-target attributes. */
(function () {
  var scrollFrame = null;

  function getScrollContainer() {
    return document.querySelector(".content");
  }

  function getSubnavs() {
    return Array.prototype.slice.call(document.querySelectorAll(".monitoring-section-subnav"));
  }

  function getSectionIds(subnav) {
    return Array.prototype.slice.call(subnav.querySelectorAll("[data-pd-subnav-target]"))
      .map(function (link) { return link.getAttribute("data-pd-subnav-target"); })
      .filter(Boolean);
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

  function updateSubnavFromScroll(subnav) {
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

  function updateActiveFromScroll() {
    getSubnavs().forEach(updateSubnavFromScroll);
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
    var subnav = link.closest(".monitoring-section-subnav");
    var target = document.getElementById(link.getAttribute("data-pd-subnav-target"));
    var scrollContainer = getScrollContainer();
    if (!target || !subnav) return;
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

  function bindAvailableSubnavs() {
    var subnavs = getSubnavs();
    subnavs.forEach(function (subnav) {
      if (subnav.dataset.monitoringSubnavBound) return;
      subnav.dataset.monitoringSubnavBound = "true";
      subnav.addEventListener("click", onClick);
    });
    var scrollContainer = getScrollContainer();
    if (scrollContainer && !scrollContainer.dataset.monitoringSubnavScrollBound) {
      scrollContainer.dataset.monitoringSubnavScrollBound = "true";
      scrollContainer.addEventListener("scroll", onScroll, { passive: true });
    } else if (!scrollContainer && !window.monitoringSubnavScrollBound) {
      window.monitoringSubnavScrollBound = true;
      window.addEventListener("scroll", onScroll, { passive: true });
    }
    if (subnavs.length) updateActiveFromScroll();
  }

  function bind() {
    bindAvailableSubnavs();
    var observer = new MutationObserver(function () {
      bindAvailableSubnavs();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
