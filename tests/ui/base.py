from contextlib import suppress
from functools import partial
from logging import DEBUG, INFO, _nameToLevel, basicConfig, error as log_error, info as log_info, warning as log_warning
from os import getenv, listdir, sep
from pathlib import Path
from time import sleep

from requests import RequestException, get
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
    level=DEBUG if getenv("ACTIONS_STEP_DEBUG", False) else _nameToLevel.get(getenv("LOG_LEVEL", "INFO").upper(), INFO),
)

os_release_path = Path(sep, "etc", "os-release")
DEFAULT_SERVER = "192.168.0.2" if os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8") else "127.0.0.1"

TEST_TYPE = getenv("TEST_TYPE", "docker")
local_geckodriver = "geckodriver" in listdir(Path.cwd())

FIREFOX_OPTIONS = Options()
if not local_geckodriver:
    FIREFOX_OPTIONS.add_argument("--headless")
    FIREFOX_OPTIONS.add_argument("--width=2560")
    FIREFOX_OPTIONS.add_argument("--height=1440")
FIREFOX_OPTIONS.log.level = "trace"  # type: ignore

ready = False
retries = 0
while not ready:
    with suppress(RequestException):
        status_code = get(f"http://{DEFAULT_SERVER}/setup").status_code

        if status_code > 500 and status_code != 502:
            log_error("An error occurred with the server, exiting ...")
            exit(1)

        ready = status_code < 400

    if retries > 20:
        log_error("UI took too long to be ready, exiting ...")
        exit(1)
    elif not ready:
        retries += 1
        log_warning("Waiting for UI to be ready, retrying in 5s ...")
        sleep(5)

driver_func = partial(webdriver.Firefox, service=Service(log_output="./geckodriver.log"), options=FIREFOX_OPTIONS)
if TEST_TYPE == "dev":
    driver_func = partial(
        webdriver.Firefox,
        service=Service(executable_path="./geckodriver" if local_geckodriver else "/usr/local/bin/geckodriver", log_output="./geckodriver.log"),
        options=FIREFOX_OPTIONS,
    )

DRIVER = driver_func()

log_info("UI is ready, starting tests ...")

__all__ = ("DEFAULT_SERVER", "TEST_TYPE", "DRIVER")
