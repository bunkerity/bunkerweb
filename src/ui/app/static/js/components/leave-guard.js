/* Existing page dirty-state logic stays authoritative. Native beforeunload covers
   refresh/close; this modal covers same-tab links and explicit confirmLeave calls. */
(function () {
  "use strict";
  if (window.BWLeaveGuard) return;
  window.BWLeaveGuard = {
    create({ isDirty }) {
      if (typeof isDirty !== "function")
        throw new TypeError(`BWLeaveGuard requires isDirty`);
      let bypass = false;
      let pending = false;
      const beforeUnload = (event) => {
        if (bypass || !isDirty()) return;
        event.preventDefault();
        event.returnValue = "";
      };
      const confirmLeave = async (action) => {
        if (pending) return false;
        if (isDirty()) {
          pending = true;
          const t = window.i18next?.t || ((key, fallback) => fallback || key);
          let leave;
          try {
            leave = await window.BWConfirm.open({
              title: t("table_system.leave_title", "Leave without saving?"),
              message: t(
                "table_system.leave_message",
                "Your unsaved changes will be lost.",
              ),
              confirmLabel: t("table_system.leave", "Leave without saving"),
              cancelLabel: t("table_system.stay", "Keep editing"),
              destructive: false,
            });
          } finally {
            pending = false;
          }
          if (!leave) return false;
        }
        bypass = true;
        try {
          await action();
        } finally {
          bypass = false;
        }
        return true;
      };
      const click = (event) => {
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        )
          return;
        const link = event.target.closest?.("a[href]");
        if (
          !link ||
          link.getAttribute("href").startsWith("#") ||
          link.hasAttribute("download") ||
          (link.target && link.target !== "_self") ||
          link.hasAttribute("data-bs-toggle") ||
          !isDirty()
        )
          return;
        const url = new URL(link.href, location.href);
        if (
          !/^https?:$/.test(url.protocol) ||
          (url.origin === location.origin &&
            url.pathname === location.pathname &&
            url.search === location.search &&
            url.hash)
        )
          return;
        event.preventDefault();
        event.stopImmediatePropagation();
        confirmLeave(() => {
          location.assign(url.href);
        });
      };
      window.addEventListener("beforeunload", beforeUnload);
      document.addEventListener("click", click, true);
      return {
        confirmLeave,
        dispose() {
          window.removeEventListener("beforeunload", beforeUnload);
          document.removeEventListener("click", click, true);
        },
      };
    },
  };
})();
