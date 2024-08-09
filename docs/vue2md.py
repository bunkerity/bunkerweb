from os.path import abspath
from pathlib import Path
from subprocess import Popen, PIPE
from typing import List
from shutil import rmtree
from re import search

outputFilename = "ui-components.md"
# We want to get path of the folder where our components are
# The path is "../src/client/dashboard/src/components" from here

inputFolder = abspath("../src/ui/client/dashboard/components")
outputFolder = abspath("../docs/components")
outputFile = abspath("../docs")


def run_command(command: List[str]) -> int:
    """Utils to run a subprocess command. This is useful to run npm commands to build vite project"""
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
    # remove outputfilename
    output_file_path = Path(outputFile) / outputFilename
    output_file_path.unlink(missing_ok=True)


def vue2js():
    """Get the script part of a Vue file and create a JS file"""
    # Create outputFolder if not exists
    Path(outputFolder).mkdir(parents=True, exist_ok=True)
    # Get every subfolders from the input folder
    print(Path(inputFolder).rglob("*"))
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


def formatMd():
    """Format each markdown file to remove useless data and format some data like params"""
    # Get all files from the output folder
    files = list(Path(outputFolder).rglob("*"))

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

        # I want to loop on each line
        lines = data.split("\n")
        line_result = []
        for line in lines:
            # remove space (so &#x20 or &#32)
            line = line.replace("&#x20", "").replace("&#32", "")

            if line.startswith("#") and ".vue" in line and "\.vue" in line:
                line = line.replace("\.vue", ".vue")

            # Case not a param, keep the line as is
            if not line.startswith("*"):
                line_result.append(line)
                continue

            # get line without first char
            line = "-" + line[1:]

            # remove each **[string][num]** pattern in a param by **string**
            reg = r"\[\w+\]\[\d+\]"
            while search(reg, line):
                # get data of the pattern
                pattern = search(reg, line).group()
                # get content of first bracket
                content = pattern.split("][")[0].replace("[", "")
                line = line.replace(pattern, f"{content}")

            line_result.append(line)

        # I can merge the lines
        data = "\n".join(line_result)
        # update the file with the new content
        file.write_text(data)


def mergeMd():
    """Merge all markdown files into one"""
    # Get all files from the output folder
    files = list(Path(outputFolder).rglob("*"))
    # Create order using the tag title path of each file
    order = []
    for file in files:
        # Get the title from first line
        data = file.read_text()
        filePath = data.split("\n")[0].replace("## ", "")
        order.append({"path": filePath, "fileName": str(file.name)})

    # Sort by path
    order.sort(key=lambda x: x["path"])

    # Create the md file to merge
    merge = Path(outputFile) / outputFilename
    merge.write_text("")
    # Append each file in order and keep indentation
    for info in order:
        file_path = Path(outputFolder) / info["fileName"]
        data = file_path.read_text()
        merge.write_text(merge.read_text() + data)

    # Remove all files
    rmtree(outputFolder, ignore_errors=True)


def formatMergeMd():
    """ATM didn't convert the js function to python.
    So I will run a command to format the file"""

    command = "node ./vue2md.js"
    run_command(command)


install_npm_packages()
reset()
vue2js()
js2md()
formatMd()
mergeMd()
formatMergeMd()
