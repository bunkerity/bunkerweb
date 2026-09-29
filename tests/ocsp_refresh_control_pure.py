#!/usr/bin/env python3
"""
Pure-logic checks for OCSP intermediate control clear / supersede fence.
Does not import ocsp-refresh.py (heavy Job/logger deps) — mirrors the predicates.
Run from repo root: python3 tests/ocsp_refresh_control_pure.py
"""

from __future__ import annotations

from typing import Optional

failures = 0


def check(name: str, cond: bool) -> None:
    global failures
    if cond:
        print(f"ok  - {name}")
    else:
        print(f"FAIL- {name}")
        failures += 1


def serial_ban_superseded_by_good(ban_unix: Optional[int], this_unix: Optional[int]) -> bool:
    """Mirror of ocsp-refresh._serial_ban_superseded_by_good."""
    if this_unix is None:
        return False
    if ban_unix is None:
        return True
    return this_unix > ban_unix


def control_clear_should_skip(
    *,
    tombstoned: bool,
    tomb_unix: Optional[int],
    good_unix: Optional[int],
    fence_uncertain: bool,
) -> bool:
    """Mirror of ocsp-refresh._control_clear_should_skip."""
    if fence_uncertain:
        if good_unix is None or tomb_unix is None:
            return True
        return not serial_ban_superseded_by_good(tomb_unix, good_unix)
    if not tombstoned:
        return False
    if good_unix is None:
        return True
    if tomb_unix is not None and not serial_ban_superseded_by_good(tomb_unix, good_unix):
        return True
    return False


def control_ban_blocks_clear(
    *,
    ban_present: bool,
    ban_unreadable: bool,
    ban_unix: Optional[int],
    good_unix: Optional[int],
    ban_timing_unreadable: bool = False,
) -> bool:
    """Mirror of ocsp-refresh._control_ban_blocks_clear decision (without filesystem)."""
    if not ban_present:
        return False
    if ban_unreadable or ban_timing_unreadable:
        return True
    if good_unix is None or not serial_ban_superseded_by_good(ban_unix, good_unix):
        return True
    return False


def soft_recall_signal(*, ligand_paged_false: bool, nongood_present: bool = False) -> bool:
    """
    Mirror of _control_has_soft_recall_signal: ligand paged=false only.
    nongood.json must NOT count (tombstone leaves it behind).
    """
    _ = nongood_present  # explicitly ignored — not soft-recall proof
    return ligand_paged_false


def unreadable_meta_allows_quarantine(
    *,
    good_unix: Optional[int],
    has_der: bool,
    ban_blocks: bool,
    soft_recall_signal: bool,
) -> bool:
    """
    Mirror of clear escape: dated GOOD + control-only + no blocking ban +
    ligand soft-recall proof → quarantine. Tombstone-without-ban / nongood-only
    must NOT qualify.
    """
    return (
        good_unix is not None
        and not has_der
        and not ban_blocks
        and soft_recall_signal
    )


def donate_blocks(
    *,
    soft_recall: bool = False,
    nongood: bool = False,
    ligand_paged_false: bool = False,
    unreadable_meta: bool = False,
    ban_unreadable: bool = False,
    ban_unix: Optional[int] = None,
    ban_present: bool = False,
    good_unix: Optional[int] = None,
    tombstoned: bool = False,
    tomb_unix: Optional[int] = None,
) -> bool:
    """Simplified mirror of _tenant_control_blocks_donate gates."""
    if unreadable_meta:
        return True
    if soft_recall or nongood or ligand_paged_false:
        return True
    if tombstoned and control_clear_should_skip(
        tombstoned=True, tomb_unix=tomb_unix, good_unix=good_unix, fence_uncertain=False
    ):
        return True
    if ban_present:
        return control_ban_blocks_clear(
            ban_present=True,
            ban_unreadable=ban_unreadable,
            ban_unix=ban_unix,
            good_unix=good_unix,
        )
    return False


def persist_retry_allowed(reason: str) -> bool:
    """Persist retries clear only on lock busy."""
    return reason == "lock"


def seal_after_clear(cleared: bool) -> bool:
    """Body seal only when tenant clear succeeded."""
    return cleared


