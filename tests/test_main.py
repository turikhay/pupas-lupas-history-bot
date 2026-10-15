import pytest

from tests.factories import group, post
from throwback.__main__ import EXIT_NOTHING_TO_POST, EXIT_POSTED, exit_code, parse_args


def test_exit_codes() -> None:
    assert exit_code(group(post(1))) == EXIT_POSTED == 0
    assert exit_code(None) == EXIT_NOTHING_TO_POST == 3


def test_dry_run_flag() -> None:
    assert parse_args([]).dry_run is False
    assert parse_args(["--dry-run"]).dry_run is True


def test_unknown_arguments_exit_with_2() -> None:
    with pytest.raises(SystemExit) as exited:
        parse_args(["--post-everything"])
    assert exited.value.code == 2
