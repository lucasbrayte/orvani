import pytest

from libreoffice_sync.affiliate_urls import (
    AffiliateUrlError,
    compose_affiliate_url,
)


PARTNER = "Contingência Máxima"


def test_query_merge_adds_affiliate_parameter_to_product_path():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123",
        "https://contingenciamaxima.com.br?ref=lukn",
        PARTNER,
    )
    assert result == (
        "https://contingenciamaxima.com.br/produto/123?ref=lukn"
    )


def test_query_merge_preserves_product_only_parameters():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123?cor=azul",
        "https://contingenciamaxima.com.br?ref=lukn",
        PARTNER,
    )
    assert result.endswith("?cor=azul&ref=lukn")


def test_affiliate_parameter_overrides_product_parameter():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123?ref=antigo&cor=azul",
        "https://contingenciamaxima.com.br?ref=lukn",
        PARTNER,
    )
    assert result.endswith("?cor=azul&ref=lukn")


def test_duplicate_affiliate_values_are_preserved():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123",
        "https://contingenciamaxima.com.br?tag=a&tag=b",
        PARTNER,
    )
    assert result.endswith("?tag=a&tag=b")


def test_percent_encoded_values_are_round_tripped_safely():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123?q=fone%20azul",
        "https://contingenciamaxima.com.br?ref=lucas%2Bteste",
        PARTNER,
    )
    assert "q=fone+azul" in result
    assert "ref=lucas%2Bteste" in result


def test_product_fragment_is_preserved():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123#detalhes",
        "https://contingenciamaxima.com.br?ref=lukn",
        PARTNER,
    )
    assert result.endswith("?ref=lukn#detalhes")


@pytest.mark.parametrize(
    ("product_url", "affiliate_url", "message"),
    [
        (
            "http://contingenciamaxima.com.br/produto/123",
            "https://contingenciamaxima.com.br?ref=lukn",
            "HTTPS",
        ),
        (
            "https://contingenciamaxima.com.br/produto/123",
            "https://outra-loja.example?ref=lukn",
            "incompatíveis",
        ),
        (
            "https://contingenciamaxima.com.br/produto/123",
            "https://contingenciamaxima.com.br",
            "parâmetros",
        ),
    ],
)
def test_query_merge_fails_closed(product_url, affiliate_url, message):
    with pytest.raises(AffiliateUrlError, match=message):
        compose_affiliate_url(product_url, affiliate_url, PARTNER)
