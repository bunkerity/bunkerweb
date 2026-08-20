"""The ACME-account recovery path, and the credential parsing that feeds it.

Every case here is a failure one of the fixes in the #3773/#3772/#3783 series was written for, so
reverting any of them turns a test red rather than going quietly green (RULE 14a). Grouped by the
function that owns the behaviour; the anti-cases matter as much as the positives, because each fix
is a widening and a widening that goes too far causes the damage it was meant to prevent.
"""

from ipaddress import ip_address
from pathlib import Path

import pytest

from letsencrypt_utils import (
    account_id_for_cert,
    extract_provider,
    failed_renewal_cert,
    is_stale_account_line,
    stale_account_uri,
)

# Verbatim from certbot/boulder output. Kept as literals: a paraphrase would test the paraphrase.
NOT_FOUND = 'Unable to validate JWS :: Account "https://acme-v02.api.letsencrypt.org/acme/acct/1234567" not found'
DEACTIVATED = 'Unable to validate JWS :: Account is not valid, has status "deactivated"'
# certbot's own message for a LOCAL directory that went missing. Repointing repairs this without
# touching the CA, so matching it would retire an account the CA still considers perfectly valid.
LOCAL_MISSING = "Account at /var/cache/bunkerweb/letsencrypt/etc/accounts/.../deadbeef does not exist"
RENEW_FAILURE = "Failed to renew certificate app.example.com with error: Some error"


class TestIsStaleAccountLine:
    @pytest.mark.parametrize("line", [NOT_FOUND, DEACTIVATED])
    def test_both_rejection_phrasings_match(self, line):
        """Only the "not found" wording was matched before, so a deactivated account retried forever."""
        assert is_stale_account_line(line)

    def test_a_missing_local_directory_is_not_a_rejection(self):
        assert not is_stale_account_line(LOCAL_MISSING)

    @pytest.mark.parametrize(
        "line",
        [
            "",
            "Some unrelated certbot chatter",
            "Account not found",  # no JWS/acct marker: not the CA rejecting us
            'Unable to validate JWS :: Order "https://.../acme/acct/1" not found',  # no "Account"
        ],
    )
    def test_unrelated_lines_do_not_match(self, line):
        assert not is_stale_account_line(line)


class TestIdentifyingTheOffender:
    def test_the_uri_is_extracted_from_the_not_found_phrasing(self):
        assert stale_account_uri(NOT_FOUND) == "https://acme-v02.api.letsencrypt.org/acme/acct/1234567"

    def test_the_deactivated_phrasing_carries_no_uri(self):
        """Which is the whole reason failed_renewal_cert exists as the second route."""
        assert stale_account_uri(DEACTIVATED) == ""

    def test_the_lineage_is_extracted_from_a_renewal_failure(self):
        assert failed_renewal_cert(RENEW_FAILURE) == "app.example.com"

    def test_an_unrelated_line_yields_no_lineage(self):
        assert failed_renewal_cert(DEACTIVATED) == ""


class TestAccountIdForCert:
    def _conf(self, tmp_path: Path, body: str) -> Path:
        renewal = tmp_path / "renewal"
        renewal.mkdir(parents=True, exist_ok=True)
        (renewal / "app.example.com.conf").write_text(body, encoding="utf-8")
        return tmp_path

    def test_reads_the_account_line(self, tmp_path):
        data = self._conf(tmp_path, "version = 2.11.0\naccount = deadbeefcafe\nserver = https://acme-v02.api.letsencrypt.org/directory\n")
        assert account_id_for_cert(data, "app.example.com") == "deadbeefcafe"

    def test_the_literal_string_None_is_not_an_account(self, tmp_path):
        """certbot writes `account = None` when there is none; returning it would send the purge hunting for a directory named None."""
        assert account_id_for_cert(self._conf(tmp_path, "account = None\n"), "app.example.com") == ""

    def test_a_missing_conf_is_empty_not_an_exception(self, tmp_path):
        assert account_id_for_cert(tmp_path, "nonexistent.example.com") == ""


class TestCredentialItemParsing:
    """`extract_provider`'s key/value split — the fix that stopped items vanishing silently.

    A leading space made the key empty and surrounding quotes made it unmatchable. Either way the
    item was dropped and the operator's only signal was a validation error naming no field.
    """

    @staticmethod
    def _items(monkeypatch, raw: str):
        monkeypatch.setenv("LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", raw)
        return extract_provider("svc", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "cloudflare", logger=None)

    @pytest.mark.parametrize(
        "raw",
        [
            "dns_cloudflare_api_token abc123",
            " dns_cloudflare_api_token abc123",  # leading space: key used to come out empty
            '"dns_cloudflare_api_token" abc123',  # quoted key: used to be unmatchable
            "dns_cloudflare_api_token\tabc123",  # tab: the split was on a literal space only
            "dns_cloudflare_api_token = abc123",
            "dns_cloudflare_api_token =abc123",
        ],
    )
    def test_every_spelling_yields_the_same_credential(self, monkeypatch, raw):
        provider = self._items(monkeypatch, raw)
        assert provider is not None, f"the item was dropped entirely: {raw!r}"
        # bytes: get_formatted_credentials() renders the file certbot will read, not a string.
        assert b"abc123" in provider.get_formatted_credentials(), f"{raw!r} did not round-trip to the token"


def _load_from_job(job_file: str, func_name: str):
    """Pull one function out of a job script without executing the script.

    `certbot-new.py` is not importable: the hyphen is not a module name, and importing it would run
    the job's top-level `try:` block. Compile just the function's AST node instead.
    """
    import ast

    path = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "letsencrypt" / "jobs" / job_file
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == func_name), None)
    assert node is not None, f"{func_name} is gone from {job_file}"
    namespace = {"ip_address": ip_address, "List": list}
    exec(compile(ast.Module(body=[node], type_ignores=[]), filename=str(path), mode="exec"), namespace)
    return namespace[func_name]


unissuable_names = _load_from_job("certbot-new.py", "unissuable_names")


class TestUnissuableNames:
    """Names no public ACME CA will ever issue for.

    Nothing else rejects them, so they reached certbot, failed on every run, and kept the whole job
    red even when every other service had its certificate.
    """

    @pytest.mark.parametrize("name", ["192.0.2.1", "2001:db8::1", "localhost", "intranet", "*.localhost", "  10.0.0.1  "])
    def test_rejected(self, name):
        assert unissuable_names([name]) == [name]

    @pytest.mark.parametrize("name", ["example.com", "www.example.com", "*.example.com", "example.com."])
    def test_accepted(self, name):
        assert unissuable_names([name]) == []

    def test_a_mixed_list_reports_only_the_unissuable(self):
        """The caller keeps the issuable names and asks for a certificate for those, so the split matters."""
        assert unissuable_names(["example.com", "localhost", "192.0.2.1", "www.example.com"]) == ["localhost", "192.0.2.1"]
