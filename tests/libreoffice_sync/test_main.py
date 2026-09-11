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


def test_wait_for_document_ready_retries_transient_uno_runtime_exception():
    assert hasattr(main, "_wait_for_document_ready")

    class RuntimeException(Exception):
        pass

    attempts = []
    sleeps = []
    workbook = SimpleNamespace(document=object())

    def initializer(document):
        assert document is workbook.document
        attempts.append(document)
        if len(attempts) < 3:
            raise RuntimeException("documento ainda não pronto")

    main._wait_for_document_ready(
        workbook,
        initializer=initializer,
        sleeper=sleeps.append,
    )

    assert len(attempts) == 3
    assert sleeps == [0.5, 0.5]


def test_wait_for_document_ready_does_not_hide_programming_errors():
    workbook = SimpleNamespace(document=object())

    def initializer(_document):
        raise ValueError("erro real")

    try:
        main._wait_for_document_ready(
            workbook,
            initializer=initializer,
            sleeper=lambda _seconds: None,
        )
    except ValueError as exc:
        assert str(exc) == "erro real"
    else:
        raise AssertionError("ValueError deveria ser propagado")
