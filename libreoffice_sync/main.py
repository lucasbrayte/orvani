
from __future__ import annotations

import argparse
import sys
import time

from .api_client import OrvaniApiClient
from .config import ConfigurationError, LocalSettings
from .sync_service import SyncService
from .uno_client import LibreOfficeWorkbook
from .workbook_init import initialize_document, initialize_workbook


def build_parser():
    parser = argparse.ArgumentParser(prog="orvani-sync")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")
    sub.add_parser("run")
    sub.add_parser("init-workbook")
    return parser


def _health(settings: LocalSettings) -> int:
    ok = True
    api = OrvaniApiClient(settings.webapp_url, settings.sync_secret)
    try:
        api.health()
        print("API: OK")
    except Exception as exc:
        ok = False
        print(f"API: FALHA ({exc})")
    finally:
        api.close()

    try:
        LibreOfficeWorkbook.connect(
            host=settings.uno_host,
            port=settings.uno_port,
        )
        print("UNO: OK")
    except Exception as exc:
        ok = False
        print(f"UNO: FALHA ({exc})")

    return 0 if ok else 1


def _wait_for_uno(
    settings: LocalSettings,
    *,
    connector=None,
    sleeper=time.sleep,
):
    connector = connector or LibreOfficeWorkbook.connect
    print(
        "Aguardando Orvani Catálogo em "
        f"{settings.uno_host}:{settings.uno_port}",
        flush=True,
    )
    while True:
        try:
            return connector(
                host=settings.uno_host,
                port=settings.uno_port,
            )
        except Exception:
            sleeper(2)


def _wait_for_workbook(
    workbook,
    path,
    *,
    sleeper=time.sleep,
) -> None:
    print(f"Aguardando Orvani.ods: {path}", flush=True)
    while not workbook.attach_expected_document(path):
        sleeper(2)


def _wait_for_document_ready(
    workbook,
    *,
    initializer=initialize_document,
    sleeper=time.sleep,
) -> None:
    # PyUNO pode expor a URL do documento antes de os intervalos
    # da planilha estarem operacionais. Repetimos somente o
    # RuntimeException transitório do UNO.
    print(
        "Aguardando Orvani.ods ficar pronto para sincronização",
        flush=True,
    )
    while True:
        try:
            initializer(workbook.document)
            return
        except Exception as exc:
            if exc.__class__.__name__ != "RuntimeException":
                raise
            sleeper(0.5)


def _run(settings: LocalSettings) -> int:
    workbook = _wait_for_uno(settings)
    _wait_for_workbook(workbook, settings.workbook_path)

    _wait_for_document_ready(workbook)

    api = OrvaniApiClient(settings.webapp_url, settings.sync_secret)
    try:
        SyncService(
            workbook,
            api,
            poll_seconds=settings.poll_seconds,
        ).run_forever()
    finally:
        api.close()
    return 0


def _init(settings: LocalSettings) -> int:
    path = initialize_workbook(
        settings.workbook_path,
        host=settings.uno_host,
        port=settings.uno_port,
    )
    print(f"Workbook criado: {path}")
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = LocalSettings.from_env()
    except ConfigurationError as exc:
        print(f"Configuração inválida: {exc}", file=sys.stderr)
        return 2

    if args.command == "health":
        return _health(settings)
    if args.command == "run":
        return _run(settings)
    if args.command == "init-workbook":
        return _init(settings)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
