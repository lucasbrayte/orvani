from collections import Counter
import socket

import httpx
import pytest

from automation.config import BODY_LIMIT_BYTES
from automation.http_client import (
    HttpResponse,
    SafeHttpClient,
    google_sheets_export_redirect_host,
)
from automation.models import (
    BlockedByStoreError,
    ProductNotFoundError,
    ResponseTooLargeError,
    TemporaryFetchError,
    UnexpectedContentTypeError,
    UnsafeRedirectError,
    UnsafeUrlError,
)


def test_returns_bounded_html_response_with_normalized_media_type(http_client_factory):
    client, _calls = http_client_factory({
        "https://example.com/item": (200, {"content-type": "Text/HTML; charset=utf-8"}, b"<h1>Produto</h1>"),
    })

    response = client.get("https://example.com/item", ("example.com",), ("text/html",))

    assert response == HttpResponse(
        url="https://example.com/item",
        status_code=200,
        media_type="text/html",
        body=b"<h1>Produto</h1>",
    )


def test_follows_allowed_relative_redirect_after_validating_each_request(http_client_factory):
    client, calls = http_client_factory({
        "https://meli.la/a": (302, {"location": "/item"}, b""),
        "https://meli.la/item": (200, {"content-type": "text/html"}, b"ok"),
    })

    response = client.get("https://meli.la/a", ("meli.la", "mercadolivre.com.br"), ("text/html",))

    assert response.url == "https://meli.la/item"
    assert calls == Counter({"https://meli.la/a": 1, "https://meli.la/item": 1})


def test_validates_every_redirect(http_client_factory):
    client, calls = http_client_factory({
        "https://meli.la/a": (302, {"location": "https://evil.example/item"}, b""),
    })

    with pytest.raises(UnsafeRedirectError):
        client.get("https://meli.la/a", ("meli.la", "mercadolivre.com.br"), ("text/html",))

    assert calls == Counter({"https://meli.la/a": 1})


def test_allows_only_the_bounded_google_sheets_export_redirect(http_client_factory):
    client, calls = http_client_factory({
        "https://docs.google.com/spreadsheets/d/fixed/export": (
            302,
            {"location": "https://doc-a1-sheets.googleusercontent.com/download"},
            b"",
        ),
        "https://doc-a1-sheets.googleusercontent.com/download": (
            200,
            {"content-type": "text/csv"},
            b"header",
        ),
    })

    response = client.get(
        "https://docs.google.com/spreadsheets/d/fixed/export",
        ("docs.google.com",),
        ("text/csv",),
        redirect_host_policy=google_sheets_export_redirect_host,
    )

    assert response.body == b"header"
    assert calls == Counter({
        "https://docs.google.com/spreadsheets/d/fixed/export": 1,
        "https://doc-a1-sheets.googleusercontent.com/download": 1,
    })


@pytest.mark.parametrize(
    "redirect_host",
    (
        "sheets.googleusercontent.com",
        "doc-a1-sheets.googleusercontent.com.evil.example",
        "doc--sheets.googleusercontent.com",
        "doc-a1-sheets.googleusercontent.co",
        "doc-" + "a" * 53 + "-sheets.googleusercontent.com",
    ),
)
def test_rejects_unrelated_or_lookalike_google_export_redirects(http_client_factory, redirect_host):
    client, calls = http_client_factory({
        "https://docs.google.com/spreadsheets/d/fixed/export": (
            302,
            {"location": f"https://{redirect_host}/download"},
            b"",
        ),
    })

    with pytest.raises(UnsafeRedirectError):
        client.get(
            "https://docs.google.com/spreadsheets/d/fixed/export",
            ("docs.google.com",),
            ("text/csv",),
            redirect_host_policy=google_sheets_export_redirect_host,
        )

    assert calls == Counter({"https://docs.google.com/spreadsheets/d/fixed/export": 1})


def test_google_export_redirect_policy_never_admits_the_initial_url(http_client_factory):
    client, calls = http_client_factory({
        "https://doc-a1-sheets.googleusercontent.com/download": (
            200,
            {"content-type": "text/csv"},
            b"header",
        ),
    })

    with pytest.raises(UnsafeUrlError):
        client.get(
            "https://doc-a1-sheets.googleusercontent.com/download",
            ("docs.google.com",),
            ("text/csv",),
            redirect_host_policy=google_sheets_export_redirect_host,
        )

    assert calls == Counter()


