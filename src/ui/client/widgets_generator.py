from os.path import abspath
from pathlib import Path
from subprocess import Popen, PIPE
from typing import List
from shutil import rmtree


# We want to get path of the folder where our components are
# The path is "../src/client/dashboard/src/components" from here

inputFolder = abspath("../client/dashboard/components")
outputFolder = abspath("../client/.widgets")


def run_command(command: List[str]) -> int:
    """Utils to run a subprocess command. This is usefull to run npm commands to build vite project"""
    print(f"Running command: {command}", flush=True)
    try:
        process = Popen(command, stdout=PIPE, stderr=PIPE, shell=True, text=True)
        while process.poll() is None:
            if process.stdout is not None:
                for line in process.stdout:
                    print(line.strip(), flush=True)

        if process.returncode != 0:
            print("Error while running command", flush=True)
            print(process.stdout.read(), flush=True)
            print(process.stderr.read(), flush=True)
            return 1
    except BaseException as e:
        print(f"Error while running command: {e}", flush=True)
        return 1

    print("Command executed successfully", flush=True)
    return 0


def install_npm_packages():
    """Install all packages needed to run the script"""
    # Install documentation package
    run_command("npm install -g documentation")


def reset():
    """Reset the docs folder"""
    # delete the output folder even if not empty
    rmtree(outputFolder, ignore_errors=True)


def vue2js():
    """Get the script part of a Vue file and create a JS file"""
    # Create outputFolder if not exists
    Path(outputFolder).mkdir(parents=True, exist_ok=True)
    # Get every subfolders from the input folder
    for folder in Path(inputFolder).rglob("*"):
        # Get only files
        if folder.is_file() and folder.suffix == ".vue":
            # Read the file content
            data = folder.read_text()
            # Get only the content between <script setup> and </script> tag
            script = data.split("<script setup>")[1].split("</script>")[0]
            # Create a file on the output folder with the same name but with .js extension
            fileName = folder.name.replace(".vue", ".js")
            dest = Path(outputFolder) / fileName
            dest.write_text(script)


def js2md():
    """Run a command to render markdown from JS files"""
    # Get all files from the output folder
    files = list(Path(outputFolder).rglob("*"))
    process_list = []
    # Create a markdown file for each JS file
    for file in files:
        # Run a process `documentation build <filename> -f md > <filename>.md
        command = f"documentation build {file} -f md > {file.with_suffix('.md')}"
        # Run the command
        # I want to run this command async
        process = Popen(command, stdout=PIPE, stderr=PIPE, shell=True, text=True)
        process_list.append(process)

    # Wait that all processes are done
    for process in process_list:
        process.wait()
    # Remove js files after
    for file in files:
        file.unlink()


def formatMD():
    """Format the markdown by removing useless content"""
    # Get all files from the output folder
    files = list(Path(outputFolder).rglob("*"))
    # Create order using the tag title path of each file
    order = []
    for file in files:
        # Get the title from first line
        data = file.read_text()
        # Remove everything after a [1]: tag
        data = data.split("[1]:")[0]
        # Remove ### Table of contents
        data = data.replace("### Table of Contents", "")
        # Remove everything before the first ## tag
        index = data.index("## ")
        data = data[index:]
        # update the file with the new content
        file.write_text(data)

    for file in files:
        data = file.read_text()
        # Get the title from first line, after the ## tag
        try:
            title = data.split("\n")[0].replace("## ", "")
            # Case there is "/", split and get the last one
            if "/" in title:
                title = title.split("/")[-1]
            # remove the extension
            title = title.replace(".vue", "")

            # subtitle is after first line and before ### Parameters
            subtitle = data.split("\n")[1]

            # params will be between ### Parameters and ### Examples
            params = data.split("### Parameters")[1].split("### Examples")[0]

            # example will be between ### Examples and the next occurence of a # tag
            example = data.split("### Examples")[1].split("#")[0]
            print(title, subtitle, params, example)

            # we need to format the params with format **[type][num]** => **[type]** here AND for documentation (because num is not needed - removed references)
            # We need to update the vue to js by keeping only the first jsdoc comment occurence to avoid issues with documentation.js

            # get each param, type and default value if exists
            # create function that will parse the params with the type and default value if exists
            # function name will be the title
            # the start of the function is """<subtitle> \n <params> \n <example>"""
            # We will create an object with that will be the default component format
        except:
            print("Error while parsing file", str(file.name))
            continue


# install_npm_packages()
reset()
vue2js()
js2md()
formatMD()
