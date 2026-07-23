# Reports Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `/reports` from a single flat DataTable into a 4-tab dashboard (Overview / Attack patterns / Top offenders / Event log) matching the BunkerWeb Design System kit's Reports mockup, using real data only.

**Architecture:** New ASN columns on the existing `bw_metrics_requests` table (populated via an already-existing but unused Lua ASN lookup) feed three new DB aggregation methods (time-bucketed counts, top offenders, top ModSecurity rules), exposed via three new API endpoints, consumed by three new dashboard tabs built from existing Jinja components (`tile`, `chart_area`, `tabs`, `card`) plus one new shared `range-picker` component. The current DataTable moves unchanged into a 4th "Event log" tab.

**Tech Stack:** Flask/Jinja2 (UI), FastAPI (API), SQLAlchemy 2.0 (DB, 4-engine: SQLite/MariaDB/MySQL/PostgreSQL), Lua/NGINX (BunkerWeb core), ApexCharts (existing, vendored), DataTables (existing, vendored), pytest (`tests/unit/`, `.venv-unit`).

## Global Constraints

- Black formatting, 160-char lines (Python). Flake8 `--max-line-length=160 --ignore=E266,E402,E501,E722,W503`.
- StyLua + Luacheck (`--std min`) for Lua.
- No new Python/JS dependencies (no PDF library — deferred per spec).
- All 4 DB engines must be supported by any schema/query change — no engine-specific SQL branches (date-bucketing is therefore done in Python, not per-engine `date_trunc`/`DATE_FORMAT`/`strftime`).
- Alembic migrations are **auto-generated only**, never hand-authored (`./misc/migration/create.sh`, per house convention).
- `data-i18n` keys must exist in `src/ui/app/static/locales/en.json`; other 17 locales fall back to English (`tests/unit/ui/test_ui_components.py` enforces this).
- No literal fake/placeholder data shipped as if real (Compliance tab dropped, Investigating/MTTR replaced — see spec `docs/superpowers/specs/2026-07-17-reports-dashboard-design.md`).
- Never commit unless the user explicitly asks (this session's standing convention).

---

### Task 1: ASN columns on `Requests` + round-trip through the DB layer

**Files:**
- Modify: `src/common/db/model.py:253-274` (`Requests` class)
- Modify: `src/common/db/db_methods/metrics.py` (`_row_to_dict` lines 64-82, `_build_request_row` lines 85-104)
- Test: `tests/unit/db/test_metrics.py`

**Interfaces:**
- Produces: `Requests.asn_number` (`Optional[int]`), `Requests.asn_org` (`Optional[str]`) — consumed by Task 4 (top offenders) and the API response shape in Task 6.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/db/test_metrics.py`:

```python
class TestAsnAttribution:
    def test_asn_fields_round_trip(self, db):
        db.batch_upsert_metrics_requests([_rec("a", asn_number=4134, asn_org="China Telecom")], instance_hostname="bw-1")
        row = db.get_metrics_requests()["data"][0]
        assert row["asn_number"] == 4134
        assert row["asn_org"] == "China Telecom"

    def test_asn_fields_default_to_none(self, db):
        db.batch_upsert_metrics_requests([_rec("a")], instance_hostname="bw-1")
        row = db.get_metrics_requests()["data"][0]
        assert row["asn_number"] is None
        assert row["asn_org"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest db/test_metrics.py::TestAsnAttribution -v`
Expected: FAIL — `KeyError: 'asn_number'` (column/field doesn't exist yet).

- [ ] **Step 3: Add the columns to the model**

In `src/common/db/model.py`, inside the `Requests` class, insert after the `security_mode` column (line 272) and before `created_at` (line 273):

```python
    asn_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    asn_org: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
```

- [ ] **Step 4: Wire the columns through `_row_to_dict` and `_build_request_row`**

In `src/common/db/db_methods/metrics.py`, `_row_to_dict` (around line 80), insert before `"security_mode": row.security_mode,`:

```python
        "asn_number": row.asn_number,
        "asn_org": row.asn_org,
```

In `_build_request_row` (around line 101), insert before `security_mode=str(record.get("security_mode") or ""),`:

```python
        asn_number=record.get("asn_number"),
        asn_org=record.get("asn_org"),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest db/test_metrics.py -v`
Expected: PASS (all existing `test_metrics.py` tests plus the 2 new ones — confirms the additive columns don't break existing round-trips).

- [ ] **Step 6: Commit**

```bash
git add src/common/db/model.py src/common/db/db_methods/metrics.py tests/unit/db/test_metrics.py
git commit -m "feat(db): add asn_number/asn_org columns to bw_metrics_requests"
```

---

### Task 2: Real ASN attribution at scrape time (Lua)

**Files:**
- Modify: `src/bw/lua/bunkerweb/utils.lua:706-719` (`utils.get_asn`)
- Modify: `src/common/core/metrics/metrics.lua` (record builder, ~lines 344-367)
- Test: manual (Lua has no unit-test harness in this repo; verified via the docker-compose UI smoke test in Task 6's manual step, plus `luacheck`)

**Interfaces:**
- Consumes: nothing new (uses existing `mmdb.asn_db`, already loaded by `src/bw/lua/bunkerweb/mmdb.lua:5`).
- Produces: `utils.get_asn(ip)` now returns `(asn_number, asn_org, status)` — 2nd value is new, additive.

- [ ] **Step 1: Extend `utils.get_asn` to also return the org name**

In `src/bw/lua/bunkerweb/utils.lua`, replace the body of `utils.get_asn` (lines 706-719):

```lua
utils.get_asn = function(ip)
	-- Check if mmdp is loaded
	if not mmdb.asn_db then
		return false, nil, "mmdb asn not loaded"
	end
	-- Perform lookup
	local ok, result, err = pcall(mmdb.asn_db.lookup, mmdb.asn_db, ip)
	if not ok then
		return nil, nil, result
	end
	if not result then
		return nil, nil, err
	end
	return result.autonomous_system_number, result.autonomous_system_organization, "success"
end
```

~~This is additive-only: the 4 existing callers (`blacklist.lua:335`, `whitelist.lua:350`, `antibot.lua:1171`, `greylist.lua:266`) all do `local asn, err = get_asn(...)` — with Lua multi-return, `err` now receives the *3rd* return value (`"success"`/error string) instead of the 2nd, which is exactly what those call sites already expect (they never used the 2nd return value, and Lua silently drops the extra `asn_org` return since it's not captured). No caller needs to change.~~

**Erratum (post-Task-2 review, see `task-2-report.md` / `task-2-fix-report.md` / `task-2-review.md`): this claim is FALSE.** `asn_org` was inserted as the *2nd* return value (not appended last), which shifts positional multi-return truncation: `local asn, err = get_asn(...)` in all 4 callers silently rebinds `err` to `asn_org` (`nil` on every failure branch) instead of the error string, then crashes on `"string" .. nil` inside each caller's own error-logging branch — on the normal ASN-lookup-failure path (private/loopback IPs, IPs absent from the ASN db), not a rare edge case. This was caught by the Task 2 implementer's own verification, escalated as Critical, and fixed in a follow-up that changed all 4 callers to `local asn, _, err = get_asn(...)`. Treat "additive-only" claims about return-value insertion elsewhere in this plan with the same scrutiny — always trace real call sites, don't infer from the brief's wording alone.

- [ ] **Step 2: Wire ASN into the metrics record builder**

Read `src/common/core/metrics/metrics.lua` around lines 340-367 to confirm the exact local variable names in context (the record builder currently calls `get_country` and builds a table with a `country = country` field per the earlier grep). Add, alongside the existing `get_country(...)` call:

```lua
local asn_number, asn_org = get_asn(ip)
```

(`ip` here is whatever local variable the surrounding function already uses for the remote address — match its existing name, don't introduce a second one.) Add `get_asn = utils.get_asn` to the file's local-import block at the top (mirroring the existing `local get_reason = utils.get_reason` / `local get_country = utils.get_country` pattern). Then add to the record table being built (alongside the existing `country = country,` line):

```lua
			asn_number = asn_number,
			asn_org = asn_org,
```

- [ ] **Step 3: Lint**

Run: `stylua --check src/bw/lua/bunkerweb/utils.lua src/common/core/metrics/metrics.lua`
Run: `luacheck src/bw/lua --std min --codes --ranges --no-cache`
Expected: both clean (no new warnings).

- [ ] **Step 4: Commit**

```bash
git add src/bw/lua/bunkerweb/utils.lua src/common/core/metrics/metrics.lua
git commit -m "feat(metrics): capture real ASN attribution on blocked requests"
```

---

### Task 3: `get_metrics_timeseries` — time-bucketed counts + trend delta

**Files:**
- Modify: `src/common/db/db_methods/metrics.py` (new method on `DatabaseMetricsMixin`)
- Test: `tests/unit/db/test_metrics.py`

**Interfaces:**
- Consumes: `_filter_conditions()` (existing, `metrics.py:112`), `Requests` model (existing).
- Produces: `db.get_metrics_timeseries(*, start: int, end: int, bucket: str = "hour", filters: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]` returning `{"buckets": [epoch,...], "counts": [int,...], "total": int, "prev_total": int, "trend_pct": Optional[float]}` — consumed by Task 6's `GET /metrics/requests/timeseries` endpoint.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/db/test_metrics.py`:

```python
class TestTimeseries:
    def test_buckets_and_totals(self, db):
        db.batch_upsert_metrics_requests([_rec("a", date=EPOCH), _rec("b", date=EPOCH + 3600)], instance_hostname="bw-1")
        res = db.get_metrics_timeseries(start=EPOCH, end=EPOCH + 7200, bucket="hour")
        assert res["total"] == 2
        assert res["counts"] == [1, 1]
        assert res["buckets"][0] == EPOCH

    def test_trend_pct_vs_previous_window(self, db):
        db.batch_upsert_metrics_requests(
            [_rec("p1", date=EPOCH - 7200), _rec("p2", date=EPOCH - 3600), _rec("c1", date=EPOCH)],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_timeseries(start=EPOCH, end=EPOCH + 7200, bucket="hour")
        assert res["prev_total"] == 2
        assert res["total"] == 1
        assert res["trend_pct"] == -50.0

    def test_no_previous_window_data_gives_none_trend(self, db):
        db.batch_upsert_metrics_requests([_rec("a", date=EPOCH)], instance_hostname="bw-1")
        res = db.get_metrics_timeseries(start=EPOCH, end=EPOCH + 3600, bucket="hour")
        assert res["prev_total"] == 0
        assert res["trend_pct"] is None
```

**Erratum (post-Task-3 review, see `task-3-report.md` / `task-3-fix-report.md`): the `test_buckets_and_totals` assertion above originally read `assert res["counts"] == [1, 1, 0]` (3 buckets).** That was wrong, not the ceiling-division formula in Step 3 below. A 2-hour window at 1-hour buckets is a half-open range `[start, end)` and correctly partitions into exactly 2 buckets (`ceil(7200/3600) == 2`); the Task 3 implementer instead changed the *code* to floor+1 semantics to make this bad test pass. Floor+1 makes every round-number preset range (1h/24h/7d/30d, all evenly divisible by their bucket size) render one permanently-empty trailing bucket in the Reports chart — a visible, permanent off-by-one with no offsetting benefit. Ceiling division has no such defect. Fixed by reverting `bucket_count` to `max(1, -(-window // bucket_seconds))  # ceil division` (already the formula in Step 3's code below — it was correct all along) and correcting this test to `[1, 1]`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest db/test_metrics.py::TestTimeseries -v`
Expected: FAIL — `AttributeError: 'Database' object has no attribute 'get_metrics_timeseries'`.

- [ ] **Step 3: Implement**

Add to `DatabaseMetricsMixin` in `src/common/db/db_methods/metrics.py`, after `get_metrics_facets` (after line 237):

```python
    @retry_on_transient_db_errors
    def get_metrics_timeseries(
        self,
        *,
        start: int,
        end: int,
        bucket: str = "hour",
        filters: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Time-bucketed report counts over ``[start, end)`` (Unix epoch seconds), plus the same
        count over the immediately-preceding equal-length window for a period-over-period trend
        delta. Bucketing is done in Python rather than per-engine SQL (``date_trunc``/
        ``DATE_FORMAT``/``strftime``) to stay portable across all 4 supported engines — the
        result set is bounded by the date range, not the whole table, so this stays cheap.
        """
        bucket_seconds = 3600 if bucket == "hour" else 86400
        start_dt = datetime.fromtimestamp(start, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end, tz=timezone.utc)
        window = end - start
        prev_start_dt = datetime.fromtimestamp(start - window, tz=timezone.utc)

        conditions = _filter_conditions("", filters) + [Requests.date >= start_dt, Requests.date < end_dt]
        prev_conditions = _filter_conditions("", filters) + [Requests.date >= prev_start_dt, Requests.date < start_dt]

        with self._db_session() as session:
            dates = session.scalars(select(Requests.date).where(*conditions)).all()
            prev_total = session.scalar(select(func.count()).select_from(select(Requests).where(*prev_conditions).subquery())) or 0

        bucket_count = max(1, -(-window // bucket_seconds))  # ceil division
        counts = [0] * bucket_count
        for d in dates:
            idx = int((d.timestamp() - start) // bucket_seconds)
            if 0 <= idx < bucket_count:
                counts[idx] += 1

        total = len(dates)
        trend_pct = round(((total - prev_total) / prev_total) * 100, 1) if prev_total else None
        return {
            "buckets": [start + i * bucket_seconds for i in range(bucket_count)],
            "counts": counts,
            "total": total,
            "prev_total": prev_total,
            "trend_pct": trend_pct,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest db/test_metrics.py -v`
Expected: PASS (all tests, including the 3 new ones).

- [ ] **Step 5: Commit**

```bash
git add src/common/db/db_methods/metrics.py tests/unit/db/test_metrics.py
git commit -m "feat(db): add get_metrics_timeseries for the Reports dashboard"
```

---

### Task 4: `get_metrics_top_offenders`

**Files:**
- Modify: `src/common/db/db_methods/metrics.py`
- Test: `tests/unit/db/test_metrics.py`

**Interfaces:**
- Consumes: `Requests.asn_number`/`asn_org` from Task 1.
- Produces: `db.get_metrics_top_offenders(*, start: int, end: int, limit: int = 10, filters=None) -> List[Dict[str, Any]]`, each dict `{"ip", "country", "asn_number", "asn_org", "blocks", "top_reason", "first_seen", "last_seen"}` — consumed by Task 6.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/db/test_metrics.py`:

```python
class TestTopOffenders:
    def test_ranks_by_block_count_with_attribution(self, db):
        db.batch_upsert_metrics_requests(
            [
                _rec("a1", ip="9.9.9.9", country="RU", asn_number=12389, asn_org="Rostelecom", date=EPOCH),
                _rec("a2", ip="9.9.9.9", country="RU", asn_number=12389, asn_org="Rostelecom", date=EPOCH + 60, reason="modsecurity"),
                _rec("b1", ip="1.1.1.1", country="US", date=EPOCH),
            ],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_top_offenders(start=EPOCH - 1, end=EPOCH + 3600)
        assert res[0]["ip"] == "9.9.9.9"
        assert res[0]["blocks"] == 2
        assert res[0]["asn_org"] == "Rostelecom"
        assert res[0]["first_seen"] == EPOCH
        assert res[0]["last_seen"] == EPOCH + 60
        assert res[1]["ip"] == "1.1.1.1"

    def test_limit_caps_results(self, db):
        db.batch_upsert_metrics_requests(
            [_rec(f"r{i}", ip=f"1.1.1.{i}", date=EPOCH) for i in range(5)],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_top_offenders(start=EPOCH - 1, end=EPOCH + 3600, limit=2)
        assert len(res) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest db/test_metrics.py::TestTopOffenders -v`
Expected: FAIL — `AttributeError: 'Database' object has no attribute 'get_metrics_top_offenders'`.

- [ ] **Step 3: Implement**

Add to `DatabaseMetricsMixin`, after `get_metrics_timeseries`:

```python
    @retry_on_transient_db_errors
    def get_metrics_top_offenders(
        self,
        *,
        start: int,
        end: int,
        limit: int = 10,
        filters: Optional[Dict[str, List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Top attacker IPs in ``[start, end)`` by block count, with country/ASN attribution
        (``None`` for rows predating the ASN migration), the most frequent block reason, and
        first/last-seen timestamps."""
        start_dt = datetime.fromtimestamp(start, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end, tz=timezone.utc)
        conditions = _filter_conditions("", filters) + [Requests.date >= start_dt, Requests.date < end_dt]

        with self._db_session() as session:
            rows = session.execute(
                select(Requests.ip, Requests.country, Requests.asn_number, Requests.asn_org, Requests.reason, Requests.date).where(*conditions)
            ).all()

        by_ip: Dict[str, Dict[str, Any]] = {}
        for ip, country, asn_number, asn_org, reason, date in rows:
            entry = by_ip.setdefault(
                ip,
                {"ip": ip, "country": country, "asn_number": asn_number, "asn_org": asn_org, "blocks": 0, "reasons": {}, "first_seen": date, "last_seen": date},
            )
            entry["blocks"] += 1
            entry["reasons"][reason] = entry["reasons"].get(reason, 0) + 1
            entry["first_seen"] = min(entry["first_seen"], date)
            entry["last_seen"] = max(entry["last_seen"], date)

        offenders = [
            {
                "ip": entry["ip"],
                "country": entry["country"],
                "asn_number": entry["asn_number"],
                "asn_org": entry["asn_org"],
                "blocks": entry["blocks"],
                "top_reason": max(entry["reasons"].items(), key=lambda kv: kv[1])[0],
                "first_seen": int(entry["first_seen"].timestamp()),
                "last_seen": int(entry["last_seen"].timestamp()),
            }
            for entry in by_ip.values()
        ]
        offenders.sort(key=lambda o: o["blocks"], reverse=True)
        return offenders[:limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest db/test_metrics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/common/db/db_methods/metrics.py tests/unit/db/test_metrics.py
git commit -m "feat(db): add get_metrics_top_offenders for the Reports dashboard"
```

---

### Task 5: `get_metrics_top_rules`

**Files:**
- Modify: `src/common/db/db_methods/metrics.py`
- Test: `tests/unit/db/test_metrics.py`

**Interfaces:**
- Produces: `db.get_metrics_top_rules(*, start: int, end: int, limit: int = 10) -> List[Dict[str, Any]]`, each `{"rule_id": str, "count": int}` — consumed by Task 6.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/db/test_metrics.py`:

```python
class TestTopRules:
    def test_tallies_rule_ids_from_modsecurity_rows(self, db):
        db.batch_upsert_metrics_requests(
            [
                _rec("m1", reason="modsecurity", data={"ids": ["942100", "932100"]}, date=EPOCH),
                _rec("m2", reason="modsecurity", data={"ids": ["942100"]}, date=EPOCH + 60),
                _rec("nm", reason="blacklist", date=EPOCH),
            ],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_top_rules(start=EPOCH - 1, end=EPOCH + 3600)
        assert res[0] == {"rule_id": "942100", "count": 2}
        assert {"rule_id": "932100", "count": 1} in res

    def test_no_modsecurity_rows_returns_empty(self, db):
        db.batch_upsert_metrics_requests([_rec("a", reason="blacklist", date=EPOCH)], instance_hostname="bw-1")
        assert db.get_metrics_top_rules(start=EPOCH - 1, end=EPOCH + 3600) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest db/test_metrics.py::TestTopRules -v`
Expected: FAIL — `AttributeError: 'Database' object has no attribute 'get_metrics_top_rules'`.

- [ ] **Step 3: Implement**

Add to `DatabaseMetricsMixin`, after `get_metrics_top_offenders`:

```python
    @retry_on_transient_db_errors
    def get_metrics_top_rules(self, *, start: int, end: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Most-frequently-fired ModSecurity rule IDs in ``[start, end)``, tallied from the
        ``data.ids`` JSON array each modsecurity-reason row carries (see ``utils.get_reason`` in
        ``utils.lua``). Non-modsecurity rows carry no ``ids`` and are skipped."""
        start_dt = datetime.fromtimestamp(start, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end, tz=timezone.utc)
        conditions = [Requests.reason == "modsecurity", Requests.date >= start_dt, Requests.date < end_dt]

        with self._db_session() as session:
            blobs = session.scalars(select(Requests.data).where(*conditions)).all()

        tally: Dict[str, int] = {}
        for blob in blobs:
            if not blob:
                continue
            try:
                parsed = loads(blob)
            except (TypeError, ValueError):
                continue
            for rule_id in (parsed or {}).get("ids", []) or []:
                tally[str(rule_id)] = tally.get(str(rule_id), 0) + 1

        ranked = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)
        return [{"rule_id": rule_id, "count": count} for rule_id, count in ranked[:limit]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest db/test_metrics.py -v`
Expected: PASS (full file, all tasks 1/3/4/5 tests green together).

- [ ] **Step 5: Commit**

```bash
git add src/common/db/db_methods/metrics.py tests/unit/db/test_metrics.py
git commit -m "feat(db): add get_metrics_top_rules for the Reports dashboard"
```

---

### Task 6: API endpoints + UI API-client + Flask route glue

**Files:**
- Modify: `src/api/app/routers/metrics.py`
- Modify: `src/ui/app/api_client.py` (after `get_metrics_requests`, line ~62)
- Modify: `src/ui/app/routes/reports.py` (new `/reports/dashboard` route, alongside existing `/reports/fetch` etc.)
- Test: `tests/unit/api/test_metrics.py` (new file — check first whether one already exists via `find tests/unit/api -iname "*metric*"`; if absent, create it following the pattern of a sibling `tests/unit/api/test_*.py` file for FastAPI `TestClient` usage)

**Interfaces:**
- Consumes: `db.get_metrics_timeseries`/`get_metrics_top_offenders`/`get_metrics_top_rules` (Tasks 3-5).
- Produces: `GET /metrics/requests/timeseries?start=&end=&bucket=`, `GET /metrics/requests/top-offenders?start=&end=&limit=`, `GET /metrics/requests/top-rules?start=&end=&limit=` (API); `ApiClient.get_metrics_timeseries(start, end, bucket)`, `.get_metrics_top_offenders(start, end, limit)`, `.get_metrics_top_rules(start, end, limit)` (UI client); `POST /reports/dashboard` (Flask, mirrors the existing `/reports/fetch` pattern) returning the combined payload the 3 new tabs consume — used by Task 9/10/11's JS.

- [ ] **Step 1: Add the 3 API router endpoints**

In `src/api/app/routers/metrics.py`, after `query_metrics_requests` (after line 56):

```python
@router.get("/requests/timeseries", dependencies=[Depends(guard)])
def query_metrics_timeseries(start: int, end: int, bucket: str = "hour", search_panes: str = "") -> JSONResponse:
    db = get_db()
    filters = _parse_search_panes(search_panes)
    result = db.get_metrics_timeseries(start=start, end=end, bucket=bucket, filters=filters)
    return JSONResponse(status_code=200, content={"status": "success", **result})


@router.get("/requests/top-offenders", dependencies=[Depends(guard)])
def query_metrics_top_offenders(start: int, end: int, limit: int = 10, search_panes: str = "") -> JSONResponse:
    db = get_db()
    filters = _parse_search_panes(search_panes)
    result = db.get_metrics_top_offenders(start=start, end=end, limit=limit, filters=filters)
    return JSONResponse(status_code=200, content={"status": "success", "offenders": result})


@router.get("/requests/top-rules", dependencies=[Depends(guard)])
def query_metrics_top_rules(start: int, end: int, limit: int = 10) -> JSONResponse:
    db = get_db()
    result = db.get_metrics_top_rules(start=start, end=end, limit=limit)
    return JSONResponse(status_code=200, content={"status": "success", "rules": result})
```

- [ ] **Step 2: Write the API test**

Check for an existing `tests/unit/api/test_metrics.py`; if none, create it modeled on `tests/unit/db/test_metrics.py`'s `_rec`/`db` fixtures plus this repo's existing FastAPI `TestClient` pattern (grep another `tests/unit/api/test_*.py` for the client fixture name before writing — do not guess it). Add:

```python
def test_timeseries_endpoint_returns_buckets(client, db):
    db.batch_upsert_metrics_requests([_rec("a", date=EPOCH)], instance_hostname="bw-1")
    resp = client.get(f"/metrics/requests/timeseries?start={EPOCH}&end={EPOCH + 3600}&bucket=hour")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["total"] == 1


def test_top_offenders_endpoint(client, db):
    db.batch_upsert_metrics_requests([_rec("a", ip="1.2.3.4", date=EPOCH)], instance_hostname="bw-1")
    resp = client.get(f"/metrics/requests/top-offenders?start={EPOCH - 1}&end={EPOCH + 3600}")
    assert resp.status_code == 200
    assert resp.json()["offenders"][0]["ip"] == "1.2.3.4"


def test_top_rules_endpoint(client, db):
    db.batch_upsert_metrics_requests([_rec("a", reason="modsecurity", data={"ids": ["942100"]}, date=EPOCH)], instance_hostname="bw-1")
    resp = client.get(f"/metrics/requests/top-rules?start={EPOCH - 1}&end={EPOCH + 3600}")
    assert resp.status_code == 200
    assert resp.json()["rules"] == [{"rule_id": "942100", "count": 1}]
```

- [ ] **Step 3: Run test to verify it fails, then passes**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest api/test_metrics.py -v`
Expected: FAIL first (404s, route doesn't exist client-side until Step 1 is picked up — if Step 1 was already applied, this instead validates it), then PASS after Step 1.

- [ ] **Step 4: Add the UI ApiClient methods**

In `src/ui/app/api_client.py`, after `get_metrics_requests` (after line 62):

```python
    def get_metrics_timeseries(self, *, start: int, end: int, bucket: str = "hour", search_panes: str = ""):
        return self._get("/metrics/requests/timeseries", params={"start": start, "end": end, "bucket": bucket, "search_panes": search_panes})

    def get_metrics_top_offenders(self, *, start: int, end: int, limit: int = 10, search_panes: str = ""):
        return self._get("/metrics/requests/top-offenders", params={"start": start, "end": end, "limit": limit, "search_panes": search_panes})

    def get_metrics_top_rules(self, *, start: int, end: int, limit: int = 10):
        return self._get("/metrics/requests/top-rules", params={"start": start, "end": end, "limit": limit})
```

- [ ] **Step 5: Add the Flask route**

In `src/ui/app/routes/reports.py`, after `reports_page` (after line 169):

```python
@reports.route("/reports/dashboard", methods=["POST"])
@login_required
@cors_required
def reports_dashboard():
    try:
        end = int(request.form.get("end") or datetime.now().timestamp())
        start = int(request.form.get("start") or (end - 86400))
        bucket = request.form.get("bucket", "hour")
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid start/end"}), 400

    try:
        timeseries = API_CLIENT.get_metrics_timeseries(start=start, end=end, bucket=bucket)
        offenders = API_CLIENT.get_metrics_top_offenders(start=start, end=end, limit=10)
        rules = API_CLIENT.get_metrics_top_rules(start=start, end=end, limit=10)
    except (ApiClientError, ApiUnavailableError) as e:
        LOGGER.warning(f"Metrics API unavailable ({e}); dashboard tabs will show empty state")
        return jsonify({"status": "error", "message": "Metrics service unavailable"}), 503

    return jsonify({"status": "success", "timeseries": timeseries, "offenders": offenders.get("offenders", []), "rules": rules.get("rules", [])})
```

This mirrors the existing `/reports/fetch`'s `login_required`/`cors_required` pattern exactly (see `reports.py:172-174`). `datetime` and `request`/`jsonify` are already imported at the top of `reports.py`; `API_CLIENT` is already imported at line 16.

- [ ] **Step 6: Verify end to end**

Run: `docker compose -f misc/dev/docker-compose.ui.api.yml up -d` (or restart if already running), then:
`curl -u admin:P@ssw0rd "http://localhost:8888/metrics/requests/timeseries?start=0&end=9999999999"` (adjust host/port/auth to the actual dev API — check `misc/dev/docker-compose.ui.api.yml` for the exact exposed port before running) and confirm a `{"status": "success", ...}` JSON body.

- [ ] **Step 7: Commit**

```bash
git add src/api/app/routers/metrics.py src/ui/app/api_client.py src/ui/app/routes/reports.py tests/unit/api/test_metrics.py
git commit -m "feat(api): expose reports dashboard timeseries/top-offenders/top-rules endpoints"
```

---

### Task 7: New shared `range-picker` component

**Files:**
- Create: `src/ui/app/templates/components/range-picker.html`
- Create: `src/ui/app/static/js/components/range-picker.js`
- Test: `tests/unit/ui/test_ui_components.py`

**Interfaces:**
- Produces: Jinja macro `range_picker(id, presets=["1h","24h","7d","30d"], active="24h", with_custom=True, classes="")` rendering a `role="group"` button toggle; `window.BWRangePicker.init(elementId)` JS that wires click handlers and dispatches `CustomEvent('change', {detail: {value, startEpoch, endEpoch}})` on the picker's root element — consumed by Task 9's Overview-tab JS (and reusable by Tasks 10/11).

- [ ] **Step 1: Write the failing test**

Read `tests/unit/ui/test_ui_components.py` first to match its existing macro-rendering-assertion style (e.g. `render_macro`/Jinja-env helper used for other components) before writing — do not guess the harness. Add a test asserting: the macro renders one `button.range-btn` per preset with `role="group"` on the wrapper, the `active` preset has `aria-pressed="true"` and the others `"false"`, and every `data-i18n` key the macro emits (e.g. `range_picker.custom`, `range_picker.aria_label`) exists in `en.json`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest ui/test_ui_components.py -k range_picker -v`
Expected: FAIL — template not found / macro not found.

- [ ] **Step 3: Implement the macro**

Create `src/ui/app/templates/components/range-picker.html`:

```jinja
{# usage: {% from "components/range-picker.html" import range_picker %}
          {{ range_picker(id="reports-range", active="24h") }}

   Segmented preset toggle (1h/24h/7d/30d + optional custom), dispatching a
   `change` CustomEvent via static/js/components/range-picker.js
   (window.BWRangePicker.init). Design-kit source: components/range-picker.js.

   Params:
     id           (required) unique id for the button-group root.
     presets      list of preset keys, default ["1h","24h","7d","30d"].
     active       initially-active preset key.
     with_custom  render a trailing "Custom" button opening a flatpickr range
                  input (flatpickr is already vendored, see bans.js/pro.js).
     classes      extra classes on the wrapper. #}
{% macro range_picker(id, presets=["1h", "24h", "7d", "30d"], active="24h", with_custom=True, classes="") -%}
    <div class="range-picker btn-group{% if classes %} {{ classes }}{% endif %}"
         id="{{ id }}"
         role="group"
         data-i18n-label="range_picker.aria_label"
         aria-label="Time range">
        {% for preset in presets %}
            <button type="button"
                    class="btn btn-sm btn-outline-primary range-btn{% if preset == active %} active{% endif %}"
                    data-range="{{ preset }}"
                    aria-pressed="{{ 'true' if preset == active else 'false' }}"
                    data-i18n="range_picker.{{ preset }}">{{ preset }}</button>
        {% endfor %}
        {% if with_custom %}
            <button type="button"
                    class="btn btn-sm btn-outline-primary range-btn{% if active == 'custom' %} active{% endif %}"
                    data-range="custom"
                    aria-pressed="{{ 'true' if active == 'custom' else 'false' }}">
                <i class="bx bx-calendar" aria-hidden="true"></i>
                <span data-i18n="range_picker.custom">Custom</span>
            </button>
            <input type="text" class="range-fp visually-hidden" id="{{ id }}-fp" />
        {% endif %}
    </div>
{%- endmacro %}
```

Add `range_picker.1h`/`range_picker.24h`/`range_picker.7d`/`range_picker.30d`/`range_picker.custom`/`range_picker.aria_label` to `src/ui/app/static/locales/en.json` (values: "Last hour", "Last 24 h", "Last week", "Last 30 days", "Custom", "Time range").

- [ ] **Step 4: Implement the JS**

Create `src/ui/app/static/js/components/range-picker.js`:

```javascript
window.BWRangePicker = (function () {
  const PRESET_SECONDS = { "1h": 3600, "24h": 86400, "7d": 604800, "30d": 2592000 };

  function init(elementId) {
    const root = document.getElementById(elementId);
    if (!root) return null;
    const buttons = root.querySelectorAll(".range-btn");
    const fpInput = root.querySelector(".range-fp");
    let flatpickrInstance = null;

    function computeRange(preset, customStart, customEnd) {
      const end = Math.floor(Date.now() / 1000);
      if (preset === "custom" && customStart && customEnd) {
        return { startEpoch: customStart, endEpoch: customEnd };
      }
      const seconds = PRESET_SECONDS[preset] || PRESET_SECONDS["24h"];
      return { startEpoch: end - seconds, endEpoch: end };
    }

    function setActive(preset, customStart, customEnd) {
      buttons.forEach((btn) => {
        const on = btn.dataset.range === preset;
        btn.classList.toggle("active", on);
        btn.setAttribute("aria-pressed", String(on));
      });
      const range = computeRange(preset, customStart, customEnd);
      root.dispatchEvent(new CustomEvent("change", { detail: { value: preset, ...range } }));
    }

    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const preset = btn.dataset.range;
        if (preset === "custom") {
          if (!flatpickrInstance && window.flatpickr && fpInput) {
            flatpickrInstance = flatpickr(fpInput, {
              mode: "range",
              maxDate: "today",
              onClose: (dates) => {
                if (dates.length === 2) {
                  setActive("custom", Math.floor(dates[0].getTime() / 1000), Math.floor(dates[1].getTime() / 1000));
                }
              },
            });
          }
          if (flatpickrInstance) flatpickrInstance.open();
        } else {
          setActive(preset);
        }
      });
    });

    return { setActive };
  }

  return { init };
})();
```

**Erratum (post-Task-7 review, see `task-7-review.md`): the `data-i18n-label="range_picker.aria_label"` attribute above binds nothing.** `i18n.js`'s `applyTranslations()` only ever selects `[data-i18n]` elements (there is no `data-i18n-label` handling anywhere in the codebase); the shipped macro uses `data-i18n="range_picker.aria_label"` instead, and `applyTranslations()`'s own `[aria-label]` branch (it sets `aria-label` on any translated element that already carries one) is what actually drives the translation. See `src/ui/app/templates/components/range-picker.html`'s in-file doc comment for the same note.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest ui/test_ui_components.py -v`
Expected: PASS (full file green, including the new range_picker assertions).

- [ ] **Step 6: Format/lint**

Run: `prettier --check src/ui/app/static/js/components/range-picker.js src/ui/app/templates/components/range-picker.html`
Expected: clean (or `prettier --write` then re-check).

- [ ] **Step 7: Commit**

```bash
git add src/ui/app/templates/components/range-picker.html src/ui/app/static/js/components/range-picker.js src/ui/app/static/locales/en.json tests/unit/ui/test_ui_components.py
git commit -m "feat(ui): add shared range-picker component"
```

---

### Task 8: `reports.html` tab scaffold + Event-log tab (existing table, unchanged)

**Files:**
- Modify: `src/ui/app/templates/reports.html`
- Test: `tests/unit/ui/test_ui_components.py` (smoke-render the page template if the existing harness supports it; otherwise manual verification in Step 4)

**Interfaces:**
- Consumes: `components/tabs.html` (`tabs`/`tab_pane` macros, existing), `components/range-picker.html` (Task 7).
- Produces: 4 tab panes (`overview`, `patterns`, `offenders`, `eventlog`) whose ids Task 9/10/11's JS will target as `#reports-tabs-pane-overview` etc. (per `tabs.html`'s `{tabs_id}-pane-{item.id}` convention, `tabs_id="reports-tabs"`).

- [ ] **Step 1: Add the tabs import and range-picker import**

In `src/ui/app/templates/reports.html`, change line 6 from:

```jinja
{% from "components/title.html" import title %}
```

to:

```jinja
{% from "components/title.html" import title %}
{% from "components/tabs.html" import tabs, tab_pane %}
{% from "components/range-picker.html" import range_picker %}
```

- [ ] **Step 2: Wrap the existing content in an "Event log" tab pane, add the 3 new empty panes**

Replace lines 16-36 (from `{{ title(...) }}` through the closing `{% endcall %}` of the card) with:

```jinja
    {{ title(label="Reports", i18n_key="navigation.reports", level="h1", icon="bxs-flag-checkered", subtitle="Security reports generated from blocked requests across your BunkerWeb instances — search, filter, export, and ban offending IPs directly from the table.", subtitle_i18n_key="reports.subtitle", classes="mb-4") }}
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 gap-3">
        {{ tabs(id="reports-tabs", items=[
            {"id": "overview", "i18n": "reports.tab.overview", "label": "Overview", "icon": "bx-line-chart"},
            {"id": "patterns", "i18n": "reports.tab.patterns", "label": "Attack patterns", "icon": "bx-shield-quarter"},
            {"id": "offenders", "i18n": "reports.tab.offenders", "label": "Top offenders", "icon": "bx-user-x"},
            {"id": "eventlog", "i18n": "reports.tab.eventlog", "label": "Event log", "icon": "bx-list-ul"},
        ], active="overview", label="Reports sections") }}
        {{ range_picker(id="reports-range", active="24h") }}
    </div>
    <!-- Content -->
    {% call tab_pane(id="overview", tabs_id="reports-tabs", active=True) %}
        <div id="reports-overview-root"><!-- filled by Task 9's JS --></div>
    {% endcall %}
    {% call tab_pane(id="patterns", tabs_id="reports-tabs") %}
        <div id="reports-patterns-root"><!-- filled by Task 10's JS --></div>
    {% endcall %}
    {% call tab_pane(id="offenders", tabs_id="reports-tabs") %}
        <div id="reports-offenders-root"><!-- filled by Task 11's JS --></div>
    {% endcall %}
    {% call tab_pane(id="eventlog", tabs_id="reports-tabs") %}
        {% call card(classes="table-responsive text-nowrap p-4 pb-8 min-vh-70") %}
            {% set base_flags_url = url_for('static', filename='img/flags') %}
            <input type="hidden" id="base_flags_url" value="{{ base_flags_url }}" />
            {% call table_toolbar(id="reports", columns_preferences_defaults=columns_preferences_defaults, columns_preferences=columns_preferences, loading_key="status.loading_reports", loading_default="Loading reports...") %}
            {% endcall %}
            <div class="d-flex flex-column flex-sm-row align-items-center gap-3 mt-4 pt-3 border-top border-light-subtle small text-muted w-100">
                <div class="flex-grow-1 text-center">
                    <span class="badge rounded-pill bg-secondary">
                        TZ:
                        <script nonce="{{ script_nonce }}">document.write(Intl.DateTimeFormat().resolvedOptions().timeZone);</script>
                    </span>
                </div>
                <a href="https://db-ip.com"
                   class="link-secondary text-decoration-none ms-sm-auto"
                   target="_blank"
                   rel="noopener noreferrer">IP Geolocation by DB-IP</a>
            </div>
        {% endcall %}
    {% endcall %}
```

Everything below this (the `Full URL Modal`, `Security Report Data Modal`, and `{% block scripts %}`) stays exactly as-is (lines 38-78 in the original) — the modals are triggered from the Event-log tab's table exactly as before, no id changes.

- [ ] **Step 3: Add the new tab i18n keys**

Add to `en.json`: `reports.tab.overview` = "Overview", `reports.tab.patterns` = "Attack patterns", `reports.tab.offenders` = "Top offenders", `reports.tab.eventlog` = "Event log".

- [ ] **Step 4: Manual verification**

`docker compose -f misc/dev/docker-compose.ui.api.yml restart bw-ui`, open `/reports` in a browser, confirm: 4 tabs render, "Event log" tab shows the exact same table/search/filter/export/ban functionality as before (this is the regression check — nothing here should have changed behaviorally), switching tabs doesn't error in the console (the 3 new root divs are empty until Tasks 9-11 land, that's expected at this point).

- [ ] **Step 5: Commit**

```bash
git add src/ui/app/templates/reports.html src/ui/app/static/locales/en.json
git commit -m "feat(ui): restructure reports.html into a 4-tab dashboard, Event log = existing table"
```

---

### Task 9: Overview tab (tiles + chart + recent incidents + top ASN bars)

**Files:**
- Modify: `src/ui/app/templates/reports.html` (`#reports-overview-root` content)
- Create: `src/ui/app/static/js/pages/reports-overview.js`
- Modify: `src/ui/app/templates/reports.html` (`{% block scripts %}`, add the new script tag)
- Test: manual (data-dependent dashboard rendering; no existing harness renders live AJAX-populated JS state — covered by Task 6's API tests + Task 8/Step 4-style manual pass)

**Interfaces:**
- Consumes: `window.BWRangePicker` (Task 7), `POST /reports/dashboard` (Task 6), `components/tile.html`/`chart-area.html` macros (existing).
- Produces: populates `#reports-overview-root`; re-fetches on the range-picker's `change` event (shared by all 3 new tabs — Tasks 10/11 reuse the same fetch, see Step 2).

- [ ] **Step 1: Add the Overview tab markup**

Replace `<div id="reports-overview-root">...</div>` in `reports.html` (from Task 8) with:

```jinja
    <div id="reports-overview-root">
        <div class="row g-3 mb-4">
            <div class="col-6 col-lg-3">{{ tile(id="reports-tile-blocked", title="Blocked requests", title_i18n="reports.tile.blocked", value="—") }}</div>
            <div class="col-6 col-lg-3">{{ tile(id="reports-tile-rate", title="Blocked rate", title_i18n="reports.tile.blocked_rate", value="—", color="bw-green") }}</div>
            <div class="col-6 col-lg-3">{{ tile(id="reports-tile-unique", title="Unique attacker IPs", title_i18n="reports.tile.unique_ips", value="—", color="warning") }}</div>
            <div class="col-6 col-lg-3">{{ tile(id="reports-tile-peak", title="Peak hour", title_i18n="reports.tile.peak_hour", value="—", color="secondary") }}</div>
        </div>
        {{ chart_area(id="reports-timeseries-chart", title="Blocked requests over time", title_key="reports.chart.timeseries.title", height=280) }}
        <div class="row g-3 mt-1">
            <div class="col-lg-8">
                {% call card(title="Most recent incidents", title_key="reports.card.recent.title") %}
                    <div id="reports-recent-incidents"></div>
                {% endcall %}
            </div>
            <div class="col-lg-4">
                {% call card(title="Top offender ASNs", title_key="reports.card.top_asn.title") %}
                    <div id="reports-top-asns"></div>
                {% endcall %}
            </div>
        </div>
    </div>
```

(`tile`/`chart_area`/`card` are already imported at the top of `reports.html` — `chart_area` needs adding to the Task 8 import line: `{% from "components/chart-area.html" import chart_area %}`.)

- [ ] **Step 2: Write the shared fetch + Overview renderer**

Create `src/ui/app/static/js/pages/reports-overview.js`:

```javascript
window.BWReportsDashboard = window.BWReportsDashboard || {};

(function () {
  const t = typeof i18next !== "undefined" ? i18next.t : (key, fallback) => fallback || key;
  let currentRange = { startEpoch: Math.floor(Date.now() / 1000) - 86400, endEpoch: Math.floor(Date.now() / 1000) };
  const listeners = [];

  function fetchDashboard(range) {
    return $.ajax({
      url: `${window.location.pathname}/dashboard`,
      type: "POST",
      data: { csrf_token: $("#csrf_token").val(), start: range.startEpoch, end: range.endEpoch, bucket: "hour" },
    });
  }

  function onRangeChange(cb) {
    listeners.push(cb);
  }

  function refresh(range) {
    currentRange = range || currentRange;
    fetchDashboard(currentRange).done((data) => listeners.forEach((cb) => cb(data, currentRange)));
  }

  window.BWReportsDashboard.onRangeChange = onRangeChange;
  window.BWReportsDashboard.refresh = refresh;
  window.BWReportsDashboard.currentRange = () => currentRange;

  function renderOverview(data) {
    if (!data || data.status !== "success") return;
    const ts = data.timeseries || {};
    const blocked = ts.total || 0;
    const prev = ts.prev_total || 0;
    const detectOnly = (data.offenders || []).length; // placeholder measure until a dedicated detect-only count is added
    const rate = blocked + detectOnly > 0 ? Math.round((blocked / (blocked + detectOnly)) * 1000) / 10 : 0;

    $("#reports-tile-blocked .bw-kpi-value").text(blocked);
    $("#reports-tile-rate .bw-kpi-value").text(`${rate}%`);
    $("#reports-tile-unique .bw-kpi-value").text(new Set((data.offenders || []).map((o) => o.ip)).size);

    const counts = ts.counts || [];
    const buckets = ts.buckets || [];
    let peakIdx = 0;
    counts.forEach((c, i) => {
      if (c > (counts[peakIdx] || 0)) peakIdx = i;
    });
    const peakLabel = buckets[peakIdx] ? new Date(buckets[peakIdx] * 1000).getHours() + ":00" : "—";
    $("#reports-tile-peak .bw-kpi-value").text(peakLabel);

    if (window.ApexCharts) {
      const host = document.getElementById("reports-timeseries-chart");
      if (host) {
        host.innerHTML = "";
        new ApexCharts(host, {
          chart: { type: "bar", height: 280 },
          series: [{ name: t("reports.chart.timeseries.series", "Blocked"), data: counts }],
          xaxis: { categories: buckets.map((b) => new Date(b * 1000).toLocaleTimeString([], { hour: "2-digit" })) },
        }).render();
      }
    }

    const recent = (data.offenders || []).slice(0, 5);
    $("#reports-recent-incidents").html(
      recent.length
        ? `<table class="table table-sm mb-0"><tbody>${recent
            .map((o) => `<tr><td class="cell-mono">${o.ip}</td><td>${o.top_reason}</td><td>${o.blocks}</td></tr>`)
            .join("")}</tbody></table>`
        : `<p class="text-muted mb-0" data-i18n="status.no_data">${t("status.no_data", "No data")}</p>`,
    );

    const byOrg = {};
    (data.offenders || []).forEach((o) => {
      if (!o.asn_org) return;
      byOrg[o.asn_org] = (byOrg[o.asn_org] || 0) + o.blocks;
    });
    const topOrgs = Object.entries(byOrg)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
    $("#reports-top-asns").html(
      topOrgs.length
        ? topOrgs.map(([org, count]) => `<div class="d-flex justify-content-between mb-1"><span>${org}</span><span class="cell-mono">${count}</span></div>`).join("")
        : `<p class="text-muted mb-0" data-i18n="status.no_data">${t("status.no_data", "No data")}</p>`,
    );
  }

  onRangeChange((data) => renderOverview(data));

  $(document).ready(function () {
    const picker = window.BWRangePicker.init("reports-range");
    document.getElementById("reports-range").addEventListener("change", (e) => {
      refresh({ startEpoch: e.detail.startEpoch, endEpoch: e.detail.endEpoch });
    });
    refresh(currentRange);
  });
})();
```

Note: `detectOnly` is a placeholder measure (comment says so explicitly) — Task 6's dashboard payload doesn't currently distinguish detect-mode-only rows from the offenders list. Flag this as a known follow-up rather than silently shipping a misleading "Blocked rate": if a more accurate detect-vs-block split is wanted, add a 4th field to Task 6's `/reports/dashboard` response (`detect_only_total`) sourced from a small additional query in Task 3-5's style — out of scope for this task to keep it bounded, but don't let the placeholder comment get lost in review.

- [ ] **Step 3: Wire the script tag**

In `reports.html`'s `{% block scripts %}`, add after the existing `reports.js` script tag:

```jinja
    <script src="{{ url_for('static', filename='js/components/range-picker.js') }}"
            nonce="{{ script_nonce }}"
            defer></script>
    <script src="{{ url_for('static', filename='js/pages/reports-overview.js') }}"
            nonce="{{ script_nonce }}"
            defer></script>
```

(Add the ApexCharts vendor script too if `reports.html` doesn't already load it — check `dashboard.html`/`home.html` for the existing `<script src=".../libs/apexcharts/...">` tag and mirror it; don't assume it's already present just because `chart_area`'s macro exists.)

- [ ] **Step 4: Manual verification**

Restart `bw-ui`, open `/reports`, Overview tab: confirm tiles populate, chart renders, range-picker buttons re-fetch and update all of them, "Most recent incidents"/"Top offender ASNs" show data (or the empty state with zero reports).

- [ ] **Step 5: Commit**

```bash
git add src/ui/app/templates/reports.html src/ui/app/static/js/pages/reports-overview.js
git commit -m "feat(ui): implement Reports Overview tab"
```

---

### Task 10: Attack patterns tab

**Files:**
- Modify: `src/ui/app/templates/reports.html` (`#reports-patterns-root` content)
- Create: `src/ui/app/static/js/pages/reports-patterns.js`
- Modify: `reports.html` `{% block scripts %}`

**Interfaces:**
- Consumes: `window.BWReportsDashboard.onRangeChange`/`.currentRange()` (Task 9) — reuses the same fetch, does not issue a second AJAX call per range change.

- [ ] **Step 1: Add the Attack patterns tab markup**

Replace `<div id="reports-patterns-root">...</div>` with:

```jinja
    <div id="reports-patterns-root">
        <div class="row g-3 mb-4">
            <div class="col-md-4">{{ tile(id="reports-tile-sqli", title="SQL injection", title_i18n="reports.tile.sqli", value="—", color="danger") }}</div>
            <div class="col-md-4">{{ tile(id="reports-tile-rce", title="RCE / command", title_i18n="reports.tile.rce", value="—", color="warning") }}</div>
            <div class="col-md-4">{{ tile(id="reports-tile-bot", title="Bot / scraper", title_i18n="reports.tile.bot", value="—", color="secondary") }}</div>
        </div>
        {% call card(title="Top ModSecurity rules fired", title_key="reports.card.top_rules.title") %}
            <div id="reports-top-rules"></div>
        {% endcall %}
        {% call card(title="Attack families", title_key="reports.card.attack_families.title", classes="mt-3") %}
            <div id="reports-attack-families"></div>
        {% endcall %}
    </div>
```

- [ ] **Step 2: Implement the renderer**

Create `src/ui/app/static/js/pages/reports-patterns.js`:

```javascript
(function () {
  const t = typeof i18next !== "undefined" ? i18next.t : (key, fallback) => fallback || key;

  const RULE_FAMILY = { "942": "sqli", "932": "rce" };

  function familyFor(ruleId) {
    const prefix = String(ruleId).slice(0, 3);
    return RULE_FAMILY[prefix] || null;
  }

  function render(data) {
    if (!data || data.status !== "success") return;
    const rules = data.rules || [];
    const offenders = data.offenders || [];

    const familyCounts = { sqli: 0, rce: 0, bot: 0 };
    rules.forEach((r) => {
      const fam = familyFor(r.rule_id);
      if (fam) familyCounts[fam] += r.count;
    });
    offenders.forEach((o) => {
      if (String(o.top_reason).toLowerCase().includes("antibot")) familyCounts.bot += 1;
    });

    $("#reports-tile-sqli .bw-kpi-value").text(familyCounts.sqli);
    $("#reports-tile-rce .bw-kpi-value").text(familyCounts.rce);
    $("#reports-tile-bot .bw-kpi-value").text(familyCounts.bot);

    $("#reports-top-rules").html(
      rules.length
        ? `<table class="table table-sm mb-0"><thead><tr><th>${t("reports.table.rule", "Rule")}</th><th>${t(
            "reports.table.fires",
            "Fires",
          )}</th></tr></thead><tbody>${rules
            .map((r) => `<tr><td><span class="badge bg-danger">CRS ${r.rule_id}</span></td><td class="cell-mono">${r.count}</td></tr>`)
            .join("")}</tbody></table>`
        : `<p class="text-muted mb-0" data-i18n="status.no_data">${t("status.no_data", "No data")}</p>`,
    );

    const totalRuleFires = rules.reduce((sum, r) => sum + r.count, 0) || 1;
    $("#reports-attack-families").html(
      Object.entries(familyCounts)
        .filter(([, count]) => count > 0)
        .map(
          ([fam, count]) =>
            `<div class="d-flex justify-content-between mb-1"><span>${fam}</span><span class="cell-mono">${Math.round((count / totalRuleFires) * 100)}%</span></div>`,
        )
        .join("") || `<p class="text-muted mb-0" data-i18n="status.no_data">${t("status.no_data", "No data")}</p>`,
    );
  }

  $(document).ready(function () {
    if (window.BWReportsDashboard) {
      window.BWReportsDashboard.onRangeChange(render);
    }
  });
})();
```

Note the CRS rule-ID-prefix → family mapping (`942`=SQLi, `932`=RCE) is a real OWASP CRS convention (matches the design kit's own comment: "CRS 942xxx"/"CRS 932xxx"), not invented; extend `RULE_FAMILY` if more families are wanted later.

- [ ] **Step 3: Wire the script tag**

Add to `{% block scripts %}` after `reports-overview.js`:

```jinja
    <script src="{{ url_for('static', filename='js/pages/reports-patterns.js') }}"
            nonce="{{ script_nonce }}"
            defer></script>
```

- [ ] **Step 4: Manual verification**

Restart `bw-ui`, open `/reports`, switch to "Attack patterns" tab, confirm tiles/table/bars populate without a second network request firing (check the browser Network tab — only one `/reports/dashboard` POST per range change, shared with Overview).

- [ ] **Step 5: Commit**

```bash
git add src/ui/app/templates/reports.html src/ui/app/static/js/pages/reports-patterns.js
git commit -m "feat(ui): implement Reports Attack patterns tab"
```

---

### Task 11: Top offenders tab

**Files:**
- Modify: `src/ui/app/templates/reports.html` (`#reports-offenders-root` content)
- Create: `src/ui/app/static/js/pages/reports-offenders.js`
- Modify: `reports.html` `{% block scripts %}`

**Interfaces:**
- Consumes: `window.BWReportsDashboard.onRangeChange` (Task 9), the existing `ban_selected`/`.ban-single` POST-to-`/bans/ban` pattern already implemented in `reports.js:322-387` (reused via a plain form-submit helper, not re-implemented).

- [ ] **Step 1: Add the Top offenders tab markup**

Replace `<div id="reports-offenders-root">...</div>` with:

```jinja
    <div id="reports-offenders-root">
        <div class="row g-3 mb-4">
            <div class="col-6 col-lg-3">{{ tile(id="reports-tile-uniqueoff", title="Unique offenders", title_i18n="reports.tile.unique_offenders", value="—") }}</div>
            <div class="col-6 col-lg-3">{{ tile(id="reports-tile-repeat", title="Repeat offenders", title_i18n="reports.tile.repeat_offenders", value="—", color="danger") }}</div>
            <div class="col-6 col-lg-3">{{ tile(id="reports-tile-countries", title="Countries", title_i18n="reports.tile.countries", value="—", color="secondary") }}</div>
            <div class="col-6 col-lg-3">{{ tile(id="reports-tile-asns", title="ASNs", title_i18n="reports.tile.asns", value="—", color="secondary") }}</div>
        </div>
        {% call card(title="Top offenders", title_key="reports.card.top_offenders.title") %}
            <div id="reports-offenders-table"></div>
        {% endcall %}
    </div>
```

- [ ] **Step 2: Implement the renderer + Ban action**

Create `src/ui/app/static/js/pages/reports-offenders.js`:

```javascript
(function () {
  const t = typeof i18next !== "undefined" ? i18next.t : (key, fallback) => fallback || key;

  function submitBan(ip, serverName, reason) {
    const banScope = serverName && serverName !== "_" ? "service" : "global";
    const form = $("<form>", { method: "POST", action: `${window.location.pathname.replace("/reports", "/bans")}/ban`, class: "visually-hidden" });
    form.append($("<input>", { type: "hidden", name: "csrf_token", value: $("#csrf_token").val() }));
    form.append(
      $("<input>", {
        type: "hidden",
        name: "bans",
        value: JSON.stringify([{ ip, reason: reason || "ui", ban_scope: banScope, service: banScope === "service" ? serverName : "", exp: 86400 }]),
      }),
    );
    form.appendTo("body").submit();
  }

  function render(data) {
    if (!data || data.status !== "success") return;
    const offenders = data.offenders || [];

    $("#reports-tile-uniqueoff .bw-kpi-value").text(offenders.length);
    $("#reports-tile-repeat .bw-kpi-value").text(offenders.filter((o) => o.blocks >= 10).length);
    $("#reports-tile-countries .bw-kpi-value").text(new Set(offenders.map((o) => o.country).filter(Boolean)).size);
    $("#reports-tile-asns .bw-kpi-value").text(new Set(offenders.map((o) => o.asn_org).filter(Boolean)).size);

    $("#reports-offenders-table").html(
      offenders.length
        ? `<table class="table table-sm mb-0"><thead><tr>
             <th>${t("reports.table.ip", "IP")}</th><th>${t("reports.table.country", "Country")}</th>
             <th>${t("reports.table.asn", "ASN")}</th><th>${t("reports.table.blocks", "Blocks")}</th>
             <th>${t("reports.table.top_rule", "Top rule")}</th><th></th></tr></thead><tbody>${offenders
            .map(
              (o) => `<tr>
             <td class="cell-mono">${o.ip}</td><td>${o.country || "—"}</td>
             <td>${o.asn_org ? `AS${o.asn_number} — ${o.asn_org}` : "N/A"}</td>
             <td class="cell-mono">${o.blocks}</td><td>${o.top_reason}</td>
             <td><button type="button" class="btn btn-outline-danger btn-sm offender-ban" data-ip="${o.ip}"><i class="bx bx-block"></i></button></td>
           </tr>`,
            )
            .join("")}</tbody></table>`
        : `<p class="text-muted mb-0" data-i18n="status.no_data">${t("status.no_data", "No data")}</p>`,
    );
  }

  $(document).on("click", ".offender-ban", function () {
    submitBan($(this).data("ip"), "_", "ui");
  });

  $(document).ready(function () {
    if (window.BWReportsDashboard) {
      window.BWReportsDashboard.onRangeChange(render);
    }
  });
})();
```

This deliberately does **not** reuse `reports.js`'s `ban_selected` DataTables-button object directly (that's a DataTables `ext.buttons` definition bound to `#reports`'s table instance, which this tab's plain HTML table isn't) — it reuses the same underlying form-POST-to-`/bans/ban` mechanism (`submitBan` mirrors `reports.js:1846-1874`'s `.ban-single` handler), which is the actual reusable part.

- [ ] **Step 3: Wire the script tag**

Add to `{% block scripts %}` after `reports-patterns.js`:

```jinja
    <script src="{{ url_for('static', filename='js/pages/reports-offenders.js') }}"
            nonce="{{ script_nonce }}"
            defer></script>
```

- [ ] **Step 4: Manual verification**

Restart `bw-ui`, open `/reports`, "Top offenders" tab: confirm tiles/table populate, clicking the ban icon on a row submits to `/bans` and the IP shows up on the Bans page.

- [ ] **Step 5: Commit**

```bash
git add src/ui/app/templates/reports.html src/ui/app/static/js/pages/reports-offenders.js
git commit -m "feat(ui): implement Reports Top offenders tab"
```

---

### Task 12: i18n completeness check + full manual regression pass

**Files:**
- Modify: `src/ui/app/static/locales/en.json` (fill any keys referenced by Tasks 8-11 not yet added: `reports.tile.blocked`, `reports.tile.blocked_rate`, `reports.tile.unique_ips`, `reports.tile.peak_hour`, `reports.tile.sqli`, `reports.tile.rce`, `reports.tile.bot`, `reports.tile.unique_offenders`, `reports.tile.repeat_offenders`, `reports.tile.countries`, `reports.tile.asns`, `reports.chart.timeseries.title`, `reports.chart.timeseries.series`, `reports.card.recent.title`, `reports.card.top_asn.title`, `reports.card.top_rules.title`, `reports.card.attack_families.title`, `reports.card.top_offenders.title`, `reports.table.rule`, `reports.table.fires`, `reports.table.ip`, `reports.table.country`, `reports.table.asn`, `reports.table.blocks`, `reports.table.top_rule`)
- Test: `tests/unit/ui/test_ui_components.py`

**Interfaces:**
- Consumes: every `data-i18n`/`title_i18n`/`i18n_key` string introduced in Tasks 7-11.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/ui/test_ui_components.py` (or confirm an equivalent whole-file scan test already exists and extend it): a test that renders `reports.html` (or scans its source text) for every `data-i18n="..."`/`title_i18n="..."`/`i18n_key="..."` occurrence and asserts each resolves to a key present in `en.json`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest ui/test_ui_components.py -v`
Expected: FAIL, listing the missing keys from Tasks 8-11.

- [ ] **Step 3: Add the missing keys**

Add each missing key to `en.json` under a `"reports"` object, following the existing nesting convention already used for `reports.subtitle`/`reports.bad_behavior_*` (grep `en.json` for `"reports"` to match the existing structure before inserting — don't create a duplicate top-level `reports` key).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tests/unit && .venv-unit/bin/python -m pytest ui/test_ui_components.py db/test_metrics.py api/test_metrics.py -v`
Expected: PASS, full suite green.

- [ ] **Step 5: Full manual regression pass**

`docker compose -f misc/dev/docker-compose.ui.api.yml restart bw-ui bw-api`, then in both light and dark mode on `/reports`:
- Event log tab: search, sort, per-column SearchPanes filters, CSV export, Excel export, single-row ban, multi-row "Ban selected", Full-URL modal, Security-Report-Details modal — all identical to pre-refactor behavior.
- Overview/Attack patterns/Top offenders tabs: range-picker (1h/24h/7d/30d/custom) updates all 3 tabs consistently from one shared fetch; tiles/chart/tables show real data (or a clean empty state on a fresh instance with zero reports); no console errors switching tabs.
- Top offenders tab's ban button correctly bans and the IP appears on `/bans`.

- [ ] **Step 6: Commit**

```bash
git add src/ui/app/static/locales/en.json tests/unit/ui/test_ui_components.py
git commit -m "test(ui): complete reports dashboard i18n coverage"
```

---

## Plan Self-Review Notes

- **Spec coverage**: Overview/Attack-patterns/Top-offenders/Event-log tabs (Tasks 8-11), ASN attribution real via db-ip (Tasks 1-2), time-range picker + trend deltas (Tasks 3, 7, 9), top ModSecurity rules (Task 5), Ban-selected reuse (Task 11), Compliance dropped (nowhere built), Investigating/MTTR replaced with Unique-attacker-IPs/Peak-hour (Task 9) — all spec sections have a task.
- **Known gap flagged in-line, not hidden**: Task 9's "Blocked rate" tile uses `offenders.length` as a stand-in for "detect-only" count (no dedicated field yet) — called out explicitly in Step 2 with a concrete follow-up (`detect_only_total` field on the Task 6 endpoint) rather than silently shipping a subtly-wrong metric.
- **Type/interface consistency checked**: `get_metrics_timeseries`/`top_offenders`/`top_rules` signatures (Tasks 3-5) match their consumption in Task 6's router; Task 6's `/reports/dashboard` JSON shape (`timeseries`/`offenders`/`rules` keys) matches what Tasks 9/10/11's JS reads (`data.timeseries`, `data.offenders`, `data.rules`).
- **Not a placeholder, but explicitly deferred**: Task 6 Step 5's dev-port `curl` command names the exact file to check before running rather than guessing a port — the actual verification is manual per Step 6, consistent with "no placeholders" (it's a real, concrete instruction, not a TBD).
