import socket

import pytest

from automation.models import UnsafeRedirectError, UnsafeUrlError
from automation.security import (
    is_allowed_host,
    normalize_url_for_signature,
    resolve_public_addresses,
    sanitize_url_for_log,
    validate_https_url,
)


ALLOWED_MERCADO_LIVRE = ("mercadolivre.com.br", "meli.la")


@pytest.mark.parametrize("url", [
    "http://www.mercadolivre.com.br/item",
    "https://user:secret@www.mercadolivre.com.br/item",
    "https://www.mercadolivre.com.br:444/item",
    "https://www.mercadolivre.com.br\\@evil.example/item",
    "https://www.mercadolivre.com.br/item with-space",
    "https://foo..mercadolivre.com.br/item",
])
def test_rejects_unsafe_url_shapes(url):
    # Removing any parsing rule above must reject this untrusted spreadsheet input.
    with pytest.raises(UnsafeUrlError):
        validate_https_url(url, ALLOWED_MERCADO_LIVRE)


@pytest.mark.parametrize("url", [
    "https://WWW.MERCADOLIVRE.COM.BR./item/MLB123",
    "https://WWW.MERCADOLIVRE.COM.BR../item/MLB123",
])
def test_rejects_trailing_dot_hostname_in_validation_and_signature_normalization(url):

    with pytest.raises(UnsafeUrlError):
        validate_https_url(url, ALLOWED_MERCADO_LIVRE)
    with pytest.raises(UnsafeUrlError):
        normalize_url_for_signature(url)


def test_rejects_an_invalid_idna_hostname():
    url = "https://" + chr(0xD800) + ".mercadolivre.com.br/item"

    with pytest.raises(UnsafeUrlError):
        validate_https_url(url, ALLOWED_MERCADO_LIVRE)


@pytest.mark.parametrize(("host", "allowed", "expected"), [
    ("mercadolivre.com.br", ALLOWED_MERCADO_LIVRE, True),
    ("www.mercadolivre.com.br", ALLOWED_MERCADO_LIVRE, True),
    ("MELI.LA.", ALLOWED_MERCADO_LIVRE, False),
    ("mercadolivre.com.br.evil.example", ALLOWED_MERCADO_LIVRE, False),
    ("evilmercadolivre.com.br", ALLOWED_MERCADO_LIVRE, False),
    ("mercadolivre..com.br", ALLOWED_MERCADO_LIVRE, False),
    ("", ALLOWED_MERCADO_LIVRE, False),
])
def test_matches_only_exact_partner_hosts_or_their_subdomains(host, allowed, expected):
    assert is_allowed_host(host, allowed) is expected


def test_can_raise_redirect_error_for_an_unsafe_redirect_url():
    with pytest.raises(UnsafeRedirectError):
        validate_https_url(
            "https://evil.example/item",
            ALLOWED_MERCADO_LIVRE,
            error_type=UnsafeRedirectError,
        )


def _resolver_for(*addresses):
    def resolver(*_args):
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, 443, 0, 0) if ":" in address else (address, 443),
            )
            for address in addresses
        ]

    return resolver


def test_resolves_only_global_dns_answers():
    addresses = resolve_public_addresses(
        "example.com", resolver=_resolver_for("8.8.8.8", "2606:4700:4700::1111")
    )

    assert addresses == ("8.8.8.8", "2606:4700:4700::1111")


@pytest.mark.parametrize("address", [
    "127.0.0.1",
    "169.254.1.1",
    "224.0.0.1",
    "240.0.0.1",
    "0.0.0.0",
    "::1",
    "::",
    "fe80::1",
    "fec0::1",
    "ff02::1",
    "2001:db8::1",
])
def test_rejects_non_global_dns_answers(address):
    # Returning a non-global address must block SSRF before any connection happens.
    with pytest.raises(UnsafeUrlError):
        resolve_public_addresses("example.com", resolver=_resolver_for(address))


def test_rejects_private_dns_answer():
    resolver = lambda *args: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))
    ]
    with pytest.raises(UnsafeUrlError):
        resolve_public_addresses("example.com", resolver=resolver)


def test_rejects_a_mixed_global_and_private_dns_answer():
    with pytest.raises(UnsafeUrlError):
        resolve_public_addresses(
            "example.com", resolver=_resolver_for("8.8.8.8", "10.0.0.8")
        )


def test_normalizes_signature_url_with_sorted_blank_query_values_and_no_fragment():
    normalized = normalize_url_for_signature(
        "HTTPS://S.SHOPEE.COM.BR/AbCd?z=last&a=&a=one#affiliate-fragment"
    )

    assert normalized == "https://s.shopee.com.br/AbCd?a=&a=one&z=last"


def test_sanitizes_tracking_url():
    safe = sanitize_url_for_log("https://s.shopee.com.br/AbCd?affiliate_id=secret#fragment")
    assert safe == "https://s.shopee.com.br/[path]"
    assert "secret" not in safe


def test_sanitizes_root_url_without_credentials_or_tracking_details():
    safe = sanitize_url_for_log("https://user:secret@s.shopee.com.br/?affiliate_id=token#fragment")

    assert safe == "https://s.shopee.com.br/"
    for sensitive_value in ("user", "secret", "token", "fragment"):
        assert sensitive_value not in safe
