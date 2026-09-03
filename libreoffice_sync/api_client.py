from __future__ import annotations

import secrets
import time
from collections.abc import Callable, Sequence

import httpx

from .models import BackendStatus
from .protocol import signed_envelope


class OrvaniApiError(RuntimeError):
    pass


class OrvaniAuthError(OrvaniApiError):
    pass


class OrvaniRetryableError(OrvaniApiError):
    pass


class OrvaniApiClient:
    def __init__(
        self,
        webapp_url: str,
        secret: str,
        *,
        client: httpx.Client | None = None,
        clock: Callable[[], int] | None = None,
        nonce_factory: Callable[[], str] | None = None,
    ) -> None:
        if not webapp_url.startswith("https://"):
            raise ValueError("ORVANI_WEBAPP_URL deve usar HTTPS.")
        if not webapp_url.rstrip().endswith("/exec"):
            raise ValueError("ORVANI_WEBAPP_URL deve terminar em /exec.")

        self._url = webapp_url
        self._secret = secret
        self._clock = clock or (lambda: int(time.time()))
        self._nonce_factory = nonce_factory or (lambda: secrets.token_hex(16))
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def _post(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        envelope = signed_envelope(
            action,
            payload,
            secret=self._secret,
            timestamp=int(self._clock()),
            nonce=self._nonce_factory(),
        )

        try:
            response = self._client.post(self._url, json=envelope)
        except httpx.TransportError as exc:
            raise OrvaniRetryableError("Falha de rede ao acessar o Apps Script.") from exc

        if response.status_code in {401, 403}:
            raise OrvaniAuthError("Apps Script recusou a autenticação.")
        if response.status_code >= 500:
            raise OrvaniRetryableError("Apps Script indisponível temporariamente.")
        if response.status_code >= 400:
            raise OrvaniApiError(f"Apps Script retornou HTTP {response.status_code}.")

        try:
            body = response.json()
        except ValueError as exc:
            raise OrvaniApiError("Apps Script retornou JSON inválido.") from exc

        if not isinstance(body, dict):
            raise OrvaniApiError("Resposta inválida do Apps Script.")
        if body.get("ok") is not True:
            raise OrvaniApiError(str(body.get("error") or "Apps Script rejeitou a solicitação."))
        return body

    def health(self) -> dict[str, object]:
        return self._post("health", {})

    def upsert_products(self, products: Sequence[dict[str, object]]) -> dict[str, object]:
        items = list(products)
        if not 1 <= len(items) <= 50:
            raise ValueError("upsert_products exige de 1 a 50 produtos.")
        return self._post("upsert_products", {"products": items})

    def get_status(self, ids: Sequence[str]) -> tuple[BackendStatus, ...]:
        requested = [str(value).strip() for value in ids]
        if not requested or any(not value for value in requested):
            raise ValueError("get_status exige IDs não vazios.")
        if len(requested) > 50:
            raise ValueError("get_status aceita no máximo 50 IDs.")
        if len(set(requested)) != len(requested):
            raise ValueError("get_status não aceita IDs duplicados.")

        body = self._post("get_status", {"ids": requested})
        rows = body.get("rows")
        if not isinstance(rows, list):
            raise OrvaniApiError("Resposta de status inválida.")

        result = []
        for row in rows:
            if not isinstance(row, dict):
                raise OrvaniApiError("Linha de status inválida.")
            result.append(
                BackendStatus(
                    automation_id=str(row.get("ID Automação", "")),
                    external_id=str(row.get("ID Externo", "")),
                    status=str(row.get("Status", "")),
                    message=str(row.get("Mensagem", "")),
                    discount=str(row.get("Desconto Calculado", "")),
                    last_published_url=str(row.get("Último Link Publicado", "")),
                    data_signature=str(row.get("Assinatura dos Dados", "")),
                    last_checked_at=str(row.get("Última Verificação", "")),
                    last_updated_at=str(row.get("Última Atualização", "")),
                )
            )
        return tuple(result)
