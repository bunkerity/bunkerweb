# I want to run process
from shutil import copy, move, rmtree
from subprocess import PIPE, Popen
from pathlib import Path
from re import sub
from typing import List

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

statics = ("assets", "css", "flags", "img", "js")


def reset():
    """Remove previous directories if exists"""
    print("Resetting...", flush=True)
    remove_dir(opt_dir_dashboard)
    remove_dir(opt_dir_setup)


def set_dashboard():
    """Utils to run needed steps to set the dashboard pages (move statics, update and rename templates)"""
    move_template(opt_dir_dashboard_pages, ui_dir_templates)
    move_statics(opt_dir_dashboard, ui_dir_static)


def set_setup():
    """Utils to run needed steps to set the setup page (all-in-one html page)"""
    move_template(opt_dir_setup_page, ui_dir_templates)


def run_command(command: List[str]):
    """Utils to run a subprocess command. This is usefull to run npm commands to build vite project"""
    print(f"Running command: {command}", flush=True)
    process = Popen(command, stdout=PIPE, stderr=PIPE, cwd=current_directory, text=True)
    while process.poll() is None:
        if process.stdout is not None:
            for line in process.stdout:
                print(line.strip(), flush=True)

    if process.returncode != 0:
        print("Error while running command", flush=True)
        print(process.stdout, flush=True)
        print(process.stderr, flush=True)
        exit(1)


def remove_dir(directory: Path):
    """Utils function to remove a directory if exists"""
    if directory.exists():
        print(f"Removing {directory}", flush=True)
        rmtree(directory)


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
        if "global-config" in file.parts or "jobs" in file.parts or "services" in file.parts:
            base_html = base_html.replace("data_server_builder[1:-1]", "data_server_builder")

        with file.open("r") as f:
            content = f.read()

        content = sub(r'(href|src)="\/(css|js|img|favicon|assets|js)\/[^<]*?(?=<|\/>)', format_template, content)
        # get the content before <body>
        content = content[: content.index("<body>")] + base_html

        # write the new content
        with file.open("w") as f:
            f.write(content)

        if target_folder.joinpath(f"{file.parent.name}.html").exists():
            target_folder.joinpath(f"{file.parent.name}.html").unlink()

        copy(file, target_folder.joinpath(f"{file.parent.name}.html"))

    rmtree(folder.parent)


def move_statics(folder: Path, target_folder: Path):
    """For the define folder, loop on each files and move them to the target folder."""

    for file in folder.glob("*"):
        if target_folder.joinpath(file.name).is_dir():
            rmtree(target_folder.joinpath(file.name))
        move(file, target_folder.joinpath(file.name))


def build():
    """All steps to build the front end and set it to the flask app"""
    reset()
    create_base_dirs()
    # Only install packages if not already installed
    if not current_directory.joinpath("node_modules").exists():
        run_command(["/usr/bin/npm", "install"])
    run_command(["/usr/bin/npm", "run", "build-dashboard"])
    set_dashboard()
    # run_command(["/usr/bin/npm", "run", "build-dashboard"])
    # run_command(["/usr/bin/npm", "run", "build-setup"])
    # set_setup()


build()
