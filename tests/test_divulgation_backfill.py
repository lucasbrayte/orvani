from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from automation.config import DIVULGATION_HEADERS, IMPORT_HEADERS, PRODUCTS_HEADERS
from automation.models import ProductRow
from automation.cli import CliDependencies, build_parser, main

NOW = datetime(2026, 9, 4, 23, 58, tzinfo=UTC)
AUTOMATION_ID = "550e8400-e29b-41d4-a716-446655440000"


def _module():
    spec = importlib.util.find_spec("automation.divulgation_backfill")
    assert spec is not None, "automation.divulgation_backfill ainda não existe"
    return importlib.import_module("automation.divulgation_backfill")


def _import_row(*, automation_id=AUTOMATION_ID, active="Sim", publish="Sim", status="PUBLICADO", affiliate="https://meli.la/item", external_id="MLB123", image="https://images.example/item.jpg", price=89.90):
    return (
        automation_id, active, publish, "Não", "", "Automático",
        "https://www.mercadolivre.com.br/item/MLB123", affiliate,
        "mercado_livre", external_id, "Produto", "Descrição", "Casa",
        "Cozinha", "Físico", price, 100.00, "10", "", "", image,
        "", "", "", "Ver oferta", status, "", 0, affiliate, "", "", "",
    )


def _product(*, row_number=6, active="Sim", affiliate="https://meli.la/item", external_id="MLB123", image="https://images.example/item.jpg"):
    return ProductRow(
        row_number=row_number, active=active, product_type="Físico",
        partner="mercado_livre", category="Casa", subcategory="Cozinha",
        name="Air Fryer antiga", description="Produto já publicado antes da Central.",
        price=Decimal("100.00"), promotional_price=Decimal("89.90"),
        coupon="", offer_expires_at="", affiliate_url=affiliate,
        button_text="Ver oferta", video_url="", image_1=image,
        image_2="", image_3="", image_4="", order="", featured="Não",
        reconstructed_external_id=external_id,
    )


def test_backfill_command_is_registered_with_dry_run():
    args = build_parser().parse_args(["backfill-divulgation", "--dry-run"])
    assert args.command == "backfill-divulgation"
    assert args.dry_run is True


def test_backfill_plans_an_old_published_product_once():
    module = _module()
    report = module.plan_divulgation_backfill(
        (_import_row(),), (_product(),), (), created_at=NOW, worksheet="Divulgação"
    )
    assert report.scanned == 1
    assert report.eligible == 1
    assert report.planned == 1
    assert report.already_queued == 0
    assert report.not_eligible == 0
    assert report.missing_product == 0
    assert report.inactive_product == 0
    assert report.invalid == 0
    assert len(report.updates) == 1
    update = report.updates[0]
    assert update.range_name == "'Divulgação'!A2:K2"
    assert update.values[0][9] == "PENDENTE"
    assert update.values[0][4] == "Air Fryer antiga"
    assert update.values[0][6] == Decimal("89.90")


def test_backfill_is_idempotent_against_existing_divulgation():
    module = _module()
    first = module.plan_divulgation_backfill(
        (_import_row(),), (_product(),), (), created_at=NOW, worksheet="Divulgação"
    )
    second = module.plan_divulgation_backfill(
        (_import_row(),), (_product(),), (first.updates[0].values[0],),
        created_at=NOW, worksheet="Divulgação",
    )
    assert second.planned == 0
    assert second.already_queued == 1
    assert second.updates == ()


def test_backfill_skips_bad_items_individually():
    module = _module()
    base = list(_import_row())
    bad_price = tuple(base[:15] + ["preço-inválido"] + base[16:])
    rows = (
        _import_row(),
        _import_row(automation_id="650e8400-e29b-41d4-a716-446655440001", active="Não"),
        _import_row(automation_id="650e8400-e29b-41d4-a716-446655440002", status="REVISAR"),
        _import_row(automation_id="650e8400-e29b-41d4-a716-446655440003", affiliate="https://meli.la/missing", external_id="MLB999"),
        _import_row(automation_id="650e8400-e29b-41d4-a716-446655440004", affiliate="https://meli.la/inactive", external_id="MLB777"),
        _import_row(automation_id="650e8400-e29b-41d4-a716-446655440005", affiliate="https://meli.la/bad-image", external_id="MLB555"),
        bad_price,
    )
    products = (
        _product(),
        _product(row_number=7, active="Não", affiliate="https://meli.la/inactive", external_id="MLB777"),
        _product(row_number=8, affiliate="https://meli.la/bad-image", external_id="MLB555", image="http://unsafe.example/item.jpg"),
    )
    report = module.plan_divulgation_backfill(
        rows, products, (), created_at=NOW, worksheet="Divulgação"
    )
    assert report.scanned == 7
    assert report.eligible == 5
    assert report.planned == 1
    assert report.not_eligible == 2
    assert report.missing_product == 1
    assert report.inactive_product == 1
    assert report.invalid == 2
    assert len(report.updates) == 1


