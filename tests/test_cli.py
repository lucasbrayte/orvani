from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys

import pytest

from automation.config import IMPORT_HEADERS, PARTNERS, PRODUCTS_HEADERS, PartnerConfig
from automation.models import ProductSnapshot


@dataclass(frozen=True)
class _Settings:
    service_account_info: object = None
    spreadsheet_id: str = "sheet-id"
    import_worksheet: str = "Importações"
    products_worksheet: str = "Produtos"
    raw_service_account_json: str = '{"private_key":"cli-secret"}'

    def __post_init__(self):
        if self.service_account_info is None:
            object.__setattr__(self, "service_account_info", {"type": "service_account", "client_email": "bot@example.invalid", "private_key": "key", "token_uri": "https://oauth2.googleapis.com/token"})


class _Registry:
    def select(self, _url):
        class Connector:
            partner_key = "mercado_livre"

            def fetch(self, url):
                return ProductSnapshot(
                    partner="mercado_livre", external_id="MLB123", catalog_id=None,
                    source_url="https://www.mercadolivre.com.br/item/MLB123", affiliate_url=url,
                    name="Produto", description="Descrição", current_price=Decimal("10"),
                    previous_price=None, currency="BRL", category="Eletrônicos", subcategory="Áudio",
                    product_type="Físico", coupon=None, coupon_expires_at=None,
                    images=("https://images.example/item.jpg",), available=True,
                    fetched_at=datetime(2026, 8, 30, tzinfo=UTC),
                )

        return Connector()


def _record(*, automation_id="auto-1", status="NOVO", update_mode="Automático", publish="Não"):
    return [
        automation_id, "Sim", publish, "Não", "", update_mode,
        "https://www.mercadolivre.com.br/item/MLB123", "https://meli.la/item", "mercado_livre", "MLB123",
        "Produto", "Descrição", "Eletrônicos", "Áudio", "Físico", 10, "", "", "", "",
        "https://images.example/item.jpg", "", "", "", "", status, "", 0, "", "", "", "",
    ]


def _product(*, affiliate_url="https://meli.la/item"):
    return [
        "Sim", "Físico", "mercado_livre", "Eletrônicos", "Áudio", "Produto", "Descrição", 10, "", "", "",
        affiliate_url, "Ver oferta", "", "https://images.example/item.jpg", "", "", "", "", "Não",
    ]


def _gateway(import_rows=(), product_rows=(), *, sheets=True):
    from conftest import FakeSheetsGateway, _quoted

    metadata = ()
    values = {}
    if sheets:
        metadata = (
            {"properties": {"sheetId": 1, "title": "Importações", "sheetType": "GRID", "gridProperties": {"rowCount": 100, "columnCount": 32}}},
            {"properties": {"sheetId": 2, "title": "Produtos", "sheetType": "GRID", "gridProperties": {"rowCount": 100, "columnCount": 20}}},
        )
        values = {
            _quoted("Importações", "A1:AF"): [list(IMPORT_HEADERS), *import_rows],
            _quoted("Importações", "A1:AF1"): [list(IMPORT_HEADERS)],
            _quoted("Produtos", "A4:T"): [list(PRODUCTS_HEADERS), [], *product_rows],
        }
    return FakeSheetsGateway(sheets=metadata, values=values)


@pytest.fixture
def cli_dependencies():
    from automation.cli import CliDependencies

    return CliDependencies(settings=_Settings(), gateway=_gateway(), registry=_Registry(), partners=PARTNERS)


@pytest.mark.parametrize("argv", [
    ["setup-sheet", "--dry-run"],
    ["sync", "--mode", "pending", "--dry-run"],
    ["sync", "--mode", "full", "--dry-run"],
    ["validate"],
])
def test_required_commands_parse(argv):
    """Catches an absent or permissive command interface."""
    from automation.cli import build_parser

    assert build_parser().parse_args(argv).command == argv[0]


