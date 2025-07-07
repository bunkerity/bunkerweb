from json import dumps, loads
from multiprocessing import Lock
from pathlib import Path
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for ui_data module")


class UIData(dict):
    # Initialize UIData with file-backed dictionary that auto-persists changes to disk.
    # Creates thread-safe data storage with automatic file synchronization for UI state management.
    def __init__(self, file_path: Path):
        if DEBUG_MODE:
            logger.debug(f"UIData.__init__() called with file_path: {file_path}")
        
        super().__init__()
        self.file_path = file_path
        self.__lock = Lock()
        
        if DEBUG_MODE:
            logger.debug(f"Initialized UIData with lock and file path: {file_path}")
        
        self.load_from_file()

    # Write current dictionary data to file with thread-safe locking.
    # Serializes data to JSON format and ensures atomic file operations for data persistence.
    def write_to_file(self):
        if DEBUG_MODE:
            logger.debug(f"write_to_file() called - writing {len(self)} items to {self.file_path}")
        
        try:
            with self.__lock:
                self.file_path.write_text(dumps(self))
                if DEBUG_MODE:
                    logger.debug(f"Successfully wrote data to file: {self.file_path}")
        except Exception as e:
            logger.exception(f"Failed to write data to file {self.file_path}")

    # Load dictionary data from file if it exists with error handling.
    # Reads JSON data from disk and populates the dictionary while preserving existing data structure.
    def load_from_file(self):
        if DEBUG_MODE:
            logger.debug(f"load_from_file() called - checking if {self.file_path} exists")
        
        if self.file_path.is_file():
            try:
                with self.__lock:
                    data = self.file_path.read_text()
                    if data:
                        loaded_data = loads(data)
                        for key, value in loaded_data.items():
                            super().__setitem__(key, value)
                        
                        if DEBUG_MODE:
                            logger.debug(f"Successfully loaded {len(loaded_data)} items from file: {self.file_path}")
                    else:
                        if DEBUG_MODE:
                            logger.debug(f"File {self.file_path} is empty, no data to load")
            except Exception as e:
                logger.exception(f"Failed to load data from file {self.file_path}")
        else:
            if DEBUG_MODE:
                logger.debug(f"File {self.file_path} does not exist, starting with empty data")

    # Set dictionary item and automatically persist changes to disk.
    # Overrides dict.__setitem__ to trigger file synchronization on every update.
    def __setitem__(self, key, value):
        if DEBUG_MODE:
            logger.debug(f"__setitem__() called - setting key: {key}")
        
        super().__setitem__(key, value)
        self.write_to_file()

    # Delete dictionary item and automatically persist changes to disk.
    # Overrides dict.__delitem__ to trigger file synchronization after deletion.
    def __delitem__(self, key):
        if DEBUG_MODE:
            logger.debug(f"__delitem__() called - deleting key: {key}")
        
        super().__delitem__(key)
        self.write_to_file()

    # Update dictionary with multiple items and persist all changes to disk.
    # Overrides dict.update to trigger single file write operation after bulk updates.
    def update(self, *args, **kwargs):
        if DEBUG_MODE:
            update_count = len(kwargs) if kwargs else (len(args[0]) if args and hasattr(args[0], '__len__') else 0)
            logger.debug(f"update() called - updating approximately {update_count} items")
        
        super().update(*args, **kwargs)
        self.write_to_file()

    # Safely update nested dictionary entries and persist to disk.
    # Navigates through key path, creates missing intermediate dictionaries, and ensures atomic updates.
    def set_nested(self, keys, value):
        if DEBUG_MODE:
            logger.debug(f"set_nested() called with keys: {keys}, value type: {type(value).__name__}")
        
        if not keys:
            if DEBUG_MODE:
                logger.debug("set_nested() called with empty keys list, returning early")
            return

        try:
            # Navigate to the parent dictionary
            target = self
            for key in keys[:-1]:
                if key not in target:
                    target[key] = {}
                    if DEBUG_MODE:
                        logger.debug(f"Created intermediate dictionary for key: {key}")
                target = target[key]

            # Set the value in the final level
            target[keys[-1]] = value
            
            if DEBUG_MODE:
                logger.debug(f"Successfully set nested value at path: {' -> '.join(map(str, keys))}")

            # Ensure changes are written to disk
            self.write_to_file()
        except Exception as e:
            logger.exception(f"Failed to set nested value at keys: {keys}")
