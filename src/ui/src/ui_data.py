from json import dumps, loads
from multiprocessing import Lock
from pathlib import Path


class UIData(dict):
    def __init__(self, file_path: Path):
        super().__init__()
        self.file_path = file_path
        self.__lock = Lock()
        self.load_from_file()

    def _write_to_file(self):
        with self.__lock:
            self.file_path.write_text(dumps(self))

    def load_from_file(self):
        if self.file_path.is_file():
            with self.__lock:
                for key, value in loads(self.file_path.read_text()).items():
                    super().__setitem__(key, value)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._write_to_file()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._write_to_file()
