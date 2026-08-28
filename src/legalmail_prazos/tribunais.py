"""Feriados forenses e suspensões de prazo específicas por tribunal.

Diferente de :mod:`holidays` (mecanismo genérico de calendário), este
módulo guarda **dados concretos pesquisados** para tribunais específicos,
sempre com a fonte citada no docstring da função. Esses calendários são
republicados todo ano (nova portaria/resolução) — antes de usar os dados
daqui para um ano diferente do já pesquisado, confirme no site oficial do
tribunal. Nunca adicione uma data aqui "de memória"/sem fonte: um feriado
forense errado pode significar um prazo perdido de verdade.

Cobertura atual: TJSC e TRT12 (12ª Região — Santa Catarina) para 2026, que
juntos respondem pela grande maioria dos processos do escritório Becker
(ver aba ATIVOS ATUAL / PRAZOS). Qualquer outro tribunal cai no calendário
genérico (só feriados nacionais) via :func:`calendario_para_tribunal`, com
``confirmado=False`` sinalizando que feriados locais próprios não estão
cobertos e precisam ser conferidos manualmente.
"""

from __future__ import annotations

from datetime import date, timedelta

from .holidays import Calendario


def feriados_tjsc(ano: int) -> set[date]:
    """Feriados forenses próprios do TJSC, além dos nacionais.

    Fonte (2026): Resolução GP TJSC n. 1/2026 (com alterações posteriores),
    conforme https://www.tjsc.jus.br/calendario-institucional. Datas móveis
    (Semana Santa, Corpus Christi, Pentecostes) mudam todo ano — só cobrimos
    2026 aqui; confirme no site do TJSC antes de usar para outro ano.
    """

    if ano == 2026:
        return {
            date(2026, 4, 2),  # Quinta-feira Santa
            date(2026, 6, 4),  # Corpus Christi
            date(2026, 5, 25),  # Festa do Divino Espírito Santo (2ª-feira de Pentecostes)
        }
    return set()


def feriados_trt12(ano: int) -> set[date]:
    """Feriados regimentais próprios do TRT12 (12ª Região), além dos nacionais.

    Fonte (2026): Portaria "Calendário Feriados 2026" do TRT12, alterada
    pela Portaria 57/2025 (https://dspace.trt12.jus.br). Alguns feriados
    regimentais foram transferidos de data em 2026: 11/08 -> 10/08,
    28/10 -> 30/10, 08/12 -> 07/12. Lista pode não estar completa —
    confirme em https://portal.trt12.jus.br/calendario-institucional antes
    de usar para outro ano.
    """

    if ano == 2026:
        return {
            date(2026, 8, 10),
            date(2026, 10, 30),
            date(2026, 12, 7),
        }
    return set()


def suspensao_prazos_tjsc_trt12(ano: int) -> set[date]:
    """Suspensão de prazos de virada de ano comum ao TJSC e ao TRT12.

    De 20/dez a 20/jan (inclusive), mais longa que o recesso genérico do
    art. 220 do CPC (que vai só até 6/jan) — o expediente forense encerra em
    6/jan, mas a contagem de prazo só volta em 21/jan. Não confundir as
    duas coisas.

    Fonte (ano-base 2025/2026): Resolução TJ n. 30/2025 (TJSC) e Portaria
    "Calendário Feriados 2026" do TRT12 (alterada pela 57/2025) — ambas
    confirmam o mesmo período de suspensão de prazo entre 20/dez e 20/jan.
    Confirme a resolução/portaria vigente antes de aplicar para outra
    virada de ano.
    """

    dias: set[date] = set()
    d = date(ano, 12, 20)
    fim_ano = date(ano, 12, 31)
    while d <= fim_ano:
        dias.add(d)
        d += timedelta(days=1)
    d = date(ano + 1, 1, 1)
    fim = date(ano + 1, 1, 20)
    while d <= fim:
        dias.add(d)
        d += timedelta(days=1)
    return dias


def _normalizar_tribunal(tribunal: str) -> str:
    return (tribunal or "").upper().replace(" ", "").replace("-", "")


def calendario_para_tribunal(
    tribunal: str, anos: tuple[int, ...], **kwargs
) -> tuple[Calendario, bool]:
    """Monta o :class:`Calendario` apropriado para o tribunal informado.

    Retorna ``(calendario, confirmado)``. ``confirmado=False`` significa que
    não há dados pesquisados para esse tribunal neste módulo — o calendário
    devolvido só tem feriados nacionais, e feriados estaduais/regimentais
    locais podem estar faltando. Trate isso como um sinal para conferir
    manualmente antes de confiar cegamente na data calculada, nunca como
    "sem feriado nenhum".
    """

    normalizado = _normalizar_tribunal(tribunal)
    feriados_extra: set[date] = set()
    confirmado = False

    for ano in anos:
        if "TJSC" in normalizado:
            if feriados_tjsc(ano):
                confirmado = True
            feriados_extra |= feriados_tjsc(ano)
            feriados_extra |= suspensao_prazos_tjsc_trt12(ano)
        elif "TRT12" in normalizado:
            if feriados_trt12(ano):
                confirmado = True
            feriados_extra |= feriados_trt12(ano)
            feriados_extra |= suspensao_prazos_tjsc_trt12(ano)

    calendario = Calendario(anos=anos, feriados_extra=frozenset(feriados_extra), **kwargs)
    return calendario, confirmado
