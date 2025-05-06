$(document).ready(function () {
  const baseFlagsUrl = $("#base_flags_url").val().trim();

  const headers = [
    {
      title: "Date",
      tooltip: "The date and time when the Report was created",
    },
    { title: "IP Address", tooltip: "The reported IP address" },
    {
      title: "Country",
      tooltip: "The country of the reported IP address",
    },
    { title: "Method", tooltip: "The method used by the attacker" },
    {
      title: "URL",
      tooltip: "The URL that was targeted by the attacker",
    },
    {
      title: "Status Code",
      tooltip: "The HTTP status code returned by BunkerWeb",
    },
    { title: "User-Agent", tooltip: "The User-Agent of the attacker" },
    { title: "Reason", tooltip: "The reason why the Report was created" },
    {
      title: "Server name",
      tooltip: "The Server name that created the report",
    },
    { title: "Data", tooltip: "Additional data about the Report" },
    { title: "Security mode", tooltip: "Security mode" },
  ];

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
      search: true,
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
    },
    bottomStart: {
      pageLength: {
        menu: [10, 25, 50, 100, { label: "All", value: -1 }],
      },
      info: true,
    },
  };

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
          reports_table.ajax.reload(null, false);
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
  const reports_table = initializeDataTable({
    tableSelector: "#reports",
    tableName: "reports",
    columnVisibilityCondition: (column) => column > 2 && column < 12,
    dataTableOptions: {
      columnDefs: [
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
          },
          targets: 3,
          render: function (data) {
            const countryCode = data.toLowerCase();
            const tooltipContent = countriesDataNames[countryCode] || "N/A";
            return `
              <span data-bs-toggle="tooltip" data-bs-original-title="${tooltipContent}">
                <img src="${baseFlagsUrl}/${
                  countryCode === "local" ? "zz" : countryCode
                }.svg"
                     class="border border-1 p-0 me-1"
                     height="17"
                     loading="lazy" />
                &nbsp;－&nbsp;${countryCode === "local" ? "N/A" : data}
              </span>`;
          },
        },
        {
          targets: 5,
          render: function (data, type, row) {
            if (type !== "display") {
              return data;
            }

            // For display, check if URL is too long
            const maxUrlLength = 30;
            if (data && data.length > maxUrlLength) {
              // Create shortened version with ellipsis
              const shortUrl = data.substring(0, maxUrlLength - 3) + "...";
              return `<div data-bs-toggle="tooltip"
                        title="Click to view full URL"
                        data-bs-placement="top"><a href="#"
                        class="text-truncate url-truncated text-decoration-underline"
                        data-bs-toggle="modal"
                        data-bs-target="#fullUrlModal"
                        data-url="${data.replace(/"/g, "&quot;")}"
                        style="cursor: pointer;">
                        ${shortUrl}
                      </a></div>`;
            }

            return data;
          },
        },
        {
          searchPanes: {
            show: true,
            combiner: "or",
          },
          targets: 9,
          render: function (data) {
            return data === "_" ? "default server" : data;
          },
        },
        {
          searchPanes: { show: true },
          targets: [2, 4, 5, 6, 8, 11],
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
      processing: true,
      serverSide: true,
      ajax: {
        url: `${window.location.pathname}/fetch`,
        type: "POST",
        data: function (d) {
          d.csrf_token = $("#csrf_token").val(); // Add CSRF token if needed
          return d;
        },
      },
      initComplete: () => {
        updateCountryTooltips();
      },
      columns: [
        {
          data: null,
          defaultContent: "",
          orderable: false,
          className: "dtr-control",
        },
        { data: "date", title: "Date" },
        { data: "ip", title: "IP Address" },
        { data: "country", title: "Country" },
        { data: "method", title: "Method" },
        { data: "url", title: "URL" },
        { data: "status", title: "Status Code" },
        { data: "user_agent", title: "User-Agent" },
        { data: "reason", title: "Reason" },
        { data: "server_name", title: "Server name" },
        { data: "data", title: "Data" },
        { data: "security_mode", title: "Security mode" },
      ],
      headerCallback: function (thead) {
        updateHeaderTooltips(thead, headers);
      },
    },
  });

  // Create the modal for displaying full URLs once at document ready
  $("body").append(`
    <div class="modal fade" id="fullUrlModal" tabindex="-1" aria-labelledby="fullUrlModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="fullUrlModalLabel">Full URL</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <span id="fullUrlContent" class="text-break"></span>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" id="copyUrlBtn" class="btn btn-sm btn-outline-primary me-1">
              <span class="tf-icons bx bx-copy me-1"></span>Copy
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-bs-dismiss="modal">Close</button>
          </div>
        </div>
      </div>
    </div>
  `);

  // Add copy functionality to the copy button
  $(document).on("click", "#copyUrlBtn", function () {
    const textToCopy = $("#fullUrlContent").text();
    navigator.clipboard.writeText(textToCopy).then(() => {
      // Change button text temporarily to indicate success
      const $btn = $(this);
      const originalHtml = $btn.html();
      $btn.html('<span class="tf-icons bx bx-check me-1"></span>Copied!');
      setTimeout(() => {
        $btn.html(originalHtml);
      }, 2000);
    });
  });

  // Update the handler for the modal to display the full URL
  $("#fullUrlModal").on("show.bs.modal", function (event) {
    const button = $(event.relatedTarget); // Button that triggered the modal
    const url = button.data("url"); // Extract URL from data-url attribute
    $("#fullUrlContent").text(url);
  });

  // Update tooltips when column visibility changes
  reports_table.on("column-visibility.dt", function () {
    updateHeaderTooltips("#reports thead", headers);
  });

  // Utility function to manage header tooltips
  function updateHeaderTooltips(selector, headers) {
    $(selector)
      .find("th")
      .each((index, element) => {
        const thText = $(element).text().trim();
        headers.forEach((header) => {
          if (thText === header.title) {
            $(element).attr({
              "data-bs-toggle": "tooltip",
              "data-bs-placement": "bottom",
              title: header.tooltip,
            });
          }
        });
      });

    // Clean up and reinitialize tooltips
    $('[data-bs-toggle="tooltip"]').each(function () {
      const instance = bootstrap.Tooltip.getInstance(this);
      if (instance) {
        instance.dispose();
      }
    });
    $('[data-bs-toggle="tooltip"]').tooltip();
  }

  if (sessionAutoRefresh === "true") {
    toggleAutoRefresh();
  }

  $("#reports_wrapper").find(".btn-secondary").removeClass("btn-secondary");

  // Update tooltips after table draw
  reports_table.on("draw.dt", function () {
    updateCountryTooltips();

    // Clean up any existing tooltips to prevent memory leaks
    $(".tooltip").remove();
  });

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
