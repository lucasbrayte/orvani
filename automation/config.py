"""Constantes seguras e configuração da automação."""

from __future__ import annotations

import json
import os
import unicodedata
from dataclasses import dataclass
from typing import Mapping

from .models import ConfigurationError

SPREADSHEET_ID = "1oj0NbAkngUjjaYfJy5sEgzfDb7I0klHaUbvTzq6ZDB0"
IMPORT_WORKSHEET = "Importações"
PRODUCTS_WORKSHEET = "Produtos"
PRODUCTS_HEADER_ROW = 4

PRODUCTS_HEADERS = (
    "Ativo *", "Tipo", "Plataforma", "Categoria", "Subcategoria", "Nome",
    "Descrição", "Preço *", "Preço Promocional", "Cupom", "Validade da oferta",
    "Link de Afiliado", "Texto do Botão", "Vídeo (URL YouTube)", "Imagem 1 *",
    "Imagem 2", "Imagem 3", "Imagem 4", "Ordem", "Destaque",
)
IMPORT_HEADERS = (
    "ID Automação", "Ativo", "Publicar", "Destaque", "Ordem", "Modo de Atualização",
    "Link do Produto", "Link de Afiliado", "Plataforma", "ID Externo", "Nome",
    "Descrição", "Categoria", "Subcategoria", "Tipo", "Preço Atual", "Preço Anterior",
    "Desconto Calculado", "Cupom", "Validade do Cupom", "Imagem 1", "Imagem 2",
    "Imagem 3", "Imagem 4", "Texto do Botão", "Status", "Mensagem",
    "Tentativas Consecutivas", "Último Link Publicado", "Assinatura dos Dados",
    "Última Verificação", "Última Atualização",
)

CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 15
REDIRECT_LIMIT = 5
BODY_LIMIT_BYTES = 2_000_000
RETRIES = 2
DESCRIPTION_LIMIT = 4_000
IMAGE_LIMIT = 4
CATALOG_CURRENCY = "BRL"
MERCADO_LIVRE_API_ALLOWED_HOSTS = ("api.mercadolibre.com",)


def normalize_unicode_text(value: object | None) -> str:
    """Normaliza Unicode e espaços para comparações determinísticas."""
    text = unicodedata.normalize("NFKC", "" if value is None else str(value))
    return " ".join(text.split())


def normalize_category_key(value: object | None) -> str:
    return normalize_unicode_text(value).casefold()


# These approved catalog labels remain the only automatic category outputs.
CATEGORY_SOURCE_MAPPINGS: Mapping[str, tuple[str, str | None]] = {
    "eletrônicos > áudio": ("Eletrônicos", "Áudio"),
    "eletronicos > audio": ("Eletrônicos", "Áudio"),
    "eletrônicos > acessórios": ("Eletrônicos", "Acessórios"),
    "eletronicos > acessorios": ("Eletrônicos", "Acessórios"),
    "moda > roupas": ("Moda", "Roupas"),
    "moda > bolsas e acessórios": ("Moda", "Bolsas e Acessórios"),
    "casa > iluminação": ("Casa", "Iluminação"),
    "casa > organização": ("Casa", "Organização"),
}
CATEGORY_FIRST_SEGMENTS: Mapping[str, str] = {
    "eletrônicos": "Eletrônicos",
    "eletronicos": "Eletrônicos",
    "moda": "Moda",
    "casa": "Casa",
}
CATEGORY_KEYWORDS: tuple[tuple[str, str, str | None], ...] = (
    ("fone", "Eletrônicos", "Áudio"),
    ("fones", "Eletrônicos", "Áudio"),
    ("headphone", "Eletrônicos", "Áudio"),
    ("teclado", "Eletrônicos", "Acessórios"),
    ("camisa", "Moda", "Roupas"),
    ("jaqueta", "Moda", "Roupas"),
    ("mochila", "Moda", "Bolsas e Acessórios"),
    ("luminária", "Casa", "Iluminação"),
    ("luminaria", "Casa", "Iluminação"),
)


@dataclass(frozen=True, slots=True)
class PartnerConfig:
    key: str
    display_name: str
    allowed_hosts: tuple[str, ...]
    live_verified: bool


PARTNERS: Mapping[str, PartnerConfig] = {
    "mercado_livre": PartnerConfig(
        "mercado_livre", "Mercado Livre", ("mercadolivre.com.br", "meli.la"), True
    ),
    "shopee": PartnerConfig("shopee", "Shopee", ("shopee.com.br", "s.shopee.com.br"), True),
    "shein": PartnerConfig(
        "shein", "SHEIN", ("shein.com", "br.shein.com", "onelink.shein.com"), False
    ),
    "tiktok_shop": PartnerConfig("tiktok_shop", "TikTok Shop", (), False),
}


@dataclass(frozen=True, slots=True)
class Settings:
    service_account_info: Mapping[str, object]
    spreadsheet_id: str = SPREADSHEET_ID
    import_worksheet: str = IMPORT_WORKSHEET
    products_worksheet: str = PRODUCTS_WORKSHEET

    @classmethod
    def from_env(cls) -> "Settings":
        raw_service_account = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not raw_service_account:
            raise ConfigurationError("GOOGLE_SERVICE_ACCOUNT_JSON não configurado.")
        try:
            service_account_info = json.loads(raw_service_account)
        except json.JSONDecodeError as error:
            raise ConfigurationError("GOOGLE_SERVICE_ACCOUNT_JSON inválido.") from error
        if not isinstance(service_account_info, dict):
            raise ConfigurationError("GOOGLE_SERVICE_ACCOUNT_JSON deve ser um objeto JSON.")
        requested_spreadsheet_id = os.environ.get("ORVANI_SPREADSHEET_ID")
        if requested_spreadsheet_id is not None and requested_spreadsheet_id != SPREADSHEET_ID:
            raise ConfigurationError("ORVANI_SPREADSHEET_ID não é permitido.")
        return cls(
            service_account_info=service_account_info,
            spreadsheet_id=SPREADSHEET_ID,
            import_worksheet=os.environ.get("ORVANI_IMPORT_WORKSHEET", IMPORT_WORKSHEET),
            products_worksheet=os.environ.get("ORVANI_PRODUCTS_WORKSHEET", PRODUCTS_WORKSHEET),
        )