class Gateway:
    def __init__(self):
        self.value_writes = []
        self._sheets = [
            {"properties": {"sheetId": 1, "title": "Importações", "sheetType": "GRID", "gridProperties": {"rowCount": 100, "columnCount": 32}}},
            {"properties": {"sheetId": 2, "title": "Produtos", "sheetType": "GRID", "gridProperties": {"rowCount": 100, "columnCount": 20}}},
            {"properties": {"sheetId": 3, "title": "Divulgação", "sheetType": "GRID", "gridProperties": {"rowCount": 100, "columnCount": 32}}},
        ]

    def get_spreadsheet(self):
        return {"sheets": self._sheets}

    def get_values(self, range_name):
        if range_name == "'Importações'!A1:AF":
            return {"values": [list(IMPORT_HEADERS), list(_import_row())]}
        if range_name == "'Produtos'!A4:T":
            product = _product()
            row = [
                product.active, product.product_type, product.partner, product.category,
                product.subcategory, product.name, product.description, 100.0, 89.9,
                product.coupon, product.offer_expires_at, product.affiliate_url,
                product.button_text, product.video_url, product.image_1, product.image_2,
                product.image_3, product.image_4, product.order, product.featured,
            ]
            return {"values": [list(PRODUCTS_HEADERS), [], row]}
        if range_name == "'Divulgação'!A1:K1":
            return {"values": [list(DIVULGATION_HEADERS)]}
        if range_name == "'Divulgação'!A1:K":
            return {"values": [list(DIVULGATION_HEADERS)]}
        raise AssertionError(f"range inesperado: {range_name}")

    def batch_update(self, _requests):
        raise AssertionError("aba Divulgação já existe; batch_update não é esperado")

    def batch_values_update(self, data, value_input_option):
        self.value_writes.append((data, value_input_option))


class Registry:
    pass


def _dependencies(gateway):
    settings = SimpleNamespace(
        service_account_info={
            "type": "service_account", "client_email": "bot@example.invalid",
            "private_key": "secret", "token_uri": "https://oauth2.googleapis.com/token",
        },
        spreadsheet_id="sheet", import_worksheet="Importações", products_worksheet="Produtos",
    )
    return CliDependencies(settings=settings, gateway=gateway, registry=Registry())


def test_cli_backfill_dry_run_plans_but_never_writes(capsys):
    gateway = Gateway()
    assert main(["backfill-divulgation", "--dry-run"], _dependencies(gateway)) == 0
    output = capsys.readouterr().out
    assert "backfill-divulgation:" in output
    assert "planejados=1" in output
    assert "dry_run=1" in output
    assert gateway.value_writes == []


def test_cli_backfill_live_writes_only_divulgation(capsys):
    gateway = Gateway()
    assert main(["backfill-divulgation"], _dependencies(gateway)) == 0
    output = capsys.readouterr().out
    assert "planejados=1" in output
    assert "dry_run=0" in output
    assert len(gateway.value_writes) == 1
    data, option = gateway.value_writes[0]
    assert option == "RAW"
    assert data[0]["range"] == "'Divulgação'!A2:K2"


def test_runner_exposes_safe_backfill_modes():
    root = Path(__file__).resolve().parents[1]
    script = root / ".github/scripts/run-affiliate-sync.sh"
    env = dict(os.environ)
    env["PYTHON_EXECUTABLE"] = "/bin/echo"

    dry = subprocess.run(["bash", str(script), "backfill-dry-run"], cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert dry.returncode == 0
    assert "-m automation.cli backfill-divulgation --dry-run" in dry.stdout

    blocked = subprocess.run(["bash", str(script), "backfill"], cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert blocked.returncode == 64
    assert "ORVANI_CONFIRM_BACKFILL=true" in blocked.stdout

    confirmed = dict(env)
    confirmed["ORVANI_CONFIRM_BACKFILL"] = "true"
    live = subprocess.run(["bash", str(script), "backfill"], cwd=root, env=confirmed, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert live.returncode == 0
    assert "-m automation.cli backfill-divulgation" in live.stdout
    assert "--dry-run" not in live.stdout


def test_workflow_exposes_backfill_confirmation():
    root = Path(__file__).resolve().parents[1]
    text = (root / ".github/workflows/sync-affiliates.yml").read_text(encoding="utf-8")
    assert "- backfill-dry-run" in text
    assert "- backfill" in text
    assert "confirm_backfill:" in text
    assert "ORVANI_CONFIRM_BACKFILL:" in text