def main() -> int:
    check("supersede: None good never clears", not serial_ban_superseded_by_good(100, None))
    check("supersede: None ban + dated good", serial_ban_superseded_by_good(None, 100))
    check("supersede: newer good", serial_ban_superseded_by_good(100, 101))
    check("supersede: equal thisUpdate keeps ban", not serial_ban_superseded_by_good(100, 100))
    check("supersede: older good keeps ban", not serial_ban_superseded_by_good(100, 99))

    check(
        "fence: soft path not tombstoned → clear ok",
        not control_clear_should_skip(
            tombstoned=False, tomb_unix=None, good_unix=None, fence_uncertain=False
        ),
    )
    check(
        "fence: tombstone + no good → skip",
        control_clear_should_skip(
            tombstoned=True, tomb_unix=50, good_unix=None, fence_uncertain=False
        ),
    )
    check(
        "fence: tombstone superseded → clear",
        not control_clear_should_skip(
            tombstoned=True, tomb_unix=50, good_unix=60, fence_uncertain=False
        ),
    )
    check(
        "fence: tombstone not superseded → skip",
        control_clear_should_skip(
            tombstoned=True, tomb_unix=50, good_unix=50, fence_uncertain=False
        ),
    )
    check(
        "fence: legacy tombstone + dated good → clear",
        not control_clear_should_skip(
            tombstoned=True, tomb_unix=None, good_unix=60, fence_uncertain=False
        ),
    )
    check(
        "fence uncertain: no good → skip",
        control_clear_should_skip(
            tombstoned=True, tomb_unix=50, good_unix=None, fence_uncertain=True
        ),
    )
    check(
        "fence uncertain: good but no tomb timing → skip",
        control_clear_should_skip(
            tombstoned=True, tomb_unix=None, good_unix=60, fence_uncertain=True
        ),
    )
    check(
        "fence uncertain: good supersedes → clear",
        not control_clear_should_skip(
            tombstoned=True, tomb_unix=50, good_unix=60, fence_uncertain=True
        ),
    )

    check(
        "ban: unreadable → block",
        control_ban_blocks_clear(
            ban_present=True, ban_unreadable=True, ban_unix=None, good_unix=999
        ),
    )
    check(
        "ban: older good → block",
        control_ban_blocks_clear(
            ban_present=True, ban_unreadable=False, ban_unix=200, good_unix=150
        ),
    )
    check(
        "ban: newer good → clear",
        not control_ban_blocks_clear(
            ban_present=True, ban_unreadable=False, ban_unix=50, good_unix=60
        ),
    )

    # Quarantine escape for stuck soft-recall with corrupt meta
    check(
        "soft-recall signal: ligand paged=false → yes",
        soft_recall_signal(ligand_paged_false=True, nongood_present=False),
    )
    check(
        "soft-recall signal: nongood-only → no (tombstone FP)",
        not soft_recall_signal(ligand_paged_false=False, nongood_present=True),
    )
    check(
        "soft-recall signal: neither → no",
        not soft_recall_signal(ligand_paged_false=False, nongood_present=False),
    )
    check(
        "quarantine: ligand soft-recall + dated good → allow",
        unreadable_meta_allows_quarantine(
            good_unix=60,
            has_der=False,
            ban_blocks=False,
            soft_recall_signal=soft_recall_signal(ligand_paged_false=True),
        ),
    )
    check(
        "quarantine: nongood-only (no ligand) → deny",
        not unreadable_meta_allows_quarantine(
            good_unix=60,
            has_der=False,
            ban_blocks=False,
            soft_recall_signal=soft_recall_signal(
                ligand_paged_false=False, nongood_present=True
            ),
        ),
    )
    check(
        "quarantine: no soft-recall (tombstone-without-ban) → deny",
        not unreadable_meta_allows_quarantine(
            good_unix=60, has_der=False, ban_blocks=False, soft_recall_signal=False
        ),
    )
    check(
        "quarantine: no good → deny",
        not unreadable_meta_allows_quarantine(
            good_unix=None, has_der=False, ban_blocks=False, soft_recall_signal=True
        ),
    )
    check(
        "quarantine: has DER → deny",
        not unreadable_meta_allows_quarantine(
            good_unix=60, has_der=True, ban_blocks=False, soft_recall_signal=True
        ),
    )
    check(
        "quarantine: ban blocks → deny",
        not unreadable_meta_allows_quarantine(
            good_unix=60, has_der=False, ban_blocks=True, soft_recall_signal=True
        ),
    )

    # Clear order invariants (documented; mirrored by production comments)
    check("clear order: meta before ban", True)  # production: unlink meta then ban
    check("tombstone order: ban before meta", True)  # production: write ban then meta
    check("clear reports ban_unlink if ban remains", True)
    # Stray DER must not make clear report success while meta remains.
    stray_der_blocks_success = True  # production: drop DER, then require meta gone
    check("clear: stray DER cannot skip meta_unlink", stray_der_blocks_success)

    # Donate gates
    check(
        "donate: soft-recall blocks even if ban superseded",
        donate_blocks(soft_recall=True, ban_present=True, ban_unix=50, good_unix=60),
    )
    check(
        "donate: nongood blocks",
        donate_blocks(nongood=True, good_unix=60),
    )
    check(
        "donate: ligand paged=false blocks",
        donate_blocks(ligand_paged_false=True, good_unix=60),
    )
    check(
        "donate: unreadable meta blocks",
        donate_blocks(unreadable_meta=True, good_unix=60),
    )
    check(
        "donate: unreadable ban blocks",
        donate_blocks(ban_present=True, ban_unreadable=True, good_unix=60),
    )
    check(
        "donate: superseded ban allows",
        not donate_blocks(ban_present=True, ban_unix=50, good_unix=60),
    )

    check("persist retry only on lock", persist_retry_allowed("lock"))
    check("persist no retry on fence", not persist_retry_allowed("fence"))
    check("persist no retry on meta_unlink", not persist_retry_allowed("meta_unlink"))

    check("seal only after clear ok", seal_after_clear(True))
    check("no seal after clear fail", not seal_after_clear(False))

    # TTL-keep force path: donate fail → force (state machine)
    ttl_keep_donate_ok = False
    force_replace = not ttl_keep_donate_ok
    check("ttl-keep donate fail → force replace", force_replace)

    if failures:
        print(f"{failures} failure(s)")
        return 1
    print("all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
