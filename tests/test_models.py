from datetime import UTC, datetime
from decimal import Decimal

import pytest

from automation.config import (
    BODY_LIMIT_BYTES,
    CONNECT_TIMEOUT_SECONDS,
    DESCRIPTION_LIMIT,
    IMAGE_LIMIT,
    IMPORT_HEADERS,
    PARTNERS,
    PRODUCTS_HEADERS,
    READ_TIMEOUT_SECONDS,
    REDIRECT_LIMIT,
    RETRIES,
    SPREADSHEET_ID,
    Settings,
)
from automation.models import (
    ConfigurationError,
    ImportStatus,
    InvalidProductDataError,
    ProductSnapshot,
    SheetUpdate,
    SyncItemResult,
    SyncReport,
    UpdateMode,
)


def test_headers_preserve_contract():
    assert len(PRODUCTS_HEADERS) == 20
    assert PRODUCTS_HEADERS[0] == "Ativo *"
    assert PRODUCTS_HEADERS[-1] == "Destaque"
    assert len(IMPORT_HEADERS) == 32


def test_headers_are_immutable_tuples():
    assert isinstance(PRODUCTS_HEADERS, tuple)
    assert isinstance(IMPORT_HEADERS, tuple)
    with pytest.raises(TypeError):
        PRODUCTS_HEADERS[0] = "Ativo"


def test_snapshot_discards_non_discount_previous_price(snapshot_kwargs):
    value = ProductSnapshot(**(snapshot_kwargs | {
        "current_price": Decimal("100.00"), "previous_price": Decimal("90.00"),
    }))
    assert value.previous_price is None


def test_snapshot_rejects_zero(snapshot_kwargs):
    with pytest.raises(InvalidProductDataError):
        ProductSnapshot(**(snapshot_kwargs | {"current_price": Decimal("0")}))


def test_snapshot_limits_images_to_four(snapshot_kwargs):
    with pytest.raises(InvalidProductDataError):
        ProductSnapshot(**(snapshot_kwargs | {
            "images": tuple(f"https://images.example/{number}.jpg" for number in range(5)),
        }))


def test_snapshot_is_frozen_and_slotted(snapshot_kwargs):
    snapshot = ProductSnapshot(**snapshot_kwargs)
    with pytest.raises(AttributeError):
        snapshot.name = "Alterado"
    with pytest.raises((AttributeError, TypeError)):
        snapshot.unexpected = "field"


def test_enum_values_preserve_sheet_contract():
    assert {item.value for item in ImportStatus} == {
        "NOVO",
        "AGUARDANDO CONVERSÃO",
        "PROCESSANDO",
        "REVISAR",
        "PRONTO PARA PUBLICAR",
        "PUBLICADO",
        "ATENÇÃO",
        "ERRO",
        "DESATIVADO",
    }
    assert {item.value for item in UpdateMode} == {"Automático", "Manual", "Bloqueado"}


def test_fixed_settings_and_partner_limits():
    assert SPREADSHEET_ID == "1oj0NbAkngUjjaYfJy5sEgzfDb7I0klHaUbvTzq6ZDB0"
    assert (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS) == (5, 15)
    assert (REDIRECT_LIMIT, BODY_LIMIT_BYTES, RETRIES) == (5, 2_000_000, 2)
    assert (DESCRIPTION_LIMIT, IMAGE_LIMIT) == (4_000, 4)
    assert PARTNERS["tiktok_shop"].allowed_hosts == ()
    assert PARTNERS["tiktok_shop"].live_verified is False


def test_settings_parses_service_account_json_in_memory(monkeypatch):
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"type":"service_account"}')
    settings = Settings.from_env()
    assert settings.service_account_info == {"type": "service_account"}
    assert settings.spreadsheet_id == SPREADSHEET_ID
    assert settings.import_worksheet == "Importações"
    assert settings.products_worksheet == "Produtos"


def test_settings_rejects_malformed_service_account_json_without_echoing_it(monkeypatch):
    secret = '{"private_key":"not-for-output"'
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", secret)
    with pytest.raises(ConfigurationError) as raised:
        Settings.from_env()
    assert secret not in str(raised.value)


def test_settings_rejects_a_different_spreadsheet_id_without_echoing_it(monkeypatch):
    unexpected_id = "not-the-orvani-spreadsheet"
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"type":"service_account"}')
    monkeypatch.setenv("ORVANI_SPREADSHEET_ID", unexpected_id)
    with pytest.raises(ConfigurationError) as raised:
        Settings.from_env()
    assert unexpected_id not in str(raised.value)


def test_sync_report_returns_the_final_status_for_reported_row():
    item = SyncItemResult(
        row_number=4,
        initial_status=ImportStatus.NOVO,
        final_status=ImportStatus.REVISAR,
        message="Pronto para revisão",
        import_changed=True,
        product_changed=False,
    )
    report = SyncReport(
        items=(item,),
        planned_import_updates=(SheetUpdate("Importações!A4", (("REVISAR",),)),),
        planned_product_updates=(),
        dry_run=True,
    )
    assert report.final_status(4) is ImportStatus.REVISAR
    with pytest.raises(KeyError):
        report.final_status(5)


def test_new_import_row_gets_one_planned_automation_id_write():
    from automation.models import ImportRecord

    record, update = ImportRecord.from_sheet_row(7, ("",))
    assert record.automation_id
    assert update is not None
    assert update.range_name == "Importações!A7"
    assert update.values == ((record.automation_id,),)
    assert record.publish == "Não"
    assert record.featured == "Não"
    assert record.update_mode is UpdateMode.AUTOMATICO
    assert record.status is ImportStatus.NOVO
    assert record.consecutive_attempts == 0


def test_none_automation_id_gets_one_planned_uuid4_write():
    from automation.models import ImportRecord

    record, update = ImportRecord.from_sheet_row(7, (None,))
    assert record.automation_id
    assert update is not None
    assert update.values == ((record.automation_id,),)
    assert record.automation_id != "None"
    assert record.automation_id.split("-")[2][0] == "4"


def test_existing_automation_id_is_preserved_without_a_planned_write():
    from automation.models import ImportRecord

    record, update = ImportRecord.from_sheet_row(7, ("stored-id",))
    assert record.automation_id == "stored-id"
    assert update is None

def test_update_mode_accepts_manual():
    assert UpdateMode("Manual") is UpdateMode.MANUAL


def test_import_record_parses_manual_update_mode():
    from automation.models import ImportRecord

    row = [""] * 32
    row[0] = "manual-row"
    row[1] = "Sim"
    row[2] = "Sim"
    row[5] = "Manual"

    record, planned = ImportRecord.from_sheet_row(2, row)

    assert planned is None
    assert record.update_mode is UpdateMode.MANUAL
