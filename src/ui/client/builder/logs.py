import json
import base64

from builder.logs import logs_builder

files = ["file1", "file2"]
current_file = ""
raw_data = "gefesfesfsefes"
output = logs_builder(files, current_file, raw_data)

with open("logs.json", "w") as f:
    json.dump(output, f, indent=4)

output_base64_bytes = base64.b64encode(bytes(json.dumps(output), "utf-8"))
output_base64_string = output_base64_bytes.decode("ascii")
with open("logs.txt", "w") as f:
    f.write(output_base64_string)
