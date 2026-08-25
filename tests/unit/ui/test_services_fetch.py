"""`/services/fetch` — the server side of the services table.

Perf Lot D measured what the old page cost: all 501 rows rendered into the HTML, 868 KB of a
1089 KB document, 10 711 DOM nodes, and 260 ms of DataTables initialisation to display ten of
them. Compression hides that on the wire — the rows are near-identical, so the page gzips to
31 KB — but not on the main thread. This endpoint is the fix for the main-thread half.

Moving a table server-side quietly moves three other things with it, and each is a way to ship a
table that looks fine and lies:

- **the search** stops being a client-side scan of rendered cells and becomes a filter here;
- **the SearchPanes counts** stop being derived from the cells in the document — there are none
  left — and have to be computed over the whole set, not over the page being shown;
- **the exports** stop seeing every row, because a `serverSide` table only holds its current page.

The route body needs a running app, so what is exercised here is the part that carries the risk:
the pure filter/sort/pane functions the endpoint and the exports both call.
"""

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "services.py"


@pytest.fixture(scope="module")
def services_route():
    """Load `services.py` without booting container-only `app.dependencies` state."""
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.CORE_PLUGINS_PATH = Path("/nonexistent")
    dependencies.DATA = {}

    # `app.routes.utils` imports qrcode at module scope for the TOTP pages; it is not in the unit
    # venv and has nothing to do with this table.
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()

    module_name = "app.routes._services_fetch_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module


def _service(name, **overrides):
    """An API service payload, with the fields the table reads."""
    service = {
        "id": name,
        "is_draft": False,
        "method": "ui",
        "security_mode": "block",
        "template": "",
        "creation_date": datetime.now(timezone.utc).isoformat(),
        "last_update": datetime.now(timezone.utc).isoformat(),
    }
    service.update(overrides)
    return service