@pytest.mark.parametrize("argv", [
    ["unknown-command"],
    ["sync", "--mode", "unknown-mode"],
    ["validate", "unexpected"],
])
def test_main_returns_parser_rejection_code(cli_dependencies, argv):
    """Catches parser failures escaping main instead of returning their process code."""
    from automation.cli import main

    assert main(argv, cli_dependencies) == 2


def test_setup_dry_run_never_writes(cli_dependencies):
    """Catches setup planning accidentally applying its request batch."""
    from automation.cli import main

    assert main(["setup-sheet", "--dry-run"], cli_dependencies) == 0
    assert cli_dependencies.gateway.spreadsheet_writes == []


def test_setup_live_writes_only_to_the_injected_gateway(cli_dependencies):
    """Catches the explicit live setup command becoming a no-op."""
    from automation.cli import main

    dependencies = replace(cli_dependencies, gateway=_gateway(sheets=False))
    assert main(["setup-sheet"], dependencies) == 0
    assert len(dependencies.gateway.spreadsheet_writes) == 1


@pytest.mark.parametrize("mode", ["pending", "full"])
def test_sync_dry_run_plans_without_writing(cli_dependencies, mode, capsys):
    """Catches dry-run forwarding the wrong write gate to SyncEngine."""
    from automation.cli import main

    dependencies = replace(cli_dependencies, gateway=_gateway([_record(status="NOVO" if mode == "pending" else "PUBLICADO")]))
    assert main(["sync", "--mode", mode, "--dry-run"], dependencies) == 0
    assert dependencies.gateway.value_writes == []
    assert "REVISAR:1" in capsys.readouterr().out


@pytest.mark.parametrize("mode", ["pending", "full"])
def test_sync_live_writes_only_to_the_injected_gateway(cli_dependencies, mode):
    """Catches a live sync being silently changed into dry-run."""
    from automation.cli import main

    dependencies = replace(cli_dependencies, gateway=_gateway([_record(status="NOVO" if mode == "pending" else "PUBLICADO")]))
    assert main(["sync", "--mode", mode], dependencies) == 0
    assert dependencies.gateway.value_writes


def test_validate_is_read_only_and_never_echoes_secret_url_or_row_body(cli_dependencies, capsys):
    """Catches validation leaking spreadsheet contents or modifying a sheet."""
    from automation.cli import main

    secret = cli_dependencies.settings.raw_service_account_json
    dependencies = replace(cli_dependencies, gateway=_gateway([_record()]))
    assert main(["validate"], dependencies) == 0
    captured = capsys.readouterr()
    assert dependencies.gateway.spreadsheet_writes == [] and dependencies.gateway.value_writes == []
    assert secret not in captured.out + captured.err
    assert "https://meli.la/item" not in captured.out + captured.err
    assert "Produto" not in captured.out + captured.err


def test_missing_environment_returns_sanitized_configuration_exit(monkeypatch, capsys):
    """Catches credential loading before parser validation or raw environment leakage."""
    from automation.cli import main

    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    assert main(["validate"]) == 2
    captured = capsys.readouterr()
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" in captured.err
    assert "Traceback" not in captured.err + captured.out


