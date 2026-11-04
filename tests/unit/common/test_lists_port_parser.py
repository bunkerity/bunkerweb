"""List formats and trust-narrowing selectors, with exact inclusion/exclusion oracles."""

import json

import pytest

import common_utils

AWS = {
    "prefixes": [
        {"ip_prefix": "192.0.2.0/24", "service": "CLOUDFRONT", "region": "GLOBAL"},
        {"ip_prefix": "198.51.100.0/24", "service": "EC2", "region": "GLOBAL"},
        {"ip_prefix": "203.0.113.0/24", "service": "CLOUDFRONT", "region": "eu-west-1"},
    ],
    "ipv6_prefixes": [{"ipv6_prefix": "2001:db8::/32", "service": "CLOUDFRONT", "region": "GLOBAL"}],
}


def entries(data, **kwargs):
    parser = getattr(common_utils, "iter_list_entries", None)
    assert parser is not None, "shared list parser is missing"
    return list(parser(data, **kwargs))


def test_cloudfront_exact_service_region_both_families():
    assert entries(json.dumps(AWS).encode(), ip_list=True, url_filter="service=CLOUDFRONT&region=GLOBAL&ip_prefix&ipv6_prefix") == [
        b"192.0.2.0/24",
        b"2001:db8::/32",
    ]


def test_percent_decoded_keys_values_and_array_condition():
    assert entries(b'{"service name":["edge network","other"],"ranges":["192.0.2.0/24"]}', ip_list=True, url_filter="service%20name=edge%20network&ranges") == [
        b"192.0.2.0/24"
    ]


@pytest.mark.parametrize(
    "selector", ["service=NOPE", "missing", "&", "service=CLOUDFRONT&&ip_prefix", "=CLOUDFRONT", "service=", "service!=CLOUDFRONT", "ip_prefix[0]", "bad%ZZ"]
)
def test_invalid_or_nonmatching_selector_never_broadens(selector):
    assert entries(json.dumps(AWS).encode(), ip_list=True, url_filter=selector) == []


@pytest.mark.parametrize("body", [b"192.0.2.0/24\n", b'192.0.2.0/24\n{"service":"EC2","ip_prefix":"198.51.100.0/24"}', b'{"service":"CLOUDFRONT", broken'])
def test_filtered_nonjson_mixed_or_malformed_fails_closed(body):
    assert entries(body, ip_list=True, url_filter="service=CLOUDFRONT") == []


def test_json_ndjson_csv_tsv_bom_comments_duplicates():
    assert entries(b"\xef\xbb\xbf#comment\n;comment\n192.0.2.1,description\n192.0.2.1\n2001:db8::1\tnote\n", ip_list=True) == [b"192.0.2.1", b"2001:db8::1"]
    assert entries(b'{"ip":"192.0.2.1"}\n{"ip":"2001:db8::1"}\n', ip_list=True, content_type="application/x-ndjson") == [b"192.0.2.1", b"2001:db8::1"]


def test_legacy_asn_rdns_whole_user_agent():
    assert entries(b"AS123 note\n.example.com comment\n") == [b"AS123", b".example.com"]
    assert entries(b"#comment\nMozilla/5.0 Example Bot\n", whole_line=True) == [b"Mozilla/5.0 Example Bot"]


def test_download_url_strips_fragment_only():
    split = getattr(common_utils, "split_list_url", None)
    assert split is not None, "URL fragment splitter is missing"
    assert split("https://host/list?q=1#service=CLOUDFRONT&ip_prefix") == ("https://host/list?q=1", "service=CLOUDFRONT&ip_prefix")
