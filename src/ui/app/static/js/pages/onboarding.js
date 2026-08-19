/**
 * Guided walkthrough: the navbar pill and the offcanvas drawer behind it.
 *
 * Loaded only while the walkthrough is active (the partial that carries this script tag is
 * itself gated), so a user who finished or dismissed it downloads nothing and issues no
 * request.
 *
 * Step completion is never tracked here. Every render comes from GET /onboarding/state,
 * which re-derives it from live signals — so navigating to a page and doing the thing ticks
 * the step on the next fetch with no client-side bookkeeping to get out of sync.
 */
(function () {
  "use strict";

  const root = document.getElementById("onboarding-root");
  if (!root) return;

  const STATE_URL = root.dataset.stateUrl;
  const CACHE_KEY = "bw-onboarding-state";
  const drawerEl = document.getElementById("side-offcanvas-onboarding");
  const listEl = document.getElementById("onboarding-steps");
  const errorEl = document.getElementById("onboarding-error");
  const barEl = document.getElementById("onboarding-progress-bar");
  const labelEl = document.getElementById("onboarding-progress-label");
  const countEl = document.getElementById("onboarding-count");
  const pillEl = document.getElementById("onboarding-button");
  const hintEl = document.getElementById("onboarding-hint");
  const PAGE_ID = root.dataset.pageId || "";

  // The catalog is a global loaded before this file runs, so a lookup is always answerable and
  // the blank-row problem this used to poll around is gone. The fallback stays for the one case
  // the catalog cannot cover: a key that is simply missing.
  const t = (key, fallback) => {
    if (!window.t) return fallback;
    const value = window.t(key, { defaultValue: fallback });
    return typeof value === "string" && value ? value : fallback;
  };

  const request = (method, body) =>
    fetch(STATE_URL, {
      method,
      credentials: "same-origin",
      headers: Object.assign(
        { "X-Requested-With": "XMLHttpRequest" },
        body ? { "Content-Type": "application/json" } : {},
      ),
      body: body ? JSON.stringify(body) : undefined,
    }).then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    });

  /** Hide both surfaces for good. Called on dismissal and on completion. */
  function retire() {
    if (pillEl && pillEl.parentElement) pillEl.parentElement.remove();
    if (drawerEl) {
      const instance =
        window.bootstrap && window.bootstrap.Offcanvas.getInstance(drawerEl);
      if (instance) instance.hide();
      drawerEl.remove();
    }
    sessionStorage.removeItem(CACHE_KEY);
  }

  function renderSteps(state) {
    listEl.replaceChildren();
    state.steps.forEach((step) => {
      const row = document.createElement("div");
      row.className = `d-flex align-items-center gap-2 py-2${step.done ? "" : " text-muted"}`;
      row.dataset.stepId = step.id;

      const icon = document.createElement("i");
      icon.className = `bx ${step.done ? "bx-check-circle text-success" : "bx-circle"} flex-shrink-0`;
      icon.setAttribute("aria-hidden", "true");

      // The icon is decorative, so the state has to be said out loud too.
      const sr = document.createElement("span");
      sr.className = "visually-hidden";
      sr.textContent = step.done
        ? t("status.done", "Completed")
        : t("status.pending", "Pending");

      const text = document.createElement("span");
      text.textContent = t(step.i18n_key, step.en);

      row.append(icon, sr, text);

      // One trailing group so the chip and the two actions cannot fight over `ms-auto`.
      const trailing = document.createElement("div");
      trailing.className = "ms-auto d-flex align-items-center gap-2";

      // The chip is what says "this one is not holding you back" — it has to show while the
      // step is still pending, which is the only moment the distinction matters.
      if (step.optional) {
        const chip = document.createElement("span");
        chip.className = "badge bg-label-secondary";
        chip.textContent = t("status.optional", "Optional");
        trailing.append(chip);
      }

      if (!step.done && step.anchor) {
        const show = document.createElement("button");
        show.type = "button";
        show.className = "btn btn-link btn-sm p-0 small text-nowrap";
        show.textContent = t("button.show_me", "Show me");
        show.addEventListener("click", () => spotlight(step));
        trailing.append(show);
      }

      if (!step.done && step.target) {
        const link = document.createElement("a");
        link.className = "small text-nowrap";
        link.href = step.target;
        link.textContent = t("button.go", "Go →");
        trailing.append(link);
      }

      if (trailing.children.length) row.append(trailing);

      listEl.append(row);
    });
  }

  /**
   * Point at where a thing lives, on demand.
   *
   * Opt-in only: nothing spotlights itself. The anchor is a `data-tour` name the chrome
   * carries, so a step points at the sidebar entry rather than at a coordinate — a menu
   * reorder cannot break it, and a deleted anchor degrades to a button that does nothing
   * rather than to a broken page. `test_every_spotlight_anchor_exists_in_a_template` is what
   * keeps that last case theoretical.
   */
  function spotlight(step) {
    const target = document.querySelector(`[data-tour="${step.anchor}"]`);
    if (!target) return;

    // The drawer covers the chrome it is pointing at.
    if (drawerEl && window.bootstrap) {
      const instance = window.bootstrap.Offcanvas.getInstance(drawerEl);
      if (instance) instance.hide();
    }

    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    target.scrollIntoView({
      behavior: reduced ? "auto" : "smooth",
      block: "center",
    });
    target.classList.add("bw-tour-target");

    let popover = null;
    if (window.bootstrap && window.bootstrap.Popover) {
      popover = new window.bootstrap.Popover(target, {
        content: t(step.i18n_key, step.en),
        placement: "right",
        trigger: "manual",
        container: "body",
        customClass: "bw-tour-popover",
      });
      popover.show();
    }

    const clear = () => {
      target.classList.remove("bw-tour-target");
      if (popover) popover.dispose();
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("click", onClick, true);
      clearTimeout(timer);
    };
    const onKey = (event) => {
      if (event.key === "Escape") clear();
    };
    // Any click ends it, including the one on the thing being pointed at — the user has
    // found it, which is the entire goal.
    const onClick = () => clear();

    const timer = setTimeout(clear, 8000);
    document.addEventListener("keydown", onKey, true);
    setTimeout(() => document.addEventListener("click", onClick, true), 0);
  }

  /**
   * The per-page orientation hint.
   *
   * Driven by the same catalog as the drawer: the hint shows only while a `read_<page>` step
   * is pending for this user, and acknowledging it is what ticks that step. Nothing here
   * knows which pages have hints — a step added to the catalog gets one for free, and a
   * track without orientation steps never renders one.
   */
  function renderHint(state) {
    if (!hintEl) return;
    hintEl.replaceChildren();
    if (!PAGE_ID) return;

    const step = state.steps.find((entry) => entry.id === `read_${PAGE_ID}`);
    if (!step || step.done) return;

    const toast = document.createElement("div");
    toast.className = "toast show";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    toast.setAttribute("aria-atomic", "true");

    const header = document.createElement("div");
    header.className = "toast-header";

    const icon = document.createElement("i");
    icon.className = "bx bx-compass me-2";
    icon.setAttribute("aria-hidden", "true");

    const title = document.createElement("strong");
    title.className = "me-auto";
    title.textContent = t("onboarding.hint.title", "Quick tour");

    // Closing without acknowledging: the hint is back on the next visit, which is the point —
    // the step is not done, and pretending otherwise would tick it off the checklist.
    const close = document.createElement("button");
    close.type = "button";
    close.className = "btn-close";
    close.setAttribute("aria-label", t("aria.label.close", "Close"));
    close.addEventListener("click", () => hintEl.replaceChildren());

    header.append(icon, title, close);

    const body = document.createElement("div");
    body.className = "toast-body";

    const text = document.createElement("p");
    text.className = "mb-2";
    text.textContent = t(
      `onboarding.hint.${PAGE_ID}`,
      t(step.i18n_key, step.en),
    );

    const ack = document.createElement("button");
    ack.type = "button";
    ack.className = "btn btn-sm btn-primary";
    ack.textContent = t("button.got_it", "Got it");
    ack.addEventListener("click", () => {
      ack.disabled = true;
      request("PATCH", { ack_hint: PAGE_ID })
        .then((result) => {
          // Read-only database: 200 with saved:false. Leave the hint standing and say so
          // rather than ticking a step that was never stored.
          if (result && result.saved === false) {
            text.textContent =
              result.message ||
              t("onboarding.not_saved", "This could not be saved.");
            ack.disabled = false;
            return;
          }
          load();
        })
        .catch(() => {
          ack.disabled = false;
        });
    });

    body.append(text, ack);
    toast.append(header, body);
    hintEl.append(toast);
  }

  function render(state) {
    errorEl.classList.add("d-none");
    renderSteps(state);

    const pct = state.total ? Math.round((state.done / state.total) * 100) : 0;
    barEl.style.width = `${pct}%`;
    barEl.setAttribute("aria-valuenow", String(pct));
    labelEl.textContent = `${state.done}/${state.total}`;

    const remaining = Math.max(state.total - state.done, 0);
    if (countEl) {
      countEl.textContent = String(remaining);
      countEl.classList.toggle("d-none", remaining === 0);
    }

    if (state.completed) celebrate();
  }

  /** Fires once: the PATCH clears the session flag, so the surfaces never come back. */
  function celebrate() {
    request("PATCH", { completed: true })
      .catch(() => {})
      .finally(() => {
        const src = root.dataset.confettiSrc;
        if (
          !src ||
          window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ) {
          retire();
          return;
        }
        const script = document.createElement("script");
        script.src = src;
        script.onload = () => {
          if (window.confetti)
            window.confetti({
              particleCount: 120,
              spread: 70,
              origin: { y: 0.7 },
            });
          setTimeout(retire, 2500);
        };
        script.onerror = () => retire();
        document.head.append(script);
      });
  }

  function load() {
    return request("GET")
      .then((state) => {
        sessionStorage.setItem(CACHE_KEY, JSON.stringify(state));
        render(state);
        // Only the live state may raise a hint. Painting one from the tab cache would flash a
        // hint another tab has already acknowledged.
        renderHint(state);
        return state;
      })
      .catch(() => {
        errorEl.classList.remove("d-none");
        return null;
      });
  }

  // Paint from the tab-local copy first so opening the drawer is never a blank panel, then
  // refresh. The cache is per tab and per session: it is a paint shortcut, not state.
  const cached = sessionStorage.getItem(CACHE_KEY);
  if (cached) {
    try {
      render(JSON.parse(cached));
    } catch (e) {
      sessionStorage.removeItem(CACHE_KEY);
    }
  }

  load().then((state) => {
    if (!state || state.completed) return;
    if (
      root.dataset.autoopen === "yes" &&
      !state.opened &&
      window.bootstrap &&
      drawerEl
    ) {
      window.bootstrap.Offcanvas.getOrCreateInstance(drawerEl).show();
      request("PATCH", { opened: true }).catch(() => {});
    }
  });

  // Opening always refetches: the user has usually just done something on another page.
  if (drawerEl) drawerEl.addEventListener("show.bs.offcanvas", () => load());

  const dismissEl = document.getElementById("onboarding-dismiss");
  if (dismissEl) {
    dismissEl.addEventListener("click", () => {
      dismissEl.disabled = true;
      request("PATCH", { dismissed: true })
        .then((result) => {
          // A read-only database answers 200 with saved:false. Say so rather than removing a
          // pill that will be back on the next page load.
          if (result && result.saved === false) {
            errorEl.textContent =
              result.message ||
              t("onboarding.not_saved", "This could not be saved.");
            errorEl.classList.remove("d-none");
            dismissEl.disabled = false;
            return;
          }
          retire();
        })
        .catch(() => {
          errorEl.classList.remove("d-none");
          dismissEl.disabled = false;
        });
    });
  }

  const retryEl = document.getElementById("onboarding-retry");
  if (retryEl) retryEl.addEventListener("click", () => load());
})();
