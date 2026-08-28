"""Interface de acesso ao Legalmail (seção 11 do documento de referência).

A execução original desta rotina foi feita via automação de navegador,
clicando na interface web do Legalmail (https://app.legalmail.com.br). Os
detalhes de clique/modal são específicos daquela camada de UI e não têm
lugar aqui. Este módulo define o contrato de dados que a lógica de negócio
(``rotina.py``) precisa, para que qualquer camada de acesso — API oficial do
Legalmail (se/quando exposta), exportação CSV manual, ou um adaptador de
automação de navegador — possa implementá-lo sem alterar as regras de
negócio das seções 4 a 10.

Este módulo em si não assume nenhuma credencial ou endpoint concreto — é só
o contrato. A implementação real sobre a API pública do Legalmail está em
:mod:`legalmail_prazos.legalmail_api_client` (ver ``docs/legalmail-openapi.json``
para a especificação completa); ela cobre listar a Entrada, arquivar para o
Acervo e encarregar o advogado responsável, mas não cobre criação de tarefa
nem audiências, por não existirem endpoints para isso na API hoje.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Protocol


@dataclass(frozen=True)
class ItemEntrada:
    """Um processo/intimação pendente na Entrada do Legalmail."""

    id_legalmail: str
    numero_processo: str
    tribunal: str
    cliente_x_parte: str
    conteudo_intimacao: str
    data_disponibilizacao: date
    segredo_justica: bool = False
    conteudo_acessivel: bool = True
    """False quando o teor está genuinamente bloqueado (seção 7) — nesse
    caso a rotina deve parar e reportar a limitação, nunca inventar dados."""


@dataclass(frozen=True)
class TipoTarefaHistorico:
    """Um tipo de tarefa já usado anteriormente no histórico do processo."""

    tipo: str
    descricao_resumo: str


@dataclass(frozen=True)
class NovaTarefaLegalmail:
    """Dados necessários para criar uma tarefa (seção 8)."""

    id_legalmail_processo: str
    tipo: str
    encarregado: str
    descricao: str
    prazo_legal: date
    prazo_interno: date | None = None


@dataclass(frozen=True)
class AudienciaLegalmail:
    id_legalmail: str
    numero_processo: str
    cliente: str
    evento: str
    area: str
    data: date
    horario: time
    cancelada: bool = False


class LegalmailClient(Protocol):
    """Contrato mínimo de acesso ao Legalmail exigido pela rotina.

    Qualquer implementação (API real, scraping/automação de navegador,
    importação de export CSV/planilha) deve satisfazer esta interface.
    """

    def listar_entrada(self) -> list[ItemEntrada]:
        """Lista os itens pendentes na Entrada."""
        ...

    def historico_tarefas_do_processo(self, id_legalmail_processo: str) -> list[TipoTarefaHistorico]:
        """Histórico de tarefas já criadas no processo, para reaproveitar o Tipo (seção 6)."""
        ...

    def criar_tarefa(self, tarefa: NovaTarefaLegalmail) -> str:
        """Cria a tarefa no Legalmail e retorna o id da tarefa criada."""
        ...

    def arquivar_para_acervo(self, id_legalmail_processo: str) -> None:
        """Move o processo da Entrada para o Acervo."""
        ...

    def listar_audiencias(self, *, a_partir_de: date) -> list[AudienciaLegalmail]:
        """Lista audiências (inclusive canceladas) com data a partir de ``a_partir_de``."""
        ...
