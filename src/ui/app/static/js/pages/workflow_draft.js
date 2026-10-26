/* One active workflow draft per browser tab, shared by the Overview and Configuration pages.
 *
 * Overview and Configuration are separate documents, so an unsaved rule edit would be lost
 * the moment the operator clicked the other tab. The editor therefore writes its draft here
 * (sessionStorage, so it never reaches another tab or outlives this one) and restores it when
 * the same workflow is opened again. Only one workflow can hold a draft: opening another one
 * first asks the operator to save, discard or keep the current draft.
 *
 * The record carries the serialised definition the draft started from (`base`). A draft whose
 * base no longer matches the stored workflow is stale and is dropped by the editor rather than
 * restored over someone else's save.
 */
(function () {
  "use strict";
  if (window.BWWorkflowDraft) return;

  var DRAFT_KEY = "bw-workflow-draft";
  var ACTIVE_KEY = "bw-workflow-active";
  var busy = false;

  function translate(key, fallback, options) {
    var text = fallback;
    if (window.i18next && window.i18next.isInitialized) {
      var settings = {
        defaultValue: fallback,
        interpolation: { escapeValue: false },
      };
      for (var name in options || {}) {
        if (Object.prototype.hasOwnProperty.call(options, name))
          settings[name] = options[name];
      }
      return window.i18next.t(key, settings);
    }
    return String(text).replace(/\{\{(\w+)\}\}/g, function (whole, name) {
      return options && Object.prototype.hasOwnProperty.call(options, name)
        ? String(options[name])
        : whole;
    });
  }

  function read() {
    var record = null;
    try {
      record = JSON.parse(window.sessionStorage.getItem(DRAFT_KEY) || "null");
    } catch (error) {
      return null;
    }
    if (
      !record ||
      typeof record.id !== "string" ||
      typeof record.base !== "string" ||
      typeof record.draft !== "string"
    )
      return null;
    return record;
  }

  function refreshBadges() {
    var record = read();
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-wf-dirty-badge]"),
      function (badge) {
        badge.hidden = !record;
      },
    );
  }

  function write(record) {
    try {
      window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(record));
    } catch (error) {
      /* storage disabled or full: the page still works, the draft just is not retained */
    }
    refreshBadges();
  }

  /* With an id, only that workflow's draft is dropped, so a page can never erase another
     workflow's pending changes. */
  function clear(id) {
    var record = read();
    if (id && record && record.id !== id) return;
    try {
      window.sessionStorage.removeItem(DRAFT_KEY);
    } catch (error) {
      /* nothing stored, nothing to clear */
    }
    refreshBadges();
  }

  function activeId() {
    try {
      return window.sessionStorage.getItem(ACTIVE_KEY) || "";
    } catch (error) {
      return "";
    }
  }

  function setActive(id) {
    try {
      window.sessionStorage.setItem(ACTIVE_KEY, id);
    } catch (error) {
      /* the Configuration tab falls back to the first workflow */
    }
  }

  /* Save / Discard / Cancel. `onSave` runs while the dialog stays open and resolves to
     {ok, message}: a failed save keeps the dialog and the draft and says why. Escape and the
     backdrop mean Cancel, never Discard. */
  function choose(options) {
    if (busy) return Promise.resolve("cancel");
    busy = true;
    var previousFocus = document.activeElement;
    var root = document.createElement("div");
    root.classList.add("modal", "fade");
    root.tabIndex = -1;
    root.setAttribute("aria-labelledby", "wf-draft-title");
    root.setAttribute("aria-hidden", "true");
    root.innerHTML =
      '<div class="modal-dialog modal-dialog-centered"><div class="modal-content">' +
      '<div class="modal-header"><h5 class="modal-title" id="wf-draft-title"></h5></div>' +
      '<div class="modal-body"><p class="wf-draft-message mb-0"></p>' +
      '<div class="alert alert-danger mt-3 mb-0" role="alert" hidden></div></div>' +
      '<div class="modal-footer">' +
      '<button type="button" class="btn btn-outline-secondary" data-wf-draft="cancel"></button>' +
      '<button type="button" class="btn btn-outline-danger" data-wf-draft="discard"></button>' +
      '<button type="button" class="btn btn-primary" data-wf-draft="save"></button>' +
      "</div></div></div>";
    root.querySelector(".modal-title").textContent = options.title;
    root.querySelector(".wf-draft-message").textContent = options.message;
    var buttons = {};
    Array.prototype.forEach.call(
      root.querySelectorAll("[data-wf-draft]"),
      function (button) {
        buttons[button.dataset.wfDraft] = button;
      },
    );
    buttons.cancel.textContent = translate("button.cancel", "Cancel");
    buttons.discard.textContent = translate(
      "workflows.shell.draft_discard",
      "Discard changes",
    );
    buttons.save.textContent = translate(
      "workflows.shell.draft_save",
      "Save and continue",
    );
    var failure = root.querySelector(".alert");
    document.body.append(root);
    var modal = new window.bootstrap.Modal(root);
    return new Promise(function (resolve) {
      var choice = "cancel";
      var saving = false;
      buttons.cancel.addEventListener("click", function () {
        modal.hide();
      });
      buttons.discard.addEventListener("click", function () {
        choice = "discard";
        modal.hide();
      });
      buttons.save.addEventListener("click", function () {
        if (saving) return;
        saving = true;
        failure.hidden = true;
        Object.keys(buttons).forEach(function (name) {
          buttons[name].disabled = true;
        });
        Promise.resolve(options.onSave())
          .catch(function () {
            return { ok: false, message: "" };
          })
          .then(function (result) {
            saving = false;
            if (result && result.ok) {
              choice = "save";
              modal.hide();
              return;
            }
            failure.textContent =
              (result && result.message) ||
              translate(
                "workflows.shell.draft_save_failed",
                "Could not save the workflow; nothing was discarded.",
              );
            failure.hidden = false;
            Object.keys(buttons).forEach(function (name) {
              buttons[name].disabled = false;
            });
          });
      });
      root.addEventListener("hide.bs.modal", function (event) {
        if (saving) event.preventDefault();
      });
      root.addEventListener("shown.bs.modal", function () {
        buttons.cancel.focus();
      });
      root.addEventListener("hidden.bs.modal", function () {
        modal.dispose();
        root.remove();
        busy = false;
        if (previousFocus && previousFocus.isConnected) previousFocus.focus();
        resolve(choice);
      });
      modal.show();
    });
  }

  function post(url, csrf, definition) {
    return window
      .fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify({ definition: definition }),
      })
      .then(function (response) {
        return response.json();
      })
      .then(function (body) {
        return { ok: body.status === "success", message: body.message || "" };
      });
  }

  /* Opening workflow `targetId` while another workflow holds the draft. Resolves true when
     the caller may go on (no foreign draft, discarded, or saved) and false on Cancel. The
     draft is saved through the same endpoint the editor uses, so the API re-validates it. */
  function resolveForeign(options) {
    var record = read();
    if (!record || record.id === options.targetId) return Promise.resolve(true);
    return choose({
      title: translate(
        "workflows.shell.draft_title",
        "Unsaved changes in {{name}}",
        { name: record.name || record.id },
      ),
      message: translate(
        "workflows.shell.draft_switch_message",
        "Opening {{target}} would leave unsaved rule changes in {{name}}. Only one draft can be open at a time: save it, discard it, or stay.",
        {
          target: options.targetName || options.targetId,
          name: record.name || record.id,
        },
      ),
      onSave: function () {
        var definition;
        try {
          definition = JSON.parse(record.draft);
        } catch (error) {
          return { ok: false, message: "" };
        }
        return post(
          options.workflowsUrl + "/" + encodeURIComponent(record.id) + "/save",
          options.csrf,
          definition,
        );
      },
    }).then(function (choice) {
      if (choice === "cancel") return false;
      clear(record.id);
      return true;
    });
  }

  /* Tab and View-select navigation keeps the draft on purpose; the editor's leave guard reads
     this flag so it does not ask "leave without saving?" for a move it is about to retain. */
  var api = {
    sectionNav: false,
    read: read,
    write: write,
    clear: clear,
    activeId: activeId,
    setActive: setActive,
    choose: choose,
    post: post,
    resolveForeign: resolveForeign,
    translate: translate,
    refreshBadges: refreshBadges,
  };
  window.BWWorkflowDraft = api;

  document.addEventListener(
    "click",
    function (event) {
      if (
        event.target.closest &&
        event.target.closest("[data-wf-section-link]")
      ) {
        api.sectionNav = true;
        window.setTimeout(function () {
          api.sectionNav = false;
        }, 0);
      }
    },
    true,
  );

  document.addEventListener("change", function (event) {
    var select = event.target;
    if (!select.matches || !select.matches("[data-wf-view-select]")) return;
    api.sectionNav = true;
    window.location.assign(select.value);
  });

  /* The API sends ISO timestamps; show them the way the operator's locale writes dates. The
     datetime attribute keeps the raw value for sorting and for assistive tech. */
  function formatDates() {
    var format;
    try {
      format = new Intl.DateTimeFormat(
        document.documentElement.lang || undefined,
        {
          dateStyle: "medium",
          timeStyle: "short",
        },
      );
    } catch (error) {
      return;
    }
    Array.prototype.forEach.call(
      document.querySelectorAll("time[data-wf-date]"),
      function (node) {
        var date = new Date(node.getAttribute("datetime"));
        if (!isNaN(date.getTime())) node.textContent = format.format(date);
      },
    );
  }

  function ready() {
    refreshBadges();
    formatDates();
  }
  document.addEventListener("DOMContentLoaded", ready);
  if (document.readyState !== "loading") ready();
})();
