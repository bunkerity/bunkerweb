#!/usr/bin/env python3
"""The onboarding step catalog — the single source of truth for the guided walkthrough.

Nothing else in the feature hardcodes a step. The drawer, the per-page hints and the
spotlight all render whatever this catalog yields for the current user, which is what keeps
one declaration serving three surfaces instead of three parallel lists drifting apart.

Everything here is pure: a step's completion is derived from a signals dict the caller
builds, never stored. Configure something outside the UI and the step is already ticked the
next time the drawer renders — the checklist self-heals rather than going stale.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

# The key this feature owns in the per-user KV. That store shares one namespace with the
# DataTables ids, so the name has to be one no table can take — asserted in the tests.
PREFERENCE_KEY = "onboarding"

# Track a user is placed in. `admin` and `writer` get tasks, `reader` gets orientation:
# every write button is already disabled for readers, so telling one to "register a service"
# is an instruction it cannot follow.
TRACKS = ("admin", "writer", "reader")

# What each track is allowed to be asked to do. `requires` gates on capability, `tracks`
# gates on relevance — both are needed, see the module docstring of the test file.
_SATISFIES: Dict[str, Tuple[str, ...]] = {
    "admin": ("read", "write", "admin"),
    "writer": ("read", "write"),
    "reader": ("read",),
}


@dataclass(frozen=True)
class Step:
    id: str  # stable slug; also the data-tour anchor name when one exists
    i18n_key: str  # data-i18n key, mirrored in en.json
    en: str  # English fallback copy
    requires: str  # "read" | "write" | "admin" — capability gate
    tracks: Tuple[str, ...]  # which tracks this step is relevant to
    endpoint: str  # Flask endpoint behind the step's "Go →" link
    done: Callable[[dict], bool]  # derived completion, reads the signals dict
    when: Callable[[dict], bool] = field(default=lambda signals: True)  # relevance gate
    anchor: Optional[str] = None  # `data-tour` name the "Show me" button points at, else None
    optional: bool = False  # never gates the "all done" verdict


def _blocks_seen(signals: dict) -> bool:
    return signals.get("blocks_total", 0) > 0


def _acked(page_id: str) -> Callable[[dict], bool]:
    return lambda signals: page_id in signals.get("acked_hints", ())


# `mfa` is shared by every track and is deliberately requires="read": `/profile` is exempt
# from the read-only gate, so any role can secure its own account.
_MFA = Step(
    id="mfa",
    i18n_key="onboarding.item.mfa",
    en="Activate MFA",
    requires="read",
    tracks=TRACKS,
    endpoint="profile.profile_page",
    anchor="user-menu",
    done=lambda signals: bool(signals.get("mfa")),
)

CATALOG: Tuple[Step, ...] = (
    Step(
        id="install",
        i18n_key="onboarding.item.install",
        en="Install BunkerWeb on 1+ host",
        requires="write",
        tracks=("admin", "writer"),
        endpoint="instances.instances_page",
        anchor="nav-instances",
        done=lambda signals: bool(signals.get("is_initialized")) and bool(signals.get("first_config_saved")),
    ),
    Step(
        id="service",
        i18n_key="onboarding.item.service",
        en="Register your first service",
        requires="write",
        tracks=("admin", "writer"),
        endpoint="services.services_page",
        anchor="nav-services",
        done=lambda signals: signals.get("services", 0) > 0,
    ),
    Step(
        id="https",
        i18n_key="onboarding.item.https",
        en="Get HTTPS working",
        requires="write",
        tracks=("admin", "writer"),
        endpoint="certificates.certificates_page",
        anchor="nav-certificates",
        done=lambda signals: signals.get("certificates_total", 0) > 0,
    ),
    # The payoff step: an operator who has never seen BunkerWeb block anything is trusting
    # that it works. This one makes them look.
    Step(
        id="first_block",
        i18n_key="onboarding.item.first_block",
        en="See BunkerWeb block something",
        requires="write",
        tracks=("admin", "writer"),
        endpoint="reports.reports_page",
        anchor="nav-reports",
        done=_blocks_seen,
    ),
    _MFA,
    # Hidden entirely rather than shown as a dead link when the workflows plugin is off.
    Step(
        id="workflow",
        i18n_key="onboarding.item.workflow",
        en="Attach a security workflow",
        requires="write",
        tracks=("admin", "writer"),
        endpoint="workflows.workflows_page",
        anchor="nav-workflows",
        done=lambda signals: signals.get("workflows_total", 0) > 0,
        when=lambda signals: bool(signals.get("workflows_available")),
        optional=True,
    ),
    # Optional so a FREE install can never be held at 6/7 by an upsell it will not act on.
    Step(
        id="pro",
        i18n_key="onboarding.item.pro",
        en="Activate BunkerWeb PRO",
        requires="admin",
        tracks=("admin",),
        endpoint="pro.pro_page",
        anchor="nav-pro",
        done=lambda signals: bool(signals.get("is_pro")),
        optional=True,
    ),
    # Reader orientation. Completion is the phase-2 hint acknowledgement, which is what makes
    # the three surfaces one feature rather than three.
    Step(
        id="read_home",
        i18n_key="onboarding.item.read_home",
        en="Read the dashboard: what is healthy right now",
        requires="read",
        tracks=("reader",),
        endpoint="home.home_page",
        anchor="nav-home",
        done=_acked("home"),
    ),
    Step(
        id="read_reports",
        i18n_key="onboarding.item.read_reports",
        en="Find out why a request was blocked",
        requires="read",
        tracks=("reader",),
        endpoint="reports.reports_page",
        anchor="nav-reports",
        done=_acked("reports"),
    ),
    Step(
        id="read_bans",
        i18n_key="onboarding.item.read_bans",
        en="See who is banned, and until when",
        requires="read",
        tracks=("reader",),
        endpoint="bans.bans_page",
        anchor="nav-bans",
        done=_acked("bans"),
    ),
    Step(
        id="read_logs",
        i18n_key="onboarding.item.read_logs",
        en="Tail live logs across instances",
        requires="read",
        tracks=("reader",),
        endpoint="logs.logs_page",
        anchor="nav-logs",
        done=_acked("logs"),
    ),
)

# The only values `PATCH /onboarding/state {"ack_hint": ...}` may write. Derived from the
# catalog rather than restated, so a new orientation step cannot forget to allow its own id
# and no crafted request can grow the stored blob without bound.
HINT_PAGE_IDS = frozenset(step.id.removeprefix("read_") for step in CATALOG if step.id.startswith("read_"))


def resolve_track(*, admin: bool, readonly: bool) -> str:
    """Map the two role flags the UI already computes onto a track."""
    if admin:
        return "admin"
    return "reader" if readonly else "writer"


def visible_steps(track: str, signals: dict) -> Tuple[Step, ...]:
    """The steps this track should see, in catalog order.

    A step renders only when its capability is satisfied AND the track is one it is relevant
    to AND its `when` gate passes.

    `tracks` is the gate that does the work today: without it an admin is told to go read the
    dashboard, because the reader orientation steps are themselves `requires="read"` and every
    track satisfies that. `requires` is currently redundant — no shipped step declares a track
    that cannot satisfy it — and it exists for the step somebody adds next with the two
    disagreeing. Both directions are asserted in `test_onboarding_catalog.py`.
    """
    satisfied = _SATISFIES.get(track, ())
    return tuple(step for step in CATALOG if step.requires in satisfied and track in step.tracks and step.when(signals))


def progress(steps: Tuple[Step, ...], signals: dict) -> Tuple[int, int]:
    """(done, total) over the steps that count. Optional steps are excluded from both."""
    counted = [step for step in steps if not step.optional]
    return sum(1 for step in counted if step.done(signals)), len(counted)


def is_complete(steps: Tuple[Step, ...], signals: dict) -> bool:
    done, total = progress(steps, signals)
    return total > 0 and done == total
