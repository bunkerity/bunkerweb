#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime, timedelta
from hashlib import sha512
from hmac import compare_digest
from os import getenv
from secrets import token_urlsafe
from typing import Any, Dict, List, Optional, Tuple

from model import Instances, Metadata  # type: ignore

from certificate_utils import decrypt_private_key, encrypt_private_key  # type: ignore
from common_utils import is_valid_host  # type: ignore

from cryptography.exceptions import InvalidTag

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import OperationalError, ProgrammingError

from .common import DatabaseMixinBase

# Secure enrollment (Tier B). Fixed module constants rather than settings: an operator knob on a
# credential-issuing TTL is a way to weaken it by accident, and nobody has asked for one.
ENROLLMENT_TTL_DEFAULT = 900  # 15 min, the GitLab CVE-2022-0735 lesson: a join token is short-lived
ENROLLMENT_TTL_MAX = 3600
# Best-effort, not a hard cap: the failure write is server-side (`enroll_failures + 1`) but is
# deliberately allowed to fail without failing the redemption, so a lost commit under contention
# just does not count. The real bound on guessing is the rate limit on POST /instances/enroll plus
# the TTL -- roughly 150 attempts against a 256-bit code, which is not a threat. This exists to end
# a code that is visibly being guessed, not to be a counter you can rely on.
ENROLLMENT_MAX_FAILURES = 5
# Methods whose rows the control plane owns, and the only ones enrollment applies to. `manual`
# joined them on the PO ruling of 2026-09-02: an instance declared through BUNKERWEB_INSTANCES /
# BUNKERWEB_INSTANCE_* -- the Docker and Linux default -- must be enrollable. That is only safe
# because `update_instances()` now carries the columns below across the rebuild it does of its own
# rows, so the `save_config.py` reconcile no longer drops a minted credential on every config save.
# `autoconf` stays out: those rows are re-sourced from a live orchestrator on every reconcile, and
# keeping a stale per-instance credential there would lock the control plane out of a healthy
# instance that dropped its API_TOKEN.
# This is NO LONGER the same set as `UI_API_METHODS` in the API router: that one answers "can the
# control plane DELETE this row", which stays {ui, api}. Two questions, two sets, on purpose.
ENROLLABLE_METHODS = ("ui", "api", "manual")
# What the control plane owns on an enrollable row and no environment can re-source. A reconcile
# keeps these for a hostname that is still declared and drops them with the row for one that has
# disappeared, which is the only way an enrollment is ever dropped by a rebuild.
# The two lists are treated differently on purpose. The ENROLLMENT ones are never written by the
# rebuild at all -- a still-declared row is UPDATEd in place, never deleted and re-INSERTed, so they
# survive by not being touched, and a future enroll_* column is preserved without anyone having to
# remember to add it here. The CREDENTIAL ones must be listed, because `_reconcile_credential_columns`
# does write them (a declared API_TOKEN wins) and needs to know what to carry when there is none.
# One exception, and only one: `credential_revoked_at` is written -- cleared -- when the environment
# re-sources the credential, because the revocation belongs to the credential it revoked and leaving
# it standing locks the control plane out of the row for good. See `_reconcile_credential_columns`.
# The pin in `tests/unit/db/test_instance_enrollment_preservation.py` asserts that every enroll_*/
# credential_* column on the table is accounted for by one of the two.
PRESERVED_ENROLLMENT_COLUMNS = ("enroll_code_state", "enroll_token_hash", "enroll_token_expires_at", "enroll_failures", "credential_revoked_at")
PRESERVED_CREDENTIAL_COLUMNS = ("credential_ciphertext", "credential_nonce", "credential_key_id", "credential_updated_at")
# Uniform failure answer: the redeem route must not tell an unauthenticated caller whether a
# hostname exists, whether its code expired, or whether it simply guessed wrong.
ENROLLMENT_REJECTED = "invalid or expired enrollment code"


def hash_enrollment_code(code: str) -> str:
    """SHA-512 hex digest of a join code. The code itself is never stored."""
    return sha512(code.encode("utf-8")).hexdigest()


def derive_enrollment_state(enroll_code_state: str, credential_set: bool, credential_revoked_at: Optional[datetime]) -> str:
    """Fold the three stored facts back into the one string the API and the UI still read.

    Presentation only -- nothing in this module branches on the result, and `API.request()`
    reads `credential_revoked` instead, so a freshly issued code can no longer un-revoke a dial.
    The order reproduces exactly what the old single column stored: issuing a code on an
    already-enrolled or revoked row stamped "pending", so a pending code wins over both.
    """
    if enroll_code_state == "pending":
        return "pending"
    if credential_revoked_at is not None:
        return "revoked"
    return "enrolled" if credential_set else "none"


