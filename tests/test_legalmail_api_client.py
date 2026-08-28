from dataclasses import dataclass, field
from datetime import date

import pytest

from legalmail_prazos.legalmail_api_client import (
    LegalmailApiClient,
    RecursoNaoSuportadoPelaApiError,
    cliente_a_partir_do_ambiente,
)


@dataclass
class FakeLegalmailApiV1:
    """Substitui LegalmailApiV1 nos testes do adaptador, sem HTTP real."""

    paginas_notices: list[dict] = field(default_factory=list)
    usuarios: list[dict] = field(default_factory=list)
    autos_por_processo: dict[int, list[dict]] = field(default_factory=dict)
    urls_por_movimentacao: dict[int, dict] = field(default_factory=dict)
    chamadas_archive: list[int] = field(default_factory=list)
    chamadas_assign: list[tuple[int, int]] = field(default_factory=list)

    def list_notices(self, **kwargs):
        return self.paginas_notices.pop(0)

    def list_users(self):
        return self.usuarios

    def lawsuit_archive(self, fk_processo: int):
        self.chamadas_archive.append(fk_processo)
        return {"status": "success"}

    def lawsuit_assign(self, idprocessos: int, idusuarios: int):
        self.chamadas_assign.append((idprocessos, idusuarios))
        return {"status": "success"}

    def lawsuit_case_files(self, idprocesso: int):
        return self.autos_por_processo.get(idprocesso, [])

    def docket_entry_url(self, idmovimentacoes: int):
        return self.urls_por_movimentacao.get(idmovimentacoes, {"status": "success", "s3_url": None})


def _notice(**overrides):
    base = {
        "id": 1,
        "idprocessos": 45211,
        "numero_processo": "1001272-96.2020.5.02.0012",
        "partes": "ACME Indústria LTDA, João da Silva",
        "data_disponibilizacao": "2026-07-28",
        "tribunal": "TJSP",
        "prazo_status": "pendente",
        "teor": "Fica a parte intimada a se manifestar no prazo de 15 dias.",
    }
    base.update(overrides)
    return base


def test_listar_entrada_converte_notices_pendentes():
    api = FakeLegalmailApiV1(
        paginas_notices=[{"total": 1, "notices": [_notice()]}],
    )
    cliente = LegalmailApiClient(api)

    itens = cliente.listar_entrada(data_captura_inicio="2026-08-24", data_captura_fim="2026-08-24")

    assert len(itens) == 1
    item = itens[0]
    assert item.id_legalmail == "45211"
    assert item.numero_processo == "1001272-96.2020.5.02.0012"
    assert item.data_disponibilizacao == date(2026, 7, 28)
    assert item.conteudo_acessivel is True


def test_listar_entrada_ignora_prazo_ja_cumprido():
    api = FakeLegalmailApiV1(
        paginas_notices=[
            {
                "total": 2,
                "notices": [_notice(prazo_status="cumprido"), _notice(prazo_status="pendente")],
            }
        ]
    )
    cliente = LegalmailApiClient(api)

    itens = cliente.listar_entrada()

    assert len(itens) == 1


def test_listar_entrada_ignora_notice_sem_processo_importado():
    api = FakeLegalmailApiV1(
        paginas_notices=[{"total": 1, "notices": [_notice(idprocessos=None)]}],
    )
    cliente = LegalmailApiClient(api)

    itens = cliente.listar_entrada()

    assert itens == []


def test_listar_entrada_pagina_ate_esgotar_total():
    api = FakeLegalmailApiV1(
        paginas_notices=[
            {"total": 51, "notices": [_notice(id=i, idprocessos=i) for i in range(50)]},
            {"total": 51, "notices": [_notice(id=50, idprocessos=50)]},
        ]
    )
    cliente = LegalmailApiClient(api)

    itens = cliente.listar_entrada()

    assert len(itens) == 51


def test_arquivar_para_acervo_chama_api_com_id_correto():
    api = FakeLegalmailApiV1()
    cliente = LegalmailApiClient(api)

    cliente.arquivar_para_acervo("45211")

    assert api.chamadas_archive == [45211]


def test_encarregar_advogado_chama_assign():
    api = FakeLegalmailApiV1()
    cliente = LegalmailApiClient(api)

    cliente.encarregar_advogado("45211", 42)

    assert api.chamadas_assign == [(45211, 42)]


def test_localizar_usuario_por_nome_case_insensitive():
    api = FakeLegalmailApiV1(usuarios=[{"idusuarios": 42, "nome": "Maria Silva"}])
    cliente = LegalmailApiClient(api)

    assert cliente.localizar_usuario_por_nome("maria silva") == 42
    assert cliente.localizar_usuario_por_nome("Outra Pessoa") is None


def test_historico_tarefas_nao_suportado():
    cliente = LegalmailApiClient(FakeLegalmailApiV1())
    with pytest.raises(RecursoNaoSuportadoPelaApiError):
        cliente.historico_tarefas_do_processo("45211")


def test_criar_tarefa_nao_suportado():
    cliente = LegalmailApiClient(FakeLegalmailApiV1())
    with pytest.raises(RecursoNaoSuportadoPelaApiError):
        cliente.criar_tarefa(None)


def test_listar_audiencias_nao_suportado():
    cliente = LegalmailApiClient(FakeLegalmailApiV1())
    with pytest.raises(RecursoNaoSuportadoPelaApiError):
        cliente.listar_audiencias(a_partir_de=date(2026, 8, 24))


def test_cliente_a_partir_do_ambiente_exige_variavel(monkeypatch):
    monkeypatch.delenv("LEGALMAIL_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        cliente_a_partir_do_ambiente()


def test_listar_autos_processo_converte_movimentacoes():
    api = FakeLegalmailApiV1(
        autos_por_processo={
            456: [
                {
                    "idmovimentacoes": 123,
                    "fk_processo": 456,
                    "titulo": "Petição inicial",
                    "data_movimentacao": "2024-05-01",
                    "tipo": "principal",
                }
            ]
        }
    )
    cliente = LegalmailApiClient(api)

    autos = cliente.listar_autos_processo("456")

    assert len(autos) == 1
    assert autos[0].id_movimentacao == 123
    assert autos[0].titulo == "Petição inicial"
    assert autos[0].data_movimentacao == date(2024, 5, 1)
    assert autos[0].tipo == "principal"


def test_listar_autos_processo_sem_autos():
    cliente = LegalmailApiClient(FakeLegalmailApiV1())
    assert cliente.listar_autos_processo("999") == []


def test_obter_url_documento():
    api = FakeLegalmailApiV1(
        urls_por_movimentacao={123: {"status": "success", "s3_url": "https://exemplo/doc.pdf"}}
    )
    cliente = LegalmailApiClient(api)

    assert cliente.obter_url_documento(123) == "https://exemplo/doc.pdf"


def test_obter_url_documento_ausente_retorna_none():
    cliente = LegalmailApiClient(FakeLegalmailApiV1())
    assert cliente.obter_url_documento(999) is None
