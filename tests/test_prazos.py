from datetime import date

from legalmail_prazos.holidays import Calendario
from legalmail_prazos.prazos import (
    MARGEM_SEGURANCA_DIAS_UTEIS,
    Prazo,
    RegimeContagem,
    calcular_prazo,
    marco_inicial_por_disponibilizacao,
)


def _calendario() -> Calendario:
    return Calendario(anos=(2026,), incluir_carnaval=False)


def test_marco_inicial_quando_disponibilizado_em_dia_util():
    cal = _calendario()
    # 2026-08-24 é segunda-feira útil; marco inicial deve ser o próximo dia útil (terça 08-25).
    assert marco_inicial_por_disponibilizacao(date(2026, 8, 24), cal) == date(2026, 8, 25)


def test_marco_inicial_quando_disponibilizado_em_fim_de_semana():
    cal = _calendario()
    # 2026-08-22 é sábado; considera-se realizada no primeiro dia útil seguinte (segunda 08-24).
    assert marco_inicial_por_disponibilizacao(date(2026, 8, 22), cal) == date(2026, 8, 24)


def test_calcular_prazo_civel_dias_uteis():
    cal = _calendario()
    prazo = calcular_prazo(
        data_disponibilizacao=date(2026, 8, 24),
        quantidade_dias=15,
        regime=RegimeContagem.CIVEL_DIAS_UTEIS,
        calendario=cal,
    )
    assert prazo.inicio_contagem == date(2026, 8, 25)
    assert prazo.data_final_legal == cal.somar_dias_uteis(date(2026, 8, 25), 15)
    assert prazo.data_final_interna < prazo.data_final_legal


def test_margem_seguranca_padrao_eh_dois_dias_uteis():
    cal = _calendario()
    prazo = calcular_prazo(
        data_disponibilizacao=date(2026, 8, 24),
        quantidade_dias=10,
        regime=RegimeContagem.CIVEL_DIAS_UTEIS,
        calendario=cal,
    )
    reconstituido = cal.somar_dias_uteis(prazo.data_final_interna, MARGEM_SEGURANCA_DIAS_UTEIS)
    assert reconstituido == prazo.data_final_legal


def test_sem_margem_seguranca_para_janela_administrativa():
    cal = _calendario()
    prazo = calcular_prazo(
        data_disponibilizacao=date(2026, 8, 24),
        quantidade_dias=1,
        regime=RegimeContagem.CIVEL_DIAS_UTEIS,
        calendario=cal,
        aplicar_margem_seguranca=False,
    )
    assert prazo.data_final_interna == prazo.data_final_legal


def test_juizado_especial_conta_dias_corridos():
    cal = _calendario()
    prazo = calcular_prazo(
        data_disponibilizacao=date(2026, 8, 24),
        quantidade_dias=10,
        regime=RegimeContagem.JUIZADO_ESPECIAL_DIAS_CORRIDOS,
        calendario=cal,
    )
    assert prazo.data_final_legal == cal.somar_dias_corridos(date(2026, 8, 25), 10)


def test_prazo_a_partir_de_tribunal_usa_datas_informadas_diretamente():
    cal = _calendario()
    prazo = Prazo.a_partir_de_tribunal(
        data_disponibilizacao=date(2026, 8, 24),
        inicio_contagem=date(2026, 8, 25),
        data_final_legal=date(2026, 9, 10),
        regime=RegimeContagem.TRABALHISTA_DIAS_UTEIS,
        quantidade_dias=8,
        calendario=cal,
    )
    assert prazo.data_final_legal == date(2026, 9, 10)
    assert prazo.data_final_interna < prazo.data_final_legal


def test_estimativa_por_analogia_fica_sinalizada():
    cal = _calendario()
    prazo = calcular_prazo(
        data_disponibilizacao=date(2026, 8, 24),
        quantidade_dias=5,
        regime=RegimeContagem.CIVEL_DIAS_UTEIS,
        calendario=cal,
        estimado_por_analogia=True,
    )
    assert prazo.estimado_por_analogia is True
