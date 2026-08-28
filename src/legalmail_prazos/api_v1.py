"""Cliente HTTP fino para a API pública do Legalmail (LegalMail Public API v1).

Baseado em ``docs/legalmail-openapi.json`` (especificação OpenAPI fornecida
pelo escritório). Cobre apenas os endpoints usados por esta rotina; não é um
SDK completo da API.

Importante sobre custo: a API é paga por crédito do workspace e a maioria
dos endpoints é cobrada por requisição bem-sucedida (2xx) — em especial
``GET /api/v1/notices`` (R$ 0,05 por requisição, independente de quantas
intimações vierem na página). Erros (4xx/5xx) não são cobrados. Por isso
este módulo nunca faz retry automático de chamadas bem-sucedidas nem
"polling" em laço — isso é responsabilidade explícita de quem chama, e
repetir a mesma consulta em intervalo curto pode gerar bloqueio progressivo
(seção "Limites de requisição" da documentação).

Nenhuma chamada real é feita a partir de testes automatizados deste
repositório — os testes usam uma sessão HTTP falsa.
"""

from __future__ import annotations

from typing import Any, Protocol

BASE_URL = "https://api.legalmail.com.br/"


class HttpResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class HttpSession(Protocol):
    """Subconjunto de ``requests.Session`` usado por este cliente."""

    def get(self, url: str, *, params: dict[str, Any]) -> HttpResponse: ...

    def post(self, url: str, *, params: dict[str, Any], json: dict[str, Any]) -> HttpResponse: ...


class LegalmailApiError(Exception):
    """Erro genérico da API do Legalmail."""

    def __init__(self, status_code: int, payload: Any, message: str | None = None) -> None:
        self.status_code = status_code
        self.payload = payload
        super().__init__(message or (payload.get("error") if isinstance(payload, dict) else str(payload)))


class LegalmailBadRequestError(LegalmailApiError):
    """400 — parâmetro ausente ou malformado."""


class LegalmailAuthError(LegalmailApiError):
    """401 — chave de API não informada."""


class LegalmailInsufficientBalanceError(LegalmailApiError):
    """402 — saldo de créditos insuficiente para a requisição."""

    @property
    def saldo_disponivel(self) -> float | None:
        return self.payload.get("saldo_disponivel") if isinstance(self.payload, dict) else None

    @property
    def custo_requisicao(self) -> float | None:
        return self.payload.get("custo_requisicao") if isinstance(self.payload, dict) else None


class LegalmailNotFoundError(LegalmailApiError):
    """404 — chave inválida ou recurso não encontrado."""


class LegalmailMethodNotAllowedError(LegalmailApiError):
    """405 — método HTTP não permitido para o endpoint."""


class LegalmailRateLimitError(LegalmailApiError):
    """429 — rate limit padrão excedido ou bloqueio por polling detectado.

    ``retry_after_seconds`` vem do cabeçalho ``Retry-After`` quando presente
    (bloqueio ativo por polling); pode ser ``None`` no caso de apenas ter
    excedido o limite padrão de 120 req/min sem bloqueio ainda vigente.
    """

    def __init__(self, status_code: int, payload: Any, retry_after_seconds: int | None) -> None:
        super().__init__(status_code, payload)
        self.retry_after_seconds = retry_after_seconds


class LegalmailServerError(LegalmailApiError):
    """5xx — erro interno da API. Documentação recomenda backoff exponencial."""


def _levantar_erro_por_status(status_code: int, payload: Any, retry_after: str | None) -> None:
    if status_code == 400:
        raise LegalmailBadRequestError(status_code, payload)
    if status_code == 401:
        raise LegalmailAuthError(status_code, payload)
    if status_code == 402:
        raise LegalmailInsufficientBalanceError(status_code, payload)
    if status_code == 404:
        raise LegalmailNotFoundError(status_code, payload)
    if status_code == 405:
        raise LegalmailMethodNotAllowedError(status_code, payload)
    if status_code == 429:
        raise LegalmailRateLimitError(
            status_code, payload, int(retry_after) if retry_after else None
        )
    if status_code >= 500:
        raise LegalmailServerError(status_code, payload)


