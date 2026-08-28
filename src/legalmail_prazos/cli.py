"""CLI utilitária para partes da rotina que não dependem de um cliente Legalmail real.

Cobre as operações que podem ser executadas diretamente contra a planilha e
o motor de cálculo de prazos, úteis para conferência manual. O fluxo
completo (ler a Entrada, arquivar para o Acervo, encarregar o responsável)
usa :class:`legalmail_prazos.legalmail_api_client.LegalmailApiClient`, que
requer a variável de ambiente ``LEGALMAIL_API_KEY`` (ver ``.env.example``).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .holidays import Calendario
from .planilha import (
    ABA_PRAZOS,
    carregar_processos_conhecidos,
    eh_caso_novo,
    normalizar_processo,
    processos_na_aba_prazos,
)
from .prazos import RegimeContagem, calcular_prazo
from .tribunais import calendario_para_tribunal
from openpyxl import load_workbook


def _cmd_verificar_processo(args: argparse.Namespace) -> int:
    processos_conhecidos = carregar_processos_conhecidos(Path(args.prazos_nums_json))
    if args.planilha:
        wb = load_workbook(args.planilha, data_only=False, read_only=True)
        processos_conhecidos |= processos_na_aba_prazos(wb[ABA_PRAZOS])
        wb.close()

    novo = eh_caso_novo(args.numero_processo, processos_conhecidos)
    normalizado = normalizar_processo(args.numero_processo)
    print(f"processo normalizado: {normalizado}")
    print("classificação: CASO NOVO" if novo else "classificação: CASO RECORRENTE")
    return 0


def _cmd_calcular_prazo(args: argparse.Namespace) -> int:
    data_disponibilizacao = date.fromisoformat(args.data_disponibilizacao)
    regime = RegimeContagem(args.regime)
    anos = (data_disponibilizacao.year, data_disponibilizacao.year + 1)

    if args.tribunal:
        calendario, confirmado = calendario_para_tribunal(args.tribunal, anos)
        if not confirmado:
            print(
                f"aviso, não há feriados forenses próprios pesquisados para "
                f"'{args.tribunal}' neste ano — usando só feriados nacionais, "
                "confira manualmente feriados estaduais/regimentais locais"
            )
    else:
        calendario = Calendario(anos=anos, aplicar_recesso_forense=args.recesso_forense)

    prazo = calcular_prazo(
        data_disponibilizacao=data_disponibilizacao,
        quantidade_dias=args.quantidade_dias,
        regime=regime,
        calendario=calendario,
        aplicar_margem_seguranca=not args.sem_margem_seguranca,
    )
    print(f"início da contagem: {prazo.inicio_contagem.isoformat()}")
    print(f"data final legal (fatal): {prazo.data_final_legal.isoformat()}")
    print(f"data final interna (com margem de segurança): {prazo.data_final_interna.isoformat()}")
    print(
        "lembrete, se o eProc/PJe já informar as datas de início e fim da contagem, "
        "use essas datas diretamente e trate este cálculo apenas como conferência cruzada"
    )
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="conciliacao-legalmail-prazos")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    p_verificar = subparsers.add_parser(
        "verificar-processo",
        help="Classifica um processo como caso novo ou recorrente (seção 4).",
    )
    p_verificar.add_argument("numero_processo")
    p_verificar.add_argument("--prazos-nums-json", required=True)
    p_verificar.add_argument("--planilha", help="Caminho do PRAZOS BECKER.xlsx (opcional)")
    p_verificar.set_defaults(func=_cmd_verificar_processo)

    p_prazo = subparsers.add_parser(
        "calcular-prazo",
        help="Calcula a data final de um prazo a partir da disponibilização eletrônica (seção 5).",
    )
    p_prazo.add_argument("data_disponibilizacao", help="AAAA-MM-DD")
    p_prazo.add_argument("quantidade_dias", type=int)
    p_prazo.add_argument(
        "--regime",
        choices=[r.value for r in RegimeContagem],
        required=True,
    )
    p_prazo.add_argument(
        "--recesso-forense",
        action="store_true",
        help=(
            "Aplicar o recesso forense genérico do art. 220 do CPC (só para prazos "
            "cíveis). Ignorado se --tribunal for informado."
        ),
    )
    p_prazo.add_argument(
        "--tribunal",
        help=(
            "Tribunal do processo (ex. 'TJSC 1G', 'TRT12 2G'), para usar o calendário "
            "forense específico pesquisado em legalmail_prazos.tribunais, em vez do "
            "recesso genérico. Avisa quando não há dado pesquisado para o tribunal."
        ),
    )
    p_prazo.add_argument("--sem-margem-seguranca", action="store_true")
    p_prazo.set_defaults(func=_cmd_calcular_prazo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
