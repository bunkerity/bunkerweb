from contextlib import suppress
from ipaddress import IPv4Address
from os import getenv, sep
from pathlib import Path
from traceback import format_exc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from socket import gaierror, gethostbyname
from typing import List

try:
    firefox_options = Options()
    firefox_options.add_argument("--headless")

    dnsbl_servers = []

    print("ℹ️ Starting Firefox ...", flush=True)
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()
        driver_wait = WebDriverWait(driver, 10)

        print("ℹ️ Navigating to https://www.dnsbl.info/dnsbl-list.php ...", flush=True)
        driver.get("https://www.dnsbl.info/dnsbl-list.php")

        print("ℹ️ Getting the DNSBL servers ...")
        links: List[WebElement] = driver_wait.until(EC.presence_of_all_elements_located((By.XPATH, "//table[@class='body_sub_body']//td")))

        for link in links:
            content = link.text
            if content:
                dnsbl_servers.append(content)

    print("ℹ️ Checking the DNSBL servers for a banned IP ...", flush=True)

    output_path = Path(sep, "output", "dnsbl_ip.txt") if getenv("TEST_TYPE", "docker") == "docker" else Path(".", "dnsbl_ip.txt")

    for ip_address in [IPv4Address(f"{x}.0.0.3") for x in range(1, 256)]:
        for dnsbl_server in dnsbl_servers:
            with suppress(gaierror):
                gethostbyname(f"{ip_address.reverse_pointer.replace('.in-addr.arpa', '')}.{dnsbl_server}")
                print(
                    f"✅ {ip_address} is banned on {dnsbl_server}, saving it to {output_path}",
                    flush=True,
                )
                output_path.write_text(f"{ip_address} {dnsbl_server}")
                exit(0)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
