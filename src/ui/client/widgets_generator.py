from os import cpu_count
from os.path import abspath
from pathlib import Path
from threading import Semaphore, Thread
from traceback import format_exc
from typing import List
from shutil import rmtree
from re import search, sub
from typing import Union
from time import sleep
from utils import run_command

# We want to get path of the folder where our components are
# The path is "../src/client/dashboard/src/components" from here

inputFolder = abspath("../client/dashboard/components")
outputFolderMd = abspath("../client/.widgets-md")
outputFolderPy = abspath("../client/.widgets")
outputFolderWidgets = abspath("../client/builder/utils")
components_path_to_exclude = ("components/Icons", "components/Forms/Error", "components/Dashboard", "components/Builder")


def install_npm_packages():
    """Install all packages needed to run the script"""
    # Install documentation package
    if run_command(["/usr/bin/npm", "install", "-g", "documentation"]):
        if run_command(["npm", "install", "-g", "documentation"]):
            exit(1)


def reset():
    """Reset the docs folder"""
    # delete the output folder even if not empty
    rmtree(outputFolderMd, ignore_errors=True)
    # Remove all files from the output folder
    rmtree(outputFolderPy, ignore_errors=True)


def vue2js():
    """Get the script part of a Vue file and create a JS file"""
    # Create outputFolder if not exists
    Path(outputFolderMd).mkdir(parents=True, exist_ok=True)
    # Get every subfolders from the input folder
    for folder in Path(inputFolder).rglob("*"):
        # Get only vue file
        if not folder.is_file() or folder.suffix != ".vue":
            continue

        # Exclude some files
        if any(folder_path in folder.as_posix() for folder_path in components_path_to_exclude):
            continue

        # Read the file content
        data = folder.read_text()
        # Get only the content between <script setup> and </script> tag
        script = data.split("<script setup>")[1].split("</script>")[0]
        # Get index of jsdoc comments
        first_doc_index_start = script.find("/**")
        first_doc_index_end = script.find("*/")
        if first_doc_index_start != -1 and first_doc_index_end != -1:
            # get content before first_doc_index_end
            script = script[first_doc_index_start : first_doc_index_end + 2]

        # Create a file on the output folder with the same name but with .js extension
        fileName = folder.name.replace(".vue", ".js")
        dest = Path(outputFolderMd) / fileName
        dest.write_text(script)


def js2md():
    """Run a command to render markdown from JS files"""
    semaphore = Semaphore(cpu_count())

    def convert_json_to_md(file: Path):
        semaphore.acquire()
        # Run the command
        output = run_command(["documentation", "build", file.as_posix(), "-f", "md"], with_output=True)
        if output == 1:
            print("Error while running command", flush=True)
            exit(1)

        # Create a new file with the same name but with .md extension
        file.with_suffix(".md").write_text(output)
        semaphore.release()

    threads = []
    # Create a markdown file for each JS file
    for file in Path(outputFolderMd).rglob("*"):
        threads.append(Thread(target=convert_json_to_md, args=(file,)))

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Remove js files after
    # rmtree(outputFolderMd, ignore_errors=True)


def formatMd():
    """Format each markdown file to remove useless data and format some data like params"""
    # Create order using the tag title path of each file
    order = []
    for file in Path(outputFolderMd).rglob("*"):
        try:
            # Get the title from first line
            data = file.read_text()
            # Remove everything after a [1]: tag
            data = data.split("[1]:")[0]
            # Remove ### Table of contents
            data = data.replace("### Table of Contents", "")
            # Remove everything before the first ## tag
            if "## " in data:
                index = data.index("## ")
                data = data[index:]

            # I want to loop on each line
            lines = data.split("\n")
            line_result = []
            for line in lines:
                # remove space (so &#x20 or &#32)
                line = line.replace("&#x20", "").replace("&#32", "")

                if line.startswith("#") and ".vue" in line and "\\.vue" in line:
                    line = line.replace("\\.vue", ".vue")

                # Escape the \ character
                line = line.replace("\\", "\\\\")

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
        except BaseException:
            print(format_exc(), flush=True)
            print("Error while parsing file", str(file.name), flush=True)
            exit(1)


