from os import getenv
from pathlib import Path
from subprocess import PIPE, Popen
from typing import List, Optional


def run_command(command: List[str], current_directory: Optional[Path] = None, *, with_output: bool = False) -> int:
    """Utils to run a subprocess command. This is usefull to run npm commands to build vite project"""
    print(f"Running command: {command}", flush=True)
    try:
        process = Popen(
            command, stdout=PIPE, stderr=PIPE, cwd=current_directory.as_posix() if current_directory else None, shell=not bool(getenv("DOCKERFILE", ""))
        )
        while process.poll() is None:
            if not with_output and process.stdout is not None:
                for line in process.stdout:
                    print(line.decode("utf-8").strip(), flush=True)

        if process.returncode != 0:
            print("Error while running command", flush=True)
            print(process.stdout.read().decode("utf-8"), flush=True)
            print(process.stderr.read().decode("utf-8"), flush=True)
            return 1
    except BaseException as e:
        print(f"Error while running command: {e}", flush=True)
        return 1

    print("Command executed successfully", flush=True)
    if with_output:
        return process.stdout.read().decode("utf-8")
    return 0
