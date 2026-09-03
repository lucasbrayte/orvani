import json

import httpx
import pytest

from libreoffice_sync.api_client import (
    OrvaniApiClient,
    OrvaniAuthError,
    OrvaniRetryableError,
)


URL = "https://script.google.com/macros/s/test/exec"
SECRET = "0123456789abcdef" * 4


def client_with(handler):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, follow_redirects=True)
    return OrvaniApiClient(
        URL,
        SECRET,
        client=http,
        clock=lambda: 1788420000,
        nonce_factory=lambda: "nonce_1234567890abcdef",
    )


def test_health_posts_signed_envelope():
    def handler(request):
        body = json.loads(request.content)
        assert body["action"] == "health"
        assert body["payload"] == {}
        assert len(body["signature"]) == 64
        return httpx.Response(
            200,
            json={"ok": True, "action": "health", "service": "orvani-sync", "version": "v1"},
        )

    result = client_with(handler).health()
    assert result["ok"] is True


def test_get_status_parses_backend_rows():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "ok": True,
                "action": "get_status",
                "rows": [{
                    "ID Automação": "uuid-1",
                    "ID Externo": "MLB12345678",
                    "Status": "PUBLICADO",
                    "Mensagem": "ok",
                    "Desconto Calculado": 43,
                    "Último Link Publicado": "https://meli.la/teste",
                    "Assinatura dos Dados": "sig",
                    "Última Verificação": "2026-09-03T15:00:00Z",
                    "Última Atualização": "2026-09-03T15:00:01Z",
                }],
            },
        )

    statuses = client_with(handler).get_status(["uuid-1"])
    assert len(statuses) == 1
    assert statuses[0].status == "PUBLICADO"
    assert statuses[0].discount == "43"


def test_upsert_products_is_bounded():
    api = client_with(lambda request: httpx.Response(200, json={"ok": True}))
    with pytest.raises(ValueError):
        api.upsert_products([])
    with pytest.raises(ValueError):
        api.upsert_products([{"ID Automação": str(i)} for i in range(51)])


def test_http_403_is_auth_error():
    api = client_with(lambda request: httpx.Response(403, text="forbidden"))
    with pytest.raises(OrvaniAuthError):
        api.health()


def test_http_5xx_is_retryable():
    api = client_with(lambda request: httpx.Response(503, text="busy"))
    with pytest.raises(OrvaniRetryableError):
        api.health()
