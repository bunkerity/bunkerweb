#!/usr/bin/env python3
from base64 import b64encode
from contextlib import suppress
from datetime import datetime
from json import dumps
from os import environ, urandom
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Set, Tuple, Union

from certificate_utils import ACTIVE_KEY_ENV, KEYS_ENV  # type: ignore
from common_utils import merge_template_settings, split_templates  # type: ignore
from model import Global_values, Metadata, Plugins, Template_settings  # type: ignore

from sqlalchemy import delete, or_, select, text, update

from .common import DatabaseMixinBase, retry_on_transient_db_errors

# Key id of the database-stored fallback keyring. The keyring is a mapping, so a future
# rotation adds "db-v2" alongside it rather than replacing this entry.
DB_KEYRING_KEY_ID = "db-v1"
# Change flags a JOB owns the acknowledgement of, each paired with a `last_<key>_change`
# watermark that only its setters write. "config" is deliberately absent: it clears nothing
# (see `checked_changes`), it only latches `first_config_saved`.
CLEARABLE_CHANGES = ("custom_configs", "external_plugins", "pro_plugins", "instances", "certificates")
# Secrets that PATCH /metadata must never be able to overwrite: replacing the keyring makes
# every stored private key and per-instance credential undecryptable, and planting a known
# key would compromise everything encrypted afterwards.
PROTECTED_METADATA_KEYS = frozenset(("certificate_keyring", "certificate_keyring_active"))


