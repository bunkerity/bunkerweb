#!/usr/bin/python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from logging import Logger
from time import sleep
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
            # Structural, not text and not `data-i18n`: server-rendered labels are translated by
            # gettext at render time now, so the attribute this used to match no longer exists on
            # anything components/button.html emits (it survives only in JS-built markup, where
            # `t()` supplies the text). Matching the translated label instead would pin the spec to
            # one locale and to a translator's wording. `type="submit"` is unique inside this modal
            # -- its only sibling button is the `type="reset"` cancel. The dot-free predicate is
            # the raw-key guard: with i18next gone there is no English fallback in the browser, so a
            # key missing from a catalog renders as `button.delete` IN THE PAGE and a purely
            # structural selector would match it and pass. Every label these specs assert on is a
            # short noun phrase with no period, while a raw key always has one. Cost of the choice:
            # a translator writing a label that ends in a period reds the spec. Specs run in English.
            '//div[@id="modal-delete-services"]//button[@type="submit"][not(contains(normalize-space(.), "."))]',
            "services",
        )
        # This assertion was vacuous until 2026-08-19. It matched `//td[@id="method-<name>"]` with
        # the name verbatim, but that id has always had its dots stripped (`services.html` at HEAD
        # renders `method-{{ service['id'].replace('.', '-') }}`, and the serverSide column renderer
        # keeps the convention through `idFor`). `app2.example.com` therefore never matched anything
        # -- and because this is a NEGATIVE assertion, "no match" reads as success: the step printed
        # "Service ... deleted ✅" whether or not the service was still there. Found by the UI
        # session while it was flipping the page, in a file it does not own.
        #
        # Two changes. The anchor is now the row's delete button, which carries the **unsanitized**
        # name in `data-service-id` and lives in the always-visible actions column -- an id-based
        # anchor would go blind again if the Method column is toggled off, since DataTables drops
        # invisible columns' cells from the DOM entirely. And the search box is driven first: with
        # `/services` serverSide, only the drawn page exists in the DOM, so "element absent" means
        # "absent from the current page" until the table is filtered to the one name.
        search = safe_get_element(LOGGER, driver, By.XPATH, '//div[@id="services_wrapper"]//input[@type="search"]')
        search.send_keys(Keys.CONTROL, "a")
        search.send_keys(step_data.name)
        sleep(2)

        element = None
        with suppress(TimeoutException):
            element = safe_get_element(
                LOGGER,
                driver,
                By.XPATH,
                f'//button[contains(@class, "delete-service") and @data-service-id="{step_data.name}"]',
                error=True,
                driver_wait=WebDriverWait(driver, 6),
            )
        if element:
            LOGGER.error(f"🦊 Service {step_data.name} was not deleted, exiting ...")
            driver.save_screenshot("error.png")
            exit(1)
        # Clear the filter before handing the page back. The search survives the step otherwise, and
        # the next one looks for a row the table is no longer drawing -- which is how this showed
        # up: `clone_service_draft_2` could not find app1's clone link because the table was still
        # filtered to the service this step had just deleted. Ctrl-A + Backspace rather than
        # `.clear()`, which does not reliably fire the `input` event DataTables redraws on.
        # If this ever flakes: on `/services`, `/bans` and `/reports` the input's event chain now
        # ends in an ajax round trip rather than a client-side redraw, so the deterministic form is
        # `driver.execute_script("$('#services').DataTable().search('').draw();")` plus a wait for
        # the row you expect -- the redraw is no longer synchronous with the call.
        search.send_keys(Keys.CONTROL, "a")
        search.send_keys(Keys.BACKSPACE)
        sleep(2)

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
