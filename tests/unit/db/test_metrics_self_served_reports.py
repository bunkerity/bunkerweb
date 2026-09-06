"""``_report_clause()`` keeps a remediation the plugin served itself, whatever status it ended on.

The persisted mirror of ``is_report()`` (``src/common/core/metrics/metrics.lua``), pinned in
``tests/unit/metrics/test_report_filter_self_served.py``. Same rule, same allowlist, two
moments: ``is_report()`` gates an instance's live buffer, this one gates the rows the scheduler
has already stored. Drifting them makes a report visible on the dashboard until the buffer rolls
over and then gone, or the reverse.

CrowdSec 1.8's AppSec bot-detection challenge is the case that forced the widening: the challenge
page is served with AppSec's own status — a 200 — and the origin is never reached, so the row was
persisted with ``reason = "crowdsec"`` and every query filtered it out again.
"""

EPOCH = 1704067200


def _rec(request_id, *, status=403, reason="blacklist", security_mode="block", **over):
    rec = {
        "id": request_id,
        "date": EPOCH,
        "ip": "1.2.3.4",
        "country": "US",
        "method": "GET",
        "url": "/admin",
        "status": status,
        "user_agent": "curl/8",
        "reason": reason,
        "server_name": "app.example.com",
        "data": "",
        "security_mode": security_mode,
    }
    rec.update(over)
    return rec


class TestSelfServedRemediationsAreReports:
    def test_a_200_crowdsec_challenge_is_a_report(self, db):
        db.batch_upsert_metrics_requests(
            [_rec("challenged", status=200, reason="crowdsec", data={"source": "appsec", "action": "challenge"})],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_requests()
        assert res["filtered"] == 1
        assert res["data"][0]["request_id"] == "challenged"
        # the verdict round-trips as a dict, which is what the UI renders the sentence from
        assert res["data"][0]["data"] == {"source": "appsec", "action": "challenge"}

    def test_the_arm_does_not_widen_the_status_range(self, db):
        """Deliberately keyed on the reason and not on a widened status range: the "ok" row is
        the one a range would have dragged in."""
        db.batch_upsert_metrics_requests(
            [_rec("ok", status=200), _rec("challenged", status=200, reason="crowdsec")],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_requests()
        assert res["total"] == 2
        assert res["filtered"] == 1
        assert [r["request_id"] for r in res["data"]] == ["challenged"]

    def test_a_200_antibot_challenge_is_a_report(self, db):
        """Antibot answers the request itself and the content phase renders the challenge with a
        200; the reason it now records (``antibot:set_challenge_reason``) is what makes the row
        reachable at all."""
        db.batch_upsert_metrics_requests(
            [
                _rec(
                    "challenged",
                    status=200,
                    reason="antibot",
                    data={"source": "antibot", "provider": "captcha", "action": "challenge", "http_status": 200},
                )
            ],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_requests()
        assert res["filtered"] == 1
        assert res["data"][0]["data"]["provider"] == "captcha"

    def test_a_302_workflows_redirect_is_a_report(self, db):
        """``workflows:apply`` sets the reason on its redirect branch and the dispatcher exits
        through ``ngx_redirect()`` with a 3xx — neither 4xx, nor detect, nor a stream session."""
        db.batch_upsert_metrics_requests(
            [_rec("redirected", status=302, reason="workflows", data={"workflow": "api-shield", "rule": "r1", "action": "redirect"})],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_requests()
        assert res["filtered"] == 1
        assert res["data"][0]["request_id"] == "redirected"

    def test_an_ordinary_3xx_row_is_not_dragged_in(self, db):
        """The workflows arm must not become "every redirect is a report"."""
        db.batch_upsert_metrics_requests(
            [_rec("moved", status=302), _rec("redirected", status=302, reason="workflows")],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_requests()
        assert res["total"] == 2
        assert [r["request_id"] for r in res["data"]] == ["redirected"]

    def test_the_allowlist_is_case_insensitive(self, db):
        """``reason`` is a plain string column: ``IN`` is case-sensitive on PostgreSQL and not
        under MariaDB's default collation, so the clause lowercases before comparing. Pins that
        the SQL half and the Lua half answer the same question on every engine."""
        db.batch_upsert_metrics_requests([_rec("challenged", status=200, reason="AntiBot")], instance_hostname="bw-1")
        assert db.get_metrics_requests()["filtered"] == 1

    def test_a_crowdsec_block_is_still_a_report(self, db):
        db.batch_upsert_metrics_requests([_rec("banned", status=403, reason="crowdsec")], instance_hostname="bw-1")
        assert db.get_metrics_requests()["filtered"] == 1

    def test_facets_see_the_served_challenge_too(self, db):
        """The facets run the report clause on their own; a row visible in the table and absent
        from its search panes reads as a broken filter."""
        db.batch_upsert_metrics_requests(
            [_rec("ok", status=200, country="US"), _rec("challenged", status=200, reason="crowdsec", country="FR")],
            instance_hostname="bw-1",
        )
        assert db.get_metrics_facets()["country"] == {"FR": {"total": 1, "count": 1}}


class TestTheAnalyticalViewsCountBlocksNotChallenges:
    """ "Show me this row" and "someone attacked me from this IP" used to be the same question.

    They came apart the moment a served challenge became a report. The Reports *table* and its
    facets must list a challenge — that is the whole PO ruling — but the analytical tabs must not
    count one: **Top offenders** is titled *Top attacker IPs* and increments a ``blocks`` counter,
    the threat map pins the row on a world map of attacks, and the overview timeseries is the
    activity chart those two are read against. A visitor who was shown a captcha is not an
    offender, and one who was redirected by a workflow rule is not either.

    ``_blocking_clause()`` is the report filter exactly as it stood before this widening, so what
    these assert is that the widening changed the table and nothing else."""

    def _mixed(self, db):
        db.batch_upsert_metrics_requests(
            [
                _rec("blocked", status=403, reason="blacklist", ip="9.9.9.9"),
                _rec("challenged", status=200, reason="antibot", ip="1.1.1.1", data={"source": "antibot", "provider": "captcha", "action": "challenge"}),
                _rec("challenged2", status=200, reason="antibot", ip="1.1.1.1"),
                _rec("redirected", status=302, reason="workflows", ip="2.2.2.2"),
                _rec("cs-served", status=200, reason="crowdsec", ip="3.3.3.3", data={"source": "appsec", "action": "challenge"}),
            ],
            instance_hostname="bw-1",
        )

    def test_the_table_still_lists_all_five(self, db):
        """The control: without this, the tests below would pass on a filter that dropped the rows
        everywhere, which is the opposite of the ruling."""
        self._mixed(db)
        assert db.get_metrics_requests()["filtered"] == 5

    def test_a_challenged_visitor_is_not_a_top_offender(self, db):
        self._mixed(db)
        offenders = db.get_metrics_top_offenders(start=EPOCH - 60, end=EPOCH + 60)
        assert [o["ip"] for o in offenders] == ["9.9.9.9"]
        assert offenders[0]["blocks"] == 1

    def test_a_challenged_visitor_is_not_on_the_threat_map(self, db):
        self._mixed(db)
        threatmap = db.get_metrics_threatmap(start=EPOCH - 3600, end=EPOCH + 3600)
        assert threatmap["count"] == 1
        assert [r["ip"] for r in threatmap["recent"]] == ["9.9.9.9"]

    def test_the_overview_timeseries_counts_blocks_only(self, db):
        self._mixed(db)
        assert sum(db.get_metrics_timeseries(start=EPOCH - 3600, end=EPOCH + 3600)["counts"]) == 1
