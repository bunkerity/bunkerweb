#!/usr/bin/env python3
"""Pre-commit hook: refuse a plugin.json whose setting `help` exceeds 512 characters.

`Configurator.__validate_plugin` (src/common/gen/Configurator.py) rejects any setting
whose `help` is longer than 512 characters, and a rejected plugin.json is skipped
entirely -- the whole plugin silently disappears at the next start, not just the
offending setting. This catches the mistake at commit time instead of at runtime.
"""

from json import JSONDecodeError, loads
from pathlib import Path
from sys import argv, exit as sys_exit

MAX_HELP_LENGTH = 512


def check_file(path: Path) -> list[str]:
    try:
        data = loads(path.read_text(encoding="utf-8"))
    except (OSError, JSONDecodeError) as exc:
        return [f"{path}: could not parse as JSON ({exc})"]

    plugin_id = data.get("id", path.parent.name)
    errors = []
    for setting, setting_data in (data.get("settings") or {}).items():
        help_text = setting_data.get("help", "")
        length = len(help_text)
        if length > MAX_HELP_LENGTH:
            errors.append(f"{path}: setting {setting} in plugin {plugin_id} has a {length}-character help (max {MAX_HELP_LENGTH})")
    return errors


def main() -> int:
    errors = []
    for filename in argv[1:]:
        errors.extend(check_file(Path(filename)))

    if errors:
        print("Plugin help text exceeds the 512-character cap enforced by Configurator.__validate_plugin:")
        for error in errors:
            print(f"  {error}")
        print("A setting over the cap makes the whole plugin fail validation and disappear silently at the next start.")
        return 1
    return 0


if __name__ == "__main__":
    sys_exit(main())
