# I want to run process
from subprocess import Popen, PIPE
import os
import shutil
import re
import asyncio

# get current directory
current_directory = os.path.dirname(os.path.realpath(__file__))
# needed dirs
opt_dir_templates = f"{current_directory}/output/templates"
opt_dir_dashboard = f"{current_directory}/opt-dashboard"
opt_dir_dashboard_pages = f"{current_directory}/opt-dashboard/dashboard/pages"
opt_dir_setup = f"{current_directory}/opt-setup"
opt_dir_setup_page = f"{current_directory}/opt-setup/setup"
ui_dir_static = f"{current_directory}/../static"
ui_dir_templates = f"{current_directory}/../templates"

statics = ("assets", "css", "flags", "img", "js")


def reset():
    """Remove previous directories if exists"""
    asyncio.run(remove_dir(opt_dir_dashboard))
    asyncio.run(remove_dir(opt_dir_setup))


def set_dashboard():
    """Utils to run needed steps to set the dashboard pages (move statics, update and rename templates)"""
    move_template(opt_dir_dashboard_pages, ui_dir_templates)
    move_statics(opt_dir_dashboard, ui_dir_static)


def set_setup():
    """Utils to run needed steps to set the setup page (all-in-one html page)"""
    move_template(opt_dir_setup_page, ui_dir_templates)


def run_command(command, need_wait=False):
    """Utils to run a subprocess command. This is usefull to run npm commands to build vite project"""
    process = Popen(command, stdout=PIPE, stderr=PIPE, cwd=current_directory, shell=True)
    if need_wait:
        process.wait()

    out, err = process.communicate()
    if err:
        print(err)


async def remove_dir(directory):
    """Utils function to remove a directory if exists"""
    if os.path.exists(directory):
        shutil.rmtree(directory)


async def create_dir(directory):
    """Utils function to create a directory if not exists"""
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def create_base_dirs():
    """Create the base directories we will need to build front end and add them to flask app"""
    asyncio.run(create_dir(opt_dir_dashboard))


def move_template(folder, target_folder):
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

    async def move_template_file(root, file, target_folder, base_html):
        """Move the template file to the target folder. This will replace relative path on file to absolute path to work with flask static"""
        file_path = os.path.join(root, file)

        def format_template(m):
            replace = m.group(0).replace('href="/', 'href="').replace('src="/', 'src="')
            if ".js" in replace:
                replace = ' nonce="{{ script_nonce }}" ' + replace
            return replace

        # get file content
        content = ""
        with open(file_path, "r") as f:
            content = f.read()
            content = re.sub(r'(href|src)="\/(css|js|img|favicon|assets|js)\/[^<]*?(?=<|\/>)', format_template, content)
            # get the content before <body>
            content = content[: content.index("<body>")] + base_html
            # write the new content

        with open(file_path, "w") as f:
            f.write(content)

        # remove previous file if exists
        if os.path.exists(f"{target_folder}/{os.path.basename(root)}.html"):
            os.remove(f"{target_folder}/{os.path.basename(root)}.html")

        shutil.copy(file_path, f"{target_folder}/{os.path.basename(root)}.html")

    # I want to run this asynchronusly
    # I want to get all subfollder of a folder
    for root, dirs, files in os.walk(folder):
        for file in files:
            asyncio.run(move_template_file(root, file, target_folder, base_html))


def move_statics(folder, target_folder):
    """For the define folder, loop on each files and move them to the target folder."""

    async def move_static_file(root, dir, target_folder):
        """Move the static file to the target folder."""
        dir = os.path.join(root, dir)

        # remove previous folder if exists
        if os.path.exists(f"{target_folder}/{os.path.basename(dir)}"):
            shutil.rmtree(f"{target_folder}/{os.path.basename(dir)}")
        # rename index.html by the name of the folder
        shutil.move(dir, f"{target_folder}/{os.path.basename(dir)}")

    # I want to get all subfollder of a folder
    for root, dirs, files in os.walk(folder):
        for dir in dirs:
            if dir not in statics:
                continue
            asyncio.run(move_static_file(root, dir, target_folder))


def build():
    """All steps to build the front end and set it to the flask app"""
    reset()
    create_base_dirs()
    # Only install packages if not already installed
    if not os.path.exists(f"{current_directory}/node_modules"):
        run_command(["npm", "install"], True)
    run_command(["npm", "run", "build-dashboard"], True)
    set_dashboard()
    # run_command(["npm", "run", "build-dashboard"])
    # run_command(["npm", "run", "build-setup"], True)
    # set_setup()


build()