def _aged(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# --------------------------------------------------------------------------------------
# The row payload
# --------------------------------------------------------------------------------------
def test_a_row_carries_facts_rather_than_markup(services_route):
    """The point of the move: a row on the wire is a handful of fields, and `services.js` renders
    the columns. Put markup back in here and the 868 KB comes back with it."""
    rows = services_route._service_rows([_service("a.example.com", is_draft=True)])

    assert rows == [
        {
            "name": "a.example.com",
            "type": "draft",
            "method": "ui",
            "security_mode": "block",
            "template": "",
            "creation_date": rows[0]["creation_date"],
            "last_update": rows[0]["last_update"],
            "deletable": rows[0]["deletable"],
            "link_port": "",
        }
    ]
    for value in rows[0].values():
        assert "<" not in str(value), "a row must not carry markup"


def test_a_service_on_its_own_port_ships_it_so_the_link_can_carry_it(services_route):
    """``HTTPS_PORT`` is multisite since Lot B: a service can listen somewhere other than the port
    the fleet publishes, and the name alone is then not a reachable URL. The API answers
    ``link_port`` (empty for every service that did not move, because the RENDERED port is not the
    published one -- the images publish ``443:8443``), and `services.js` appends it."""
    assert services_route._service_rows([_service("a.example.com", link_port="9443")])[0]["link_port"] == "9443"
    assert services_route._service_rows([_service("a.example.com")])[0]["link_port"] == ""


def test_a_timestamp_leaves_with_an_offset_on_it(services_route):
    """The API answers naive UTC, and `new Date("2026-08-19T06:00:00")` in a browser reads a
    string with no offset as *local* time. Ship it raw and every date on the page moves by the
    viewer's offset — silently, and only for viewers who are not on UTC.

    The template used to fix this with the `to_iso` filter. The rows are JSON now, so it has to
    happen here instead."""
    rows = services_route._service_rows([_service("a.example.com", creation_date="2026-08-19T06:00:00")])

    moment = datetime.fromisoformat(rows[0]["creation_date"])
    assert moment.tzinfo is not None, "a browser would read this as local time"
    assert moment == datetime(2026, 8, 19, 6, 0, tzinfo=timezone.utc), "the instant itself must not move"


def test_an_unreadable_timestamp_empties_the_cell_rather_than_raising(services_route):
    """One malformed date in one service must not take the whole table down with it."""
    rows = services_route._service_rows([_service("a.example.com", creation_date="not a date", last_update=None)])

    assert rows[0]["creation_date"] == ""
    assert rows[0]["last_update"] == ""


def test_a_service_with_no_security_mode_defaults_to_block(services_route):
    """`block` is the product default. Rendering an empty cell would read as "no protection"."""
    rows = services_route._service_rows([_service("a.example.com", security_mode=None)])

    assert rows[0]["security_mode"] == "block"


# --------------------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------------------
def _filter(module, rows, **kwargs):
    return module._filter_and_sort_services(rows, kwargs.get("search", ""), kwargs.get("panes", {}), kwargs.get("order", 0), kwargs.get("direction", "asc"))


def test_the_search_matches_any_column_the_table_shows(services_route):
    """It replaces a client-side scan over rendered cells, so it has to cover the same ground —
    a user who searched for a method or a template name before must still find it."""
    rows = services_route._service_rows(
        [
            _service("alpha.example.com", method="scheduler"),
            _service("beta.example.com", template="high"),
        ]
    )

    assert [row["name"] for row in _filter(services_route, rows, search="scheduler")] == ["alpha.example.com"]
    assert [row["name"] for row in _filter(services_route, rows, search="high")] == ["beta.example.com"]
    assert [row["name"] for row in _filter(services_route, rows, search="example.com")] == ["alpha.example.com", "beta.example.com"]


def test_the_search_is_case_insensitive(services_route):
    rows = services_route._service_rows([_service("Alpha.Example.COM")])

    assert len(_filter(services_route, rows, search="alpha.example")) == 1


def test_a_pane_selection_filters_on_the_stored_value(services_route):
    """The client-side panes matched `data-value="draft"` in the rendered cell. There is no cell
    now, so the pane sends the value itself and it has to mean the same thing."""
    rows = services_route._service_rows([_service("a.example.com", is_draft=True), _service("b.example.com")])

    assert [row["name"] for row in _filter(services_route, rows, panes={"type": ["draft"]})] == ["a.example.com"]
    assert [row["name"] for row in _filter(services_route, rows, panes={"type": ["online"]})] == ["b.example.com"]


def test_no_template_is_a_selectable_state_not_an_absence(services_route):
    """ "No template" is a real answer a user filters by, and it is stored as an empty string.
    Left as-is it would be unselectable — the pane would offer a value nothing matches."""
    rows = services_route._service_rows([_service("a.example.com"), _service("b.example.com", template="high")])

    assert [row["name"] for row in _filter(services_route, rows, panes={"template": ["none"]})] == ["a.example.com"]
    assert [row["name"] for row in _filter(services_route, rows, panes={"template": ["high"]})] == ["b.example.com"]


def test_two_panes_narrow_each_other(services_route):
    rows = services_route._service_rows(
        [
            _service("a.example.com", is_draft=True, security_mode="detect"),
            _service("b.example.com", is_draft=True),
            _service("c.example.com", security_mode="detect"),
        ]
    )

    selected = _filter(services_route, rows, panes={"type": ["draft"], "security_mode": ["detect"]})

    assert [row["name"] for row in selected] == ["a.example.com"]


def test_a_date_pane_buckets_by_age(services_route):
    rows = services_route._service_rows(
        [
            _service("fresh.example.com", creation_date=_aged(0)),
            _service("week.example.com", creation_date=_aged(3)),
            _service("ancient.example.com", creation_date=_aged(400)),
        ]
    )

    assert [row["name"] for row in _filter(services_route, rows, panes={"creation_date": ["last_24h"]})] == ["fresh.example.com"]
    assert {row["name"] for row in _filter(services_route, rows, panes={"creation_date": ["last_7d"]})} == {"fresh.example.com", "week.example.com"}
    assert [row["name"] for row in _filter(services_route, rows, panes={"creation_date": ["older_30d"]})] == ["ancient.example.com"]


def test_an_unparseable_timestamp_is_excluded_rather_than_fatal(services_route):
    """One malformed date must not take the whole table down with a 500."""
    rows = services_route._service_rows([_service("a.example.com", creation_date="not a date"), _service("b.example.com", creation_date=None)])

    assert _filter(services_route, rows, panes={"creation_date": ["last_24h"]}) == []


# --------------------------------------------------------------------------------------
# Sorting
# --------------------------------------------------------------------------------------
def test_sorting_uses_the_column_the_table_asked_for(services_route):
    """DataTables sends the *visual* column index and the endpoint shifts it by the two leading
    non-data columns. Get that offset wrong and every sort silently orders by the wrong field."""
    rows = services_route._service_rows(
        [
            _service("b.example.com", method="scheduler"),
            _service("a.example.com", method="ui"),
        ]
    )

    by_name = services_route._filter_and_sort_services(rows, "", {}, 0, "asc")
    by_method = services_route._filter_and_sort_services(rows, "", {}, 2, "asc")

    assert [row["name"] for row in by_name] == ["a.example.com", "b.example.com"]
    assert [row["method"] for row in by_method] == ["scheduler", "ui"]


def test_sorting_is_case_insensitive_on_names(services_route):
    """Otherwise every capitalised server name sorts ahead of every lowercase one."""
    rows = services_route._service_rows([_service("beta.example.com"), _service("Alpha.example.com")])

    assert [row["name"] for row in services_route._filter_and_sort_services(rows, "", {}, 0, "asc")] == ["Alpha.example.com", "beta.example.com"]


def test_an_out_of_range_sort_column_falls_back_instead_of_raising(services_route):
    """The index arrives from the browser; a stale saved table state can name a column that no
    longer exists."""
    rows = services_route._service_rows([_service("a.example.com")])

    assert services_route._filter_and_sort_services(rows, "", {}, 99, "asc")


# --------------------------------------------------------------------------------------
# SearchPanes counts
# --------------------------------------------------------------------------------------
def test_pane_totals_count_every_service_not_just_the_page(services_route):
    """This is the failure the move invites: counts derived from the rows in the document would
    now describe ten services and claim to describe all of them."""
    rows = services_route._service_rows([_service(f"s{i}.example.com", is_draft=i < 7) for i in range(10)])
    filtered = _filter(services_route, rows, panes={"type": ["draft"]})

    options = services_route._service_pane_options(rows, filtered)
    by_value = {option["value"]: option for option in options["type"]}

    assert by_value["draft"]["total"] == 7
    assert by_value["online"]["total"] == 3
    assert by_value["draft"]["count"] == 7, "the selected pane still counts its own rows"
    assert by_value["online"]["count"] == 0, "and the unselected one drops to zero"


def test_every_pane_the_table_shows_gets_options(services_route):
    """Six panes are configured in `services.js`. A missing key renders an empty pane, which reads
    as "no services have a method" rather than as a bug."""
    rows = services_route._service_rows([_service("a.example.com")])

    options = services_route._service_pane_options(rows, rows)

    assert set(options) == {"type", "method", "security_mode", "template", "creation_date", "last_update"}
    assert all(options[pane] for pane in options), f"empty pane: {[pane for pane in options if not options[pane]]}"


def test_a_pane_label_escapes_what_came_from_the_api(services_route):
    """Method and template names reach the label as HTML. They are not free-form today, but the
    pane is rendered as markup and this is the boundary."""
    rows = services_route._service_rows([_service("a.example.com", method="<img src=x onerror=alert(1)>")])

    labels = [option["label"] for option in services_route._service_pane_options(rows, rows)["method"]]

    assert "<img" not in " ".join(labels)
    assert "&lt;img" in " ".join(labels)


# --------------------------------------------------------------------------------------
# The endpoint itself
# --------------------------------------------------------------------------------------
@pytest.fixture
def call_fetch(services_route):
    """Invoke `services_fetch` past its `@login_required` / `@cors_required` wrappers."""
    from flask import Flask

    app = Flask(__name__)
    app.secret_key = "test"

    def call(services_list, form=None):
        services_route.API_CLIENT.get_services.return_value = services_list
        with app.test_request_context("/services/fetch", method="POST", data=form or {}):
            response = services_fetch_unwrapped(services_route)()
            return response.get_json()

    return call


def services_fetch_unwrapped(module):
    handler = module.services_fetch
    while hasattr(handler, "__wrapped__"):
        handler = handler.__wrapped__
    return handler


def test_the_endpoint_answers_the_shape_datatables_expects(call_fetch):
    """`draw` echoed, both counts present, `data` a list. Miss one and the table stays on its
    loading spinner with nothing in the console."""
    payload = call_fetch([_service("a.example.com"), _service("b.example.com")], {"draw": "7", "start": "0", "length": "10"})

    assert payload["draw"] == 7
    assert payload["recordsTotal"] == 2
    assert payload["recordsFiltered"] == 2
    assert [row["name"] for row in payload["data"]] == ["a.example.com", "b.example.com"]
    assert "searchPanes" in payload


def test_the_endpoint_shifts_the_column_index_past_the_two_control_columns(call_fetch):
    """DataTables sends the *visual* index, and the services table has two non-data columns in
    front (details-control, select). Drop the shift and asking to sort by name sorts by something
    else — with the right number of rows, in the wrong order, and no error anywhere.

    Column 2 is `name`, column 4 is `method`."""
    services = [_service("b.example.com", method="scheduler"), _service("a.example.com", method="ui")]

    by_name = call_fetch(services, {"order[0][column]": "2", "order[0][dir]": "asc", "length": "10"})
    by_method = call_fetch(services, {"order[0][column]": "4", "order[0][dir]": "asc", "length": "10"})

    assert [row["name"] for row in by_name["data"]] == ["a.example.com", "b.example.com"]
    assert [row["method"] for row in by_method["data"]] == ["scheduler", "ui"]


def test_the_endpoint_paginates(call_fetch):
    services = [_service(f"s{index}.example.com") for index in range(25)]

    page = call_fetch(services, {"start": "10", "length": "5"})
    expected = sorted(service["id"] for service in services)[10:15]

    assert len(page["data"]) == 5
    assert page["recordsTotal"] == 25
    assert [row["name"] for row in page["data"]] == expected


def test_a_length_of_minus_one_means_every_row(call_fetch):
    """DataTables' "All" page length. Treated as a slice bound it would return nothing."""
    payload = call_fetch([_service(f"s{index}.example.com") for index in range(12)], {"length": "-1"})

    assert len(payload["data"]) == 12


def test_an_api_failure_answers_an_empty_table_rather_than_a_500(call_fetch, services_route):
    """The table polls this endpoint. A 500 leaves the page spinning with no message; an empty
    result at least renders the table's own "no services" state."""
    services_route.API_CLIENT.get_services.side_effect = Exception("API down")
    try:
        from flask import Flask

        app = Flask(__name__)
        app.secret_key = "test"
        with app.test_request_context("/services/fetch", method="POST", data={}):
            payload = services_fetch_unwrapped(services_route)().get_json()
    finally:
        services_route.API_CLIENT.get_services.side_effect = None

    assert payload["recordsTotal"] == 0
    assert payload["data"] == []


# --------------------------------------------------------------------------------------
# The exports
# --------------------------------------------------------------------------------------
@pytest.fixture
def export_rows(services_route):
    """`_services_export_rows()` under a request context carrying the given query string."""
    from flask import Flask

    app = Flask(__name__)
    app.secret_key = "test"

    def call(services_list, query=""):
        services_route.API_CLIENT.get_services.return_value = services_list
        with app.test_request_context(f"/services/export/csv?{query}"):
            return services_route._services_export_rows()

    return call


def test_the_export_writes_every_row_not_the_page_on_screen(export_rows):
    """The defect this endpoint exists to prevent. DataTables' own export buttons write what the
    table holds, and a `serverSide` table holds one page — so they would have produced a ten-row
    file with no error and no sign that 491 services were missing."""
    rows = export_rows([_service(f"s{index}.example.com") for index in range(501)])

    assert len(rows) == 501


def test_the_export_honours_the_filter_that_is_on_screen(export_rows):
    """The other half: exporting *everything* when the user has filtered down to drafts is just as
    wrong as exporting one page, only in the opposite direction."""
    services = [_service("a.example.com", is_draft=True), _service("b.example.com"), _service("c.example.com", is_draft=True)]

    rows = export_rows(services, "searchPanes[type][0]=draft")

    assert [row["name"] for row in rows] == ["a.example.com", "c.example.com"]


def test_the_export_honours_the_search_box(export_rows):
    services = [_service("alpha.example.com"), _service("beta.example.com")]

    rows = export_rows(services, "search=alpha")

    assert [row["name"] for row in rows] == ["alpha.example.com"]


def test_the_export_orders_by_name_rather_than_by_a_column_index(export_rows):
    """The fetch endpoint receives DataTables' numeric column index; the export receives a field
    name, because it is a plain link a user can also type. An unknown name falls back rather than
    raising."""
    services = [_service("b.example.com", method="scheduler"), _service("a.example.com", method="ui")]

    by_method = export_rows(services, "order_column=method&order_dir=asc")
    nonsense = export_rows(services, "order_column=not_a_column")

    assert [row["method"] for row in by_method] == ["scheduler", "ui"]
    assert [row["name"] for row in nonsense] == ["a.example.com", "b.example.com"]


def test_an_absent_template_exports_as_a_word_rather_than_a_blank(export_rows):
    """The table shows a "No template" badge. A blank spreadsheet cell reads as missing data."""
    rows = export_rows([_service("a.example.com")])

    assert rows[0]["template"] == "none"


def test_a_malformed_timestamp_exports_as_na_rather_than_raising(export_rows):
    """One bad date must not take the whole export down."""
    rows = export_rows([_service("a.example.com", creation_date="not a date", last_update=None)])

    assert rows[0]["creation_date"] == "N/A"
    assert rows[0]["last_update"] == "N/A"


def test_a_service_name_cannot_smuggle_a_formula_into_the_csv(services_route):
    """Server names are user-controlled, and a cell starting with `=` is a formula to Excel and
    LibreOffice (CWE-1236). `csv_writer` is the escaping wrapper the other exports use; plain
    `csv.writer` here would ship a spreadsheet that executes on open."""
    from flask import Flask

    app = Flask(__name__)
    app.secret_key = "test"
    services_route.API_CLIENT.get_services.return_value = [_service("=cmd|'/c calc'!A1")]

    handler = services_route.services_export_csv
    while hasattr(handler, "__wrapped__"):
        handler = handler.__wrapped__

    with app.test_request_context("/services/export/csv"):
        body = handler().get_data(as_text=True)

    payload = [line for line in body.splitlines() if "calc" in line]
    assert payload, "the row is missing from the export"
    assert not payload[0].lstrip('"').startswith("="), f"formula reached the file unescaped: {payload[0]}"
