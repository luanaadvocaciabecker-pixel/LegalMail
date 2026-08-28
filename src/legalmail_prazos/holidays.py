"""Calendário de dias não úteis usado no cálculo de prazos.

Este módulo cobre os feriados nacionais fixos e móveis (cálculo pela
Páscoa) e o recesso forense do art. 220 do CPC. Feriados estaduais e
municipais variam por tribunal/comarca e por isso NÃO são hardcoded aqui:
devem ser informados pelo escritório via ``feriados_extra`` ao construir um
:class:`Calendario`. Ver seção 5, item 9 do documento de referência
(docs/CONFIGURACOES_ROTINA_CONCILIACAO_LEGALMAIL_PRAZOS.md) sobre a
necessidade de confirmar a vigência de cada norma antes de aplicar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


def pascoa(ano: int) -> date:
    """Data da Páscoa no ano informado (algoritmo de Gauss/Meeus)."""

    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados_nacionais(ano: int, *, incluir_carnaval: bool = True) -> set[date]:
    """Feriados nacionais (Lei 6.802/1980 e alterações) para o ano informado.

    ``incluir_carnaval`` está ligado por padrão porque, embora Carnaval não
    seja feriado nacional por lei (é ponto facultativo), a quase totalidade
    dos tribunais suspende o expediente forense nessas datas. Confirme o
    calendário forense do tribunal específico antes de confiar cegamente
    nisso (item 5.8 do documento de referência).
    """

    p = pascoa(ano)
    feriados = {
        date(ano, 1, 1),  # Confraternização Universal
        date(ano, 4, 21),  # Tiradentes
        date(ano, 5, 1),  # Dia do Trabalho
        date(ano, 9, 7),  # Independência do Brasil
        date(ano, 10, 12),  # Nossa Senhora Aparecida
        date(ano, 11, 2),  # Finados
        date(ano, 11, 15),  # Proclamação da República
        date(ano, 12, 25),  # Natal
        p - timedelta(days=2),  # Sexta-feira Santa
    }
    if ano >= 2024:
        # Dia Nacional de Zumbi e da Consciência Negra (Lei 14.759/2023).
        feriados.add(date(ano, 11, 20))
    if incluir_carnaval:
        segunda = p - timedelta(days=48)
        feriados.add(segunda)
        feriados.add(segunda + timedelta(days=1))
    return feriados


def recesso_forense(ano: int) -> set[date]:
    """Dias do recesso forense de 20/dez a 06/jan (art. 220 do CPC).

    Aplica-se apenas a prazos processuais cíveis (Justiça Estadual/Federal
    comum). Não usar para prazos trabalhistas ou de Juizados Especiais sem
    confirmar a regra do tribunal específico.
    """

    dias: set[date] = set()
    d = date(ano, 12, 20)
    fim = date(ano, 12, 31)
    while d <= fim:
        dias.add(d)
        d += timedelta(days=1)
    d = date(ano, 1, 1)
    fim = date(ano, 1, 6)
    while d <= fim:
        dias.add(d)
        d += timedelta(days=1)
    return dias


@dataclass
class Calendario:
    """Calendário de dias não úteis para um intervalo de anos.

    Parameters
    ----------
    anos:
        Anos a pré-carregar (feriados nacionais móveis dependem do ano).
    incluir_carnaval:
        Ver :func:`feriados_nacionais`.
    aplicar_recesso_forense:
        Se ``True``, os dias do recesso do art. 220 do CPC também contam
        como não úteis. Use ``True`` para prazos cíveis e ``False`` para
        prazos trabalhistas/Juizados, salvo confirmação em contrário.
    feriados_extra:
        Feriados estaduais/municipais específicos do tribunal/comarca do
        processo, que o escritório deve manter atualizados (não incluídos
        por padrão neste módulo).
    """

    anos: tuple[int, ...]
    incluir_carnaval: bool = True
    aplicar_recesso_forense: bool = False
    feriados_extra: frozenset[date] = field(default_factory=frozenset)
    _dias_nao_uteis: set[date] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        dias: set[date] = set()
        for ano in self.anos:
            dias |= feriados_nacionais(ano, incluir_carnaval=self.incluir_carnaval)
            if self.aplicar_recesso_forense:
                dias |= recesso_forense(ano)
        dias |= set(self.feriados_extra)
        self._dias_nao_uteis = dias

    def eh_dia_util(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self._dias_nao_uteis

    def proximo_dia_util(self, d: date) -> date:
        cursor = d
        while not self.eh_dia_util(cursor):
            cursor += timedelta(days=1)
        return cursor

    def somar_dias_uteis(self, inicio: date, quantidade: int) -> date:
        """Soma ``quantidade`` dias úteis a partir de ``inicio`` (exclusivo).

        Segue a regra de exclusão do dia do começo (CPC art. 224): o dia
        ``inicio`` nunca é contado, mesmo que seja útil.
        """

        cursor = inicio
        restantes = quantidade
        while restantes > 0:
            cursor += timedelta(days=1)
            if self.eh_dia_util(cursor):
                restantes -= 1
        return cursor

    def somar_dias_corridos(self, inicio: date, quantidade: int) -> date:
        """Soma dias corridos e prorroga se cair em dia não útil (CPC art. 224, §1º)."""

        fim = inicio + timedelta(days=quantidade)
        return self.proximo_dia_util(fim)