class DatabaseInstancesMixin(DatabaseMixinBase):
    """BunkerWeb instance registry management."""

    def add_instance(
        self,
        hostname: str,
        port: int,
        server_name: str,
        method: str,
        changed: Optional[bool] = True,
        *,
        name: Optional[str] = None,
        listen_https: bool = False,
        https_port: int = 5443,
        credential: Optional[str] = None,
        tls_mode: Optional[str] = None,
        tls_fingerprint: Optional[str] = None,
    ) -> str:
        """Add instance."""
        if not is_valid_host(hostname):
            return f"Invalid instance hostname: {hostname}"

        # Resolve the keyring before the session: reading the metadata-backed keyring opens
        # one of its own and `_db_session` is not reentrant (see _decrypt_instance_credential).
        keyring = self._keyring_values()

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instance = session.execute(select(Instances.hostname).filter_by(hostname=hostname).limit(1)).first()

            if db_instance is not None:
                return f"Instance {hostname} already exists, will not be added."

            credential_columns: Dict[str, Any] = {}
            if credential:
                encrypted = self._encrypt_instance_credential(hostname, credential, keyring)
                if encrypted is not None:
                    ciphertext, nonce, key_id = encrypted
                    credential_columns = {
                        "credential_ciphertext": ciphertext,
                        "credential_nonce": nonce,
                        "credential_key_id": key_id,
                        "credential_updated_at": datetime.now().astimezone(),
                    }
                # else: encryption unavailable (already logged); the instance falls back to the global token

            current_time = datetime.now().astimezone()
            session.add(
                Instances(
                    hostname=hostname,
                    name=name or "manual instance",
                    port=port,
                    listen_https=listen_https,
                    https_port=https_port,
                    server_name=server_name,
                    method=method,
                    creation_date=current_time,
                    last_seen=current_time,
                    tls_mode=tls_mode or "off",
                    tls_fingerprint=tls_fingerprint or None,
                    **credential_columns,
                )
            )

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.get(Metadata, 1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while adding the instance {hostname} (port: {port}, server name: {server_name}, method: {method}).\n{e}"

        return ""

    def delete_instances(self, hostnames: List[str], changed: Optional[bool] = True) -> str:
        """Delete instances."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instances = session.scalars(select(Instances).where(Instances.hostname.in_(hostnames))).all()

            if not db_instances:
                return "No instances found to delete."

            for db_instance in db_instances:
                session.delete(db_instance)

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.get(Metadata, 1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while deleting the instances {', '.join(hostnames)}.\n{e}"

        return ""

    def delete_instance(self, hostname: str, changed: Optional[bool] = True) -> str:
        """Delete instance."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instance = session.scalars(select(Instances).filter_by(hostname=hostname).limit(1)).first()

            if db_instance is None:
                return f"Instance {hostname} does not exist, will not be deleted."

            session.delete(db_instance)

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.get(Metadata, 1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while deleting the instance {hostname}.\n{e}"

        return ""

    def update_instances(self, instances: List[Dict[str, Any]], method: str, changed: Optional[bool] = True) -> str:
        """Update instances."""
        for instance in instances:
            hostname = instance.get("hostname")
            if hostname is not None and not is_valid_host(hostname):
                return f"Invalid instance hostname: {hostname}"

        to_put = []
        # Resolve the keyring before the session: reading the metadata-backed keyring opens
        # one of its own and `_db_session` is not reentrant (see _decrypt_instance_credential).
        keyring = self._keyring_values()
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if not instances and method == "autoconf":
                existing_count = session.scalar(select(func.count()).select_from(Instances).where(Instances.method == method))
                if existing_count > 0:
                    self.logger.warning(
                        f"Received empty instances list for method 'autoconf' but database has {existing_count} existing instance(s), "
                        "skipping deletion to prevent data loss"
                    )
                    return ""

            # Delete only what disappeared from the roster; a hostname that is still declared keeps
            # its row and is updated in place below. `save_config.py` sends the whole `manual` roster
            # again on every scheduler config save, and the old shape -- DELETE every row of this
            # method, then re-INSERT -- dropped a minted credential and the enrollment that produced
            # it on each of those saves (PO ruling 2026-09-02). Updating in place fixes that without
            # a snapshot, which matters: a snapshot taken before the DELETE is stale for anything
            # that commits while the rebuild runs (a redemption, a rotation), and writing it back
            # would recreate exactly the lockout this is here to prevent. It also stops
            # `creation_date` churning on every config save for a row that never went away.
            declared = {instance["hostname"] for instance in instances if instance.get("hostname")}
            deletion = delete(Instances).where(Instances.method == method)
            if declared:
                deletion = deletion.where(Instances.hostname.notin_(declared))
            session.execute(deletion)

            global_token = getenv("API_TOKEN")

            for instance in instances:
                if instance.get("hostname") is None:
                    continue

                current_time = datetime.now().astimezone()

                db_instance = session.scalars(select(Instances).filter_by(hostname=instance["hostname"]).limit(1)).first()
                row_method = db_instance.method if db_instance is not None else None
                if (
                    db_instance is not None
                    and row_method != method
                    and (
                        db_instance.enroll_code_state != "none"
                        or db_instance.credential_ciphertext is not None
                        or db_instance.credential_revoked_at is not None
                    )
                ):
                    # The row belongs to ANOTHER method -- it is a control-plane-owned row that
                    # happens to share a hostname with something the reconcile discovered. (A row of
                    # this reconcile's own method now survives too, and is updated in place instead:
                    # that is the preservation, and it must not be skipped here or a still-declared
                    # enrolled instance would stop picking up its own declared ports.)
                    # Rewriting it would flip its method and let
                    # `_reconcile_credential_columns` clear the minted credential: the dial would
                    # then fall back to the global token, the instance would refuse it, and nothing
                    # would report it. The `credential_revoked_at` arm keeps the documented
                    # behaviour that a revoked row stays invisible to the reconcile until the
                    # revocation is lifted or the row deleted (report-L-A §6b).
                    self.logger.warning(f"Instance {instance['hostname']} carries a control-plane enrollment; the {method} reconcile will not take it over")
                    continue
                if db_instance is not None:
                    db_instance.name = instance.get("name", "manual instance")
                    db_instance.port = instance["env"].get("API_HTTP_PORT", 5000)
                    db_instance.listen_https = instance["env"].get("API_LISTEN_HTTPS", "no") == "yes"
                    db_instance.https_port = instance["env"].get("API_HTTPS_PORT", 5443)
                    db_instance.server_name = instance["env"].get("API_SERVER_NAME", "bwapi")
                    db_instance.type = instance.get("type", "static")
                    db_instance.status = instance.get("status", "up" if instance.get("health", True) else "down")
                    db_instance.method = instance.get("method", method)
                    db_instance.last_seen = instance.get("last_seen", current_time)
                    # Only when the caller declares them: an autoconf reconcile carries no TLS keys
                    # and must not reset a row's pinning to "off" behind the operator's back.
                    if "tls_mode" in instance:
                        db_instance.tls_mode = instance["tls_mode"] or "off"
                    if "tls_fingerprint" in instance:
                        db_instance.tls_fingerprint = instance["tls_fingerprint"] or None
                    # Enrollment columns are deliberately absent from the assignments above: an
                    # updated-in-place row keeps them untouched. The credential columns are not, so
                    # they are handed back explicitly -- otherwise a row the environment declares no
                    # API_TOKEN for would be cleared, which is the original bug. `None` for a row of
                    # another method, and for `autoconf`, whose credential really is re-sourced from
                    # its orchestrator on every reconcile.
                    carried = (
                        {column: getattr(db_instance, column) for column in PRESERVED_CREDENTIAL_COLUMNS}
                        if row_method == method and method in ENROLLABLE_METHODS
                        else None
                    )
                    reconciled = self._reconcile_credential_columns(instance["hostname"], instance.get("env"), global_token, keyring, carried)
                    # Lifting a revocation is a security control being switched back off, so it says
                    # so. The warning inside `_reconcile_credential_columns` cannot cover this: a
                    # revoke NULLs the credential columns, so `preserved["credential_ciphertext"]`
                    # is empty and the "replacing a stored credential" branch never runs. The row
                    # object here is the only place that still knows the stamp was there.
                    if db_instance.credential_revoked_at is not None and reconciled.get("credential_revoked_at", "keep") is None:
                        self.logger.warning(
                            f"Instance {instance['hostname']} was revoked but declares its own API token in its environment; "
                            "the environment re-sources the credential, so the revocation is being lifted. Remove the declared "
                            "token if the revocation is meant to hold."
                        )
                    for column, value in reconciled.items():
                        setattr(db_instance, column, value)
                    to_put.append(db_instance)
                    continue

                to_put.append(
                    Instances(
                        hostname=instance["hostname"],
                        name=instance.get("name", "manual instance"),
                        port=instance["env"].get("API_HTTP_PORT", 5000),
                        listen_https=instance["env"].get("API_LISTEN_HTTPS", "no") == "yes",
                        https_port=instance["env"].get("API_HTTPS_PORT", 5443),
                        server_name=instance["env"].get("API_SERVER_NAME", "bwapi"),
                        type=instance.get("type", "static"),
                        status=instance.get("status", "up" if instance.get("health", True) else "down"),
                        method=instance.get("method", method),
                        creation_date=instance.get("creation_date", current_time),
                        last_seen=instance.get("last_seen", current_time),
                        tls_mode=instance.get("tls_mode") or "off",
                        tls_fingerprint=instance.get("tls_fingerprint") or None,
                        # A hostname the roster did not carry before: the enrollment and credential
                        # columns take the model defaults ("none" / 0 / NULL). Nothing to preserve --
                        # a still-declared hostname never reaches this branch, it is updated above.
                        **self._reconcile_credential_columns(instance["hostname"], instance.get("env"), global_token, keyring),
                    )
                )

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.get(Metadata, 1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now().astimezone()

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_instance(self, hostname: str, status: str) -> str:
        """Update instance."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            # Use a direct UPDATE to avoid race conditions with concurrent threads
            update_values: dict = {"status": status}
            if status != "down":
                update_values["last_seen"] = datetime.now().astimezone()

            try:
                result = session.execute(update(Instances).filter_by(hostname=hostname).values(update_values), execution_options={"synchronize_session": False})

                if result.rowcount == 0:
                    return f"Instance {hostname} does not exist, will not be updated."

                session.commit()
            except BaseException as e:
                return f"An error occurred while updating the instance {hostname}.\n{e}"

        return ""

    def update_instance_fields(
        self,
        hostname: str,
        *,
        name: Optional[str] = None,
        port: Optional[int] = None,
        listen_https: Optional[bool] = None,
        https_port: Optional[int] = None,
        server_name: Optional[str] = None,
        method: Optional[str] = None,
        tls_mode: Optional[str] = None,
        tls_fingerprint: Optional[str] = None,
        changed: Optional[bool] = True,
    ) -> str:
        """Update instance metadata fields (name, port, server_name, method, tls_mode, tls_fingerprint)."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            # Use a direct UPDATE to avoid race conditions with concurrent threads
            # (MariaDB error 1020: "Record has changed since last read")
            update_values: dict = {}
            if name is not None:
                update_values["name"] = name
            if port is not None:
                update_values["port"] = port
            if listen_https is not None:
                update_values["listen_https"] = listen_https
            if https_port is not None:
                update_values["https_port"] = https_port
            if server_name is not None:
                update_values["server_name"] = server_name
            if method is not None:
                update_values["method"] = method
            if tls_mode is not None:
                update_values["tls_mode"] = tls_mode
            if tls_fingerprint is not None:
                update_values["tls_fingerprint"] = tls_fingerprint or None

            try:
                if update_values:
                    result = session.execute(
                        update(Instances).filter_by(hostname=hostname).values(update_values), execution_options={"synchronize_session": False}
                    )
                    if result.rowcount == 0:
                        return f"Instance {hostname} does not exist, will not be updated."

                if changed:
                    with suppress(ProgrammingError, OperationalError):
                        session.execute(
                            update(Metadata).filter_by(id=1).values({"instances_changed": True, "last_instances_change": datetime.now().astimezone()})
                        )

                session.commit()
            except BaseException as e:
                return f"An error occurred while updating the instance {hostname}.\n{e}"

        return ""

    def _encrypt_instance_credential(self, hostname: str, token: str, keyring=None) -> Optional[tuple]:
        """Encrypt a per-instance credential with the shared AES-256-GCM keyring.

        Best-effort: returns None (and logs) when no keyring is available so an
        optional per-instance token never breaks instance persistence — the dial
        simply falls back to the global API_TOKEN. With the metadata-backed keyring
        this now only happens on a read-only database or before metadata exists.

        Callers inside a session must resolve `keyring` first and pass it: reading the
        metadata-backed keyring opens a session, `_db_session` is not reentrant, and the
        removal would detach the very rows the caller is iterating.
        """
        try:
            return encrypt_private_key(token.encode("utf-8"), hostname, self._keyring_values() if keyring is None else keyring)
        except Exception as e:  # keyring absent/misconfigured must never break persistence
            self.logger.warning(f"Could not encrypt the credential for instance {hostname}; it will fall back to the global API token: {e}")
            return None

    def _decrypt_instance_credential(self, instance: Instances, keyring=None) -> Optional[str]:
        """Decrypt a stored per-instance credential; None when unset or unreadable.

        `keyring` is not optional for a caller inside a session — see
        `_encrypt_instance_credential`. Reading it from here detached the instance rows
        `get_instances` was iterating, which only stayed invisible because a one-instance
        stack has already read everything it needs by the time the first decrypt runs.
        """
        if not instance.credential_ciphertext or not instance.credential_nonce or not instance.credential_key_id:
            return None
        try:
            return decrypt_private_key(
                instance.credential_ciphertext,
                instance.credential_nonce,
                instance.credential_key_id,
                instance.hostname,
                self._keyring_values() if keyring is None else keyring,
            ).decode("utf-8")
        except (InvalidTag, ValueError) as e:
            self.logger.error(f"Could not decrypt the credential for instance {instance.hostname}: {e}")
            return None

    def _reconcile_credential_columns(
        self, hostname: str, env: Optional[Dict[str, Any]], global_token: Optional[str], keyring=None, preserved: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Credential columns for a reconcile insert/update.

        Encrypt the instance's own API_TOKEN only when it is present and distinct
        from the global one; otherwise fall back to `preserved` -- the columns the row
        carried before the rebuild -- and to "unset" when there is nothing to carry, so
        the dial falls back to the global token.

        `preserved` is what makes an enrolled `manual` row survive a config save: the
        environment declares no token for it, so without it the row would come back with
        an empty credential and the control plane would be locked out of a healthy
        instance. It is None for a row the caller does not own (an autoconf reconcile, a
        hostname taken over from another method), which keeps the historical clearing.

        A declared env token still wins over a stored credential: an instance whose
        identity is declared in its own environment is not one the control plane mints
        for (see the docs, "Enrollment vs a declared token"). On that one path the
        returned mapping also carries `credential_revoked_at: None` -- the single
        enrollment column this reconcile ever writes, cleared because the revocation
        belongs to the credential the environment just replaced. See the comment above
        that return; every other path returns credential columns only.
        """
        cleared = {"credential_ciphertext": None, "credential_nonce": None, "credential_key_id": None, "credential_updated_at": None}
        env_token = (env or {}).get("API_TOKEN")
        if not env_token or env_token == global_token:
            if preserved is None:
                return cleared
            return {column: preserved.get(column) for column in PRESERVED_CREDENTIAL_COLUMNS}
        if preserved and preserved.get("credential_ciphertext"):
            # About to replace a credential this row is already holding. Decrypt it first so the
            # warning below only fires when the value actually changes -- a row whose stored
            # credential IS the declared token is the ordinary case and must stay quiet.
            stored = None
            with suppress(Exception):
                stored = decrypt_private_key(
                    preserved["credential_ciphertext"],
                    preserved["credential_nonce"],
                    preserved["credential_key_id"],
                    hostname,
                    self._keyring_values() if keyring is None else keyring,
                ).decode("utf-8")
            if stored != env_token:
                # An instance that redeemed an enrollment answers ONLY to the credential it was
                # minted (`api.lua:is_allowed_token`); the shared token stops being a key to it.
                # So replacing that credential here locks the control plane out of a healthy
                # instance, every push is refused, and this line is the only thing that says why.
                self.logger.warning(
                    f"Instance {hostname} declares its own API token in its environment AND holds a control-plane "
                    "credential; the environment wins and the stored credential is being replaced. If this instance "
                    "was enrolled it still answers only to the credential it was minted, so every push to it will be "
                    "refused: remove its declared token to keep the enrollment, or revoke the enrollment to keep the "
                    "declared token."
                )
        # `credential_revoked_at` goes with the credential it revoked. This is the ONE place the
        # rebuild writes an enrollment column, and it has to: a revocation stamps the row and clears
        # its credential, and `API.from_instance` then dials it with `token=""` (API.py) no matter
        # what the credential columns say. So re-sourcing the declared token while leaving the
        # revocation standing would hand the row a fresh, valid credential the control plane refuses
        # to use -- permanently, since no reconcile clears it and a `manual` row cannot be deleted
        # from the UI (`UI_API_METHODS`). Same rule as the credential itself: the environment
        # declares this instance's identity, so it owns the revocation of it too. A row with no
        # declared token never reaches here, so a revoked ENROLLED row still stays revoked across a
        # config save (`test_a_revocation_survives_a_config_save`). It is lifted only where the
        # declared credential actually LANDS: on the encryption-failure path below the row ends up
        # with no credential at all, and lifting there would buy nothing (an instance that declares
        # its own token does not answer to the global one either) while widening the rule past what
        # it says.
        encrypted = self._encrypt_instance_credential(hostname, env_token, keyring)
        if encrypted is None:
            return cleared
        ciphertext, nonce, key_id = encrypted
        return {
            "credential_ciphertext": ciphertext,
            "credential_nonce": nonce,
            "credential_key_id": key_id,
            "credential_updated_at": datetime.now().astimezone(),
            "credential_revoked_at": None,
        }

    def set_instance_credential(self, hostname: str, token: Optional[str], *, changed: Optional[bool] = True) -> str:
        """Set (or clear, when token is falsy) the per-instance control-plane credential."""
        # Resolve the keyring before the session: reading the metadata-backed keyring opens
        # one of its own and `_db_session` is not reentrant (see _decrypt_instance_credential).
        keyring = self._keyring_values()
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if token:
                encrypted = self._encrypt_instance_credential(hostname, token, keyring)
                if encrypted is None:
                    return "No certificate encryption keyring is configured; cannot store a per-instance credential"
                ciphertext, nonce, key_id = encrypted
                values: Dict[str, Any] = {
                    "credential_ciphertext": ciphertext,
                    "credential_nonce": nonce,
                    "credential_key_id": key_id,
                    "credential_updated_at": datetime.now().astimezone(),
                }
            else:
                values = {"credential_ciphertext": None, "credential_nonce": None, "credential_key_id": None, "credential_updated_at": None}

            try:
                result = session.execute(update(Instances).filter_by(hostname=hostname).values(values), execution_options={"synchronize_session": False})
                if result.rowcount == 0:
                    return f"Instance {hostname} does not exist, will not be updated."

                if changed:
                    with suppress(ProgrammingError, OperationalError):
                        session.execute(
                            update(Metadata).filter_by(id=1).values({"instances_changed": True, "last_instances_change": datetime.now().astimezone()})
                        )

                session.commit()
            except BaseException as e:
                return f"An error occurred while updating the credential of instance {hostname}.\n{e}"

        return ""

    def get_instance_credential(self, hostname: str) -> Optional[str]:
        """Return the decrypted per-instance credential, or None when unset/unreadable."""
        # Resolve the keyring before the session: reading the metadata-backed keyring opens
        # one of its own and `_db_session` is not reentrant (see _decrypt_instance_credential).
        keyring = self._keyring_values()
        with self._db_session() as session:
            instance = session.scalars(select(Instances).filter_by(hostname=hostname).limit(1)).first()
            if not instance:
                return None
            return self._decrypt_instance_credential(instance, keyring)

    def _touch_instances_changed(self, session) -> None:
        """Mark the instance registry dirty so the scheduler re-reads it."""
        with suppress(ProgrammingError, OperationalError):
            session.execute(update(Metadata).filter_by(id=1).values({"instances_changed": True, "last_instances_change": datetime.now().astimezone()}))

    def issue_enrollment_code(self, hostname: str, ttl_seconds: Optional[int] = None) -> Tuple[Optional[str], str]:
        """Mint a single-use join code for an instance; returns (code, error).

        The plaintext code is returned here and nowhere else: only its SHA-512 digest is stored.
        Re-issuing overwrites the previous digest, so two enrollments of the same host never share
        a code. An already-enrolled row keeps its current credential until the new code is
        redeemed, so re-enrollment has no window where the instance is unreachable.
        """
        ttl = ENROLLMENT_TTL_DEFAULT if not ttl_seconds else max(1, min(int(ttl_seconds), ENROLLMENT_TTL_MAX))
        with self._db_session() as session:
            if self.readonly:
                return None, "The database is read-only, the changes will not be saved"

            instance = session.scalars(select(Instances).filter_by(hostname=hostname).limit(1)).first()
            if instance is None:
                return None, f"Instance {hostname} does not exist"
            if instance.method not in ENROLLABLE_METHODS:
                return None, (
                    f"Instance {hostname} is sourced from its environment (method: {instance.method}); "
                    "enrollment only applies to control-plane-owned instances"
                )

            code = token_urlsafe(32)
            try:
                session.execute(
                    update(Instances)
                    .filter_by(hostname=hostname)
                    .values(
                        {
                            "enroll_token_hash": hash_enrollment_code(code),
                            "enroll_token_expires_at": datetime.now().astimezone() + timedelta(seconds=ttl),
                            "enroll_failures": 0,
                            "enroll_code_state": "pending",
                        }
                    ),
                    execution_options={"synchronize_session": False},
                )
                session.commit()
            except BaseException as e:
                return None, f"An error occurred while issuing an enrollment code for instance {hostname}.\n{e}"

        return code, ""

    def redeem_enrollment_code(self, hostname: str, code: str) -> Tuple[Optional[str], str]:
        """Redeem a join code and mint that instance's credential; returns (credential, error).

        Every rejection returns the same opaque message: this runs unauthenticated, so telling the
        caller apart "unknown host" from "wrong code" from "expired" would turn it into an
        instance enumerator. The digest is consumed in the same UPDATE that stores the credential,
        and that UPDATE is conditioned on the digest still being the one we read -- two concurrent
        redemptions of one code therefore leave exactly one winner.
        """
        keyring = self._keyring_values()
        now = datetime.now().astimezone()
        # Hashed before any branch: the early rejections below do no work at all, so computing the
        # digest only on the path that needs it made the response time itself say "this hostname
        # exists and has a code pending".
        provided_hash = hash_enrollment_code(code)
        # Probed before the row is even read. Probing it later — after the host/method/pending
        # checks — made the 503 an oracle of its own: on a server with a broken keyring, 503 meant
        # "this hostname exists and has a code pending" and 401 meant everything else.
        if self._encrypt_instance_credential(hostname, "keyring-probe", keyring) is None:
            return None, "No certificate encryption keyring is configured; cannot store a per-instance credential"
        with self._db_session() as session:
            if self.readonly:
                return None, "The database is read-only, the changes will not be saved"

            instance = session.scalars(select(Instances).filter_by(hostname=hostname).limit(1)).first()
            if instance is None or instance.method not in ENROLLABLE_METHODS or instance.enroll_code_state != "pending" or not instance.enroll_token_hash:
                return None, ENROLLMENT_REJECTED

            expired = instance.enroll_token_expires_at is None or instance.enroll_token_expires_at.astimezone() <= now
            stored_hash = instance.enroll_token_hash

            if not expired and compare_digest(stored_hash, provided_hash):
                credential = token_urlsafe(48)
                encrypted = self._encrypt_instance_credential(hostname, credential, keyring)
                if encrypted is None:
                    return None, "No certificate encryption keyring is configured; cannot store a per-instance credential"
                ciphertext, nonce, key_id = encrypted
                try:
                    result = session.execute(
                        update(Instances)
                        .where(Instances.hostname == hostname, Instances.enroll_token_hash == stored_hash)
                        .values(
                            {
                                "credential_ciphertext": ciphertext,
                                "credential_nonce": nonce,
                                "credential_key_id": key_id,
                                "credential_updated_at": datetime.now().astimezone(),
                                # A successful redemption lifts a revocation: the instance proved it
                                # holds the code an admin just issued. It is no longer the ONLY thing
                                # that does -- since 2026-09-06 a re-sourced declared token lifts one
                                # too, see `_reconcile_credential_columns` -- but it is the only
                                # operator-driven one.
                                "credential_revoked_at": None,
                                "enroll_code_state": "none",
                                "enroll_token_hash": None,
                                "enroll_token_expires_at": None,
                                "enroll_failures": 0,
                            }
                        ),
                        execution_options={"synchronize_session": False},
                    )
                    if result.rowcount == 0:
                        # Lost the race: another redemption consumed this digest first.
                        session.rollback()
                        return None, ENROLLMENT_REJECTED
                    self._touch_instances_changed(session)
                    session.commit()
                except BaseException as e:
                    self.logger.error(f"An error occurred while redeeming the enrollment code of instance {hostname}: {e}")
                    return None, ENROLLMENT_REJECTED
                return credential, ""

            failures = (instance.enroll_failures or 0) + 1
            # Server-side increment: N parallel wrong guesses all read the same value, so a Python
            # `+ 1` lets them all write the same number and the cap never arrives.
            values: Dict[str, Any] = {"enroll_failures": Instances.enroll_failures + 1}
            if expired or failures >= ENROLLMENT_MAX_FAILURES:
                # Burn the code rather than lock a timer: recovery is one re-issue by an admin.
                # This only ends the CODE. It cannot touch the credential or the revocation any
                # more -- those live in their own columns -- which is what the old single-column
                # state made possible: burning a code on an enrolled row stamped "none" over a row
                # still holding a live credential.
                values |= {
                    "enroll_token_hash": None,
                    "enroll_token_expires_at": None,
                    "enroll_code_state": "none",
                }
            with suppress(BaseException):
                session.execute(
                    update(Instances).where(Instances.hostname == hostname, Instances.enroll_token_hash == stored_hash).values(values),
                    execution_options={"synchronize_session": False},
                )
                session.commit()

        return None, ENROLLMENT_REJECTED

    def revoke_instance_enrollment(self, hostname: str) -> str:
        """Clear an instance's credential and mark it revoked.

        The row keeps no credential and no pending code; `API.request()` refuses to dial a revoked
        row outright, so it never falls back to the global API token.
        """
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            instance = session.scalars(select(Instances).filter_by(hostname=hostname).limit(1)).first()
            if instance is None:
                return f"Instance {hostname} does not exist, will not be updated."
            if instance.method not in ENROLLABLE_METHODS:
                # Same guard as issuing, and the reason is now the opposite of what it used to be:
                # an orchestrator-owned row (`autoconf`) declares no API_TOKEN of its own, so the
                # reconcile takes the `preserved`/`cleared` path and never clears
                # `credential_revoked_at`. Revoking one would park it with every push refused for
                # good -- no reconcile lifts it and the UI cannot delete the row either (DELETE
                # refuses those rows). `manual` rows are enrollable now and are NOT in this branch:
                # a declared token re-sources the credential and lifts the revocation with it
                # (`_reconcile_credential_columns`), a minted one keeps it.
                return (
                    f"Instance {hostname} is sourced from its environment (method: {instance.method}); "
                    "enrollment only applies to control-plane-owned instances"
                )

            try:
                result = session.execute(
                    update(Instances)
                    .filter_by(hostname=hostname)
                    .values(
                        {
                            "credential_ciphertext": None,
                            "credential_nonce": None,
                            "credential_key_id": None,
                            "credential_updated_at": None,
                            "enroll_token_hash": None,
                            "enroll_token_expires_at": None,
                            "enroll_failures": 0,
                            "enroll_code_state": "none",
                            "credential_revoked_at": datetime.now().astimezone(),
                        }
                    ),
                    execution_options={"synchronize_session": False},
                )
                if result.rowcount == 0:
                    return f"Instance {hostname} does not exist, will not be updated."
                self._touch_instances_changed(session)
                session.commit()
            except BaseException as e:
                return f"An error occurred while revoking the enrollment of instance {hostname}.\n{e}"

        return ""

    def get_instances(self, *, method: Optional[str] = None, autoconf: bool = False, with_credential: bool = False) -> List[Dict[str, Any]]:
        """Get instances. Set with_credential=True (internal dial callers only) to
        include the decrypted per-instance token; never expose it to API clients."""
        # Resolve the keyring before the session: reading the metadata-backed keyring opens
        # one of its own and `_db_session` is not reentrant (see _decrypt_instance_credential).
        keyring = self._keyring_values()
        with self._db_session() as session:
            query = select(Instances)
            if method:
                query = query.filter_by(method=method)

            return [
                {
                    "hostname": instance.hostname,
                    "name": instance.name,
                    "port": instance.port,
                    "listen_https": instance.listen_https,
                    "https_port": instance.https_port,
                    "server_name": instance.server_name,
                    "type": instance.type,
                    "status": instance.status,
                    "method": instance.method,
                    "creation_date": instance.creation_date,
                    "last_seen": instance.last_seen,
                    "tls_mode": instance.tls_mode,
                    "tls_fingerprint": instance.tls_fingerprint,
                    "credential_set": instance.credential_ciphertext is not None,
                    "credential_updated_at": instance.credential_updated_at.astimezone().isoformat() if instance.credential_updated_at else None,
                    "credential_revoked": instance.credential_revoked_at is not None,
                    "enrollment_state": derive_enrollment_state(
                        instance.enroll_code_state, instance.credential_ciphertext is not None, instance.credential_revoked_at
                    ),
                    "enrollment_expires_at": (instance.enroll_token_expires_at.astimezone().isoformat() if instance.enroll_token_expires_at else None),
                }
                | ({"health": instance.status == "up", "env": {}} if autoconf else {})
                | ({"credential": self._decrypt_instance_credential(instance, keyring)} if with_credential else {})
                for instance in session.scalars(query)
            ]

    def get_instance(self, hostname: str, *, method: Optional[str] = None, with_credential: bool = False) -> Dict[str, Any]:
        """Get instance. Set with_credential=True (internal dial callers only) to
        include the decrypted per-instance token; never expose it to API clients."""
        # Resolve the keyring before the session: reading the metadata-backed keyring opens
        # one of its own and `_db_session` is not reentrant (see _decrypt_instance_credential).
        keyring = self._keyring_values()
        with self._db_session() as session:
            query = select(Instances).filter_by(hostname=hostname)
            if method:
                query = query.filter_by(method=method)

            instance = session.scalars(query.limit(1)).first()

            if not instance:
                return {}

            return {
                "hostname": instance.hostname,
                "name": instance.name,
                "port": instance.port,
                "listen_https": instance.listen_https,
                "https_port": instance.https_port,
                "server_name": instance.server_name,
                "type": instance.type,
                "status": instance.status,
                "method": instance.method,
                "creation_date": instance.creation_date,
                "last_seen": instance.last_seen,
                "tls_mode": instance.tls_mode,
                "tls_fingerprint": instance.tls_fingerprint,
                "credential_set": instance.credential_ciphertext is not None,
                "credential_updated_at": instance.credential_updated_at.astimezone().isoformat() if instance.credential_updated_at else None,
                "credential_revoked": instance.credential_revoked_at is not None,
                "enrollment_state": derive_enrollment_state(
                    instance.enroll_code_state, instance.credential_ciphertext is not None, instance.credential_revoked_at
                ),
                "enrollment_expires_at": instance.enroll_token_expires_at.astimezone().isoformat() if instance.enroll_token_expires_at else None,
            } | ({"credential": self._decrypt_instance_credential(instance, keyring)} if with_credential else {})
