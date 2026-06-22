/* Section sub-navigation behaviour for #saas-subnav: highlights the "Models
   in Scope" chip whose model card is currently in view, and clicking a chip
   smooth-scrolls to that card. */
(function () {
  var scrollFrame = null;

  function getScrollContainer() {
    return document.querySelector(".content");
  }

  function scrollToTarget(targetId) {
    var target = document.getElementById(targetId);
    var scrollContainer = getScrollContainer();
    if (!target || !scrollContainer) return;
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
