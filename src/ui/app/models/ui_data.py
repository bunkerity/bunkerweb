from json import dumps, loads
from multiprocessing import Lock
from pathlib import Path


class UIData(dict):
    def __init__(self, file_path: Path):
        super().__init__()
        self.file_path = file_path
        self.__lock = Lock()
        self.__file_signature = None
        self.load_from_file()

    def write_to_file(self):
        with self.__lock:
            self.file_path.write_text(dumps(self))
            file_stat = self.file_path.stat()
            self.__file_signature = (file_stat.st_mtime_ns, file_stat.st_size)

    def load_from_file(self):
        if self.file_path.is_file():
            with self.__lock:
                file_stat = self.file_path.stat()
                file_signature = (file_stat.st_mtime_ns, file_stat.st_size)
                if self.__file_signature == file_signature:
                    return
                data = self.file_path.read_text()
                if data:
                    for key, value in loads(data).items():
                        super().__setitem__(key, value)
                self.__file_signature = file_signature

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.write_to_file()

    def __delitem__(self, key):
        super().__delitem__(key)
        self.write_to_file()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self.write_to_file()
