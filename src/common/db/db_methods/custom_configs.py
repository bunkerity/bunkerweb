#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Union

from model import Custom_configs, Metadata, Services, Template_custom_configs  # type: ignore

from common_utils import bytes_hash, split_templates  # type: ignore

from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError, ProgrammingError

from .common import DatabaseMixinBase


class DatabaseCustomConfigsMixin(DatabaseMixinBase):
    """Custom NGINX configuration snippets (global and per-service)."""

    def save_custom_configs(
        self,
        custom_configs: List[
            Dict[
                Literal[
                    "service_id",
                    "type",
                    "name",
                    "data",
                    "value",
                    "checksum",
                    "method",
                    "exploded",
                ],
                Union[str, bytes, List[str]],
            ]
        ],
        method: str,
        changed: Optional[bool] = True,
        *,
        disable_cleanup: bool = False,
    ) -> str:
        """Save the custom configs in the database"""
        message = ""
        # Materialize once: callers may pass dict_values or a generator, and the
        # data-loss guard below needs to count items before the for-loop consumes them.
        custom_configs = [*custom_configs]
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            # Only meaningful for the autoconf method.
            disable_cleanup = disable_cleanup and method == "autoconf"

            if not disable_cleanup:
                # Data-loss guard (mirror of the save_config guards above): refuse the
                # cleanup when a ui/api save_custom_configs call would wipe every
                # method-owned custom config row while supplying nothing to replace
                # them. An empty incoming list with existing rows almost always means
                # the caller built an incomplete payload (route exception, form rebuild
                # race, missing in-memory state). Genuine "remove all custom configs"
                # actions delete rows individually through the UI/API, so by the time
                # an empty payload reaches save_custom_configs there is nothing left
                # to wipe and this guard is a no-op.
                if method in ("ui", "api") and not custom_configs:
                    existing_count = session.scalar(select(func.count()).select_from(Custom_configs).where(Custom_configs.method == method))
                    if existing_count > 0:
                        self.logger.warning(
                            f"Refusing save_custom_configs: incoming method={method!r} payload is empty while {existing_count} "
                            f"{method}-method custom config row(s) exist in the database. This indicates the caller submitted "
                            f"an incomplete payload (e.g. a service edit that lost its in-memory custom-config map). Aborting "
                            f"save_custom_configs to prevent data loss."
                        )
                        return message
                # Delete all the old config
                session.execute(delete(Custom_configs).where(Custom_configs.method == method))

            expected_keys: Set[Tuple[str, str, Optional[str]]] = set()

            to_put = []
            endl = "\n"
            for custom_config in custom_configs:
                if "exploded" in custom_config:
                    config = {"data": custom_config["value"], "method": method, "is_draft": bool(custom_config.get("is_draft", False))}

                    if custom_config["exploded"][0]:
                        if not session.execute(select(Services.id).filter_by(id=custom_config["exploded"][0]).limit(1)).first():
                            message += f"{endl if message else ''}Service {custom_config['exploded'][0]} not found, please check your config"

                        config.update(
                            {
                                "service_id": custom_config["exploded"][0],
                                "type": custom_config["exploded"][1],
                                "name": custom_config["exploded"][2],
                            }
                        )
                    else:
                        config.update(
                            {
                                "type": custom_config["exploded"][1],
                                "name": custom_config["exploded"][2],
                            }
                        )

                    custom_config = config

                custom_config["type"] = custom_config["type"].strip().replace("-", "_").lower()  # type: ignore
                custom_config["is_draft"] = bool(custom_config.get("is_draft", False))
                custom_config["data"] = custom_config["data"].encode("utf-8") if isinstance(custom_config["data"], str) else custom_config["data"]
                custom_config["checksum"] = custom_config.get("checksum", bytes_hash(custom_config["data"], algorithm="sha256"))  # type: ignore

                service_id = custom_config.get("service_id") or None
                filters = {
                    "type": custom_config["type"],
                    "name": custom_config["name"],
                    "service_id": service_id,
                }
                expected_keys.add((custom_config["type"], custom_config["name"], service_id))

                custom_conf = session.scalars(select(Custom_configs).filter_by(**filters).limit(1)).first()

                if not custom_conf:
                    to_put.append(Custom_configs(**custom_config))
                elif method == "manual" and custom_conf.method in {"manual", "ui", "api"}:
                    should_update_data = custom_config["checksum"] != custom_conf.checksum
                    if should_update_data:
                        custom_conf.data = custom_config["data"]
                        custom_conf.checksum = custom_config["checksum"]
                    if custom_conf.is_draft != custom_config["is_draft"] or should_update_data:
                        custom_conf.is_draft = custom_config["is_draft"]
                # Scheduler-method custom configs only ever originate from explicit
                # CUSTOM_CONF_* environment variables, so the scheduler override is
                # legitimate here (no default-filled pass exists for custom configs).
                elif self._methods_are_compatible(method, custom_conf.method, allow_scheduler_override=True):
                    should_update_data = custom_config["checksum"] != custom_conf.checksum
                    if should_update_data:
                        custom_conf.data = custom_config["data"]
                        custom_conf.checksum = custom_config["checksum"]
                    if custom_conf.is_draft != custom_config["is_draft"] or should_update_data:
                        custom_conf.is_draft = custom_config["is_draft"]
                        custom_conf.method = method
                    custom_conf.is_draft = custom_config["is_draft"]

            if disable_cleanup:
                # Mark autoconf custom configs that are no longer emitted by the orchestrator as draft
                # so they survive the removal and follow the service they belong to.
                orphan_configs = session.scalars(select(Custom_configs).where(Custom_configs.method == "autoconf", Custom_configs.is_draft.is_(False))).all()
                for orphan in orphan_configs:
                    if (orphan.type, orphan.name, orphan.service_id) not in expected_keys:
                        orphan.is_draft = True

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.get(Metadata, 1)
                    if metadata is not None:
                        metadata.custom_configs_changed = True
                        metadata.last_custom_configs_change = datetime.now().astimezone()

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return f"{f'{message}{endl}' if message else ''}{e}"

        return message

    def get_custom_configs(self, *, with_drafts: bool = False, with_data: bool = True, as_dict: bool = False) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Get the custom configs from the database"""
        db_config = self.get_non_default_settings(with_drafts=with_drafts, filtered_settings=("USE_TEMPLATE",))

        with self._db_session() as session:
            services = session.execute(select(Services.id, Services.is_draft)).all()
            allowed_services = {srv.id for srv in services if with_drafts or not srv.is_draft}

            entities = [
                Custom_configs.service_id,
                Custom_configs.type,
                Custom_configs.name,
                Custom_configs.checksum,
                Custom_configs.method,
                Custom_configs.is_draft,
            ]
            if with_data:
                entities.append(Custom_configs.data)

            custom_configs = []
            for custom_config in session.execute(select(*entities)):
                if custom_config.service_id and custom_config.service_id not in allowed_services:
                    continue
                if custom_config.is_draft and not with_drafts:
                    continue

                data = {
                    "service_id": custom_config.service_id,
                    "type": custom_config.type,
                    "name": custom_config.name,
                    "checksum": custom_config.checksum,
                    "method": custom_config.method,
                    "template": None,
                    "is_draft": custom_config.is_draft,
                }
                if with_data:
                    data["data"] = custom_config.data
                custom_configs.append(data)

            if not db_config:
                if as_dict:
                    dict_custom_configs = {}
                    for custom_config in custom_configs:
                        dict_custom_configs[
                            (f"{custom_config['service_id']}_" if custom_config["service_id"] else "") + f"{custom_config['type']}_{custom_config['name']}"
                        ] = custom_config
                    return dict_custom_configs
                return custom_configs

            template_entities = [Template_custom_configs.type, Template_custom_configs.name, Template_custom_configs.checksum]
            if with_data:
                template_entities.append(Template_custom_configs.data)

            # A real row shadows the one its template would provide. Indexed once instead of
            # rescanning the accumulating list for every template config.
            provided = {(config["service_id"], config["type"].replace("-", "_"), config["name"]) for config in custom_configs}
            # Services share templates; read each one once.
            template_configs: Dict[str, List[Any]] = {}

            for service_id in allowed_services:
                # `db_config` is NOT limited to USE_TEMPLATE — `get_non_default_settings` adds
                # SERVER_NAME and MULTISITE, and every service carries an IS_DRAFT. Matching on
                # the `{service_id}_` prefix therefore took each of those values for a template
                # id and looked it up: 500 services meant 500 queries for a template named "no",
                # half a million prefix tests, and 287 ms to return nothing. Ask for the one key
                # that holds a template id — which is what `get_custom_config` already does.
                template = db_config.get(f"{service_id}_USE_TEMPLATE")
                if not template:
                    continue

                # REVERSED, and this is the one place last-wins is not free. Shadowing here runs
                # through `provided`: the FIRST layer to claim a (service, type, name) keeps it
                # and every later one is skipped — first-wins, the opposite of the settings
                # overlay (config_read.py:318-400), which lets a later layer overwrite because
                # the earlier value carries method "default". Walking the layers backwards makes
                # the LAST declared layer claim the key first, so both artefacts agree on
                # last-wins. Real `bw_custom_configs` rows are unaffected: `provided` is
                # pre-seeded from them above, so they still shadow every layer.
                for template_id in reversed(split_templates(template)):
                    if template_id not in template_configs:
                        template_configs[template_id] = session.execute(
                            select(*template_entities).filter_by(template_id=template_id).order_by(Template_custom_configs.order)
                        ).all()

                    for template_config in template_configs[template_id]:
                        config_type = template_config.type.replace("_", "-").replace(".conf", "").strip()
                        # Real custom_configs rows use the underscore enum form while config_type is hyphenated here;
                        # normalize both sides so an overriding row correctly suppresses the template-provided config.
                        key = (service_id, config_type.replace("-", "_"), template_config.name)
                        if key in provided:
                            continue

                        custom_config = {
                            "service_id": service_id,
                            "type": config_type,
                            "name": template_config.name,
                            "checksum": template_config.checksum,
                            "method": "default",
                            # The owning LAYER, never the whole list — the UI's editability
                            # check (routes/services.py) membership-tests this against the list.
                            "template": template_id,
                            "is_draft": False,
                        }
                        if with_data:
                            custom_config["data"] = template_config.data
                        custom_configs.append(custom_config)
                        provided.add(key)

            if as_dict:
                dict_custom_configs = {}
                for custom_config in custom_configs:
                    dict_custom_configs[
                        (f"{custom_config['service_id']}_" if custom_config["service_id"] else "") + f"{custom_config['type']}_{custom_config['name']}"
                    ] = custom_config
                return dict_custom_configs
            return custom_configs

    def get_custom_config(self, config_type: str, name: str, *, service_id: Optional[str] = None, with_data: bool = True) -> Dict[str, Any]:
        """Get a custom config from the database"""
        config_type = config_type.strip().replace("-", "_").lower()
        with self._db_session() as session:
            entities = [
                Custom_configs.service_id,
                Custom_configs.type,
                Custom_configs.name,
                Custom_configs.checksum,
                Custom_configs.method,
                Custom_configs.is_draft,
            ]
            if with_data:
                entities.append(Custom_configs.data)

            db_config = session.execute(select(*entities).filter_by(service_id=service_id, type=config_type, name=name).limit(1)).first()

        if not db_config:
            if service_id:
                service_config = self.get_non_default_settings(with_drafts=True, filtered_settings=("USE_TEMPLATE",))
                # Reversed for the same reason as get_custom_configs: the LAST declared layer
                # that provides this config is the one in effect. First match wins the scan.
                for template_id in reversed(split_templates(service_config.get(f"{service_id}_USE_TEMPLATE"))):
                    with self._db_session() as session:
                        template_config = session.scalars(
                            select(Template_custom_configs).filter_by(template_id=template_id, type=config_type, name=name).limit(1)
                        ).first()
                        if template_config:
                            custom_config = {
                                "service_id": service_id,
                                "type": config_type,
                                "name": name,
                                "checksum": template_config.checksum,
                                "method": "default",
                                "template": template_id,
                                "is_draft": False,
                            }
                            if with_data:
                                custom_config["data"] = template_config.data
                            return custom_config
            return {}

        custom_config = {
            "service_id": service_id,
            "type": config_type,
            "name": name,
            "checksum": db_config.checksum,
            "method": db_config.method,
            "template": None,
            "is_draft": getattr(db_config, "is_draft", False),
        }
        if with_data:
            custom_config["data"] = db_config.data

        return custom_config

    def get_custom_config_compatibility_error(self, config_type: str, *, service_id: Optional[str] = None, with_drafts: bool = True) -> str:
        """Return a validation error when a custom config is incompatible with current global settings."""
        normalized_type = config_type.strip().replace("-", "_").lower()
        if normalized_type != "modsec_crs" or service_id in (None, "", "global"):
            return ""

        use_global_crs = self.get_config(global_only=True, methods=False, with_drafts=with_drafts, filtered_settings=("USE_MODSECURITY_GLOBAL_CRS",)).get(
            "USE_MODSECURITY_GLOBAL_CRS", "no"
        )
        if isinstance(use_global_crs, dict):
            use_global_crs = use_global_crs.get("value", "no")

        return self.GLOBAL_CRS_SERVICE_SCOPED_MODSEC_CRS_ERROR if use_global_crs == "yes" else ""

    def upsert_custom_config(self, config_type: str, name: str, config: Dict[str, Any], *, service_id: Optional[str] = None, new: bool = False) -> str:
        """Update or insert a custom config in the database"""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            filters = {
                "type": config_type,
                "name": name,
                "service_id": service_id or None,
            }

            custom_config = session.scalars(select(Custom_configs).filter_by(**filters).limit(1)).first()

            data = config["data"].encode("utf-8") if isinstance(config["data"], str) else config["data"]
            checksum = config.get("checksum", bytes_hash(data, algorithm="sha256"))
            is_draft = bool(config.get("is_draft", False))

            if not custom_config:
                session.add(
                    Custom_configs(
                        service_id=config.get("service_id"),
                        type=config["type"],
                        name=config["name"],
                        data=data,
                        checksum=checksum,
                        method=config["method"],
                        is_draft=is_draft,
                    )
                )
            else:
                if new:
                    return "The custom config already exists"
                custom_config.service_id = config.get("service_id")
                custom_config.data = data
                custom_config.checksum = checksum
                custom_config.is_draft = is_draft
                for key in ("type", "name", "method"):
                    if key in config:
                        setattr(custom_config, key, config[key])

            with suppress(ProgrammingError, OperationalError):
                metadata = session.get(Metadata, 1)
                if metadata is not None:
                    metadata.custom_configs_changed = True
                    metadata.last_custom_configs_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def delete_custom_configs(
        self, keys: Set[Tuple[Optional[str], str, str]]
    ) -> Tuple[str, Set[Tuple[Optional[str], str, str]], Set[Tuple[Optional[str], str, str]]]:
        """Delete exact UI/API custom config keys.

        Each key is ``(service_id, config_type, name)``. Only rows written by the UI or API
        method are removable; a matching row owned by any other method is reported as
        protected instead of deleted. Returns ``(error, deleted_keys, protected_keys)``.
        """
        normalized_keys = {
            (None if service_id in (None, "", "global") else service_id, config_type.strip().replace("-", "_").lower(), name)
            for service_id, config_type, name in keys
        }
        deleted_keys: Set[Tuple[Optional[str], str, str]] = set()
        protected_keys: Set[Tuple[Optional[str], str, str]] = set()

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved", deleted_keys, protected_keys

            try:
                for key in normalized_keys:
                    service_id, config_type, name = key
                    filters = {"service_id": service_id, "type": config_type, "name": name}
                    deleted = session.execute(
                        delete(Custom_configs).filter_by(**filters).where(Custom_configs.method.in_(("ui", "api"))),
                        execution_options={"synchronize_session": False},
                    ).rowcount
                    if deleted:
                        deleted_keys.add(key)
                    elif session.scalars(select(Custom_configs.id).filter_by(**filters).limit(1)).first() is not None:
                        protected_keys.add(key)

                if deleted_keys:
                    metadata = session.get(Metadata, 1)
                    if metadata is not None:
                        metadata.custom_configs_changed = True
                        metadata.last_custom_configs_change = datetime.now().astimezone()

                session.commit()
            except BaseException as e:
                session.rollback()
                return str(e), set(), set()

        return "", deleted_keys, protected_keys
