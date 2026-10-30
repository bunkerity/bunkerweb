#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from pathlib import Path
from tempfile import mkdtemp
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from utils.ui import safe_get_element


def handle_upload(LOGGER: Logger, ctx, step_data: Any) -> None:
    source = Path(step_data.path).resolve()
    if not source.exists():
        LOGGER.error(f"🦊 Upload source {source} does not exist")
        exit(1)

    if source.is_dir():
        # The plugin archive is built here, so the repository keeps the plugin as plain text files
        archive = Path(mkdtemp(prefix="bw-ui-upload-")) / f"{source.name}.zip"
        with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
            for file in sorted(source.rglob("*")):
                if file.is_file():
                    zip_file.write(file, file.relative_to(source).as_posix())
        source = archive

    safe_get_element(LOGGER, ctx.driver, step_data.by, step_data.selector).send_keys(str(source))
    LOGGER.info(f"🦊 Uploaded {source.name} through {step_data.selector} ✅")
