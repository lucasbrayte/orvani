from __future__ import annotations

import csv
import io
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlsplit

SPREADSHEET_ID = "1oj0NbAkngUjjaYfJy5sEgzfDb7I0klHaUbvTzq6ZDB0"
CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    + SPREADSHEET_ID
    + "/gviz/tq?tqx=out:csv&sheet=Divulga%C3%A7%C3%A3o"
)
HEADERS = (
    "ID Divulgação", "ID Automação", "ID Externo", "Plataforma", "Nome",
    "Descrição Curta", "Preço", "Imagem", "Link Afiliado",
    "Status WhatsApp", "Criado em",
)
STATUSES = frozenset({"PENDENTE", "PUBLICADO", "ARQUIVADO"})
_SHARE_ID = re.compile(r"[0-9a-f]{32}")
_MAX_BODY = 2_000_000

class SourceError(RuntimeError):
    pass

@dataclass(frozen=True, slots=True)
class ShareItem:
    share_id: str
    automation_id: str
    external_id: str
    partner: str
    name: str
    description: str
    price: Decimal
    image_url: str
    affiliate_url: str
    backend_status: str
    created_at: str

    def as_dict(self, *, status=None, status_updated_at=""):
        effective = status or self.backend_status
        return {
            "id": self.share_id,
            "automationId": self.automation_id,
            "externalId": self.external_id,
            "partner": self.partner,
            "name": self.name,
            "description": self.description,
            "price": format_brl(self.price),
            "priceRaw": format(self.price, "f"),
            "image": self.image_url,
            "affiliateUrl": self.affiliate_url,
            "status": effective,
            "createdAt": self.created_at,
            "statusUpdatedAt": status_updated_at,
            "publication": publication_text(self),
        }

def _safe_https(value: str, field: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise SourceError(f"{field} inválido.")
    try:
        parsed = urlsplit(value)
    except Exception:
        raise SourceError(f"{field} inválido.") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port is not None
        or parsed.hostname.endswith(".")
    ):
        raise SourceError(f"{field} inválido.")
    return value

def _price(value: str) -> Decimal:
    raw = str(value).strip().replace("R$", "").replace(" ", "")
    if not raw:
        raise SourceError("Preço ausente.")
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        result = Decimal(raw)
    except InvalidOperation:
        raise SourceError("Preço inválido.") from None
    if not result.is_finite() or result <= 0:
        raise SourceError("Preço inválido.")
    return result

def parse_divulgation_csv(text: str) -> tuple[ShareItem, ...]:
    try:
        rows = list(csv.reader(io.StringIO(str(text))))
    except csv.Error:
        raise SourceError("CSV de Divulgação inválido.") from None
    if not rows or tuple(rows[0]) != HEADERS:
        raise SourceError("Cabeçalhos de Divulgação inválidos.")

    output = []
    seen = set()
    for row in rows[1:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) > len(HEADERS):
            raise SourceError("Linha de Divulgação inválida.")
        cells = row + [""] * (len(HEADERS) - len(row))
        share_id = cells[0].strip().lower()
        if not _SHARE_ID.fullmatch(share_id) or share_id in seen:
            raise SourceError("ID Divulgação inválido ou duplicado.")
        seen.add(share_id)
        status = cells[9].strip().upper() or "PENDENTE"
        if status not in STATUSES:
            raise SourceError("Status WhatsApp inválido.")
        name = cells[4].strip()
        if not name:
            raise SourceError("Nome de divulgação ausente.")
        output.append(ShareItem(
            share_id=share_id,
            automation_id=cells[1].strip(),
            external_id=cells[2].strip(),
            partner=cells[3].strip(),
            name=name,
            description=cells[5].strip(),
            price=_price(cells[6]),
            image_url=_safe_https(cells[7].strip(), "Imagem"),
            affiliate_url=_safe_https(cells[8].strip(), "Link Afiliado"),
            backend_status=status,
            created_at=cells[10].strip(),
        ))
    return tuple(output)

def fetch_items(*, url: str = CSV_URL, timeout: float = 12.0):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "OrvaniShareCenter/1.0",
            "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.1",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(_MAX_BODY + 1)
            if len(body) > _MAX_BODY:
                raise SourceError("Fila de Divulgação excedeu o limite.")
            charset = response.headers.get_content_charset() or "utf-8"
            text = body.decode(charset)
    except SourceError:
        raise
    except (urllib.error.URLError, TimeoutError, UnicodeError, OSError):
        raise SourceError("Fila backend ainda não está disponível.") from None
    return parse_divulgation_csv(text)

def format_brl(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole, fraction = f"{quantized:.2f}".split(".")
    groups = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    integer = ".".join(reversed(groups)) or "0"
    return f"R$ {integer},{fraction}"

def publication_text(item: ShareItem) -> str:
    parts = [f"🛍️ {item.name.strip()}"]
    if item.description.strip():
        parts.append(item.description.strip())
    parts.append(f"💰 {format_brl(item.price)}")
    parts.append("🔗 Confira na loja:\n" + item.affiliate_url)
    return "\n\n".join(parts)
