"""Size controls for the real shared-dict metrics query; no reporter content."""

import pytest
from _lua_core_helpers import LUA
from test_metrics_phases_coverage_lua import run

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


@pytest.mark.parametrize("size", [49999, 50000, 60570, 65535, 65536])
@pytest.mark.parametrize("status", [200, 399, 403, 444, 500])
def test_shared_dict_large_reports_keep_matching_rows_and_facet_counts(size, status):
    out = run(
        """
local row = {id = 'large', date = 42, status = STATUS, ip = '192.0.2.10', data = {matched_vars = {string.rep('x', SIZE)}}}
VALUES.requests_0 = json.encode({row})
ARGS = {search_panes = 'ip:192.0.2.10'}
local page = self:api_requests_query().message
ARGS.count_only = 'true'
emit({page = page, counts = self:api_requests_query().message})
""",
        SIZE=size,
        STATUS=status,
    )
    page = out["page"]
    assert out["counts"] == {"total": 1, "filtered": 1}
    assert (page["total"], page["filtered"], len(page["data"])) == (1, 1, 1)
    assert page["pane_counts"]["ip"] == {"192.0.2.10": {"total": 1, "count": 1}}
    assert page["data"][0]["data"]["matched_vars"] == ["x" * size]
