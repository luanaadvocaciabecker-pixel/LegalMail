from datetime import date

from legalmail_prazos.classificacao import (
    contem_designacao_pericia,
    eh_intimacao_de_audiencia,
    extrair_data_e_horario,
    sugerir_area_por_tribunal,
    sugerir_evento_audiencia,
)


def test_eh_intimacao_de_audiencia_usa_tipo_estruturado_primeiro():
    assert eh_intimacao_de_audiencia(tipo="Audiência", teor="qualquer coisa") is True
    assert eh_intimacao_de_audiencia(tipo="Intimação", teor="sem relação com pauta") is False


def test_eh_intimacao_de_audiencia_cai_para_teor_quando_tipo_ausente():
    assert eh_intimacao_de_audiencia(tipo=None, teor="Designo AUDIÊNCIA de instrução") is True
    assert eh_intimacao_de_audiencia(tipo=None, teor="Manifeste-se em 15 dias") is False


def test_contem_designacao_pericia():
    assert contem_designacao_pericia("Nomeio perito para realização de perícia médica") is True
    assert contem_designacao_pericia("Manifeste-se sobre a contestação") is False


def test_contem_designacao_pericia_nao_confunde_com_audiencia():
    # uma intimação de audiência não deve, por si só, disparar perícia
    assert contem_designacao_pericia("Designo audiência de instrução para o dia 10/10/2026") is False


def test_sugerir_evento_audiencia():
    assert sugerir_evento_audiencia("Audiência de instrução designada") == "AUDIÊNCIA DE INSTRUÇÃO"
    assert sugerir_evento_audiencia("Audiência de conciliação designada") == "AUDIÊNCIA DE CONCILIAÇÃO"
    assert sugerir_evento_audiencia("Audiência designada sem mais detalhes") == "AUDIÊNCIA"


def test_sugerir_area_por_tribunal():
    assert sugerir_area_por_tribunal("TRT12 1G") == "TRABALHISTA"
    assert sugerir_area_por_tribunal("TST") == "TRABALHISTA"
    assert sugerir_area_por_tribunal("TJSC 1G") == "CÍVEL"
    assert sugerir_area_por_tribunal("") == "CÍVEL"


def test_extrair_data_e_horario_com_sucesso():
    resultado = extrair_data_e_horario(
        "Fica designada audiência de instrução para o dia 06/05/2026, às 14:30h."
    )
    assert resultado.data == date(2026, 5, 6)
    assert resultado.horario == "14:30"
    assert resultado.confirmar_manualmente is False


def test_extrair_data_e_horario_aceita_hora_com_h_sem_dois_pontos():
    resultado = extrair_data_e_horario("Audiência marcada para 10/10/2026 às 9h30")
    assert resultado.horario == "09:30"


def test_extrair_data_e_horario_sem_correspondencia_fica_none():
    resultado = extrair_data_e_horario("Manifeste-se sobre a petição da parte contrária.")
    assert resultado.data is None
    assert resultado.horario is None
    assert resultado.confirmar_manualmente is True


def test_extrair_data_e_horario_ignora_data_invalida():
    resultado = extrair_data_e_horario("Documento datado de 31/02/2026 (data inexistente).")
    assert resultado.data is None
    assert resultado.confirmar_manualmente is True
