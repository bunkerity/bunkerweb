from json import dumps, loads
from multiprocessing import Lock
from os import sep
from os.path import join
from pathlib import Path
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-ui-data",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-ui-data")


class UIData(dict):
    def __init__(self, file_path: Path):
        super().__init__()
        self.file_path = file_path
        self.__lock = Lock()
        self.load_from_file()

    def write_to_file(self):
        with self.__lock:
            self.file_path.write_text(dumps(self))

    def load_from_file(self):
        if self.file_path.is_file():
            with self.__lock:
                data = self.file_path.read_text()
                if data:
                    for key, value in loads(data).items():
                        super().__setitem__(key, value)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.write_to_file()

    def __delitem__(self, key):
        super().__delitem__(key)
        self.write_to_file()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self.write_to_file()

    def set_nested(self, keys, value):
        """
        Safely update nested dictionary entries and persist to disk.

        Args:
            keys (list): List of keys forming the path to the value
            value: Value to set at the specified path
        """
        if not keys:
            return

        # Navigate to the parent dictionary
        target = self
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]

        # Set the value in the final level
        target[keys[-1]] = value

        # Ensure changes are written to disk
        self.write_to_file()
