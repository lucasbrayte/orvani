"""Validações de URL e DNS para entradas não confiáveis da automação."""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import UnsafeRedirectError, UnsafeUrlError


_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_AddressResolver = Callable[..., list[tuple[object, ...]]]
_UnsafeUrlType = type[UnsafeUrlError] | type[UnsafeRedirectError]


def _canonical_hostname(host: str) -> str:
    """Return a lowercase, ASCII hostname or raise ``ValueError``."""
    hostname = host.rstrip(".")
    if not hostname or len(hostname) > 253:
        raise ValueError("hostname ausente ou longo demais")
    try:
        encoded = hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise ValueError("hostname IDNA inválido") from error
    labels = encoded.split(".")
    if any(not _HOST_LABEL.fullmatch(label) for label in labels):
        raise ValueError("hostname inválido")
    return encoded


def is_allowed_host(host: str, allowed_hosts: Iterable[str]) -> bool:
    """Whether *host* is an explicit partner host or one of its subdomains."""
    try:
        candidate = _canonical_hostname(host)
    except (TypeError, ValueError):
        return False
    for allowed_host in allowed_hosts:
        try:
            allowed = _canonical_hostname(allowed_host)
        except (TypeError, ValueError):
            continue
        if candidate == allowed or candidate.endswith(f".{allowed}"):
            return True
    return False


def validate_https_url(
    url: str,
    allowed_hosts: Iterable[str],
    *,
    error_type: _UnsafeUrlType = UnsafeUrlError,
) -> None:
    """Reject a URL unless it is a safe HTTPS URL for the given partner."""
    try:
        if not isinstance(url, str) or not url or "\\" in url or any(char.isspace() for char in url):
            raise ValueError("formato de URL inseguro")
        parsed = urlsplit(url)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValueError("HTTPS obrigatório")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("credenciais não são permitidas")
        if parsed.port not in (None, 443):
            raise ValueError("porta não permitida")
        hostname = parsed.hostname
        if hostname is None:
            raise ValueError("hostname ausente")
        _canonical_hostname(hostname)
        if not is_allowed_host(hostname, allowed_hosts):
            raise ValueError("hostname fora da allowlist")
    except (TypeError, ValueError) as error:
        raise error_type("URL insegura.") from error


def resolve_public_addresses(
    host: str,
    *,
    resolver: _AddressResolver = socket.getaddrinfo,
) -> tuple[str, ...]:
    """Resolve *host* only when every DNS result is globally routable."""
    try:
        answers = resolver(host, 443, 0, socket.SOCK_STREAM)
        addresses = tuple(answer[4][0] for answer in answers)
        if not addresses:
            raise ValueError("DNS sem respostas")
        parsed_addresses = tuple(ipaddress.ip_address(address) for address in addresses)
        if any(
            not address.is_global
            or address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
            for address in parsed_addresses
        ):
            raise ValueError("DNS retornou endereço não global")
    except (OSError, TypeError, ValueError) as error:
        raise UnsafeUrlError("Resolução DNS insegura.") from error
    return tuple(str(address) for address in parsed_addresses)


def normalize_url_for_signature(url: str) -> str:
    """Create a stable URL representation for deterministic signatures."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        if hostname is None:
            raise ValueError("hostname ausente")
        host = _canonical_hostname(hostname)
        if ":" in host:
            host = f"[{host}]"
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
        return urlunsplit((parsed.scheme.lower(), host, parsed.path, query, ""))
    except (TypeError, ValueError) as error:
        raise UnsafeUrlError("URL inválida para assinatura.") from error


def sanitize_url_for_log(url: str) -> str:
    """Return a URL-shaped log value without credentials, path, query, or fragment."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        if hostname is None:
            raise ValueError("hostname ausente")
        host = _canonical_hostname(hostname)
        if ":" in host:
            host = f"[{host}]"
        scheme = parsed.scheme.lower() or "url"
        suffix = "/" if parsed.path in ("", "/") else "/[path]"
        return f"{scheme}://{host}{suffix}"
    except (TypeError, ValueError):
        return "[invalid-url]"