def test_isolates_injected_client_cookie_state_without_sending_cookies():
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path == "/start":
            return httpx.Response(
                302,
                headers={
                    "location": "/end",
                    "set-cookie": "response_cookie=should-not-return; Path=/",
                },
                request=request,
            )
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"ok", request=request)

    shared_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Cookie": "header_cookie=should-not-send"},
        cookies={"jar_cookie": "should-not-send"},
    )
    before_cookie_jar = _cookie_jar_snapshot(shared_client.cookies)
    client = SafeHttpClient(
        client=shared_client,
        dns_resolver=lambda *_args: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
        ],
    )

    try:
        response = client.get("https://example.com/start", ("example.com",), ("text/html",))

        assert response.body == b"ok"
        assert [request.headers.get("cookie") for request in requests] == [None, None]
        assert _cookie_jar_snapshot(shared_client.cookies) == before_cookie_jar
        assert shared_client.cookies.get("response_cookie") is None
    finally:
        client.close()
        assert shared_client.is_closed is False
        shared_client.close()


def test_default_client_ignores_ambient_transport_settings_and_starts_cookie_free():
    client = SafeHttpClient()

    try:
        assert client._client.trust_env is False
        assert list(client._client.cookies.items()) == []
    finally:
        client.close()


def _cookie_jar_snapshot(cookies):
    return tuple(
        tuple(sorted(vars(cookie).items(), key=lambda item: item[0]))
        for cookie in cookies.jar
    )


def test_rejects_private_dns_before_making_a_request(http_client_factory):
    def private_dns(*_args):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))]

    client, calls = http_client_factory(
        {"https://example.com/item": (200, {"content-type": "text/html"}, b"ok")},
        dns_resolver=private_dns,
    )

    with pytest.raises(UnsafeUrlError):
        client.get("https://example.com/item", ("example.com",), ("text/html",))

    assert calls == Counter()


def test_rejects_a_body_that_exceeds_two_megabytes(http_client_factory):
    client, _calls = http_client_factory({
        "https://example.com/item": (200, {"content-type": "text/html"}, b"x" * (BODY_LIMIT_BYTES + 1)),
    })

    with pytest.raises(ResponseTooLargeError):
        client.get("https://example.com/item", ("example.com",), ("text/html",))


def test_rejects_an_unexpected_media_type(http_client_factory):
    client, _calls = http_client_factory({
        "https://example.com/item": (200, {"content-type": "application/octet-stream"}, b"binary"),
    })

    with pytest.raises(UnexpectedContentTypeError):
        client.get("https://example.com/item", ("example.com",), ("text/html",))


def test_maps_not_found_to_typed_error(http_client_factory):
    client, _calls = http_client_factory({
        "https://example.com/item": (404, {}, b"missing"),
    })

    with pytest.raises(ProductNotFoundError):
        client.get("https://example.com/item", ("example.com",), ("text/html",))


@pytest.mark.parametrize("status_code", [401, 403, 407])
def test_does_not_retry_persistent_store_blocks(http_client_factory, status_code):
    client, calls = http_client_factory({
        "https://example.com/item": [(status_code, {}, b"blocked")] * 3,
    })

    with pytest.raises(BlockedByStoreError):
        client.get("https://example.com/item", ("example.com",), ("text/html",))

    assert calls["https://example.com/item"] == 1


def test_retries_a_temporary_status_once_with_injected_backoff(http_client_factory):
    sleeps = []
    client, calls = http_client_factory({
        "https://example.com/item": [
            (503, {}, b"unavailable"),
            (200, {"content-type": "text/html"}, b"ok"),
        ],
    }, sleeps=sleeps)

    response = client.get("https://example.com/item", ("example.com",), ("text/html",))

    assert response.body == b"ok"
    assert calls["https://example.com/item"] == 2
    assert sleeps == [0.5]


def test_stops_after_two_temporary_retries(http_client_factory):
    sleeps = []
    client, calls = http_client_factory({
        "https://example.com/item": [(503, {}, b"unavailable")] * 3,
    }, sleeps=sleeps)

    with pytest.raises(TemporaryFetchError):
        client.get("https://example.com/item", ("example.com",), ("text/html",))

    assert calls["https://example.com/item"] == 3
    assert sleeps == [0.5, 1.0]


