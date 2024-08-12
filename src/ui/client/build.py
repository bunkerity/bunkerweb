# I want to run process
from os import getenv
from shutil import copy, move, rmtree, copytree
from subprocess import PIPE, Popen
from pathlib import Path
from re import sub
from typing import List

from utils import run_command

# get current directory
current_directory = Path.cwd()
# needed dirs
opt_dir_templates = current_directory.joinpath("output", "templates")
opt_dir_dashboard = current_directory.joinpath("opt-dashboard")
opt_dir_dashboard_pages = current_directory.joinpath("opt-dashboard", "dashboard", "pages")
opt_dir_setup = current_directory.joinpath("opt-setup")
opt_dir_setup_page = current_directory.joinpath("opt-setup", "setup")
ui_dir_static = current_directory.parent.joinpath("static")
ui_dir_templates = current_directory.parent.joinpath("templates")
legacy_dir_static = current_directory.joinpath("legacy", "static")
legacy_dir_templates = current_directory.joinpath("legacy", "templates")
builder_dir_pages = current_directory.joinpath("builder", "pages")
builder_dir_utils = current_directory.joinpath("builder", "pages", "utils")
ui_dir_builder = current_directory.parent.joinpath("builder")
ui_dir_builder_utils = current_directory.parent.joinpath("builder", "utils")

statics = ("assets", "css", "flags", "img", "js")


def reset():
    """Remove previous directories if exists"""
    print("Resetting...", flush=True)
    remove_dir(opt_dir_dashboard)
    remove_dir(opt_dir_setup)
    remove_dir(ui_dir_static)
    remove_dir(ui_dir_templates)
    remove_dir(ui_dir_builder)


def set_dashboard():
    """Utils to run needed steps to set the dashboard pages (move statics, update and rename templates)"""
    move_template(opt_dir_dashboard_pages, ui_dir_templates)
    move_statics(opt_dir_dashboard, ui_dir_static)


def set_setup():
    """Utils to run needed steps to set the setup page (all-in-one html page)"""
    move_template(opt_dir_setup_page, ui_dir_templates)


def remove_dir(directory: Path):
    """Utils function to remove a directory if exists"""
    if directory.exists():
        print(f"Removing {directory}", flush=True)
        rmtree(directory.as_posix())


def create_dir(directory: Path):
    """Utils function to create a directory if not exists"""
    print(f"Creating {directory}", flush=True)
    directory.mkdir(parents=True, exist_ok=True)


def create_base_dirs():
    """Create the base directories we will need to build front end and add them to flask app"""
    create_dir(opt_dir_dashboard)


def move_template(folder: Path, target_folder: Path):
    """For the define folder, loop on each files and move them to the target folder with some modification (replace relative path to absolute path for example)"""

    base_html = """
    <body>
    {% set data_server_flash = [] %}
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% for category, message in messages %}
        {% if data_server_flash.append({"type": "error" if category == "error" else "success", "title": "dashboard_error" if category == "error" else "dashboard_success", "message": message}) %}{% endif %}
        {% endfor %}
    {% endwith %}
    <div class='hidden' data-csrf-token='{{ csrf_token() }}'></div>
    <div class='hidden' data-server-global='{{data_server_global if data_server_global else {}}}'></div>
    <div class='hidden' data-server-flash='{{data_server_flash|tojson}}'></div>
    <div class='hidden' data-server-builder='{{data_server_builder[1:-1]}}'></div>
    <div id='app'></div>
    </body>
    </html>"""

    def format_template(m):
        replace = m.group(0).replace('href="/', 'href="').replace('src="/', 'src="')
        if ".js" in replace:
            replace = ' nonce="{{ script_nonce }}" ' + replace
        return replace

    for file in folder.rglob("index.html"):
        file_html = base_html
        is_parts = any(part in file.parts for part in ("global-config", "jobs", "services", "modes", "logs", "instances", "home"))
        if is_parts:
            file_html = base_html.replace("data_server_builder[1:-1]", "data_server_builder")

        content = file.read_text()
        content = sub(r'(href|src)="\/(css|js|img|favicon|assets|js)\/[^<]*?(?=<|\/>)', format_template, content)
        # get the content before <body>
        content = content[: content.index("<body>")] + file_html

        # write the new content
        file.write_text(content)

        if target_folder.joinpath(f"{file.parent.name}.html").exists():
            target_folder.joinpath(f"{file.parent.name}.html").unlink()

        copy(file.as_posix(), target_folder.joinpath(f"{file.parent.name}.html").as_posix())

    if folder.parent.is_dir():
        rmtree(folder.parent.as_posix())


def move_statics(folder: Path, target_folder: Path):
    """For the define folder, loop on each files and move them to the target folder."""

    for file in folder.glob("*"):
        if target_folder.joinpath(file.name).is_dir():
            rmtree(target_folder.joinpath(file.name).as_posix())
        move(file.as_posix(), target_folder.joinpath(file.name).as_posix())


def add_legacy():
    # copy dir
    copytree(legacy_dir_static.as_posix(), ui_dir_static.as_posix())
    copytree(legacy_dir_templates.as_posix(), ui_dir_templates.as_posix())


def add_builder_and_widgets():
    # First we want to generate widgets by executing "widgets_generator.py" that is on same level
    if run_command(["/usr/bin/python3", "widgets_generator.py"], current_directory):
        if run_command(["python3", "widgets_generator.py"], current_directory):
            if run_command(["python", "widgets_generator.py"], current_directory):
                exit(1)

    # Create output folders
    copytree(builder_dir_pages.as_posix(), ui_dir_builder.as_posix())
    # I want to loop on each file
    for file in ui_dir_builder.glob("*.py"):
        # I want to replace "from .utils." by "from builder.utils."
        content = file.read_text()
        content = content.replace("from .utils.", "from builder.utils.")
        content = content.replace("# from src.", "from src.")
        content = (
            """from os.path import join, sep
from sys import path as sys_path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

"""
            + content
        )
        file.write_text(content)

    # remove utils folder
    remove_dir(ui_dir_builder_utils)
    copytree(builder_dir_utils.as_posix(), ui_dir_builder_utils.as_posix())


def build():
    """All steps to build the front end and set it to the flask app"""
    reset()
    create_base_dirs()
    add_legacy()
    # Only install packages if not already installed
    if not current_directory.joinpath("node_modules").exists():
        if run_command(["/usr/bin/npm", "install"], current_directory):
            if run_command(["npm", "install"], current_directory):
                exit(1)
    if run_command(["/usr/bin/npm", "run", "build-dashboard"], current_directory):
        if run_command(["npm", "run", "build-dashboard"], current_directory):
            exit(1)
    set_dashboard()
    # run_command(["/usr/bin/npm", "run", "build-setup"], current_directory)
    # set_setup()
    add_builder_and_widgets()


build()
