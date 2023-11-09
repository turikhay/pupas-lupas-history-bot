class Memery():
    def is_posted_already(self, id: int) -> bool:
        raise NotImplementedError()
    
    def store(self, id: int) -> None:
        raise NotImplementedError()
    
    def get_all(self) -> set[int]:
        raise NotImplementedError()