def test_module_validate_without_environment_returns_sanitized_exit():
    """Catches module entrypoint bypassing main's configuration gate."""
    environment = dict(os.environ)
    environment.pop("GOOGLE_SERVICE_ACCOUNT_JSON", None)
    result = subprocess.run(
        [sys.executable, "-m", "automation.cli", "validate"],
        cwd=Path(__file__).parents[1], env=environment, text=True, capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stdout + result.stderr
    assert "RuntimeWarning" not in result.stderr
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" in result.stderr


def test_validate_rejects_malformed_credential_structure(cli_dependencies, capsys):
    """Catches a structurally incomplete credential reaching a gateway."""
    from automation.cli import main

    dependencies = replace(cli_dependencies, settings=_Settings(service_account_info={"type": "service_account"}))
    assert main(["validate"], dependencies) == 2
    assert "cli-secret" not in capsys.readouterr().err


def test_validate_requires_token_uri_before_any_gateway_access(cli_dependencies):
    """Catches a fake-only credential shape that Google service-account loading rejects."""
    from automation.cli import main

    settings = _Settings(service_account_info={"type": "service_account", "client_email": "bot@example.invalid", "private_key": "key"})
    dependencies = replace(cli_dependencies, settings=settings)
    assert main(["validate"], dependencies) == 2
    assert dependencies.gateway.spreadsheet_reads == 0 and dependencies.gateway.value_reads == []


def test_validate_accepts_the_minimum_side_effect_free_credential_shape(cli_dependencies):
    """Catches validation requiring credential construction or fields beyond the minimum gate."""
    from automation.cli import main

    settings = _Settings(service_account_info={"type": "service_account", "client_email": "bot@example.invalid", "private_key": "key", "token_uri": "https://oauth2.googleapis.com/token"})
    assert main(["validate"], replace(cli_dependencies, settings=settings)) == 0


def test_validate_rejects_incorrect_header_contract(cli_dependencies):
    """Catches validation treating a present but wrong header row as usable."""
    from automation.cli import main

    gateway = _gateway()
    gateway._values["'Importações'!A1:AF"] = [["wrong header"]]
    assert main(["validate"], replace(cli_dependencies, gateway=gateway)) == 1


@pytest.mark.parametrize("column,value", [(1, "Talvez"), (2, "Talvez"), (3, "Talvez"), (4, "-1"), (15, "zero")])
def test_validate_rejects_every_import_enum_and_scalar_sync_rejects(cli_dependencies, column, value):
    """Catches validation accepting a scalar rejected before sync can safely plan."""
    from automation.cli import main

    row = _record()
    row[column] = value
    assert main(["validate"], replace(cli_dependencies, gateway=_gateway([row]))) == 1


def test_validate_normalizes_automation_ids_before_duplicate_detection(cli_dependencies):
    """Catches duplicate automation IDs differing only in harmless spacing."""
    from automation.cli import main

    assert main(["validate"], replace(cli_dependencies, gateway=_gateway([_record(), _record(automation_id=" auto-1 ")]))) == 1


@pytest.mark.parametrize("column", [1, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 20])
def test_validate_requires_every_published_product_input(cli_dependencies, column):
    """Catches a published row missing a field required to map a product."""
    from automation.cli import main

    row = _record(status="PUBLICADO", publish="Sim")
    row[column] = ""
    assert main(["validate"], replace(cli_dependencies, gateway=_gateway([row]))) == 1


@pytest.mark.parametrize("column", [6, 7, 8, 9, 10, 11, 12, 13, 14, 20])
def test_validate_rejects_whitespace_only_published_text_input(cli_dependencies, column):
    """Catches normalized-empty publication fields bypassing the literal-empty gate."""
    from automation.cli import main

    row = _record(status="PUBLICADO", publish="Sim")
    row[column] = "   "
    assert main(["validate"], replace(cli_dependencies, gateway=_gateway([row]))) == 1


def test_validate_rejects_ambiguous_products_by_normalized_last_published_link(cli_dependencies):
    """Catches ambiguity hidden by reordered query parameters on the published link."""
    from automation.cli import main

    row = _record(status="PRONTO PARA PUBLICAR", publish="Sim")
    row[28] = "https://meli.la/item?a=1&b=2"
    products = [_product(affiliate_url="https://meli.la/item?b=2&a=1"), _product(affiliate_url="https://meli.la/item?b=2&a=1")]
    assert main(["validate"], replace(cli_dependencies, gateway=_gateway([row], products))) == 1


def test_validate_rejects_ambiguous_products_by_partner_external_id(cli_dependencies):
    """Catches ambiguity falling through to the canonical partner/external-ID tier."""
    from automation.cli import main

    row = _record(status="PRONTO PARA PUBLICAR", publish="Sim")
    row[7] = "https://meli.la/no-match"
    row[9] = "MLB123456"
    products = [
        _product(affiliate_url="https://www.mercadolivre.com.br/item/MLB123456?a=1"),
        _product(affiliate_url="https://www.mercadolivre.com.br/item/MLB123456?a=2"),
    ]
    assert main(["validate"], replace(cli_dependencies, gateway=_gateway([row], products))) == 1


def test_schema_or_access_error_returns_operational_exit_without_raw_exception(cli_dependencies, capsys):
    """Catches gateway failures escaping as detailed operational errors."""
    from automation.cli import main

    class FailingGateway:
        def get_spreadsheet(self):
            raise RuntimeError("https://private.invalid/?token=secret")

    assert main(["validate"], replace(cli_dependencies, gateway=FailingGateway())) == 1
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "private.invalid" not in output and "secret" not in output and "Traceback" not in output


def test_validate_identifies_the_product_data_stage_without_echoing_cells(cli_dependencies, capsys):
    """Catches a malformed product being hidden behind an unactionable generic failure."""
    from automation.cli import main

    product = _product()
    product[7] = "secret-invalid-price"

    assert main(
        ["validate"],
        replace(cli_dependencies, gateway=_gateway(product_rows=[product])),
    ) == 1
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "etapa=dados-produtos" in output
    assert "secret-invalid-price" not in output and "Traceback" not in output


@pytest.mark.parametrize(("range_name", "stage"), [
    ("'Importações'!A1:AF", "leitura-importacoes"),
    ("'Produtos'!A4:T", "leitura-produtos"),
])
def test_validate_identifies_the_table_read_stage_without_echoing_headers(
    cli_dependencies, capsys, range_name, stage
):
    """Catches a header mismatch being indistinguishable from unrelated runtime failures."""
    from automation.cli import main

    gateway = _gateway()
    gateway._values[range_name][0][0] = "secret-invalid-header"

    assert main(["validate"], replace(cli_dependencies, gateway=gateway)) == 1
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert f"etapa={stage}" in output
    assert "secret-invalid-header" not in output and "Traceback" not in output


@pytest.mark.parametrize("mutator", [
    lambda rows, products: rows.append(_record(automation_id="auto-1")),
    lambda rows, products: rows.__setitem__(0, _record(update_mode="Inválido")),
    lambda rows, products: _ambiguous_products(rows, products),
    lambda rows, products: rows.__setitem__(0, _record(status="PUBLICADO", publish="Sim").__setitem__(10, "") if False else _published_missing_name()),
])
def test_validate_rejects_invalid_operational_data(cli_dependencies, capsys, mutator):
    """Catches validation accepting duplicate IDs, bad enums, ambiguous adoption, or incomplete publication."""
    from automation.cli import main

    rows, products = [_record()], []
    mutator(rows, products)
    assert main(["validate"], replace(cli_dependencies, gateway=_gateway(rows, products))) == 1
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "Produto" not in output and "https://meli.la/item" not in output


def _published_missing_name():
    row = _record(status="PUBLICADO", publish="Sim")
    row[10] = ""
    return row


def _ambiguous_products(rows, products):
    rows[0] = _record(status="PUBLICADO", publish="Sim")
    products.extend([_product(), _product()])


def test_validate_reports_partner_rules_and_tiktok_limitation(cli_dependencies, capsys):
    """Catches an unreported TikTok allowlist limitation or invalid configured host policy."""
    from automation.cli import main

    assert main(["validate"], cli_dependencies) == 0
    output = capsys.readouterr().out
    assert "TikTok Shop" in output and "limitação" in output

    partners = dict(PARTNERS)
    partners["shopee"] = PartnerConfig("shopee", "Shopee", (), True)
    assert main(["validate"], replace(cli_dependencies, partners=partners)) == 1


@pytest.mark.parametrize("partner", [
    PartnerConfig("shopee", "Shopee", ("unconfirmed.example",), True),
    PartnerConfig("shopee", "Shopee", PARTNERS["shopee"].allowed_hosts, False),
])
def test_validate_rejects_well_formed_but_unauthorized_partner_config(cli_dependencies, partner):
    """Catches host or verification-policy substitutions that look syntactically safe."""
    from automation.cli import main

    partners = dict(PARTNERS)
    partners["shopee"] = partner
    assert main(["validate"], replace(cli_dependencies, partners=partners)) == 1
