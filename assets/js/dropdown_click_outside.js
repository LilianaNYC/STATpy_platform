/* Click-outside-to-close for the `.checkbox-dropdown` filter menus shared by
   the Monitoring and SAAS dashboards (build_single_select_dropdown and the
   SAAS checkbox-dropdown builder both use this same toggle/menu markup).
   Selecting an option leaves the menu open (multi-selects need that), so the
   only way to close it today is re-clicking the toggle -- this adds the
   click-away affordance users expect from a dropdown.

   We simulate a click on the toggle button rather than editing the menu's
   className directly: className is a Dash-owned prop (State(menu_id,
   "className") drives the toggle callback's own open/closed logic), so a
   direct DOM edit here would desync from what Dash thinks the className is
   and require two clicks to reopen. Clicking the toggle runs Dash's existing
   callback instead, keeping server-side state consistent. */
(function () {
  function closeOpenMenusOutside(target) {
    document.querySelectorAll(".checkbox-dropdown").forEach(function (wrapper) {
      var menu = wrapper.querySelector(".checkbox-dropdown-menu.open");
      if (!menu || wrapper.contains(target)) return;
      var toggle = wrapper.querySelector(".checkbox-dropdown-toggle");
      if (toggle) toggle.click();
    });
  }

  document.addEventListener("mousedown", function (evt) {
    closeOpenMenusOutside(evt.target);
  });
})();
