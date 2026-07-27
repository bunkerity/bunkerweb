"""Convention check: order.json and the PLUGINS_ORDER_* defaults list the same plugins.

The runtime order is not read from ``order.json`` alone. ``helpers.order_plugins`` applies the
``PLUGINS_ORDER_<PHASE>`` setting as an override, so a plugin added to ``order.json`` but missing
from the matching default is silently pushed to the end of its phase — which, for the
``ssl_certificate`` phase, means a certificate provider that should have won gets to run only
after the ones it was meant to precede. Membership is asserted rather than exact order because
the two lists disagree on the relative position of ``bunkerweb``/``crowdsec`` in ``access``,
which predates this check and changes runtime behaviour to "fix".
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ORDER = json.loads(ROOT.joinpath("src", "common", "core", "order.json").read_text())
SETTINGS = json.loads(ROOT.joinpath("src", "common", "settings.json").read_text())


def test_every_ordered_plugin_is_in_its_phase_default():
    mismatches = {}
    for phase, plugin_ids in ORDER.items():
        setting = SETTINGS.get(f"PLUGINS_ORDER_{phase.upper()}")
        if setting is None:
            continue
        default = setting["default"].split()
        if set(default) != set(plugin_ids):
            mismatches[phase] = {"only_in_order_json": sorted(set(plugin_ids) - set(default)), "only_in_default": sorted(set(default) - set(plugin_ids))}

    assert not mismatches, f"order.json and the PLUGINS_ORDER_* defaults disagree: {mismatches}"


def test_the_certificates_plugin_precedes_the_settings_driven_providers():
    """An inventory attachment must win over the provider a service still has configured."""
    for source in (ORDER["ssl_certificate"], SETTINGS["PLUGINS_ORDER_SSL_CERTIFICATE"]["default"].split()):
        assert source.index("certificates") < min(source.index(provider) for provider in ("customcert", "letsencrypt", "selfsigned"))
