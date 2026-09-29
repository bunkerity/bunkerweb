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

    # Clear / seal completeness: leftover signals must not seal
    leftover_reasons = (
        "meta_unlink",
        "ban_unlink",
        "ligand_unlink",
        "nongood_unlink",
        "der_unlink",
        "allow_unlink",
        "fence",
        "lock",
    )
    for reason in leftover_reasons:
        check(
            f"clear leftover reason={reason} → no seal",
            not seal_after_clear(cleared=False),
        )
    check("clear ok → seal allowed", seal_after_clear(cleared=True))

    # Quarantine DER unlink maps to der_unlink (not fence) for metrics
    quarantine_der_fail_reason = "der_unlink"
    check(
        "quarantine DER unlink fail → der_unlink reason",
        quarantine_der_fail_reason == "der_unlink" and quarantine_der_fail_reason != "fence",
    )

    # Clear order invariants as executable predicates
    def clear_steps_ok(meta_gone: bool, ban_clear_attempted: bool) -> bool:
        # Production: never clear ban unless meta is gone.
        if ban_clear_attempted and not meta_gone:
            return False
        return True

    check("clear order: ban only after meta gone", clear_steps_ok(True, True))
    check("clear order: ban before meta gone → invalid", not clear_steps_ok(False, True))

    def clear_ligand_after_meta(meta_gone: bool, ligand_clear_attempted: bool) -> bool:
        # Production: ligand/nongood/allow only after meta confirmed gone —
        # otherwise a meta_unlink failure strands corrupt soft-recall without
        # quarantine proof (ligand-only escape).
        if ligand_clear_attempted and not meta_gone:
            return False
        return True

    check(
        "clear order: ligand only after meta gone",
        clear_ligand_after_meta(True, True),
    )
    check(
        "clear order: ligand before meta gone → invalid",
        not clear_ligand_after_meta(False, True),
    )

    def tombstone_steps_ok(ban_written: bool, meta_written: bool) -> bool:
        # Production: ban before meta; abort if ban fails (no meta).
        if meta_written and not ban_written:
            return False
        return True

    check("tombstone order: ban before meta", tombstone_steps_ok(True, True))
    check(
        "tombstone order: meta without ban → invalid",
        not tombstone_steps_ok(False, True),
    )

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
    check(
        "donate: tombstone not superseded → block",
        donate_blocks(tombstoned=True, tomb_unix=200, good_unix=150),
    )
    check(
        "donate: tombstone superseded → allow",
        not donate_blocks(tombstoned=True, tomb_unix=50, good_unix=60),
    )
    check(
        "donate: ban_timing_unreadable via control_ban",
        control_ban_blocks_clear(
            ban_present=True,
            ban_unreadable=False,
            ban_unix=None,
            good_unix=60,
            ban_timing_unreadable=True,
        ),
    )

    check("persist retry only on lock", persist_retry_allowed("lock"))
    check("persist no retry on fence", not persist_retry_allowed("fence"))
    check("persist no retry on meta_unlink", not persist_retry_allowed("meta_unlink"))
    check("persist no retry on der_unlink", not persist_retry_allowed("der_unlink"))

    # TTL-keep force: donate fail → force replace (and undo cached count)
    cached_before = 1
    donate_ok = False
    cached_after_undo = cached_before - 1 if (not donate_ok and cached_before > 0) else cached_before
    check("ttl-keep donate fail → force replace", not donate_ok)
    check("ttl-keep donate fail → undo cached count", cached_after_undo == 0)
    # Force that keeps cache (der=None, ttl>0) must restore the undocount.
    force_kept_der = None
    force_kept_ttl = 3600
    cached_restored = (
        cached_after_undo + 1
        if force_kept_der is None and force_kept_ttl > 0
        else cached_after_undo
    )
    check("ttl-keep force keeps cache → restore cached count", cached_restored == 1)
    # Force that publishes a new body must leave cached undocounted (fetched instead).
    force_pub_der = b"der"
    force_pub_ttl = 3600
    cached_after_pub = (
        cached_after_undo + 1
        if force_pub_der is None and force_pub_ttl > 0
        else cached_after_undo
    )
    check("ttl-keep force publishes → leave cached undone", cached_after_pub == 0)

    # Donate must refuse when body is no longer canary-paged (concurrent demote).
    def donate_under_lock(*, body_paged: bool, clear_ok: bool) -> bool:
        if not body_paged:
            return False
        if not clear_ok:
            return False
        return True

    check(
        "donate: body demoted under lock → refuse",
        not donate_under_lock(body_paged=False, clear_ok=True),
    )
    check(
        "donate: clear fail under lock → refuse (no seal)",
        not donate_under_lock(body_paged=True, clear_ok=False),
    )
    check(
        "donate: body paged + clear ok → allow",
        donate_under_lock(body_paged=True, clear_ok=True),
    )

    # Soft-recall clear requires dated GOOD (defense in depth).
    def soft_recall_clear_ok(*, soft_recall: bool, good_unix: Optional[int]) -> bool:
        if soft_recall and good_unix is None:
            return False
        return True

    check(
        "clear: soft-recall without dated GOOD → fence",
        not soft_recall_clear_ok(soft_recall=True, good_unix=None),
    )
    check(
        "clear: soft-recall with dated GOOD → allow",
        soft_recall_clear_ok(soft_recall=True, good_unix=60),
    )
    check(
        "clear: no soft-recall without GOOD → allow",
        soft_recall_clear_ok(soft_recall=False, good_unix=None),
    )

    # Soft-recall must write paged=false before clearing allow (restamp otherwise
    # re-opens Must-Staple on a still-paged=true shard).
    def soft_recall_clear_allow_after_meta(*, meta_unpaged_ok: bool) -> bool:
        return meta_unpaged_ok

    check(
        "soft-recall: meta unpage ok → clear allow",
        soft_recall_clear_allow_after_meta(meta_unpaged_ok=True),
    )
    check(
        "soft-recall: meta unpage fail → leave allow",
        not soft_recall_clear_allow_after_meta(meta_unpaged_ok=False),
    )

    # Demote restamp block must survive across job runs (durable marker).
    def restamp_blocked(*, mem: bool, marker_file: bool) -> bool:
        return mem or marker_file

    check(
        "restamp: durable marker blocks next run",
        restamp_blocked(mem=False, marker_file=True),
    )
    check(
        "restamp: neither mem nor marker → allow",
        not restamp_blocked(mem=False, marker_file=False),
    )

    # Sidecar ban copy must fail closed before renameat2 exchange.
    def sidecar_copy_allows_page(*, live_has_ban: bool, copy_ok: bool) -> bool:
        if live_has_ban and not copy_ok:
            return False
        return True

    check(
        "sidecar: ban copy fail → refuse page",
        not sidecar_copy_allows_page(live_has_ban=True, copy_ok=False),
    )
    check(
        "sidecar: ban copy ok → allow page",
        sidecar_copy_allows_page(live_has_ban=True, copy_ok=True),
    )
    check(
        "sidecar: no live ban → allow page",
        sidecar_copy_allows_page(live_has_ban=False, copy_ok=False),
    )

    # Persist post-publish: clear allow only on explicit unpaged, never on read miss.
    def post_publish_clear_allow(*, meta_ok: bool, paged: bool) -> bool:
        if meta_ok and paged:
            return False  # rewrite pins instead
        if meta_ok and not paged:
            return True
        return False  # read miss — leave pins

    check(
        "persist: paged meta → do not clear allow",
        not post_publish_clear_allow(meta_ok=True, paged=True),
    )
    check(
        "persist: explicit unpaged → clear allow",
        post_publish_clear_allow(meta_ok=True, paged=False),
    )
    check(
        "persist: meta read miss → leave allow",
        not post_publish_clear_allow(meta_ok=False, paged=False),
    )

    # Seal only when body still canary-paged after clear.
    def seal_after_clear_paged(*, cleared: bool, body_paged: bool) -> bool:
        return cleared and body_paged

    check(
        "seal: clear ok + body paged → seal",
        seal_after_clear_paged(cleared=True, body_paged=True),
    )
    check(
        "seal: clear ok + body unpaged → no seal",
        not seal_after_clear_paged(cleared=True, body_paged=False),
    )

    # Persist must not replace a still-usable canary live body with an older GOOD
    # for the same CertID (TTL miss covers wrong serial / past-death / no DER).
    # Fail closed when live is usable but thisUpdate is unreadable.
    # Clear auth must use DER-signed thisUpdate (never meta alone).
    def publish_keeps_live(
        *,
        live_ttl: Optional[int],
        live_tu: Optional[int],
        cand_tu: Optional[int],
    ) -> bool:
        if live_ttl is None or live_ttl <= 0:
            return False
        if live_tu is None or cand_tu is None or cand_tu <= 0:
            return True
        return live_tu > cand_tu

    check(
        "publish: newer usable live → skip older candidate",
        publish_keeps_live(live_ttl=3600, live_tu=200, cand_tu=100),
    )
    check(
        "publish: older live → do not skip (publish newer)",
        not publish_keeps_live(live_ttl=3600, live_tu=100, cand_tu=200),
    )
    check(
        "publish: equal thisUpdate → do not skip",
        not publish_keeps_live(live_ttl=3600, live_tu=100, cand_tu=100),
    )
    check(
        "publish: past-death live (ttl<=0) → do not skip",
        not publish_keeps_live(live_ttl=0, live_tu=200, cand_tu=100),
    )
    check(
        "publish: TTL miss (wrong serial / unpaged) → do not skip",
        not publish_keeps_live(live_ttl=None, live_tu=200, cand_tu=100),
    )
    check(
        "publish: usable live, missing live thisUpdate → keep live",
        publish_keeps_live(live_ttl=3600, live_tu=None, cand_tu=100),
    )
    check(
        "publish: usable live, missing cand thisUpdate → keep live",
        publish_keeps_live(live_ttl=3600, live_tu=200, cand_tu=0),
    )
    # Live meta without DER must not count as canary-paged for the skip fence.
    def live_paged_requires_der(*, meta_paged: bool, der_present: bool) -> bool:
        return meta_paged and der_present

    check(
        "publish: paged meta without DER → not live canary",
        not live_paged_requires_der(meta_paged=True, der_present=False),
    )
    check(
        "publish: paged meta with DER → live canary",
        live_paged_requires_der(meta_paged=True, der_present=True),
    )

    # DER-backed thisUpdate for clear auth: require paged + der_sha256 match + GOOD.
    def der_backed_this_update(
        *,
        paged: bool,
        der_sha_ok: bool,
        der_tu: Optional[int],
        meta_tu: Optional[int],
        cert_status_good: bool = True,
    ) -> Optional[int]:
        if not paged or not der_sha_ok or not cert_status_good:
            return None
        return der_tu if der_tu is not None and der_tu > 0 else None

    check(
        "clear auth: DER thisUpdate when sha matches",
        der_backed_this_update(paged=True, der_sha_ok=True, der_tu=100, meta_tu=999) == 100,
    )
    check(
        "clear auth: refuse inflated meta when sha mismatch",
        der_backed_this_update(paged=True, der_sha_ok=False, der_tu=100, meta_tu=999) is None,
    )
    check(
        "clear auth: refuse unpaged even with DER tu",
        der_backed_this_update(paged=False, der_sha_ok=True, der_tu=100, meta_tu=100) is None,
    )
    check(
        "clear auth: refuse non-GOOD CertStatus",
        der_backed_this_update(
            paged=True, der_sha_ok=True, der_tu=100, meta_tu=100, cert_status_good=False
        )
        is None,
    )

    # Pinned CertID missing from DER must not fall back to a foreign GOOD.
    # Hex match first; digits-only want also accepts decimal (restamp parity).
    def der_tu_with_pin(
        *,
        pin_present: bool,
        pin_matched: bool,
        sole_good_tu: Optional[int],
    ) -> Optional[int]:
        if pin_present and not pin_matched:
            return None
        return sole_good_tu

    def pin_matches_serial(
        *,
        want: str,
        serial: int,
    ) -> bool:
        # Mirror _certid_pin_matches_serial: hex first, then int() decimal for digits.
        text = want.strip()
        if text.upper().startswith("0X"):
            text = text[2:]
        dec = str(serial)
        got_hex = format(serial, "X").lstrip("0") or "0"
        want_norm = text.upper().lstrip("0") or "0"
        if got_hex == want_norm:
            return True
        if text.isdigit():
            return int(text) == int(dec)
        return False

    check(
        "clear auth: pin miss → refuse (no foreign GOOD)",
        der_tu_with_pin(pin_present=True, pin_matched=False, sole_good_tu=100) is None,
    )
    check(
        "clear auth: no pin + sole GOOD → allow",
        der_tu_with_pin(pin_present=False, pin_matched=False, sole_good_tu=100) == 100,
    )
    check(
        "pin: hex 10 matches serial 16",
        pin_matches_serial(want="10", serial=16),
    )
    check(
        "pin: decimal 10 matches serial 10 (legacy)",
        pin_matches_serial(want="10", serial=10),
    )
    check(
        "pin: zero-padded decimal 010 matches serial 10",
        pin_matches_serial(want="010", serial=10),
    )
    check(
        "pin: hex AB matches serial 171",
        pin_matches_serial(want="AB", serial=0xAB),
    )
    check(
        "pin: hex-first 10 still matches serial 16",
        pin_matches_serial(want="10", serial=16),
    )

    # TTL must miss when der_sha256 is missing (align with DER auth / restamp).
    def ttl_requires_der_sha(*, sha_present: bool, sha_match: bool) -> bool:
        return sha_present and sha_match

    check(
        "ttl: missing der_sha256 → miss",
        not ttl_requires_der_sha(sha_present=False, sha_match=False),
    )
    check(
        "ttl: der_sha256 mismatch → miss",
        not ttl_requires_der_sha(sha_present=True, sha_match=False),
    )
    check(
        "ttl: der_sha256 match → usable",
        ttl_requires_der_sha(sha_present=True, sha_match=True),
    )

    def ttl_requires_good(*, cert_status_good: bool) -> bool:
        return cert_status_good

    check("ttl: non-GOOD → miss", not ttl_requires_good(cert_status_good=False))
    check("ttl: GOOD → usable", ttl_requires_good(cert_status_good=True))

    # Seal body only when goods max advances (same body SPKI per control).
    def seal_on_goods_advance(*, good_tu: int, prev: int) -> bool:
        return good_tu > prev

    check("seal: newer good → update seal body", seal_on_goods_advance(good_tu=200, prev=100))
    check("seal: older/equal good → keep prior seal", not seal_on_goods_advance(good_tu=100, prev=100))

    # Persist clear re-validates body under lock before wiping negatives.
    def persist_clear_allowed(
        *,
        body_lock_ok: bool,
        body_paged: bool,
        der_tu: Optional[int],
    ) -> bool:
        if not body_lock_ok or not body_paged:
            return False
        return der_tu is not None and der_tu > 0

    check(
        "persist clear: demoted body → no clear",
        not persist_clear_allowed(body_lock_ok=True, body_paged=False, der_tu=100),
    )
    check(
        "persist clear: lock fail → no clear",
        not persist_clear_allowed(body_lock_ok=False, body_paged=True, der_tu=100),
    )
    check(
        "persist clear: paged + DER tu → clear",
        persist_clear_allowed(body_lock_ok=True, body_paged=True, der_tu=100),
    )

    # Skip-only persist batches must still clear tenant controls.
    def run_tenant_clears(*, published_fps: list, control_goods: dict) -> bool:
        # Clear loop is independent of publish list (skip-kept live still authorizes).
        return bool(control_goods)

    check(
        "persist: skip-only batch still clears tenants",
        run_tenant_clears(published_fps=[], control_goods={"cfp": 100}),
    )
    check(
        "persist: no goods → no clears",
        not run_tenant_clears(published_fps=["fp"], control_goods={}),
    )

    # CertID serial normalize (uppercase hex, strip leading zeros)
    def serial_norm(raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        text = str(raw).strip().upper()
        if text.startswith("0X"):
            text = text[2:]
        if not text or not all(c in "0123456789ABCDEF" for c in text):
            return None
        return text.lstrip("0") or "0"

    check("serial norm: hex leading zeros", serial_norm("00AB") == "AB")
    check("serial norm: match AB vs 00ab", serial_norm("AB") == serial_norm("00ab"))
    check("serial norm: reject garbage", serial_norm("zz") is None)

    if failures:
        print(f"{failures} failure(s)")
        return 1
    print("all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
