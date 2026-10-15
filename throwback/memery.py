import json
import logging
import os
from typing import Protocol


class Memery(Protocol):
    """Remembers what has been reposted: group keys and the messages those groups replied to."""

    def is_posted_already(self, id: int) -> bool: ...

    def store(self, id: int) -> None: ...


class JsonMemery:
    def __init__(self, path: str):
        self.path = path

    def is_posted_already(self, id: int) -> bool:
        return id in self.__read()

    def store(self, id: int) -> None:
        content = self.__read()
        content.add(id)
        self.__write(content)

    def __read(self) -> set[int]:
        try:
            with open(self.path) as f:
                return set(json.loads(f.read()))
        except FileNotFoundError:
            logging.warning(f"Memery file {self.path} doesn't exist, starting from scratch")
            return set()

    def __write(self, content: set[int]) -> None:
        # Write to a temp file and swap it in, so a crash can't leave broken JSON behind
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w") as f:
            f.write(json.dumps(sorted(content)))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.path)
