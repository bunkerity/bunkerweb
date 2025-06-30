// Log debug messages only when LOG_LEVEL environment variable is set to
// "debug"
function debugLog(message) {
    if (process.env.LOG_LEVEL === "debug") {
        console.debug(`[DEBUG] ${message}`);
    }
}

// Main initialization function that waits for all dependencies to load
// before initializing the Let's Encrypt certificate management interface
(async function waitForDependencies() {
    // Wait for jQuery
    while (typeof jQuery === "undefined") {
        await new Promise((resolve) => setTimeout(resolve, 100));
    }

    // Wait for $ to be available (in case of jQuery.noConflict())
    while (typeof $ === "undefined") {
        await new Promise((resolve) => setTimeout(resolve, 100));
    }

    // Wait for DataTable to be available
    while (typeof $.fn.DataTable === "undefined") {
        await new Promise((resolve) => setTimeout(resolve, 100));
    }

    $(document).ready(function () {
        const logLevel = process.env.LOG_LEVEL;
        const isDebug = logLevel === "debug";

        debugLog("Initializing Let's Encrypt certificate management");
        debugLog(`Log level: ${logLevel}`);
        debugLog(`jQuery version: ${$.fn.jquery}`);
        debugLog(`DataTables version: ${$.fn.DataTable.version}`);

        // Ensure i18next is loaded before using it
        const t =
            typeof i18next !== "undefined"
                ? i18next.t
                : (key, fallback) => fallback || key;

        var actionLock = false;
        const isReadOnly = $("#is-read-only").val()?.trim() === "True";
        const userReadOnly = $("#user-read-only").val()?.trim() === "True";

        debugLog("Application state initialized:");
        debugLog(`- Read-only mode: ${isReadOnly}`);
        debugLog(`- User read-only: ${userReadOnly}`);
        debugLog(`- Action lock: ${actionLock}`);
        debugLog(`- CSRF token available: ${!!$("#csrf_token").val()}`);

        const headers = [
            {
                title: "Domain",
                tooltip: "Domain name for the certificate",
            },
            {
                title: "Common Name",
                tooltip: "Common Name (CN) in the certificate",
            },
            {
                title: "Issuer",
                tooltip: "Certificate issuing authority",
            },
            {
                title: "Valid From",
                tooltip: "Date from which the certificate is valid",
            },
            {
                title: "Valid To",
                tooltip: "Date until which the certificate is valid",
            },
            {
                title: "Preferred Profile",
                tooltip: "Preferred profile for the certificate",
            },
            {
                title: "Challenge",
                tooltip: "Challenge type used for domain validation",
            },
            {
                title: "Key Type",
                tooltip: "Type of key used in the certificate",
            },
            {
                title: "OCSP",
                tooltip: "Online Certificate Status Protocol support",
            },
        ];

        // Configure the delete confirmation modal for certificate deletion
        // operations, supporting both single and multiple certificate
        // deletion workflows
        const setupDeleteCertModal = (certs) => {
            debugLog(`Setting up delete modal for certificates: ${
                certs.map(c => c.domain).join(", ")}`);
            debugLog(`Modal setup - certificate count: ${certs.length}`);

            const $modalBody = $("#deleteCertContent");
            $modalBody.empty();

            if (certs.length === 1) {
                debugLog(`Configuring modal for single certificate: ${
                    certs[0].domain}`);

                $modalBody.html(
                    `<p>You are about to delete the certificate for: ` +
                    `<strong>${certs[0].domain}</strong></p>`
                );
                $("#confirmDeleteCertBtn").data("cert-name", 
                                                 certs[0].domain);
            } else {
                debugLog(`Configuring modal for multiple certificates: ${
                    certs.map(c => c.domain).join(", ")}`);

                const certList = certs
                    .map((cert) => `<li>${cert.domain}</li>`)
                    .join("");
                $modalBody.html(
                    `<p>You are about to delete these certificates:</p>
                     <ul>${certList}</ul>`
                );
                $("#confirmDeleteCertBtn").data(
                    "cert-names",
                    certs.map((c) => c.domain)
                );
            }

            debugLog("Modal configuration completed");
        };

        // Display error modal with specified title and message for user
        // feedback during certificate management operations
        const showErrorModal = (title, message) => {
            debugLog(`Showing error modal: ${title} - ${message}`);

            $("#errorModalLabel").text(title);
            $("#errorModalContent").text(message);
            const errorModal = new bootstrap.Modal(
                document.getElementById("errorModal")
            );
            errorModal.show();
        };

        // Handle delete button click events for certificate deletion
        // confirmation modal
        $("#confirmDeleteCertBtn").on("click", function () {
            const certName = $(this).data("cert-name");
            const certNames = $(this).data("cert-names");

            debugLog(`Delete button clicked: certName=${certName}, ` +
                    `certNames=${certNames}`);

            if (certName) {
                deleteCertificate(certName);
            } else if (certNames && Array.isArray(certNames)) {
                // Delete multiple certificates sequentially
                const deleteNext = (index) => {
                    if (index < certNames.length) {
                        deleteCertificate(certNames[index], () => {
                            deleteNext(index + 1);
                        });
                    } else {
                        $("#deleteCertModal").modal("hide");
                        $("#letsencrypt").DataTable().ajax.reload();
                    }
                };
                deleteNext(0);
            }

            $("#deleteCertModal").modal("hide");
        });

        // Delete a single certificate via AJAX request with optional callback
        // for sequential deletion operations
        function deleteCertificate(certName, callback) {
            debugLog("Starting certificate deletion process:");
            debugLog(`- Certificate name: ${certName}`);
            debugLog(`- Has callback: ${!!callback}`);
            debugLog(`- Request URL: ${
                window.location.pathname}/delete`);

            const requestData = { cert_name: certName };
            const csrfToken = $("#csrf_token").val();

            debugLog(`Request payload: ${JSON.stringify(requestData)}`);
            debugLog(`CSRF token: ${csrfToken ? "present" : "missing"}`);

            $.ajax({
                url: `${window.location.pathname}/delete`,
                type: "POST",
                contentType: "application/json",
                data: JSON.stringify(requestData),
                headers: {
                    "X-CSRFToken": csrfToken,
                },
                beforeSend: function(xhr) {
                    debugLog(`AJAX request starting for: ${certName}`);
                    debugLog(`Request headers: ${
                        xhr.getAllResponseHeaders()}`);
                },
                success: function (response) {
                    debugLog("Delete response received:");
                    debugLog(`- Status: ${response.status}`);
                    debugLog(`- Message: ${response.message}`);
                    debugLog(`- Full response: ${
                        JSON.stringify(response)}`);

                    if (response.status === "ok") {
                        debugLog(`Certificate deletion successful: ${
                            certName}`);

                        if (callback) {
                            debugLog("Executing callback function");
                            callback();
                        } else {
                            debugLog("Reloading DataTable data");
                            $("#letsencrypt").DataTable().ajax.reload();
                        }
                    } else {
                        debugLog(`Certificate deletion failed: ${
                            response.message}`);

                        showErrorModal(
                            "Certificate Deletion Error",
                            `Error deleting certificate ${certName}: ${
                                response.message || "Unknown error"}`
                        );
                        if (callback) callback();
                        else $("#letsencrypt").DataTable().ajax.reload();
                    }
                },
                error: function (xhr, status, error) {
                    debugLog("AJAX error details:");
                    debugLog(`- XHR status: ${xhr.status}`);
                    debugLog(`- Status text: ${status}`);
                    debugLog(`- Error: ${error}`);
                    debugLog(`- Response text: ${xhr.responseText}`);
                    debugLog(`- Response JSON: ${
                        JSON.stringify(xhr.responseJSON)}`);

                    console.error("Error deleting certificate:", error, xhr);

                    let errorMessage = `Failed to delete certificate ` +
                                     `${certName}: `;

                    if (xhr.responseJSON && xhr.responseJSON.message) {
                        errorMessage += xhr.responseJSON.message;
                    } else if (xhr.responseText) {
                        try {
                            const parsedError = JSON.parse(xhr.responseText);
                            errorMessage += 
                                parsedError.message || error;
                        } catch (e) {
                            debugLog(`Failed to parse error response: ${e}`);
                            if (xhr.responseText.length < 200) {
                                errorMessage += xhr.responseText;
                            } else {
                                errorMessage += error || "Unknown error";
                            }
                        }
                    } else {
                        errorMessage += error || "Unknown error";
                    }

                    showErrorModal("Certificate Deletion Failed",
                                   errorMessage);

                    if (callback) callback();
                    else $("#letsencrypt").DataTable().ajax.reload();
                },
                complete: function(xhr, status) {
                    debugLog("AJAX request completed:");
                    debugLog(`- Final status: ${status}`);
                    debugLog(`- Certificate: ${certName}`);
                }
            });
        }

        // DataTable Layout and Button configuration
        const layout = {
            top1: {
                searchPanes: {
                    viewTotal: true,
                    cascadePanes: true,
                    collapse: false,
                    // Issuer, Preferred Profile, Challenge, Key Type, and OCSP
                    columns: [2, 5, 6, 7, 8],
                },
            },
            topStart: {},
            topEnd: {
                search: true,
                buttons: [
                    {
                        extend: "auto_refresh",
                        className: (
                            "btn btn-sm btn-outline-primary " +
                            "d-flex align-items-center"
                        ),
                    },
                    {
                        extend: "toggle_filters",
                        className: "btn btn-sm btn-outline-primary " +
                                  "toggle-filters",
                    },
                ],
            },
            bottomStart: {
                pageLength: {
                    menu: [10, 25, 50, 100, 
                           { label: "All", value: -1 }],
                },
                info: true,
            },
        };

        debugLog("DataTable layout configuration:");
        debugLog(`- Search panes columns: ${
            layout.top1.searchPanes.columns.join(", ")}`);
        debugLog(`- Page length options: ${
            JSON.stringify(layout.bottomStart.pageLength.menu)}`);
        debugLog(`- Layout structure: ${JSON.stringify(layout)}`);
        debugLog(`- Headers count: ${headers.length}`);

        layout.topStart.buttons = [
            {
                extend: "colvis",
                columns: "th:not(:nth-child(-n+3)):not(:last-child)",
                text: (
                    `<span class="tf-icons bx bx-columns bx-18px ` +
                    `me-md-2"></span><span class="d-none d-md-inline" ` +
                    `data-i18n="button.columns">${t(
                        "button.columns",
                        "Columns"
                    )}</span>`
                ),
                className: "btn btn-sm btn-outline-primary rounded-start",
                columnText: function (dt, idx, title) {
                    return `${idx + 1}. ${title}`;
                },
            },
            {
                extend: "colvisRestore",
                text: (
                    `<span class="tf-icons bx bx-reset bx-18px ` +
                    `me-2"></span><span class="d-none d-md-inline" ` +
                    `data-i18n="button.reset_columns">${t(
                        "button.reset_columns",
                        "Reset columns"
                    )}</span>`
                ),
                className: "btn btn-sm btn-outline-primary d-none d-md-inline",
            },
            {
                extend: "collection",
                text: (
                    `<span class="tf-icons bx bx-export bx-18px ` +
                    `me-md-2"></span><span class="d-none d-md-inline" ` +
                    `data-i18n="button.export">${t(
                        "button.export",
                        "Export"
                    )}</span>`
                ),
                className: "btn btn-sm btn-outline-primary",
                buttons: [
                    {
                        extend: "copy",
                        text: (
                            `<span class="tf-icons bx bx-copy bx-18px ` +
                            `me-2"></span><span ` +
                            `data-i18n="button.copy_visible">${t(
                                "button.copy_visible",
                                "Copy visible"
                            )}</span>`
                        ),
                        exportOptions: {
                            columns: (
                                ":visible:not(:nth-child(-n+2)):" +
                                "not(:last-child)"
                            ),
                        },
                    },
                    {
                        extend: "csv",
                        text: (
                            `<span class="tf-icons bx bx-table bx-18px ` +
                            `me-2"></span>CSV`
                        ),
                        bom: true,
                        filename: "bw_certificates",
                        exportOptions: {
                            modifier: { search: "none" },
                            columns: (
                                ":not(:nth-child(-n+2)):not(:last-child)"
                            ),
                        },
                    },
                    {
                        extend: "excel",
                        text: (
                            `<span class="tf-icons bx bx-table bx-18px ` +
                            `me-2"></span>Excel`
                        ),
                        filename: "bw_certificates",
                        exportOptions: {
                            modifier: { search: "none" },
                            columns: (
                                ":not(:nth-child(-n+2)):not(:last-child)"
                            ),
                        },
                    },
                ],
            },
            {
                extend: "collection",
                text: (
                    `<span class="tf-icons bx bx-play bx-18px ` +
                    `me-md-2"></span><span class="d-none d-md-inline" ` +
                    `data-i18n="button.actions">${t(
                        "button.actions",
                        "Actions"
                    )}</span>`
                ),
                className: (
                    "btn btn-sm btn-outline-primary action-button disabled"
                ),
                buttons: [
                    { extend: "delete_cert", className: "text-danger" }
                ],
            },
        ];

        let autoRefresh = false;
        let autoRefreshInterval = null;
        const sessionAutoRefresh = 
            sessionStorage.getItem("letsencryptAutoRefresh");

        // Toggle auto-refresh functionality for DataTable data with
        // visual feedback and interval management
        function toggleAutoRefresh() {
            autoRefresh = !autoRefresh;
            sessionStorage.setItem("letsencryptAutoRefresh", autoRefresh);

            debugLog(`Auto-refresh toggled: ${autoRefresh}`);

            if (autoRefresh) {
                $(".bx-loader")
                    .addClass("bx-spin")
                    .closest(".btn")
                    .removeClass("btn-outline-primary")
                    .addClass("btn-primary");
                
                if (autoRefreshInterval) clearInterval(autoRefreshInterval);
                
                autoRefreshInterval = setInterval(() => {
                    if (!autoRefresh) {
                        clearInterval(autoRefreshInterval);
                        autoRefreshInterval = null;
                    } else {
                        $("#letsencrypt").DataTable().ajax.reload(null, 
                                                                  false);
                    }
                }, 10000);
            } else {
                $(".bx-loader")
                    .removeClass("bx-spin")
                    .closest(".btn")
                    .removeClass("btn-primary")
                    .addClass("btn-outline-primary");
                
                if (autoRefreshInterval) {
                    clearInterval(autoRefreshInterval);
                    autoRefreshInterval = null;
                }
            }
        }

        if (sessionAutoRefresh === "true") {
            toggleAutoRefresh();
        }

        // Extract currently selected certificates from DataTable rows
        // and return their domain information for bulk operations
        const getSelectedCertificates = () => {
            const certs = [];
            $("tr.selected").each(function () {
                const $row = $(this);
                const domain = $row.find("td:eq(2)").text().trim();
                certs.push({ domain: domain });
            });

            debugLog(`Selected certificates: ${
                certs.map(c => c.domain).join(", ")}`);

            return certs;
        };

        // Custom DataTable button for auto-refresh functionality
        $.fn.dataTable.ext.buttons.auto_refresh = {
            text: (
                '<span class="bx bx-loader bx-18px lh-1"></span>' +
                '&nbsp;&nbsp;<span data-i18n="button.auto_refresh">' +
                'Auto refresh</span>'
            ),
            action: (e, dt, node, config) => {
                toggleAutoRefresh();
            },
        };

        // Custom DataTable button for certificate deletion with
        // read-only mode checks and selection validation
        $.fn.dataTable.ext.buttons.delete_cert = {
            text: (
                `<span class="tf-icons bx bx-trash bx-18px me-2"></span>` +
                `Delete certificate`
            ),
            action: function (e, dt, node, config) {
                if (isReadOnly) {
                    alert(
                        t(
                            "alert.readonly_mode",
                            "This action is not allowed in read-only mode."
                        )
                    );
                    return;
                }
                
                if (actionLock) return;
                actionLock = true;
                $(".dt-button-background").click();

                const certs = getSelectedCertificates();
                if (certs.length === 0) {
                    actionLock = false;
                    return;
                }
                
                setupDeleteCertModal(certs);

                const deleteModal = new bootstrap.Modal(
                    document.getElementById("deleteCertModal")
                );
                deleteModal.show();

                actionLock = false;
            },
        };

        // Build column definitions for DataTable configuration with
        // responsive controls, selection, and search pane settings
        function buildColumnDefs() {
            return [
                { 
                    orderable: false, 
                    className: "dtr-control", 
                    targets: 0 
                },
                { 
                    orderable: false, 
                    render: DataTable.render.select(), 
                    targets: 1 
                },
                { type: "string", targets: 2 },
                { orderable: true, targets: -1 },
                {
                    targets: [5, 6],
                    render: function (data, type, row) {
                        if (type === "display" || type === "filter") {
                            const date = new Date(data);
                            if (!isNaN(date.getTime())) {
                                return date.toLocaleString();
                            }
                        }
                        return data;
                    },
                },
                {
                    searchPanes: {
                        show: true,
                        combiner: "or",
                        header: t("searchpane.issuer", "Issuer"),
                    },
                    targets: 2,
                },
                {
                    searchPanes: {
                        show: true,
                        header: t("searchpane.preferred_profile", 
                                  "Preferred Profile"),
                        combiner: "or",
                    },
                    targets: 5,
                },
                {
                    searchPanes: {
                        show: true,
                        header: t("searchpane.challenge", "Challenge"),
                        combiner: "or",
                    },
                    targets: 6,
                },
                {
                    searchPanes: {
                        show: true,
                        header: t("searchpane.key_type", "Key Type"),
                        combiner: "or",
                    },
                    targets: 7,
                },
                {
                    searchPanes: {
                        show: true,
                        header: t("searchpane.ocsp", "OCSP Support"),
                        combiner: "or",
                    },
                    targets: 8,
                },
            ];
        }

        // Define the columns for the DataTable with data mappings
        // and display configurations for certificate information
        function buildColumns() {
            return [
                {
                    data: null,
                    defaultContent: "",
                    orderable: false,
                    className: "dtr-control",
                },
                { data: null, defaultContent: "", orderable: false },
                { data: "domain", title: "Domain" },
                { data: "common_name", title: "Common Name" },
                { data: "issuer", title: "Issuer" },
                { data: "valid_from", title: "Valid From" },
                { data: "valid_to", title: "Valid To" },
                { data: "preferred_profile", title: "Preferred Profile" },
                { data: "challenge", title: "Challenge" },
                { data: "key_type", title: "Key Type" },
                { data: "ocsp_support", title: "OCSP" },
                { data: "serial_number", title: "Serial Number" },
                { data: "fingerprint", title: "Fingerprint" },
                { data: "version", title: "Version" },
            ];
        }

        // Manage header tooltips for DataTable columns by applying
        // Bootstrap tooltip attributes to table headers
        function updateHeaderTooltips(selector, headers) {
            $(selector)
                .find("th")
                .each((index, element) => {
                    const $th = $(element);
                    const tooltip = headers[index] ? 
                                   headers[index].tooltip : "";
                    if (!tooltip) return;

                    $th.attr({
                        "data-bs-toggle": "tooltip",
                        "data-bs-placement": "bottom",
                        title: tooltip,
                    });
                });

            $('[data-bs-toggle="tooltip"]').tooltip("dispose").tooltip();
        }

        // Initialize the DataTable with complete configuration including
        // server-side processing, AJAX data loading, and UI components
        const letsencrypt_config = {
            tableSelector: "#letsencrypt",
            tableName: "letsencrypt",
            columnVisibilityCondition: (column) => column > 2 && column < 14,
            dataTableOptions: {
                columnDefs: buildColumnDefs(),
                order: [[2, "asc"]],
                autoFill: false,
                responsive: true,
                select: {
                    style: "multi+shift",
                    selector: "td:nth-child(2)",
                    headerCheckbox: true,
                },
                layout: layout,
                processing: true,
                serverSide: true,
                ajax: {
                    url: `${window.location.pathname}/fetch`,
                    type: "POST",
                    data: function (d) {
                        debugLog(`DataTable AJAX request data: ${
                            JSON.stringify(d)}`);
                        debugLog("Request parameters:");
                        debugLog(`- Draw: ${d.draw}`);
                        debugLog(`- Start: ${d.start}`);
                        debugLog(`- Length: ${d.length}`);
                        debugLog(`- Search value: ${d.search?.value}`);

                        d.csrf_token = $("#csrf_token").val();
                        return d;
                    },
                    error: function (jqXHR, textStatus, errorThrown) {
                        debugLog("DataTable AJAX error details:");
                        debugLog(`- Status: ${jqXHR.status}`);
                        debugLog(`- Status text: ${textStatus}`);
                        debugLog(`- Error: ${errorThrown}`);
                        debugLog(`- Response text: ${jqXHR.responseText}`);
                        debugLog(`- Response headers: ${
                            jqXHR.getAllResponseHeaders()}`);

                        console.error("DataTables AJAX error:", 
                                      textStatus, errorThrown);
                        
                        $("#letsencrypt").addClass("d-none");
                        $("#letsencrypt-waiting")
                            .removeClass("d-none")
                            .text("Error loading certificates. " +
                                  "Please try refreshing the page.")
                            .addClass("text-danger");
                        
                        $(".dataTables_processing").hide();
                    },
                    success: function(data, textStatus, jqXHR) {
                        debugLog("DataTable AJAX success:");
                        debugLog(`- Records total: ${data.recordsTotal}`);
                        debugLog(`- Records filtered: ${
                            data.recordsFiltered}`);
                        debugLog(`- Data length: ${data.data?.length}`);
                        debugLog(`- Draw number: ${data.draw}`);
                    }
                },
                columns: buildColumns(),
                initComplete: function (settings, json) {
                    debugLog(`DataTable initialized with settings: ${
                        JSON.stringify(settings)}`);

                    $("#letsencrypt_wrapper .btn-secondary")
                        .removeClass("btn-secondary");

                    $("#letsencrypt-waiting").addClass("d-none");
                    $("#letsencrypt").removeClass("d-none");

                    if (isReadOnly) {
                        const titleKey = userReadOnly
                            ? "tooltip.readonly_user_action_disabled"
                            : "tooltip.readonly_db_action_disabled";
                        const defaultTitle = userReadOnly
                            ? "Your account is readonly, action disabled."
                            : "The database is in readonly, action disabled.";
                    }
                },
                headerCallback: function (thead) {
                    updateHeaderTooltips(thead, headers);
                },
            },
        };

        const dt = initializeDataTable(letsencrypt_config);
        
        dt.on("draw.dt", function () {
            updateHeaderTooltips(dt.table().header(), headers);
            $(".tooltip").remove();
        });
        
        dt.on("column-visibility.dt", function (e, settings, column, state) {
            updateHeaderTooltips(dt.table().header(), headers);
            $(".tooltip").remove();
        });

        // Toggle action button based on row selection state
        dt.on("select.dt deselect.dt", function () {
            const count = dt.rows({ selected: true }).count();
            $(".action-button").toggleClass("disabled", count === 0);
            
            debugLog(`Selection changed, count: ${count}`);
        });
    });
})();