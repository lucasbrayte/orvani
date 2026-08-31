"""Cliente HTTP limitado para consultar somente páginas públicas autorizadas."""

from __future__ import annotations

import re
import socket
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
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
from .security import is_allowed_host, resolve_public_addresses, validate_https_url


_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
_BLOCKED_STATUS_CODES = {401, 403, 407}
_NOT_FOUND_STATUS_CODES = {404, 410}
_TEMPORARY_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
_BACKOFF_SECONDS = (0.5, 1.0)
_REQUEST_TIMEOUT = httpx.Timeout(
    connect=CONNECT_TIMEOUT_SECONDS,
    read=READ_TIMEOUT_SECONDS,
    write=READ_TIMEOUT_SECONDS,
    pool=CONNECT_TIMEOUT_SECONDS,
)
_RedirectHostPolicy = Callable[[str], bool]
_GOOGLE_SHEETS_EXPORT_REDIRECT_HOST = re.compile(
    r"doc-[a-z0-9](?:[a-z0-9-]{0,50}[a-z0-9])?-sheets\.googleusercontent\.com\Z"
)


def google_sheets_export_redirect_host(host: str) -> bool:
    """Allow only a bounded terminal host used by the fixed Sheets CSV export."""
    return isinstance(host, str) and _GOOGLE_SHEETS_EXPORT_REDIRECT_HOST.fullmatch(host) is not None


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


class _BorrowedTransport(httpx.BaseTransport):
    """Delegate requests without taking ownership of an injected transport."""

    def __init__(self, transport: httpx.BaseTransport) -> None:
        self._transport = transport

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self._transport.handle_request(request)

    def close(self) -> None:
        """The caller, not the safe wrapper, owns the wrapped transport."""


class SafeHttpClient:
    """Fetch allowed HTTPS URLs without automatic redirects or unbounded bodies."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        dns_resolver: Callable[..., list[tuple[object, ...]]] = socket.getaddrinfo,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if client is not None and transport is not None:
            raise ValueError("Use client ou transport, não ambos.")
        if client is not None:
            transport = _borrowed_client_transport(client)
        elif transport is not None:
            transport = _BorrowedTransport(transport)
        self._client = httpx.Client(
            transport=transport,
            follow_redirects=False,
            headers={"User-Agent": "Orvani affiliate catalog automation/1.0"},
            timeout=_REQUEST_TIMEOUT,
            trust_env=False,
        )
        self._dns_resolver = dns_resolver
        self._sleep = sleep

    def close(self) -> None:
        """Close the isolated client without closing a caller-owned transport."""
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
        *,
        redirect_host_policy: _RedirectHostPolicy | None = None,
    ) -> HttpResponse:
        """Return a safe response or a typed error for an expected fetch failure."""
        allowed_hosts = tuple(allowed_hosts)
        expected_content_types = tuple(_normalize_media_type(value) for value in expected_content_types)

        for attempt in range(RETRIES + 1):
            try:
                return self._get_once(
                    url,
                    allowed_hosts,
                    expected_content_types,
                    redirect_host_policy=redirect_host_policy,
                )
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
        *,
        redirect_host_policy: _RedirectHostPolicy | None,
    ) -> HttpResponse:
        current_url = url
        redirect_count = 0

        while True:
            self._validate_request_url(
                current_url,
                allowed_hosts,
                redirected=redirect_count > 0,
                redirect_host_policy=redirect_host_policy,
            )
            try:
                with self._cookie_free_stream(current_url) as response:
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
        redirect_host_policy: _RedirectHostPolicy | None,
    ) -> None:
        error_type = UnsafeRedirectError if redirected else UnsafeUrlError
        try:
            host = urlsplit(url).hostname
        except (TypeError, ValueError) as error:
            raise error_type("URL insegura.") from error
        if host is None:
            raise error_type("URL insegura.")
        validate_https_url(url, (host,), error_type=error_type)
        if not is_allowed_host(host, allowed_hosts) and not _redirect_host_is_allowed(
            host,
            redirected=redirected,
            redirect_host_policy=redirect_host_policy,
        ):
            raise error_type("URL insegura.")
        try:
            resolve_public_addresses(host, resolver=self._dns_resolver)
        except UnsafeUrlError as error:
            if redirected:
                raise UnsafeRedirectError("Redirecionamento com DNS inseguro.") from error
            raise

    def _build_cookie_free_request(self, url: str) -> httpx.Response:
        request = self._client.build_request("GET", url, timeout=_REQUEST_TIMEOUT)
        request.headers.pop("cookie", None)
        return self._client.send(request, stream=True, follow_redirects=False)

    @contextmanager
    def _cookie_free_stream(self, url: str) -> Iterator[httpx.Response]:
        response = self._build_cookie_free_request(url)
        try:
            yield response
        finally:
            response.close()

    @staticmethod
    def _next_redirect_url(response: httpx.Response, current_url: str, redirect_count: int) -> str:
        if redirect_count >= REDIRECT_LIMIT:
            raise UnsafeRedirectError("Limite de redirecionamentos excedido.")
        location = response.headers.get("location")
        if not location:
            raise UnsafeRedirectError("Redirecionamento sem destino.")
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


def _redirect_host_is_allowed(
    host: str,
    *,
    redirected: bool,
    redirect_host_policy: _RedirectHostPolicy | None,
) -> bool:
    if not redirected or redirect_host_policy is None:
        return False
    try:
        return redirect_host_policy(host)
    except Exception:
        return False


def _borrowed_client_transport(client: httpx.Client) -> httpx.BaseTransport:
    """Create an owned client boundary over an HTTPX client's base transport.

    HTTPX exposes no public transport accessor. This compatibility path reads
    only the base transport, never sends through or changes the injected client.
    New callers can inject ``transport`` directly.
    """
    transport = getattr(client, "_transport", None)
    if not isinstance(transport, httpx.BaseTransport):
        raise ValueError("Cliente HTTP sem transporte compatível.")
    return _BorrowedTransport(transport)


def _read_bounded_body(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > BODY_LIMIT_BYTES:
            raise ResponseTooLargeError("Resposta excede o limite de 2 MB.")
        chunks.append(chunk)
    return b"".join(chunks)
