
from __future__ import annotations

import threading
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .models import BackendStatus, CatalogRow
from .workbook_schema import CATALOG_SHEET


def _string(cell: Any) -> str:
    value = getattr(cell, "String", "")
    return "" if value is None else str(value).strip()


def _decimal(cell: Any) -> Decimal | None:
    numeric = getattr(cell, "Value", None)
    if numeric not in (None, 0, 0.0):
        try:
            return Decimal(str(numeric))
        except (InvalidOperation, ValueError):
            pass

    text = _string(cell)
    if not text:
        return None

    normalized = text.replace("R$", "").replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


class _SimpleSaveListener:
    def __init__(self, callback):
        self._callback = callback

    def documentEventOccurred(self, event):
        if getattr(event, "EventName", "") in {"OnSaveDone", "OnSaveAsDone"}:
            self._callback()

    def disposing(self, _event):
        return None


class LibreOfficeWorkbook:
    def __init__(self, *, desktop=None, document=None, expected_path: Path | None = None):
        self._desktop = desktop
        self._document = document
        self._expected_path = expected_path.resolve() if expected_path else None
        self._save_event = threading.Event()
        self._listener = None

    @classmethod
    def from_document(cls, document, expected_path: Path):
        instance = cls(document=document, expected_path=expected_path)
        instance._install_listener()
        return instance

    @classmethod
    def connect(cls, host: str = "127.0.0.1", port: int = 2002):
        if host != "127.0.0.1":
            raise ValueError("UNO deve usar somente 127.0.0.1.")

        import uno  # type: ignore

        local_ctx = uno.getComponentContext()
        resolver = local_ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver",
            local_ctx,
        )
        ctx = resolver.resolve(
            f"uno:socket,host={host},port={int(port)};urp;StarOffice.ComponentContext"
        )
        desktop = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop",
            ctx,
        )
        return cls(desktop=desktop)

    @property
    def desktop(self):
        return self._desktop

    @property
    def document(self):
        return self._document

    def _install_listener(self):
        if self._document is None or not hasattr(
            self._document, "addDocumentEventListener"
        ):
            return

        self._listener = _SimpleSaveListener(self.mark_saved)
        self._document.addDocumentEventListener(self._listener)

    def attach_expected_document(self, path: Path) -> bool:
        if self._desktop is None:
            return False

        expected = path.resolve().as_uri()
        components = self._desktop.getComponents()
        enumeration = components.createEnumeration()

        while enumeration.hasMoreElements():
            component = enumeration.nextElement()
            if getattr(component, "URL", "") == expected:
                sheets = getattr(component, "Sheets", None)
                if sheets is None or not sheets.hasByName(CATALOG_SHEET):
                    return False
                self._document = component
                self._expected_path = path.resolve()
                self._install_listener()
                return True

        return False

    def _sheet(self):
        if self._document is None:
            raise RuntimeError("Documento Orvani.ods não está anexado.")
        sheets = self._document.Sheets
        if not sheets.hasByName(CATALOG_SHEET):
            raise RuntimeError('Aba "Catálogo" não encontrada.')
        return sheets.getByName(CATALOG_SHEET)

    @staticmethod
    def _row_index(row_number: int) -> int:
        if row_number < 2:
            raise ValueError("row_number deve ser >= 2.")
        return row_number - 1

    def _last_used_row_index(self, sheet) -> int:
        try:
            cursor = sheet.createCursor()
            cursor.gotoEndOfUsedArea(True)
            return int(cursor.RangeAddress.EndRow)
        except Exception:
            return 1

    def read_catalog_rows(self) -> tuple[CatalogRow, ...]:
        sheet = self._sheet()
        end_row = self._last_used_row_index(sheet)
        rows = []

        for row_index in range(1, end_row + 1):
            editable = [_string(sheet.getCellByPosition(col, row_index)) for col in range(22)]
            automation_id = _string(sheet.getCellByPosition(27, row_index))
            acknowledged_hash = _string(sheet.getCellByPosition(33, row_index))
            local_hash = _string(sheet.getCellByPosition(32, row_index))

            if not any(editable) and not automation_id:
                continue

            rows.append(
                CatalogRow(
                    row_number=row_index + 1,
                    automation_id=automation_id,
                    active=editable[0],
                    publish=editable[1],
                    featured=editable[2],
                    order=editable[3],
                    update_mode=editable[4],
                    product_url=editable[5],
                    affiliate_url=editable[6],
                    partner=editable[7],
                    name=editable[8],
                    description=editable[9],
                    category=editable[10],
                    subcategory=editable[11],
                    product_type=editable[12],
                    current_price=_decimal(sheet.getCellByPosition(13, row_index)),
                    previous_price=_decimal(sheet.getCellByPosition(14, row_index)),
                    coupon=editable[15],
                    coupon_expires_at=editable[16],
                    images=(editable[17], editable[18], editable[19], editable[20]),
                    button_text=editable[21],
                    row_hash=local_hash,
                    acknowledged_hash=acknowledged_hash,
                )
            )

        return tuple(rows)

    def ensure_automation_id(self, row_number: int) -> str:
        sheet = self._sheet()
        row_index = self._row_index(row_number)
        cell = sheet.getCellByPosition(27, row_index)
        current = _string(cell)
        if current:
            return current

        generated = str(uuid.uuid4())
        cell.String = generated
        return generated

    def write_local_error(self, row_number: int, message: str) -> None:
        sheet = self._sheet()
        row_index = self._row_index(row_number)
        sheet.getCellByPosition(22, row_index).String = "ERRO LOCAL"
        sheet.getCellByPosition(23, row_index).String = str(message)

    def clear_local_error(self, row_number: int) -> None:
        sheet = self._sheet()
        row_index = self._row_index(row_number)
        if _string(sheet.getCellByPosition(22, row_index)) == "ERRO LOCAL":
            sheet.getCellByPosition(22, row_index).String = ""
            sheet.getCellByPosition(23, row_index).String = ""

    def write_row_hash(self, row_number: int, value: str) -> None:
        sheet = self._sheet()
        row_index = self._row_index(row_number)
        sheet.getCellByPosition(32, row_index).String = value

    def write_acknowledged_hash(self, row_number: int, value: str) -> None:
        sheet = self._sheet()
        row_index = self._row_index(row_number)
        sheet.getCellByPosition(33, row_index).String = value

    def write_last_local_sync(self, row_number: int, value: str) -> None:
        sheet = self._sheet()
        row_index = self._row_index(row_number)
        sheet.getCellByPosition(31, row_index).String = value

    def _find_row_by_id(self, automation_id: str) -> int | None:
        if not automation_id:
            return None
        sheet = self._sheet()
        end_row = self._last_used_row_index(sheet)
        for row_index in range(1, end_row + 1):
            if _string(sheet.getCellByPosition(27, row_index)) == automation_id:
                return row_index
        return None

    def apply_status(self, status: BackendStatus) -> bool:
        row_index = self._find_row_by_id(status.automation_id)
        if row_index is None:
            return False

        sheet = self._sheet()
        updates = {
            22: status.status,
            23: status.message,
            24: status.discount,
            25: status.last_checked_at,
            26: status.last_updated_at,
            28: status.external_id,
            29: status.last_published_url,
            30: status.data_signature,
        }
        for col, value in updates.items():
            sheet.getCellByPosition(col, row_index).String = str(value)
        return True

    def mark_saved(self) -> None:
        self._save_event.set()

    def consume_save_event(self) -> bool:
        if not self._save_event.is_set():
            return False
        self._save_event.clear()
        return True
