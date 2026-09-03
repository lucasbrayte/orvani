from __future__ import annotations

import hashlib
import json

from .models import CatalogRow


def editable_payload(row: CatalogRow) -> dict[str, object]:
    return {
        "ID Automação": row.automation_id,
        "Ativo": row.active,
        "Publicar": row.publish,
        "Destaque": row.featured,
        "Ordem": row.order,
        "Modo de Atualização": row.update_mode,
        "Link do Produto": row.product_url,
        "Link de Afiliado": row.affiliate_url,
        "Plataforma": row.partner,
        "Nome": row.name,
        "Descrição": row.description,
        "Categoria": row.category,
        "Subcategoria": row.subcategory,
        "Tipo": row.product_type,
        "Preço Atual": format(row.current_price, "f") if row.current_price is not None else "",
        "Preço Anterior": format(row.previous_price, "f") if row.previous_price is not None else "",
        "Cupom": row.coupon,
        "Validade do Cupom": row.coupon_expires_at,
        "Imagem 1": row.images[0],
        "Imagem 2": row.images[1],
        "Imagem 3": row.images[2],
        "Imagem 4": row.images[3],
        "Texto do Botão": row.button_text,
    }


def row_hash(row: CatalogRow) -> str:
    encoded = json.dumps(
        editable_payload(row),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
