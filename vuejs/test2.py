import json
import copy

css = ""


    
# add "z-2" to "z-50" on zIndex list
for i in range(0, 51):
    css += f".-z-{i} {{ @apply -z-[{i}] }}\n"


for i in range(0, 81):
    css += f".z-{i} {{ @apply z-[{i}] }}\n"

print(css)