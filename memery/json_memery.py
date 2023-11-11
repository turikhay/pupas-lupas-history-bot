import json
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
        with open(self.path, "r") as f:
            return json.loads(f.read())
        
    def __write(self, content: list[int]) -> None:
        with open(self.path, "w") as f:
            f.write(json.dumps(content))
