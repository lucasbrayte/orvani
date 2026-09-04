
from __future__ import annotations

from pathlib import Path

from .uno_client import LibreOfficeWorkbook
from .workbook_schema import CATALOG_SHEET


ALL_HEADERS = (
    "Ativo", "Publicar", "Destaque", "Ordem", "Modo Atualização",
    "Link Produto", "Link Afiliado", "Plataforma", "Nome", "Descrição",
    "Categoria", "Subcategoria", "Tipo", "Preço Atual", "Preço Anterior",
    "Cupom", "Validade Cupom", "Imagem 1", "Imagem 2", "Imagem 3",
    "Imagem 4", "Texto Botão", "Status", "Mensagem", "Desconto",
    "Última Verificação", "Última Atualização", "ID Automação", "ID Externo",
    "Último Link Publicado", "Assinatura", "Última Sincronização Local",
    "Hash da Linha", "Hash Confirmado",
)


def _list_validation(range_obj, values: tuple[str, ...]) -> None:
    validation = range_obj.Validation
    try:
        import uno  # type: ignore
        validation.Type = uno.getConstantByName(
            "com.sun.star.sheet.ValidationType.LIST"
        )
    except Exception:
        validation.Type = "LIST"
    # Cada entrada precisa ser uma string explícita na fórmula.
    # Sem aspas, valores com espaço (ex.: Mercado Livre) podem ser
    # interpretados como tokens separados pelo Calc.
    escaped = tuple(value.replace('"', '""') for value in values)
    validation.Formula1 = ";".join(f'"{value}"' for value in escaped)
    validation.ShowErrorMessage = True
    validation.ErrorMessage = "Selecione um valor permitido."
    range_obj.Validation = validation


_WRAPPED_TEXT_COLUMNS = (5, 6, 8, 9, 17, 18, 19, 20, 21, 23)
_DATA_ROW_HEIGHT = 700
_FIRST_DATA_ROW_INDEX = 1
_LAST_DATA_ROW_INDEX = 1999


def _apply_text_layout(sheet) -> None:
    if hasattr(sheet, "getCellRangeByPosition"):
        for col in _WRAPPED_TEXT_COLUMNS:
            try:
                sheet.getCellRangeByPosition(
                    col,
                    _FIRST_DATA_ROW_INDEX,
                    col,
                    _LAST_DATA_ROW_INDEX,
                ).IsTextWrapped = True
            except Exception:
                pass

    if hasattr(sheet, "Rows"):
        for row_index in range(
            _FIRST_DATA_ROW_INDEX,
            _LAST_DATA_ROW_INDEX + 1,
        ):
            try:
                row = sheet.Rows.getByIndex(row_index)
                row.OptimalHeight = False
                row.Height = _DATA_ROW_HEIGHT
            except Exception:
                pass


def configure_catalog_sheet(sheet) -> None:
    for col, header in enumerate(ALL_HEADERS):
        sheet.getCellByPosition(col, 0).String = header

    for col in range(27, 34):
        sheet.Columns.getByIndex(col).IsVisible = False

    widths = {
        5: 7000, 6: 7000, 8: 5500, 9: 10000,
        10: 4200, 11: 4200, 17: 7000, 18: 7000,
        19: 7000, 20: 7000, 22: 3500, 23: 8000,
    }
    for col, width in widths.items():
        try:
            sheet.Columns.getByIndex(col).Width = width
        except Exception:
            pass

    _apply_text_layout(sheet)

    # Compatibilidade com os fakes unitários antigos:
    # em LibreOffice real este método existe; em fakes mínimos ele pode não existir.
    if hasattr(sheet, "getCellRangeByPosition"):
        _list_validation(
            sheet.getCellRangeByPosition(0, 1, 0, 1999), ("Sim", "Não")
        )
        _list_validation(
            sheet.getCellRangeByPosition(1, 1, 1, 1999), ("Sim", "Não")
        )
        _list_validation(
            sheet.getCellRangeByPosition(2, 1, 2, 1999), ("Sim", "Não")
        )
        _list_validation(
            sheet.getCellRangeByPosition(4, 1, 4, 1999),
            ("Automático", "Manual", "Bloqueado"),
        )
        _list_validation(
            sheet.getCellRangeByPosition(7, 1, 7, 1999),
            ("Mercado Livre", "Shopee", "SHEIN", "Amazon"),
        )
        _list_validation(
            sheet.getCellRangeByPosition(12, 1, 12, 1999),
            ("Físico", "Digital"),
        )


def _apply_price_format(document, sheet) -> None:
    try:
        import uno  # type: ignore
        locale = uno.createUnoStruct("com.sun.star.lang.Locale")
        locale.Language = "pt"
        locale.Country = "BR"
        formats = document.NumberFormats
        key = formats.queryKey("R$ #,##0.00", locale, True)
        if key == -1:
            key = formats.addNew("R$ #,##0.00", locale)
        sheet.getCellRangeByPosition(13, 1, 14, 1999).NumberFormat = key
    except Exception:
        pass


def initialize_document(document) -> None:
    sheets = document.Sheets
    if sheets.hasByName(CATALOG_SHEET):
        sheet = sheets.getByName(CATALOG_SHEET)
    else:
        sheet = sheets.getByIndex(0)
        sheet.Name = CATALOG_SHEET

    configure_catalog_sheet(sheet)

    try:
        document.getCurrentController().freezeAtPosition(0, 1)
    except Exception:
        pass

    _apply_price_format(document, sheet)


def _property(name, value):
    import uno  # type: ignore
    prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    prop.Name = name
    prop.Value = value
    return prop


def initialize_workbook(
    path: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 2002,
) -> Path:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    connection = LibreOfficeWorkbook.connect(host=host, port=port)
    desktop = connection.desktop
    if desktop is None:
        raise RuntimeError("Não foi possível obter o Desktop do LibreOffice.")

    document = desktop.loadComponentFromURL(
        "private:factory/scalc", "_blank", 0, ()
    )
    if document is None:
        raise RuntimeError("LibreOffice não criou o documento Calc.")

    initialize_document(document)
    document.storeAsURL(
        target.as_uri(),
        (_property("FilterName", "calc8"), _property("Overwrite", True)),
    )
    return target
