from dataclasses import dataclass, field
from typing import Any

import pytest

from legalmail_prazos.api_v1 import (
    BASE_URL,
    LegalmailApiV1,
    LegalmailAuthError,
    LegalmailBadRequestError,
    LegalmailInsufficientBalanceError,
    LegalmailNotFoundError,
    LegalmailRateLimitError,
    LegalmailServerError,
)


@dataclass
class FakeResponse:
    status_code: int
    payload: Any
    headers: dict = field(default_factory=dict)

    def json(self) -> Any:
        return self.payload


@dataclass
class FakeSession:
    """Sessão HTTP falsa: nunca faz uma chamada de rede real."""

    respostas: list[FakeResponse]
    chamadas: list[tuple[str, str, dict]] = field(default_factory=list)

    def get(self, url: str, *, params: dict) -> FakeResponse:
        self.chamadas.append(("GET", url, params))
        return self.respostas.pop(0)

    def post(self, url: str, *, params: dict, json: dict) -> FakeResponse:
        self.chamadas.append(("POST", url, {**params, "json": json}))
        return self.respostas.pop(0)


def test_balance_sucesso():
    sessao = FakeSession(respostas=[FakeResponse(200, {"saldo_disponivel": 42.0})])
    api = LegalmailApiV1("chave-teste", session=sessao)

    resultado = api.balance()

    assert resultado == {"saldo_disponivel": 42.0}
    metodo, url, params = sessao.chamadas[0]
    assert metodo == "GET"
    assert url == f"{BASE_URL}api/v1/balance"
    assert params["api_key"] == "chave-teste"


def test_list_notices_envia_parametros_e_omite_none():
    sessao = FakeSession(respostas=[FakeResponse(200, {"total": 0, "notices": []})])
    api = LegalmailApiV1("chave-teste", session=sessao)

    api.list_notices(data_captura_inicio="2026-08-24", data_captura_fim="2026-08-24")

    _, _, params = sessao.chamadas[0]
    assert params["data_captura_inicio"] == "2026-08-24"
    assert "processo" not in params  # None não deve ser enviado como parâmetro


def test_lawsuit_archive_envia_body_correto():
    sessao = FakeSession(respostas=[FakeResponse(200, {"status": "success"})])
    api = LegalmailApiV1("chave-teste", session=sessao)

    resultado = api.lawsuit_archive(123)

    assert resultado == {"status": "success"}
    metodo, url, params = sessao.chamadas[0]
    assert metodo == "POST"
    assert params["json"] == {"fk_processo": 123}


def test_lawsuit_assign_envia_body_correto():
    sessao = FakeSession(respostas=[FakeResponse(200, {"status": "success"})])
    api = LegalmailApiV1("chave-teste", session=sessao)

    api.lawsuit_assign(idprocessos=10, idusuarios=42)

    _, _, params = sessao.chamadas[0]
    assert params["json"] == {"idprocessos": 10, "idusuarios": 42}


def test_lawsuit_detail_exige_exatamente_um_parametro():
    sessao = FakeSession(respostas=[])
    api = LegalmailApiV1("chave-teste", session=sessao)

    with pytest.raises(ValueError):
        api.lawsuit_detail()

    with pytest.raises(ValueError):
        api.lawsuit_detail(numero_processo="123", idprocesso=1)


@pytest.mark.parametrize(
    "status_code,excecao",
    [
        (400, LegalmailBadRequestError),
        (401, LegalmailAuthError),
        (404, LegalmailNotFoundError),
        (500, LegalmailServerError),
    ],
)
def test_erros_http_mapeados_para_excecoes(status_code, excecao):
    sessao = FakeSession(respostas=[FakeResponse(status_code, {"error": "algo deu errado"})])
    api = LegalmailApiV1("chave-teste", session=sessao)

    with pytest.raises(excecao):
        api.balance()


def test_erro_402_expoe_saldo_e_custo():
    payload = {
        "error": "Insufficient balance",
        "saldo_disponivel": 4.5,
        "custo_requisicao": 5.0,
    }
    sessao = FakeSession(respostas=[FakeResponse(402, payload)])
    api = LegalmailApiV1("chave-teste", session=sessao)

    with pytest.raises(LegalmailInsufficientBalanceError) as exc_info:
        api.list_notices()

    assert exc_info.value.saldo_disponivel == 4.5
    assert exc_info.value.custo_requisicao == 5.0


def test_erro_429_expoe_retry_after():
    sessao = FakeSession(
        respostas=[
            FakeResponse(
                429,
                {"error": "Prática de polling detectada", "retry_after_seconds": 567},
                headers={"Retry-After": "567"},
            )
        ]
    )
    api = LegalmailApiV1("chave-teste", session=sessao)

    with pytest.raises(LegalmailRateLimitError) as exc_info:
        api.balance()

    assert exc_info.value.retry_after_seconds == 567


def test_construtor_rejeita_api_key_vazia():
    with pytest.raises(ValueError):
        LegalmailApiV1("", session=FakeSession(respostas=[]))
