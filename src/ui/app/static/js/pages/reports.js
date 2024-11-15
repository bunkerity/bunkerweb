$(function () {
  const reportsNumber = parseInt($("#reports_number").val(), 10) || 0;
  const dataCountries = ($("#countries").val() || "")
    .split(",")
    .filter((code) => code && code !== "local");
  const baseFlagsUrl = $("#base_flags_url").val().trim();

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

  // Assuming baseFlagsUrl, dataCountries, and countriesDataNames are defined
  const countriesSearchPanesOptions = [
    {
      label: `<img src="${baseFlagsUrl}/zz.svg" class="border border-1 p-0 me-1" height="17" />&nbsp;－&nbsp;N/A`,
      value: (rowData) => rowData[2].includes("N/A"),
    },
    ...Object.entries(filteredCountriesDataNames).map(([code, name]) => ({
      label: `<img src="${baseFlagsUrl}/${code.toLowerCase()}.svg" class="border border-1 p-0 me-1" height="17" />&nbsp;－&nbsp;${name}`,
      value: (rowData) =>
        rowData[2].includes(`data-bs-original-title="${code}"`),
    })),
  ];

  // Batch update tooltips
  const updateCountryTooltips = () => {
    $("[data-bs-original-title]").each(function () {
      const $elem = $(this);
      const countryCode = $elem.attr("data-bs-original-title");
      const countryName = countriesDataNames[countryCode];
      if (countryName) {
        $elem.attr("data-bs-original-title", countryName);
      }
    });
    // Initialize tooltips once
    $('[data-bs-toggle="tooltip"]').tooltip();
  };

  // Configure DataTable layout
  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [1, 2, 3, 4, 5, 7, 8],
      },
    },
    topStart: {},
    topEnd: {
      buttons: [
        {
          extend: "auto_refresh",
          className: "btn btn-sm btn-outline-primary d-flex align-items-center",
        },
        {
          extend: "toggle_filters",
          className: "btn btn-sm btn-outline-primary toggle-filters",
        },
      ],
      search: true,
    },
    bottomStart: {
      info: true,
    },
    bottomEnd: {},
  };

  // Adjust page length options based on reports number
  if (reportsNumber > 10) {
    const menu = [10];
    if (reportsNumber > 25) menu.push(25);
    if (reportsNumber > 50) menu.push(50);
    if (reportsNumber > 100) menu.push(100);
    menu.push({ label: "All", value: -1 });
    layout.bottomStart = {
      pageLength: {
        menu: menu,
      },
      info: true,
    };
    layout.bottomEnd.paging = true;
  }

  // Define DataTable buttons
  layout.topStart.buttons = [
    {
      extend: "colvis",
      columns: "th:not(:first-child):not(:last-child)",
      text: '<span class="tf-icons bx bx-columns bx-18px me-2"></span>Columns',
      className: "btn btn-sm btn-outline-primary",
      columnText: (dt, idx, title) => `${idx + 1}. ${title}`,
    },
    {
      extend: "colvisRestore",
      text: '<span class="tf-icons bx bx-reset bx-18px me-2"></span>Reset<span class="d-none d-md-inline"> columns</span>',
      className: "btn btn-sm btn-outline-primary",
    },
    {
      extend: "collection",
      text: '<span class="tf-icons bx bx-export bx-18px me-2"></span>Export',
      className: "btn btn-sm btn-outline-primary",
      buttons: [
        {
          extend: "copy",
          text: '<span class="tf-icons bx bx-copy bx-18px me-2"></span>Copy visible',
          exportOptions: {
            columns: ":visible:not(:first-child):not(:last-child)",
          },
        },
        {
          extend: "csv",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV',
          bom: true,
          filename: "bw_report",
          exportOptions: {
            modifier: { search: "none" },
          },
        },
        {
          extend: "excel",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel',
          filename: "bw_report",
          exportOptions: {
            modifier: { search: "none" },
          },
        },
      ],
    },
  ];

  // Custom button for toggling filters
  $.fn.dataTable.ext.buttons.toggle_filters = {
    text: '<span class="tf-icons bx bx-filter bx-18px me-2"></span><span id="show-filters">Show</span><span id="hide-filters" class="d-none">Hide</span><span class="d-none d-md-inline"> filters</span>',
    action: (e, dt, node, config) => {
      reports_table.searchPanes.container().slideToggle();
      $("#show-filters, #hide-filters").toggleClass("d-none");
    },
  };

  // Custom button for auto-refresh
  let autoRefresh = false;
  const sessionAutoRefresh = sessionStorage.getItem("reportsAutoRefresh");

  function toggleAutoRefresh() {
    autoRefresh = !autoRefresh;
    sessionStorage.setItem("reportsAutoRefresh", autoRefresh);
    if (autoRefresh) {
      $(".bx-loader")
        .addClass("bx-spin")
        .closest(".btn")
        .removeClass("btn-outline-primary")
        .addClass("btn-primary");
      const interval = setInterval(() => {
        if (!autoRefresh) {
          clearInterval(interval);
        } else {
          window.location.reload();
        }
      }, 10000); // 10 seconds
    } else {
      $(".bx-loader")
        .removeClass("bx-spin")
        .closest(".btn")
        .removeClass("btn-primary")
        .addClass("btn-outline-primary");
    }
  }

  $.fn.dataTable.ext.buttons.auto_refresh = {
    text: '<span class="bx bx-loader bx-18px lh-1"></span>&nbsp;&nbsp;Auto refresh',
    action: (e, dt, node, config) => {
      toggleAutoRefresh();
    },
  };

  // Initialize DataTable
  const reports_table = new DataTable("#reports", {
    columnDefs: [
      { orderable: false, targets: -1 },
      { visible: false, targets: [6, 9] },
      { type: "ip-address", targets: 1 },
      {
        targets: 0,
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
        },
        targets: 2,
      },
      {
        searchPanes: { show: true },
        targets: [1, 2, 3, 4, 5, 7, 8],
      },
    ],
    order: [[0, "desc"]],
    autoFill: false,
    responsive: true,
    layout: layout,
    language: {
      info: "Showing _START_ to _END_ of _TOTAL_ reports",
      infoEmpty: "No reports available",
      infoFiltered: "(filtered from _MAX_ total reports)",
      lengthMenu: "Display _MENU_ reports",
      zeroRecords: "No matching reports found",
      select: {
        rows: {
          _: "Selected %d reports",
          0: "No reports selected",
          1: "Selected 1 report",
        },
      },
    },
    initComplete: () => {
      $("#reports_wrapper").find(".btn-secondary").removeClass("btn-secondary");
      updateCountryTooltips();
    },
  });

  $(".dt-type-numeric").removeClass("dt-type-numeric");

  if (sessionAutoRefresh === "true") {
    toggleAutoRefresh();
  }

  // Initially hide search panes
  reports_table.searchPanes.container().hide();

  // Show the reports table and hide the loading indicator
  $("#reports").removeClass("d-none");
  $("#reports-waiting").addClass("visually-hidden");

  // Update tooltips after table draw
  reports_table.on("draw.dt", updateCountryTooltips);
});
