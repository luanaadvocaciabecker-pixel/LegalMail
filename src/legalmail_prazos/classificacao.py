"""Classifica intimações da Entrada em audiência, perícia ou prazo normal.

A API pública do Legalmail não tem endpoint de audiências nem marca
perícias de forma estruturada (seção 11) — a única fonte disponível é o
campo ``tipo`` (estruturado, definido pela própria plataforma ao capturar a
intimação) e o texto livre em ``teor``. Por isso:

- Classificar "é uma intimação de audiência" é relativamente confiável,
  porque normalmente se apoia em ``tipo`` (ex. ``"Audiência"``), um campo
  estruturado, não em adivinhação sobre texto livre.
- Detectar "tem perícia designada" e extrair data/horário são heurísticas
  sobre texto livre (regex), e nunca devem ser tratadas como definitivas —
  quando a extração falha ou é ambígua, o campo correspondente fica em
  branco na planilha (ver ``planilha.NovaAudiencia``/``NovaPericia``) para
  preenchimento manual, em vez de inventar um valor (seção 7).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_PALAVRAS_AUDIENCIA = ("audiência", "audiencia")
_PALAVRAS_PERICIA = ("perícia", "pericia", "pericial")

_PADRAO_DATA = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_PADRAO_HORA = re.compile(r"\b(\d{1,2})[:h](\d{2})h?\b", re.IGNORECASE)


def _contem_alguma(texto: str, palavras: tuple[str, ...]) -> bool:
    texto_normalizado = (texto or "").lower()
    return any(palavra in texto_normalizado for palavra in palavras)


def eh_intimacao_de_audiencia(*, tipo: str | None, teor: str) -> bool:
    """True quando a intimação designa/trata de uma audiência.

    Prioriza o campo ``tipo`` (estruturado); cai para busca no ``teor``
    apenas quando ``tipo`` não veio preenchido pela API.
    """

    if tipo:
        return _contem_alguma(tipo, _PALAVRAS_AUDIENCIA)
    return _contem_alguma(teor, _PALAVRAS_AUDIENCIA)


def contem_designacao_pericia(teor: str) -> bool:
    """True quando o teor da intimação menciona perícia/pericial.

    Não confunda com :func:`eh_intimacao_de_audiencia`: uma intimação normal
    de prazo pode também mencionar uma perícia designada (seção 4, item 4 do
    documento de referência) — por isso esta função é independente, não
    mutuamente exclusiva com a classificação de audiência.
    """

    return _contem_alguma(teor, _PALAVRAS_PERICIA)


def sugerir_evento_audiencia(teor: str) -> str:
    """Sugere o rótulo do evento a partir de palavras-chave comuns no teor.

    Sempre em maiúsculas, no padrão usado na aba AUDIÊNCIA. Cai para
    "AUDIÊNCIA" genérico quando não reconhece o tipo específico.
    """

    texto = (teor or "").lower()
    if "instrução" in texto or "instrucao" in texto:
        return "AUDIÊNCIA DE INSTRUÇÃO"
    if "conciliação" in texto or "conciliacao" in texto:
        return "AUDIÊNCIA DE CONCILIAÇÃO"
    return "AUDIÊNCIA"


def sugerir_area_por_tribunal(tribunal: str) -> str:
    """TRABALHISTA para PJe/TRT, CÍVEL para eProc/TJ (regra da seção 9)."""

    tribunal_normalizado = (tribunal or "").upper()
    if "TRT" in tribunal_normalizado or "TST" in tribunal_normalizado:
        return "TRABALHISTA"
    return "CÍVEL"


@dataclass(frozen=True)
class ExtracaoTexto:
    """Resultado de uma extração best-effort de data/horário a partir de texto livre."""

    data: date | None
    horario: str | None

    @property
    def confirmar_manualmente(self) -> bool:
        """True quando algum dos dois campos não pôde ser extraído com confiança."""

        return self.data is None or self.horario is None


def extrair_data_e_horario(teor: str) -> ExtracaoTexto:
    """Extrai a primeira data (``dd/mm/aaaa``) e horário (``hh:mm``/``hhhmm``) do texto.

    Best-effort: quando o texto tem mais de uma data (ex. data da intimação
    e data da audiência juntas), pode pegar a errada — por isso o resultado
    deve sempre ser conferido manualmente antes de ser tratado como certo
    (``confirmar_manualmente``), nunca lançado direto sem revisão.
    """

    texto = teor or ""
    m_data = _PADRAO_DATA.search(texto)
    m_hora = _PADRAO_HORA.search(texto)

    data_extraida: date | None = None
    if m_data:
        dia, mes, ano = (int(grupo) for grupo in m_data.groups())
        try:
            data_extraida = date(ano, mes, dia)
        except ValueError:
            data_extraida = None

    horario_extraido = f"{int(m_hora.group(1)):02d}:{m_hora.group(2)}" if m_hora else None

    return ExtracaoTexto(data=data_extraida, horario=horario_extraido)
