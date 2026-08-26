#!/usr/bin/env python3

from argparse import ArgumentParser
from os import R_OK, W_OK, X_OK, access, getenv, sep
from os.path import join
from pathlib import Path
from shutil import rmtree
from ssl import PROTOCOL_TLS_CLIENT, SSLContext, SSLError
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Any, Dict

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore
from Configurator import Configurator
from Templator import Templator
from resource_group_resolver import expand_config_groups  # type: ignore
from redirect_resolver import expand_service_redirects  # type: ignore
from upstream_resolver import expand_service_upstreams  # type: ignore
from plugin_extensions import run_config_extensions  # type: ignore

DB_PATH = Path(sep, "usr", "share", "bunkerweb", "db")

LOGGER = getLogger("GENERATOR")

# The public root bundle every Lua cosocket verifies against, shipped in the image and named by
# `lua_ssl_trusted_certificate` in confs/http.conf and confs/stream.conf.
LUA_TRUSTED_CA_SOURCE = Path(sep, "usr", "share", "bunkerweb", "misc", "root-ca.pem")
# Written into the rendered tree, so those same two templates can name it and push-configs ships
# it to every instance in the same tar as the configuration that points at it.
LUA_TRUSTED_CA_BUNDLE = "lua-trusted-ca.pem"


def write_lua_trusted_ca_bundle(redis_ssl_ca: str, output_path: Path) -> None:
    """Append the operator's Redis/Valkey CA onto the trust store the Lua request path uses.

    `clusterstore.lua` reaches Redis through an OpenResty cosocket, and a cosocket has no
    per-connection trust store: it verifies against the single `lua_ssl_trusted_certificate`
    file of the surrounding NGINX configuration. That is why REDIS_SSL_CA could not reach the
    request path at all, and why it can only reach it by joining that one file.

    Appended, never substituted. The same store is what antibot, BunkerNet and CrowdSec verify
    their outbound HTTPS against, so replacing it with the operator's CA would break all three
    on the whole fleet; adding to it only grants trust the operator asked for.

    Unset REDIS_SSL_CA writes nothing, and the two templates keep naming the baked-in bundle --
    the rendered tree is then byte-for-byte what it was before this existed.

    Every failure below is fatal on purpose. `lua_ssl_trusted_certificate` pointing at a missing
    or malformed file makes NGINX refuse to start, so a bad value has to stop generation here:
    push-configs treats a non-zero generator as "render failed", pushes nothing, and every
    instance keeps serving the configuration it already has.
    """
    redis_ssl_ca = (redis_ssl_ca or "").strip()
    if not redis_ssl_ca:
        return

    ca_file = Path(redis_ssl_ca)
    if not ca_file.is_file():
        LOGGER.error(f"REDIS_SSL_CA is set but is not a file : {ca_file}")
        sys_exit(1)
    elif not access(ca_file, R_OK):
        LOGGER.error(f"REDIS_SSL_CA is set but can't be read : {ca_file}")
        sys_exit(1)

    if not LUA_TRUSTED_CA_SOURCE.is_file() or not access(LUA_TRUSTED_CA_SOURCE, R_OK):
        LOGGER.error(
            f"REDIS_SSL_CA is set but the root bundle is missing : {LUA_TRUSTED_CA_SOURCE}"
            " (refusing to ship a trust store without it, which would break every other Lua HTTPS client)"
        )
        sys_exit(1)

    # Bytes, not text. `read_text()` normalises line endings, and the shipped root bundle uses CRLF
    # (1794 of them) -- reading it as text and writing it back silently rewrote 1794 bytes of a
    # bundle this is only supposed to APPEND to. OpenSSL accepts either ending, so nothing would
    # have failed; the roots would just no longer have been the bytes that shipped.
    try:
        roots = LUA_TRUSTED_CA_SOURCE.read_bytes()
        operator_ca = ca_file.read_bytes()
    except OSError as e:
        LOGGER.error(f"REDIS_SSL_CA : can't read the CA material ({e})")
        sys_exit(1)

    # `load_verify_locations(cadata=...)` reads PEM only from a str -- bytes there mean DER.
    try:
        roots_pem = roots.decode()
        operator_pem = operator_ca.decode()
    except UnicodeDecodeError as e:
        LOGGER.error(f"REDIS_SSL_CA : the CA material is not text, so it is not PEM ({e})")
        sys_exit(1)

    # The operator's file is validated ON ITS OWN, and that separation is load-bearing: OpenSSL
    # silently ignores non-PEM text trailing a valid bundle, so validating only the concatenation
    # would happily accept a REDIS_SSL_CA containing nothing but garbage and ship a trust store
    # that does not actually trust the Redis/Valkey CA.
    try:
        SSLContext(PROTOCOL_TLS_CLIENT).load_verify_locations(cadata=operator_pem)
    except (SSLError, ValueError) as e:
        LOGGER.error(f"REDIS_SSL_CA is not a valid PEM CA bundle : {ca_file} ({e})")
        sys_exit(1)

    combined = (roots if roots.endswith(b"\n") else roots + b"\n") + operator_ca

    try:
        combined_ctx = SSLContext(PROTOCOL_TLS_CLIENT)
        combined_ctx.load_verify_locations(cadata=combined.decode())
        root_ctx = SSLContext(PROTOCOL_TLS_CLIENT)
        root_ctx.load_verify_locations(cadata=roots_pem)
    except (SSLError, ValueError, UnicodeDecodeError) as e:
        LOGGER.error(f"REDIS_SSL_CA : the combined trust bundle is not loadable ({e})")
        sys_exit(1)

    # "Append, never replace", asserted instead of assumed. Fewer certificates than the root
    # bundle alone means the concatenation lost some, and the loss would surface as every Lua
    # HTTPS client failing verification across the fleet rather than as an error here.
    if len(combined_ctx.get_ca_certs()) < len(root_ctx.get_ca_certs()):
        LOGGER.error(f"REDIS_SSL_CA : the combined trust bundle dropped certificates from {LUA_TRUSTED_CA_SOURCE}")
        sys_exit(1)

    bundle_path = output_path.joinpath(LUA_TRUSTED_CA_BUNDLE)
    bundle_path.write_bytes(combined)
    LOGGER.info(f"Appended REDIS_SSL_CA ({ca_file}) onto the Lua trust bundle : {bundle_path}")


