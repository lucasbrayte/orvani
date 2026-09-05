from pathlib import Path
from types import SimpleNamespace

import libreoffice_sync.main as main


def test_cli_exposes_expected_commands():
    parser = main.build_parser()
    for command in ("health", "run", "init-workbook"):
        args = parser.parse_args([command])
        assert args.command == command


def test_wait_for_uno_retries_until_catalog_instance_exists():
    assert hasattr(main, "_wait_for_uno")

    expected = object()
    attempts = []
    sleeps = []

    def connector(*, host, port):
        attempts.append((host, port))
        if len(attempts) == 1:
            raise RuntimeError("UNO indisponível")
        return expected

    settings = SimpleNamespace(
        uno_host="127.0.0.1",
        uno_port=2002,
    )

    result = main._wait_for_uno(
        settings,
        connector=connector,
        sleeper=sleeps.append,
    )

    assert result is expected
    assert attempts == [
        ("127.0.0.1", 2002),
        ("127.0.0.1", 2002),
    ]
    assert sleeps == [2]


def test_wait_for_workbook_retries_exact_expected_path():
    assert hasattr(main, "_wait_for_workbook")

    attempts = []
    sleeps = []

    class Workbook:
        def attach_expected_document(self, path):
            attempts.append(path)
            return len(attempts) == 3

    path = Path("/home/lucas/Documents/Orvani.ods")

    main._wait_for_workbook(
        Workbook(),
        path,
        sleeper=sleeps.append,
    )

    assert attempts == [path, path, path]
    assert sleeps == [2, 2]
