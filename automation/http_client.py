"""Cliente HTTP limitado para consultar somente páginas públicas autorizadas."""

from __future__ import annotations

import socket
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from .config import (
    BODY_LIMIT_BYTES,
    CONNECT_TIMEOUT_SECONDS,
    READ_TIMEOUT_SECONDS,
    REDIRECT_LIMIT,
    RETRIES,
)
from .models import (
    BlockedByStoreError,
    ConnectorError,
    ProductNotFoundError,
    ResponseTooLargeError,
    TemporaryFetchError,
    UnexpectedContentTypeError,
    UnsafeRedirectError,
    UnsafeUrlError,
)
from .security import resolve_public_addresses, validate_https_url


_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
_BLOCKED_STATUS_CODES = {401, 403, 407}
_NOT_FOUND_STATUS_CODES = {404, 410}
_TEMPORARY_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
_BACKOFF_SECONDS = (0.5, 1.0)


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """A successful, bounded HTTP response with a normalized media type."""

    url: str
    status_code: int
    media_type: str
    body: bytes

    @property
    def content(self) -> bytes:
        """Compatibility alias for callers that use HTTPX's response vocabulary."""
        return self.body


class SafeHttpClient:
    """Fetch allowed HTTPS URLs without automatic redirects or unbounded bodies."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        dns_resolver: Callable[..., list[tuple[object, ...]]] = socket.getaddrinfo,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client or httpx.Client(
            follow_redirects=False,
            headers={"User-Agent": "Orvani affiliate catalog automation/1.0"},
            timeout=httpx.Timeout(
                connect=CONNECT_TIMEOUT_SECONDS,
                read=READ_TIMEOUT_SECONDS,
                write=READ_TIMEOUT_SECONDS,
                pool=CONNECT_TIMEOUT_SECONDS,
            ),
        )
        self._dns_resolver = dns_resolver
        self._sleep = sleep

    def close(self) -> None:
        """Close the underlying client, including one injected by a caller."""
        self._client.close()

    def __enter__(self) -> "SafeHttpClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def get(
        self,
        url: str,
        allowed_hosts: Iterable[str],
        expected_content_types: Iterable[str],
    ) -> HttpResponse:
        """Return a safe response or a typed error for an expected fetch failure."""
        allowed_hosts = tuple(allowed_hosts)
        expected_content_types = tuple(_normalize_media_type(value) for value in expected_content_types)

        for attempt in range(RETRIES + 1):
            try:
                return self._get_once(url, allowed_hosts, expected_content_types)
            except TemporaryFetchError:
                if attempt == RETRIES:
                    raise
                self._sleep(_BACKOFF_SECONDS[attempt])
        raise AssertionError("tentativas HTTP esgotadas sem resultado")

    def _get_once(
        self,
        url: str,
        allowed_hosts: tuple[str, ...],
        expected_content_types: tuple[str, ...],
    ) -> HttpResponse:
        current_url = url
        redirect_count = 0

        while True:
            self._validate_request_url(
                current_url,
                allowed_hosts,
                redirected=redirect_count > 0,
            )
            try:
                with self._client.stream("GET", current_url) as response:
                    if response.status_code in _REDIRECT_STATUS_CODES:
                        current_url = self._next_redirect_url(response, current_url, redirect_count)
                        redirect_count += 1
                        continue
                    self._raise_for_status(response.status_code)
                    media_type = _normalize_media_type(response.headers.get("content-type", ""))
                    if media_type not in expected_content_types:
                        raise UnexpectedContentTypeError("Tipo de conteúdo inesperado.")
                    return HttpResponse(
                        url=current_url,
                        status_code=response.status_code,
                        media_type=media_type,
                        body=_read_bounded_body(response),
                    )
            except httpx.TimeoutException as error:
                raise TemporaryFetchError("Tempo de consulta esgotado.") from error

    def _validate_request_url(
        self,
        url: str,
        allowed_hosts: tuple[str, ...],
        *,
        redirected: bool,
    ) -> None:
        error_type = UnsafeRedirectError if redirected else UnsafeUrlError
        validate_https_url(url, allowed_hosts, error_type=error_type)
        host = urlsplit(url).hostname
        if host is None:
            raise error_type("URL insegura.")
        try:
            resolve_public_addresses(host, resolver=self._dns_resolver)
        except UnsafeUrlError as error:
            if redirected:
                raise UnsafeRedirectError("Redirecionamento com DNS inseguro.") from error
            raise

    @staticmethod
    def _next_redirect_url(response: httpx.Response, current_url: str, redirect_count: int) -> str:
        if redirect_count >= REDIRECT_LIMIT:
            raise UnsafeRedirectError("Limite de redirecionamentos excedido.")
        location = response.headers.get("location")
        if not location:
            raise ConnectorError("Redirecionamento sem destino.")
        return urljoin(current_url, location)

    @staticmethod
    def _raise_for_status(status_code: int) -> None:
        if status_code in _BLOCKED_STATUS_CODES:
            raise BlockedByStoreError("A loja bloqueou a consulta pública.")
        if status_code in _NOT_FOUND_STATUS_CODES:
            raise ProductNotFoundError("Produto não encontrado.")
        if status_code in _TEMPORARY_STATUS_CODES:
            raise TemporaryFetchError("Falha temporária ao consultar a loja.")
        if not 200 <= status_code < 300:
            raise ConnectorError("Resposta HTTP não suportada.")


def _normalize_media_type(value: str) -> str:
    return value.split(";", maxsplit=1)[0].strip().lower()


def _read_bounded_body(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > BODY_LIMIT_BYTES:
            raise ResponseTooLargeError("Resposta excede o limite de 2 MB.")
        chunks.append(chunk)
    return b"".join(chunks)