def md2py():
    # create py folder if not exists
    Path(outputFolderPy).mkdir(parents=True, exist_ok=True)
    # Get all files from the output folder
    # Create order using the tag title path of each file
    for file in Path(outputFolderMd).rglob("*"):
        data = file.read_text()
        # Get the title from first line, after the ## tag
        try:
            title = get_py_title(data)
            desc = get_py_desc(data)
            params = get_py_params(data)
            # Case not params, we don't need to generate the widget
            if not params:
                continue
            params = convert_params(params)
            widget = create_widget(title, desc, params)
            Path(f"{outputFolderPy}/{title.capitalize()}.py").write_text(widget)

        except BaseException:
            print(format_exc(), flush=True)
            print("Error while parsing file", str(file.name), flush=True)
            exit(1)

    # Remove widgets-md
    rmtree(outputFolderMd, ignore_errors=True)


def get_py_title(data: str) -> str:
    title = data.split("\n")[0].replace("## ", "")
    # Case there is "/", split and get the last one
    if "/" in title:
        title = title.split("/")[-1]
    # remove the extension
    title = title.replace(".vue", "")
    return title


def get_py_desc(data: str) -> str:
    # remove first line
    desc = "\n".join(data.split("\n")[1:])
    # Get line where Parameters string is with at least one # tag before
    lines = desc.split("\n")
    new_lines = []
    for line in lines:
        if "# Parameters" in line:
            new_lines.append("PARAMETERS")
            continue

        if "# Examples" in line:
            new_lines.append("EXAMPLE")
            continue

        new_lines.append(line)

    # merge
    desc = "\n".join(new_lines)
    # remove ```javascript and ``` from the string
    desc = sub(r"```javascript\n", "", desc)
    desc = sub(r"```\n", "", desc)
    return desc


def get_py_params(data: str) -> Union[str, bool]:
    try:
        # params will be between ### Parameters and ### Examples
        if not "### Parameters" in data:
            return False
        params = data.split("### Parameters")[1].split("### Examples")[0]
        list_params = []
        lines = params.split("\n")
        for line in lines:
            if not line.startswith("-"):
                continue
            # Get first and second ` index
            first = line.find("`")
            second = line.find("`", first + 1)
            param_name = line[first + 1 : second] or None
            # Get first and second ** index
            first = line.find("**")
            second = line.find("**", first + 1)
            param_type = line[first + 2 : second] or None

            # Check if (optional is in line
            default = None
            if "(optional, default" in line:
                first = line.find("(optional, default")
                # get substring starting from the first index
                opt_sub = line[first + len("(optional, default") :]
                # get the first ` index
                first = opt_sub.find("`")
                # get the second ` index
                default = opt_sub[first + 1 : opt_sub.find("`", first + 1)]

            list_params.append({"name": param_name, "type": param_type, "default": default})

        # remove default key if None
        return list_params
    except BaseException:
        print(format_exc(), flush=True)
        print("Error while parsing params", flush=True)


