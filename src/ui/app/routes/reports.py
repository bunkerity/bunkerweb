from collections import defaultdict
from datetime import datetime
from itertools import chain
from json import dumps, loads
from traceback import format_exc

from flask import Blueprint, flash, jsonify, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS
from app.utils import LOGGER

from app.routes.utils import cors_required, get_redis_client

reports = Blueprint("reports", __name__)

COUNTRIES_DATA_NAMES = {
    "ad": "Andorra",
    "ae": "United Arab Emirates",
    "af": "Afghanistan",
    "ag": "Antigua and Barbuda",
    "ai": "Anguilla",
    "al": "Albania",
    "am": "Armenia",
    "ao": "Angola",
    "aq": "Antarctica",
    "ar": "Argentina",
    "as": "American Samoa",
    "at": "Austria",
    "au": "Australia",
    "aw": "Aruba",
    "ax": "Åland Islands",
    "az": "Azerbaijan",
    "ba": "Bosnia and Herzegovina",
    "bb": "Barbados",
    "bd": "Bangladesh",
    "be": "Belgium",
    "bf": "Burkina Faso",
    "bg": "Bulgaria",
    "bh": "Bahrain",
    "bi": "Burundi",
    "bj": "Benin",
    "bl": "Saint Barthélemy",
    "bm": "Bermuda",
    "bn": "Brunei Darussalam",
    "bo": "Bolivia, Plurinational State of",
    "bq": "Caribbean Netherlands",
    "br": "Brazil",
    "bs": "Bahamas",
    "bt": "Bhutan",
    "bv": "Bouvet Island",
    "bw": "Botswana",
    "by": "Belarus",
    "bz": "Belize",
    "ca": "Canada",
    "cc": "Cocos (Keeling) Islands",
    "cd": "Congo, the Democratic Republic of the",
    "cf": "Central African Republic",
    "cg": "Republic of the Congo",
    "ch": "Switzerland",
    "ci": "Côte d'Ivoire",
    "ck": "Cook Islands",
    "cl": "Chile",
    "cm": "Cameroon",
    "cn": "China (People's Republic of China)",
    "co": "Colombia",
    "cr": "Costa Rica",
    "cu": "Cuba",
    "cv": "Cape Verde",
    "cw": "Curaçao",
    "cx": "Christmas Island",
    "cy": "Cyprus",
    "cz": "Czech Republic",
    "de": "Germany",
    "dj": "Djibouti",
    "dk": "Denmark",
    "dm": "Dominica",
    "do": "Dominican Republic",
    "dz": "Algeria",
    "ec": "Ecuador",
    "ee": "Estonia",
    "eg": "Egypt",
    "eh": "Western Sahara",
    "er": "Eritrea",
    "es": "Spain",
    "et": "Ethiopia",
    "eu": "Europe",
    "fi": "Finland",
    "fj": "Fiji",
    "fk": "Falkland Islands (Malvinas)",
    "fm": "Micronesia, Federated States of",
    "fo": "Faroe Islands",
    "fr": "France",
    "ga": "Gabon",
    "gb": "United Kingdom",
    "gd": "Grenada",
    "ge": "Georgia",
    "gf": "French Guiana",
    "gg": "Guernsey",
    "gh": "Ghana",
    "gi": "Gibraltar",
    "gl": "Greenland",
    "gm": "Gambia",
    "gn": "Guinea",
    "gp": "Guadeloupe",
    "gq": "Equatorial Guinea",
    "gr": "Greece",
    "gs": "South Georgia and the South Sandwich Islands",
    "gt": "Guatemala",
    "gu": "Guam",
    "gw": "Guinea-Bissau",
    "gy": "Guyana",
    "hk": "Hong Kong",
    "hm": "Heard Island and McDonald Islands",
    "hn": "Honduras",
    "hr": "Croatia",
    "ht": "Haiti",
    "hu": "Hungary",
    "id": "Indonesia",
    "ie": "Ireland",
    "il": "Israel",
    "im": "Isle of Man",
    "in": "India",
    "io": "British Indian Ocean Territory",
    "iq": "Iraq",
    "ir": "Iran, Islamic Republic of",
    "is": "Iceland",
    "it": "Italy",
    "je": "Jersey",
    "jm": "Jamaica",
    "jo": "Jordan",
    "jp": "Japan",
    "ke": "Kenya",
    "kg": "Kyrgyzstan",
    "kh": "Cambodia",
    "ki": "Kiribati",
    "km": "Comoros",
    "kn": "Saint Kitts and Nevis",
    "kp": "Korea, Democratic People's Republic of",
    "kr": "Korea, Republic of",
    "kw": "Kuwait",
    "ky": "Cayman Islands",
    "kz": "Kazakhstan",
    "la": "Laos (Lao People's Democratic Republic)",
    "lb": "Lebanon",
    "lc": "Saint Lucia",
    "li": "Liechtenstein",
    "lk": "Sri Lanka",
    "lr": "Liberia",
    "ls": "Lesotho",
    "lt": "Lithuania",
    "lu": "Luxembourg",
    "lv": "Latvia",
    "ly": "Libya",
    "ma": "Morocco",
    "mc": "Monaco",
    "md": "Moldova, Republic of",
    "me": "Montenegro",
    "mf": "Saint Martin",
    "mg": "Madagascar",
    "mh": "Marshall Islands",
    "mk": "North Macedonia",
    "ml": "Mali",
    "mm": "Myanmar",
    "mn": "Mongolia",
    "mo": "Macao",
    "mp": "Northern Mariana Islands",
    "mq": "Martinique",
    "mr": "Mauritania",
    "ms": "Montserrat",
    "mt": "Malta",
    "mu": "Mauritius",
    "mv": "Maldives",
    "mw": "Malawi",
    "mx": "Mexico",
    "my": "Malaysia",
    "mz": "Mozambique",
    "na": "Namibia",
    "nc": "New Caledonia",
    "ne": "Niger",
    "nf": "Norfolk Island",
    "ng": "Nigeria",
    "ni": "Nicaragua",
    "nl": "Netherlands",
    "no": "Norway",
    "np": "Nepal",
    "nr": "Nauru",
    "nu": "Niue",
    "nz": "New Zealand",
    "om": "Oman",
    "pa": "Panama",
    "pe": "Peru",
    "pf": "French Polynesia",
    "pg": "Papua New Guinea",
    "ph": "Philippines",
    "pk": "Pakistan",
    "pl": "Poland",
    "pm": "Saint Pierre and Miquelon",
    "pn": "Pitcairn",
    "pr": "Puerto Rico",
    "ps": "Palestine",
    "pt": "Portugal",
    "pw": "Palau",
    "py": "Paraguay",
    "qa": "Qatar",
    "re": "Réunion",
    "ro": "Romania",
    "rs": "Serbia",
    "ru": "Russian Federation",
    "rw": "Rwanda",
    "sa": "Saudi Arabia",
    "sb": "Solomon Islands",
    "sc": "Seychelles",
    "sd": "Sudan",
    "se": "Sweden",
    "sg": "Singapore",
    "sh": "Saint Helena, Ascension and Tristan da Cunha",
    "si": "Slovenia",
    "sj": "Svalbard and Jan Mayen Islands",
    "sk": "Slovakia",
    "sl": "Sierra Leone",
    "sm": "San Marino",
    "sn": "Senegal",
    "so": "Somalia",
    "sr": "Suriname",
    "ss": "South Sudan",
    "st": "Sao Tome and Principe",
    "sv": "El Salvador",
    "sx": "Sint Maarten (Dutch part)",
    "sy": "Syrian Arab Republic",
    "sz": "Swaziland",
    "tc": "Turks and Caicos Islands",
    "td": "Chad",
    "tf": "French Southern Territories",
    "tg": "Togo",
    "th": "Thailand",
    "tj": "Tajikistan",
    "tk": "Tokelau",
    "tl": "Timor-Leste",
    "tm": "Turkmenistan",
    "tn": "Tunisia",
    "to": "Tonga",
    "tr": "Turkey",
    "tt": "Trinidad and Tobago",
    "tv": "Tuvalu",
    "tw": "Taiwan (Republic of China)",
    "tz": "Tanzania, United Republic of",
    "ua": "Ukraine",
    "ug": "Uganda",
    "um": "US Minor Outlying Islands",
    "us": "United States",
    "uy": "Uruguay",
    "uz": "Uzbekistan",
    "va": "Holy See (Vatican City State)",
    "vc": "Saint Vincent and the Grenadines",
    "ve": "Venezuela, Bolivarian Republic of",
    "vg": "Virgin Islands, British",
    "vi": "Virgin Islands, U.S.",
    "vn": "Vietnam",
    "vu": "Vanuatu",
    "wf": "Wallis and Futuna Islands",
    "ws": "Samoa",
    "xk": "Kosovo",
    "ye": "Yemen",
    "yt": "Mayotte",
    "za": "South Africa",
    "zm": "Zambia",
    "zw": "Zimbabwe",
}