if __name__ == "__main__":
    try:
        # Parse arguments
        parser = ArgumentParser(description="BunkerWeb config generator")
        parser.add_argument("--settings", default=join(sep, "usr", "share", "bunkerweb", "settings.json"), type=str, help="file containing the main settings")
        parser.add_argument(
            "--templates", default=join(sep, "usr", "share", "bunkerweb", "confs"), type=str, help="directory containing the main template files"
        )
        parser.add_argument("--core", default=join(sep, "usr", "share", "bunkerweb", "core"), type=str, help="directory containing the core plugins")
        parser.add_argument("--plugins", default=join(sep, "etc", "bunkerweb", "plugins"), type=str, help="directory containing the external plugins")
        parser.add_argument("--pro-plugins", default=join(sep, "etc", "bunkerweb", "pro", "plugins"), type=str, help="directory containing the pro plugins")
        parser.add_argument("--output", default=join(sep, "etc", "nginx"), type=str, help="where to write the rendered files")
        parser.add_argument("--target", default=join(sep, "etc", "nginx"), type=str, help="where nginx will search for configurations files")
        parser.add_argument("--variables", type=str, help="path to the file containing environment variables")
        args = parser.parse_args()

        settings_path = Path(args.settings)
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        templates_path = Path(args.templates)
        templates_path.mkdir(parents=True, exist_ok=True)

        core_path = Path(args.core)
        core_path.mkdir(parents=True, exist_ok=True)

        plugins_path = Path(args.plugins)
        plugins_path.mkdir(parents=True, exist_ok=True)

        pro_plugins_path = Path(args.pro_plugins)
        pro_plugins_path.mkdir(parents=True, exist_ok=True)

        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)

        target_path = Path(args.target)
        target_path.mkdir(parents=True, exist_ok=True)

        LOGGER.info("Generator started ...")
        LOGGER.info(f"Settings : {settings_path}")
        LOGGER.info(f"Templates : {templates_path}")
        LOGGER.info(f"Core : {core_path}")
        LOGGER.info(f"Plugins : {plugins_path}")
        LOGGER.info(f"Pro plugins : {pro_plugins_path}")
        LOGGER.info(f"Output : {output_path}")
        LOGGER.info(f"Target : {target_path}")

        dotenv_env = {}
        if args.variables:
            variables_path = Path(args.variables)
            LOGGER.info(f"Variables : {variables_path}")
            with variables_path.open() as f:
                dotenv_env = dict(line.strip().split("=", 1) for line in f if line.strip() and not line.startswith("#") and "=" in line)

        db = None
        if DB_PATH.is_dir():
            if DB_PATH.as_posix() not in sys_path:
                sys_path.append(DB_PATH.as_posix())

            from Database import Database  # type: ignore

            db = Database(LOGGER, sqlalchemy_string=dotenv_env.get("DATABASE_URI", getenv("DATABASE_URI", None)))

        if args.variables:
            # Check existences and permissions
            LOGGER.info("Checking arguments ...")
            files = [settings_path, variables_path]
            paths_rx = [core_path, plugins_path, pro_plugins_path, templates_path]
            paths_rwx = [output_path]
            for file in files:
                if not file.is_file():
                    LOGGER.error(f"Missing file : {file}")
                    sys_exit(1)
                elif not access(file, R_OK):
                    LOGGER.error(f"Can't read file : {file}")
                    sys_exit(1)
            for path in paths_rx + paths_rwx:
                if not path.is_dir():
                    LOGGER.error(f"Missing directory : {path}")
                    sys_exit(1)
                elif not access(path, R_OK | X_OK):
                    LOGGER.error(f"Missing RX rights on directory : {path}")
                    sys_exit(1)
            for path in paths_rwx:
                if not access(path, W_OK):
                    LOGGER.error(f"Missing W rights on directory : {path}")
                    sys_exit(1)

            # Compute the config
            LOGGER.info("Computing config ...")
            config: Dict[str, Any] = Configurator(
                settings_path.as_posix(),
                core_path.as_posix(),
                plugins_path.as_posix(),
                pro_plugins_path.as_posix(),
                variables_path.as_posix(),
                LOGGER,
            ).get_config(db)
            full_config = config.copy()
            default_config = config.copy()
        else:
            config: Dict[str, Any] = db.get_non_default_settings() | {"DATABASE_URI": db.database_uri}
            full_config = db.get_config(methods=True) | {"DATABASE_URI": {"default": "sqlite:////var/lib/bunkerweb/db.sqlite3", "value": db.database_uri}}
            default_config = {setting: data["default"] for setting, data in full_config.items()}
            full_config = {setting: data["value"] for setting, data in full_config.items()}

        # Expand @resource-group tokens in list settings to flat values just before rendering,
        # so NGINX/Lua only ever see literal values (the @name tokens stay stored in the DB).
        config = expand_config_groups(config, db, LOGGER)
        full_config = expand_config_groups(full_config, db, LOGGER)

        # Flatten redirect resources attached to a service into the next free REDIRECT_*
        # suffixes, so the redirect template renders them exactly like inline rules. Runs
        # after the group expansion because a resource carries literal values only.
        config = expand_service_redirects(config, db, LOGGER)
        full_config = expand_service_redirects(full_config, db, LOGGER)

        # Same treatment for upstream pools: each attachment takes the next free reverse-proxy
        # suffix, and every pool used by at least one service is declared globally for the
        # http-context upstream {} blocks.
        config = expand_service_upstreams(config, db, LOGGER)
        full_config = expand_service_upstreams(full_config, db, LOGGER)

        # Let plugins compile their own stored documents into derived settings and a cache
        # artefact. Runs last, so a compiler sees groups, redirects and upstreams already
        # expanded, and before the render, so its variables reach the templates. A failure
        # raises: nothing is written and the previous push stays live on every instance.
        config, full_config = run_config_extensions(db, config, full_config, LOGGER)

        # Remove old files. iterdir(), not glob("*"), which skips dotfiles: the instance's
        # ".bw-applied" push marker used to survive here, so a restart regenerated the whole
        # directory as the loading configuration while still claiming the last pushed digest
        # was applied. The scheduler then re-sent that identical configuration, the digest
        # matched, the push was skipped, and the instance stayed on the loading config.
        LOGGER.info("Removing old files ...")
        for file in Path(args.output).iterdir():
            if file.is_symlink() or file.is_file():
                file.unlink()
            elif file.is_dir():
                rmtree(file.as_posix(), ignore_errors=True)

        # After the wipe (which would delete it) and before the render (which needs it to exist
        # by the time http.conf/stream.conf name it). A failure here exits non-zero, so nothing
        # is rendered and nothing is pushed.
        write_lua_trusted_ca_bundle(config.get("REDIS_SSL_CA", ""), output_path)

        # Render the templates
        LOGGER.info("Rendering templates ...")
        templator = Templator(
            templates_path.as_posix(),
            core_path.as_posix(),
            plugins_path.as_posix(),
            pro_plugins_path.as_posix(),
            output_path.as_posix(),
            target_path.as_posix(),
            config,
            default_config,
            full_config,
        )
        templator.render()
    except SystemExit as e:
        raise e
    except:
        LOGGER.error(f"Exception while executing generator : {format_exc()}")
        sys_exit(1)

    # We're done
    LOGGER.info("Generator successfully executed !")
