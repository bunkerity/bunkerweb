#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from redis import Redis, Sentinel
from valkey import Valkey


def handle(LOGGER: Logger, action: Any) -> None:
    library_name = "Valkey" if action.valkey else "Redis"
    LOGGER.info(f"🔗 Connecting to {library_name} server ...")

    if action.sentinel:
        sentinel_hosts = (
            ("127.0.0.1", action.sentinel_port),
            ("127.0.0.1", action.sentinel_port + 1),
            ("127.0.0.1", action.sentinel_port + 2),
        )

        redis_username = action.user[0] if action.user else None
        redis_password = action.user[1] if action.user else action.password
        sentinel_username = action.sentinel_user[0] if action.sentinel_user else None
        sentinel_password = action.sentinel_user[1] if action.sentinel_user else None

        LOGGER.debug(
            f"ℹ️ Trying to connect to {library_name} Sentinel with the following parameters:\n"
            + f"hosts: {sentinel_hosts}\n"
            + f"master: {action.sentinel_master}\n"
            + f"db: {action.db}\n"
            + f"tls: {action.tls}\n"
            + f"redis username: {redis_username}\n"
            + f"redis password: {redis_password}\n"
            + f"sentinel username: {sentinel_username}\n"
            + f"sentinel password: {sentinel_password}",
        )

        sentinel_kwargs = {}
        if sentinel_username:
            sentinel_kwargs["username"] = sentinel_username
        if sentinel_password:
            sentinel_kwargs["password"] = sentinel_password

        sentinel = Sentinel(
            sentinel_hosts,
            sentinel_kwargs=sentinel_kwargs,
            # sentinel_kwargs=dict(ssl=action.sentinel_tls, ssl_cert_reqs="none"),
            socket_timeout=1,
        )

        if action.sentinel_type == "slave":
            LOGGER.info(
                f"ℹ️ Trying to get a {library_name} Sentinel slave for master {action.sentinel_master} with the following parameters:\n"
                + f"db: {action.db}\n"
                + f"username: {redis_username}\n"
                + f"password: {redis_password}",
            )
            test_client = sentinel.slave_for(
                action.sentinel_master,
                db=action.db,
                username=redis_username,
                password=redis_password,
                decode_responses=True,
            )
        else:
            LOGGER.info(
                f"ℹ️ Trying to get a {library_name} Sentinel master for master {action.sentinel_master} with the following parameters:\n"
                + f"db: {action.db}\n"
                + f"username: {redis_username}\n"
                + f"password: {redis_password}",
            )
            test_client = sentinel.master_for(
                action.sentinel_master,
                db=action.db,
                username=redis_username,
                password=redis_password,
                decode_responses=True,
            )
    else:
        LOGGER.debug(
            f"ℹ️ Trying to connect to {library_name} with the following parameters:\n"
            + "host: 127.0.0.1\n"
            + f"port: {action.port if not action.tls else action.tls_port}\n"
            + f"db: {action.db}\n"
            + f"tls: {action.tls}\n"
            + f"username: {action.user[0] if action.user else None}\n"
            + f"password: {action.user[1] if action.user else action.password}",
        )

        # For Valkey with password but no username, use the 'admin' user
        username = action.user[0] if action.user else None
        password = action.user[1] if action.user else action.password
        if action.valkey and password and not username:
            username = "admin"

        if action.valkey:
            test_client = Valkey(
                host="127.0.0.1",
                port=action.port if not action.tls else action.tls_port,
                username=username,
                password=password,
                db=action.db,
                ssl=action.tls,
                socket_timeout=1,
                ssl_cert_reqs="none",
                decode_responses=True,
            )
        else:
            test_client = Redis(
                host="127.0.0.1",
                port=action.port if not action.tls else action.tls_port,
                username=action.user[0] if action.user else None,
                password=action.user[1] if action.user else action.password,
                db=action.db,
                ssl=action.tls,
                socket_timeout=1,
                ssl_cert_reqs="none",
                decode_responses=True,
            )

    resp = test_client.ping()
    if not resp:
        LOGGER.error(f"🔗 {library_name} server is not running, exiting ...")
        exit(1)

    LOGGER.info(f"🔗 Running {library_name} query {action.query!r} ...")
    ret = test_client.execute_command(action.query)
    LOGGER.debug(f"🔗 {library_name} query output: {ret}")

    if action.result is not None:
        if action.result not in str(ret):
            LOGGER.error(f"🔗 Result {action.result!r} not found in {library_name} query output, exiting ...")
            LOGGER.error(f"🔗 {library_name} query output: {ret}")
            exit(1)

        LOGGER.info(f"🔗 Result {action.result!r} found in {library_name} query output")
    else:
        if not all(key in ret for key in action.keys):
            LOGGER.error(f"🔗 Not all keys {action.keys} found in {library_name} query output, exiting ...")
            LOGGER.error(f"🔗 {library_name} query output: {ret}")
            exit(1)

        LOGGER.info(f"🔗 All keys {action.keys} found in {library_name} query output")

    LOGGER.info(f"🔗 All {library_name} queries ran successfully")
