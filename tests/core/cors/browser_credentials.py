#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Credentialed fetches from a page of an allowed origin, in a real browser.

Usage: browser_credentials.py <page url> <target url>

Loads <page url> in headless Firefox, then sends two `credentials: 'include'` fetches to <target url>:
a simple one and a preflighted one (JSON POST). A browser refuses either when the CORS answer is
wrong, which `requests` cannot tell: credentialed CORS needs the real response to carry
`Access-Control-Allow-Credentials` as well as the preflight. Prints
`cors browser credentials: both fetches succeeded` on success, exits 1 otherwise.
"""

from os import path
from sys import argv, exit as sys_exit
from time import sleep

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

FETCHES = (
    ("a simple", "{credentials: 'include'}"),
    ("a preflighted", "{method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'}, body: '{}'}"),
)

if len(argv) != 3:
    sys_exit(f"usage: {argv[0]} <page url> <target url>")
page_url, target_url = argv[1], argv[2]

options = Options()
options.add_argument("--headless")
options.accept_insecure_certs = True  # the stack serves its self-signed certificate

# Same geckodriver the `xpath` handler uses when it is installed, else Selenium's own lookup.
geckodriver = "/usr/local/bin/geckodriver"
service = Service(executable_path=geckodriver) if path.exists(geckodriver) else Service()

failures = []
driver = webdriver.Firefox(options=options, service=service)
try:
    driver.set_script_timeout(30)
    driver.delete_all_cookies()
    driver.get(page_url)
    sleep(1.5)
    for label, init in FETCHES:
        result = driver.execute_async_script(f"""
            const done = arguments[arguments.length - 1];
            fetch("{target_url}", {init}).then((r) => done("ok " + r.status)).catch((e) => done("error " + e));
            """)
        print(f"{label} credentialed fetch to {target_url}: {result}")
        if not str(result).startswith("ok"):
            failures.append(f"{label} credentialed fetch failed in the browser: {result}")
finally:
    driver.quit()

if failures:
    sys_exit("\n".join(failures))
print("cors browser credentials: both fetches succeeded")
