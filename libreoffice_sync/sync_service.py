
from __future__ import annotations

import time
from datetime import datetime, timezone

from .api_client import OrvaniApiError, OrvaniAuthError, OrvaniRetryableError
from .hashing import editable_payload, row_hash
from .validation import LocalValidationError, validate_catalog_row


class SyncService:
    RETRY_DELAYS = (2, 5, 15, 30, 60)

    def __init__(self, workbook, api, *, poll_seconds: int = 20):
        self.workbook = workbook
        self.api = api
        self.poll_seconds = int(poll_seconds)
        self._next_poll_at = 0.0
        self._retry_at = None
        self._retry_index = 0

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _prepare_changed(self):
        rows = self.workbook.read_catalog_rows()

        if any(not row.automation_id for row in rows):
            for row in rows:
                if not row.automation_id:
                    self.workbook.ensure_automation_id(row.row_number)
            rows = self.workbook.read_catalog_rows()

        pending = []
        metadata = {}

        for row in rows:
            current_hash = row_hash(row)
            self.workbook.write_row_hash(row.row_number, current_hash)

            try:
                validate_catalog_row(row)
            except LocalValidationError as exc:
                self.workbook.write_local_error(row.row_number, str(exc))
                continue

            self.workbook.clear_local_error(row.row_number)

            if current_hash != row.acknowledged_hash:
                pending.append(editable_payload(row))
                metadata[row.automation_id] = (row.row_number, current_hash)

        return pending, metadata

    def _upload_pending(self):
        pending, metadata = self._prepare_changed()
        if not pending:
            self._retry_at = None
            self._retry_index = 0
            return

        for start in range(0, len(pending), 50):
            batch = pending[start:start + 50]
            self.api.upsert_products(batch)

            # A successful Apps Script action means the entire validated
            # batch was accepted. This also makes retries restart-safe when
            # the first server response was lost but the write already landed.
            for item in batch:
                automation_id = str(item["ID Automação"])
                row_number, current_hash = metadata[automation_id]
                self.workbook.write_acknowledged_hash(row_number, current_hash)
                self.workbook.write_last_local_sync(row_number, self._timestamp())

        self._retry_at = None
        self._retry_index = 0

    def _schedule_retry(self, now_monotonic: float):
        delay = self.RETRY_DELAYS[min(
            self._retry_index, len(self.RETRY_DELAYS) - 1
        )]
        self._retry_index = min(
            self._retry_index + 1, len(self.RETRY_DELAYS) - 1
        )
        self._retry_at = now_monotonic + delay

    def _write_api_error(self, message: str):
        for row in self.workbook.read_catalog_rows():
            self.workbook.write_local_error(row.row_number, message)

    def _poll_status(self, now_monotonic: float):
        rows = self.workbook.read_catalog_rows()
        ids = [row.automation_id for row in rows if row.automation_id]

        for start in range(0, len(ids), 50):
            batch = ids[start:start + 50]
            if not batch:
                continue
            for status in self.api.get_status(batch):
                self.workbook.apply_status(status)

        self._next_poll_at = now_monotonic + self.poll_seconds

    def run_once(self, now_monotonic: float) -> None:
        should_upload = self.workbook.consume_save_event()
        if self._retry_at is not None and now_monotonic >= self._retry_at:
            should_upload = True

        if should_upload:
            try:
                self._upload_pending()
            except OrvaniRetryableError:
                self._schedule_retry(now_monotonic)
            except (OrvaniAuthError, OrvaniApiError) as exc:
                self._write_api_error(f"Sincronização: {exc}")
                self._retry_at = None

        if now_monotonic >= self._next_poll_at:
            try:
                self._poll_status(now_monotonic)
            except OrvaniRetryableError:
                self._next_poll_at = now_monotonic + min(self.poll_seconds, 20)
            except (OrvaniAuthError, OrvaniApiError):
                self._next_poll_at = now_monotonic + self.poll_seconds

    def run_forever(self) -> None:
        while True:
            self.run_once(time.monotonic())
            time.sleep(0.5)
