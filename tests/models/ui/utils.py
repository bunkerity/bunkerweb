from os import listdir
from os.path import basename, splitext


# Get Python files in the current directory (excluding __init__.py and this script itself)
def get_python_files(_dir: str) -> tuple[str, ...]:
    return tuple(
        splitext(f)[0]
        for f in listdir(_dir)
        if f.endswith(".py") and f != "__init__.py" and f != basename(__file__)  # Remove .py extension  # List current dir
    )
