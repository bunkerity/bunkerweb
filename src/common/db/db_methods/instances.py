#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Optional

from model import Instances, Metadata  # type: ignore

from common_utils import is_valid_host  # type: ignore

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import OperationalError, ProgrammingError

from .common import DatabaseMixinBase


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
    ) -> str:
        """Add instance."""
        if not is_valid_host(hostname):
            return f"Invalid instance hostname: {hostname}"

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instance = session.execute(select(Instances.hostname).filter_by(hostname=hostname).limit(1)).first()

            if db_instance is not None:
                return f"Instance {hostname} already exists, will not be added."

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

            session.execute(delete(Instances).where(Instances.method == method))

            for instance in instances:
                if instance.get("hostname") is None:
                    continue

                current_time = datetime.now().astimezone()

                db_instance = session.scalars(select(Instances).filter_by(hostname=instance["hostname"]).limit(1)).first()
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
                        status="up" if instance.get("health", True) else "down",
                        method=instance.get("method", method),
                        creation_date=instance.get("creation_date", current_time),
                        last_seen=instance.get("last_seen", current_time),
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
        changed: Optional[bool] = True,
    ) -> str:
        """Update instance metadata fields (name, port, server_name, method)."""
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

    def get_instances(self, *, method: Optional[str] = None, autoconf: bool = False) -> List[Dict[str, Any]]:
        """Get instances."""
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
                }
                | ({"health": instance.status == "up", "env": {}} if autoconf else {})
                for instance in session.scalars(query)
            ]

    def get_instance(self, hostname: str, *, method: Optional[str] = None) -> Dict[str, Any]:
        """Get instance."""
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
            }
