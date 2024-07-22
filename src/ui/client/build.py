# I want to run process
from subprocess import Popen, PIPE
import os
import shutil

# get current directory
current_directory = os.path.dirname(os.path.realpath(__file__))
# needed dirs
opt_dir = f"{current_directory}/output"
opt_dir_templates = f"{current_directory}/output/templates"
opt_dir_dashboard = f"{current_directory}/opt-dashboard"
opt_dir_dashboard_pages = f"{current_directory}/opt-dashboard/dashboard/pages"
opt_dir_setup = f"{current_directory}/opt-setup"
opt_dir_setup_page = f"{current_directory}/opt-setup/setup"
ui_dir_static = f"{current_directory}/../static"
ui_dir_templates = f"{current_directory}/../templates"

statics = ("assets", "css", "flags", "img", "js")


def run_command(command, need_wait=False):
    process = Popen(command, stdout=PIPE, stderr=PIPE, cwd=current_directory, shell=True)
    if need_wait:
        process.wait()

    out, err = process.communicate()
    if err:
        print("Error: ", err)
    print(out)


def remove_dir(directory):
    if os.path.exists(directory):
        shutil.rmtree(directory)


def reset():
    remove_dir(opt_dir)
    remove_dir(opt_dir_dashboard)
    remove_dir(opt_dir_setup)
    os.makedirs(opt_dir, exist_ok=True)
    os.makedirs(opt_dir_templates, exist_ok=True)


def move_template(folder, target_folder):
    # I want to get all subfollder of a folder
    for root, dirs, files in os.walk(folder):
        for file in files:
            file_path = os.path.join(root, file)
            # rename index.html by the name of the folder
            # remove previous file if exists
            if os.path.exists(f"{target_folder}/{os.path.basename(root)}.html"):
                os.remove(f"{target_folder}/{os.path.basename(root)}.html")

            shutil.copy(file_path, f"{target_folder}/{os.path.basename(root)}.html")


def move_statics(folder, target_folder):
    # I want to get all subfollder of a folder
    for root, dirs, files in os.walk(folder):
        for dir in dirs:
            if dir not in statics:
                continue
            dir = os.path.join(root, dir)

            # remove previous folder if exists
            if os.path.exists(f"{target_folder}/{os.path.basename(dir)}"):
                shutil.rmtree(f"{target_folder}/{os.path.basename(dir)}")
            # rename index.html by the name of the folder
            shutil.move(dir, f"{target_folder}/{os.path.basename(dir)}")


def move_opt_to_ui():
    move_statics(opt_dir_dashboard)


def build():
    reset()
    run_command(["npm", "install"], True)
    run_command(["npm", "run", "build-dashboard"])
    run_command(["npm", "run", "build-setup"], True)
    # format dashboard files
    move_template(opt_dir_dashboard_pages, ui_dir_templates)
    move_statics(opt_dir_dashboard, ui_dir_static)
    # format setup files
    move_template(opt_dir_setup_page, ui_dir_templates)
    # now move output files to the ui


build()
