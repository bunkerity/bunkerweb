$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key; // Fallback

  var actionLock = false;
  let addBanNumber = 1;
  const banNumber = parseInt($("#bans_number").val());
  const dataCountries = ($("#countries").val() || "")
    .split(",")
    .filter((code) => code && code !== "local");
  const baseFlagsUrl = $("#base_flags_url").val().trim();
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const userReadOnly = $("#user-read-only").val().trim() === "True";

  const countriesDataNames = {
    AD: "Andorra",
    AE: "United Arab Emirates",
    AF: "Afghanistan",
    AG: "Antigua and Barbuda",
    AI: "Anguilla",
    AL: "Albania",
    AM: "Armenia",
    AO: "Angola",
    AQ: "Antarctica",
    AR: "Argentina",
    AS: "American Samoa",
    AT: "Austria",
    AU: "Australia",
    AW: "Aruba",
    AX: "Åland Islands",
    AZ: "Azerbaijan",
    BA: "Bosnia and Herzegovina",
    BB: "Barbados",
    BD: "Bangladesh",
    BE: "Belgium",
    BF: "Burkina Faso",
    BG: "Bulgaria",
    BH: "Bahrain",
    BI: "Burundi",
    BJ: "Benin",
    BL: "Saint Barthélemy",
    BM: "Bermuda",
    BN: "Brunei Darussalam",
    BO: "Bolivia, Plurinational State of",
    BQ: "Caribbean Netherlands",
    BR: "Brazil",
    BS: "Bahamas",
    BT: "Bhutan",
    BV: "Bouvet Island",
    BW: "Botswana",
    BY: "Belarus",
    BZ: "Belize",
    CA: "Canada",
    CC: "Cocos (Keeling) Islands",
    CD: "Congo, the Democratic Republic of the",
    CF: "Central African Republic",
    CG: "Republic of the Congo",
    CH: "Switzerland",
    CI: "Côte d'Ivoire",
    CK: "Cook Islands",
    CL: "Chile",
    CM: "Cameroon",
    CN: "China (People's Republic of China)",
    CO: "Colombia",
    CR: "Costa Rica",
    CU: "Cuba",
    CV: "Cape Verde",
    CW: "Curaçao",
    CX: "Christmas Island",
    CY: "Cyprus",
    CZ: "Czech Republic",
    DE: "Germany",
    DJ: "Djibouti",
    DK: "Denmark",
    DM: "Dominica",
    DO: "Dominican Republic",
    DZ: "Algeria",
    EC: "Ecuador",
    EE: "Estonia",
    EG: "Egypt",
    EH: "Western Sahara",
    ER: "Eritrea",
    ES: "Spain",
    ET: "Ethiopia",
    EU: "Europe",
    FI: "Finland",
    FJ: "Fiji",
    FK: "Falkland Islands (Malvinas)",
    FM: "Micronesia, Federated States of",
    FO: "Faroe Islands",
    FR: "France",
    GA: "Gabon",
    GB: "United Kingdom",
    GD: "Grenada",
    GE: "Georgia",
    GF: "French Guiana",
    GG: "Guernsey",
    GH: "Ghana",
    GI: "Gibraltar",
    GL: "Greenland",
    GM: "Gambia",
    GN: "Guinea",
    GP: "Guadeloupe",
    GQ: "Equatorial Guinea",
    GR: "Greece",
    GS: "South Georgia and the South Sandwich Islands",
    GT: "Guatemala",
    GU: "Guam",
    GW: "Guinea-Bissau",
    GY: "Guyana",
    HK: "Hong Kong",
    HM: "Heard Island and McDonald Islands",
    HN: "Honduras",
    HR: "Croatia",
    HT: "Haiti",
    HU: "Hungary",
    ID: "Indonesia",
    IE: "Ireland",
    IL: "Israel",
    IM: "Isle of Man",
    IN: "India",
    IO: "British Indian Ocean Territory",
    IQ: "Iraq",
    IR: "Iran, Islamic Republic of",
    IS: "Iceland",
    IT: "Italy",
    JE: "Jersey",
    JM: "Jamaica",
    JO: "Jordan",
    JP: "Japan",
    KE: "Kenya",
    KG: "Kyrgyzstan",
    KH: "Cambodia",
    KI: "Kiribati",
    KM: "Comoros",
    KN: "Saint Kitts and Nevis",
    KP: "Korea, Democratic People's Republic of",
    KR: "Korea, Republic of",
    KW: "Kuwait",
    KY: "Cayman Islands",
    KZ: "Kazakhstan",
    LA: "Laos (Lao People's Democratic Republic)",
    LB: "Lebanon",
    LC: "Saint Lucia",
    LI: "Liechtenstein",
    LK: "Sri Lanka",
    LR: "Liberia",
    LS: "Lesotho",
    LT: "Lithuania",
    LU: "Luxembourg",
    LV: "Latvia",
    LY: "Libya",
    MA: "Morocco",
    MC: "Monaco",
    MD: "Moldova, Republic of",
    ME: "Montenegro",
    MF: "Saint Martin",
    MG: "Madagascar",
    MH: "Marshall Islands",
    MK: "North Macedonia",
    ML: "Mali",
    MM: "Myanmar",
    MN: "Mongolia",
    MO: "Macao",
    MP: "Northern Mariana Islands",
    MQ: "Martinique",
    MR: "Mauritania",
    MS: "Montserrat",
    MT: "Malta",
    MU: "Mauritius",
    MV: "Maldives",
    MW: "Malawi",
    MX: "Mexico",
    MY: "Malaysia",
    MZ: "Mozambique",
    NA: "Namibia",
    NC: "New Caledonia",
    NE: "Niger",
    NF: "Norfolk Island",
    NG: "Nigeria",
    NI: "Nicaragua",
    NL: "Netherlands",
    NO: "Norway",
    NP: "Nepal",
    NR: "Nauru",
    NU: "Niue",
    NZ: "New Zealand",
    OM: "Oman",
    PA: "Panama",
    PE: "Peru",
    PF: "French Polynesia",
    PG: "Papua New Guinea",
    PH: "Philippines",
    PK: "Pakistan",
    PL: "Poland",
    PM: "Saint Pierre and Miquelon",
    PN: "Pitcairn",
    PR: "Puerto Rico",
    PS: "Palestine",
    PT: "Portugal",
    PW: "Palau",
    PY: "Paraguay",
    QA: "Qatar",
    RE: "Réunion",
    RO: "Romania",
    RS: "Serbia",
    RU: "Russian Federation",
    RW: "Rwanda",
    SA: "Saudi Arabia",
    SB: "Solomon Islands",
    SC: "Seychelles",
    SD: "Sudan",
    SE: "Sweden",
    SG: "Singapore",
    SH: "Saint Helena, Ascension and Tristan da Cunha",
    SI: "Slovenia",
    SJ: "Svalbard and Jan Mayen Islands",
    SK: "Slovakia",
    SL: "Sierra Leone",
    SM: "San Marino",
    SN: "Senegal",
    SO: "Somalia",
    SR: "Suriname",
    SS: "South Sudan",
    ST: "Sao Tome and Principe",
    SV: "El Salvador",
    SX: "Sint Maarten (Dutch part)",
    SY: "Syrian Arab Republic",
    SZ: "Swaziland",
    TC: "Turks and Caicos Islands",
    TD: "Chad",
    TF: "French Southern Territories",
    TG: "Togo",
    TH: "Thailand",
    TJ: "Tajikistan",
    TK: "Tokelau",
    TL: "Timor-Leste",
    TM: "Turkmenistan",
    TN: "Tunisia",
    TO: "Tonga",
    TR: "Turkey",
    TT: "Trinidad and Tobago",
    TV: "Tuvalu",
    TW: "Taiwan (Republic of China)",
    TZ: "Tanzania, United Republic of",
    UA: "Ukraine",
    UG: "Uganda",
    UM: "US Minor Outlying Islands",
    US: "United States",
    UY: "Uruguay",
    UZ: "Uzbekistan",
    VA: "Holy See (Vatican City State)",
    VC: "Saint Vincent and the Grenadines",
    VE: "Venezuela, Bolivarian Republic of",
    VG: "Virgin Islands, British",
    VI: "Virgin Islands, U.S.",
    VN: "Vietnam",
    VU: "Vanuatu",
    WF: "Wallis and Futuna Islands",
    WS: "Samoa",
    XK: "Kosovo",
    YE: "Yemen",
    YT: "Mayotte",
    ZA: "South Africa",
    ZM: "Zambia",
    ZW: "Zimbabwe",
  };

  // Filter countriesDataNames to include only necessary countries
  const filteredCountriesDataNames = dataCountries.reduce((obj, code) => {
    if (countriesDataNames[code]) {
      obj[code] = countriesDataNames[code];
    }
    return obj;
  }, {});

  const countriesSearchPanesOptions = [
    {
      label: `<img src="${baseFlagsUrl}/zz.svg" class="border border-1 p-0 me-1" height="17" loading="lazy" />&nbsp;－&nbsp;<span data-i18n="country.not_applicable">${t(
        "country.not_applicable",
        "N/A",
      )}</span>`,
      value: (rowData) => rowData[4].includes('data-country="unknown"'),
    },
    ...Object.entries(filteredCountriesDataNames).map(
      ([code, fallbackName]) => ({
        label: `<img src="${baseFlagsUrl}/${code.toLowerCase()}.svg" class="border border-1 p-0 me-1" height="17" loading="lazy" />&nbsp;－&nbsp;<span data-i18n="country.${code}">${code}</span>`,
        value: (rowData) => rowData[4].includes(`data-country="${code}"`),
      }),
    ),
  ];

  // Batch update tooltips
  const updateCountryTooltips = () => {
    $("[data-country]").each(function () {
      const $elem = $(this);
      const countryCode = $elem.data("country");

      const countryName = t(
        countryCode === "unknown"
          ? "country.not_applicable"
          : `country.${countryCode}`,
        countriesDataNames[countryCode],
      );
      if (countryName && countryName !== "country.not_applicable") {
        $elem.attr("data-bs-original-title", countryName);
      }
    });
    $('[data-bs-toggle="tooltip"]').tooltip("dispose").tooltip();
  };

  // Utility functions
  function addDays(date, days) {
    const result = new Date(date);
    result.setDate(result.getDate() + days);
    return result;
  }

  function addHours(date, hours) {
    const result = new Date(date);
    result.setHours(result.getHours() + hours);
    return result;
  }

  function formatDate(date) {
    const year = date.getFullYear();
    let month = date.getMonth() + 1; // Months are zero-based in JavaScript
    let day = date.getDate();

    // Pad month and day with leading zeros if needed
    month = month < 10 ? "0" + month : month;
    day = day < 10 ? "0" + day : day;

    return `${year}-${month}-${day}`;
  }

  function formatTime(date) {
    let hours = date.getHours();
    let minutes = date.getMinutes();

    // Pad hours and minutes with leading zeros if needed
    hours = hours < 10 ? "0" + hours : hours;
    minutes = minutes < 10 ? "0" + minutes : minutes;

    return `${hours}:${minutes}`;
  }

  // Select the Flatpickr input elements
  const flatpickrDatetime = $("[type='flatpickr-datetime']");

  // Get the current date and times
  const currentDatetime = new Date();
  const minDatetime = addHours(currentDatetime, 1);
  const defaultDatetime = addDays(currentDatetime, 1);

  // Format dates and times
  const minDateStr = formatDate(minDatetime);
  const minTimeStr = formatTime(minDatetime);

  // Create the minMaxTime table
  const minMaxTable = {
    [minDateStr]: {
      minTime: minTimeStr,
    },
  };

  const getTimeZoneOffset = () => {
    const offset = -currentDatetime.getTimezoneOffset(); // getTimezoneOffset returns minutes behind UTC
    const sign = offset >= 0 ? "+" : "-";
    const absOffset = Math.abs(offset);
    const hours = String(Math.floor(absOffset / 60)).padStart(2, "0");
    const minutes = String(absOffset % 60).padStart(2, "0");
    return `${sign}${hours}:${minutes}`;
  };

  // Initialize Flatpickr with altInput and altFormat
  const originalFlatpickr = flatpickrDatetime.flatpickr({
    enableTime: true,
    dateFormat: "Y-m-d\\TH:i:S", // ISO format
    altInput: true,
    altFormat: "F j, Y h:i K", // User-friendly display format
    time_24hr: true,
    defaultDate: defaultDatetime,
    minDate: minDatetime,
    plugins: [
      new minMaxTimePlugin({
        table: minMaxTable,
      }),
    ],
  });

  // Function to set up the unban modal
  const setupUnbanModal = (bans) => {
    const $modalBody = $("#selected-ips-unban");
    $modalBody.empty(); // Clear previous content

    // Create and append the header row
    const $header = $(`
      <ul class="list-group list-group-horizontal w-100">
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold" data-i18n="table.header.ip_address">${t(
              "table.header.ip_address",
            )}</div>
          </div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="fw-bold" data-i18n="table.header.scope">${t(
            "table.header.scope",
          )}</div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="fw-bold" data-i18n="table.header.time_left">${t(
            "table.header.time_left",
          )}</div>
        </li>
      </ul>
    `);
    $modalBody.append($header);

    // Iterate over bans and append list items
    bans.forEach((ban) => {
      const scopeText =
        ban.ban_scope === "global"
          ? t("scope.global", "Global")
          : t("scope.service_specific", "Service-specific");
      const serviceText =
        ban.service && ban.ban_scope === "service" ? ` (${ban.service})` : "";

      const $row = $(`
        <ul class="list-group list-group-horizontal w-100">
          <li class="list-group-item" style="flex: 1 0;">
            <div class="ms-2 me-auto">
              <div class="fw-bold">${ban.ip}</div>
            </div>
          </li>
          <li class="list-group-item" style="flex: 1 0;">
            <div class="ms-2 me-auto">
              ${scopeText}${serviceText}
            </div>
          </li>
          <li class="list-group-item" style="flex: 1 0;">
            <div class="ms-2 me-auto">
              ${ban.time_remaining}
            </div>
          </li>
        </ul>
      `);
      $modalBody.append($row);
    });

    // Show the modal
    const $unbanModal = $("#modal-unban-ips");
    const modalInstance = new bootstrap.Modal($unbanModal[0]);

    // Update the alert text using i18next (assuming keys exist)
    const alertTextKey =
      bans.length > 1
        ? "modal.body.unban_confirmation_alert_plural"
        : "modal.body.unban_confirmation_alert";
    $unbanModal
      .find(".alert")
      .text(
        t(
          alertTextKey,
          "Are you sure you want to unban the selected IP address(es)?",
        ),
      );

    modalInstance.show();

    // Set the hidden input value
    $("#selected-ips-input-unban").val(JSON.stringify(bans));
  };

  // DataTable Layout and Buttons
  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [2, 4, 7, 8],
      },
    },
    topStart: {},
    topEnd: {
      search: true,
      buttons: [
        {
          extend: "toggle_filters",
          className: "btn btn-sm btn-outline-primary toggle-filters",
        },
      ],
    },
    bottomStart: {
      info: true,
    },
    bottomEnd: {},
  };

  if (banNumber > 10) {
    const menu = [10];
    if (banNumber > 25) menu.push(25);
    if (banNumber > 50) menu.push(50);
    if (banNumber > 100) menu.push(100);
    menu.push({ label: t("datatable.length_all", "All"), value: -1 }); // Translate "All"
    layout.bottomStart = {
      pageLength: { menu: menu },
      info: true,
    };
    layout.bottomEnd.paging = true;
  }

  layout.topStart.buttons = [
    { extend: "add_ban" },
    {
      extend: "colvis",
      columns: "th:not(:nth-child(-n+3)):not(:last-child)",
      text: `<span class="tf-icons bx bx-columns bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.columns">${t(
        "button.columns",
        "Columns",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary rounded-start",
      columnText: function (dt, idx, title) {
        const headerCell = dt.column(idx).header(); // Get header cell DOM element
        const $header = $(headerCell);
        // Find the element with data-i18n (likely a span inside the th)
        const $translatableElement = $header.find("[data-i18n]");
        let i18nKey = $translatableElement.data("i18n");
        let translatedTitle = title; // Use original title as fallback

        if (i18nKey) {
          translatedTitle = t(i18nKey, title); // Pass original title as defaultValue
        } else {
          translatedTitle = $header.text().trim() || title; // Use text content or DT title
          console.warn(
            `ColVis: No data-i18n key found for column index ${idx}, using header text or title: '${translatedTitle}'`,
          );
        }
        return `${idx + 1}. <span data-i18n="${
          i18nKey || ""
        }">${translatedTitle}</span>`;
      },
    },
    {
      extend: "colvisRestore",
      text: `<span class="tf-icons bx bx-reset bx-18px me-2"></span><span class="d-none d-md-inline" data-i18n="button.reset_columns">${t(
        "button.reset_columns",
        "Reset columns",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary d-none d-md-inline",
    },
    {
      extend: "collection",
      text: `<span class="tf-icons bx bx-export bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.export">${t(
        "button.export",
        "Export",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary",
      buttons: [
        {
          extend: "copy",
          text: `<span class="tf-icons bx bx-copy bx-18px me-2"></span><span data-i18n="button.copy_visible">${t(
            "button.copy_visible",
            "Copy visible",
          )}</span>`,
          exportOptions: {
            columns: ":visible:not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "csv",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV`,
          bom: true,
          filename: "bw_bans",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
          filename: "bw_bans",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
      ],
    },
    {
      extend: "collection",
      text: `<span class="tf-icons bx bx-play bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.actions">${t(
        "button.actions",
        "Actions",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary action-button disabled",
      buttons: [{ extend: "unban_ips", className: "text-danger" }],
    },
  ];

  $("#modal-unban-ips").on("hidden.bs.modal", function () {
    $("#selected-ips-unban").empty();
    $("#selected-ips-input-unban").val("");
  });

  const getSelectedBans = () => {
    const bans = [];
    $("tr.selected").each(function () {
      const $row = $(this);
      const ip = $row.find("td:eq(3)").text().trim();
      const time_remaining = $row.find("td:eq(9)").text().trim();
      const scopeHtml = $row.find("td:eq(6)").html();
      const serviceHtml = $row.find("td:eq(7)").html();

      // Extract scope text, handling potential badge structure
      const scopeText = $(scopeHtml).find("span[data-i18n]").length
        ? $(scopeHtml).find("span[data-i18n]").text().trim()
        : $(scopeHtml).text().trim();

      // Extract service text, handling potential links or static text
      const serviceText = $(serviceHtml).find("strong").length
        ? $(serviceHtml).find("strong").text().trim()
        : $(serviceHtml).find("span[data-i18n]").length
          ? $(serviceHtml).find("span[data-i18n]").text().trim()
          : $(serviceHtml).text().trim();

      const ban_scope =
        scopeText === t("scope.global", "Global") ? "global" : "service";
      const service =
        serviceText === t("scope.all_services", "All services")
          ? null
          : serviceText;

      bans.push({
        ip: ip,
        time_remaining: time_remaining,
        ban_scope: ban_scope,
        service: service,
      });
    });
    return bans;
  };

  // Custom Button Definitions
  $.fn.dataTable.ext.buttons.add_ban = {
    text: `<span class="tf-icons bx bx-plus"></span><span class="d-none d-md-inline" data-i18n="button.add_ban_plural"> ${t(
      "button.add_ban_plural",
      "Add ban(s)",
    )}</span>`,
    className: `btn btn-sm rounded me-4 btn-bw-green${
      isReadOnly ? " disabled" : ""
    }`,
    action: function (e, dt, node, config) {
      if (isReadOnly) {
        alert(
          t(
            "alert.readonly_mode",
            "This action is not allowed in read-only mode.",
          ),
        );
        return;
      }
      const ban_modal = $("#modal-ban-ips");
      const modal = new bootstrap.Modal(ban_modal);
      modal.show();
    },
  };

  $.fn.dataTable.ext.buttons.unban_ips = {
    text: `<span class="tf-icons bx bxs-buoy bx-18px me-2"></span><span data-i18n="button.unban">${t(
      "button.unban",
      "Unban",
    )}</span>`,
    action: function (e, dt, node, config) {
      if (isReadOnly) {
        alert(
          t(
            "alert.readonly_mode",
            "This action is not allowed in read-only mode.",
          ),
        );
        return;
      }
      if (actionLock) return;
      actionLock = true;
      $(".dt-button-background").click();

      const bans = getSelectedBans();
      if (bans.length === 0) {
        actionLock = false;
        return;
      }
      setupUnbanModal(bans);
      actionLock = false;
    },
  };

  const bans_config = {
    tableSelector: "#bans",
    tableName: "bans",
    columnVisibilityCondition: (column) => column > 2 && column < 11,
    dataTableOptions: {
      columnDefs: [
        { orderable: false, className: "dtr-control", targets: 0 },
        { orderable: false, render: DataTable.render.select(), targets: 1 },
        { type: "ip-address", targets: 3 },
        { orderable: false, targets: -1 },
        {
          targets: [2, 8],
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
            options: countriesSearchPanesOptions,
            header: t("searchpane.country", "Country"),
          },
          targets: 4,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.start_date", "Start Date"),
            options: [
              {
                label: `<span data-i18n="searchpane.last_24h">${t(
                  "searchpane.last_24h",
                  "Last 24 hours",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[2]) < 86400000,
              },
              {
                label: `<span data-i18n="searchpane.last_7d">${t(
                  "searchpane.last_7d",
                  "Last 7 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[2]) < 604800000,
              },
              {
                label: `<span data-i18n="searchpane.last_30d">${t(
                  "searchpane.last_30d",
                  "Last 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[2]) < 2592000000,
              },
              {
                label: `<span data-i18n="searchpane.older_30d">${t(
                  "searchpane.older_30d",
                  "More than 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[2]) >= 2592000000,
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 2,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.scope", "Scope"),
            options: [
              {
                label: `<i class="bx bx-xs bx-globe"></i> <span data-i18n="scope.global">${t(
                  "scope.global",
                  "Global",
                )}</span>`,
                value: (rowData) => rowData[6].includes("scope.global"),
              },
              {
                label: `<i class="bx bx-xs bx-server"></i> <span data-i18n="scope.service_specific">${t(
                  "scope.service_specific",
                  "Service",
                )}</span>`,
                value: (rowData) => rowData[6].includes("scope.service"),
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 6,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.service", "Service"),
          },
          targets: 7,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.end_date", "End Date"),
            options: [
              {
                label: `<span data-i18n="searchpane.next_24h">${t(
                  "searchpane.next_24h",
                  "Next 24 hours",
                )}</span>`,
                value: (rowData) =>
                  new Date(rowData[8]) - new Date() < 86400000,
              },
              {
                label: `<span data-i18n="searchpane.next_7d">${t(
                  "searchpane.next_7d",
                  "Next 7 days",
                )}</span>`,
                value: (rowData) =>
                  new Date(rowData[8]) - new Date() < 604800000,
              },
              {
                label: `<span data-i18n="searchpane.next_30d">${t(
                  "searchpane.next_30d",
                  "Next 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date(rowData[8]) - new Date() < 2592000000,
              },
              {
                label: `<span data-i18n="searchpane.future_30d">${t(
                  "searchpane.future_30d",
                  "More than 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date(rowData[8]) - new Date() >= 2592000000,
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 8,
        },
      ],
      order: [[2, "desc"]],
      autoFill: false,
      responsive: true,
      select: {
        style: "multi+shift",
        selector: "td:nth-child(2)",
        headerCheckbox: true,
      },
      layout: layout,
      initComplete: function (settings, json) {
        $("#bans_wrapper .btn-secondary").removeClass("btn-secondary");
        if (isReadOnly) {
          const titleKey = userReadOnly
            ? "tooltip.readonly_user_action_disabled"
            : "tooltip.readonly_db_action_disabled";
          const defaultTitle = userReadOnly
            ? "Your account is readonly, action disabled."
            : "The database is in readonly, action disabled.";
          $("#bans_wrapper .dt-buttons")
            .attr(
              "data-bs-original-title",
              t(titleKey, defaultTitle, {
                action: t("button.add_ban_plural"),
              }),
            )
            .attr("data-bs-placement", "right")
            .tooltip();
        }
        updateCountryTooltips();
      },
    },
  };

  // Wait for window.i18nextReady = true before continuing
  if (typeof window.i18nextReady === "undefined" || !window.i18nextReady) {
    const waitForI18next = (resolve) => {
      if (window.i18nextReady) {
        resolve();
      } else {
        setTimeout(() => waitForI18next(resolve), 50);
      }
    };
    new Promise((resolve) => {
      waitForI18next(resolve);
    }).then(() => {
      const dt = initializeDataTable(bans_config);
      dt.on("draw.dt", updateCountryTooltips);
      return dt;
    });
  }

  $(document).on("click", ".unban-ip", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const $this = $(this);
    const $row = $this.closest("tr");
    const $scopeCell = $row.find("td:eq(6)");
    const $serviceCell = $row.find("td:eq(7)");

    const scopeText =
      $scopeCell.find("span[data-i18n]").text().trim() ||
      $scopeCell.text().trim();
    const serviceText =
      $serviceCell.find("strong").text().trim() ||
      $serviceCell.find("span[data-i18n]").text().trim() ||
      $serviceCell.text().trim();

    const ban_scope =
      scopeText === t("scope.global", "Global") ? "global" : "service";
    const service =
      serviceText === t("scope.all_services", "All services")
        ? null
        : serviceText;

    setupUnbanModal([
      {
        ip: $this.data("ip"),
        time_remaining: $this.data("time-left"),
        ban_scope: ban_scope,
        service: service,
      },
    ]);
  });

  $("#add-ban").on("click", function () {
    const originalBan = $("#ban-1");
    const banClone = originalBan.clone();
    banClone.attr("id", `ban-${++addBanNumber}`);

    banClone
      .find("input[name='ip']")
      .removeClass("is-valid is-invalid")
      .val("");
    banClone.find("[readonly='readonly']").remove();
    banClone.find(".flatpickr-input").flatpickr({
      enableTime: true,
      dateFormat: "Y-m-d\\TH:i:S", // ISO format
      altInput: true,
      altFormat: "F j, Y h:i K",
      time_24hr: true,
      defaultDate: defaultDatetime,
      minDate: minDatetime,
      plugins: [new minMaxTimePlugin({ table: minMaxTable })],
    });
    banClone.find("input[name='reason']").val("ui");

    const deleteButtonContainer = banClone.find(".col-12.col-md-1");
    deleteButtonContainer.html(`
      <button type="button"
              class="btn btn-outline-danger btn-sm delete-ban"
              data-bs-toggle="tooltip"
              data-bs-placement="right"
              title="${t("tooltip.remove_ban_entry", "Remove this ban entry")}">
        <i class="bx bx-trash bx-xs"></i>
      </button>
    `);

    // Initialize ban scope handlers for the cloned item
    initializeBanScopeHandlers(banClone);

    $("#bans-container").append(banClone);

    // Initialize tooltip for the new delete button
    banClone.find('[data-bs-toggle="tooltip"]').tooltip();
  });

  $("#clear-bans").on("click", function () {
    $("#bans-container")
      .find("li.ban-item")
      .each(function () {
        if ($(this).attr("id") !== "ban-1") {
          $(this).remove();
        }
      });
  });

  $(document).on("click", ".delete-ban", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const banContainer = $(this).closest("li.ban-item");
    if (banContainer.attr("id") === "ban-1") return;
    banContainer.fadeOut(300, function () {
      $(this).remove();
    });
  });

  $("#modal-ban-ips").on("hidden.bs.modal", function () {
    $("#clear-bans").trigger("click");
    const firstBan = $("#ban-1");
    firstBan
      .find("input[name='ip']")
      .val("")
      .removeClass("is-invalid is-valid");
    firstBan.find("input[name='reason']").val("ui");
    firstBan.find(".invalid-feedback").remove();
    originalFlatpickr.setDate(defaultDatetime);
    firstBan.find(".ban-scope-select").val("global").trigger("change");
  });

  const ipRegex = new RegExp(
    /^(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?!$)|$)){4}$|^((?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}|(?:[A-Fa-f0-9]{1,4}:){1,7}:|:(?::[A-Fa-f0-9]{1,4}){1,7}|::)$/i,
  );

  const validateBan = (banIpInput, ipServiceMap) => {
    const value = banIpInput.val().trim();
    let errorMessageKey = "";
    let isValid = true;
    const banContainer = banIpInput.closest("li.ban-item");

    if (value === "") {
      errorMessageKey = "validation.ip_required";
      isValid = false;
    } else if (!ipRegex.test(value)) {
      errorMessageKey = "validation.ip_invalid";
      isValid = false;
    } else {
      const banScope = banContainer.find('select[name="ban_scope"]').val();

      if (banScope === "global") {
        if (ipServiceMap.has(`${value}:global`)) {
          errorMessageKey = "validation.ip_global_duplicate";
          isValid = false;
        }
      } else if (banScope === "service") {
        const service = banContainer.find('select[name="service"]').val();
        if (!service) {
          errorMessageKey = "validation.service_required_for_ban";
          isValid = false;
        } else if (ipServiceMap.has(`${value}:service:${service}`)) {
          errorMessageKey = "validation.ip_service_duplicate";
          isValid = false;
        }
      }
    }

    banIpInput
      .toggleClass("is-valid", isValid)
      .toggleClass("is-invalid", !isValid);

    let $feedback = banIpInput.next(".invalid-feedback");
    if (!$feedback.length && !isValid) {
      $feedback = $('<div class="invalid-feedback"></div>').insertAfter(
        banIpInput,
      );
    }

    if (!isValid) {
      const service = banContainer.find('select[name="service"]').val();
      $feedback.text(t(errorMessageKey, { service: service }));
    } else if ($feedback.length) {
      $feedback.text("");
    }

    return isValid;
  };

  $("#bans-container").on("input", "input[name='ip']", function () {
    debounce(() => {
      const $input = $(this);
      const ipServiceMap = new Map();

      $("#bans-container")
        .find("li.ban-item")
        .not($input.closest("li.ban-item"))
        .each(function () {
          const $li = $(this);
          const ip = $li.find("input[name='ip']").val().trim();
          if (!ip) return;

          const banScope = $li.find("select[name='ban_scope']").val();
          if (banScope === "global") {
            ipServiceMap.set(`${ip}:global`, true);
          } else if (banScope === "service") {
            const service = $li.find("select[name='service']").val();
            if (service) ipServiceMap.set(`${ip}:service:${service}`, true);
          }
        });
      validateBan($input, ipServiceMap);
    }, 100)();
  });

  $("#bans-form").on("submit", function (e) {
    e.preventDefault();
    let allValid = true;
    const ipServiceMap = new Map();

    $("#bans-container")
      .find("li.ban-item")
      .each(function () {
        const $li = $(this);
        const $input = $li.find("input[name='ip']");
        if (!validateBan($input, ipServiceMap)) {
          // Validate *and* update the map
          allValid = false;
        } else {
          // If valid, add to map for subsequent checks
          const ip = $input.val().trim();
          const banScope = $li.find("select[name='ban_scope']").val();
          if (banScope === "global") {
            ipServiceMap.set(`${ip}:global`, true);
          } else if (banScope === "service") {
            const service = $li.find("select[name='service']").val();
            if (service) ipServiceMap.set(`${ip}:service:${service}`, true);
          }
        }
      });

    if (!allValid) return; // Stop if any entry is invalid

    // Collect valid ban data
    const bans = [];
    $("#bans-container")
      .find("li.ban-item")
      .each(function () {
        // Changed selector slightly
        const $this = $(this);
        const ip = $this.find("input[name='ip']").val().trim();
        const end_date = $this.find(".flatpickr-input").val();
        const reason = $this.find("input[name='reason']").val().trim();
        const ban_scope = $this.find("select[name='ban_scope']").val();
        const service =
          ban_scope === "service"
            ? $this.find("select[name='service']").val()
            : null; // Set service to null for global

        bans.push({
          ip: ip,
          end_date: `${end_date}${getTimeZoneOffset()}`,
          reason: reason,
          ban_scope: ban_scope,
          service: service,
        });
      });

    // Create and submit the form
    const form = $("<form>", {
      method: "POST",
      action: `${window.location.pathname}/ban`,
      class: "visually-hidden",
    });
    form.append(
      $("<input>", {
        type: "hidden",
        name: "csrf_token",
        value: $("#csrf_token").val(),
      }),
    );
    form.append(
      $("<input>", {
        type: "hidden",
        name: "bans",
        value: JSON.stringify(bans),
      }),
    );
    form.appendTo("body").submit();
  });

  // Re-validate IP when service selection changes
  $("#bans-container").on("change", "select[name='service']", function () {
    const $ipInput = $(this).closest("li.ban-item").find("input[name='ip']");
    if ($ipInput.val().trim()) $ipInput.trigger("input");
  });

  // Initialize handlers for the initial ban item
  initializeBanScopeHandlers($("#ban-1"));

  // Function to show/hide service selection based on scope
  function initializeBanScopeHandlers($banItem) {
    const $banScopeSelect = $banItem.find(".ban-scope-select");
    const $serviceField = $banItem.find(".service-field");
    const $serviceSelect = $serviceField.find('select[name="service"]');

    toggleServiceField($banScopeSelect.val(), $serviceField, $serviceSelect); // Initial state

    $banScopeSelect.on("change", function () {
      const newScope = $(this).val();
      toggleServiceField(newScope, $serviceField, $serviceSelect);
      // Re-validate IP on scope change
      const $ipInput = $banItem.find("input[name='ip']");
      if ($ipInput.val().trim())
        setTimeout(() => $ipInput.trigger("input"), 50);
    });
  }

  // Helper to toggle service field visibility and requirement
  function toggleServiceField(scopeValue, $serviceField, $serviceSelect) {
    const showService = scopeValue === "service";
    $serviceField.toggleClass("show", showService); // Use 'show' class for visibility
    if (showService) {
      $serviceSelect.attr("required", true);
    } else {
      $serviceSelect.removeAttr("required");
      $serviceSelect.val(""); // Clear selection when hiding
      // Clear potential validation errors on the service select itself
      $serviceSelect.removeClass("is-invalid");
      const $serviceFeedback = $serviceSelect.next(".invalid-feedback");
      if ($serviceFeedback.length) $serviceFeedback.remove();
    }
  }
});
