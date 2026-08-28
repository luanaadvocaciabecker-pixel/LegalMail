import datetime as dt
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from legalmail_prazos.holidays import Calendario
from legalmail_prazos.legalmail_client import (
    AudienciaLegalmail,
    ItemEntrada,
    NovaTarefaLegalmail,
    TipoTarefaHistorico,
)
from legalmail_prazos.planilha import ABA_AUDIENCIA, ABA_PRAZOS
from legalmail_prazos.prazos import Prazo, RegimeContagem, calcular_prazo
from legalmail_prazos.rotina import (
    DecisaoItemEntrada,
    escolher_tipo_tarefa,
    processar_parte1,
    processar_parte2,
)


@dataclass
class FakeLegalmailClient:
    historico_por_processo: dict[str, list[TipoTarefaHistorico]] = field(default_factory=dict)
    tarefas_criadas: list[NovaTarefaLegalmail] = field(default_factory=list)
    processos_arquivados: list[str] = field(default_factory=list)

    def listar_entrada(self):  # pragma: no cover - não usado nestes testes
        return []

    def historico_tarefas_do_processo(self, id_legalmail_processo: str):
        return self.historico_por_processo.get(id_legalmail_processo, [])

    def criar_tarefa(self, tarefa: NovaTarefaLegalmail) -> str:
        self.tarefas_criadas.append(tarefa)
        return f"tarefa-{len(self.tarefas_criadas)}"

    def arquivar_para_acervo(self, id_legalmail_processo: str) -> None:
        self.processos_arquivados.append(id_legalmail_processo)

    def listar_audiencias(self, *, a_partir_de: date):  # pragma: no cover
        return []


def _prazo_teste() -> Prazo:
    cal = Calendario(anos=(2026,), incluir_carnaval=False)
    return calcular_prazo(
        data_disponibilizacao=date(2026, 8, 24),
        quantidade_dias=10,
        regime=RegimeContagem.CIVEL_DIAS_UTEIS,
        calendario=cal,
    )


def test_escolher_tipo_tarefa_reaproveita_por_similaridade():
    historico = [
        TipoTarefaHistorico(tipo="CIENCIA", descricao_resumo="Ciência de despacho simples"),
        TipoTarefaHistorico(
            tipo="MANIFESTAÇÃO ENDEREÇO", descricao_resumo="Manifestar sobre endereço do réu"
        ),
    ]
    tipo = escolher_tipo_tarefa(historico, "Manifestar sobre o novo endereço informado")
    assert tipo == "MANIFESTAÇÃO ENDEREÇO"


def test_escolher_tipo_tarefa_sem_historico_retorna_none():
    assert escolher_tipo_tarefa([], "qualquer descrição") is None


def test_processar_parte1_caso_novo_cria_linha_tarefa_e_arquiva(planilha_sintetica: Path, tmp_path: Path):
    client = FakeLegalmailClient(
        historico_por_processo={
            "item-1": [
                TipoTarefaHistorico(tipo="CIENCIA", descricao_resumo="Ciência de decisão")
            ]
        }
    )
    item = ItemEntrada(
        id_legalmail="item-1",
        numero_processo="0001000-00.2026.5.12.0001",
        tribunal="TRT12 1G",
        cliente_x_parte="CLIENTE TESTE DOIS",
        conteudo_intimacao="Decisão para ciência.",
        data_disponibilizacao=date(2026, 8, 24),
    )
    decisao = DecisaoItemEntrada(
        item=item,
        descricao_tarefa="Ciência de decisão proferida nos autos",
        prazo=_prazo_teste(),
        encarregado_override="BELTRANA SILVA",
    )

    relatorio = processar_parte1(
        decisoes=[decisao],
        client=client,
        caminho_planilha=planilha_sintetica,
        caminho_prazos_nums_json=tmp_path / "prazos_nums.json",
        pasta_outputs=tmp_path / "outputs",
    )

    assert len(relatorio.casos_novos) == 1
    assert relatorio.casos_novos[0].numero_processo == "0001000-00.2026.5.12.0001"
    assert relatorio.tarefas_criadas == 1
    assert client.tarefas_criadas[0].tipo == "CIENCIA"
    assert client.processos_arquivados == ["item-1"]

    wb = load_workbook(planilha_sintetica)
    processos = {ws_row[1] for ws_row in wb[ABA_PRAZOS].iter_rows(min_row=9, values_only=True)}
    assert "0001000-00.2026.5.12.0001" in processos


