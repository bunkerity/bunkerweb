#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from shutil import rmtree
from subprocess import STDOUT, Popen, PIPE, run
from sys import exit as sys_exit, path as sys_path, version_info

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("LETS-ENCRYPT-DNS.install-deps", getenv("LOG_LEVEL", "INFO"))
status = 0

PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt_dns")
LIB_PATH = Path(sep, "var", "lib", "bunkerweb", "letsencrypt_dns")
PIP_PATH = LIB_PATH.joinpath("pip")
PYTHON_DEPS_PATH = LIB_PATH.joinpath("python")

try:

    # * Check if we're using let's encrypt DNS
    all_domains = getenv("SERVER_NAME", "")

    if not all_domains:
        LOGGER.warning("There are no server names, skipping additional dependencies installation...")
        sys_exit(0)

    use_letsencrypt_dns = False
    is_multisite = getenv("MULTISITE", "no") == "yes"
    server_names = all_domains.split(" ")

    if not is_multisite:
        use_letsencrypt_dns = getenv("AUTO_LETS_ENCRYPT_DNS", "no") == "yes"
    else:
        for first_server in server_names:
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT_DNS", getenv("AUTO_LETS_ENCRYPT_DNS", "no")) == "yes":
                use_letsencrypt_dns = True
                break

    if not use_letsencrypt_dns:
        LOGGER.info("Let's Encrypt DNS is not activated, skipping additional dependencies installation...")
        sys_exit(0)

    if PYTHON_DEPS_PATH.is_dir() and list(PYTHON_DEPS_PATH.iterdir()):
        LOGGER.info("Additional dependencies already installed, checking for updates...")

        deps = {}
        with PLUGIN_PATH.joinpath("requirements.in").open("r") as f:
            for line in f:
                if (line := line.strip()) and not line.startswith("#"):
                    package, version = line.split("==")
                    deps[package] = version

        all_deps_up_to_date = True
        process = Popen(
            ["python3", "-m", "pip", "freeze", "--local"],
            stdout=PIPE,
            stderr=STDOUT,
            universal_newlines=True,
            env=environ | {"PYTHONPATH": PYTHON_DEPS_PATH.as_posix()},
        )
        while process.poll() is None:
            if process.stdout is not None:
                for line in process.stdout:
                    if (line := line.strip()) and not line.startswith("#"):
                        split = line.split("==")
                        if len(split) != 2:
                            continue
                        package, version = split

                        if package in deps and deps[package] != version:
                            LOGGER.info(f"⚠️ {package} is outdated: {version} -> {deps[package]}")
                            all_deps_up_to_date = False

        if process.returncode != 0:
            LOGGER.error("❌ Error while checking additional python dependencies, updating just in case...")
        elif all_deps_up_to_date:
            LOGGER.info("✅ All additional dependencies are up to date")
            sys_exit(0)
        else:
            LOGGER.warning("Some additional dependencies are outdated, updating...")
        rmtree(PYTHON_DEPS_PATH, ignore_errors=True)
    else:
        LOGGER.info("Deps path not found, installing additional dependencies...")

    PYTHON_DEPS_PATH.mkdir(parents=True, exist_ok=True)

    pip_cmd = ["python3", "-m", "pip"]
    cmd_env = environ | {"PYTHONPATH": PYTHON_DEPS_PATH.as_posix()}

    if PIP_PATH.joinpath("usr", "local", "bin").is_dir() and PIP_PATH.joinpath("usr", "local", "lib").is_dir():
        pip_cmd = [PIP_PATH.joinpath("usr", "local", "bin", "pip3").as_posix()]
        cmd_env["PYTHONPATH"] += ":" + PIP_PATH.joinpath("usr", "local", "lib", f"python{version_info.major}.{version_info.minor}", "site-packages").as_posix()
    else:
        process = run(pip_cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)

        if process.returncode != 0:
            LOGGER.warning("Pip is not installed, installing pip locally...")
            process = Popen(
                ["python3", "-m", "ensurepip", "--root", PIP_PATH.as_posix()],
                stdout=PIPE,
                stderr=STDOUT,
                universal_newlines=True,
            )
            while process.poll() is None:
                if process.stdout is not None:
                    for line in process.stdout:
                        LOGGER.debug(line.strip())

            if process.returncode != 0:
                LOGGER.error("❌ Error while ensuring pip is up to date")
                sys_exit(1)

            LOGGER.info("✅ Pip installed successfully")

            pip_cmd = [PIP_PATH.joinpath("usr", "local", "bin", "pip3").as_posix()]
            cmd_env["PYTHONPATH"] += (
                ":" + PIP_PATH.joinpath("usr", "local", "lib", f"python{version_info.major}.{version_info.minor}", "site-packages").as_posix()
            )

    LOGGER.info("Installing additional python dependencies...")
    current_date = datetime.now()
    process = Popen(
        pip_cmd
        + [
            "install",
            "--no-cache-dir",
            "--require-hashes",
            "--ignore-installed",
            "--target",
            PYTHON_DEPS_PATH.as_posix(),
            "-r",
            PLUGIN_PATH.joinpath("requirements.txt").as_posix(),
        ],
        stdout=PIPE,
        stderr=STDOUT,
        universal_newlines=True,
        env=cmd_env,
    )
    while process.poll() is None:
        if process.stdout is not None:
            for line in process.stdout:
                if datetime.now() - current_date > timedelta(seconds=5):
                    LOGGER.info("⏳ Still installing additional python dependencies...")
                    current_date = datetime.now()
                LOGGER.debug(line.strip())

    if process.returncode != 0:
        LOGGER.error("❌ Error while installing additional python dependencies")
        sys_exit(1)

    LOGGER.info("✅ Additional dependencies installed successfully")
except SystemExit as e:
    status = e.code
except:
    status = 1
    LOGGER.exception("Exception while running install-dependencies.py")

sys_exit(status)
