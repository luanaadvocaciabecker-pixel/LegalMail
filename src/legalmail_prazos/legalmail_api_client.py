"""Implementação de :class:`LegalmailClient` sobre a API pública real do Legalmail.

Construída a partir de ``docs/legalmail-openapi.json`` (a especificação
OpenAPI da "LegalMail Public API" fornecida pelo escritório). A API real
cobre bem menos do que a automação de navegador original fazia na tela:

- **Suportado pela API**: listar a Entrada (``GET /api/v1/notices``, com
  ``prazo_status``/``tipo_prazo``/``data_limite_manifestacao`` e o texto
  completo da intimação em ``teor``), consultar o processo
  (``GET /api/v1/lawsuit/detail``, que inclusive expõe ``data_prazo`` — o
  prazo atualmente ativo do processo, gerido pela própria plataforma),
  arquivar o processo da Entrada para o Acervo
  (``POST /api/v1/lawsuit/archive``), encarregar o advogado responsável
  (``POST /api/v1/lawsuit/assign``), listar usuários do workspace
  (``GET /api/v1/users``, para resolver nome do advogado -> ``idusuarios``), e
  montar contexto para um esboço de manifestação (``listar_autos_processo``
  + ``obter_url_documento``, sobre ``GET /api/v1/lawsuit/case-files`` e
  ``GET /api/v1/lawsuit/docket-entry/url`` — mais barato e rápido que baixar
  o merge completo dos autos, que só pode ser pedido 1x a cada 3 dias).
- **Não suportado pela API** (continua manual, na interface do Legalmail):
  criar uma "tarefa" com Tipo/Descrição/Prazo — não existe endpoint para
  isso, nem para definir ``data_prazo`` diretamente; e não há nenhum
  endpoint de audiências. Os métodos correspondentes do Protocol
  (:meth:`historico_tarefas_do_processo`, :meth:`criar_tarefa`,
  :meth:`listar_audiencias`) levantam :class:`RecursoNaoSuportadoPelaApiError`
  explicando isso, em vez de simular um comportamento que a API não tem.

Custo: ``listar_entrada`` chama um endpoint pago por requisição
(``GET /api/v1/notices``, R$ 0,05 cada, cobrado só em respostas 2xx). Chame
esta rotina uma vez por dia, não em laço — ver o módulo :mod:`api_v1` para
os detalhes de rate limit e cobrança.
"""

from __future__ import annotations

import os
from datetime import date, datetime

from .api_v1 import LegalmailApiV1
from .legalmail_client import (
    AudienciaLegalmail,
    ItemEntrada,
    MovimentacaoProcesso,
    NovaTarefaLegalmail,
    TipoTarefaHistorico,
)


class RecursoNaoSuportadoPelaApiError(NotImplementedError):
    """Levantado quando a operação não existe na API pública do Legalmail.

    A operação continua possível manualmente na interface do Legalmail; ela
    só não pode ser automatizada via API hoje.
    """


def _partes_para_cliente_x_parte(partes: str | None) -> str:
    return partes or ""


def _item_entrada_a_partir_de_notice(notice: dict) -> ItemEntrada | None:
    """Converte um item de ``GET /api/v1/notices`` em :class:`ItemEntrada`.

    Retorna ``None`` quando a intimação ainda não tem processo importado no
    workspace (``idprocessos`` nulo) — sem um id de processo no Legalmail
    não é possível arquivar nem encarregar via API, então esses casos ficam
    fora do que esta rotina consegue processar automaticamente (precisam
    primeiro ser importados via ``POST /api/v1/uploads/request``, fora do
    escopo desta rotina).
    """

    id_processo = notice.get("idprocessos")
    if id_processo is None:
        return None

    data_disponibilizacao_str = notice.get("data_disponibilizacao")
    if data_disponibilizacao_str:
        data_disponibilizacao = datetime.strptime(data_disponibilizacao_str, "%Y-%m-%d").date()
    else:
        data_disponibilizacao = date.today()

    teor = notice.get("teor") or ""
    return ItemEntrada(
        id_legalmail=str(id_processo),
        numero_processo=notice.get("numero_processo") or "",
        tribunal=notice.get("tribunal") or "",
        cliente_x_parte=_partes_para_cliente_x_parte(notice.get("partes")),
        conteudo_intimacao=teor,
        data_disponibilizacao=data_disponibilizacao,
        segredo_justica=False,  # a API não expõe esse dado.
        conteudo_acessivel=teor != "",
        tipo=notice.get("tipo"),
    )


