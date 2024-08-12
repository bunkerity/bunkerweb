from pathlib import Path
import json
import base64


def save_builder(page_name: str, output: str, store_json: bool = True, update_page: bool = True):
    if store_json:
        with open(f"test_{page_name.lower()}.json", "w") as f:
            json.dump(output, f, indent=4)

    data = base64.b64encode(bytes(json.dumps(output), "utf-8"))
    data = data.decode("ascii")
    # get current directory
    current_directory = Path.cwd()
    # needed dirs
    opt_dir_templates = current_directory.parent.joinpath("dashboard", "pages", page_name)
    new_content = f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/x-icon" href="/img/favicon.ico" />
    <link rel="stylesheet" href="/css/style.css" />
    <link rel="stylesheet" href="/css/flag-icons.min.css" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>BunkerWeb | {page_name.lower().capitalize()}</title>
  </head>
  <body>
    <div
      class="hidden"
      data-server-global='{{"username" : "admin", "plugins_page": [{{"id" : "antibot", "name": "Antibot"}}, {{"id": "backup", "name" : "backup"}} ]}}'
    ></div>
    <div
      class="hidden"
      data-server-flash='[{{"type" : "success", "title" : "title", "message" : "Success feedback"}}, {{"type" : "error", "title" : "title", "message" : "Error feedback"}}, {{"type" : "warning", "title" : "title", "message" : "Warning feedback"}}, {{"type" : "info", "title" : "title", "message" : "Info feedback"}}]'
    ></div>
    <div
      class="hidden"
      data-server-builder='{data}'
    ></div>
    <div id="app"></div>
    <script type="module" src="{page_name.lower()}.js"></script>
  </body>
</html>
"""
    for file in opt_dir_templates.glob("index.html"):
        file.write_text(new_content)