def test_processar_parte1_caso_recorrente_nao_duplica_linha(planilha_sintetica: Path, tmp_path: Path):
    client = FakeLegalmailClient()
    item = ItemEntrada(
        id_legalmail="item-2",
        numero_processo="5000000-00.2025.8.24.0038",  # já existe na planilha sintética
        tribunal="TJSC 1G",
        cliente_x_parte="CLIENTE TESTE UM",
        conteudo_intimacao="Nova intimação no processo já conhecido.",
        data_disponibilizacao=date(2026, 8, 24),
    )
    decisao = DecisaoItemEntrada(
        item=item,
        descricao_tarefa="Nova manifestação necessária",
        prazo=_prazo_teste(),
        encarregado_override="FULANA DE TAL",
    )

    relatorio = processar_parte1(
        decisoes=[decisao],
        client=client,
        caminho_planilha=planilha_sintetica,
        caminho_prazos_nums_json=tmp_path / "prazos_nums.json",
        pasta_outputs=tmp_path / "outputs",
    )

    assert relatorio.casos_novos == []
    assert relatorio.tarefas_criadas == 1

    wb = load_workbook(planilha_sintetica)
    processos = [
        row[1] for row in wb[ABA_PRAZOS].iter_rows(min_row=9, values_only=True) if row[1]
    ]
    assert processos.count("5000000-00.2025.8.24.0038") == 1


def test_processar_parte1_conteudo_bloqueado_nao_inventa_dados(planilha_sintetica: Path, tmp_path: Path):
    client = FakeLegalmailClient()
    item = ItemEntrada(
        id_legalmail="item-3",
        numero_processo="0005000-00.2026.8.24.0038",
        tribunal="TJSC 1G",
        cliente_x_parte="CLIENTE TESTE CINCO",
        conteudo_intimacao="",
        data_disponibilizacao=date(2026, 8, 24),
        segredo_justica=True,
        conteudo_acessivel=False,
    )
    decisao = DecisaoItemEntrada(item=item, descricao_tarefa="", prazo=_prazo_teste())

    relatorio = processar_parte1(
        decisoes=[decisao],
        client=client,
        caminho_planilha=planilha_sintetica,
        caminho_prazos_nums_json=tmp_path / "prazos_nums.json",
        pasta_outputs=tmp_path / "outputs",
    )

    assert relatorio.tarefas_criadas == 0
    assert client.tarefas_criadas == []
    assert relatorio.limitacoes  # a limitação foi reportada


def test_relatorio_texto_sem_dois_pontos():
    from legalmail_prazos.rotina import RelatorioConciliacao, ResultadoCasoNovo

    relatorio = RelatorioConciliacao(
        casos_novos=[
            ResultadoCasoNovo(numero_processo="0006000-00.2026.8.24.0038", cliente="CLIENTE TESTE SEIS", tribunal="TJSC 1G")
        ],
        tarefas_criadas=1,
    )
    assert ":" not in relatorio.texto()


def test_processar_parte2_adiciona_audiencia_nova(planilha_sintetica: Path, tmp_path: Path):
    audiencia = AudienciaLegalmail(
        id_legalmail="aud-1",
        numero_processo="0007000-00.2026.5.12.0030",
        cliente="cliente teste sete",
        evento="AUDIÊNCIA DE CONCILIAÇÃO",
        area="TRABALHISTA",
        data=date(2026, 10, 10),
        horario=dt.time(14, 0),
    )
    relatorio = processar_parte2(
        audiencias_legalmail=[audiencia],
        caminho_planilha=planilha_sintetica,
        pasta_outputs=tmp_path / "outputs",
    )
    assert relatorio.audiencias_adicionadas == 1

    wb = load_workbook(planilha_sintetica)
    ws = wb[ABA_AUDIENCIA]
    linha = ws.max_row
    assert ws.cell(row=linha, column=1).value == "CLIENTE TESTE SETE"
    assert ws.cell(row=linha, column=10).value is None


def test_processar_parte2_nao_duplica_audiencia_existente(planilha_sintetica: Path, tmp_path: Path):
    audiencia = AudienciaLegalmail(
        id_legalmail="aud-2",
        numero_processo="0008000-00.2026.5.12.0030",
        cliente="cliente teste oito",
        evento="AUDIÊNCIA DE INSTRUÇÃO",
        area="TRABALHISTA",
        data=date(2026, 10, 12),
        horario=dt.time(9, 0),
    )
    processar_parte2(
        audiencias_legalmail=[audiencia],
        caminho_planilha=planilha_sintetica,
        pasta_outputs=tmp_path / "outputs",
    )
    relatorio2 = processar_parte2(
        audiencias_legalmail=[audiencia],
        caminho_planilha=planilha_sintetica,
        pasta_outputs=tmp_path / "outputs",
    )
    assert relatorio2.audiencias_adicionadas == 0
