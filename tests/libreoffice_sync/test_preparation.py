from dataclasses import replace

from libreoffice_sync.preparation import prepare_catalog_row


def test_afiliado_is_inferred_and_affiliate_link_is_composed(valid_row):
    raw = replace(
        valid_row,
        partner="",
        product_type="Digital",
        product_url=(
            "https://contingenciamaxima.com.br/"
            "produto/9b597da1-2d3a-47e5-86c6-5852f2c68000"
        ),
        affiliate_url="https://contingenciamaxima.com.br?ref=lukn",
    )

    prepared = prepare_catalog_row(raw)

    assert prepared.partner == "Afiliado"
    assert prepared.product_url == raw.product_url
    assert prepared.affiliate_url == raw.product_url + "?ref=lukn"
    assert raw.affiliate_url == "https://contingenciamaxima.com.br?ref=lukn"


def test_existing_partner_link_is_not_rewritten(valid_row):
    prepared = prepare_catalog_row(valid_row)
    assert prepared.affiliate_url == valid_row.affiliate_url