def test_retries_transport_timeouts_with_injected_backoff(http_client_factory):
    sleeps = []
    client, calls = http_client_factory({
        "https://example.com/item": [
            httpx.ReadTimeout("read timeout"),
            (200, {"content-type": "text/html"}, b"ok"),
        ],
    }, sleeps=sleeps)

    response = client.get("https://example.com/item", ("example.com",), ("text/html",))

    assert response.body == b"ok"
    assert calls["https://example.com/item"] == 2
    assert sleeps == [0.5]


def test_rejects_a_sixth_redirect(http_client_factory):
    routes = {
        f"https://example.com/{number}": (302, {"location": f"/{number + 1}"}, b"")
        for number in range(6)
    }
    client, calls = http_client_factory(routes)

    with pytest.raises(UnsafeRedirectError):
        client.get("https://example.com/0", ("example.com",), ("text/html",))

    assert sum(calls.values()) == 6


def test_disables_redirects_for_an_injected_client_configured_to_follow(http_client_factory):
    client, calls = http_client_factory(
        {
            "https://meli.la/a": (302, {"location": "https://evil.example/item"}, b""),
            "https://evil.example/item": (200, {"content-type": "text/html"}, b"unsafe"),
        },
        client_builder=lambda transport: httpx.Client(
            transport=transport,
            follow_redirects=True,
        ),
    )

    with pytest.raises(UnsafeRedirectError):
        client.get("https://meli.la/a", ("meli.la",), ("text/html",))

    assert calls == Counter({"https://meli.la/a": 1})


def test_enforces_approved_timeouts_when_the_injected_client_disables_them(http_client_factory):
    requests = []
    client, _calls = http_client_factory(
        {"https://example.com/item": (200, {"content-type": "text/html"}, b"ok")},
        requests=requests,
        client_builder=lambda transport: httpx.Client(transport=transport, timeout=None),
    )

    client.get("https://example.com/item", ("example.com",), ("text/html",))

    assert requests[0].extensions["timeout"] == {
        "connect": 5,
        "read": 15,
        "write": 15,
        "pool": 5,
    }


class _ChunkedBody(httpx.SyncByteStream):
    def __init__(self, chunks):
        self._chunks = chunks

    def __iter__(self):
        yield from self._chunks


def test_accepts_exactly_two_megabytes_streamed_in_multiple_chunks(http_client_factory):
    chunks = (b"a" * 800_000, b"b" * 700_000, b"c" * 500_000)
    client, _calls = http_client_factory({
        "https://example.com/item": (200, {"content-type": "text/html"}, _ChunkedBody(chunks)),
    })

    response = client.get("https://example.com/item", ("example.com",), ("text/html",))

    assert response.body == b"".join(chunks)
    assert len(response.body) == BODY_LIMIT_BYTES


def test_rejects_stream_when_its_final_chunk_crosses_two_megabytes(http_client_factory):
    chunks = (b"a" * 800_000, b"b" * 1_199_999, b"c" * 2)
    client, _calls = http_client_factory({
        "https://example.com/item": (200, {"content-type": "text/html"}, _ChunkedBody(chunks)),
    })

    with pytest.raises(ResponseTooLargeError):
        client.get("https://example.com/item", ("example.com",), ("text/html",))


def test_rejects_redirect_without_location(http_client_factory):
    client, calls = http_client_factory({
        "https://example.com/item": (302, {}, b""),
    })

    with pytest.raises(UnsafeRedirectError):
        client.get("https://example.com/item", ("example.com",), ("text/html",))

    assert calls == Counter({"https://example.com/item": 1})


def test_rejects_redirect_cycle_after_the_fixed_redirect_limit(http_client_factory):
    client, calls = http_client_factory({
        "https://example.com/a": [(302, {"location": "/b"}, b"")] * 3,
        "https://example.com/b": [(302, {"location": "/a"}, b"")] * 3,
    })

    with pytest.raises(UnsafeRedirectError):
        client.get("https://example.com/a", ("example.com",), ("text/html",))

    assert sum(calls.values()) == 6


def test_closing_safe_client_does_not_close_an_injected_shared_client():
    raw_client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request)))
    client = SafeHttpClient(client=raw_client)

    client.close()

    assert raw_client.is_closed is False
    raw_client.close()
