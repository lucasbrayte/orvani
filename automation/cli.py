"""CLI segura para a automação do catálogo de afiliados."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import sys
from typing import Any, Protocol

from .config import IMPORT_HEADERS, PARTNERS, PRODUCTS_HEADERS, PartnerConfig, Settings
from .connectors.base import build_connector_registry
from .http_client import SafeHttpClient
from .models import ConfigurationError, ImportStatus, SheetSchemaError, UpdateMode
from .sheets import GoogleSheetsGateway, SheetsGateway, read_table, setup_import_sheet
from .sync import SyncEngine


class _SettingsLike(Protocol):
    service_account_info: Mapping[str, object]
    spreadsheet_id: str
    import_worksheet: str
    products_worksheet: str


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
    imports = read_table(
        dependencies.gateway, dependencies.settings.import_worksheet, headers=IMPORT_HEADERS
    )
    products = read_table(
        dependencies.gateway, dependencies.settings.products_worksheet, headers=PRODUCTS_HEADERS
    )
    failures = _validate_rows(imports, products)
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
            print(
                "sync: "
                f"itens={len(report.items)} importações_planejadas={len(report.planned_import_updates)} "
                f"produtos_planejados={len(report.planned_product_updates)} estados={status_counts} dry_run={int(arguments.dry_run)}"
            )
            return 0
        imports, products, issues = validate_environment(dependencies)
        limitations = _tiktok_limitation(dependencies.partners)
        print(f"validate: importações={imports} produtos={products} parceiros={len(dependencies.partners)} limitações={limitations} falhas={issues - limitations}")
        if limitations:
            print("limitação: TikTok Shop sem hosts de produção aprovados.")
        return 1 if issues > limitations else 0
    except ConfigurationError:
        print("erro de configuração: GOOGLE_SERVICE_ACCOUNT_JSON ausente ou inválido.", file=sys.stderr)
        return 2
    except Exception:
        print("erro operacional: validação não concluída.", file=sys.stderr)
        return 1


def _production_dependencies() -> CliDependencies:
    settings = Settings.from_env()
    gateway = GoogleSheetsGateway.from_settings(settings)
    return CliDependencies(
        settings=settings,
        gateway=gateway,
        registry=build_connector_registry(SafeHttpClient()),
    )


def _validate_credentials(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ConfigurationError("Credenciais inválidas.")
    required = ("type", "client_email", "private_key")
    if (
        value.get("type") != "service_account"
        or any(not isinstance(value.get(key), str) or not value[key].strip() for key in required[1:])
    ):
        raise ConfigurationError("Credenciais inválidas.")


def _validate_partners(partners: Mapping[str, PartnerConfig]) -> int:
    expected = set(PARTNERS)
    if not isinstance(partners, Mapping) or set(partners) != expected:
        raise SheetSchemaError("Parceiros configurados são inválidos.")
    for key, partner in partners.items():
        if not isinstance(partner, PartnerConfig) or partner.key != key or not partner.display_name.strip():
            raise SheetSchemaError("Parceiros configurados são inválidos.")
        if key == "tiktok_shop":
            if partner.allowed_hosts:
                raise SheetSchemaError("Hosts TikTok Shop são inválidos.")
            continue
        if not partner.allowed_hosts or any(
            not isinstance(host, str) or not host or ":" in host or "/" in host or host != host.lower()
            for host in partner.allowed_hosts
        ):
            raise SheetSchemaError("Hosts de parceiro são inválidos.")
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
    published_links: list[str] = []
    for row in imports:
        cells = tuple(row) + ("",) * (len(IMPORT_HEADERS) - len(row))
        automation_id = cells[0] if isinstance(cells[0], str) else ""
        if not automation_id or automation_id in ids:
            failures += 1
        ids.add(automation_id)
        if cells[5] not in ("", *(mode.value for mode in UpdateMode)):
            failures += 1
        if cells[25] not in ("", *(status.value for status in ImportStatus)):
            failures += 1
        if cells[25] == ImportStatus.PUBLICADO.value:
            required = (1, 6, 7, 8, 9, 10, 15, 20)
            if any(cells[index] in (None, "") for index in required):
                failures += 1
            link = cells[28] or cells[7]
            if isinstance(link, str) and link:
                published_links.append(link)
    product_links = [row[11] for row in products if len(row) > 11 and isinstance(row[11], str) and row[11]]
    failures += sum(product_links.count(link) > 1 for link in set(published_links))
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
