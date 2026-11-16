"""The API refuses what is not a bare address and hands every spelling of one address to the instances as one text."""

import pytest
from pydantic import ValidationError
from schemas import BanRequest, UnbanRequest  # type: ignore


@pytest.mark.parametrize("model", [BanRequest, UnbanRequest])
@pytest.mark.parametrize(
    ("given", "canonical"),
    [
        ("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"),
        ("2001:db8::1", "2001:db8::1"),
        ("::ffff:192.0.2.1", "192.0.2.1"),
        ("::FFFF:C000:201", "192.0.2.1"),
        (" 192.0.2.1 ", "192.0.2.1"),
        ("::102:304", "::1.2.3.4"),
    ],
)
def test_one_address_one_spelling(model, given, canonical):
    assert model(ip=given).ip == canonical


@pytest.mark.parametrize("model", [BanRequest, UnbanRequest])
@pytest.mark.parametrize("bad", ["fe80::1%eth0", "[2001:db8::1]", "2001:db8::/64", "1.2.3.4/32", "example.com", ""])
def test_what_is_not_a_bare_address_is_refused(model, bad):
    with pytest.raises(ValidationError):
        model(ip=bad)
