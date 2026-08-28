from datetime import date

from legalmail_prazos.tribunais import (
    calendario_para_tribunal,
    feriados_tjsc,
    feriados_trt12,
    suspensao_prazos_tjsc_trt12,
)


def test_feriados_tjsc_2026():
    feriados = feriados_tjsc(2026)
    assert date(2026, 4, 2) in feriados  # Quinta-feira Santa
    assert date(2026, 6, 4) in feriados  # Corpus Christi
    assert date(2026, 5, 25) in feriados  # Divino Espírito Santo


def test_feriados_tjsc_ano_nao_pesquisado_fica_vazio():
    assert feriados_tjsc(2027) == set()


def test_feriados_trt12_2026():
    feriados = feriados_trt12(2026)
    assert date(2026, 8, 10) in feriados
    assert date(2026, 10, 30) in feriados
    assert date(2026, 12, 7) in feriados


def test_suspensao_prazos_tjsc_trt12_cobre_virada_do_ano():
    dias = suspensao_prazos_tjsc_trt12(2026)
    assert date(2026, 12, 20) in dias
    assert date(2026, 12, 31) in dias
    assert date(2027, 1, 1) in dias
    assert date(2027, 1, 20) in dias
    assert date(2026, 12, 19) not in dias
    assert date(2027, 1, 21) not in dias


def test_calendario_para_tjsc_confirmado_e_aplica_feriados_proprios():
    cal, confirmado = calendario_para_tribunal("TJSC 1G", (2026,))
    assert confirmado is True
    assert cal.eh_dia_util(date(2026, 4, 2)) is False  # Quinta-feira Santa
    assert cal.eh_dia_util(date(2027, 1, 20)) is False  # suspensão de prazo
    assert cal.eh_dia_util(date(2027, 1, 21)) is True  # suspensão terminou


def test_calendario_para_tribunal_reconhece_variacoes_de_grafia():
    cal, confirmado = calendario_para_tribunal("TJ SC 2G", (2026,))
    assert confirmado is True
    assert cal.eh_dia_util(date(2026, 6, 4)) is False  # Corpus Christi


def test_calendario_para_trt12_confirmado_e_aplica_feriados_proprios():
    cal, confirmado = calendario_para_tribunal("TRT 12 2G", (2026,))
    assert confirmado is True
    assert cal.eh_dia_util(date(2026, 8, 10)) is False
    assert cal.eh_dia_util(date(2027, 1, 20)) is False  # mesma suspensão do TJSC


def test_calendario_para_tribunal_nao_pesquisado_fica_nao_confirmado():
    cal, confirmado = calendario_para_tribunal("STJ", (2026,))
    assert confirmado is False
    # Sem dado pesquisado, cai no calendário só com feriados nacionais:
    # datas específicas do TJSC não devem aparecer aqui.
    assert cal.eh_dia_util(date(2026, 4, 2)) is True
    assert cal.eh_dia_util(date(2027, 1, 20)) is True


def test_calendario_para_tribunal_nao_confunde_trt9_com_trt12():
    cal, confirmado = calendario_para_tribunal("TRT9 1G", (2026,))
    assert confirmado is False
    assert cal.eh_dia_util(date(2026, 8, 10)) is True