@reports.route("/reports", methods=["GET"])
@login_required
def reports_page():
    return render_template("reports.html")


@reports.route("/reports/fetch", methods=["POST"])
@login_required
@cors_required
def reports_fetch():
    redis_client = get_redis_client()

    # Fetch reports
    def fetch_reports():
        if redis_client:
            try:
                redis_reports = redis_client.lrange("requests", 0, -1)
                redis_reports = (loads(report_raw.decode("utf-8", "replace")) for report_raw in redis_reports)
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Failed to fetch reports from Redis: {e}")
                flash("Failed to fetch reports from Redis, see logs for more information.", "error")
                redis_reports = []
        else:
            redis_reports = []
        instance_reports = BW_INSTANCES_UTILS.get_reports() if BW_INSTANCES_UTILS else []
        return chain(redis_reports, instance_reports)

    # Filter valid and unique reports
    seen_ids = set()
    all_reports = list(
        report
        for report in fetch_reports()
        if report.get("id") not in seen_ids
        and (400 <= report.get("status", 0) < 500 or report.get("security_mode") == "detect")
        and not seen_ids.add(report.get("id"))
    )

    # Extract DataTables parameters
    draw = int(request.form.get("draw", 1))
    start = int(request.form.get("start", 0))
    length = int(request.form.get("length", 10))
    search_value = request.form.get("search[value]", "").lower()
    order_column_index = int(request.form.get("order[0][column]", 0)) - 1
    order_direction = request.form.get("order[0][dir]", "desc")
    search_panes = defaultdict(list)
    for key, value in request.form.items():
        if key.startswith("searchPanes["):
            field = key.split("[")[1].split("]")[0]
            search_panes[field].append(value)

    columns = ["date", "ip", "country", "method", "url", "status", "user_agent", "reason", "server_name", "data", "security_mode"]

    # Apply searchPanes filters
    def filter_by_search_panes(reports):
        for field, selected_values in search_panes.items():
            reports = [report for report in reports if report.get(field, "N/A") in selected_values]
        return reports

    # Global search filtering
    def global_search_filter(report):
        return any(search_value in str(report.get(col, "")).lower() for col in columns)

    # Sort reports
    def sort_reports(reports):
        if 0 <= order_column_index < len(columns):
            sort_key = columns[order_column_index]
            reports.sort(key=lambda x: x.get(sort_key, ""), reverse=(order_direction == "desc"))

    # Apply filters and sort
    filtered_reports = filter(global_search_filter, all_reports) if search_value else all_reports
    filtered_reports = list(filter_by_search_panes(filtered_reports))
    sort_reports(filtered_reports)

    # Pagination
    paginated_reports = filtered_reports[start : start + length]  # noqa: E203

    # Format reports for the response
    def format_report(report):
        return {
            "date": datetime.fromtimestamp(report.get("date", 0)).isoformat() if report.get("date") else "N/A",
            "ip": report.get("ip", "N/A"),
            "country": report.get("country", "N/A"),
            "method": report.get("method", "N/A"),
            "url": report.get("url", "N/A"),
            "status": report.get("status", "N/A"),
            "user_agent": report.get("user_agent", "N/A"),
            "reason": report.get("reason", "N/A"),
            "server_name": report.get("server_name", "N/A"),
            "data": dumps(report.get("data", {})),
            "security_mode": report.get("security_mode", "N/A"),
        }

    formatted_reports = [format_report(report) for report in paginated_reports]

    # Calculate pane counts
    pane_counts = defaultdict(lambda: defaultdict(lambda: {"total": 0, "count": 0}))
    filtered_ids = {report["id"] for report in filtered_reports}

    for report in all_reports:
        for field in columns[1:]:  # Skip date field
            value = report.get(field, "N/A")

            # Ensure value is hashable (convert dicts or lists to strings if necessary)
            if isinstance(value, (dict, list)):
                value = str(value)

            pane_counts[field][value]["total"] += 1
            if report["id"] in filtered_ids:
                pane_counts[field][value]["count"] += 1

    # Prepare SearchPanes options
    base_flags_url = url_for("static", filename="img/flags")
    search_panes_options = {}
    for field, values in pane_counts.items():
        if field == "country":
            search_panes_options["country"] = []
            for code, counts in values.items():
                country_code = code.lower()
                country_name = COUNTRIES_DATA_NAMES.get(country_code, "N/A")
                search_panes_options["country"].append(
                    {
                        "label": f"""<img src="{base_flags_url}/{'zz' if code == 'local' else country_code}.svg" class="border border-1 p-0 me-1" height="17" />&nbsp;－&nbsp;{'N/A' if code == 'local' else country_name}""",
                        "value": code,
                        "total": counts["total"],
                        "count": counts["count"],
                    }
                )
        elif field == "server_name":
            search_panes_options["server_name"] = []
            for name, counts in values.items():
                display_name = "default server" if name == "_" else name
                search_panes_options["server_name"].append(
                    {
                        "label": display_name,
                        "value": name,
                        "total": counts["total"],
                        "count": counts["count"],
                    }
                )
        else:
            search_panes_options[field] = [
                {
                    "label": value,
                    "value": value,
                    "total": counts["total"],
                    "count": counts["count"],
                }
                for value, counts in values.items()
            ]

    # Response
    return jsonify(
        {
            "draw": draw,
            "recordsTotal": len(all_reports),
            "recordsFiltered": len(filtered_reports),
            "data": formatted_reports,
            "searchPanes": {"options": search_panes_options},
        }
    )
