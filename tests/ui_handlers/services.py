#!/usr/bin/python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from logging import Logger
from time import sleep
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from utils.ui import access_page, assert_button_click, on_page, safe_get_element


def handle_service_flow(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver

    items_str = step_data.item.replace("_", "-")
    # Path-only match: `/loading?next=/services` is not the services page, and taking it for one
    # skips the navigation below and runs the whole flow against the interstitial.
    if not on_page(driver, f"{items_str}{'' if items_str == 'global-config' else 's'}"):
        driver.get(f"{ctx.base_url}/{items_str}{'' if items_str == 'global-config' else 's'}")
        sleep(2)

    if step_data.type == "delete":
        assert_button_click(LOGGER, driver, f'//button[contains(@class, "delete-service") and @data-service-id="{step_data.name}"]')
        sleep(2)
        access_page(
            LOGGER,
            driver,
            # The label span carries data-i18n, never the <button> -- components/button.html puts
            # it there on purpose so translating the label cannot wipe the button's own markup.
            '//div[@id="modal-delete-services"]//button[@type="submit"][.//span[@data-i18n="button.delete"]]',
            "services",
        )
        element = None
        with suppress(TimeoutException):
            element = safe_get_element(
                LOGGER,
                driver,
                By.XPATH,
                f'//td[@id="method-{step_data.name}" and contains(text(), "ui")]',
                error=True,
                driver_wait=WebDriverWait(driver, 6),
            )
        if element:
            LOGGER.error(f"🦊 Service {step_data.name} was not deleted, exiting ...")
            driver.save_screenshot("error.png")
            exit(1)
        LOGGER.info(f"🦊 Service {step_data.name} deleted ✅")
        return

    if step_data.item in ("global_config", "service"):
        if step_data.item == "service":
            if step_data.type == "create":
                if step_data.clone:
                    access_page(
                        LOGGER,
                        driver,
                        f'//a[@data-i18n="tooltip.link.clone_service" and contains(@data-i18n-options, "{step_data.clone}")]',
                        # Path only: `on_page` matches the URL path, so a `?clone=` query here never
                        # matched and the clone step timed out on the page it was already on. Which
                        # service was cloned is proven by the settings read that follows.
                        "new",
                    )
                else:
                    # The create action is a link in the page-head band since the 1.7 reskin, not
                    # the green button the DataTable toolbar used to carry.
                    access_page(
                        LOGGER,
                        driver,
                        "//*[@id='services-create-btn']",
                        "new",
                    )
            # `read` navigates too: saving leaves the browser on /loading, the check above then
            # lands it on the services list, and a read that assumed it was still on the service
            # page would look for the settings editor on a DataTable.
            elif step_data.type in ("update", "read") and step_data.name not in driver.current_url:
                access_page(
                    LOGGER,
                    driver,
                    f'//a[@href="/services/{step_data.name}"]',
                    step_data.name,
                )

        # Compose and Raw are the only panes left: the settings monolith was split, per-plugin
        # editing moved to /<page>/plugins/<plugin>, and #navs-modes-easy / #navs-modes-advanced
        # were deleted with it. On /services and /global-settings the switch is a LINK rather
        # than a Bootstrap tab -- both panes are re-rendered from the database on navigation, so
        # an unsaved twin cannot exist -- which is why the pane is selected by URL here.
        #
        # Value round-trips go through the raw editor: it posts the same keys through the same
        # route as compose, and a `KEY=value` document is a far steadier target than walking one
        # widget per setting. The compose shelf itself (the plugin on/off toggles) has no
        # coverage in this handler yet.
        if step_data.mode != "raw":
            LOGGER.warning(f"🦊 Mode '{step_data.mode}' no longer exists in the UI, reading and writing through raw")

        current = urlsplit(driver.current_url)
        query = dict(parse_qsl(current.query, keep_blank_values=True))
        if query.get("mode") != "raw":
            query["mode"] = "raw"
            driver.get(urlunsplit(current._replace(query=urlencode(query))))
            sleep(2)

        LOGGER.info("🦊 Filling settings ...")
        LOGGER.debug(step_data.config)

        # The <textarea id="raw-config"> still backs the editor, but it is `d-none` and only
        # carries the value the server rendered: ACE owns what is on screen and what the form
        # posts, so both directions go through ace.edit() -- clear()/send_keys() on the hidden
        # textarea raises "element not interactable".
        raw_config = driver.execute_script("return ace.edit('raw-config-editor').getValue();")
        raw_config_dict: dict[str, str | None] = {}
        for line in raw_config.splitlines():
            # One line per key. A multiline value (a PEM block in a `file` setting) is folded
            # away by this parse and would be rewritten as its first line alone, so a spec that
            # needs one has to go through compose, not here.
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            raw_config_dict[key.strip()] = value.strip().strip('"')
        LOGGER.debug(f"Raw config dict: {raw_config_dict}")

        if step_data.item == "service" and step_data.type == "read":
            if raw_config_dict.get("IS_DRAFT", "no") != ("yes" if step_data.draft else "no"):
                LOGGER.info(
                    f"🦊 Service is {'draft' if raw_config_dict.get('IS_DRAFT', 'no') == 'yes' else 'online'}, but it should be {'draft' if step_data.draft else 'online'}, exiting ..."
                )
                driver.save_screenshot("error.png")
                exit(1)
            LOGGER.info(f"🦊 Service is {'draft' if raw_config_dict.get('IS_DRAFT', 'no') == 'yes' else 'online'}, as expected ✅")

        config = dict(step_data.config)

        if step_data.item == "service":
            server_val = config.pop("SERVER_NAME", step_data.name)
            # ensure SERVER_NAME is always the first key
            config = {"SERVER_NAME": server_val, "IS_DRAFT": "yes" if step_data.draft else "no"} | config

        for key, expected in config.items():
            actual = raw_config_dict.get(key)

            if step_data.type == "read":
                if actual is None:
                    if expected is not None:
                        LOGGER.info(f"🦊 Element '{key}' was not found, but it should be there, exiting ...")
                        driver.save_screenshot("error.png")
                        exit(1)
                    LOGGER.info(f"🦊 Element '{key}' was not found, as expected ✅")
                elif expected is None:
                    LOGGER.info(f"🦊 Element '{key}' was found, but it should not be there, exiting ...")
                    driver.save_screenshot("error.png")
                    exit(1)
                elif actual != expected:
                    LOGGER.info(f"🦊 Element '{key}' was found, but the value is wrong (actual {actual}, expected {expected}), exiting ...")
                    driver.save_screenshot("error.png")
                    exit(1)
                elif key != "IS_DRAFT":
                    LOGGER.info(f"🦊 Element '{key}' was found and the value is correct ✅")
            elif expected is None:
                # A null in the spec means "this key must go away", which in a KEY=value document
                # is the line being absent, not an empty value.
                raw_config_dict.pop(key, None)
            elif actual != expected:
                raw_config_dict[key] = expected

        if step_data.type in ("create", "update"):
            document = "\n".join(f"{key}={value}" for key, value in raw_config_dict.items())
            driver.execute_script("ace.edit('raw-config-editor').setValue(arguments[0], -1);", document)
            sleep(0.5)
            assert_button_click(
                LOGGER,
                driver,
                "//div[@id='navs-modes-raw']//button[contains(@class, 'save-settings')]",
            )

            # Saving goes through /loading while the scheduler applies the change, and the page
            # redirects itself when it is done. Returning here without waiting handed the next
            # step a browser sitting on the interstitial: it navigated away on its own, killing
            # the redirect, and then looked for a service the list had not picked up yet.
            waited = 0
            while on_page(driver, "loading") and waited < 120:
                sleep(1)
                waited += 1
            if on_page(driver, "loading"):
                LOGGER.error("🦊 Settings save never left the loading page, exiting ...")
                driver.save_screenshot("error.png")
                exit(1)
            sleep(2)