def convert_params(params: List[dict]) -> List[dict]:
    convert_types = {
        "string": "str",
        "number": "int",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
    }

    convert_values = {
        "false": "False",
        "true": "True",
        "null": "None",
        "undefined": "None",
        "uuidv4()": "",
        "uuidv4": "",
        "contentindex": "",
        "contentIndex": "",
    }
    try:
        convert_params = []
        for param in params:
            if not param.get("name") or not param.get("type"):
                continue

            param_type = param.get("type").lower().strip()

            convert_type = None
            # Case we have only one type
            if param_type and param_type and not "(" in param_type and param_type in convert_types:
                convert_type = convert_types[param_type]

            # Case we have multiple types
            if param_type and param_type and "(" in param_type and "|" in param_type:
                is_union = True
                # We need to remove parenthesis
                param_type = param_type.replace("(", "").replace(")", "")
                # We need to split by |
                param_types = param_type.split("|")
                convert_type = "Union["
                for param_value in param_types:
                    if param_value.strip() in convert_types:
                        convert_type += convert_types[param_value.strip()] + ", "

                # remove last ','
                convert_type = convert_type[:-2]
                convert_type += "]"

            default = param.get("default")
            if default and default in convert_values:
                default = convert_values[default]

            convert_params.append({"name": param.get("name"), "type": convert_type, "default": default})

        # remove None values
        convert_params = [{k: v for k, v in d.items() if v is not None} for d in convert_params]

        # sort to get first params without default or type, then params with type but without default, then others
        convert_params = sorted(convert_params, key=lambda x: x.get("default") is not None)
        convert_params = sorted(convert_params, key=lambda x: x.get("type") is not None)

        return convert_params
    except BaseException:
        print(format_exc(), flush=True)
        print("Error while converting params", flush=True)


def create_widget(title: str, desc: str, params: List[dict]):
    try:
        # format function title from camelCase to snake_case
        f_title = sub(r"([A-Z])", r"_\1", title).lower()
        # Case title start by _, remove it
        if f_title.startswith("_"):
            f_title = f_title[1:]

        # Add indentation to desc
        desc_lines = desc.split("\n")
        desc_indent = []
        for line in desc_lines:
            desc_indent.append(f"    {line}")
        desc = "\n".join(desc_indent)
        desc = '    """' + desc + '"""\n'

        # Create function params with type and optional value if exists
        params_str = ""
        for param in params:
            param_name = param.get("name")
            param_type = param.get("type")
            param_default = '""' if param.get("default") == "" else param.get("default")
            params_str += (
                f"    {param_name}: {param_type} = {param_default},\n"
                if "type" in param and "default" in param
                else (f"    {param_name}: {param_type},\n" if "type" in param else f"    {param_name},\n")
            )

        # remove last ',' in params_str
        params_str = params_str[:-2]

        # By default, we set on data dict the values without default value (means value are needed)
        data = "    data = {\n"
        for param in params:
            if "default" in param:
                continue
            param_name = param.get("name")
            data += f"""        "{param_name}" : {param_name},\n"""
        data += "       }\n"

        # Check to add keys if value is not default value
        add_keys_not_default = ""
        for param in params:
            if not "default" in param:
                continue
            param_name = param.get("name")
            param_default = '""' if param.get("default") == "" else param.get("default")
            add_keys_not_default += f"""("{param_name}", {param_name}, {param_default}),"""

        if add_keys_not_default:
            add_keys_not_default = f"""
    # List of params that will be add only if not default value
    list_params = [{add_keys_not_default.rstrip(',')}]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])
"""

        widget_function = f"""
def {f_title}_widget(
{params_str}
    ):
{desc}
{data}
{add_keys_not_default}
    return {{ "type" : "{title.lower().capitalize()}", "data" : data }}
        """
        return widget_function
    except BaseException:
        print(format_exc(), flush=True)
        print("Error while creating widget", flush=True)


def merge_widgets():
    # Create widgets.py file
    Path(outputFolderWidgets).mkdir(parents=True, exist_ok=True)
    # Create widgets.py
    Path(f"{outputFolderWidgets}/widgets.py").write_text("")

    content = """
from typing import Union

# Add params to data dict only if value is not the default one
def add_key_value(data, key, value, default):
    if value == default:
        return
    data[key] = value
        """
    # get all files from the output folder
    for file in Path(outputFolderPy).rglob("*.py"):
        data = file.read_text()
        content += data
        content += "\n"
    # Utils function to add key value to data dict if not default value

    # Remove previous file if exists
    if Path(f"{outputFolderWidgets}/widgets.py").exists():
        Path(f"{outputFolderWidgets}/widgets.py").unlink()

    Path(f"{outputFolderWidgets}/widgets.py").write_text(content)


install_npm_packages()
reset()
vue2js()
js2md()
formatMd()
md2py()
merge_widgets()
# reset()
