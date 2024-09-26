$(function () {
  const reportsNumber = parseInt($("#reports_number").val(), 10) || 0;
  const dataCountries = ($("#countries").val() || "")
    .split(",")
    .filter((code) => code && code !== "local");

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
    AX: "\u00c5land Islands",
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
    CI: "C\u00f4te d'Ivoire",
    CK: "Cook Islands",
    CL: "Chile",
    CM: "Cameroon",
    CN: "China (People's Republic of China)",
    CO: "Colombia",
    CR: "Costa Rica",
    CU: "Cuba",
    CV: "Cape Verde",
    CW: "Cura\u00e7ao",
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

  const countriesSearchPanesOptions = [
    {
      label: "N/A",
      value: function (rowData) {
        return $(rowData[2]).text().trim() === "N/A";
      },
    },
  ];

  dataCountries.forEach((countryCode) => {
    const regex = new RegExp(`\\b${countryCode}$`, "i");
    countriesSearchPanesOptions.push({
      label: countryCode,
      value: function (rowData) {
        return $(rowData[2]).text().trim().match(regex);
      },
    });
  });

  const updateCountryTooltips = function () {
    dataCountries.forEach((countryCode) => {
      const country = countriesDataNames[countryCode];
      if (country) {
        $(`[data-bs-original-title="${countryCode}"]`).attr(
          "data-bs-original-title",
          country,
        );
      }
    });
    $('[data-bs-toggle="tooltip"]').tooltip();
  };

  const layout = {
    topStart: {},
    bottomEnd: {},
    bottom1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        columns: [1, 2, 3, 4, 5, 7],
      },
    },
  };

  if (reportsNumber > 10) {
    const menu = [10];
    if (reportsNumber > 25) menu.push(25);
    if (reportsNumber > 50) menu.push(50);
    if (reportsNumber > 100) menu.push(100);
    menu.push({ label: "All", value: -1 });
    layout.topStart.pageLength = { menu };
    layout.bottomEnd.paging = true;
  }

  layout.topStart.buttons = [
    {
      extend: "colvis",
      columns: "th:not(:first-child):not(:last-child)",
      text: '<span class="tf-icons bx bx-columns bx-18px me-2"></span>Columns',
      className: "btn btn-sm btn-outline-primary",
      columnText: function (dt, idx, title) {
        return `${idx + 1}. ${title}`;
      },
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
          text: '<span class="tf-icons bx bx-copy bx-18px me-2"></span>Copy current page',
          exportOptions: {
            modifier: { page: "current" },
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

  $(".report-date").each(function () {
    const $this = $(this);
    const isoDateStr = $this.text().trim();
    const date = new Date(isoDateStr);
    if (!isNaN(date)) {
      $this.text(date.toLocaleString());
    }
  });

  const reports_table = new DataTable("#reports", {
    columnDefs: [
      { orderable: false, targets: -1 },
      { visible: false, targets: [6, -1] },
      { type: "ip-address", targets: 1 },
      {
        searchPanes: {
          show: true,
          options: countriesSearchPanesOptions,
        },
        targets: 2,
      },
      {
        searchPanes: { show: true },
        targets: [1, 2, 3, 4, 5, 7],
      },
      {
        targets: "_all",
        createdCell: function (td) {
          $(td).addClass("align-items-center");
        },
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
    initComplete: function () {
      const $wrapper = $("#reports_wrapper");
      $wrapper.find(".btn-secondary").removeClass("btn-secondary");
      $wrapper.find("th").addClass("text-center");
      updateCountryTooltips();
    },
  });

  $("#reports").removeClass("d-none");
  $("#reports-waiting").addClass("visually-hidden");

  let lastRowIdx = null;

  reports_table.on("mouseenter", "td", function () {
    const cellIdx = reports_table.cell(this).index();
    if (!cellIdx) return;
    const rowIdx = cellIdx.row;

    if (lastRowIdx !== null && lastRowIdx !== rowIdx) {
      reports_table.row(lastRowIdx).nodes().to$().removeClass("highlight");
    }

    reports_table.row(rowIdx).nodes().to$().addClass("highlight");
    lastRowIdx = rowIdx;
  });

  reports_table.on("mouseleave", "td", function () {
    if (lastRowIdx !== null) {
      reports_table.row(lastRowIdx).nodes().to$().removeClass("highlight");
      lastRowIdx = null;
    }
  });

  reports_table.on("draw.dt", updateCountryTooltips);
});
