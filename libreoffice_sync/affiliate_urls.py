from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class AffiliateUrlError(ValueError):
    pass


QUERY_MERGE_PARTNERS = {
    "Contingência Máxima": ("contingenciamaxima.com.br",),
}


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _validated_parts(value: str, field: str):
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError:
        raise AffiliateUrlError(f"{field} é inválido.") from None

    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host:
        raise AffiliateUrlError(f"{field} deve usar HTTPS.")
    return parsed, host


def compose_affiliate_url(
    product_url: str,
    affiliate_url: str,
    partner: str,
) -> str:
    domains = QUERY_MERGE_PARTNERS.get(partner)
    if not domains:
        return str(affiliate_url or "").strip()

    product, product_host = _validated_parts(product_url, "Link Produto")
    affiliate, affiliate_host = _validated_parts(
        affiliate_url,
        "Link Afiliado",
    )

    if not any(
        _host_matches(product_host, domain)
        and _host_matches(affiliate_host, domain)
        for domain in domains
    ):
        raise AffiliateUrlError(
            "Link Produto e Link Afiliado pertencem a domínios incompatíveis."
        )

    affiliate_pairs = parse_qsl(
        affiliate.query,
        keep_blank_values=True,
    )
    if not affiliate_pairs:
        raise AffiliateUrlError(
            "Link Afiliado não possui parâmetros para composição."
        )

    affiliate_keys = {key for key, _ in affiliate_pairs}
    product_pairs = [
        pair
        for pair in parse_qsl(product.query, keep_blank_values=True)
        if pair[0] not in affiliate_keys
    ]

    query = urlencode(
        [*product_pairs, *affiliate_pairs],
        doseq=True,
    )

    return urlunsplit(
        (
            product.scheme,
            product.netloc,
            product.path,
            query,
            product.fragment,
        )
    )
