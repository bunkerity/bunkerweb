/**
 * Pre-save validation for the customcert certificate/key pair.
 *
 * Custom certificates are loaded at runtime by ssl_certificate_by_lua, so a bad
 * pair does not fail nginx -t. It logs one line and the service falls back to the
 * default certificate, which means the first signal the operator gets is a browser
 * warning on a service that was working a minute ago. This puts the answer next to
 * the fields instead.
 *
 * Only the data settings can be checked: CUSTOM_SSL_CERT and CUSTOM_SSL_KEY point
 * at the scheduler's filesystem, which the UI is not on in any integration but
 * all-in-one.
 */

const CERT_SETTING = "CUSTOM_SSL_CERT_DATA";
const KEY_SETTING = "CUSTOM_SSL_KEY_DATA";
const KEY_ID_SUFFIX = "custom-ssl-key-data";
const CERT_ID_SUFFIX = "custom-ssl-cert-data";
const PRIORITY_ID_SUFFIX = "custom-ssl-cert-priority";
const SERVER_NAME_ID_SUFFIX = "server-name";

// Settings render with a per-mode id prefix (easy, advanced, pro), so the two
// halves of a pair are found through each other's id rather than by walking up to
// a container that is shaped differently in every mode.
const siblingSetting = (element, suffix) => {
  const id = String(element.id || "");
  if (!id.endsWith(KEY_ID_SUFFIX)) return $();
  return $(
    document.getElementById(id.slice(0, -KEY_ID_SUFFIX.length) + suffix),
  );
};

const settingValue = ($input) => String($input.val() ?? "").trim();

export function initCertificateValidation(t) {
  const endpoint = $("#validate-certificate-url").val();
  if (!endpoint) return;

  $(`input.plugin-setting-file-text[name="${KEY_SETTING}"]`).each(function () {
    const $key = $(this);
    const $cert = siblingSetting(this, CERT_ID_SUFFIX);
    if (!$cert.length || $cert.attr("name") !== CERT_SETTING) return;

    const $priority = siblingSetting(this, PRIORITY_ID_SUFFIX);
    const $siblingServerName = siblingSetting(this, SERVER_NAME_ID_SUFFIX);
    const $wrapper = $key.closest(".plugin-file-setting-wrapper");
    if (!$wrapper.length) return;

    const $button = $("<button>", {
      type: "button",
      class:
        "btn btn-outline-primary btn-sm align-self-start certificate-validate-btn",
    }).append(
      $("<i>", { class: "bx bx-shield-quarter" }),
      $("<span>", {
        class: "ms-1",
        "data-i18n": "button.validate_certificate",
        text: t("button.validate_certificate"),
      }),
    );
    const $result = $("<small>", {
      class: "d-block mt-1 certificate-validate-result d-none",
    });

    $wrapper.append(
      $("<div>", { class: "mt-2 certificate-validate" }).append(
        $button,
        $result,
      ),
    );

    const report = (cssClass, lines) => {
      $result
        .removeClass("d-none text-danger text-muted text-success text-warning")
        .addClass(cssClass)
        .empty()
        .append(
          lines.map((line) => $("<span>", { class: "d-block", text: line })),
        );
    };

    $button.on("click", () => {
      if (settingValue($priority) === "file") {
        report("text-warning", [t("validation.certificate_file_mode")]);
        return;
      }

      const cert = settingValue($cert);
      const key = settingValue($key);
      if (!cert || !key) {
        report("text-warning", [t("validation.certificate_missing")]);
        return;
      }

      // Easy mode renders one copy of the form per template, each with its own
      // SERVER_NAME, so prefer the one sharing this field's id prefix. Advanced mode
      // keeps SERVER_NAME under another plugin, where the mode pane holds exactly one.
      // Not ".tab-pane": every plugin is a tab pane of its own.
      const $pane = $key.closest('[id^="navs-modes-"]');
      const $serverName = $siblingServerName.length
        ? $siblingServerName
        : ($pane.length ? $pane : $(document))
            .find('input[name="SERVER_NAME"]')
            .first();
      const serverName = settingValue($serverName);

      $button.prop("disabled", true);
      report("text-muted", [t("validation.certificate_checking")]);

      $.ajax({
        url: endpoint,
        type: "POST",
        data: {
          csrf_token: $("#csrf_token").val(),
          cert: cert,
          key: key,
          server_name: serverName,
        },
      })
        .done((data) => {
          if (!data.ok) {
            report("text-danger", [data.error]);
            return;
          }

          const summary = [
            data.subject_cn
              ? `${t("validation.certificate_subject")} ${data.subject_cn}`
              : null,
            data.key_type,
            data.days_remaining >= 0
              ? t("validation.certificate_expires_in", {
                  days: data.days_remaining,
                })
              : null,
          ].filter(Boolean);

          const details = [
            t("validation.certificate_valid"),
            summary.join(" - "),
          ].filter(Boolean);
          report(
            data.warnings.length ? "text-warning" : "text-success",
            details.concat(data.warnings),
          );
        })
        .fail((xhr) => {
          const message = xhr.responseJSON && xhr.responseJSON.error;
          report("text-danger", [
            message || t("validation.certificate_failed"),
          ]);
        })
        .always(() => $button.prop("disabled", false));
    });
  });
}
