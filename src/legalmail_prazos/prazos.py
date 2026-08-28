"""Cálculo de prazos processuais (seção 5 do documento de referência).

Este módulo implementa apenas a mecânica de contagem descrita na
especificação. Ele NÃO substitui a conferência jurídica humana: sempre que
o eProc/PJe informar explicitamente a data inicial e final da contagem,
essas datas devem prevalecer (item 5.10) — use :func:`Prazo.a_partir_de_tribunal`
nesse caso e trate o cálculo manual apenas como conferência cruzada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from .holidays import Calendario


class RegimeContagem(str, Enum):
    """Regime de contagem de prazo aplicável ao ato processual."""

    CIVEL_DIAS_UTEIS = "civel_dias_uteis"
    """CPC arts. 218 a 232 (dias úteis, redação da Lei 13.105/2015)."""

    TRABALHISTA_DIAS_UTEIS = "trabalhista_dias_uteis"
    """CLT art. 775 e seguintes, na redação da Lei 13.467/2017 (reforma)."""

    JUIZADO_ESPECIAL_DIAS_CORRIDOS = "juizado_especial_dias_corridos"
    """Lei 9.099/95, dias corridos (Enunciado FONAJE 165)."""


MARGEM_SEGURANCA_DIAS_UTEIS = 2
"""Margem interna padrão: prazo interno = prazo legal - 2 dias úteis.

Não se aplica a janelas puramente administrativas de ciência (ex.: prazo de
1 dia só para anotação/ciência) — nesse caso passe
``aplicar_margem_seguranca=False`` para :func:`calcular_prazo`.
"""


@dataclass(frozen=True)
class Prazo:
    """Resultado do cálculo de um prazo, com data legal e data interna."""

    data_disponibilizacao: date
    """Data em que a intimação foi disponibilizada eletronicamente."""

    inicio_contagem: date
    """Primeiro dia útil após a disponibilização (marco inicial real)."""

    data_final_legal: date
    """Último dia do prazo perante o tribunal (data fatal)."""

    data_final_interna: date
    """Data final recomendada internamente (com margem de segurança), se aplicável."""

    regime: RegimeContagem
    quantidade_dias: int
    estimado_por_analogia: bool = False
    """True quando a quantidade de dias não veio expressa no despacho e foi
    inferida por analogia com tarefa anterior semelhante (item 5.11) — deve
    ser sinalizado ao usuário como estimativa sujeita a confirmação."""

    @classmethod
    def a_partir_de_tribunal(
        cls,
        *,
        data_disponibilizacao: date,
        inicio_contagem: date,
        data_final_legal: date,
        regime: RegimeContagem,
        quantidade_dias: int,
        calendario: Calendario,
        aplicar_margem_seguranca: bool = True,
    ) -> "Prazo":
        """Constrói um :class:`Prazo` a partir de datas já informadas pelo
        próprio sistema do tribunal (eProc/PJe), conforme item 5.10 — usar
        essas datas diretamente em vez de recalcular manualmente.
        """

        data_final_interna = data_final_legal
        if aplicar_margem_seguranca:
            data_final_interna = _subtrair_dias_uteis(
                data_final_legal, MARGEM_SEGURANCA_DIAS_UTEIS, calendario
            )
        return cls(
            data_disponibilizacao=data_disponibilizacao,
            inicio_contagem=inicio_contagem,
            data_final_legal=data_final_legal,
            data_final_interna=data_final_interna,
            regime=regime,
            quantidade_dias=quantidade_dias,
        )


def _subtrair_dias_uteis(d: date, quantidade: int, calendario: Calendario) -> date:
    cursor = d
    restantes = quantidade
    while restantes > 0:
        cursor -= timedelta(days=1)
        if calendario.eh_dia_util(cursor):
            restantes -= 1
    return cursor


def marco_inicial_por_disponibilizacao(
    data_disponibilizacao: date, calendario: Calendario
) -> date:
    """Aplica a Resolução CNJ 455/2022 c/c art. 224 c/c art. 231, V do CPC.

    Quando a intimação é disponibilizada em dia útil, considera-se realizada
    no primeiro dia útil seguinte; o prazo então começa a correr a partir do
    primeiro dia útil após essa data (dia do começo sempre excluído).
    """

    considerada_realizada = calendario.proximo_dia_util(
        data_disponibilizacao + timedelta(days=1)
        if calendario.eh_dia_util(data_disponibilizacao)
        else data_disponibilizacao
    )
    return considerada_realizada


def calcular_prazo(
    *,
    data_disponibilizacao: date,
    quantidade_dias: int,
    regime: RegimeContagem,
    calendario: Calendario,
    aplicar_margem_seguranca: bool = True,
    estimado_por_analogia: bool = False,
) -> Prazo:
    """Calcula um prazo a partir da data de disponibilização eletrônica.

    Use apenas como cálculo manual de conferência cruzada quando o próprio
    eProc/PJe já informar as datas de início/fim da contagem (item 5.10);
    nesse caso prefira :meth:`Prazo.a_partir_de_tribunal`.
    """

    inicio = marco_inicial_por_disponibilizacao(data_disponibilizacao, calendario)

    if regime == RegimeContagem.JUIZADO_ESPECIAL_DIAS_CORRIDOS:
        data_final_legal = calendario.somar_dias_corridos(inicio, quantidade_dias)
    else:
        # CIVEL_DIAS_UTEIS e TRABALHISTA_DIAS_UTEIS contam em dias úteis.
        data_final_legal = calendario.somar_dias_uteis(inicio, quantidade_dias)

    data_final_interna = data_final_legal
    if aplicar_margem_seguranca:
        data_final_interna = _subtrair_dias_uteis(
            data_final_legal, MARGEM_SEGURANCA_DIAS_UTEIS, calendario
        )

    return Prazo(
        data_disponibilizacao=data_disponibilizacao,
        inicio_contagem=inicio,
        data_final_legal=data_final_legal,
        data_final_interna=data_final_interna,
        regime=regime,
        quantidade_dias=quantidade_dias,
        estimado_por_analogia=estimado_por_analogia,
    )
