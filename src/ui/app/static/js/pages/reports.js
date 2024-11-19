$(function () {
  const reportsNumber = parseInt($("#reports_number").val(), 10) || 0;
  const dataCountries = ($("#countries").val() || "")
    .split(",")
    .filter((code) => code && code !== "local");
  const baseFlagsUrl = $("#base_flags_url").val().trim();

  const countriesDataNames = {
    ad: "Andorra",
    ae: "United Arab Emirates",
    af: "Afghanistan",
    ag: "Antigua and Barbuda",
    ai: "Anguilla",
    al: "Albania",
    am: "Armenia",
    ao: "Angola",
    aq: "Antarctica",
    ar: "Argentina",
    as: "American Samoa",
    at: "Austria",
    au: "Australia",
    aw: "Aruba",
    ax: "Åland Islands",
    az: "Azerbaijan",
    ba: "Bosnia and Herzegovina",
    bb: "Barbados",
    bd: "Bangladesh",
    be: "Belgium",
    bf: "Burkina Faso",
    bg: "Bulgaria",
    bh: "Bahrain",
    bi: "Burundi",
    bj: "Benin",
    bl: "Saint Barthélemy",
    bm: "Bermuda",
    bn: "Brunei Darussalam",
    bo: "Bolivia, Plurinational State of",
    bq: "Caribbean Netherlands",
    br: "Brazil",
    bs: "Bahamas",
    bt: "Bhutan",
    bv: "Bouvet Island",
    bw: "Botswana",
    by: "Belarus",
    bz: "Belize",
    ca: "Canada",
    cc: "Cocos (Keeling) Islands",
    cd: "Congo, the Democratic Republic of the",
    cf: "Central African Republic",
    cg: "Republic of the Congo",
    ch: "Switzerland",
    ci: "Côte d'Ivoire",
    ck: "Cook Islands",
    cl: "Chile",
    cm: "Cameroon",
    cn: "China (People's Republic of China)",
    co: "Colombia",
    cr: "Costa Rica",
    cu: "Cuba",
    cv: "Cape Verde",
    cw: "Curaçao",
    cx: "Christmas Island",
    cy: "Cyprus",
    cz: "Czech Republic",
    de: "Germany",
    dj: "Djibouti",
    dk: "Denmark",
    dm: "Dominica",
    do: "Dominican Republic",
    dz: "Algeria",
    ec: "Ecuador",
    ee: "Estonia",
    eg: "Egypt",
    eh: "Western Sahara",
    er: "Eritrea",
    es: "Spain",
    et: "Ethiopia",
    eu: "Europe",
    fi: "Finland",
    fj: "Fiji",
    fk: "Falkland Islands (Malvinas)",
    fm: "Micronesia, Federated States of",
    fo: "Faroe Islands",
    fr: "France",
    ga: "Gabon",
    gb: "United Kingdom",
    gd: "Grenada",
    ge: "Georgia",
    gf: "French Guiana",
    gg: "Guernsey",
    gh: "Ghana",
    gi: "Gibraltar",
    gl: "Greenland",
    gm: "Gambia",
    gn: "Guinea",
    gp: "Guadeloupe",
    gq: "Equatorial Guinea",
    gr: "Greece",
    gs: "South Georgia and the South Sandwich Islands",
    gt: "Guatemala",
    gu: "Guam",
    gw: "Guinea-Bissau",
    gy: "Guyana",
    hk: "Hong Kong",
    hm: "Heard Island and McDonald Islands",
    hn: "Honduras",
    hr: "Croatia",
    ht: "Haiti",
    hu: "Hungary",
    id: "Indonesia",
    ie: "Ireland",
    il: "Israel",
    im: "Isle of Man",
    in: "India",
    io: "British Indian Ocean Territory",
    iq: "Iraq",
    ir: "Iran, Islamic Republic of",
    is: "Iceland",
    it: "Italy",
    je: "Jersey",
    jm: "Jamaica",
    jo: "Jordan",
    jp: "Japan",
    ke: "Kenya",
    kg: "Kyrgyzstan",
    kh: "Cambodia",
    ki: "Kiribati",
    km: "Comoros",
    kn: "Saint Kitts and Nevis",
    kp: "Korea, Democratic People's Republic of",
    kr: "Korea, Republic of",
    kw: "Kuwait",
    ky: "Cayman Islands",
    kz: "Kazakhstan",
    la: "Laos (Lao People's Democratic Republic)",
    lb: "Lebanon",
    lc: "Saint Lucia",
    li: "Liechtenstein",
    lk: "Sri Lanka",
    lr: "Liberia",
    ls: "Lesotho",
    lt: "Lithuania",
    lu: "Luxembourg",
    lv: "Latvia",
    ly: "Libya",
    ma: "Morocco",
    mc: "Monaco",
    md: "Moldova, Republic of",
    me: "Montenegro",
    mf: "Saint Martin",
    mg: "Madagascar",
    mh: "Marshall Islands",
    mk: "North Macedonia",
    ml: "Mali",
    mm: "Myanmar",
    mn: "Mongolia",
    mo: "Macao",
    mp: "Northern Mariana Islands",
    mq: "Martinique",
    mr: "Mauritania",
    ms: "Montserrat",
    mt: "Malta",
    mu: "Mauritius",
    mv: "Maldives",
    mw: "Malawi",
    mx: "Mexico",
    my: "Malaysia",
    mz: "Mozambique",
    na: "Namibia",
    nc: "New Caledonia",
    ne: "Niger",
    nf: "Norfolk Island",
    ng: "Nigeria",
    ni: "Nicaragua",
    nl: "Netherlands",
    no: "Norway",
    np: "Nepal",
    nr: "Nauru",
    nu: "Niue",
    nz: "New Zealand",
    om: "Oman",
    pa: "Panama",
    pe: "Peru",
    pf: "French Polynesia",
    pg: "Papua New Guinea",
    ph: "Philippines",
    pk: "Pakistan",
    pl: "Poland",
    pm: "Saint Pierre and Miquelon",
    pn: "Pitcairn",
    pr: "Puerto Rico",
    ps: "Palestine",
    pt: "Portugal",
    pw: "Palau",
    py: "Paraguay",
    qa: "Qatar",
    re: "Réunion",
    ro: "Romania",
    rs: "Serbia",
    ru: "Russian Federation",
    rw: "Rwanda",
    sa: "Saudi Arabia",
    sb: "Solomon Islands",
    sc: "Seychelles",
    sd: "Sudan",
    se: "Sweden",
    sg: "Singapore",
    sh: "Saint Helena, Ascension and Tristan da Cunha",
    si: "Slovenia",
    sj: "Svalbard and Jan Mayen Islands",
    sk: "Slovakia",
    sl: "Sierra Leone",
    sm: "San Marino",
    sn: "Senegal",
    so: "Somalia",
    sr: "Suriname",
    ss: "South Sudan",
    st: "Sao Tome and Principe",
    sv: "El Salvador",
    sx: "Sint Maarten (Dutch part)",
    sy: "Syrian Arab Republic",
    sz: "Swaziland",
    tc: "Turks and Caicos Islands",
    td: "Chad",
    tf: "French Southern Territories",
    tg: "Togo",
    th: "Thailand",
    tj: "Tajikistan",
    tk: "Tokelau",
    tl: "Timor-Leste",
    tm: "Turkmenistan",
    tn: "Tunisia",
    to: "Tonga",
    tr: "Turkey",
    tt: "Trinidad and Tobago",
    tv: "Tuvalu",
    tw: "Taiwan (Republic of China)",
    tz: "Tanzania, United Republic of",
    ua: "Ukraine",
    ug: "Uganda",
    um: "US Minor Outlying Islands",
    us: "United States",
    uy: "Uruguay",
    uz: "Uzbekistan",
    va: "Holy See (Vatican City State)",
    vc: "Saint Vincent and the Grenadines",
    ve: "Venezuela, Bolivarian Republic of",
    vg: "Virgin Islands, British",
    vi: "Virgin Islands, U.S.",
    vn: "Vietnam",
    vu: "Vanuatu",
    wf: "Wallis and Futuna Islands",
    ws: "Samoa",
    xk: "Kosovo",
    ye: "Yemen",
    yt: "Mayotte",
    za: "South Africa",
    zm: "Zambia",
    zw: "Zimbabwe",
  };

  // Precompute filtered options using jQuery's map for efficiency
  const countriesSearchPanesOptions = $.map(dataCountries, function (code) {
    if (countriesDataNames[code]) {
      return {
        label: `<img src="${baseFlagsUrl}/${code}.svg" class="border border-1 p-0 me-1" height="17" />&nbsp;－&nbsp;${countriesDataNames[code]}`,
        value: function (rowData) {
          return rowData[3].indexOf(`${code}.svg`) !== -1;
        },
      };
    }
  });

  // Append the "N/A" option first
  countriesSearchPanesOptions.unshift({
    label: `<img src="${baseFlagsUrl}/zz.svg" class="border border-1 p-0 me-1" height="17" />&nbsp;－&nbsp;N/A`,
    value: function (rowData) {
      return rowData[3].indexOf("N/A") !== -1;
    },
  });

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
        columns: [2, 3, 4, 5, 6, 8, 9, 11],
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
      columns: "th:not(:nth-child(-n+3))",
      text: '<span class="tf-icons bx bx-columns bx-18px me-2"></span>Columns',
      className: "btn btn-sm btn-outline-primary",
      columnText: function (dt, idx, title) {
        return idx + 1 + ". " + title;
      },
    },
    {
      extend: "colvisRestore",
      text: '<span class="tf-icons bx bx-reset bx-18px me-md-2"></span><span class="d-none d-md-inline">Reset columns</span>',
      className: "btn btn-sm btn-outline-primary",
    },
    {
      extend: "collection",
      text: '<span class="tf-icons bx bx-export bx-18px me-md-2"></span><span class="d-none d-md-inline">Export</span>',
      className: "btn btn-sm btn-outline-primary",
      buttons: [
        {
          extend: "copy",
          text: '<span class="tf-icons bx bx-copy bx-18px me-2"></span>Copy visible',
          exportOptions: {
            columns: ":visible:not(:first-child)",
          },
        },
        {
          extend: "csv",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV',
          bom: true,
          filename: "bw_report",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:first-child)",
          },
        },
        {
          extend: "excel",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel',
          filename: "bw_report",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:first-child)",
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
      {
        orderable: false,
        className: "dtr-control",
        targets: 0,
      },
      { orderable: false, targets: -1 },
      { visible: false, targets: [4, 5, 6, 7, 10] },
      { type: "ip-address", targets: 2 },
      {
        render: function (data, type, row) {
          if (type === "display" || type === "filter") {
            const date = new Date(data);
            if (!isNaN(date.getTime())) {
              return date.toLocaleString();
            }
          }
          return data;
        },
        targets: 1,
      },
      {
        searchPanes: {
          show: true,
          combiner: "or",
          options: countriesSearchPanesOptions,
        },
        targets: 3,
      },
      {
        searchPanes: { show: true },
        targets: [2, 4, 5, 6, 8, 9, 11],
      },
    ],
    order: [[1, "desc"]],
    autoFill: false,
    responsive: true,
    layout: layout,
    language: {
      info: "Showing _START_ to _END_ of _TOTAL_ reports",
      infoEmpty: "No reports available",
      infoFiltered: "(filtered from _MAX_ total reports)",
      lengthMenu: "Display _MENU_ reports",
      zeroRecords: "No matching reports found",
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

  const defaultColsVisibility = {
    3: true,
    4: false,
    5: false,
    6: false,
    7: false,
    8: true,
    9: true,
    10: false,
    11: true,
  };

  var columnVisibility = localStorage.getItem("bw-reports-columns");
  if (columnVisibility === null) {
    columnVisibility = JSON.parse(JSON.stringify(defaultColsVisibility));
  } else {
    columnVisibility = JSON.parse(columnVisibility);
    Object.entries(columnVisibility).forEach(([key, value]) => {
      reports_table.column(key).visible(value);
    });
  }

  reports_table.responsive.recalc();

  // Update tooltips after table draw
  reports_table.on("draw.dt", updateCountryTooltips);

  reports_table.on(
    "column-visibility.dt",
    function (e, settings, column, state) {
      if (column < 3) return;
      columnVisibility[column] = state;
      // Check if columVisibility is equal to defaultColsVisibility
      const isDefault =
        JSON.stringify(columnVisibility) ===
        JSON.stringify(defaultColsVisibility);
      // If it is, remove the key from localStorage
      if (isDefault) {
        localStorage.removeItem("bw-reports-columns");
      } else {
        localStorage.setItem(
          "bw-reports-columns",
          JSON.stringify(columnVisibility),
        );
      }
    },
  );

  const hashValue = location.hash;
  if (hashValue) {
    $("#dt-length-0").val(hashValue.replace("#", ""));
    $("#dt-length-0").trigger("change");
  }

  $("#dt-length-0").on("change", function () {
    const value = $(this).val();
    history.replaceState(
      null,
      "",
      value === "10" ? location.pathname : `#${value}`,
    );
  });
});
