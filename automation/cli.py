"""CLI segura para a automação do catálogo de afiliados."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import sys
from typing import Any, Protocol

from .config import IMPORT_HEADERS, PARTNERS, PRODUCTS_HEADERS, PartnerConfig, Settings, normalize_unicode_text
from .connectors.base import build_connector_registry
from .http_client import SafeHttpClient
from .models import AmbiguousProductMatchError, ConfigurationError, ImportRecord, ImportStatus, SheetSchemaError
from .sheets import GoogleSheetsGateway, SheetsGateway, read_table, setup_import_sheet
from .sync import SyncEngine, find_product_match, parse_product_rows, validate_import_row


class _SettingsLike(Protocol):
    service_account_info: Mapping[str, object]
    spreadsheet_id: str
    import_worksheet: str
    products_worksheet: str


class _ValidationStageError(Exception):
    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(stage)


@dataclass(frozen=True, slots=True)
class CliDependencies:
    """Injected collaborators for local, network-free CLI execution."""

    settings: _SettingsLike
    gateway: SheetsGateway
    registry: Any
    partners: Mapping[str, PartnerConfig] = field(default_factory=lambda: PARTNERS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orvani-automation")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup-sheet")
    setup.add_argument("--dry-run", action="store_true")
    sync = commands.add_parser("sync")
    sync.add_argument("--mode", choices=("pending", "full"), required=True)
    sync.add_argument("--dry-run", action="store_true")
    commands.add_parser("validate")
    return parser


def validate_environment(dependencies: CliDependencies) -> tuple[int, int, int]:
    """Read and check the current contract without exposing row contents."""
    _validate_credentials(dependencies.settings.service_account_info)
    limitations = _validate_partners(dependencies.partners)
    metadata = dependencies.gateway.get_spreadsheet()
    _validate_worksheet_access(metadata, dependencies.settings)
    try:
        imports = read_table(
            dependencies.gateway, dependencies.settings.import_worksheet, headers=IMPORT_HEADERS
        )
    except Exception:
        raise _ValidationStageError("leitura-importacoes") from None
    try:
        products = read_table(
            dependencies.gateway, dependencies.settings.products_worksheet, headers=PRODUCTS_HEADERS
        )
    except Exception:
        raise _ValidationStageError("leitura-produtos") from None
    try:
        failures = _validate_rows(imports, products)
    except SheetSchemaError as error:
        raise SheetSchemaError(f"Dados inválidos em Importações/Produtos: {error}") from None
    except Exception:
        raise _ValidationStageError("dados-produtos") from None
    return len(imports), len(products), limitations + failures


def main(argv: Sequence[str] | None = None, cli_dependencies: CliDependencies | None = None) -> int:
    parser = build_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)
    try:
        dependencies = cli_dependencies or _production_dependencies()
        if arguments.command == "setup-sheet":
            plan = setup_import_sheet(
                dependencies.gateway,
                dependencies.settings.import_worksheet,
                dry_run=arguments.dry_run,
            )
            print(f"setup-sheet: criado={int(plan.created)} alterações={len(plan.requests)} dry_run={int(arguments.dry_run)}")
            return 0
        if arguments.command == "sync":
            report = SyncEngine(
                dependencies.gateway,
                dependencies.registry,
                import_worksheet=dependencies.settings.import_worksheet,
                products_worksheet=dependencies.settings.products_worksheet,
            ).run(arguments.mode, dry_run=arguments.dry_run)
            statuses = Counter(item.final_status.value for item in report.items)
            status_counts = ",".join(
                f"{status}:{count}" for status, count in sorted(statuses.items())
            ) or "nenhum"
            product_ranges = ";".join(
                update.range_name for update in report.planned_product_updates
            ) or "nenhum"
            print(
                "sync: "
                f"itens={len(report.items)} importações_planejadas={len(report.planned_import_updates)} "
                f"produtos_planejados={len(report.planned_product_updates)} "
                f"produtos_ranges={product_ranges} estados={status_counts} dry_run={int(arguments.dry_run)}"
            )
            return 0
        imports, products, issues = validate_environment(dependencies)
        limitations = _tiktok_limitation(dependencies.partners)
        print(f"validate: importações={imports} produtos={products} parceiros={len(dependencies.partners)} limitações={limitations} falhas={issues - limitations}")
        if limitations:
            print("limitação: TikTok Shop sem hosts de produção aprovados.")
        return 1 if issues > limitations else 0
    except _ValidationStageError as error:
        print(f"erro operacional: etapa={error.stage}.", file=sys.stderr)
        return 1
    except ConfigurationError:
        print(
            "erro de configuração: GOOGLE_SERVICE_ACCOUNT_JSON ausente ou inválido.",
            file=sys.stderr,
        )
        return 2
    except SheetSchemaError as error:
        print(f"erro de estrutura da planilha: {error}", file=sys.stderr)
        return 1
    except Exception:
        print("erro operacional: validação não concluída.", file=sys.stderr)
        return 1


def _production_dependencies() -> CliDependencies:
    settings = Settings.from_env()
    _validate_credentials(settings.service_account_info)
    gateway = GoogleSheetsGateway.from_settings(settings)
    return CliDependencies(
        settings=settings,
        gateway=gateway,
        registry=build_connector_registry(SafeHttpClient()),
    )


def _validate_credentials(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ConfigurationError("Credenciais inválidas.")
    required = ("type", "client_email", "private_key", "token_uri")
    if (
        value.get("type") != "service_account"
        or any(not isinstance(value.get(key), str) or not value[key].strip() for key in required[1:])
    ):
        raise ConfigurationError("Credenciais inválidas.")


def _validate_partners(partners: Mapping[str, PartnerConfig]) -> int:
    expected = set(PARTNERS)
    if not isinstance(partners, Mapping) or set(partners) != expected:
        raise SheetSchemaError("Parceiros configurados são inválidos.")
    for key, approved in PARTNERS.items():
        partner = partners[key]
        if not isinstance(partner, PartnerConfig) or partner != approved:
            raise SheetSchemaError("Parceiros configurados são inválidos.")
    return _tiktok_limitation(partners)


def _tiktok_limitation(partners: Mapping[str, PartnerConfig]) -> int:
    partner = partners.get("tiktok_shop")
    return int(isinstance(partner, PartnerConfig) and not partner.allowed_hosts)


def _validate_worksheet_access(metadata: object, settings: _SettingsLike) -> None:
    if not isinstance(metadata, Mapping) or not isinstance(metadata.get("sheets"), list):
        raise SheetSchemaError("Planilha inacessível.")
    titles = {
        sheet.get("properties", {}).get("title")
        for sheet in metadata["sheets"]
        if isinstance(sheet, Mapping) and isinstance(sheet.get("properties"), Mapping)
    }
    if settings.import_worksheet not in titles or settings.products_worksheet not in titles:
        raise SheetSchemaError("Abas obrigatórias ausentes.")


def _validate_rows(imports: Sequence[tuple[Any, ...]], products: Sequence[tuple[Any, ...]]) -> int:
    failures = 0
    ids: set[str] = set()
    records: list[ImportRecord] = []
    for row_number, row in enumerate(imports, start=2):
        try:
            validate_import_row(row)
        except SheetSchemaError:
            failures += 1
            continue
        cells = tuple(row) + ("",) * (len(IMPORT_HEADERS) - len(row))
        automation_id = normalize_unicode_text(cells[0]) if isinstance(cells[0], str) else ""
        if not automation_id or automation_id in ids:
            failures += 1
        ids.add(automation_id)
        if cells[25] == ImportStatus.PUBLICADO.value:
            required = (1, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 20)
            if any(_published_input_missing(cells[index]) for index in required):
                failures += 1
        try:
            record, _ = ImportRecord.from_sheet_row(row_number, cells)
        except (ArithmeticError, TypeError, ValueError):
            failures += 1
        else:
            records.append(record)
    product_rows = parse_product_rows(products)
    for record in records:
        if record.publish != "Sim":
            continue
        try:
            find_product_match(record, product_rows)
        except AmbiguousProductMatchError:
            failures += 1
    return failures


def _published_input_missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and not normalize_unicode_text(value))


if __name__ == "__main__":
    raise SystemExit(main())
