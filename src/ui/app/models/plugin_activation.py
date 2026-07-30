"""Per-service activation, including state that lives in attachments rather than settings.

`get_config` cannot see resource attachments: `src/common/gen/main.py:142-149` expands
redirects and upstreams into flat settings AFTER the DB read, at generation time. So a service
with an attached redirect resource still reports `REDIRECT_TO == ""`. Judging those plugins on
settings alone tells the operator a plugin is off while it is demonstrably running.
"""

from typing import Any, Dict

from app.utils import is_plugin_active

# plugin id -> the resource family whose attachments activate it.
#
# Certificates are deliberately excluded: unlike redirect/upstream/workflow, the
# certificate family has an open-ended set of owning plugins, discovered at runtime via
# `extensions.certificate_source` (see `iter_certificate_sources` in
# `src/common/utils/plugin_extensions.py`) rather than a fixed one-plugin-per-family
# mapping -- that's what lets a new PRO or third-party certificate provider ship with no
# core change and no schema migration. An attached certificate therefore cannot be
# attributed to a single plugin id at authoring time (a cert issued by letsencrypt must
# not make customcert read as active), so no certificate mapping is declared here.
# Attributing a certificate's activation to its actual issuing plugin would need to read
# the resource's own recorded source and is a possible future direction, not this slice.
_RESOURCE_BACKED = {
    "redirect": "redirect",
    "reverseproxy": "upstream",
    "workflows": "workflow",
}


def is_plugin_active_for_service(plugin_id: str, plugin_name: str, config: dict, attachments: Dict[str, Dict[str, Any]]) -> bool:
    """Same verdict as `is_plugin_active`, except a resource-backed plugin with at least
    one attachment in its family always reads active, regardless of what settings say.

    A family whose read failed (``attachments[family]["error"]`` set, so ``items`` is
    empty) is treated as "no attachments" rather than raising -- a dead resource API
    must not flip a plugin's reported state.
    """
    family = _RESOURCE_BACKED.get(plugin_id)
    if family and attachments.get(family, {}).get("items"):
        return True
    return is_plugin_active(plugin_id, plugin_name, config)
