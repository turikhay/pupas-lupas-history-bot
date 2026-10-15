import json
from pathlib import Path

from throwback.memery import JsonMemery


def test_starts_empty_without_a_file(tmp_path: Path) -> None:
    memery = JsonMemery(str(tmp_path / "memery.json"))
    assert not memery.is_posted_already(5)
    assert not (tmp_path / "memery.json").exists()


def test_store_writes_sorted_ids_without_leftovers(tmp_path: Path) -> None:
    path = tmp_path / "memery.json"
    memery = JsonMemery(str(path))
    for id in (7_000_000_000_000_000_001, 5, 5):
        memery.store(id)
    assert memery.is_posted_already(5)
    assert json.loads(path.read_text()) == [5, 7_000_000_000_000_000_001]
    assert [p.name for p in tmp_path.iterdir()] == ["memery.json"]


def test_reads_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "memery.json"
    path.write_text("[3, 1, 2]")
    memery = JsonMemery(str(path))
    assert all(memery.is_posted_already(id) for id in (1, 2, 3))
