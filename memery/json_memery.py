import json
import logging
import os
from .memery import Memery

class JsonMemery(Memery):
    def __init__(self, path: str):
        self.path = path

    def is_posted_already(self, id: int) -> bool:
        content = set(self.__read())
        return id in content
    
    def store(self, id: int) -> None:
        content = set(self.__read())
        content.add(id)
        self.__write(list(content))
    
    def get_all(self) -> set[int]:
        return set(self.__read())

    def __read(self) -> list[int]:
        try:
            with open(self.path, "r") as f:
                return json.loads(f.read())
        except FileNotFoundError:
            logging.warning(f"Memery file {self.path} doesn't exist, starting from scratch")
            return []

    def __write(self, content: list[int]) -> None:
        # Write to a temp file and swap it in, so a crash can't leave broken JSON behind
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w") as f:
            f.write(json.dumps(sorted(content)))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.path)
