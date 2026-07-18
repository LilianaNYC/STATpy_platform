/* Click-outside-to-close for the dropdown-style menus that otherwise only
   close by re-clicking their own toggle:

   1. `.checkbox-dropdown` filter menus shared by Monitoring and SAAS
      (build_single_select_dropdown and the SAAS checkbox-dropdown builder
      both use this toggle/menu markup). Selecting an option leaves the menu
      open (multi-selects need that), so the click-away is the only close
      affordance besides the toggle. We simulate a click on the toggle button
      rather than editing the menu's className directly: className is a
      Dash-owned prop (State(menu_id, "className") drives the toggle
      callback's own open/closed logic), so a direct DOM edit here would
      desync from what Dash thinks the className is and require two clicks to
      reopen. Clicking the toggle runs Dash's existing callback instead,
      keeping server-side state consistent.

   2. The SAAS "Export" menu, a native <details>/<summary> disclosure rather
      than a .checkbox-dropdown. Its `open` attribute is only ever
      Dash-written as an Output (forced closed when the applied-filters store
      changes), never read back as a State/Input, so there's no server-side
      toggle state to desync -- setting `.open = false` directly is safe. */
(function () {
  function closeOpenMenusOutside(target) {
    document.querySelectorAll(".checkbox-dropdown").forEach(function (wrapper) {
      var menu = wrapper.querySelector(".checkbox-dropdown-menu.open");
      if (!menu || wrapper.contains(target)) return;
      var toggle = wrapper.querySelector(".checkbox-dropdown-toggle");
      if (toggle) toggle.click();
    });

    document.querySelectorAll("details.saas-download-actions[open]").forEach(function (details) {
      if (!details.contains(target)) details.open = false;
    });
  }

  document.addEventListener("mousedown", function (evt) {
    closeOpenMenusOutside(evt.target);
  });
})();