class DatabaseMetadataMixin(DatabaseMixinBase):
    """Database metadata, versioning and change-flag methods."""

    def initialize_db(self, version: str, integration: str = "Unknown") -> str:
        """Initialize the database"""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.get(Metadata, 1)

                if metadata:
                    metadata.version = version
                    metadata.integration = integration
                    # initialize_db() means the schema is ready: ensure the flag is set even
                    # on an existing row (e.g. a partial prior init left it False) so the API's
                    # DB-init wait cannot deadlock against the scheduler on upgrade.
                    metadata.is_initialized = True
                else:
                    session.add(
                        Metadata(
                            is_initialized=True,
                            first_config_saved=False,
                            scheduler_first_start=True,
                            version=version,
                            integration=integration,
                        )
                    )
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def _keyring_values(self) -> Mapping[str, str]:
        """Return the mapping the AES-256-GCM keyring is loaded from.

        An operator-provided environment keyring always wins and keeps the key material
        outside the database. Without one, fall back to a keyring persisted in the metadata
        row so certificate and per-instance credential encryption work on a stock install
        instead of failing every write.
        """
        if environ.get(KEYS_ENV, "").strip() and environ.get(ACTIVE_KEY_ENV, "").strip():
            return environ
        if self._db_keyring is None:
            self._db_keyring = self._load_or_create_db_keyring()
        return self._db_keyring

    def _load_or_create_db_keyring(self) -> Dict[str, str]:
        """Load the metadata-stored keyring, generating it once when absent.

        The write is a compare-and-set on an unset keyring, so components racing at first
        boot (API, scheduler, worker) all converge on whichever key landed first. Returns an
        empty mapping when no key can be obtained — a read-only database, or metadata that
        does not exist yet — which makes callers fail closed exactly as an unconfigured
        environment keyring does.
        """
        with self._db_session() as session:
            row = session.execute(select(Metadata.certificate_keyring, Metadata.certificate_keyring_active).filter_by(id=1).limit(1)).first()
            if row is None:
                return {}

            if not row.certificate_keyring or not row.certificate_keyring_active:
                if self.readonly:
                    return {}
                self.logger.warning(
                    f"No certificate encryption keyring is configured; generating one and storing it in the database. "
                    f"It only provides envelope encryption: a database dump contains both the key and the ciphertext it protects. "
                    f"Set {KEYS_ENV} and {ACTIVE_KEY_ENV} in the environment to keep the key outside the database."
                )
                try:
                    session.execute(
                        update(Metadata)
                        .where(
                            Metadata.id == 1,
                            or_(Metadata.certificate_keyring.is_(None), Metadata.certificate_keyring == ""),
                        )
                        .values(
                            certificate_keyring=dumps({DB_KEYRING_KEY_ID: b64encode(urandom(32)).decode()}, separators=(",", ":")),
                            certificate_keyring_active=DB_KEYRING_KEY_ID,
                        )
                    )
                    session.commit()
                except BaseException as e:
                    session.rollback()
                    self.logger.error(f"Could not store the generated certificate encryption keyring: {e}")
                    return {}
                # Re-read so a component that lost the race adopts the winner's key.
                row = session.execute(select(Metadata.certificate_keyring, Metadata.certificate_keyring_active).filter_by(id=1).limit(1)).first()
                if row is None or not row.certificate_keyring or not row.certificate_keyring_active:
                    return {}

        return {KEYS_ENV: row.certificate_keyring, ACTIVE_KEY_ENV: row.certificate_keyring_active}

    def get_version(self) -> str:
        """Get the database version"""
        with self._db_session() as session:
            try:
                metadata = session.execute(select(Metadata.version).filter_by(id=1).limit(1)).first()
                if metadata:
                    return metadata.version
                return "1.7.0~beta"
            except BaseException as e:
                return f"Error: {e}"

    def cleanup_template_polluted_global_values(self) -> List[Tuple[str, str, str]]:
        """One-shot cleanup of ``bw_global_values`` rows a pre-fix (< c965d81ec) multi-layer
        template save wrote as ``method="scheduler"`` rows carrying the TEMPLATE's own value,
        instead of leaving the setting unset. Those rows do not self-heal (the update branch
        in ``config_save.py`` only deletes a row on a VALUE CHANGE) and they then shield future
        template edits: ``config_read`` skips a layer's default for any key whose stored row
        carries a non-default method. See ``.cache/results-2026-09-01-wave11/report-L-B.md``,
        "Open questions" Q1.

        A row is pollution only if it matches ALL of:
          * ``method == "scheduler"``
          * its ``setting_id`` is one the currently active global ``USE_TEMPLATE`` layers declare
          * its value equals THAT LAYER'S resolved (last-wins across layers) default

        Post-fix, ``config_save`` never stores a row whose value equals the resolved template
        default (it is implicit and gets skipped or deleted instead of written), so every row
        this rule matches today predates the fix -- safe to delete unconditionally, and no
        future save can ever create a false positive here again. That guarantee assumes a
        non-NULL layer default: ``Template_settings.default`` is nullable, and a NULL layer
        default compares here as ``""`` (``_empty_if_none``) while ``config_save.py`` compares
        it raw (``value == nm_default``, no normalisation) -- a real, PO-parked divergence
        (L-B "Open questions" Q2), not something this function should silently paper over by
        picking a side.

        Guarded by ``bw_metadata.template_values_cleaned_at``: NULL means no pass has completed,
        a timestamp means one has and this returns immediately. The marker is written in the same
        transaction as the deletes, so a failed sweep leaves it NULL and the next process retries.
        The in-process flag on the caller (``get_metadata``'s ``self``) is kept in front of it: it
        is what stops the marker SELECT itself from running on every ``get_metadata()`` call in a
        long-lived process (the API's ``get_db()`` singleton serves it on every UI page). It is not
        sufficient on its own -- "once per ``Database`` instance" is **not** once per process: a
        fresh ``Database`` is built per job execution (``jobs.py``'s ``Job.__init__``, since
        ``src/worker/executor.py`` loads each job module from scratch with no caching), per
        ``gen/save_config.py`` subprocess (every scheduler boot and every SIGHUP/config save), and
        per ``bwcli`` invocation, which is what made the sweep run over and over.

        The marker is deliberately NOT set on the "no active template layers" early return: a stack
        that adopts templates later would otherwise find the sweep already disabled before it could
        ever match a row. The residual, accepted: pollution left by a template that is swapped out
        *after* the first completed pass is never swept. It is pre-fix legacy data only, and the
        recovery is one row delete.
        """
        deleted: List[Tuple[str, str, str]] = []
        if self.readonly:
            return deleted

        try:
            with self._db_session() as session:
                marker = session.execute(select(Metadata.template_values_cleaned_at).filter_by(id=1).limit(1)).first()
                if marker is not None and marker.template_values_cleaned_at is not None:
                    return deleted

                use_template_row = session.execute(select(Global_values.value).filter_by(setting_id="USE_TEMPLATE", suffix=0).limit(1)).first()
                template_used = self._empty_if_none(use_template_row.value) if use_template_row else ""
                template_ids = split_templates(template_used)
                if not template_ids:
                    return deleted

                layers: Dict[str, Dict[Tuple[str, int], Optional[str]]] = {}
                owning_layer: Dict[Tuple[str, int], str] = {}
                for ts in session.execute(
                    select(Template_settings.template_id, Template_settings.setting_id, Template_settings.suffix, Template_settings.default)
                    .filter(Template_settings.template_id.in_(template_ids))
                    .order_by(Template_settings.order)
                ):
                    layers.setdefault(ts.template_id, {})[(ts.setting_id, ts.suffix or 0)] = ts.default

                # Replayed in declared layer order so the last layer to declare a key wins --
                # the same precedence merge_template_settings folds the values with below.
                for template_id in template_ids:
                    for key in layers.get(template_id, {}):
                        owning_layer[key] = template_id

                defaults = merge_template_settings(layers, template_ids)
                if not defaults:
                    return deleted

                declared_setting_ids = {setting_id for setting_id, _ in defaults}

                candidates = session.execute(
                    select(Global_values.setting_id, Global_values.suffix, Global_values.value).filter(
                        Global_values.method == "scheduler",
                        Global_values.setting_id.in_(declared_setting_ids),
                    )
                ).all()

                for row in candidates:
                    key = (row.setting_id, row.suffix or 0)
                    if key not in defaults:
                        continue
                    row_value = self._empty_if_none(row.value)
                    if row_value != self._empty_if_none(defaults[key]):
                        continue

                    result = session.execute(
                        delete(Global_values).where(
                            Global_values.setting_id == row.setting_id,
                            Global_values.suffix == row.suffix,
                            Global_values.method == "scheduler",
                        )
                    )
                    # Only log/report a row that THIS call actually removed. Several Database
                    # instances can reach this concurrently (see the frequency note above); a
                    # second one racing the first would otherwise log a "deleted" line for a row
                    # the first already removed, misrepresenting the audit trail the brief asked
                    # for a log of.
                    if result.rowcount:
                        deleted.append((row.setting_id, row_value, owning_layer.get(key, "")))

                # A pass completed: stamp it in the SAME transaction as the deletes, so a failure
                # anywhere above rolls the marker back with them and the next process retries.
                session.execute(update(Metadata).filter_by(id=1).values({"template_values_cleaned_at": datetime.now().astimezone()}))
                session.commit()
        except BaseException as e:
            # debug, not error: a transient lock-wait/permission failure here must not land a "❌"
            # in the scheduler log stream that tests/core/db.yml's not_log assertions watch for
            # (Criticos round 3) -- this is a best-effort one-shot cleanup, not a required step,
            # and the empty return already tells every caller nothing was cleaned up this call.
            self.logger.debug(f"Error while cleaning up template-polluted global values: {e}")
            return []

        for setting_id, value, template_id in deleted:
            self.logger.info(f"Deleted template-polluted bw_global_values row: setting={setting_id!r} value={value!r} layer={template_id!r}")

        return deleted

    @retry_on_transient_db_errors
    def get_metadata(self) -> Dict[str, Any]:
        """Get the metadata from the database"""
        data = {
            "is_initialized": False,
            "is_pro": False,
            "pro_license": "",
            "pro_expire": None,
            "pro_status": "invalid",
            "pro_services": 0,
            "non_draft_services": 0,
            "pro_overlapped": False,
            "last_pro_check": None,
            "force_pro_update": False,
            "failover": False,
            "failover_message": "",
            "first_config_saved": False,
            "autoconf_loaded": False,
            "scheduler_first_start": True,
            "custom_configs_changed": False,
            "external_plugins_changed": False,
            "pro_plugins_changed": False,
            "instances_changed": False,
            "certificates_changed": False,
            "plugins_config_changed": {},
            "last_custom_configs_change": None,
            "last_external_plugins_change": None,
            "last_pro_plugins_change": None,
            "last_instances_change": None,
            "last_certificates_change": None,
            "reload_ui_plugins": False,
            "integration": "unknown",
            "version": "1.7.0~beta",
            "database_version": "Unknown",  # ? Extracted from the database
            "default": True,  # ? Extra field to know if the returned data is the default one
        }
        with self._db_session() as session:
            with suppress(BaseException):
                database = self.database_uri.split(":")[0].split("+")[0]
                if database == "sqlite":
                    sql_query = text("SELECT sqlite_version()")
                elif database == "oracle":
                    # Use PRODUCT_COMPONENT_VERSION which is more accessible than v$instance
                    sql_query = text("SELECT version FROM PRODUCT_COMPONENT_VERSION WHERE PRODUCT LIKE 'Oracle%' AND ROWNUM = 1")
                else:
                    sql_query = text("SELECT VERSION()")

                try:
                    data["database_version"] = (session.execute(sql_query).first() or ["unknown"])[0]
                except Exception:
                    data["database_version"] = "Unknown (access restricted)"
                metadata = session.scalars(select(Metadata).filter_by(id=1).limit(1)).first()
                if metadata:
                    for key in data.copy():
                        if hasattr(metadata, key) and key not in ("database_version", "default"):
                            data[key] = getattr(metadata, key)
                    data["default"] = False

                data["plugins_config_changed"] = {
                    plugin.id: plugin.last_config_change
                    for plugin in session.execute(select(Plugins.id, Plugins.last_config_change).filter_by(config_changed=True)).all()
                }

        # Gated on is_initialized, not merely "after the session block": a fresh install has no
        # bw_global_values table yet (initialize_db() creates the schema, this only reads it), and
        # the cleanup's own error handling would otherwise log an ERROR-level "no such table" on
        # every call until the schema exists -- exactly the noisy, misleading failure this is meant
        # to avoid, not reproduce.
        if data["is_initialized"] and not getattr(self, "_template_defaults_cleanup_attempted", False):
            self._template_defaults_cleanup_attempted = True
            self.cleanup_template_polluted_global_values()

        return data

    def set_metadata(self, data: Dict[str, Any]) -> str:
        """Set the metadata values"""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.get(Metadata, 1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                for key, value in data.items():
                    if key in PROTECTED_METADATA_KEYS:
                        self.logger.warning(f"Metadata key {key} is protected and cannot be set through this method")
                        continue

                    if not hasattr(metadata, key):
                        self.logger.warning(f"Metadata key {key} does not exist")
                        continue

                    setattr(metadata, key, value)
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    @retry_on_transient_db_errors
    def clear_applied_changes(self, snapshot: Mapping[str, Any], keys: Optional[Sequence[str]] = None) -> str:
        """Acknowledge the changes a job has just applied — and only those.

        The scheduler used to clear the change flags in the same breath as *dispatching* the job
        that applies them, which is fire-and-forget (no result backend). A push that never
        completed — worker killed and the delivery abandoned, dispatch refused, the job failing —
        therefore left the flags already clear, so nothing ever re-dispatched it and every
        instance kept serving the previous configuration with only a failed job run as evidence.

        Clearing belongs to whoever did the work. That moves the risk from "lost update on the
        failure path" to "lost update on the success path": a change landing WHILE the job runs
        must not be acknowledged by it. Hence compare-and-clear — `snapshot` is a `get_metadata()`
        taken before the job read the data it applied, and a flag is only cleared while its
        `last_*_change` watermark still holds the snapshotted value. Anything newer belongs to a
        change this run never saw: the flag stays set and the scheduler re-dispatches.

        This deliberately never WRITES a `last_*_change`. Those columns are written by the
        setters alone, which is what makes them usable as generation tokens; moving one here
        would destroy the very value the next comparison depends on.

        Known residual: on MySQL and MariaDB these columns are second-resolution `DATETIME`, so
        two changes inside the same second share a watermark and the second one can be
        acknowledged by a run that never saw it. That is a ~1s window against the previous
        behaviour's window of the entire push, and closing it needs `DATETIME(6)` — a migration
        across four engines, which belongs to the Alembic closure work rather than here.
        """
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                for key in keys or CLEARABLE_CHANGES:
                    # The `_changed` test is an optimization, not a guard: a flag that was not
                    # set in the snapshot cannot be wrongly cleared anyway, because a change
                    # arriving since would have moved the watermark the WHERE compares. It only
                    # skips UPDATEs that would match nothing or write False over False.
                    if key not in CLEARABLE_CHANGES or not snapshot.get(f"{key}_changed"):
                        continue
                    watermark = snapshot.get(f"last_{key}_change")
                    timestamp_column = getattr(Metadata, f"last_{key}_change")
                    session.execute(
                        update(Metadata)
                        .where(Metadata.id == 1, timestamp_column.is_(None) if watermark is None else timestamp_column == watermark)
                        .values({getattr(Metadata, f"{key}_changed"): False})
                    )

                # `plugins_config_changed` arrives from `get_metadata` already shaped as
                # {plugin_id: last_config_change} (see above), so each plugin carries its own
                # token and they are cleared one by one -- never with a WHERE-less UPDATE over
                # every row, which is what `checked_changes(plugins_changes="all")` does and why
                # it erases changes it never looked at.
                if not keys or "plugins_config" in keys:
                    for plugin_id, watermark in (snapshot.get("plugins_config_changed") or {}).items():
                        session.execute(
                            update(Plugins)
                            .where(
                                Plugins.id == plugin_id,
                                Plugins.last_config_change.is_(None) if watermark is None else Plugins.last_config_change == watermark,
                            )
                            .values({Plugins.config_changed: False})
                        )

                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def checked_changes(
        self,
        changes: Optional[List[str]] = None,
        plugins_changes: Optional[Union[Literal["all"], Set[str], List[str], Tuple[str]]] = None,
        value: Optional[bool] = False,
    ) -> str:
        """Set changed bit for config, custom configs, instances and plugins"""
        changes = changes or ["config", "custom_configs", "external_plugins", "pro_plugins", "instances", "certificates", "ui_plugins"]
        plugins_changes = plugins_changes or set()
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.get(Metadata, 1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                current_time = datetime.now().astimezone()

                if "config" in changes:
                    if not metadata.first_config_saved:
                        metadata.first_config_saved = True
                if "custom_configs" in changes:
                    metadata.custom_configs_changed = value
                    metadata.last_custom_configs_change = current_time
                if "external_plugins" in changes:
                    metadata.external_plugins_changed = value
                    metadata.last_external_plugins_change = current_time
                if "pro_plugins" in changes:
                    metadata.pro_plugins_changed = value
                    metadata.last_pro_plugins_change = current_time
                if "instances" in changes:
                    metadata.instances_changed = value
                    metadata.last_instances_change = current_time
                if "certificates" in changes:
                    metadata.certificates_changed = value
                    metadata.last_certificates_change = current_time
                if "ui_plugins" in changes:
                    metadata.reload_ui_plugins = value

                if plugins_changes:
                    if plugins_changes == "all":
                        session.execute(update(Plugins).values({Plugins.config_changed: value, Plugins.last_config_change: current_time}))
                    else:
                        session.execute(
                            update(Plugins)
                            .where(Plugins.id.in_(plugins_changes))
                            .values({Plugins.config_changed: value, Plugins.last_config_change: current_time})
                        )

                session.commit()
            except BaseException as e:
                return str(e)

        return ""
