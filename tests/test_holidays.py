from datetime import date, timedelta

from legalmail_prazos.holidays import Calendario, feriados_nacionais, pascoa, recesso_forense


def test_pascoa_datas_conhecidas():
    assert pascoa(2025) == date(2025, 4, 20)
    assert pascoa(2026) == date(2026, 4, 5)


def test_feriados_nacionais_fixos_2026():
    feriados = feriados_nacionais(2026, incluir_carnaval=False)
    assert date(2026, 1, 1) in feriados
    assert date(2026, 4, 21) in feriados
    assert date(2026, 5, 1) in feriados
    assert date(2026, 9, 7) in feriados
    assert date(2026, 10, 12) in feriados
    assert date(2026, 11, 2) in feriados
    assert date(2026, 11, 15) in feriados
    assert date(2026, 11, 20) in feriados
    assert date(2026, 12, 25) in feriados
    # Sexta-feira Santa = Páscoa - 2 dias.
    assert pascoa(2026) - timedelta(days=2) in feriados


def test_carnaval_opcional():
    com = feriados_nacionais(2026, incluir_carnaval=True)
    sem = feriados_nacionais(2026, incluir_carnaval=False)
    assert com - sem  # duas datas de carnaval a mais


def test_recesso_forense_cobre_virada_do_ano():
    dias = recesso_forense(2025)
    assert date(2025, 12, 20) in dias
    assert date(2025, 12, 31) in dias
    assert date(2025, 1, 6) in dias
    assert date(2025, 1, 7) not in dias
    assert date(2025, 12, 19) not in dias


def test_calendario_dia_util_fim_de_semana_e_feriado():
    cal = Calendario(anos=(2026,), incluir_carnaval=False)
    assert cal.eh_dia_util(date(2026, 8, 24)) is True  # segunda-feira comum
    assert cal.eh_dia_util(date(2026, 8, 22)) is False  # sábado
    assert cal.eh_dia_util(date(2026, 9, 7)) is False  # feriado nacional


def test_somar_dias_uteis_pula_fim_de_semana():
    cal = Calendario(anos=(2026,), incluir_carnaval=False)
    # 2026-08-21 é sexta-feira; +1 dia útil deve cair na segunda 2026-08-24.
    resultado = cal.somar_dias_uteis(date(2026, 8, 21), 1)
    assert resultado == date(2026, 8, 24)


def test_somar_dias_corridos_prorroga_se_cair_em_fim_de_semana():
    cal = Calendario(anos=(2026,), incluir_carnaval=False)
    # 2026-08-21 (sexta) + 2 dias corridos = domingo 2026-08-23, prorroga para segunda 2026-08-24.
    resultado = cal.somar_dias_corridos(date(2026, 8, 21), 2)
    assert resultado == date(2026, 8, 24)


def test_recesso_forense_configuravel_no_calendario():
    cal_sem = Calendario(anos=(2025, 2026), aplicar_recesso_forense=False)
    cal_com = Calendario(anos=(2025, 2026), aplicar_recesso_forense=True)
    assert cal_sem.eh_dia_util(date(2025, 12, 22)) is True
    assert cal_com.eh_dia_util(date(2025, 12, 22)) is False
