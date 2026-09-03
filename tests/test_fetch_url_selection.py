from automation.models import ImportRecord
from automation.sync import _fetch_url


def _record(*, partner: str, product_url: str, affiliate_url: str) -> ImportRecord:
    row = [""] * 32
    row[0] = "test-automation-id"
    row[1] = "Sim"
    row[2] = "Sim"
    row[5] = "Automático"
    row[6] = product_url
    row[7] = affiliate_url
    row[8] = partner
    record, _ = ImportRecord.from_sheet_row(2, row)
    return record


def test_mercado_livre_fetch_prefers_direct_product_url_over_affiliate_shortlink():
    product_url = "https://produto.mercadolivre.com.br/MLB-1234567890-produto"
    affiliate_url = "https://meli.la/abc123"

    record = _record(
        partner="mercado_livre",
        product_url=product_url,
        affiliate_url=affiliate_url,
    )

    assert _fetch_url(record) == product_url
