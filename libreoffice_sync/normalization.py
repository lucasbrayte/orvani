from __future__ import annotations

from dataclasses import replace
import unicodedata
from urllib.parse import urlsplit

from .models import CatalogRow


def _fold(value: str) -> str:
    text = unicodedata.normalize(
        "NFKD", str(value or "").strip().casefold()
    )
    return "".join(
        ch for ch in text if not unicodedata.combining(ch)
    )


def _canonical(
    value: str,
    mapping: dict[str, str],
    *,
    default: str = "",
) -> str:
    raw = str(value or "").strip()
    if not raw:
        return default
    return mapping.get(_fold(raw), raw)


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def infer_partner(*urls: str) -> str:
    for raw in urls:
        try:
            host = (
                urlsplit(str(raw or "").strip()).hostname or ""
            ).lower().rstrip(".")
        except ValueError:
            continue

        if not host:
            continue
        if (
            _host_matches(host, "mercadolivre.com.br")
            or _host_matches(host, "meli.la")
        ):
            return "Mercado Livre"
        if _host_matches(host, "shopee.com.br"):
            return "Shopee"
        if _host_matches(host, "shein.com"):
            return "SHEIN"
        if (
                _host_matches(host, "amazon.com.br")
                or _host_matches(host, "amzn.to")
                or _host_matches(host, "link.amazon")
        ):
            return "Amazon"
    return ""


def normalize_catalog_row(row: CatalogRow) -> CatalogRow:
    yes_no = {
        "sim": "Sim",
        "nao": "Não",
    }
    modes = {
        "automatico": "Automático",
        "manual": "Manual",
        "bloqueado": "Bloqueado",
    }
    partners = {
        "mercado livre": "Mercado Livre",
        "mercadolivre": "Mercado Livre",
        "shopee": "Shopee",
        "shein": "SHEIN",
        "amazon": "Amazon",
    }
    product_types = {
        "fisico": "Físico",
        "digital": "Digital",
    }

    partner = _canonical(row.partner, partners)
    allowed_partners = {"Mercado Livre", "Shopee", "SHEIN", "Amazon"}
    if partner not in allowed_partners:
        inferred = infer_partner(row.product_url, row.affiliate_url)
        if inferred:
            partner = inferred

    return replace(
        row,
        active=_canonical(row.active, yes_no),
        publish=_canonical(row.publish, yes_no),
        featured=_canonical(row.featured, yes_no),
        update_mode=_canonical(
            row.update_mode,
            modes,
            default="Automático",
        ),
        product_url=str(row.product_url or "").strip(),
        affiliate_url=str(row.affiliate_url or "").strip(),
        partner=partner,
        product_type=_canonical(row.product_type, product_types),
        button_text=str(row.button_text or "").strip(),
    )
