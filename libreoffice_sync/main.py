
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


def _run(settings: LocalSettings) -> int:
    workbook = LibreOfficeWorkbook.connect(
        host=settings.uno_host,
        port=settings.uno_port,
    )

    print(f"Aguardando Orvani.ods: {settings.workbook_path}")
    while not workbook.attach_expected_document(settings.workbook_path):
        time.sleep(2)

    # Reaplica o contrato visual na planilha existente:
    # listas com Sim/Não e Automático/Manual/Bloqueado.
    initialize_document(workbook.document)

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
