
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


def configure_catalog_sheet(sheet) -> None:
    for col, header in enumerate(ALL_HEADERS):
        sheet.getCellByPosition(col, 0).String = header

    for col in range(27, 34):
        sheet.Columns.getByIndex(col).IsVisible = False


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
        "private:factory/scalc",
        "_blank",
        0,
        (),
    )
    if document is None:
        raise RuntimeError("LibreOffice não criou o documento Calc.")

    sheets = document.Sheets
    first = sheets.getByIndex(0)
    first.Name = CATALOG_SHEET
    configure_catalog_sheet(first)

    store_props = (
        _property("FilterName", "calc8"),
        _property("Overwrite", True),
    )
    document.storeAsURL(target.as_uri(), store_props)
    return target