class LegalmailApiClient:
    """Adapta :class:`LegalmailApiV1` ao Protocol :class:`LegalmailClient`."""

    def __init__(self, api: LegalmailApiV1) -> None:
        self._api = api

    def listar_entrada(
        self, *, data_captura_inicio: str | None = None, data_captura_fim: str | None = None
    ) -> list[ItemEntrada]:
        """Lista a Entrada via ``GET /api/v1/notices`` (pendentes de prazo aberto).

        Pagina internamente por ``offset`` até esgotar o ``total`` retornado.
        Cada página é uma requisição paga (R$ 0,05) — para uma rotina diária
        isso é normalmente poucas páginas.
        """

        itens: list[ItemEntrada] = []
        offset = 0
        limit = 50
        while True:
            pagina = self._api.list_notices(
                data_captura_inicio=data_captura_inicio,
                data_captura_fim=data_captura_fim,
                offset=offset,
                limit=limit,
                ordenar_por="data_captura",
                ordem="asc",
            )
            for notice in pagina.get("notices", []):
                if notice.get("prazo_status") != "pendente":
                    continue
                item = _item_entrada_a_partir_de_notice(notice)
                if item is not None:
                    itens.append(item)
            offset += limit
            if offset >= pagina.get("total", 0):
                break
        return itens

    def historico_tarefas_do_processo(self, id_legalmail_processo: str) -> list[TipoTarefaHistorico]:
        raise RecursoNaoSuportadoPelaApiError(
            "a API pública do Legalmail não expõe histórico de tarefas de um processo; "
            "reaproveitar o Tipo da tarefa continua sendo um passo manual na interface"
        )

    def criar_tarefa(self, tarefa: NovaTarefaLegalmail) -> str:
        raise RecursoNaoSuportadoPelaApiError(
            "a API pública do Legalmail não tem endpoint para criar tarefa (Tipo/Descrição/Prazo); "
            "o prazo do processo (data_prazo) é somente leitura via GET /api/v1/lawsuit/detail "
            "e é gerido pela própria plataforma. Criar a tarefa continua manual na interface"
        )

    def arquivar_para_acervo(self, id_legalmail_processo: str) -> None:
        """``POST /api/v1/lawsuit/archive`` com ``fk_processo=id_legalmail_processo``."""

        self._api.lawsuit_archive(int(id_legalmail_processo))

    def encarregar_advogado(self, id_legalmail_processo: str, id_usuario: int) -> None:
        """``POST /api/v1/lawsuit/assign`` — mecanismo real de encaminhar ao
        responsável quando não há suporte a "criar tarefa" (ver seção 8)."""

        self._api.lawsuit_assign(int(id_legalmail_processo), id_usuario)

    def localizar_usuario_por_nome(self, nome: str) -> int | None:
        """Busca ``idusuarios`` pelo nome exato (case-insensitive) em ``GET /api/v1/users``."""

        for usuario in self._api.list_users():
            if usuario.get("nome", "").strip().lower() == nome.strip().lower():
                return usuario.get("idusuarios")
        return None

    def listar_autos_processo(self, id_legalmail_processo: str) -> list[MovimentacaoProcesso]:
        """``GET /api/v1/lawsuit/case-files`` — movimentações classificadas como
        autos do processo, para montar contexto de um esboço de manifestação
        sem precisar do merge completo dos autos (limitado a 1x a cada 3 dias)."""

        itens = self._api.lawsuit_case_files(int(id_legalmail_processo))
        movimentacoes = []
        for item in itens:
            data_str = item.get("data_movimentacao")
            data_movimentacao = (
                datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else date.today()
            )
            movimentacoes.append(
                MovimentacaoProcesso(
                    id_movimentacao=item["idmovimentacoes"],
                    titulo=item.get("titulo") or "",
                    data_movimentacao=data_movimentacao,
                    tipo=item.get("tipo") or "",
                )
            )
        return movimentacoes

    def obter_url_documento(self, id_movimentacao: int) -> str | None:
        """``GET /api/v1/lawsuit/docket-entry/url`` — URL pré-assinada (S3) do
        documento de uma movimentação específica dos autos."""

        resposta = self._api.docket_entry_url(id_movimentacao)
        return resposta.get("s3_url")

    def listar_audiencias(self, *, a_partir_de: date) -> list[AudienciaLegalmail]:
        raise RecursoNaoSuportadoPelaApiError(
            "a API pública do Legalmail não tem nenhum endpoint de audiências; "
            "a Parte 2 desta rotina continua dependendo de conferência manual na interface"
        )


def cliente_a_partir_do_ambiente() -> LegalmailApiClient:
    """Monta um :class:`LegalmailApiClient` real a partir de ``LEGALMAIL_API_KEY``.

    Nunca coloque o valor da chave em código ou em commits; defina a
    variável de ambiente (ver ``.env.example``).
    """

    api_key = os.environ.get("LEGALMAIL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "defina a variável de ambiente LEGALMAIL_API_KEY (ver .env.example) antes de "
            "usar o cliente real da API do Legalmail"
        )
    import requests

    return LegalmailApiClient(LegalmailApiV1(api_key, session=requests.Session()))
