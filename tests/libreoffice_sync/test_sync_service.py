
from __future__ import annotations

from dataclasses import replace

from libreoffice_sync.hashing import row_hash
from libreoffice_sync.models import BackendStatus
from libreoffice_sync.sync_service import SyncService


class FakeWorkbook:
    def __init__(self, rows):
        self.rows = tuple(rows)
        self.saved = False
        self.errors = {}
        self.hashes = {}
        self.acks = {}
        self.synced = {}
        self.statuses = []

    def consume_save_event(self):
        value = self.saved
        self.saved = False
        return value

    def read_catalog_rows(self):
        return self.rows

    def ensure_automation_id(self, row_number):
        value = f"generated-{row_number}"
        self.rows = tuple(
            replace(row, automation_id=value)
            if row.row_number == row_number else row
            for row in self.rows
        )
        return value

    def write_local_error(self, row_number, message):
        self.errors[row_number] = message

    def clear_local_error(self, row_number):
        self.errors.pop(row_number, None)

    def write_row_hash(self, row_number, value):
        self.hashes[row_number] = value

    def write_acknowledged_hash(self, row_number, value):
        self.acks[row_number] = value
        self.rows = tuple(
            replace(row, acknowledged_hash=value)
            if row.row_number == row_number else row
            for row in self.rows
        )

    def write_last_local_sync(self, row_number, value):
        self.synced[row_number] = value

    def apply_status(self, status):
        self.statuses.append(status)
        return True


class FakeApi:
    def __init__(self):
        self.upserts = []
        self.status_calls = []
        self.statuses = []

    def upsert_products(self, products):
        self.upserts.append(list(products))
        return {"ok": True, "action": "upsert_products", "changed": len(products)}

    def get_status(self, ids):
        self.status_calls.append(list(ids))
        return tuple(self.statuses)


def test_save_uploads_only_changed_valid_rows(valid_row):
    changed = replace(valid_row, acknowledged_hash="old")
    same_base = replace(valid_row, row_number=3, automation_id="uuid-3")
    same = replace(same_base, acknowledged_hash=row_hash(same_base))

    wb = FakeWorkbook([changed, same])
    api = FakeApi()
    service = SyncService(wb, api, poll_seconds=20)
    wb.saved = True

    service.run_once(100.0)

    assert len(api.upserts) == 1
    assert [item["ID Automação"] for item in api.upserts[0]] == ["uuid-1"]
    assert 2 in wb.acks
    assert 3 not in wb.acks


def test_ack_advances_after_success_even_when_server_reports_no_change(valid_row):
    row = replace(valid_row, acknowledged_hash="old")
    wb = FakeWorkbook([row])
    api = FakeApi()

    def unchanged(products):
        api.upserts.append(list(products))
        return {
            "ok": True,
            "action": "upsert_products",
            "changed": 0,
            "changedIds": [],
        }

    api.upsert_products = unchanged
    service = SyncService(wb, api)
    wb.saved = True

    service.run_once(1.0)

    assert 2 in wb.acks


def test_validation_error_stays_local_and_is_not_uploaded(valid_row):
    invalid = replace(valid_row, current_price=None)
    wb = FakeWorkbook([invalid])
    api = FakeApi()
    service = SyncService(wb, api)
    wb.saved = True

    service.run_once(1.0)

    assert api.upserts == []
    assert "Preço Atual" in wb.errors[2]


def test_status_poll_runs_once_per_interval(valid_row):
    wb = FakeWorkbook([valid_row])
    api = FakeApi()
    api.statuses = [
        BackendStatus(
            automation_id="uuid-1",
            external_id="",
            status="PUBLICADO",
            message="ok",
            discount="",
            last_published_url="",
            data_signature="",
            last_checked_at="",
            last_updated_at="",
        )
    ]
    service = SyncService(wb, api, poll_seconds=20)

    service.run_once(100.0)
    service.run_once(119.9)
    service.run_once(120.0)

    assert len(api.status_calls) == 2
    assert len(wb.statuses) == 2
