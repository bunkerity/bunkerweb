"""``certbot-new.py`` refuses a wildcard group that cannot cover every configured hostname.

Port of dev ``4b5e27c1b``. A wildcard matches exactly **one** label: ``*.example.com`` covers
``a.example.com`` but not ``a.b.example.com``. The grouping code used to return the common suffix
as the wildcard base regardless of depth, so a service declaring ``example.com`` and
``a.b.example.com`` got a certificate for ``*.example.com`` + ``example.com`` — served for
``a.b.example.com`` as well, where it does not validate. The group is now refused whole.

That is a *behaviour* change with teeth: such a service goes from "a certificate covering some of
its names" to **no certificate at all** (``build_service_entries`` logs ``No valid wildcard groups
found, skipping generation``). Worse with ``LETS_ENCRYPT_CLEAR_OLD_CERTS=yes`` (opt-in, default
``no``): a refused group drops out of ``entries``, the lineage is then not ``active``, and
``certbot-new.py:1277`` **deletes the existing, currently-serving certificate** at the next job run
rather than leaving it to expire. 1.7 has no ``misconfigured_services`` reporter — dev's other half
of the signal, see the comments in the job — so the single ``LOGGER.error`` below is the whole
notice. Pinning both the refusal and the error text is what keeps that visible.

The two functions are extracted from the job's source rather than imported: ``certbot-new.py`` is
not a legal module name and its module-level imports pull in certbot, the API client and the job
runner. Same approach as ``tests/unit/common/test_regex_match_memoize.py``.
"""

import re
from pathlib import Path
from typing import Dict, List, Set  # noqa: F401  (the extracted signatures annotate with these)

import pytest

JOB = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "letsencrypt" / "jobs" / "certbot-new.py"


class _Logger:
    def __init__(self):
        self.errors: List[str] = []

    def error(self, message):
        self.errors.append(str(message))


def _load():
    """exec just the two grouping functions, with a recording LOGGER and the stdlib they use."""
    source = JOB.read_text(encoding="utf-8")
    chunks = []
    for pattern, what in (
        (r"^def extract_wildcard_groups\(.*?\n(?=\n\ndef |\n\n[A-Za-z_])", "extract_wildcard_groups"),
        (r"^def _determine_wildcard_bases\(.*?\n(?=\n\ndef |\n\n[A-Za-z_])", "_determine_wildcard_bases"),
    ):
        found = re.search(pattern, source, re.S | re.M)
        assert found, f"{what} not found in certbot-new.py -- renamed or restructured?"
        chunks.append(found.group(0))
    logger = _Logger()
    namespace = {"defaultdict": __import__("collections").defaultdict, "LOGGER": logger, "Dict": Dict, "List": List, "Set": Set}
    exec("\n".join(chunks), namespace)  # noqa: S102  -- the code under test, read from the repo
    return namespace["extract_wildcard_groups"], logger


@pytest.fixture
def grouping():
    return _load()


def test_a_group_a_wildcard_can_cover_is_still_issued(grouping):
    """Anti-vacuity. Without this, a refusal that fired on everything would look like a pass."""
    extract, logger = grouping

    groups = extract(["a.example.com", "b.example.com"], "svc")

    assert groups == {"example.com": ["*.example.com", "example.com"]}
    assert logger.errors == []


def test_a_name_one_label_deeper_refuses_the_whole_group(grouping):
    """``*.example.com`` cannot cover ``a.b.example.com``; issuing anyway drops it silently."""
    extract, logger = grouping

    groups = extract(["example.com", "a.b.example.com"], "svc")

    assert groups == {}
    assert len(logger.errors) == 1
    error = logger.errors[0]
    assert "[Service: svc]" in error, error
    assert "a.b.example.com" in error, "the error must name the hostname that cannot be covered"
    assert "separate services" in error, "the error must say what to do about it"


def test_the_bare_base_alongside_a_single_label_is_fine(grouping):
    """``*.example.com`` + ``example.com`` covers both; depth is exactly len(suffix) + 1."""
    extract, logger = grouping

    assert extract(["example.com", "a.example.com"], "svc") == {"example.com": ["*.example.com", "example.com"]}
    assert logger.errors == []


def test_an_already_wildcarded_name_is_normalised_not_refused(grouping):
    """The caller passes the configured names, which may already carry the ``*.`` prefix."""
    extract, logger = grouping

    assert extract(["*.example.com", "example.com"], "svc") == {"example.com": ["*.example.com", "example.com"]}
    assert logger.errors == []


def test_two_separate_domains_each_get_their_own_group(grouping):
    extract, logger = grouping

    groups = extract(["a.example.com", "a.example.org"], "svc")

    assert set(groups) == {"example.com", "example.org"}
    assert logger.errors == []


def test_a_refused_group_does_not_take_its_siblings_down(grouping):
    """The refusal is per group: names are grouped by their last two labels first.

    Without this, "refuse the group" and "refuse the service" are indistinguishable — and they are
    very different when the certificate of an unrelated domain on the same service is at stake.
    """
    extract, logger = grouping

    groups = extract(["example.com", "a.b.example.com", "x.example.org"], "svc")

    assert groups == {"example.org": ["*.example.org", "example.org"]}, "the healthy sibling group must still issue"
    assert len(logger.errors) == 1
    assert "example.org" not in logger.errors[0], "the sibling must not be named in the refusal"