class LegalmailApiV1:
    """Cliente fino para os endpoints da API v1 usados por esta rotina."""

    def __init__(self, api_key: str, *, session: HttpSession, base_url: str = BASE_URL) -> None:
        if not api_key:
            raise ValueError("api_key não pode ser vazio")
        self._api_key = api_key
        self._session = session
        self._base_url = base_url.rstrip("/")

    def _get(self, caminho: str, **params: Any) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        params["api_key"] = self._api_key
        resposta = self._session.get(f"{self._base_url}{caminho}", params=params)
        return self._tratar_resposta(resposta)

    def _post(self, caminho: str, corpo: dict[str, Any]) -> Any:
        resposta = self._session.post(
            f"{self._base_url}{caminho}", params={"api_key": self._api_key}, json=corpo
        )
        return self._tratar_resposta(resposta)

    @staticmethod
    def _tratar_resposta(resposta: HttpResponse) -> Any:
        payload = resposta.json()
        if resposta.status_code >= 400:
            retry_after = getattr(resposta, "headers", {}).get("Retry-After") if hasattr(
                resposta, "headers"
            ) else None
            _levantar_erro_por_status(resposta.status_code, payload, retry_after)
        return payload

    def balance(self) -> dict[str, Any]:
        """``GET /api/v1/balance`` — gratuito."""

        return self._get("/api/v1/balance")

    def list_notices(
        self,
        *,
        data_captura_inicio: str | None = None,
        data_captura_fim: str | None = None,
        offset: int = 0,
        limit: int = 50,
        ordenar_por: str = "data_captura",
        ordem: str = "asc",
        processo: str | None = None,
        destinatario_id: int | None = None,
    ) -> dict[str, Any]:
        """``GET /api/v1/notices`` — cobrado R$ 0,05 por requisição (2xx).

        Pagine com ``offset`` até somar o ``total`` retornado, sempre com a
        mesma ordenação e intervalo de datas fechado (ver seção "Receita
        para a rotina diária" da documentação).
        """

        return self._get(
            "/api/v1/notices",
            data_captura_inicio=data_captura_inicio,
            data_captura_fim=data_captura_fim,
            offset=offset,
            limit=limit,
            ordenar_por=ordenar_por,
            ordem=ordem,
            processo=processo,
            destinatario_id=destinatario_id,
        )

    def lawsuit_detail(
        self, *, numero_processo: str | None = None, idprocesso: int | None = None
    ) -> Any:
        """``GET /api/v1/lawsuit/detail``. Informe apenas um dos dois parâmetros."""

        if bool(numero_processo) == bool(idprocesso):
            raise ValueError("informe exatamente um de numero_processo ou idprocesso")
        return self._get(
            "/api/v1/lawsuit/detail", numero_processo=numero_processo, idprocesso=idprocesso
        )

    def lawsuit_archive(self, fk_processo: int) -> dict[str, Any]:
        """``POST /api/v1/lawsuit/archive`` — alterna entrada/acervo.

        Se o processo estiver na Entrada, é enviado para o Acervo (e o
        ``data_prazo`` do processo é removido pela própria plataforma).
        """

        return self._post("/api/v1/lawsuit/archive", {"fk_processo": fk_processo})

    def lawsuit_assign(self, idprocessos: int, idusuarios: int) -> dict[str, Any]:
        """``POST /api/v1/lawsuit/assign`` — encarrega um usuário no processo."""

        return self._post(
            "/api/v1/lawsuit/assign", {"idprocessos": idprocessos, "idusuarios": idusuarios}
        )

    def list_users(self) -> list[dict[str, Any]]:
        """``GET /api/v1/users``."""

        return self._get("/api/v1/users")

    def list_lawsuits_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        usuario_id: int | None = None,
        oab: str | None = None,
        oab_uf: str | None = None,
    ) -> Any:
        """``GET /api/v1/lawsuit/all`` — apenas id, número e classe de cada processo."""

        return self._get(
            "/api/v1/lawsuit/all",
            offset=offset,
            limit=limit,
            usuario_id=usuario_id,
            oab=oab,
            oab_uf=oab_uf,
        )
