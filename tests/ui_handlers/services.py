#!/usr/bin/python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from logging import Logger
from time import sleep
from typing import Any

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from utils.ui import access_page, assert_button_click, safe_get_element


def handle_service_flow(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver

    items_str = step_data.item.replace("_", "-")
    if f"/{items_str}{'' if items_str == 'global-config' else 's'}" not in driver.current_url:
        driver.get(f"{ctx.base_url}/{items_str}{'' if items_str == 'global-config' else 's'}")
        sleep(2)

    if step_data.type == "delete":
        assert_button_click(LOGGER, driver, f'//button[contains(@class, "delete-service") and @data-service-id="{step_data.name}"]')
        sleep(2)
        access_page(
            LOGGER,
            driver,
            '//div[@id="modal-delete-services"]//button[@type="submit" and @data-i18n="button.delete"]',
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
                        f"new?clone={step_data.clone}",
                    )
                else:
                    access_page(
                        LOGGER,
                        driver,
                        "//button[@aria-controls='services' and contains(@class, 'btn-bw-green')]",
                        "new",
                    )
            elif step_data.type == "update" and step_data.name not in driver.current_url:
                access_page(
                    LOGGER,
                    driver,
                    f'//a[@href="/services/{step_data.name}"]',
                    step_data.name,
                )

        assert_button_click(
            LOGGER,
            driver,
            f"//button[@data-bs-target='#navs-modes-{step_data.mode}' and not(ancestor::div[@id='floating-modes-menu'])]",
        )
        sleep(1)

        LOGGER.info("🦊 Filling settings ...")
        LOGGER.debug(step_data.config)

        if step_data.item == "service" and step_data.mode in ("easy", "advanced"):
            draft_button = safe_get_element(
                LOGGER,
                driver,
                By.XPATH,
                f'//div[@id="navs-modes-{step_data.mode}"]//button[contains(@class, "toggle-draft")]',
            )
            draft_button_text = draft_button.text.lower()
            if ("draft" in draft_button_text) != step_data.draft:
                if step_data.type == "read":
                    LOGGER.info(
                        f"🦊 Service is {'draft' if 'draft' in draft_button_text else 'online'}, but it should be {'draft' if step_data.draft else 'online'}, exiting ..."
                    )
                    driver.save_screenshot("error.png")
                    exit(1)
                LOGGER.info("🦊 Toggling draft status ...")
                assert_button_click(LOGGER, driver, draft_button)
            elif step_data.type == "read":
                LOGGER.info(f"🦊 Service is {'draft' if 'draft' in draft_button_text else 'online'}, as expected ✅")

        if step_data.mode == "easy":
            if step_data.type == "read":
                selected_option = safe_get_element(LOGGER, driver, By.XPATH, "//ul[@id='templates-dropdown-menu']//button[@aria-selected='true']")
                expected_target = f"#navs-templates-{step_data.template}"
                if selected_option.get_attribute("data-bs-target") != expected_target:
                    LOGGER.error(f"Template shown is not '{step_data.template}': got '{selected_option.get_attribute('data-bs-target')}' instead.")
                    driver.save_screenshot("error.png")
                    exit(1)
            else:
                assert_button_click(LOGGER, driver, "select-template", By.ID)
                assert_button_click(
                    LOGGER,
                    driver,
                    f"//ul[@id='templates-dropdown-menu']//button[@data-bs-target='#navs-templates-{step_data.template}']",
                )
                sleep(1)

            config = dict(step_data.config)

            if step_data.item == "service":
                server_val = config.pop("SERVER_NAME", step_data.name)
                # ensure SERVER_NAME is always the first key
                config = {"SERVER_NAME": server_val} | config

            not_saved_settings = set(config.keys())
            template_steps = safe_get_element(
                LOGGER,
                driver,
                By.XPATH,
                f"//div[starts-with(@id, 'navs-steps-{step_data.template}-')]",
                multiple=True,
            )
            for template_step, step_nav in enumerate(template_steps, start=1):
                LOGGER.info(f"🦊 Filling step {template_step} ...")

                for step_setting in safe_get_element(
                    LOGGER,
                    driver,
                    By.XPATH,
                    f"//div[@id='navs-steps-{step_data.template}-{template_step}']//*[contains(@class, 'plugin-setting') or contains(@class, 'form-select') or contains(@class, 'form-check-input')]",
                    multiple=True,
                ):
                    setting_name = step_setting.get_attribute("name")
                    if setting_name in config:
                        value = config[setting_name]
                        not_saved_settings.remove(setting_name)

                        if step_setting.get_attribute("type") == "checkbox":
                            if ("yes" if step_setting.get_attribute("checked") else "no") != value:
                                if step_data.type == "read":
                                    LOGGER.info(
                                        f"🦊 Element '{setting_name}' in template {step_data.template}'s step {template_step} was found, but the value is wrong, exiting ..."
                                    )
                                    driver.save_screenshot("error.png")
                                    exit(1)
                                assert_button_click(LOGGER, driver, step_setting)
                        elif step_setting.tag_name == "select":
                            selected_option = step_setting.find_element(By.XPATH, "./option[@selected]")
                            if selected_option.get_attribute("value") != value:
                                if step_data.type == "read":
                                    LOGGER.info(
                                        f"🦊 Element '{setting_name}' in template {step_data.template}'s step {template_step} was found, but the value is wrong, exiting ..."
                                    )
                                    driver.save_screenshot("error.png")
                                    exit(1)
                                assert_button_click(LOGGER, driver, step_setting)
                                assert_button_click(LOGGER, step_setting, f'./option[@value="{value}"]')
                        else:
                            if step_setting.get_attribute("value") != value:
                                if step_data.type == "read":
                                    LOGGER.info(
                                        f"🦊 Element '{setting_name}' in template {step_data.template}'s step {template_step} was found, but the value is wrong, exiting ..."
                                    )
                                    driver.save_screenshot("error.png")
                                    exit(1)
                                step_setting.clear()
                                step_setting.send_keys(value)

                        if step_data.type == "read":
                            LOGGER.info(
                                f"🦊 Element '{setting_name}' in template {step_data.template}'s step {template_step} was found and the value is correct ✅"
                            )

                if template_step < len(template_steps):
                    assert_button_click(LOGGER, driver, f'//div[@id="navs-templates-{step_data.template}"]//button[contains(@class, "next-step")]')
                    sleep(1)

                if not not_saved_settings:
                    break

            if not_saved_settings:
                LOGGER.warning(f"🦊 The following settings were not found in template {step_data.template}: {not_saved_settings}")
        if step_data.mode == "advanced":
            keyword_search_input = safe_get_element(LOGGER, driver, By.ID, "plugin-keyword-search-top")

            config = dict(step_data.config)

            if step_data.item == "service":
                server_val = config.pop("SERVER_NAME", step_data.name)
                # ensure SERVER_NAME is always the first key
                config = {"SERVER_NAME": server_val} | config

            for key, value in config.items():
                sleep(0.3)

                custom_driver_wait = WebDriverWait(driver, 1)
                keyword_search_input.clear()
                for c in key:
                    keyword_search_input.send_keys(c)
                    sleep(0.05)
                sleep(0.5)

                setting_element = None
                suffix = None
                import re

                match = re.search(r"^(?P<setting>.+)_(?P<suffix>\d+)$", key)
                if match:
                    setting, suffix = match.group("setting"), match.group("suffix")

                if value is None and not suffix:
                    LOGGER.error(f"🦊 Element '{key}' is not a multiple setting, therefore it should have a value")
                    driver.save_screenshot("error.png")
                    exit(1)

                with suppress(TimeoutException):
                    setting_element = safe_get_element(
                        LOGGER,
                        driver,
                        By.XPATH,
                        f"//div[@id='navs-modes-advanced']//*[@name='{key}']",
                        error=True,
                    )

                if not setting_element:
                    if step_data.type == "read":
                        LOGGER.info(f"🦊 Element '{key}' was not found, as expected ✅")
                        continue

                    if not match:
                        LOGGER.error(f"🦊 Element '{key}' is not a valid multiple setting")
                        driver.save_screenshot("error.png")
                        exit(1)

                    keyword_search_input.clear()
                    for c in setting:
                        keyword_search_input.send_keys(c)
                        sleep(0.05)
                    sleep(0.5)

                    setting_element = None
                    with suppress(TimeoutException):
                        setting_element = safe_get_element(
                            LOGGER,
                            driver,
                            By.XPATH,
                            f"//div[@id='navs-modes-advanced']//*[@name='{setting}']",
                            driver_wait=custom_driver_wait,
                            error=True,
                        )

                    if not setting_element:
                        LOGGER.error(f"🦊 Element '{setting}' is not found in global config settings")
                        driver.save_screenshot("error.png")
                        exit(1)

                with suppress((NoSuchElementException, TimeoutException)):
                    multiple_collapse_parent = setting_element.find_element(By.XPATH, "ancestor::*[contains(@class, 'multiple-collapse')]")
                    parent_id = multiple_collapse_parent.get_attribute("id")
                    LOGGER.debug(f"Element '{key}' is inside a 'multiple-collapse' container with ID '{parent_id}'.")

                    parent_classes = multiple_collapse_parent.get_attribute("class")
                    parent_shown = "show" in parent_classes

                    if suffix:
                        delete_button = None
                        with suppress(TimeoutException):
                            delete_button = safe_get_element(LOGGER, driver, By.ID, f"remove-{parent_id}", error=True)

                        if value is None:
                            if delete_button:
                                if step_data.type == "read":
                                    LOGGER.info(f"🦊 Element '{key}' was found, but it should not be there, exiting ...")
                                    driver.save_screenshot("error.png")
                                    exit(1)
                                assert_button_click(LOGGER, driver, delete_button)
                                sleep(1)
                            continue

                        add_button = None
                        with suppress(TimeoutException):
                            add_button = safe_get_element(LOGGER, driver, By.ID, f"add-{parent_id.rsplit('-', 1)[0]}", error=True)

                        if not add_button:
                            if step_data.type == "read":
                                LOGGER.info(f"🦊 Element '{key}' was not found, but it should be there, exiting ...")
                                driver.save_screenshot("error.png")
                                exit(1)
                            LOGGER.error(f"🦊 Element '{key}' is not a valid multiple setting")
                            driver.save_screenshot("error.png")
                            exit(1)
                        elif step_data.type in ("create", "update"):
                            assert_button_click(LOGGER, driver, add_button)
                            sleep(1)

                        setting_element = safe_get_element(
                            LOGGER,
                            driver,
                            By.XPATH,
                            f"//div[@id='navs-modes-advanced']//*[@name='{key}']",
                            driver_wait=custom_driver_wait,
                        )
                    elif not parent_shown:
                        assert_button_click(LOGGER, driver, f"show-{parent_id}", By.ID)
                        sleep(1)

                if suffix and "multiple_collapse_parent" not in locals():
                    LOGGER.error(f"🦊 Element '{key}' is not a valid multiple setting")
                    driver.save_screenshot("error.png")
                    exit(1)

                if setting_element.get_attribute("type") == "checkbox":
                    if ("yes" if setting_element.get_attribute("checked") else "no") != value:
                        if step_data.type == "read":
                            LOGGER.info(f"🦊 Element '{key}' was found, but the value is wrong, exiting ...")
                            driver.save_screenshot("error.png")
                            exit(1)
                        assert_button_click(LOGGER, driver, setting_element)
                elif setting_element.tag_name == "select":
                    selected_option = setting_element.find_element(By.XPATH, "./option[@selected]")
                    if selected_option.get_attribute("value") != value:
                        if step_data.type == "read":
                            LOGGER.info(f"🦊 Element '{key}' was found, but the value is wrong, exiting ...")
                            driver.save_screenshot("error.png")
                            exit(1)
                        assert_button_click(LOGGER, driver, setting_element)
                        assert_button_click(LOGGER, setting_element, f'./option[@value="{value}"]')
                elif "multivalue-hidden-input" in setting_element.get_attribute("class"):
                    if setting_element.get_attribute("value") != value:
                        if step_data.type == "read":
                            LOGGER.info(f"🦊 Element '{key}' was found, but the value is wrong, exiting ...")
                            driver.save_screenshot("error.png")
                            exit(1)
                        container = setting_element.find_element(By.XPATH, "ancestor::div[contains(@class, 'multivalue-container')]")
                        separator = container.get_attribute("data-separator") or " "
                        remove_multivalue_buttons = container.find_elements(By.XPATH, ".//button[contains(@class, 'remove-multivalue-item')]")
                        for remove_button in reversed(remove_multivalue_buttons):
                            remove_button.click()

                        x = 0
                        split_values = value.split(separator)
                        for val in split_values:
                            multivalue_inputs = container.find_elements(By.XPATH, ".//input[contains(@class, 'multivalue-input')]")
                            multivalue_inputs[-1].send_keys(val)
                            if x < len(split_values) - 1:
                                add_buttons = container.find_elements(By.XPATH, ".//button[contains(@class, 'add-multivalue-item')]")
                                add_buttons[-1].click()
                            x += 1
                else:
                    if setting_element.get_attribute("value") != value:
                        if step_data.type == "read":
                            LOGGER.info(f"🦊 Element '{key}' was found, but the value is wrong, exiting ...")
                            driver.save_screenshot("error.png")
                            exit(1)
                        setting_element.clear()
                        setting_element.send_keys(value)

                if step_data.type == "read":
                    LOGGER.info(f"🦊 Element '{key}' was found and the value is correct ✅")
        elif step_data.mode == "raw":
            raw_config_textarea = safe_get_element(LOGGER, driver, By.ID, "raw-config")
            raw_config = raw_config_textarea.get_attribute("value")
            raw_config_dict: dict[str, str | None] = {}
            for line in raw_config.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
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
                    elif actual != expected:
                        LOGGER.info(f"🦊 Element '{key}' was found, but the value is wrong (actual {actual}, expected {expected}), exiting ...")
                        driver.save_screenshot("error.png")
                        exit(1)
                    elif key != "IS_DRAFT":
                        LOGGER.info(f"🦊 Element '{key}' was found and the value is correct ✅")
                else:
                    if actual != expected:
                        raw_config_dict[key] = expected

            if step_data.type in ("create", "update"):
                raw_config_textarea.clear()
                raw_config_textarea.send_keys("\n".join(f"{key}={value}" for key, value in raw_config_dict.items()))

        if step_data.type in ("create", "update"):
            assert_button_click(
                LOGGER,
                driver,
                f"//div[@id='navs-modes-{step_data.mode}']//button[contains(@class, 'save-settings')]",
            )
